"""Waste / TARI (ENVIRONMENT / TCP): equipment, disposals and discounts."""
from __future__ import annotations

from datetime import date

from custom_components.acegasapsamga import rifiuti as rf


def test_estrai_dotazioni_svuotamenti_e_vantaggi():
    dotazioni = rf.estrai_dotazioni(
        [
            {
                "equipmentCode": "EQ-001",
                "type": "BIDONE",
                "status": "ACTIVE",
                "description": "Bidone RSU 120L",
                "volume": 120,
                "assignmentDate": 1764201600000,
                "materialCode": "MAT1",
            },
            {
                "equipmentCode": "EQ-002",
                "type": "TESSERA",
                "status": "DEACTIVE",
                "description": "Tessera vecchia",
                "volume": 0,
            },
        ]
    )
    assert len(dotazioni) == 2
    assert dotazioni[0].attiva is True
    assert dotazioni[0].data_assegnazione == date(2025, 11, 27)
    assert dotazioni[1].attiva is False

    svuotamenti, vol_tot = rf.estrai_svuotamenti(
        {
            "totalVolume": 360,
            "wasteDisposals": [
                {
                    "equipmentCode": "EQ-001",
                    "equipmentType": "BIDONE",
                    "wasteType": "RSU",
                    "volume": 120,
                    "disposalDate": 1773356400000,  # 2026-03-13
                },
                {
                    "equipmentCode": "EQ-001",
                    "equipmentType": "BIDONE",
                    "wasteType": "RSU",
                    "volume": 120,
                    "disposalDate": 1775512800000,  # 2026-04-07
                },
                {
                    "equipmentCode": "EQ-003",
                    "equipmentType": "BIDONE",
                    "wasteType": "CARTA",
                    "volume": 120,
                    "disposalDate": 1775600000000,  # 2026-04-08
                },
            ],
        }
    )
    assert vol_tot == 360.0
    assert len(svuotamenti) == 3

    vantaggi = rf.estrai_vantaggi(
        [{"siebelValue": "V1", "friendlyName": "Compostaggio domestico"}]
    )
    assert vantaggi == [{"codice": "V1", "descrizione": "Compostaggio domestico"}]

    dati = rf.DatiRifiuti(
        dotazioni=dotazioni,
        svuotamenti_anno_corrente=svuotamenti,
        volume_anno_corrente=vol_tot,
        volume_anno_precedente=480.0,
        vantaggi=vantaggi,
    )
    assert len(dati.dotazioni_attive) == 1
    assert dati.volume_totale_corrente == 360.0
    assert dati.volume_totale_precedente == 480.0
    per_tipo = dati.per_tipo()
    assert per_tipo["RSU"] == {"svuotamenti": 2, "volume": 240.0}
    assert per_tipo["CARTA"] == {"svuotamenti": 1, "volume": 120.0}

    mesi = dati.per_mese()
    assert len(mesi) == 12
    assert mesi[2]["svuotamenti"] == 1  # March
    assert mesi[3]["svuotamenti"] == 2  # April
    assert mesi[3]["per_tipo"] == {"RSU": 1, "CARTA": 1}

    ricaricato = rf.DatiRifiuti.da_dict(dati.come_dict())
    assert ricaricato is not None
    assert ricaricato.come_dict() == dati.come_dict()


def test_anno_precedente_fino_allo_stesso_giorno():
    prima = [
        rf.Svuotamento(giorno=date(2025, 3, 1), tipo_rifiuto="RSU", volume=120),
        rf.Svuotamento(giorno=date(2025, 11, 20), tipo_rifiuto="CARTA", volume=120),
        rf.Svuotamento(giorno=date(2025, 11, 21), tipo_rifiuto="RSU", volume=120),
        rf.Svuotamento(giorno=date(2025, 12, 15), tipo_rifiuto="RSU", volume=None),
    ]
    dati = rf.DatiRifiuti(svuotamenti_anno_precedente=prima)
    # On 20 Nov 2026 the comparison stops at 20 Nov 2025, that day included.
    assert dati.anno_precedente_ad_oggi(date(2026, 11, 20)) == (2, 240.0)
    assert rf.DatiRifiuti().anno_precedente_ad_oggi(date(2026, 11, 20)) is None
    assert rf.un_anno_prima(date(2028, 2, 29)) == date(2027, 2, 28)
