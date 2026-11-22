"""Texts Home Assistant cannot translate: device model, statistic name,
and calendar event summaries.

They follow the server language (Italian, otherwise English). Everything else
goes through translations/*.json.
"""
from __future__ import annotations

LINGUA_PREDEFINITA = "en"

TESTI: dict[str, dict[str, str]] = {
    "it": {
        "servizio_WATER": "Acqua",
        "servizio_GAS": "Gas",
        "servizio_ELECTRIC": "Luce",
        "servizio_HEATING": "Teleriscaldamento",
        "servizio_ENVIRONMENT": "Rifiuti",
        "modello_WATER": "Contatore acqua",
        "modello_GAS": "Contatore gas",
        "modello_ELECTRIC": "Contatore luce",
        "modello_HEATING": "Contatore teleriscaldamento",
        "modello_ENVIRONMENT": "Utenza TARI / Rifiuti",
        "modello_account": "Account Servizi Online",
        "statistica": "AcegasApsAmga {servizio} {codice}",
        "evento_autolettura": "Autolettura {servizio} {codice}",
        "evento_autolettura_desc": "Finestra di autolettura per il contratto {contratto}",
        "evento_bolletta": "Scadenza bolletta {servizio} ({importo} EUR)",
        "evento_bolletta_desc": "Bolletta {numero} - residuo {importo} EUR",
    },
    "en": {
        "servizio_WATER": "Water",
        "servizio_GAS": "Gas",
        "servizio_ELECTRIC": "Electricity",
        "servizio_HEATING": "District heating",
        "servizio_ENVIRONMENT": "Waste",
        "modello_WATER": "Water meter",
        "modello_GAS": "Gas meter",
        "modello_ELECTRIC": "Electricity meter",
        "modello_HEATING": "District heating meter",
        "modello_ENVIRONMENT": "Waste / TARI contract",
        "modello_account": "Servizi Online account",
        "statistica": "AcegasApsAmga {servizio} {codice}",
        "evento_autolettura": "Self-reading {servizio} {codice}",
        "evento_autolettura_desc": "Self-reading window for contract {contratto}",
        "evento_bolletta": "{servizio} bill due ({importo} EUR)",
        "evento_bolletta_desc": "Bill {numero} - amount due {importo} EUR",
    },
}


def lingua_supportata(lingua: str | None) -> str:
    """'it', 'it-IT' -> 'it'; anything else -> English."""
    base = (lingua or "").split("-")[0].split("_")[0].lower()
    return base if base in TESTI else LINGUA_PREDEFINITA


def testo(lingua: str | None, chiave: str, **segnaposto: str) -> str:
    valore = TESTI[lingua_supportata(lingua)][chiave]
    return valore.format(**segnaposto) if segnaposto else valore
