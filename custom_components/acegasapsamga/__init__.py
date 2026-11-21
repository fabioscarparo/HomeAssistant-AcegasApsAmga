"""AcegasApsAmga: meter readings from the Servizi Online portal, as statistics
for the Energy Dashboard."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import VERSIONE_STORE, AcegasCoordinator
from .energy_dashboard import async_configura_energy_dashboard
from .lovelace_card import async_registra_card

PLATFORMS: list[Platform] = [Platform.SENSOR]
SERVIZIO_CONFIGURA_ENERGY_DASHBOARD = "configura_energy_dashboard"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AcegasConfigEntry = ConfigEntry[AcegasCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the card and register the integration's actions."""
    await async_registra_card(hass)

    async def _configura_energy_dashboard(call: ServiceCall) -> ServiceResponse:
        coordinatori = [
            entry.runtime_data for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        ]
        if not coordinatori:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="nessuna_configurazione"
            )
        aggiunte = await async_configura_energy_dashboard(hass, coordinatori)
        return {"aggiunte": aggiunte} if call.return_response else None

    hass.services.async_register(
        DOMAIN,
        SERVIZIO_CONFIGURA_ENERGY_DASHBOARD,
        _configura_energy_dashboard,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AcegasConfigEntry) -> bool:
    coordinator = AcegasCoordinator(hass, entry)
    entry.runtime_data = coordinator
    if await coordinator.async_carica_cache():
        # With saved data the sensors come up right away and the portal is
        # refreshed without blocking Home Assistant's startup. Forwarding
        # platforms first also ensures a failed auth cancels the polling timer.
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_create_task(
            hass, coordinator.async_refresh(), f"{DOMAIN}_refresh_{entry.entry_id}"
        )
        return True
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AcegasConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the saved readings. The statistics stay: they are the user's history."""
    await Store(hass, VERSIONE_STORE, f"{DOMAIN}.{entry.entry_id}").async_remove()
