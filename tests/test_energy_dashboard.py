"""Energy Dashboard action and diagnostics."""
from __future__ import annotations

import json

import pytest
from homeassistant.components.energy.data import async_get_manager
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from custom_components.acegasapsamga.diagnostics import async_get_config_entry_diagnostics

from .test_integrazione import ADESSO, STATISTICA, portale  # noqa: F401


async def test_configura_energy_dashboard(recorder_mock, hass, entry, portale, freezer):  # noqa: F811
    freezer.move_to(ADESSO)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    risposta = await hass.services.async_call(
        "acegasapsamga", "configura_energy_dashboard", blocking=True, return_response=True
    )
    assert risposta == {"aggiunte": [STATISTICA]}
    manager = await async_get_manager(hass)
    assert manager.data["energy_sources"] == [
        {
            "type": "water",
            "stat_energy_from": STATISTICA,
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": None,
            "name": "Water 0500000000000001",
        }
    ]

    # A second run adds nothing.
    risposta = await hass.services.async_call(
        "acegasapsamga", "configura_energy_dashboard", blocking=True, return_response=True
    )
    assert risposta == {"aggiunte": []}
    assert len(manager.data["energy_sources"]) == 1


async def test_configura_senza_configurazioni(hass):
    assert await async_setup_component(hass, "acegasapsamga", {})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("acegasapsamga", "configura_energy_dashboard", blocking=True)


async def test_diagnostica_senza_dati_personali(recorder_mock, hass, entry, portale, freezer):  # noqa: F811
    freezer.move_to(ADESSO)
    # Include an older replaced meter, an unconfigured contract in a grouped bill,
    # an uppercase POD and the user's email inside ultimo_errore.
    vecchia = dict(portale.archivio[-1], meterId="VECCHIA_MATRICOLA_99")
    portale.archivio = [*portale.archivio[:-1], vecchia]
    portale.bollette = [
        dict(
            portale.bollette[0],
            contractServiceTypeList=[
                {"contractId": "1000000001", "type": "WATER"},
                {"contractId": "9999999999", "type": "GAS"},
            ],
        ),
        *portale.bollette[1:],
    ]
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entry.runtime_data.ultimo_errore = "Account utente@example.com locked"
    entry.runtime_data.serie_scritte["acegasapsamga:it001e_pod_maiuscolo_acqua"] = ADESSO
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "contratti": [{**entry.data["contratti"][0], "pod": "IT001E-POD-MAIUSCOLO"}],
        },
    )

    testo = json.dumps(await async_get_config_entry_diagnostics(hass, entry))
    for dato in (
        "utente@example.com",
        "segreta",
        "1000000001",
        "9999999999",
        "IT001E-POD-MAIUSCOLO",
        "it001e_pod_maiuscolo",
        "MATRICOLA0001",
        "VECCHIA_MATRICOLA_99",
        "VIA DI ESEMPIO",
        "0000000000000103",
    ):
        assert dato not in testo
    assert "CONTRATTO_1" in testo
    assert "CONTRATTO_2" in testo
    assert "CONTATORE_2" in testo
    assert "BOLLETTA_1" in testo
    assert "EMAIL" in testo
