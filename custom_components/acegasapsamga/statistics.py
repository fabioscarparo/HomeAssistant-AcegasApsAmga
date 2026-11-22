"""External statistics for the Energy Dashboard.

One series per metered contract, named after the supply point code:
acegasapsamga:<pod>_acqua, _gas, _luce, _teleriscaldamento.

When only new readings are appended at the tail, only new hours are added;
after historical corrections the whole series is cleared and rewritten.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SERVIZIO_ACQUA,
    SERVIZIO_GAS,
    SERVIZIO_LUCE,
    SERVIZIO_TLR,
)

_LOGGER = logging.getLogger(__name__)

SUFFISSI = {
    SERVIZIO_ACQUA: "acqua",
    SERVIZIO_GAS: "gas",
    SERVIZIO_LUCE: "luce",
    SERVIZIO_TLR: "teleriscaldamento",
}


def statistic_id(servizio: str, codice: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", codice.lower()).strip("_") or "contratto"
    suffisso = SUFFISSI.get(servizio, servizio.lower())
    return f"{DOMAIN}:{slug}_{suffisso}"


def unita_servizio(servizio: str, unita_contatore: str | None = None) -> tuple[str, str]:
    """Return (unit_of_measurement, unit_class) for a metered service."""
    if servizio == SERVIZIO_LUCE:
        return UnitOfEnergy.KILO_WATT_HOUR, "energy"
    if servizio == SERVIZIO_TLR:
        if unita_contatore and unita_contatore.strip().lower() == "mwh":
            return UnitOfEnergy.MEGA_WATT_HOUR, "energy"
        return UnitOfEnergy.KILO_WATT_HOUR, "energy"
    return UnitOfVolume.CUBIC_METERS, "volume"


def metadata(
    statistic_id: str,
    nome: str,
    *,
    servizio: str = SERVIZIO_ACQUA,
    unita_contatore: str | None = None,
) -> dict[str, Any]:
    unita, classe = unita_servizio(servizio, unita_contatore)
    return {
        "mean_type": StatisticMeanType.NONE,
        "has_sum": True,
        "name": nome,
        "source": DOMAIN,
        "statistic_id": statistic_id,
        "unit_of_measurement": unita,
        "unit_class": classe,
    }


async def async_ultima_ora(hass: HomeAssistant, statistic_id: str) -> datetime | None:
    """Start of the last hour in the Recorder, None if the series is missing."""
    ultime = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, False, {"sum"}
    )
    righe = ultime.get(statistic_id)
    if not righe or righe[0].get("start") is None:
        return None
    return dt_util.utc_from_timestamp(righe[0]["start"])


async def async_cancella_serie(hass: HomeAssistant, statistic_id: str) -> None:
    """Remove all rows of a statistic from the Recorder."""
    _LOGGER.info("%s: svuoto la serie nel Recorder", statistic_id)
    get_instance(hass).async_clear_statistics([statistic_id])


async def async_scrivi_serie(
    hass: HomeAssistant,
    statistic_id: str,
    nome: str,
    righe: list[dict[str, Any]],
    *,
    ultima_ora_scritta: datetime | None,
    riscrivi: bool = True,
    servizio: str = SERVIZIO_ACQUA,
    unita_contatore: str | None = None,
) -> None:
    if not righe:
        if ultima_ora_scritta is not None:
            await async_cancella_serie(hass, statistic_id)
        return
    if ultima_ora_scritta is not None and (riscrivi or righe[-1]["start"] < ultima_ora_scritta):
        _LOGGER.info("%s: riscrivo la serie da zero", statistic_id)
        # The Recorder runs its jobs in order: the clear happens before the import.
        get_instance(hass).async_clear_statistics([statistic_id])
        da_scrivere = righe
    elif ultima_ora_scritta is not None:
        da_scrivere = [r for r in righe if r["start"] > ultima_ora_scritta]
        if not da_scrivere:
            return
    else:
        da_scrivere = righe
    async_add_external_statistics(
        hass,
        metadata(statistic_id, nome, servizio=servizio, unita_contatore=unita_contatore),
        da_scrivere,
    )
    _LOGGER.info(
        "%s: scritte %d ore, dal %s al %s",
        statistic_id,
        len(da_scrivere),
        da_scrivere[0]["start"].isoformat(),
        da_scrivere[-1]["start"].isoformat(),
    )
