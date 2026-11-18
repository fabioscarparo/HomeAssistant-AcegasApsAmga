"""Full setup with a real Recorder: statistics, sensors, saved data, reauth."""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import get_last_statistics, get_metadata
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.acegasapsamga import coordinator as coord
from custom_components.acegasapsamga.api import ApiError
from custom_components.acegasapsamga.auth import CredenzialiNonValide, Token

from .conftest import carica

STATISTICA = "acegasapsamga:0500000000000001_acqua"
ADESSO = "2026-11-17 12:00:00+00:00"


class PortaleFinto:
    """Stands in for both AuthClient and ApiClient."""

    def __init__(self):
        self.archivio = carica("archivio_acqua.json")["list"]
        self.bollette = carica("bollette.json")["list"]
        self.errore_api: Exception | None = None
        self.errore_bollette: Exception | None = None
        self.raggruppamenti = 0
        self.errore_login: Exception | None = None
        self.accessi = 0
        self.access_token = ""

    async def async_login(self, email, password):
        if self.errore_login:
            raise self.errore_login
        self.accessi += 1
        return Token("AT", "RT", time.time() + 3600, "utente-1")

    async def async_refresh(self, refresh_token):
        return Token("AT2", "RT2", time.time() + 3600, "utente-1")

    async def async_letture(self, profilo, servizio, contratto):
        if self.errore_api:
            raise self.errore_api
        return self.archivio

    async def async_consumi(self, profilo, contratto):
        return carica("consumi_acqua.json")["list"]

    async def async_finestra_autolettura(self, profilo, contratto):
        return carica("finestra.json")

    async def async_raggruppamento_bollette(self, profilo):
        self.raggruppamenti += 1
        return "PLICO"

    async def async_bollette(self, profilo, raggruppamento):
        assert raggruppamento == "PLICO"
        if self.errore_bollette:
            raise self.errore_bollette
        return self.bollette


@pytest.fixture
def portale(monkeypatch) -> PortaleFinto:
    finto = PortaleFinto()
    monkeypatch.setattr(coord, "AuthClient", lambda session: finto)
    monkeypatch.setattr(coord, "ApiClient", lambda session: finto)
    return finto


def _stato(hass, chiave: str):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", "acegasapsamga", f"1000000001_{chiave}")
    return hass.states.get(entity_id)


async def _ultima_statistica(hass):
    ultime = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, STATISTICA, False, {"sum", "state"}
    )
    return ultime[STATISTICA][0]


async def test_setup_scrive_statistiche_e_sensori(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    freezer.move_to(ADESSO)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    assert entry.state is ConfigEntryState.LOADED
    ultima = await _ultima_statistica(hass)
    assert ultima["sum"] == pytest.approx(28.0)
    assert ultima["state"] == pytest.approx(28.0)
    metadati = await get_instance(hass).async_add_executor_job(
        lambda: get_metadata(hass, statistic_ids={STATISTICA})
    )
    assert metadati[STATISTICA][1]["unit_of_measurement"] == "m³"
    assert metadati[STATISTICA][1]["has_sum"]

    lettura = _stato(hass, "lettura")
    assert lettura.state == "28.0"
    assert lettura.attributes["device_class"] == "water"
    assert "state_class" not in lettura.attributes
    assert lettura.attributes["letture"][0] == {"giorno": "2026-11-11", "valore": 28.0, "tipo": "ESTIMATED"}
    assert _stato(hass, "data_lettura").state == "2026-09-22"
    periodo = _stato(hass, "consumo_periodo")
    assert periodo.state == "6.0"
    assert periodo.attributes["dal"] == "2026-08-26"
    assert len(periodo.attributes["periodi"]) == 9
    assert periodo.attributes["periodi"][-1] == {"dal": "2026-08-26", "al": "2026-09-22", "giorni": 28, "consumo": 6.0}
    assert float(_stato(hass, "media_giornaliera").state) == pytest.approx(214.3)
    autolettura = _stato(hass, "autolettura")
    assert autolettura.state == "2027-02-28"
    assert autolettura.attributes["fine"] == "2027-03-05"

    bolletta = _stato(hass, "bolletta")
    assert bolletta.state == "48.2"
    assert bolletta.attributes["unit_of_measurement"] == "EUR"
    assert bolletta.attributes["device_class"] == "monetary"
    assert bolletta.attributes["numero"] == "0000000000000103"
    assert bolletta.attributes["emissione"] == "2026-11-13"
    assert bolletta.attributes["scadenza"] == "2026-12-09"
    assert bolletta.attributes["domiciliata"] is True
    assert [b["stato"] for b in bolletta.attributes["bollette"]] == ["unpaid", "paid", "paid"]
    assert _stato(hass, "da_pagare").state == "48.2"
    assert _stato(hass, "scadenza_bolletta").state == "2026-12-09"
    stato = _stato(hass, "stato_bolletta")
    assert stato.state == "unpaid"
    assert "other" in stato.attributes["options"]


async def test_bollette_pagate_e_errori(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    freezer.move_to(ADESSO)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The bill is paid: nothing due and no due date.
    portale.bollette = [dict(portale.bollette[0], paymentStatus="PAID", residual=0.0), *portale.bollette[1:]]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert _stato(hass, "stato_bolletta").state == "paid"
    assert _stato(hass, "da_pagare").state == "0.0"
    assert _stato(hass, "scadenza_bolletta").state == "unknown"

    # Bills that cannot be read leave the readings alone and keep the last ones.
    portale.errore_bollette = ApiError("down", status=503)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert entry.runtime_data.last_update_success
    assert _stato(hass, "stato_bolletta").state == "paid"
    assert _stato(hass, "bolletta").state == "48.2"
    # The grouping of the bills is read once.
    assert portale.raggruppamenti == 1


async def test_senza_novita_non_riscrive(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    freezer.move_to(ADESSO)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    with patch.object(coord, "async_scrivi_serie") as scrivi:
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
    scrivi.assert_not_called()

    # A new real reading rewrites the series.
    nuova = dict(portale.archivio[1], date=1794268800000, type="REAL")  # 2026-11-10
    nuova["measurements"] = [{"value": 31.0, "correttore": False}]
    portale.archivio = [nuova, *portale.archivio]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    assert (await _ultima_statistica(hass))["sum"] == pytest.approx(31.0)
    assert _stato(hass, "lettura").state == "31.0"


async def test_dati_salvati_se_il_portale_non_risponde(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    freezer.move_to(ADESSO)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)

    portale.errore_api = ApiError("down", status=503)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert _stato(hass, "lettura").state == "28.0"
    assert _stato(hass, "bolletta").state == "48.2"
    assert entry.runtime_data.update_interval == coord.INTERVALLO_DOPO_ERRORE


async def test_primo_avvio_senza_portale_riprova(recorder_mock, hass, entry, portale):
    portale.errore_api = ApiError("down", rete=True)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_password_cambiata_chiede_riautenticazione(recorder_mock, hass, entry, portale):
    portale.errore_login = CredenzialiNonValide("Credenziali non valide.")
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flussi = hass.config_entries.flow.async_progress_by_handler("acegasapsamga")
    assert [f["context"]["source"] for f in flussi] == ["reauth"]


async def test_token_rifiutato_nuovo_accesso(recorder_mock, hass, entry, portale, freezer):
    freezer.move_to(ADESSO)
    from custom_components.acegasapsamga.api import TokenScaduto

    letture = portale.async_letture
    chiamate = SimpleNamespace(n=0)

    async def una_volta_rifiutato(*argomenti):
        chiamate.n += 1
        if chiamate.n == 1:
            raise TokenScaduto("scaduto", status=403)
        return await letture(*argomenti)

    portale.async_letture = una_volta_rifiutato
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert chiamate.n == 2
    assert _stato(hass, "lettura").state == "28.0"


async def test_sessioni_con_cookie_jar_per_b2c(hass, entry, monkeypatch):
    from custom_components.acegasapsamga import config_flow as cf

    usati = []

    def crea(hass, **kwargs):
        usati.append(kwargs["cookie_jar"])
        return SimpleNamespace(detach=lambda: None)

    monkeypatch.setattr(coord, "async_create_clientsession", crea)
    monkeypatch.setattr(cf, "async_create_clientsession", crea)
    coord.AcegasCoordinator(hass, entry)
    with patch.object(cf, "AuthClient", side_effect=ApiError("stop")), pytest.raises(ApiError):
        await cf.async_accedi(hass, "utente@example.com", "segreta")
    assert len(usati) == 2
    assert all(jar._quote_cookie is False for jar in usati)
