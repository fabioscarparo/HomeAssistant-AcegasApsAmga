"""API client with recorded answers: headers, pagination, errors, bills, waste and account endpoints."""
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
    assert ("domiciliation", "true") in sessione.richieste[1]["params"]
    assert ("status", "DEACTIVE") in sessione.richieste[1]["params"]


def test_contratto_da_api_esclude_pii_da_contract_bill():
    grezzo = {
        **carica("contratti.json")["list"][0],
        "contractBill": {
            "domiciled": True,
            "domiciliationType": "RID",
            "domiciliationData": "IT60X0542811101000000123456",
            "email": "segreta@example.com",
            "deliveryTypes": ["EMAIL", "XML"],
        },
    }
    risultato = api.contratto_da_api("P1", grezzo)
    assert risultato["domiciliato"] is True
    assert risultato["tipo_domiciliazione"] == "RID"
    assert risultato["bolletta_web"] is True
    assert risultato["modalita_recapito"] == ["EMAIL", "XML"]
    testo = str(risultato)
    assert "IT60X" not in testo
    assert "segreta@example.com" not in testo


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


async def test_bollette_e_profilo_capacita():
    sessione = SessioneFinta()
    sessione.aggiungi(
        "GET", f"{API_BASE_URL}/profile/P/bill/list", RispostaFinta(200, carica("bollette.json"))
    )
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/profile/P",
        RispostaFinta(
            200,
            {
                "billGroupType": "PLICO",
                "enabledDailyReads": True,
                "waterManager": True,
                "environmentManager": False,
                "energyWallet": False,
                "zcode": "Z001",
                "contractNumerosity": 2,
                "fiscalCode": "XXXXXX00X00X000X",
            },
        ),
    )
    client = api.ApiClient(sessione, "T")

    info = await client.async_profilo("P")
    assert info["raggruppamento"] == "PLICO"
    assert info["letture_giornaliere"] is True
    assert "fiscalCode" not in info
    bollette = await client.async_bollette("P", "PLICO")
    assert len(bollette) == 3
    parametri = dict(sessione.richieste[1]["params"])
    assert parametri["groupBy"] == "PLICO"


async def test_utente_pdf_e_autolettura_errori_692_695():
    sessione = SessioneFinta()
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/user",
        RispostaFinta(
            200,
            {
                "pwdChangedTime": 1794524400000,
                "pwdExpireTime": 1810076400000,
                "renewPassword": False,
                "newConditionsAcceptance": True,
                "firstName": "Mario",
            },
        ),
    )
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/profile/P/bill/export/pdf/B1",
        RispostaFinta(200, b"%PDF-1.4 sample"),
    )
    sessione.aggiungi(
        "POST",
        f"{API_BASE_URL}/v2/profile/P/read",
        [
            RispostaFinta(692, "less than previous"),
            RispostaFinta(695, "out of timeframe"),
            RispostaFinta(200, ""),
        ],
    )
    client = api.ApiClient(sessione, "T")

    utente = await client.async_utente()
    assert utente["cambio_password"] == "2026-11-13"
    assert utente["scadenza_password"] == "2027-05-12"
    assert "firstName" not in utente

    pdf = await client.async_bolletta_pdf("P", "B1")
    assert pdf == b"%PDF-1.4 sample"
    assert sessione.richieste[1]["headers"]["Accept"] == "*/*"

    with pytest.raises(api.AutoletturaInferiore):
        await client.async_invia_autolettura("P", {"contractId": "C1"})
    with pytest.raises(api.AutoletturaFuoriFinestra):
        await client.async_invia_autolettura("P", {"contractId": "C1"})
    assert await client.async_invia_autolettura("P", {"contractId": "C1"}) is None


async def test_notifiche_vas_calendario_e_tcp():
    sessione = SessioneFinta()
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/profile/P/notification/list",
        RispostaFinta(
            200,
            {
                "total": 2,
                "toRead": 1,
                "list": [
                    {
                        "id": "N1",
                        "isRead": False,
                        "type": "ALERT",
                        "title": "Avviso idrico",
                        "subTitle": "Manutenzione",
                        "description": "Dettaglio",
                        "date": 1794524400000,
                    }
                ],
            },
        ),
    )
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/profile/P/notification/configuration/list",
        RispostaFinta(
            200,
            {
                "configurations": [
                    {
                        "id": "C1",
                        "name": "Interruzioni idriche",
                        "type": "WATER_SERVICE",
                        "notifyType": "WTR_FLT",
                        "enabled": True,
                        "channels": [{"type": "SMS", "value": "+3900000000"}],
                    }
                ]
            },
        ),
    )
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/profile/P/vas/list",
        RispostaFinta(
            200,
            {
                "list": [
                    {
                        "service": "WATER",
                        "contractId": "1000000001",
                        "deliveryTypeEmail": True,
                        "vasList": [
                            {"id": "AC", "status": "active", "referer": "ORS", "offerCode": "ACDOM"}
                        ],
                    }
                ]
            },
        ),
    )
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/profile/P/TCP/wastedisposal/C1",
        RispostaFinta(
            200,
            {
                "totalVolume": 240,
                "hasNext": False,
                "wasteDisposals": [
                    {"wasteType": "RSU", "volume": 120, "disposalDate": 1794524400000}
                ],
            },
        ),
    )
    client = api.ApiClient(sessione, "T")

    notifiche = await client.async_notifiche("P")
    assert notifiche["non_lette"] == 1
    assert notifiche["lista"][0]["data"] == "2026-11-13"

    conf = await client.async_configurazione_notifiche("P")
    assert conf[0]["categoria"] == "WTR_FLT"
    assert "+39" not in str(conf)

    vas = await client.async_vas("P")
    assert vas[0]["servizi"][0]["id"] == "AC"

    tcp = await client.async_svuotamenti_rifiuti("P", "C1", tipo="RSU", anno="CURRENT")
    assert tcp["totalVolume"] == 240
    assert len(tcp["wasteDisposals"]) == 1


async def test_lista_non_dizionario_solleva_api_error():
    sessione = SessioneFinta()
    sessione.aggiungi("GET", f"{API_BASE_URL}/profile/list", RispostaFinta(200, "testo"))
    with pytest.raises(api.ApiError):
        await api.ApiClient(sessione, "T").async_profili()


async def test_paginazione_si_ferma_su_pagina_vuota():
    sessione = SessioneFinta()
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/v2/profile/P/read/archive/WATER",
        RispostaFinta(200, {"list": [], "hasNext": True}),
    )
    assert await api.ApiClient(sessione, "T").async_letture("P", "WATER", "C") == []
    assert len(sessione.richieste) == 1


async def test_contratti_multi_profilo_e_scarta_senza_id():
    sessione = SessioneFinta()
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/profile/list",
        RispostaFinta(200, {"list": [{"id": "P1"}, {"id": "P2"}]}),
    )
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/profile/P1/contract/list",
        RispostaFinta(200, {"list": [{"id": "C1", "serviceType": "WATER"}, {"serviceType": "WATER"}]}),
    )
    sessione.aggiungi(
        "GET",
        f"{API_BASE_URL}/profile/P2/contract/list",
        RispostaFinta(200, {"list": [{"id": "C2", "serviceType": "ELECTRIC"}]}),
    )
    risultato = await api.ApiClient(sessione, "T").async_contratti_account()
    assert [(p, c["id"]) for p, c in risultato] == [("P1", "C1"), ("P2", "C2")]
