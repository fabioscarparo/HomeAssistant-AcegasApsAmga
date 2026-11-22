"""Full integration tests: Recorder statistics, sensors, calendar, repairs, actions and multi-service."""
from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import get_last_statistics, get_metadata
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.acegasapsamga import coordinator as coord
from custom_components.acegasapsamga.api import (
    ApiError,
    AutoletturaFuoriFinestra,
    AutoletturaInferiore,
)
from custom_components.acegasapsamga.auth import CredenzialiNonValide, Token
from custom_components.acegasapsamga.const import CONF_CONTRATTI, DOMAIN

from .conftest import CONTRATTO, carica

STATISTICA = "acegasapsamga:0500000000000001_acqua"
ADESSO = "2026-11-17 12:00:00+00:00"


class PortaleFinto:
    """Stands in for both AuthClient and ApiClient."""

    def __init__(self):
        self.archivio = carica("archivio_acqua.json")["list"]
        self.autoletture_archivio: list[dict] = [
            {
                "date": 1790035200000,
                "type": "SELFREADING",
                "status": "OK",
                "channel": "WEB",
                "meterId": "MATRICOLA0001",
                "measurements": [{"value": 28.0, "correttore": False}],
            }
        ]
        self.bollette = carica("bollette.json")["list"]
        self.pagamenti = [
            {
                "id": "INV1",
                "amount": 31.75,
                "paymentStatus": "PAYMENT",
                "paymentDate": 1786053600000,
                "billIds": ["0000000000000102"],
            }
        ]
        self.utente = {
            "cambio_password": "2026-11-13",
            "scadenza_password": "2027-05-12",
            "rinnovo_password": False,
            "nuove_condizioni_accettate": True,
            "energy_manager": False,
            "hera_ambiente": False,
        }
        self.profilo_info = {
            "raggruppamento": "PLICO",
            "letture_giornaliere": False,
            "gestore_acqua": True,
            "gestore_ambiente": False,
            "energy_wallet": False,
            "zcode": "Z001",
            "numerosita_contratti": 1,
        }
        self.notifiche = {
            "totale": 2,
            "non_lette": 1,
            "lista": [
                {
                    "id": "N1",
                    "letta": False,
                    "tipo": "ALERT",
                    "titolo": "Avviso idrico",
                    "sottotitolo": "Manutenzione programmata",
                    "descrizione": "Dettaglio",
                    "data": "2026-11-15",
                }
            ],
        }
        self.conf_notifiche = [
            {
                "id": "W1",
                "nome": "Interruzioni idriche",
                "tipo": "WATER_SERVICE",
                "categoria": "WTR_FLT",
                "attivo": True,
            }
        ]
        self.vas = [
            {
                "servizio": "WATER",
                "contratto": "1000000001",
                "bolletta_email": True,
                "servizi": [{"id": "AC", "stato": "active", "riferimento": "ORS", "offerta": "ACDOM"}],
            }
        ]
        self.calendario = [
            {"period": "2027-03", "startDate": 1803769200000, "endDate": 1804201200000},
            {"period": "2027-06", "startDate": 1811800800000, "endDate": 1812232800000},
        ]
        self.consumi_giornalieri = [
            {"usageFromDate": 1794700800000, "totalUsage": 0.25, "readType": "REAL"}
        ]
        self.dotazioni_rifiuti = [
            {
                "equipmentCode": "EQ-SECRET-99",
                "type": "BIDONE",
                "status": "ACTIVE",
                "description": "Bidone RSU 120L",
                "volume": 120,
                "assignmentDate": 1764201600000,
            }
        ]
        self.svuotamenti_rifiuti = {
            "RSU": {
                "CURRENT": {
                    "totalVolume": 240,
                    "wasteDisposals": [
                        {
                            "equipmentCode": "EQ-SECRET-99",
                            "equipmentType": "BIDONE",
                            "wasteType": "RSU",
                            "volume": 120,
                            "disposalDate": 1790035200000,
                        },
                        {
                            "equipmentCode": "EQ-SECRET-99",
                            "equipmentType": "BIDONE",
                            "wasteType": "RSU",
                            "volume": 120,
                            "disposalDate": 1792000000000,
                        },
                    ],
                },
                "PREVIOUS": {"totalVolume": 360, "wasteDisposals": []},
            }
        }
        self.vantaggi_rifiuti = [{"siebelValue": "V1", "friendlyName": "Compostaggio"}]
        self.ultima_lettura_struttura: dict | None = {
            "measurements": [
                {"id": "WATER", "type": "WATER", "bands": [{"id": "001", "type": "F0", "value": 28}]}
            ]
        }
        self.autoletture_inviate: list[dict] = []
        self.errore_invio: Exception | None = None
        self.pdf_bytes: bytes = b"%PDF-1.4 finto"
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

    async def async_utente(self):
        return dict(self.utente)

    async def async_profilo(self, profilo):
        self.raggruppamenti += 1
        return dict(self.profilo_info)

    async def async_raggruppamento_bollette(self, profilo):
        return (await self.async_profilo(profilo)).get("raggruppamento")

    async def async_letture(self, profilo, servizio, contratto):
        if self.errore_api:
            raise self.errore_api
        return self.archivio

    async def async_autoletture(self, profilo, servizio, contratto):
        return self.autoletture_archivio

    async def async_consumi(self, profilo, contratto):
        return carica("consumi_acqua.json")["list"]

    async def async_consumi_giornalieri(self, profilo, contratto, pdr, dal_ms, al_ms):
        return self.consumi_giornalieri

    async def async_finestra_autolettura(self, profilo, contratto):
        return carica("finestra.json")

    async def async_calendario_autoletture(self, profilo, contratto):
        return self.calendario

    async def async_ultima_lettura_contatore(self, profilo, contratto, contatore, *, pod=False):
        return self.ultima_lettura_struttura

    async def async_invia_autolettura(self, profilo, payload):
        if self.errore_invio:
            raise self.errore_invio
        self.autoletture_inviate.append(payload)
        return None

    async def async_bollette(self, profilo, raggruppamento):
        assert raggruppamento == "PLICO"
        if self.errore_bollette:
            raise self.errore_bollette
        return self.bollette

    async def async_pagamenti_bollette(self, profilo):
        return self.pagamenti

    async def async_bolletta_pdf(self, profilo, numero, *, dettaglio=False):
        return self.pdf_bytes

    async def async_notifiche(self, profilo):
        return self.notifiche

    async def async_configurazione_notifiche(self, profilo):
        return self.conf_notifiche

    async def async_vas(self, profilo):
        return self.vas

    async def async_dotazioni_rifiuti(self, profilo, contratto):
        return self.dotazioni_rifiuti

    async def async_svuotamenti_rifiuti(self, profilo, contratto, *, tipo="RSU", anno="CURRENT"):
        return self.svuotamenti_rifiuti.get(tipo, {}).get(anno, {"wasteDisposals": [], "totalVolume": None})

    async def async_vantaggi_rifiuti(self, profilo, contratto):
        return self.vantaggi_rifiuti


@pytest.fixture
def portale(monkeypatch) -> PortaleFinto:
    finto = PortaleFinto()
    monkeypatch.setattr(coord, "AuthClient", lambda session: finto)
    monkeypatch.setattr(coord, "ApiClient", lambda session: finto)
    return finto


def _stato(hass, chiave: str, contratto: str = "1000000001"):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{contratto}_{chiave}")
    return hass.states.get(entity_id)


def _stato_account(hass, entry_id: str, chiave: str):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"account_{entry_id}_{chiave}")
    return hass.states.get(entity_id)


async def _ultima_statistica(hass, sid: str = STATISTICA):
    ultime = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, sid, False, {"sum", "state"}
    )
    return ultime[sid][0]


async def test_setup_scrive_statistiche_sensori_account_e_calendario(
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
    assert lettura.attributes["servizio"] == "WATER"
    assert lettura.attributes["diario_consumi"] is True
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
    assert autolettura.attributes["giorni_mancanti"] == 103
    assert autolettura.attributes["ultima_autolettura"] == "2026-09-22"
    assert autolettura.attributes["stato_ultima_autolettura"] == "OK"

    bolletta = _stato(hass, "bolletta")
    assert bolletta.state == "48.2"
    assert bolletta.attributes["stato_dettaglio"] == "Pagamento in ricezione"
    assert bolletta.attributes["pdf_disponibile"] is True
    assert bolletta.attributes["importo_servizio"] == 48.2
    assert bolletta.attributes["bollette"][1]["data_pagamento"] == "2026-08-07"
    assert _stato(hass, "da_pagare").state == "48.2"
    assert _stato(hass, "scadenza_bolletta").state == "2026-12-09"
    stato = _stato(hass, "stato_bolletta")
    assert stato.state == "unpaid"
    assert stato.attributes["stato_dettaglio"] == "Pagamento in ricezione"

    # Account-level sensors
    pwd = _stato_account(hass, entry.entry_id, "scadenza_password")
    assert pwd.state == "2027-05-12"
    assert pwd.attributes["giorni_rimanenti"] > 100
    assert pwd.attributes["rinnovo_richiesto"] is False
    notif = _stato_account(hass, entry.entry_id, "notifiche")
    assert notif.state == "1"
    assert notif.attributes["avvisi_idrici_attivi"] is True
    assert notif.attributes["ultima_notifica"] == "Avviso idrico"

    # Calendar platform
    cal_id = er.async_get(hass).async_get_entity_id("calendar", DOMAIN, "1000000001_calendario")
    assert cal_id is not None
    cal_state = hass.states.get(cal_id)
    assert cal_state is not None
    cal_ent = hass.data["entity_components"]["calendar"].get_entity(cal_id)
    eventi = await cal_ent.async_get_events(
        hass,
        datetime(2026, 12, 1, tzinfo=UTC),
        datetime(2027, 7, 1, tzinfo=UTC),
    )
    # Unpaid bill due 2026-12-09 + 2 self-reading windows in 2027
    assert len(eventi) == 3
    assert eventi[0].start.isoformat() == "2026-12-09"
    assert eventi[1].start.isoformat() == "2027-02-28"
    assert eventi[1].end.isoformat() == "2027-03-06"


async def test_repair_issues_password_e_condizioni(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    freezer.move_to(ADESSO)
    portale.utente = {
        "cambio_password": "2026-06-01",
        "scadenza_password": "2026-11-25",  # 8 days left -> warning issue
        "rinnovo_password": False,
        "nuove_condizioni_accettate": False,
        "energy_manager": False,
        "hera_ambiente": False,
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reg = ir.async_get(hass)
    assert reg.async_get_issue(DOMAIN, f"password_scadenza_{entry.entry_id}") is not None
    assert reg.async_get_issue(DOMAIN, f"nuove_condizioni_{entry.entry_id}") is not None

    # Resolve both on the portal -> repair issues are automatically deleted.
    portale.utente["scadenza_password"] = "2027-05-12"
    portale.utente["nuove_condizioni_accettate"] = True
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert reg.async_get_issue(DOMAIN, f"password_scadenza_{entry.entry_id}") is None
    assert reg.async_get_issue(DOMAIN, f"nuove_condizioni_{entry.entry_id}") is None


async def test_azioni_invia_autolettura_e_scarica_bolletta(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    freezer.move_to(ADESSO)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # 1. Submit water self-reading
    risposta = await hass.services.async_call(
        DOMAIN,
        "invia_autolettura",
        {"valore": 31},
        blocking=True,
        return_response=True,
    )
    assert risposta["inviata"] is True
    assert portale.autoletture_inviate[-1]["measurements"][0]["bands"][0]["value"] == 31.0

    # 2. HTTP 692 and 695 raise ServiceValidationError
    portale.errore_invio = AutoletturaInferiore("low", status=692)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "invia_autolettura", {"valore": 5}, blocking=True)
    portale.errore_invio = AutoletturaFuoriFinestra("closed", status=695)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "invia_autolettura", {"valore": 35}, blocking=True)
    portale.errore_invio = None

    # 3. Download latest bill PDF into HA config dir
    pdf_res = await hass.services.async_call(
        DOMAIN,
        "scarica_bolletta",
        {},
        blocking=True,
        return_response=True,
    )
    assert pdf_res["numero"] == "0000000000000103"
    assert pdf_res["dimensione"] == len(b"%PDF-1.4 finto")
    assert Path(pdf_res["percorso"]).read_bytes() == b"%PDF-1.4 finto"

    # 4. Path traversal and non-pdf paths are rejected
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "scarica_bolletta", {"percorso": "../../outside.pdf"}, blocking=True
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "scarica_bolletta", {"percorso": "www/bolletta.txt"}, blocking=True
        )


async def test_multiservizio_luce_tlr_rifiuti_e_letture_giornaliere(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    freezer.move_to(ADESSO)
    portale.profilo_info["letture_giornaliere"] = True
    luce = dict(
        CONTRATTO,
        contratto="3000000001",
        servizio="ELECTRIC",
        pod="IT001E00000001",
        contatore="EL1",
        unita="kWh",
        tipo_contatore="MULTI",
        potenza="3 kW",
        teleletto=True,
    )
    tlr = dict(
        CONTRATTO,
        contratto="4000000001",
        servizio="HEATING",
        pod="TLR0001",
        contatore="MT1",
        unita="MWh",
    )
    rifiuti = dict(
        CONTRATTO,
        contratto="5000000001",
        servizio="ENVIRONMENT",
        pod="TARI0001",
        contatore=None,
    )
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_CONTRATTI: [luce, tlr, rifiuti]}
    )

    archivio_luce = [
        {
            "date": 1788134400000,
            "type": "REAL",
            "meterId": "EL1",
            "measurements": [
                {
                    "type": "ACTIVE",
                    "bands": [
                        {"type": "F1", "value": 140.0},
                        {"type": "F2", "value": 250.0},
                        {"type": "F3", "value": 390.0},
                    ],
                }
            ],
        },
        {
            "date": 1785456000000,
            "type": "REAL",
            "meterId": "EL1",
            "measurements": [
                {
                    "type": "ACTIVE",
                    "bands": [
                        {"type": "F1", "value": 100.0},
                        {"type": "F2", "value": 200.0},
                        {"type": "F3", "value": 300.0},
                    ],
                }
            ],
        },
    ]
    archivio_tlr = [
        {"date": 1788134400000, "type": "REAL", "meterId": "MT1", "measurements": [{"value": 12.5}]},
        {"date": 1785456000000, "type": "REAL", "meterId": "MT1", "measurements": [{"value": 10.0}]},
    ]

    async def _letture_per_servizio(profilo, servizio, contratto):
        return archivio_luce if servizio == "ELECTRIC" else archivio_tlr

    portale.async_letture = _letture_per_servizio

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # Electric F1/F2/F3 sensors & kWh statistics
    l_luce = _stato(hass, "lettura", "3000000001")
    assert l_luce.state == "780.0"
    assert l_luce.attributes["unit_of_measurement"] == "kWh"
    assert l_luce.attributes["fasce"] == {"F1": 140.0, "F2": 250.0, "F3": 390.0}
    c_luce = _stato(hass, "consumo_periodo", "3000000001")
    assert c_luce.attributes["fasce"] == {"F1": 40.0, "F2": 50.0, "F3": 90.0}
    assert len(c_luce.attributes["consumi_giornalieri"]) == 1
    # Smart meter (teleletto=True) disables autolettura sensor by default
    ent_reg = er.async_get(hass)
    auto_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "3000000001_autolettura")
    assert ent_reg.async_get(auto_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Heating MWh statistics
    metadati = await get_instance(hass).async_add_executor_job(
        lambda: get_metadata(
            hass,
            statistic_ids={
                "acegasapsamga:it001e00000001_luce",
                "acegasapsamga:tlr0001_teleriscaldamento",
            },
        )
    )
    assert metadati["acegasapsamga:it001e00000001_luce"][1]["unit_of_measurement"] == "kWh"
    assert metadati["acegasapsamga:tlr0001_teleriscaldamento"][1]["unit_of_measurement"] == "MWh"

    # Multi-band electric self-reading submission
    portale.ultima_lettura_struttura = {
        "measurements": [
            {
                "id": "ACTIVE",
                "type": "ACTIVE",
                "bands": [
                    {"id": "001", "type": "F1"},
                    {"id": "002", "type": "F2"},
                    {"id": "003", "type": "F3"},
                ],
            }
        ]
    }
    await hass.services.async_call(
        DOMAIN,
        "invia_autolettura",
        {"contratto": "3000000001", "f1": 150, "f2": 260, "f3": 400},
        blocking=True,
    )
    bande = portale.autoletture_inviate[-1]["measurements"][0]["bands"]
    assert [(b["type"], b["value"]) for b in bande] == [("F1", 150.0), ("F2", 260.0), ("F3", 400.0)]

    # Environment / TARI waste sensors (and no meter lettura sensor)
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "5000000001_lettura") is None
    svu = _stato(hass, "svuotamenti_rifiuti", "5000000001")
    assert svu.state == "2"
    assert svu.attributes["per_tipo"]["RSU"]["svuotamenti"] == 2
    assert _stato(hass, "volume_rifiuti", "5000000001").state == "240.0"
    assert _stato(hass, "dotazioni_rifiuti", "5000000001").state == "1"


async def test_bollette_pagate_e_errori(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    freezer.move_to(ADESSO)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    portale.bollette = [dict(portale.bollette[0], paymentStatus="PAID", residual=0.0), *portale.bollette[1:]]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert _stato(hass, "stato_bolletta").state == "paid"
    assert _stato(hass, "da_pagare").state == "0.0"
    assert _stato(hass, "scadenza_bolletta").state == "unknown"

    portale.errore_bollette = ApiError("down", status=503)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert entry.runtime_data.last_update_success
    assert _stato(hass, "stato_bolletta").state == "paid"
    assert _stato(hass, "bolletta").state == "48.2"
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

    nuova = dict(portale.archivio[1], date=1794268800000, type="REAL")  # 2026-11-10
    nuova["measurements"] = [{"value": 31.0, "correttore": False}]
    portale.archivio = [nuova, *portale.archivio]
    with patch(
        "custom_components.acegasapsamga.statistics.async_add_external_statistics",
        wraps=__import__(
            "homeassistant.components.recorder.statistics", fromlist=["async_add_external_statistics"]
        ).async_add_external_statistics,
    ) as aggiungi:
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
    righe_scritte = aggiungi.call_args.args[2]
    assert len(righe_scritte) == 49 * 24 + 1
    assert (await _ultima_statistica(hass))["sum"] == pytest.approx(31.0)
    assert _stato(hass, "lettura").state == "31.0"

    corretta = dict(portale.archivio[2], measurements=[{"value": 29.0, "correttore": False}])
    portale.archivio = [portale.archivio[0], portale.archivio[1], corretta, *portale.archivio[3:]]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    assert (await _ultima_statistica(hass))["sum"] == pytest.approx(31.0)


async def test_reauth_con_cache_ferma_il_polling(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    freezer.move_to(ADESSO)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)

    portale.errore_login = CredenzialiNonValide("Credenziali non valide.")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert _stato(hass, "lettura").state == "28.0"
    assert entry.runtime_data._unsub_refresh is None
    flussi = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flussi] == ["reauth"]


async def test_403_su_endpoint_opzionale_non_blocca_le_letture(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    from custom_components.acegasapsamga.api import TokenScaduto

    freezer.move_to(ADESSO)
    portale.errore_bollette = TokenScaduto("forbidden", status=403)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.last_update_success
    assert _stato(hass, "lettura").state == "28.0"


async def test_autolettura_aperta_dinamica_e_aggiornamento_matricola(
    recorder_mock, hass, entry: MockConfigEntry, portale, freezer
):
    freezer.move_to(ADESSO)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _stato(hass, "autolettura").attributes["aperta"] is False

    freezer.move_to("2027-03-02 10:00:00+00:00")
    entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()
    assert _stato(hass, "autolettura").attributes["aperta"] is True
    assert _stato(hass, "autolettura").attributes["giorni_mancanti"] == 0

    nuovo_contatore = dict(portale.archivio[1], date=1794268800000, meterId="MATRICOLA_NUOVA")
    portale.archivio = [nuovo_contatore, *portale.archivio]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    dispositivo = next(
        d
        for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        if (DOMAIN, "1000000001") in d.identifiers
    )
    assert dispositivo.serial_number == "MATRICOLA_NUOVA"


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
    flussi = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
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
