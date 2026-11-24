"""AcegasApsAmga: meter readings, waste tracking, bills, calendar and actions
from the Servizi Online portal."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    SERVIZI_CONSUMO,
    SERVIZIO_CONFIGURA_ENERGY_DASHBOARD,
    SERVIZIO_INVIA_AUTOLETTURA,
    SERVIZIO_SCARICA_BOLLETTA,
)
from .coordinator import VERSIONE_STORE, AcegasCoordinator
from .energy_dashboard import async_configura_energy_dashboard
from .lovelace_card import async_registra_card

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AcegasConfigEntry = ConfigEntry[AcegasCoordinator]

SCHEMA_INVIA_AUTOLETTURA = vol.Schema(
    {
        vol.Optional("device_id"): cv.string,
        vol.Optional("contratto"): cv.string,
        vol.Optional("valore"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("f1"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("f2"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("f3"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)

SCHEMA_SCARICA_BOLLETTA = vol.Schema(
    {
        vol.Optional("device_id"): cv.string,
        vol.Optional("contratto"): cv.string,
        vol.Optional("numero"): cv.string,
        vol.Optional("dettaglio", default=False): cv.boolean,
        vol.Optional("percorso"): cv.string,
    }
)


def _risolvi_contratto(
    hass: HomeAssistant,
    coordinatori: list[AcegasCoordinator],
    *,
    device_id: str | None = None,
    contratto: str | None = None,
    solo_consumo: bool = False,
) -> tuple[AcegasCoordinator, str]:
    """Find (coordinator, contract_number) from device_id, contract number, or single fallback."""
    if not coordinatori:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="nessuna_configurazione"
        )

    numero_cercato = (contratto or "").strip() or None
    if device_id and not numero_cercato:
        dispositivo = dr.async_get(hass).async_get(device_id)
        if dispositivo is not None:
            for dominio, ident in dispositivo.identifiers:
                if dominio == DOMAIN and not str(ident).startswith("account_"):
                    numero_cercato = str(ident)
                    break

    if numero_cercato:
        for coord in coordinatori:
            if coord.trova_contratto(numero_cercato) is not None:
                return coord, numero_cercato
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="contratto_non_trovato",
            translation_placeholders={"contratto": numero_cercato},
        )

    candidati = [
        (coord, c["contratto"])
        for coord in coordinatori
        for c in coord.contratti
        if not solo_consumo or c.get("servizio") in SERVIZI_CONSUMO
    ]
    if len(candidati) == 1:
        return candidati[0]
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="contratto_non_trovato",
        translation_placeholders={"contratto": device_id or "-"},
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the Lovelace cards and register the integration's actions."""
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

    async def _invia_autolettura(call: ServiceCall) -> ServiceResponse:
        coordinatori = [
            entry.runtime_data for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        ]
        coord, numero = _risolvi_contratto(
            hass,
            coordinatori,
            device_id=call.data.get("device_id"),
            contratto=call.data.get("contratto"),
            solo_consumo=True,
        )
        risultato = await coord.async_invia_autolettura(
            numero,
            valore=call.data.get("valore"),
            f1=call.data.get("f1"),
            f2=call.data.get("f2"),
            f3=call.data.get("f3"),
        )
        return risultato if call.return_response else None

    async def _scarica_bolletta(call: ServiceCall) -> ServiceResponse:
        coordinatori = [
            entry.runtime_data for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        ]
        coord, numero = _risolvi_contratto(
            hass,
            coordinatori,
            device_id=call.data.get("device_id"),
            contratto=call.data.get("contratto"),
        )
        risultato = await coord.async_scarica_bolletta(
            numero,
            numero_bolletta=call.data.get("numero"),
            dettaglio=call.data.get("dettaglio", False),
            percorso=call.data.get("percorso"),
        )
        return risultato if call.return_response else None

    # All three change something: the Energy dashboard settings, a reading sent
    # to the utility, a file on disk. Only administrators may call them;
    # automations and scripts run without a user and keep working.
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVIZIO_CONFIGURA_ENERGY_DASHBOARD,
        _configura_energy_dashboard,
        supports_response=SupportsResponse.OPTIONAL,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVIZIO_INVIA_AUTOLETTURA,
        _invia_autolettura,
        schema=SCHEMA_INVIA_AUTOLETTURA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVIZIO_SCARICA_BOLLETTA,
        _scarica_bolletta,
        schema=SCHEMA_SCARICA_BOLLETTA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AcegasConfigEntry) -> bool:
    coordinator = AcegasCoordinator(hass, entry)
    entry.runtime_data = coordinator
    if await coordinator.async_carica_cache():
        # With saved data the entities come up right away and the portal is
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
    """Delete saved data and repair issues. Recorder statistics stay as user history."""
    ir.async_delete_issue(hass, DOMAIN, f"password_scadenza_{entry.entry_id}")
    ir.async_delete_issue(hass, DOMAIN, f"nuove_condizioni_{entry.entry_id}")
    await Store(hass, VERSIONE_STORE, f"{DOMAIN}.{entry.entry_id}").async_remove()
