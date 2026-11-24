"""Waste / TARI (ENVIRONMENT / TCP): equipment, disposals and discounts.

Parses the portal's TCP endpoints:
- profile/{p}/TCP/equipment/{c}
- profile/{p}/TCP/wastedisposal/{c}
- v1/profile/{p}/TCP/advantage/{c}

No Home Assistant imports.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .const import TIPI_RIFIUTO
from .letture import giorno_da_ms


def _numero(valore: Any) -> float | None:
    if valore is None or isinstance(valore, bool):
        return None
    try:
        numero = float(valore)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numero) or numero < 0:
        return None
    return round(numero, 2)


@dataclass(frozen=True)
class Dotazione:
    codice: str
    tipo: str
    stato: str
    descrizione: str | None = None
    volume: float | None = None
    data_assegnazione: date | None = None
    codice_materiale: str | None = None

    @property
    def attiva(self) -> bool:
        return self.stato.upper() == "ACTIVE"

    def come_dict(self) -> dict[str, Any]:
        return {
            "codice": self.codice,
            "tipo": self.tipo,
            "stato": self.stato,
            "descrizione": self.descrizione,
            "volume": self.volume,
            "data_assegnazione": (
                self.data_assegnazione.isoformat() if self.data_assegnazione else None
            ),
            "codice_materiale": self.codice_materiale,
        }

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> Dotazione:
        return cls(
            codice=str(dati["codice"]),
            tipo=str(dati.get("tipo") or "UNKNOWN"),
            stato=str(dati.get("stato") or "UNKNOWN"),
            descrizione=dati.get("descrizione"),
            volume=_numero(dati.get("volume")),
            data_assegnazione=(
                date.fromisoformat(dati["data_assegnazione"])
                if dati.get("data_assegnazione")
                else None
            ),
            codice_materiale=dati.get("codice_materiale"),
        )


@dataclass(frozen=True)
class Svuotamento:
    giorno: date
    tipo_rifiuto: str
    volume: float | None = None
    tipo_dotazione: str | None = None
    codice_dotazione: str | None = None

    def come_dict(self) -> dict[str, Any]:
        return {
            "giorno": self.giorno.isoformat(),
            "tipo_rifiuto": self.tipo_rifiuto,
            "volume": self.volume,
            "tipo_dotazione": self.tipo_dotazione,
            "codice_dotazione": self.codice_dotazione,
        }

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> Svuotamento:
        return cls(
            giorno=date.fromisoformat(dati["giorno"]),
            tipo_rifiuto=str(dati.get("tipo_rifiuto") or "RSU").upper(),
            volume=_numero(dati.get("volume")),
            tipo_dotazione=dati.get("tipo_dotazione"),
            codice_dotazione=dati.get("codice_dotazione"),
        )


@dataclass
class DatiRifiuti:
    dotazioni: list[Dotazione] = field(default_factory=list)
    svuotamenti_anno_corrente: list[Svuotamento] = field(default_factory=list)
    svuotamenti_anno_precedente: list[Svuotamento] = field(default_factory=list)
    volume_anno_corrente: float | None = None
    volume_anno_precedente: float | None = None
    vantaggi: list[dict[str, Any]] = field(default_factory=list)

    @property
    def dotazioni_attive(self) -> list[Dotazione]:
        return [d for d in self.dotazioni if d.attiva]

    @property
    def volume_totale_corrente(self) -> float:
        if self.volume_anno_corrente is not None:
            return round(self.volume_anno_corrente, 2)
        return round(sum(s.volume or 0.0 for s in self.svuotamenti_anno_corrente), 2)

    @property
    def volume_totale_precedente(self) -> float | None:
        if self.volume_anno_precedente is not None:
            return round(self.volume_anno_precedente, 2)
        if not self.svuotamenti_anno_precedente:
            return None
        return round(sum(s.volume or 0.0 for s in self.svuotamenti_anno_precedente), 2)

    def anno_precedente_ad_oggi(self, oggi: date) -> tuple[int, float] | None:
        """Disposals and litres of last year up to the same day, to compare this
        year with the same stretch of last year. None without last year's list."""
        if not self.svuotamenti_anno_precedente:
            return None
        fino = un_anno_prima(oggi)
        scelti = [s for s in self.svuotamenti_anno_precedente if s.giorno <= fino]
        return len(scelti), round(sum(s.volume or 0.0 for s in scelti), 2)

    def per_tipo(self) -> dict[str, dict[str, Any]]:
        """Counts and total volumes grouped by waste fraction (current year)."""
        gruppi: dict[str, dict[str, Any]] = {}
        for s in self.svuotamenti_anno_corrente:
            voce = gruppi.setdefault(s.tipo_rifiuto, {"svuotamenti": 0, "volume": 0.0})
            voce["svuotamenti"] += 1
            voce["volume"] = round(voce["volume"] + (s.volume or 0.0), 2)
        ordinati: dict[str, dict[str, Any]] = {}
        for tipo in TIPI_RIFIUTO:
            if tipo in gruppi:
                ordinati[tipo] = gruppi[tipo]
        for tipo in sorted(set(gruppi) - set(ordinati)):
            ordinati[tipo] = gruppi[tipo]
        return ordinati

    def per_mese(self) -> list[dict[str, Any]]:
        """Monthly disposal counts and volumes (current year, 1..12)."""
        mesi: list[dict[str, Any]] = [
            {"mese": m, "svuotamenti": 0, "volume": 0.0, "per_tipo": {}}
            for m in range(1, 13)
        ]
        for s in self.svuotamenti_anno_corrente:
            voce = mesi[s.giorno.month - 1]
            voce["svuotamenti"] += 1
            voce["volume"] = round(voce["volume"] + (s.volume or 0.0), 2)
            voce["per_tipo"][s.tipo_rifiuto] = voce["per_tipo"].get(s.tipo_rifiuto, 0) + 1
        return mesi

    def come_dict(self) -> dict[str, Any]:
        return {
            "dotazioni": [d.come_dict() for d in self.dotazioni],
            "svuotamenti_anno_corrente": [s.come_dict() for s in self.svuotamenti_anno_corrente],
            "svuotamenti_anno_precedente": [
                s.come_dict() for s in self.svuotamenti_anno_precedente
            ],
            "volume_anno_corrente": self.volume_anno_corrente,
            "volume_anno_precedente": self.volume_anno_precedente,
            "vantaggi": list(self.vantaggi),
        }

    @classmethod
    def da_dict(cls, dati: dict[str, Any] | None) -> DatiRifiuti | None:
        if not isinstance(dati, dict):
            return None
        dotazioni = []
        for g in dati.get("dotazioni") or []:
            try:
                dotazioni.append(Dotazione.da_dict(g))
            except (KeyError, TypeError, ValueError):
                continue
        correnti = []
        for g in dati.get("svuotamenti_anno_corrente") or []:
            try:
                correnti.append(Svuotamento.da_dict(g))
            except (KeyError, TypeError, ValueError):
                continue
        precedenti = []
        for g in dati.get("svuotamenti_anno_precedente") or []:
            try:
                precedenti.append(Svuotamento.da_dict(g))
            except (KeyError, TypeError, ValueError):
                continue
        vantaggi = [v for v in dati.get("vantaggi") or [] if isinstance(v, dict)]
        return cls(
            dotazioni=dotazioni,
            svuotamenti_anno_corrente=sorted(correnti, key=lambda s: s.giorno, reverse=True),
            svuotamenti_anno_precedente=sorted(precedenti, key=lambda s: s.giorno, reverse=True),
            volume_anno_corrente=_numero(dati.get("volume_anno_corrente")),
            volume_anno_precedente=_numero(dati.get("volume_anno_precedente")),
            vantaggi=vantaggi,
        )


def un_anno_prima(giorno: date) -> date:
    """The same day a year before; 29 February becomes the 28th."""
    try:
        return giorno.replace(year=giorno.year - 1)
    except ValueError:
        return giorno.replace(year=giorno.year - 1, day=28)


def estrai_dotazioni(grezze: list[dict[str, Any]]) -> list[Dotazione]:
    risultato: list[Dotazione] = []
    for voce in grezze:
        if not isinstance(voce, dict):
            continue
        codice = str(voce.get("equipmentCode") or "").strip()
        if not codice:
            continue
        risultato.append(
            Dotazione(
                codice=codice,
                tipo=str(voce.get("type") or "UNKNOWN").upper(),
                stato=str(voce.get("status") or "UNKNOWN").upper(),
                descrizione=voce.get("description"),
                volume=_numero(voce.get("volume")),
                data_assegnazione=giorno_da_ms(voce.get("assignmentDate")),
                codice_materiale=voce.get("materialCode"),
            )
        )
    return risultato


def estrai_svuotamenti(
    risposta: dict[str, Any] | None, *, tipo_predefinito: str = "RSU"
) -> tuple[list[Svuotamento], float | None]:
    if not isinstance(risposta, dict):
        return [], None
    svuotamenti: list[Svuotamento] = []
    for voce in risposta.get("wasteDisposals") or []:
        if not isinstance(voce, dict):
            continue
        giorno = giorno_da_ms(voce.get("disposalDate"))
        if giorno is None:
            continue
        tipo = str(voce.get("wasteType") or tipo_predefinito).strip().upper()
        svuotamenti.append(
            Svuotamento(
                giorno=giorno,
                tipo_rifiuto=tipo,
                volume=_numero(voce.get("volume")),
                tipo_dotazione=(
                    str(voce["equipmentType"]).upper() if voce.get("equipmentType") else None
                ),
                codice_dotazione=(
                    str(voce["equipmentCode"]).strip() if voce.get("equipmentCode") else None
                ),
            )
        )
    svuotamenti.sort(key=lambda s: s.giorno, reverse=True)
    return svuotamenti, _numero(risposta.get("totalVolume"))


def estrai_vantaggi(grezze: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risultato: list[dict[str, Any]] = []
    for voce in grezze:
        if not isinstance(voce, dict):
            continue
        codice = voce.get("siebelValue") or voce.get("id") or voce.get("code")
        nome = voce.get("friendlyName") or voce.get("description") or voce.get("name")
        if codice or nome:
            risultato.append({"codice": str(codice or ""), "descrizione": str(nome or codice or "")})
    return risultato
