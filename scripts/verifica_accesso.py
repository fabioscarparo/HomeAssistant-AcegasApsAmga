"""Check the login and the data against a real account, without Home Assistant.

    python scripts/verifica_accesso.py

Asks for email and password, logs in like the integration, lists the
contracts and, for each supported contract, prints readings, waste data,
and profile bills. Nothing is saved unless you pass --salva: then the raw
answers go to verifica_*.json (personal data, never commit them).

Needs only aiohttp.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import importlib.util
import json
import sys
import types
from datetime import UTC, datetime
from pathlib import Path

import aiohttp

PACCHETTO = Path(__file__).resolve().parent.parent / "custom_components" / "acegasapsamga"


def _carica_moduli():
    """Load the integration's pure modules without its __init__ (which needs Home Assistant)."""
    nome = "acegasapsamga_verifica"
    pacchetto = types.ModuleType(nome)
    pacchetto.__path__ = [str(PACCHETTO)]
    sys.modules[nome] = pacchetto
    moduli = {}
    for modulo in ("const", "auth", "letture", "api", "bollette", "rifiuti"):
        spec = importlib.util.spec_from_file_location(f"{nome}.{modulo}", PACCHETTO / f"{modulo}.py")
        moduli[modulo] = importlib.util.module_from_spec(spec)
        sys.modules[f"{nome}.{modulo}"] = moduli[modulo]
        spec.loader.exec_module(moduli[modulo])
    return (
        moduli["const"],
        moduli["auth"],
        moduli["api"],
        moduli["letture"],
        moduli["bollette"],
        moduli["rifiuti"],
    )


def _unita(contratto: dict) -> str:
    servizio = contratto["servizio"]
    if servizio == "ELECTRIC":
        return "kWh"
    if servizio == "HEATING":
        return "MWh" if str(contratto.get("unita") or "").lower() == "mwh" else "kWh"
    return "m³"


async def main(salva: bool) -> int:
    const, auth, api, lt, bl, rf = _carica_moduli()
    email = input("Email dei Servizi Online: ").strip()
    password = getpass.getpass("Password: ")

    async with aiohttp.ClientSession(cookie_jar=auth.nuovo_cookie_jar()) as sessione:
        try:
            token = await auth.AuthClient(sessione).async_login(email, password)
        except auth.AuthError as err:
            print(f"\nAccesso non riuscito ({type(err).__name__}): {err}")
            return 1
        print(
            f"\nAccesso riuscito. Token valido per {int(token.scadenza - datetime.now().timestamp())} s, "
            f"refresh token {'presente' if token.refresh_token else 'assente'}."
        )

        if token.refresh_token:
            try:
                token = await auth.AuthClient(sessione).async_refresh(token.refresh_token)
                print("Rinnovo del token: ok.")
            except auth.AuthError as err:
                print(f"Rinnovo del token non riuscito ({type(err).__name__}): {err}")

        client = api.ApiClient(sessione, token.access_token)
        try:
            utente = await client.async_utente()
            print(
                f"Password scade il: {utente.get('scadenza_password') or 'n/d'} "
                f"(rinnovo={utente.get('rinnovo_password')}, condizioni={utente.get('nuove_condizioni_accettate')})"
            )
        except api.ApiError as err:
            print(f"Stato account non disponibile: {err}")

        contratti = await client.async_contratti_account()
        print(f"\nContratti trovati: {len(contratti)}")
        for profilo, grezzo in contratti:
            contratto = api.contratto_da_api(profilo, grezzo)
            print(
                f"- {contratto['servizio']} {contratto['contratto']} ({contratto['stato']}), "
                f"POD {contratto['pod']}, contatore {contratto['modello']}"
            )
            if contratto["servizio"] == const.SERVIZIO_AMBIENTE:
                dot = rf.estrai_dotazioni(
                    await client.async_dotazioni_rifiuti(profilo, contratto["contratto"])
                )
                rsu = await client.async_svuotamenti_rifiuti(
                    profilo, contratto["contratto"], tipo="RSU", anno="CURRENT"
                )
                sv, vol = rf.estrai_svuotamenti(rsu)
                print(f"  Dotazioni attive: {sum(1 for d in dot if d.attiva)}/{len(dot)}, "
                      f"svuotamenti RSU anno corrente: {len(sv)} ({vol} L)")
                continue

            if contratto["servizio"] not in const.SERVIZI_CONSUMO:
                continue

            unita = _unita(contratto)
            archivio = await client.async_letture(profilo, contratto["servizio"], contratto["contratto"])
            letture = lt.estrai_letture(archivio)
            print(f"  {len(letture)} letture, {len(lt.ancore(letture))} reali:")
            for lettura in letture:
                fasce = f"  {dict(lettura.fasce)}" if lettura.fasce else ""
                print(f"    {lettura.giorno}  {lettura.valore:>8.1f} {unita}  {lettura.tipo}{fasce}")
            righe = lt.serie_oraria(letture, datetime.now(UTC))
            if righe:
                inizio, fine = (righe[i]["start"].astimezone(lt.FUSO) for i in (0, -1))
                print(
                    f"  Serie Energia: {len(righe)} ore, dal {inizio:%d/%m/%Y} "
                    f"al {fine:%d/%m/%Y}, totale {righe[-1]['sum']:.1f} {unita}"
                )
            if periodo := lt.ultimo_periodo(letture):
                if contratto["servizio"] == const.SERVIZIO_ACQUA:
                    media = f"{periodo['media_giornaliera'] * 1000:.0f} L al giorno"
                else:
                    media = f"{periodo['media_giornaliera']:.2f} {unita} al giorno"
                print(
                    f"  Ultimo periodo: {periodo['dal']} - {periodo['al']}, "
                    f"{periodo['consumo']:.1f} {unita}, {media}"
                )

            if salva:
                file = Path(f"verifica_{contratto['contratto']}.json")
                file.write_text(
                    json.dumps(
                        {
                            "contratto": grezzo,
                            "letture": archivio,
                            "consumi": await client.async_consumi(profilo, contratto["contratto"]),
                            "finestra": await client.async_finestra_autolettura(
                                profilo, contratto["contratto"]
                            ),
                        },
                        indent=1,
                        ensure_ascii=False,
                    )
                )
                print(f"  Risposte salvate in {file} (dati personali: non condividerle)")

        for indice, profilo in enumerate(dict.fromkeys(p for p, _ in contratti), start=1):
            try:
                info = await client.async_profilo(profilo)
                raggruppamento = info.get("raggruppamento")
                grezze = await client.async_bollette(profilo, raggruppamento)
                pagamenti = await client.async_pagamenti_bollette(profilo)
            except api.ApiError as err:
                print(f"\nBollette del profilo {indice} non disponibili: {err}")
                continue
            bollette = bl.applica_pagamenti(bl.estrai_bollette(grezze), pagamenti)
            print(
                f"\nBollette del profilo {indice} (raggruppate per {raggruppamento}): {len(bollette)}"
            )
            for b in bollette:
                pag = f"  pagata il {b.data_pagamento}" if b.data_pagamento else ""
                print(
                    f"    {b.numero}  emessa {b.emissione}  scade {b.scadenza}  {b.importo:>8.2f} €  "
                    f"residuo {b.residuo:.2f} €  {b.stato}"
                    f"{'  domiciliata' if b.domiciliata else ''}{pag}"
                )
            print(
                f"  Da pagare: {bl.totale_da_pagare(bollette):.2f} €, "
                f"prossima scadenza: {bl.prossima_scadenza(bollette) or 'nessuna'}"
            )
            if salva:
                file = Path(f"verifica_bollette_{indice}.json")
                file.write_text(json.dumps(grezze, indent=1, ensure_ascii=False))
                print(f"  Risposte salvate in {file} (dati personali: non condividerle)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--salva", action="store_true", help="salva le risposte grezze in verifica_*.json"
    )
    sys.exit(asyncio.run(main(parser.parse_args().salva)))
