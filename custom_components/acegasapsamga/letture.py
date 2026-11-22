"""Meter readings and the hourly series for the Energy Dashboard.

The portal gives cumulative readings (in m³ for water/gas, kWh or MWh for
electricity/district heating), about one a month. Between two readings the
consumption is spread evenly over the hours, like the portal's daily average.

Rules:
- only real readings count: estimated ones are billing estimates;
- a reading dated D closes day D, as in the portal's billing periods;
- the series stops at the last real reading, with no extrapolation;
- a new meter adds nothing across the change, the sum carries on;
- a reading lower than the previous one counts as zero consumption.

No Home Assistant imports.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .const import FUSO_ITALIA, STATI_LETTURA_NON_VALIDI, TIPI_LETTURA_REALI

_LOGGER = logging.getLogger(__name__)

FUSO = ZoneInfo(FUSO_ITALIA)
UN_ORA = timedelta(hours=1)
_TIPI_MISURA_SECONDARI = ("REACTIVE", "POWER", "POTENZA", "REATTIVA")


@dataclass(frozen=True)
class Lettura:
    giorno: date
    valore: float
    tipo: str
    canale: str | None = None
    contatore: str | None = None
    stato: str | None = None
    fasce: tuple[tuple[str, float], ...] | None = None

    @property
    def reale(self) -> bool:
        if self.stato and self.stato.upper() in STATI_LETTURA_NON_VALIDI:
            return False
        return self.tipo.upper() in TIPI_LETTURA_REALI

    @property
    def fasce_dict(self) -> dict[str, float] | None:
        return dict(self.fasce) if self.fasce else None

    def come_dict(self) -> dict[str, Any]:
        risultato: dict[str, Any] = {
            "giorno": self.giorno.isoformat(),
            "valore": self.valore,
            "tipo": self.tipo,
            "canale": self.canale,
            "contatore": self.contatore,
        }
        if self.stato is not None:
            risultato["stato"] = self.stato
        if self.fasce:
            risultato["fasce"] = dict(self.fasce)
        return risultato

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> Lettura:
        valore = float(dati["valore"])
        if not math.isfinite(valore) or valore < 0:
            raise ValueError(f"valore non valido: {valore}")
        fasce_raw = dati.get("fasce")
        fasce: tuple[tuple[str, float], ...] | None = None
        if isinstance(fasce_raw, dict) and fasce_raw:
            pulisci: dict[str, float] = {}
            for k, v in fasce_raw.items():
                num = _numero_valido(v)
                if num is not None:
                    pulisci[str(k).upper()] = num
            if pulisci:
                fasce = tuple(sorted(pulisci.items()))
        return cls(
            giorno=date.fromisoformat(dati["giorno"]),
            valore=valore,
            tipo=str(dati["tipo"]),
            canale=dati.get("canale"),
            contatore=dati.get("contatore"),
            stato=dati.get("stato"),
            fasce=fasce,
        )


def giorno_da_ms(valore: Any) -> date | None:
    """Calendar day of a portal date.

    Some endpoints send midnight UTC, others midnight Italian time: read in
    Europe/Rome, both give the same day.
    """
    if isinstance(valore, bool):
        return None
    try:
        secondi = float(valore) / 1000
        if not math.isfinite(secondi):
            return None
        return datetime.fromtimestamp(secondi, FUSO).date()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _numero_valido(valore: Any) -> float | None:
    if valore is None or isinstance(valore, bool):
        return None
    try:
        numero = float(valore)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numero) or numero < 0:
        return None
    return numero


def _valore_misura(
    misura: dict[str, Any],
) -> tuple[float | None, tuple[tuple[str, float], ...] | None]:
    """Extract total reading and optional F1/F2/F3 bands from one measurement."""
    valore_diretto = _numero_valido(misura.get("value"))
    bande: dict[str, float] = {}
    bande_senza_tipo: list[float] = []
    for fascia in misura.get("bands") or []:
        if not isinstance(fascia, dict):
            continue
        num = _numero_valido(fascia.get("value"))
        if num is None:
            continue
        tipo_fascia = str(fascia.get("type") or "").upper()
        if tipo_fascia:
            bande[tipo_fascia] = num
        else:
            bande_senza_tipo.append(num)

    # Multi-band electricity meter (F1/F2/F3).
    fasce_orarie = {k: v for k, v in bande.items() if k in ("F1", "F2", "F3")}
    if len(fasce_orarie) >= 2:
        somma = round(sum(fasce_orarie.values()), 3)
        totale = valore_diretto if (valore_diretto is not None and valore_diretto > 0) else somma
        return totale, tuple(sorted(fasce_orarie.items()))

    if valore_diretto is not None:
        return valore_diretto, None
    if len(bande) == 1:
        return next(iter(bande.values())), None
    if len(bande_senza_tipo) == 1:
        return bande_senza_tipo[0], None
    return None, None


def _estrai_misura(
    elemento: dict[str, Any],
) -> tuple[float | None, tuple[tuple[str, float], ...] | None]:
    """Meter value (and optional time-of-use bands) of an archive item,
    skipping volume correctors and preferring active over reactive energy."""
    misure = [
        m
        for m in elemento.get("measurements") or []
        if isinstance(m, dict) and not m.get("correttore")
    ]
    primarie = [
        m
        for m in misure
        if not any(
            sec in str(m.get("type") or m.get("title") or "").upper()
            for sec in _TIPI_MISURA_SECONDARI
        )
    ]
    for lista in (primarie, misure):
        for misura in lista:
            valore, fasce = _valore_misura(misura)
            if valore is not None:
                return valore, fasce
    return None, None


def estrai_letture(grezze: list[dict[str, Any]]) -> list[Lettura]:
    """Readings of a read archive answer, oldest first."""
    letture: list[Lettura] = []
    for elemento in grezze:
        giorno = giorno_da_ms(elemento.get("date"))
        valore, fasce = _estrai_misura(elemento)
        if giorno is None or valore is None:
            _LOGGER.debug("Lettura non interpretabile, ignorata: %r", elemento)
            continue
        stato_grezzo = elemento.get("status")
        stato = str(stato_grezzo) if stato_grezzo not in (None, "", "UNKNOWN") else None
        letture.append(
            Lettura(
                giorno=giorno,
                valore=valore,
                tipo=str(elemento.get("type") or "UNKNOWN"),
                canale=elemento.get("channel"),
                contatore=elemento.get("meterId"),
                stato=stato,
                fasce=fasce,
            )
        )
    return ordina(set(letture))


def estrai_consumi_giornalieri(grezze: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse daily consumption rows from v2/profile/{p}/contract/{c}/usage."""
    per_giorno: dict[date, dict[str, Any]] = {}
    for elemento in grezze:
        giorno = giorno_da_ms(elemento.get("usageFromDate") or elemento.get("usageToDate"))
        valore = _numero_valido(elemento.get("totalUsage"))
        if giorno is None or valore is None:
            continue
        per_giorno[giorno] = {
            "giorno": giorno.isoformat(),
            "consumo": round(valore, 3),
            "tipo": str(elemento.get("readType") or "UNKNOWN"),
        }
    return [per_giorno[g] for g in sorted(per_giorno)]


def ordina(letture) -> list[Lettura]:
    """Oldest first. On the same day the old meter comes before the new one,
    so a meter change reads in the right order."""
    letture = list(letture)
    primo_giorno: dict[str | None, date] = {}
    for lettura in letture:
        if lettura.contatore not in primo_giorno or lettura.giorno < primo_giorno[lettura.contatore]:
            primo_giorno[lettura.contatore] = lettura.giorno
    return sorted(
        letture,
        key=lambda l: (
            l.giorno,
            primo_giorno[l.contatore],
            str(l.contatore),
            l.reale,
            l.valore,
            l.tipo.upper() == "REAL",
            l.tipo,
        ),
    )


def unisci(salvate: list[Lettura], nuove: list[Lettura]) -> list[Lettura]:
    """Merge stored and downloaded readings.

    From the portal's oldest reading on, the portal wins (corrections and
    cancellations included). Older stored readings are kept: if the portal
    drops old history, the series must not restart from a later point.
    """
    if not nuove:
        return ordina(salvate)
    inizio = min(lettura.giorno for lettura in nuove)
    return ordina({*(l for l in salvate if l.giorno < inizio), *nuove})


def ancore(letture: list[Lettura]) -> list[Lettura]:
    """Real readings, one per meter and day."""
    per_giorno: dict[tuple[str | None, date], Lettura] = {}
    for lettura in ordina(l for l in letture if l.reale):
        per_giorno[(lettura.contatore, lettura.giorno)] = lettura
    return list(per_giorno.values())


def istante(giorno: date) -> datetime:
    """When a reading of 'giorno' applies: the end of that day, Italian time."""
    return datetime.combine(giorno + timedelta(days=1), time(0), FUSO).astimezone(UTC)


def serie_oraria(letture: list[Lettura], adesso: datetime) -> list[dict[str, Any]]:
    """Hourly rows for async_add_external_statistics.

    'state' is the meter value at the end of the hour, 'sum' the consumption
    since the first real reading. Hours not over yet are left out.
    """
    punti = ancore(letture)
    righe: list[dict[str, Any]] = []
    somma = 0.0
    for precedente, successiva in zip(punti, punti[1:], strict=False):
        if precedente.contatore != successiva.contatore:
            _LOGGER.info(
                "Cambio contatore tra il %s e il %s: nessun consumo nel passaggio",
                precedente.giorno,
                successiva.giorno,
            )
            continue
        inizio, fine = istante(precedente.giorno), istante(successiva.giorno)
        ore = int((fine - inizio) / UN_ORA)
        if ore <= 0:
            continue
        delta = successiva.valore - precedente.valore
        if delta < 0:
            _LOGGER.warning(
                "Lettura del %s (%s) inferiore alla precedente del %s (%s): consumo zero",
                successiva.giorno,
                successiva.valore,
                precedente.giorno,
                precedente.valore,
            )
            delta = 0.0
        for ora in range(ore):
            start = inizio + ora * UN_ORA
            if start + UN_ORA > adesso:
                return righe
            frazione = (ora + 1) / ore
            righe.append(
                {
                    "start": start,
                    "state": round(precedente.valore + delta * frazione, 6),
                    "sum": round(somma + delta * frazione, 6),
                }
            )
        somma += delta
    return righe


def periodi(letture: list[Lettura]) -> list[dict[str, Any]]:
    """Periods between consecutive real readings of the same meter, oldest first."""
    punti = ancore(letture)
    risultato = []
    for precedente, successiva in zip(punti, punti[1:], strict=False):
        giorni = (successiva.giorno - precedente.giorno).days
        if precedente.contatore != successiva.contatore or giorni <= 0:
            continue
        consumo = max(successiva.valore - precedente.valore, 0.0)
        voce: dict[str, Any] = {
            "dal": precedente.giorno + timedelta(days=1),
            "al": successiva.giorno,
            "giorni": giorni,
            "consumo": consumo,
            "media_giornaliera": consumo / giorni,
        }
        if precedente.fasce and successiva.fasce:
            f_prec = dict(precedente.fasce)
            f_succ = dict(successiva.fasce)
            comuni = sorted(f_prec.keys() & f_succ.keys())
            if comuni:
                voce["fasce"] = {
                    k: round(max(f_succ[k] - f_prec[k], 0.0), 3) for k in comuni
                }
        risultato.append(voce)
    return risultato


def ultimo_periodo(letture: list[Lettura]) -> dict[str, Any] | None:
    """Consumption between the last two real readings of the same meter."""
    tutti = periodi(letture)
    return tutti[-1] if tutti else None


def ultima_reale(letture: list[Lettura]) -> Lettura | None:
    punti = ancore(letture)
    return punti[-1] if punti else None
