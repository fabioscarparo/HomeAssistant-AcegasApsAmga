"""Bills: from the portal's bill list to what the sensors show.

A bill can group several contracts of the same account: amounts are those
of the whole bill. Only the fields the sensors use are kept, so the store
holds no names, addresses or bank details.

No Home Assistant imports.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .letture import giorno_da_ms

# Statuses of the portal, grouped into the states of the status sensor.
STATI = {
    "UNPAID": "unpaid",
    "EXPIRED": "expired",
    "PAID_PARTIAL": "paid_partial",
    "PAID": "paid",
    "PAID_SBF": "paid",
    "NOT_TO_PAY": "not_to_pay",
    "CREDIT": "credit",
    "REVERSED": "reversed",
    "REVERSED_PARTIAL": "reversed",
}
STATO_ALTRO = "other"
OPZIONI_STATO = [*dict.fromkeys(STATI.values()), STATO_ALTRO]

# Statuses whose residual is still to be paid.
STATI_DA_PAGARE = {"unpaid", "expired", "paid_partial"}


@dataclass(frozen=True)
class Bolletta:
    numero: str
    emissione: date
    scadenza: date | None
    importo: float
    residuo: float
    stato: str
    domiciliata: bool
    contratti: tuple[str, ...]

    @property
    def da_pagare(self) -> bool:
        return self.stato in STATI_DA_PAGARE and self.residuo > 0

    def come_dict(self) -> dict[str, Any]:
        return {
            "numero": self.numero,
            "emissione": self.emissione.isoformat(),
            "scadenza": self.scadenza.isoformat() if self.scadenza else None,
            "importo": self.importo,
            "residuo": self.residuo,
            "stato": self.stato,
            "domiciliata": self.domiciliata,
            "contratti": list(self.contratti),
        }

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> Bolletta:
        return cls(
            numero=str(dati["numero"]),
            emissione=date.fromisoformat(dati["emissione"]),
            scadenza=date.fromisoformat(dati["scadenza"]) if dati.get("scadenza") else None,
            importo=float(dati["importo"]),
            residuo=float(dati.get("residuo") or 0),
            stato=dati.get("stato") or STATO_ALTRO,
            domiciliata=bool(dati.get("domiciliata")),
            contratti=tuple(dati.get("contratti") or ()),
        )


def _numero(valore: Any) -> float | None:
    try:
        return round(float(valore), 2)
    except (TypeError, ValueError):
        return None


def _stato(grezza: dict[str, Any]) -> str:
    stato = grezza.get("paymentStatus")
    if not stato:
        macro = (grezza.get("paymentStatusTranscoding") or {}).get("macroStatus") or {}
        stato = macro.get("name")
    return STATI.get(str(stato).upper(), STATO_ALTRO) if stato else STATO_ALTRO


def _contratti(grezza: dict[str, Any]) -> tuple[str, ...]:
    codici = [c.get("contractId") for c in grezza.get("contractServiceTypeList") or [] if isinstance(c, dict)]
    codici.append(grezza.get("contractId"))
    return tuple(dict.fromkeys(str(c) for c in codici if c))


def estrai_bollette(grezze: list[dict[str, Any]]) -> list[Bolletta]:
    """Bills of the list, newest first. Items without number, date or
    amount are skipped."""
    bollette = []
    for grezza in grezze:
        emissione = giorno_da_ms(grezza.get("emissionDate"))
        importo = _numero(grezza.get("amount"))
        if not grezza.get("id") or emissione is None or importo is None:
            continue
        residuo = _numero(grezza.get("residual"))
        bollette.append(
            Bolletta(
                numero=str(grezza["id"]).strip(),
                emissione=emissione,
                scadenza=giorno_da_ms(grezza.get("expireDate")),
                importo=importo,
                residuo=residuo if residuo is not None else 0.0,
                stato=_stato(grezza),
                domiciliata=bool(grezza.get("domicilied")),
                contratti=_contratti(grezza),
            )
        )
    return ordina(bollette)


def ordina(bollette: list[Bolletta]) -> list[Bolletta]:
    return sorted(bollette, key=lambda b: (b.emissione, b.numero), reverse=True)


def del_contratto(bollette: list[Bolletta], contratto: str) -> list[Bolletta]:
    """Bills that include the contract. A bill that names no contract
    belongs to all of them."""
    return [b for b in bollette if not b.contratti or contratto in b.contratti]


def totale_da_pagare(bollette: list[Bolletta]) -> float:
    return round(sum((b.residuo for b in bollette if b.da_pagare), 0.0), 2)


def prossima_scadenza(bollette: list[Bolletta]) -> date | None:
    """Earliest due date among the bills still to pay."""
    scadenze = [b.scadenza for b in bollette if b.da_pagare and b.scadenza]
    return min(scadenze) if scadenze else None
