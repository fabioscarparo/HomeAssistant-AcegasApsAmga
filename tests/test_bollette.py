"""Bills: parsing of the portal's list, extra fields, payment dates and due dates."""
from __future__ import annotations

from datetime import date

from custom_components.acegasapsamga import bollette as bl

from .conftest import carica


def _bollette() -> list[bl.Bolletta]:
    return bl.estrai_bollette(carica("bollette.json")["list"])


def test_estrai_bollette_e_campi_estesi():
    bollette = _bollette()
    assert [b.numero for b in bollette] == ["0000000000000103", "0000000000000102", "0000000000000101"]
    ultima = bollette[0]
    assert ultima.emissione == date(2026, 11, 13)
    assert ultima.scadenza == date(2026, 12, 9)
    assert (ultima.importo, ultima.residuo) == (48.2, 48.2)
    assert ultima.stato == "unpaid"
    assert ultima.stato_dettaglio == "Pagamento in ricezione"
    assert ultima.pdf_disponibile is True
    assert ultima.pagopa is True
    assert ultima.domiciliata
    assert ultima.contratti == ("1000000001",)
    assert ultima.importi_servizi_dict == {"WATER": 48.2}
    # Bill 101 has two WATER entries in companyServices (44.1 + 42.3 = 86.4)
    assert bollette[2].importo_servizio("WATER") == 86.4


def test_bolletta_multiservizio_e_bolletta_web():
    grezza = dict(
        carica("bollette.json")["list"][0],
        id="MULTI1",
        amount=130.5,
        deliveryTypes=["EMAIL", "XML"],
        companyServices=[
            {"type": "WATER", "amount": 40.0, "reverserBillId": "ST1"},
            {"type": "GAS", "amount": 90.5},
        ],
    )
    [b] = bl.estrai_bollette([grezza])
    assert b.bolletta_web is True
    assert b.importo_servizio("WATER") == 40.0
    assert b.importo_servizio("GAS") == 90.5
    assert b.importo_servizio("ELECTRIC") == 130.5
    assert b.stornata_da == "ST1"


def test_applica_pagamenti_e_rimborsi():
    bollette = _bollette()
    pagamenti = [
        {
            "id": "INV1",
            "amount": 31.75,
            "paymentStatus": "PAYMENT",
            "paymentDate": 1786053600000,  # 2026-08-07
            "billIds": ["0000000000000102"],
        },
        {
            "id": "REF1",
            "amount": 12.5,
            "paymentStatus": "REFUND",
            "paymentDate": 1786140000000,  # 2026-08-08
            "paymentType": "Bonifico",
        },
    ]
    arricchite = bl.applica_pagamenti(bollette, pagamenti)
    mappa = {b.numero: b for b in arricchite}
    assert mappa["0000000000000102"].data_pagamento == date(2026, 8, 7)
    assert mappa["0000000000000103"].data_pagamento is None

    rimborsi = bl.estrai_rimborsi(pagamenti)
    assert rimborsi == [{"data": "2026-08-08", "importo": 12.5, "tipo": "Bonifico"}]


def test_da_pagare_e_scadenza():
    bollette = _bollette()
    assert bl.totale_da_pagare(bollette) == 48.2
    assert bl.prossima_scadenza(bollette) == date(2026, 12, 9)

    pagate = bollette[1:]
    assert bl.totale_da_pagare(pagate) == 0
    assert bl.prossima_scadenza(pagate) is None


def test_in_parte_pagata_conta_il_residuo():
    grezza = dict(carica("bollette.json")["list"][0], paymentStatus="PAID_PARTIAL", residual=10.5)
    [bolletta] = bl.estrai_bollette([grezza])
    assert bolletta.stato == "paid_partial"
    assert bl.totale_da_pagare([bolletta]) == 10.5


def test_stato_da_macro_stato_o_sconosciuto():
    grezza = dict(carica("bollette.json")["list"][0], paymentStatus=None)
    assert bl.estrai_bollette([grezza])[0].stato == "unpaid"
    grezza = dict(grezza, paymentStatus="NUOVO_STATO")
    assert bl.estrai_bollette([grezza])[0].stato == "other"
    assert "other" in bl.OPZIONI_STATO


def test_bollette_non_valide_ignorate():
    valida = carica("bollette.json")["list"][0]
    grezze = [dict(valida, id=None), dict(valida, emissionDate=None), dict(valida, amount="n/d"), valida]
    assert len(bl.estrai_bollette(grezze)) == 1


def test_bollette_del_contratto():
    [ultima, *_] = _bollette()
    altro = bl.Bolletta.da_dict({**ultima.come_dict(), "numero": "2", "contratti": ["9999999999"]})
    senza = bl.Bolletta.da_dict({**ultima.come_dict(), "numero": "3", "contratti": []})
    assert bl.del_contratto([ultima, altro, senza], "1000000001") == [ultima, senza]


def test_salvataggio_e_retrocompatibilita_store():
    for bolletta in _bollette():
        assert bl.Bolletta.da_dict(bolletta.come_dict()) == bolletta
    # Legacy v0.3.0 / v0.4.0-beta.1 dict without new optional fields loads cleanly.
    vecchio = {
        "numero": "B1",
        "emissione": "2026-01-10",
        "scadenza": "2026-02-10",
        "importo": 20.0,
        "residuo": 0.0,
        "stato": "paid",
        "domiciliata": True,
        "contratti": ["C1"],
    }
    caricata = bl.Bolletta.da_dict(vecchio)
    assert caricata.numero == "B1"
    assert caricata.data_pagamento is None
    assert caricata.importi_servizi == ()


def test_stati_aggiuntivi_duplicati_e_nan():
    base = carica("bollette.json")["list"][0]
    grezze = [
        dict(base, id="B1", paymentStatus="PARTIALLY_REVERSED"),
        dict(base, id="B2", paymentStatus="UNDERTHRESHOLD"),
        dict(base, id="B3", paymentStatus="UNPAID", underthreshold=True),
        dict(base, id="B4", paymentStatus="UNPAID", installmentParent=True),
        dict(base, id="B5", paymentStatus="UNPAID", amount=20.0, residual=20.0),
        dict(base, id="B5", paymentStatus="UNPAID", amount=20.0, residual=20.0),
        dict(base, id="B6", amount=float("nan")),
        dict(base, id="B7", amount=True),
    ]
    bollette = {b.numero: b for b in bl.estrai_bollette(grezze)}
    assert set(bollette) == {"B1", "B2", "B3", "B4", "B5"}
    assert bollette["B1"].stato == "reversed"
    assert bollette["B2"].stato == "not_to_pay"
    assert bollette["B3"].stato == "not_to_pay"
    assert bollette["B4"].stato == "installment"
    assert bl.totale_da_pagare(list(bollette.values())) == 20.0
