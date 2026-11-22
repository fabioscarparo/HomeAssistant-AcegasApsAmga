"""Energy Dashboard action (water, gas, grid) and diagnostics redaction."""
from __future__ import annotations

import json

import pytest
from homeassistant.components.energy.data import async_get_manager
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from custom_components.acegasapsamga.const import CONF_CONTRATTI
from custom_components.acegasapsamga.diagnostics import async_get_config_entry_diagnostics

from .conftest import CONTRATTO
from .test_integrazione import ADESSO, STATISTICA, portale  # noqa: F401


async def test_configura_energy_dashboard_multiservizio(recorder_mock, hass, entry, portale, freezer):  # noqa: F811
    freezer.move_to(ADESSO)
    gas = dict(CONTRATTO, contratto="2000000001", servizio="GAS", pod="00880000000001", contatore="MG1")
    luce = dict(CONTRATTO, contratto="3000000001", servizio="ELECTRIC", pod="IT001E00000001", contatore="ME1")
    tlr = dict(CONTRATTO, contratto="4000000001", servizio="HEATING", pod="TLR0001", contatore="MT1")
    rifiuti = dict(CONTRATTO, contratto="5000000001", servizio="ENVIRONMENT", pod="TARI0001", contatore=None)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_CONTRATTI: [dict(CONTRATTO), gas, luce, tlr, rifiuti]}
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    risposta = await hass.services.async_call(
        "acegasapsamga", "configura_energy_dashboard", blocking=True, return_response=True
    )
    assert risposta == {
        "aggiunte": [
            STATISTICA,
            "acegasapsamga:00880000000001_gas",
            "acegasapsamga:it001e00000001_luce",
        ]
    }
    manager = await async_get_manager(hass)
    tipi = {s["stat_energy_from"]: s["type"] for s in manager.data["energy_sources"]}
    assert tipi == {
        STATISTICA: "water",
        "acegasapsamga:00880000000001_gas": "gas",
        "acegasapsamga:it001e00000001_luce": "grid",
    }

    # A second run adds nothing.
    risposta = await hass.services.async_call(
        "acegasapsamga", "configura_energy_dashboard", blocking=True, return_response=True
    )
    assert risposta == {"aggiunte": []}
    assert len(manager.data["energy_sources"]) == 3


async def test_configura_senza_configurazioni(hass):
    assert await async_setup_component(hass, "acegasapsamga", {})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("acegasapsamga", "configura_energy_dashboard", blocking=True)


async def test_diagnostica_senza_dati_personali(recorder_mock, hass, entry, portale, freezer):  # noqa: F811
    freezer.move_to(ADESSO)
    vecchia = dict(portale.archivio[-1], meterId="VECCHIA_MATRICOLA_99")
    portale.archivio = [*portale.archivio[:-1], vecchia]
    portale.bollette = [
        dict(
            portale.bollette[0],
            contractServiceTypeList=[
                {"contractId": "1000000001", "type": "WATER"},
                {"contractId": "9999999999", "type": "GAS"},
            ],
            companyServices=[
                {"type": "WATER", "amount": 48.2, "reverserBillId": "STORNATA_777"},
            ],
        ),
        *portale.bollette[1:],
    ]
    portale.notifiche = {
        "totale": 1,
        "non_lette": 1,
        "lista": [
            {
                "id": "N1",
                "letta": False,
                "tipo": "ALERT",
                "titolo": "Avviso",
                "sottotitolo": "Via Privata Segreta 42",
                "descrizione": "Dettaglio personale utente@example.com",
                "data": "2026-11-10",
            }
        ],
    }
    rifiuti = dict(CONTRATTO, contratto="5000000001", servizio="ENVIRONMENT", pod="TARI0001", contatore=None)
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_CONTRATTI: [
                {**entry.data[CONF_CONTRATTI][0], "pod": "IT001E-POD-MAIUSCOLO"},
                rifiuti,
            ],
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entry.runtime_data.ultimo_errore = "Account utente@example.com locked"
    entry.runtime_data.serie_scritte["acegasapsamga:it001e_pod_maiuscolo_acqua"] = ADESSO

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
        "STORNATA_777",
        "200000000001",
        "EQ-SECRET-99",
        "Via Privata Segreta 42",
    ):
        assert dato not in testo, dato
    assert "CONTRATTO_1" in testo
    assert "CONTATORE_3" in testo
    assert "BOLLETTA_1" in testo
    assert "DOTAZIONE_1" in testo
    assert "EMAIL" in testo
