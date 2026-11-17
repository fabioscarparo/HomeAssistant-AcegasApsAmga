"""External statistics for the Energy Dashboard.

One series per contract, named after the supply point code:
acegasapsamga:<pod>_acqua (and <pod>_gas once gas is enabled).

The whole series is rewritten every time, from all the readings: that keeps
it consistent after corrections. If it got shorter it is cleared first, so no
stale hours stay after its end.
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
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SERVIZIO_ACQUA, SERVIZIO_GAS

_LOGGER = logging.getLogger(__name__)

SUFFISSI = {SERVIZIO_ACQUA: "acqua", SERVIZIO_GAS: "gas"}


def statistic_id(servizio: str, codice: str) -> str:
    slug = re.sub(r"[^a-z0-9_]", "_", codice.lower())
    return f"{DOMAIN}:{slug}_{SUFFISSI[servizio]}"


def metadata(statistic_id: str, nome: str) -> dict[str, Any]:
    return {
        "mean_type": StatisticMeanType.NONE,
        "has_sum": True,
        "name": nome,
        "source": DOMAIN,
        "statistic_id": statistic_id,
        "unit_of_measurement": UnitOfVolume.CUBIC_METERS,
        "unit_class": "volume",
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


async def async_scrivi_serie(
    hass: HomeAssistant,
    statistic_id: str,
    nome: str,
    righe: list[dict[str, Any]],
    *,
    ultima_ora_scritta: datetime | None,
) -> None:
    if not righe:
        return
    if ultima_ora_scritta is not None and righe[-1]["start"] < ultima_ora_scritta:
        _LOGGER.info("%s: la serie si è accorciata, la riscrivo da zero", statistic_id)
        # The Recorder runs its jobs in order: the clear happens before the import.
        get_instance(hass).async_clear_statistics([statistic_id])
    async_add_external_statistics(hass, metadata(statistic_id, nome), righe)
    _LOGGER.info(
        "%s: scritte %d ore, dal %s al %s",
        statistic_id,
        len(righe),
        righe[0]["start"].isoformat(),
        righe[-1]["start"].isoformat(),
    )
