"""Texts Home Assistant cannot translate: device model and statistic name.

They follow the server language (Italian, otherwise English). Everything else
goes through translations/*.json.
"""
from __future__ import annotations

LINGUA_PREDEFINITA = "en"

TESTI: dict[str, dict[str, str]] = {
    "it": {
        "servizio_WATER": "Acqua",
        "servizio_GAS": "Gas",
        "modello_WATER": "Contatore acqua",
        "modello_GAS": "Contatore gas",
        "statistica": "AcegasApsAmga {servizio} {codice}",
    },
    "en": {
        "servizio_WATER": "Water",
        "servizio_GAS": "Gas",
        "modello_WATER": "Water meter",
        "modello_GAS": "Gas meter",
        "statistica": "AcegasApsAmga {servizio} {codice}",
    },
}


def lingua_supportata(lingua: str | None) -> str:
    """'it', 'it-IT' -> 'it'; anything else -> English."""
    base = (lingua or "").split("-")[0].split("_")[0].lower()
    return base if base in TESTI else LINGUA_PREDEFINITA


def testo(lingua: str | None, chiave: str, **segnaposto: str) -> str:
    valore = TESTI[lingua_supportata(lingua)][chiave]
    return valore.format(**segnaposto) if segnaposto else valore
