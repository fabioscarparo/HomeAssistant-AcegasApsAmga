"""Bills: from the portal's bill list to what the sensors show.

A bill can group several contracts of the same account: amounts are those
of the whole bill, while importi_servizi preserves the service-specific split
from companyServices. Only safe non-PII fields are kept.

No Home Assistant imports.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
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
    "UNDERTHRESHOLD": "not_to_pay",
    "CREDIT": "credit",
    "REVERSED": "reversed",
    "REVERSED_PARTIAL": "reversed",
    "PARTIALLY_REVERSED": "reversed",
    "INSTALLED": "installment",
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
    stato_dettaglio: str | None = None
    bolletta_web: bool | None = None
    pdf_disponibile: bool = False
    rateizzabile: bool = False
    pagopa: bool = False
    bonifico: bool = False
    sotto_soglia: bool = False
    data_pagamento: date | None = None
    importi_servizi: tuple[tuple[str, float], ...] = ()
    stornata_da: str | None = None

    @property
    def da_pagare(self) -> bool:
        return self.stato in STATI_DA_PAGARE and self.residuo > 0

    @property
    def importi_servizi_dict(self) -> dict[str, float]:
        return dict(self.importi_servizi)

    def importo_servizio(self, servizio: str | None) -> float:
        """Amount for one service in a grouped bill, or the full amount."""
        if servizio and self.importi_servizi:
            mappa = dict(self.importi_servizi)
            if servizio in mappa:
                return mappa[servizio]
        return self.importo

    def come_dict(self) -> dict[str, Any]:
        risultato: dict[str, Any] = {
            "numero": self.numero,
            "emissione": self.emissione.isoformat(),
            "scadenza": self.scadenza.isoformat() if self.scadenza else None,
            "importo": self.importo,
            "residuo": self.residuo,
            "stato": self.stato,
            "domiciliata": self.domiciliata,
            "contratti": list(self.contratti),
        }
        if self.stato_dettaglio is not None:
            risultato["stato_dettaglio"] = self.stato_dettaglio
        if self.bolletta_web is not None:
            risultato["bolletta_web"] = self.bolletta_web
        if self.pdf_disponibile:
            risultato["pdf_disponibile"] = True
        if self.rateizzabile:
            risultato["rateizzabile"] = True
        if self.pagopa:
            risultato["pagopa"] = True
        if self.bonifico:
            risultato["bonifico"] = True
        if self.sotto_soglia:
            risultato["sotto_soglia"] = True
        if self.data_pagamento is not None:
            risultato["data_pagamento"] = self.data_pagamento.isoformat()
        if self.importi_servizi:
            risultato["importi_servizi"] = dict(self.importi_servizi)
        if self.stornata_da is not None:
            risultato["stornata_da"] = self.stornata_da
        return risultato

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> Bolletta:
        importo = _numero(dati["importo"])
        if importo is None:
            raise ValueError(f"importo non valido: {dati['importo']!r}")
        residuo = _numero(dati.get("residuo"))
        importi_raw = dati.get("importi_servizi")
        importi_servizi: tuple[tuple[str, float], ...] = ()
        if isinstance(importi_raw, dict):
            puliti: dict[str, float] = {}
            for k, v in importi_raw.items():
                num = _numero(v)
                if num is not None:
                    puliti[str(k)] = num
            importi_servizi = tuple(sorted(puliti.items()))
        return cls(
            numero=str(dati["numero"]),
            emissione=date.fromisoformat(dati["emissione"]),
            scadenza=date.fromisoformat(dati["scadenza"]) if dati.get("scadenza") else None,
            importo=importo,
            residuo=residuo if residuo is not None else 0.0,
            stato=dati.get("stato") or STATO_ALTRO,
            domiciliata=bool(dati.get("domiciliata")),
            contratti=tuple(dati.get("contratti") or ()),
            stato_dettaglio=dati.get("stato_dettaglio"),
            bolletta_web=dati.get("bolletta_web") if isinstance(dati.get("bolletta_web"), bool) else None,
            pdf_disponibile=bool(dati.get("pdf_disponibile")),
            rateizzabile=bool(dati.get("rateizzabile")),
            pagopa=bool(dati.get("pagopa")),
            bonifico=bool(dati.get("bonifico")),
            sotto_soglia=bool(dati.get("sotto_soglia")),
            data_pagamento=(
                date.fromisoformat(dati["data_pagamento"]) if dati.get("data_pagamento") else None
            ),
            importi_servizi=importi_servizi,
            stornata_da=str(dati["stornata_da"]) if dati.get("stornata_da") else None,
        )


def _numero(valore: Any) -> float | None:
    if isinstance(valore, bool):
        return None
    try:
        numero = float(valore)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numero):
        return None
    return round(numero, 2)


def _stato(grezza: dict[str, Any]) -> str:
    if grezza.get("installmentParent"):
        return "installment"
    stato = grezza.get("paymentStatus")
    if not stato:
        macro = (grezza.get("paymentStatusTranscoding") or {}).get("macroStatus") or {}
        stato = macro.get("name")
    mappato = STATI.get(str(stato).upper(), STATO_ALTRO) if stato else STATO_ALTRO
    if grezza.get("underthreshold") and mappato in STATI_DA_PAGARE:
        return "not_to_pay"
    return mappato


def _stato_dettaglio(grezza: dict[str, Any]) -> str | None:
    transcoding = grezza.get("paymentStatusTranscoding")
    if not isinstance(transcoding, dict):
        return None
    testo = transcoding.get("customerTranscoding") or transcoding.get("transcoding")
    return str(testo).strip() if testo and str(testo).strip() else None


def _bolletta_web(grezza: dict[str, Any]) -> bool | None:
    tipi = grezza.get("deliveryTypes")
    if not isinstance(tipi, list) or not tipi:
        return None
    normalizzati = {str(t).upper() for t in tipi if t}
    if not normalizzati:
        return None
    return bool(normalizzati & {"EMAIL", "PAPEREMAIL", "PEC"})


def _servizi_e_storno(
    grezza: dict[str, Any],
) -> tuple[tuple[tuple[str, float], ...], str | None]:
    somme: dict[str, float] = {}
    stornata_da: str | None = None
    for voce in grezza.get("companyServices") or []:
        if not isinstance(voce, dict):
            continue
        tipo = str(voce.get("type") or "").strip().upper()
        importo = _numero(voce.get("amount"))
        if tipo and importo is not None:
            somme[tipo] = round(somme.get(tipo, 0.0) + importo, 2)
        if stornata_da is None and voce.get("reverserBillId"):
            stornata_da = str(voce["reverserBillId"]).strip() or None
    return tuple(sorted(somme.items())), stornata_da


def _contratti(grezza: dict[str, Any]) -> tuple[str, ...]:
    codici = [c.get("contractId") for c in grezza.get("contractServiceTypeList") or [] if isinstance(c, dict)]
    codici.append(grezza.get("contractId"))
    return tuple(dict.fromkeys(str(c).strip() for c in codici if c and str(c).strip()))


def estrai_bollette(grezze: list[dict[str, Any]]) -> list[Bolletta]:
    """Bills of the list, newest first, deduplicated by number. Items without
    number, date or amount are skipped."""
    viste: dict[str, Bolletta] = {}
    for grezza in grezze:
        emissione = giorno_da_ms(grezza.get("emissionDate"))
        importo = _numero(grezza.get("amount"))
        numero = str(grezza["id"]).strip() if grezza.get("id") else ""
        if not numero or emissione is None or importo is None or numero in viste:
            continue
        residuo = _numero(grezza.get("residual"))
        importi_servizi, stornata_da = _servizi_e_storno(grezza)
        viste[numero] = Bolletta(
            numero=numero,
            emissione=emissione,
            scadenza=giorno_da_ms(grezza.get("expireDate")),
            importo=importo,
            residuo=residuo if residuo is not None else 0.0,
            stato=_stato(grezza),
            domiciliata=bool(grezza.get("domicilied")),
            contratti=_contratti(grezza),
            stato_dettaglio=_stato_dettaglio(grezza),
            bolletta_web=_bolletta_web(grezza),
            pdf_disponibile=bool(grezza.get("documentAvailable")),
            rateizzabile=bool(grezza.get("installmentEnabled")),
            pagopa=bool(grezza.get("pagoPaEnabled")),
            bonifico=bool(grezza.get("bankTransferEnabled")),
            sotto_soglia=bool(grezza.get("underthreshold")),
            data_pagamento=giorno_da_ms(grezza.get("paymentDate")),
            importi_servizi=importi_servizi,
            stornata_da=stornata_da,
        )
    return ordina(list(viste.values()))


def applica_pagamenti(
    bollette: list[Bolletta], pagamenti: list[dict[str, Any]]
) -> list[Bolletta]:
    """Enrich bills with their actual payment date from bill/invoice/list."""
    date_pagamento: dict[str, date] = {}
    for movimento in pagamenti:
        if not isinstance(movimento, dict):
            continue
        stato = str(movimento.get("paymentStatus") or "PAYMENT").upper()
        if stato == "REFUND":
            continue
        giorno = giorno_da_ms(movimento.get("paymentDate") or movimento.get("valueDate"))
        if giorno is None:
            continue
        for codice in movimento.get("billIds") or []:
            numero = str(codice).strip()
            if numero and (numero not in date_pagamento or giorno > date_pagamento[numero]):
                date_pagamento[numero] = giorno
    if not date_pagamento:
        return bollette
    return [
        replace(b, data_pagamento=date_pagamento[b.numero])
        if b.numero in date_pagamento and b.data_pagamento is None
        else b
        for b in bollette
    ]


def estrai_rimborsi(pagamenti: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract refund movements from bill/invoice/list."""
    rimborsi: list[dict[str, Any]] = []
    for movimento in pagamenti:
        if not isinstance(movimento, dict):
            continue
        if str(movimento.get("paymentStatus") or "").upper() != "REFUND":
            continue
        giorno = giorno_da_ms(movimento.get("paymentDate") or movimento.get("valueDate"))
        importo = _numero(movimento.get("amount"))
        if giorno is None or importo is None:
            continue
        rimborsi.append(
            {
                "data": giorno.isoformat(),
                "importo": importo,
                "tipo": movimento.get("paymentType"),
            }
        )
    return sorted(rimborsi, key=lambda r: r["data"], reverse=True)


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
