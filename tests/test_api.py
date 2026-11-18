"""API client with recorded answers: headers, pagination, errors."""
from __future__ import annotations

import aiohttp
import pytest

from custom_components.acegasapsamga import api
from custom_components.acegasapsamga.const import API_BASE_URL

from .conftest import CONTRATTO, RispostaFinta, SessioneFinta, carica


async def test_intestazioni_e_contratti():
    sessione = SessioneFinta()
    sessione.aggiungi("GET", f"{API_BASE_URL}/profile/list", RispostaFinta(200, carica("profili.json")))
    sessione.aggiungi(
        "GET", f"{API_BASE_URL}/profile/PROFILO0001/contract/list", RispostaFinta(200, carica("contratti.json"))
    )
    client = api.ApiClient(sessione, "TOKEN")

    contratti = await client.async_contratti_account()

    assert [api.contratto_da_api(p, c) for p, c in contratti] == [CONTRATTO]
    intestazioni = sessione.richieste[0]["headers"]
    assert intestazioni["Authorization"] == "Bearer TOKEN"
    assert intestazioni["X-Bwb-Referer"] == "ACEGAS"
    assert ("status", "DEACTIVE") in sessione.richieste[1]["params"]


async def test_letture_su_piu_pagine():
    archivio = carica("archivio_acqua.json")["list"]
    sessione = SessioneFinta()
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/v2/profile/P/read/archive/WATER",
        [
            RispostaFinta(200, {"list": archivio[:6], "hasNext": True}),
            RispostaFinta(200, {"list": archivio[6:], "hasNext": False}),
        ],
    )
    letture = await api.ApiClient(sessione, "T").async_letture("P", "WATER", "C")
    assert len(letture) == 13
    assert dict(sessione.richieste[1]["params"])["pageNumber"] == "1"
    assert dict(sessione.richieste[0]["params"])["contractId"] == "C"


@pytest.mark.parametrize("stato", [401, 403])
async def test_token_rifiutato(stato):
    sessione = SessioneFinta()
    sessione.aggiungi(
        "GET", API_BASE_URL, RispostaFinta(stato, {"reason": "Access forbidden: role not allowed"})
    )
    with pytest.raises(api.TokenScaduto):
        await api.ApiClient(sessione, "T").async_profili()


async def test_errore_del_server():
    sessione = SessioneFinta()
    sessione.aggiungi("GET", API_BASE_URL, RispostaFinta(500, "errore"))
    with pytest.raises(api.ApiError) as errore:
        await api.ApiClient(sessione, "T").async_profili()
    assert errore.value.status == 500
    assert not isinstance(errore.value, api.TokenScaduto)


async def test_rete():
    sessione = SessioneFinta()
    sessione.aggiungi("GET", API_BASE_URL, aiohttp.ClientConnectionError("dns"))
    with pytest.raises(api.ApiError) as errore:
        await api.ApiClient(sessione, "T").async_profili()
    assert errore.value.rete


async def test_bollette_con_raggruppamento_del_profilo():
    sessione = SessioneFinta()
    sessione.aggiungi(
        "GET", f"{API_BASE_URL}/profile/P/bill/list", RispostaFinta(200, carica("bollette.json"))
    )
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/profile/P",
        RispostaFinta(200, {"billGroupType": "PLICO", "fiscalCode": "XXXXXX00X00X000X"}),
    )
    client = api.ApiClient(sessione, "T")

    assert await client.async_raggruppamento_bollette("P") == "PLICO"
    bollette = await client.async_bollette("P", "PLICO")

    assert len(bollette) == 3
    parametri = dict(sessione.richieste[1]["params"])
    assert parametri["groupBy"] == "PLICO"
    assert parametri["pageNumber"] == "0"
