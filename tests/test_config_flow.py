"""Config flow: login, multi-service contract choice, errors, reauth and options."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType

from custom_components.acegasapsamga import config_flow as cf
from custom_components.acegasapsamga.auth import CredenzialiNonValide, ErroreRete, PassaggioInatteso
from custom_components.acegasapsamga.const import CONF_CONTRATTI, DOMAIN

from .conftest import CONTRATTO

SECONDO = dict(CONTRATTO, contratto="1000000002", pod="0500000000000002", stato="DEACTIVE")
GAS = dict(CONTRATTO, contratto="2000000001", servizio="GAS", pod="00880000000001")
LUCE = dict(CONTRATTO, contratto="3000000001", servizio="ELECTRIC", pod="IT001E00000001")
AMBIENTE = dict(CONTRATTO, contratto="4000000001", servizio="ENVIRONMENT", pod="TARI0001")
ALTRO = dict(CONTRATTO, contratto="5000000001", servizio="OTHER", pod="OTH001")
CREDENZIALI = {CONF_EMAIL: " utente@example.com ", CONF_PASSWORD: "segreta"}


@pytest.fixture(autouse=True)
def _senza_setup():
    with patch("custom_components.acegasapsamga.async_setup_entry", return_value=True):
        yield


def _accedi(*contratti, id_utente="utente-1", errore=None, chiamate=None):
    async def finto(hass, email, password, **kwargs):
        if chiamate is not None:
            chiamate.append({"email": email, "password": password, **kwargs})
        if errore:
            raise errore
        return cf.Accesso(id_utente, [dict(c) for c in contratti])

    return patch.object(cf, "async_accedi", finto)


async def _inizia(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


async def test_un_contratto_crea_subito_la_voce(hass):
    risultato = await _inizia(hass)
    assert risultato["type"] is FlowResultType.FORM
    with _accedi(CONTRATTO, ALTRO):
        risultato = await hass.config_entries.flow.async_configure(risultato["flow_id"], CREDENZIALI)

    assert risultato["type"] is FlowResultType.CREATE_ENTRY
    assert risultato["title"] == "utente@example.com"
    assert risultato["data"][CONF_CONTRATTI] == [CONTRATTO]
    assert risultato["result"].unique_id == "utente-1"


async def test_piu_contratti_multiservizio_si_sceglie(hass):
    risultato = await _inizia(hass)
    with _accedi(CONTRATTO, GAS, LUCE, AMBIENTE, SECONDO):
        risultato = await hass.config_entries.flow.async_configure(risultato["flow_id"], CREDENZIALI)
    assert risultato["step_id"] == "contratti"

    risultato = await hass.config_entries.flow.async_configure(
        risultato["flow_id"], {CONF_CONTRATTI: []}
    )
    assert risultato["errors"] == {"base": "nessuna_scelta"}

    risultato = await hass.config_entries.flow.async_configure(
        risultato["flow_id"], {CONF_CONTRATTI: ["2000000001", "3000000001", "4000000001"]}
    )
    assert risultato["type"] is FlowResultType.CREATE_ENTRY
    assert [c["servizio"] for c in risultato["data"][CONF_CONTRATTI]] == [
        "GAS",
        "ELECTRIC",
        "ENVIRONMENT",
    ]


@pytest.mark.parametrize(
    ("errore", "chiave"),
    [
        (CredenzialiNonValide("Credenziali non valide."), "credenziali_non_valide"),
        (PassaggioInatteso("SelfAsserted"), "passaggio_inatteso"),
        (ErroreRete("dns"), "impossibile_connettersi"),
    ],
)
async def test_errori_di_accesso(hass, errore, chiave):
    risultato = await _inizia(hass)
    with _accedi(errore=errore):
        risultato = await hass.config_entries.flow.async_configure(risultato["flow_id"], CREDENZIALI)
    assert risultato["type"] is FlowResultType.FORM
    assert risultato["errors"] == {"base": chiave}


async def test_solo_servizio_non_supportato(hass):
    risultato = await _inizia(hass)
    with _accedi(ALTRO):
        risultato = await hass.config_entries.flow.async_configure(risultato["flow_id"], CREDENZIALI)
    assert risultato["type"] is FlowResultType.ABORT
    assert risultato["reason"] == "nessun_contratto"
    assert risultato["description_placeholders"] == {"servizi": "OTHER"}


async def test_account_gia_configurato(hass, entry):
    risultato = await _inizia(hass)
    with _accedi(CONTRATTO):
        risultato = await hass.config_entries.flow.async_configure(risultato["flow_id"], CREDENZIALI)
    assert risultato["reason"] == "already_configured"


async def test_riautenticazione(hass, entry):
    risultato = await entry.start_reauth_flow(hass)
    assert risultato["step_id"] == "reauth_confirm"

    chiamate = []
    with _accedi(CONTRATTO, id_utente="altro", chiamate=chiamate):
        altro = await hass.config_entries.flow.async_configure(
            risultato["flow_id"], {CONF_PASSWORD: "nuova"}
        )
    assert altro["reason"] == "account_diverso"
    assert chiamate[-1]["solo_login"] is True

    risultato = await entry.start_reauth_flow(hass)
    with _accedi(CONTRATTO):
        risultato = await hass.config_entries.flow.async_configure(
            risultato["flow_id"], {CONF_EMAIL: "nuova@example.com", CONF_PASSWORD: "nuova"}
        )
    assert risultato["reason"] == "reauth_successful"
    assert entry.data[CONF_EMAIL] == "nuova@example.com"
    assert entry.data[CONF_PASSWORD] == "nuova"
    assert entry.title == "nuova@example.com"


async def test_opzioni_cambiano_i_contratti(hass, entry):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    with _accedi(CONTRATTO, SECONDO):
        risultato = await hass.config_entries.options.async_init(entry.entry_id)
        assert risultato["step_id"] == "init"
        risultato = await hass.config_entries.options.async_configure(
            risultato["flow_id"], {CONF_CONTRATTI: ["1000000001", "1000000002"]}
        )
    assert risultato["type"] is FlowResultType.CREATE_ENTRY
    assert [c["contratto"] for c in entry.data[CONF_CONTRATTI]] == ["1000000001", "1000000002"]

    # Removing a contract also cleans up its device and entities.
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    dispositivo = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "1000000002")}
    )
    ent_reg.async_get_or_create(
        "sensor", DOMAIN, "1000000002_lettura", config_entry=entry, device_id=dispositivo.id
    )
    with _accedi(CONTRATTO, SECONDO):
        risultato = await hass.config_entries.options.async_init(entry.entry_id)
        risultato = await hass.config_entries.options.async_configure(
            risultato["flow_id"], {CONF_CONTRATTI: ["1000000001"]}
        )
    assert risultato["type"] is FlowResultType.CREATE_ENTRY
    assert dev_reg.async_get(dispositivo.id) is None
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "1000000002_lettura") is None


async def test_opzioni_senza_portale(hass, entry):
    with _accedi(errore=ErroreRete("dns")):
        risultato = await hass.config_entries.options.async_init(entry.entry_id)
    assert risultato["type"] is FlowResultType.ABORT
    assert risultato["reason"] == "impossibile_connettersi"
