"""Diagnostics for bug reports.

Safe to attach to a public issue: no email, password, token, address or
notification body; contract, supply point, meter, profile, equipment and bill
numbers become CONTRATTO_1, POD_1, CONTATORE_1, BOLLETTA_1, DOTAZIONE_1...
"""
from __future__ import annotations

import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CONF_CONTRATTI, CONF_ID_UTENTE, DOMAIN

DA_NASCONDERE = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_ID_UTENTE,
    "indirizzo",
    "descrizione",
    "sottotitolo",
}
CODICI = (
    ("contratto", "CONTRATTO"),
    ("pod", "POD"),
    ("contatore", "CONTATORE"),
    ("profilo", "PROFILO"),
    ("raggruppamento", "RAGGRUPPAMENTO"),
)


def _aggiungi_sostituzione(sostituzioni: dict[str, str], codice: Any, etichetta: str) -> None:
    if not codice:
        return
    testo = str(codice).strip()
    if not testo:
        return
    sostituzioni.setdefault(testo, etichetta)
    # statistic_id lowercases and slugifies POD/contract codes: anonymize that form too.
    slug = re.sub(r"[^a-z0-9]+", "_", testo.lower()).strip("_")
    if slug and slug != testo:
        sostituzioni.setdefault(slug, etichetta.lower())


def _sostituzioni(entry: ConfigEntry, contratti: list[dict[str, Any]]) -> dict[str, str]:
    sostituzioni: dict[str, str] = {}
    if email := entry.data.get(CONF_EMAIL):
        sostituzioni[str(email)] = "EMAIL"
        sostituzioni.setdefault(str(email).lower(), "EMAIL")
    if id_utente := entry.data.get(CONF_ID_UTENTE):
        sostituzioni[str(id_utente)] = "UTENTE"
    for indice, contratto in enumerate(contratti, start=1):
        for campo, etichetta in CODICI:
            _aggiungi_sostituzione(sostituzioni, contratto.get(campo), f"{etichetta}_{indice}")
    return sostituzioni


def _anonimizza(valore: Any, coppie: list[tuple[str, str]]) -> Any:
    """Replace the codes in keys and values, longest first."""
    if isinstance(valore, dict):
        return {_anonimizza(k, coppie): _anonimizza(v, coppie) for k, v in valore.items()}
    if isinstance(valore, list | tuple):
        return [_anonimizza(v, coppie) for v in valore]
    if isinstance(valore, str):
        for codice, etichetta in coppie:
            valore = valore.replace(codice, etichetta)
    return valore


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    contratti = list(entry.data.get(CONF_CONTRATTI) or [])
    integrazione = await async_get_integration(hass, DOMAIN)
    coordinator = getattr(entry, "runtime_data", None)

    diagnostica: dict[str, Any] = {
        "versione_integrazione": str(integrazione.version),
        "versione_home_assistant": HA_VERSION,
        "lingua": hass.config.language,
        "fuso_orario": hass.config.time_zone,
        "entry": {
            "stato": entry.state.value,
            "data": async_redact_data(
                {**entry.data, CONF_CONTRATTI: [async_redact_data(c, DA_NASCONDERE) for c in contratti]},
                DA_NASCONDERE,
            ),
        },
    }
    sostituzioni = _sostituzioni(entry, contratti)
    if coordinator is not None:
        dati_coordinator = coordinator.data or {}
        prossimo_contatore = len(contratti) + 1
        prossimo_contratto = len(contratti) + 1
        prossima_dotazione = 1
        numeri_bollette: dict[str, None] = {}

        for dati in dati_coordinator.values():
            for lettura in (*dati.letture, *dati.autoletture):
                if lettura.contatore and lettura.contatore not in sostituzioni:
                    _aggiungi_sostituzione(
                        sostituzioni, lettura.contatore, f"CONTATORE_{prossimo_contatore}"
                    )
                    prossimo_contatore += 1
            for bolletta in dati.bollette:
                numeri_bollette.setdefault(bolletta.numero, None)
                if bolletta.stornata_da:
                    numeri_bollette.setdefault(bolletta.stornata_da, None)
                for codice_contratto in bolletta.contratti:
                    if codice_contratto not in sostituzioni:
                        _aggiungi_sostituzione(
                            sostituzioni, codice_contratto, f"CONTRATTO_{prossimo_contratto}"
                        )
                        prossimo_contratto += 1
            if dati.rifiuti:
                for dot in dati.rifiuti.dotazioni:
                    if dot.codice and dot.codice not in sostituzioni:
                        _aggiungi_sostituzione(
                            sostituzioni, dot.codice, f"DOTAZIONE_{prossima_dotazione}"
                        )
                        prossima_dotazione += 1
                for sv in (
                    *dati.rifiuti.svuotamenti_anno_corrente,
                    *dati.rifiuti.svuotamenti_anno_precedente,
                ):
                    if sv.codice_dotazione and sv.codice_dotazione not in sostituzioni:
                        _aggiungi_sostituzione(
                            sostituzioni, sv.codice_dotazione, f"DOTAZIONE_{prossima_dotazione}"
                        )
                        prossima_dotazione += 1

        for indice, numero in enumerate(numeri_bollette, start=1):
            sostituzioni.setdefault(numero, f"BOLLETTA_{indice}")

        account_dict = coordinator.dati_account.come_dict()
        account_dict["notifiche"] = [
            async_redact_data(n, DA_NASCONDERE) for n in account_dict.get("notifiche") or []
        ]
        diagnostica["coordinator"] = {
            "ultimo_aggiornamento_riuscito": coordinator.last_update_success,
            "intervallo": str(coordinator.update_interval),
            "ultimo_accesso": coordinator.ultimo_accesso,
            "ultimo_errore": coordinator.ultimo_errore,
            "serie_scritte": coordinator.serie_scritte,
            "account": account_dict,
            "dati": {numero: dati.come_dict() for numero, dati in dati_coordinator.items()},
        }
    coppie = sorted(sostituzioni.items(), key=lambda voce: len(voce[0]), reverse=True)
    return _anonimizza(diagnostica, coppie)
