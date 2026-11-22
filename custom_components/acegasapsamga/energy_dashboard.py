"""Adds metered contracts to the Energy Dashboard as water, gas, or grid sources.

Sources that already exist are left untouched, so it is safe to run again.
No price is set: Home Assistant does not accept a price on an external statistic.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.energy.data import EnergyPreferencesUpdate, async_get_manager
from homeassistant.core import HomeAssistant

from .const import SERVIZIO_ACQUA, SERVIZIO_GAS, SERVIZIO_LUCE
from .coordinator import AcegasCoordinator
from .testi import testo

_LOGGER = logging.getLogger(__name__)

TIPI_SORGENTE = {
    SERVIZIO_ACQUA: "water",
    SERVIZIO_GAS: "gas",
    SERVIZIO_LUCE: "grid",
}


def _sorgente(tipo: str, sid: str, nome: str) -> dict[str, Any]:
    if tipo == "grid":
        return {
            "type": "grid",
            "stat_energy_from": sid,
            "stat_energy_to": None,
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": None,
            "stat_compensation": None,
            "entity_energy_price_export": None,
            "number_energy_price_export": None,
            "cost_adjustment_day": 0.0,
            "name": nome,
        }
    return {
        "type": tipo,
        "stat_energy_from": sid,
        "stat_cost": None,
        "entity_energy_price": None,
        "number_energy_price": None,
        "name": nome,
    }


async def async_configura_energy_dashboard(
    hass: HomeAssistant, coordinatori: list[AcegasCoordinator]
) -> list[str]:
    """Add the missing sources. Returns the statistic ids added."""
    manager = await async_get_manager(hass)
    sorgenti: list[dict[str, Any]] = (
        [dict(s) for s in manager.data["energy_sources"]] if manager.data else []
    )
    presenti = {s.get("stat_energy_from") for s in sorgenti}

    aggiunte: list[str] = []
    for coordinator in coordinatori:
        for contratto in coordinator.contratti:
            tipo = TIPI_SORGENTE.get(contratto["servizio"])
            if tipo is None:
                continue
            sid = coordinator.statistic_id(contratto)
            if sid in presenti:
                continue
            nome = (
                f"{testo(coordinator.lingua, 'servizio_' + contratto['servizio'])} "
                f"{coordinator.codice(contratto)}"
            )
            sorgenti.append(_sorgente(tipo, sid, nome))
            presenti.add(sid)
            aggiunte.append(sid)

    if not aggiunte:
        _LOGGER.info("Energy Dashboard: nessuna sorgente da aggiungere, già tutto configurato")
        return aggiunte
    aggiornamento: EnergyPreferencesUpdate = {"energy_sources": sorgenti}
    await manager.async_update(aggiornamento)
    _LOGGER.info("Energy Dashboard: aggiunte le sorgenti %s", ", ".join(aggiunte))
    return aggiunte
