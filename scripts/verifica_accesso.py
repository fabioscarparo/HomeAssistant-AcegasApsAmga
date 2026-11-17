"""Check the login and the data against a real account, without Home Assistant.

    python scripts/verifica_accesso.py

Asks for email and password, logs in like the integration, lists the
contracts and, for each water contract, the readings and the series the
Energy Dashboard would get. Nothing is saved unless you pass --salva: then
the raw answers go to verifica_*.json (personal data, never commit them).

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
    for modulo in ("const", "auth", "api", "letture"):
        spec = importlib.util.spec_from_file_location(f"{nome}.{modulo}", PACCHETTO / f"{modulo}.py")
        moduli[modulo] = importlib.util.module_from_spec(spec)
        sys.modules[f"{nome}.{modulo}"] = moduli[modulo]
        spec.loader.exec_module(moduli[modulo])
    return moduli["auth"], moduli["api"], moduli["letture"]


async def main(salva: bool) -> int:
    auth, api, lt = _carica_moduli()
    email = input("Email dei Servizi Online: ").strip()
    password = getpass.getpass("Password: ")

    async with aiohttp.ClientSession(cookie_jar=auth.nuovo_cookie_jar()) as sessione:
        try:
            token = await auth.AuthClient(sessione).async_login(email, password)
        except auth.AuthError as err:
            print(f"\nAccesso non riuscito ({type(err).__name__}): {err}")
            return 1
        print(f"\nAccesso riuscito. Token valido per {int(token.scadenza - datetime.now().timestamp())} s, "
              f"refresh token {'presente' if token.refresh_token else 'assente'}.")

        if token.refresh_token:
            try:
                await auth.AuthClient(sessione).async_refresh(token.refresh_token)
                print("Rinnovo del token: ok.")
            except auth.AuthError as err:
                print(f"Rinnovo del token non riuscito ({type(err).__name__}): {err}")

        client = api.ApiClient(sessione, token.access_token)
        contratti = await client.async_contratti_account()
        print(f"\nContratti trovati: {len(contratti)}")
        for profilo, grezzo in contratti:
            contratto = api.contratto_da_api(profilo, grezzo)
            print(f"- {contratto['servizio']} {contratto['contratto']} ({contratto['stato']}), "
                  f"POD {contratto['pod']}, contatore {contratto['modello']}")
            if contratto["servizio"] not in ("WATER", "GAS"):
                continue

            archivio = await client.async_letture(profilo, contratto["servizio"], contratto["contratto"])
            letture = lt.estrai_letture(archivio)
            print(f"  {len(letture)} letture, {len(lt.ancore(letture))} reali:")
            for lettura in letture:
                print(f"    {lettura.giorno}  {lettura.valore:>8.1f} m³  {lettura.tipo}")
            righe = lt.serie_oraria(letture, datetime.now(UTC))
            if righe:
                # Days in Italian time, like the portal.
                inizio, fine = (righe[i]["start"].astimezone(lt.FUSO) for i in (0, -1))
                print(f"  Serie Energia: {len(righe)} ore, dal {inizio:%d/%m/%Y} "
                      f"al {fine:%d/%m/%Y}, totale {righe[-1]['sum']:.1f} m³")
            if periodo := lt.ultimo_periodo(letture):
                print(f"  Ultimo periodo: {periodo['dal']} - {periodo['al']}, {periodo['consumo']:.1f} m³, "
                      f"{periodo['media_giornaliera'] * 1000:.0f} L al giorno")

            if salva:
                file = Path(f"verifica_{contratto['contratto']}.json")
                file.write_text(json.dumps({
                    "contratto": grezzo,
                    "letture": archivio,
                    "consumi": await client.async_consumi(profilo, contratto["contratto"]),
                    "finestra": await client.async_finestra_autolettura(profilo, contratto["contratto"]),
                }, indent=1, ensure_ascii=False))
                print(f"  Risposte salvate in {file} (dati personali: non condividerle)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salva", action="store_true", help="salva le risposte grezze in verifica_*.json")
    sys.exit(asyncio.run(main(parser.parse_args().salva)))
