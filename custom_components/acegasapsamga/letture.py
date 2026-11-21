"""Meter readings and the hourly series for the Energy Dashboard.

The portal gives cumulative readings in whole m³, about one a month. Between
two readings the consumption is spread evenly over the hours, like the
portal's daily average.

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


@dataclass(frozen=True)
class Lettura:
    giorno: date
    valore: float
    tipo: str
    canale: str | None = None
    contatore: str | None = None
    stato: str | None = None

    @property
    def reale(self) -> bool:
        if self.stato and self.stato.upper() in STATI_LETTURA_NON_VALIDI:
            return False
        return self.tipo.upper() in TIPI_LETTURA_REALI

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
        return risultato

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> Lettura:
        valore = float(dati["valore"])
        if not math.isfinite(valore) or valore < 0:
            raise ValueError(f"valore non valido: {valore}")
        return cls(
            giorno=date.fromisoformat(dati["giorno"]),
            valore=valore,
            tipo=str(dati["tipo"]),
            canale=dati.get("canale"),
            contatore=dati.get("contatore"),
            stato=dati.get("stato"),
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


def _valore(elemento: dict[str, Any]) -> float | None:
    """Meter value of an archive item, skipping the volume corrector that gas
    meters can have."""
    for misura in elemento.get("measurements") or []:
        if not isinstance(misura, dict) or misura.get("correttore"):
            continue
        valore = misura.get("value")
        if valore is None:
            fasce = [f.get("value") for f in misura.get("bands") or [] if isinstance(f, dict)]
            fasce = [f for f in fasce if f is not None]
            valore = fasce[0] if len(fasce) == 1 else None
        if valore is None or isinstance(valore, bool):
            continue
        try:
            numero = float(valore)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numero) and numero >= 0:
            return numero
    return None


def estrai_letture(grezze: list[dict[str, Any]]) -> list[Lettura]:
    """Readings of a read archive answer, oldest first."""
    letture: list[Lettura] = []
    for elemento in grezze:
        giorno = giorno_da_ms(elemento.get("date"))
        valore = _valore(elemento)
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
            )
        )
    return ordina(set(letture))


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
        risultato.append(
            {
                "dal": precedente.giorno + timedelta(days=1),
                "al": successiva.giorno,
                "giorni": giorni,
                "consumo": consumo,
                "media_giornaliera": consumo / giorni,
            }
        )
    return risultato


def ultimo_periodo(letture: list[Lettura]) -> dict[str, Any] | None:
    """Consumption between the last two real readings of the same meter."""
    tutti = periodi(letture)
    return tutti[-1] if tutti else None


def ultima_reale(letture: list[Lettura]) -> Lettura | None:
    punti = ancore(letture)
    return punti[-1] if punti else None
