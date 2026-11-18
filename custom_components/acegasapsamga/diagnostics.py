"""Diagnostics for bug reports.

Safe to attach to a public issue: no email, password or token, and contract,
supply point, meter, profile and bill numbers become CONTRATTO_1, POD_1,
BOLLETTA_1...
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CONF_CONTRATTI, CONF_ID_UTENTE, DOMAIN

DA_NASCONDERE = {CONF_EMAIL, CONF_PASSWORD, CONF_ID_UTENTE, "indirizzo"}
CODICI = (("contratto", "CONTRATTO"), ("pod", "POD"), ("contatore", "CONTATORE"), ("profilo", "PROFILO"))


def _sostituzioni(contratti: list[dict[str, Any]]) -> dict[str, str]:
    sostituzioni: dict[str, str] = {}
    for indice, contratto in enumerate(contratti, start=1):
        for campo, etichetta in CODICI:
            if contratto.get(campo):
                sostituzioni.setdefault(str(contratto[campo]), f"{etichetta}_{indice}")
    return sostituzioni


def _anonimizza(valore: Any, sostituzioni: dict[str, str]) -> Any:
    """Replace the codes in keys and values."""
    if isinstance(valore, dict):
        return {
            _anonimizza(k, sostituzioni): _anonimizza(v, sostituzioni) for k, v in valore.items()
        }
    if isinstance(valore, list | tuple):
        return [_anonimizza(v, sostituzioni) for v in valore]
    if isinstance(valore, str):
        for codice, etichetta in sostituzioni.items():
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
    sostituzioni = _sostituzioni(contratti)
    if coordinator is not None:
        numeri = dict.fromkeys(
            b.numero for dati in (coordinator.data or {}).values() for b in dati.bollette
        )
        for indice, numero in enumerate(numeri, start=1):
            sostituzioni.setdefault(numero, f"BOLLETTA_{indice}")
        diagnostica["coordinator"] = {
            "ultimo_aggiornamento_riuscito": coordinator.last_update_success,
            "intervallo": str(coordinator.update_interval),
            "ultimo_accesso": coordinator.ultimo_accesso,
            "ultimo_errore": coordinator.ultimo_errore,
            "serie_scritte": coordinator.serie_scritte,
            "dati": {
                numero: dati.come_dict() for numero, dati in (coordinator.data or {}).items()
            },
        }
    return _anonimizza(diagnostica, sostituzioni)
