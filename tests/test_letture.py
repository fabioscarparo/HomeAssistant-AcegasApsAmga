"""Readings and hourly series, including multi-band electricity and daily reads."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from custom_components.acegasapsamga import letture as lt

from .conftest import carica

ADESSO = datetime(2026, 11, 17, 12, tzinfo=UTC)


def _letture() -> list[lt.Lettura]:
    return lt.estrai_letture(carica("archivio_acqua.json")["list"])


def _lettura(giorno: str, valore: float, tipo: str = "REAL", contatore: str = "M1") -> lt.Lettura:
    return lt.Lettura(date.fromisoformat(giorno), valore, tipo, "DEALER", contatore)


def test_giorno_da_ms_utc_e_ora_italiana():
    # 2026-09-22 at midnight UTC and at midnight in Rome (22:00 UTC the day before).
    assert lt.giorno_da_ms(1790035200000) == date(2026, 9, 22)
    assert lt.giorno_da_ms(1790028000000) == date(2026, 9, 22)
    assert lt.giorno_da_ms(None) is None


def test_estrai_letture_ordinate():
    letture = _letture()
    assert len(letture) == 13
    assert letture[0] == lt.Lettura(date(2025, 11, 27), 0.0, "REAL", "DEALER", "MATRICOLA0001")
    assert letture[-1].giorno == date(2026, 11, 11)
    assert not letture[-1].reale
    assert [l.giorno for l in letture] == sorted(l.giorno for l in letture)


def test_le_stime_non_sono_ancore():
    ancore = lt.ancore(_letture())
    assert len(ancore) == 10
    assert all(a.reale for a in ancore)
    assert lt.ultima_reale(_letture()).giorno == date(2026, 9, 22)


def test_serie_oraria_reale():
    righe = lt.serie_oraria(_letture(), ADESSO)
    assert righe[0]["start"] == datetime(2025, 11, 27, 23, tzinfo=UTC)
    assert righe[-1]["start"] == datetime(2026, 9, 22, 21, tzinfo=UTC)
    assert righe[-1]["sum"] == 28.0
    assert righe[-1]["state"] == 28.0
    assert all(b["sum"] >= a["sum"] for a, b in zip(righe, righe[1:], strict=False))
    assert all(b["start"] - a["start"] == timedelta(hours=1) for a, b in zip(righe, righe[1:], strict=False))


def test_ogni_lettura_reale_cade_a_fine_giornata():
    righe = {r["start"]: r for r in lt.serie_oraria(_letture(), ADESSO)}
    for ancora in lt.ancore(_letture())[1:]:
        ultima_ora = lt.istante(ancora.giorno) - timedelta(hours=1)
        assert righe[ultima_ora]["state"] == ancora.valore


def test_cambio_ora_legale():
    letture = [_lettura("2026-03-28", 10), _lettura("2026-03-30", 12)]
    righe = lt.serie_oraria(letture, ADESSO)
    assert len(righe) == 47
    assert righe[-1]["sum"] == 2.0


def test_la_serie_si_ferma_all_ora_corrente():
    letture = [_lettura("2026-11-15", 10), _lettura("2026-11-17", 12)]
    righe = lt.serie_oraria(letture, datetime(2026, 11, 17, 10, 30, tzinfo=UTC))
    assert righe[-1]["start"] == datetime(2026, 11, 17, 9, tzinfo=UTC)
    assert righe[-1]["sum"] < 2.0


def test_lettura_in_calo_vale_zero():
    letture = [_lettura("2026-01-01", 10), _lettura("2026-01-02", 8), _lettura("2026-01-03", 9)]
    righe = lt.serie_oraria(letture, ADESSO)
    assert righe[23]["sum"] == 0.0
    assert righe[-1]["sum"] == 1.0


def test_cambio_contatore_senza_consumo_nel_passaggio():
    letture = [
        _lettura("2026-01-01", 100, contatore="VECCHIO"),
        _lettura("2026-01-02", 101, contatore="VECCHIO"),
        _lettura("2026-01-02", 0, contatore="NUOVO"),
        _lettura("2026-01-03", 2, contatore="NUOVO"),
    ]
    righe = lt.serie_oraria(letture, ADESSO)
    assert len(righe) == 48
    assert righe[23]["sum"] == 1.0
    assert righe[-1]["sum"] == 3.0
    assert righe[-1]["state"] == 2.0


def test_unisci_tiene_lo_storico_vecchio_e_applica_le_correzioni():
    salvate = [_lettura("2026-01-01", 1), _lettura("2026-02-01", 2), _lettura("2026-03-01", 3)]
    nuove = [_lettura("2026-02-01", 2.5), _lettura("2026-04-01", 4)]
    unite = lt.unisci(salvate, nuove)
    assert [(l.giorno.isoformat(), l.valore) for l in unite] == [
        ("2026-01-01", 1),
        ("2026-02-01", 2.5),
        ("2026-04-01", 4),
    ]
    assert lt.unisci(salvate, []) == salvate


def test_ultimo_periodo():
    periodo = lt.ultimo_periodo(_letture())
    assert periodo == {
        "dal": date(2026, 8, 26),
        "al": date(2026, 9, 22),
        "giorni": 28,
        "consumo": 6.0,
        "media_giornaliera": 6.0 / 28,
    }


def test_meno_di_due_letture():
    assert lt.serie_oraria([_lettura("2026-01-01", 1)], ADESSO) == []
    assert lt.ultimo_periodo([_lettura("2026-01-01", 1)]) is None


def test_valore_del_correttore_ignorato():
    elemento = {
        "date": 1790035200000,
        "type": "REAL",
        "measurements": [
            {"correttore": True, "value": 999.0},
            {"correttore": False, "value": 12.0},
        ],
    }
    assert lt.estrai_letture([elemento])[0].valore == 12.0


def test_luce_multifascia_f1_f2_f3_e_delta_periodi():
    grezze = [
        {
            "date": 1785456000000,  # 2026-07-31
            "type": "REAL",
            "meterId": "EL1",
            "measurements": [
                {
                    "type": "REACTIVE",
                    "bands": [{"type": "F1", "value": 5.0}, {"type": "F2", "value": 5.0}],
                },
                {
                    "type": "ACTIVE",
                    "value": None,
                    "bands": [
                        {"type": "F1", "value": 100.0},
                        {"type": "F2", "value": 200.0},
                        {"type": "F3", "value": 300.0},
                    ],
                },
            ],
        },
        {
            "date": 1788134400000,  # 2026-08-31
            "type": "REAL",
            "meterId": "EL1",
            "measurements": [
                {
                    "type": "ACTIVE",
                    "value": None,
                    "bands": [
                        {"type": "F1", "value": 140.0},
                        {"type": "F2", "value": 250.0},
                        {"type": "F3", "value": 390.0},
                    ],
                }
            ],
        },
    ]
    letture = lt.estrai_letture(grezze)
    assert len(letture) == 2
    assert letture[0].valore == 600.0
    assert letture[0].fasce_dict == {"F1": 100.0, "F2": 200.0, "F3": 300.0}
    assert lt.Lettura.da_dict(letture[0].come_dict()) == letture[0]

    [periodo] = lt.periodi(letture)
    assert periodo["consumo"] == 180.0
    assert periodo["fasce"] == {"F1": 40.0, "F2": 50.0, "F3": 90.0}


def test_consumi_giornalieri():
    righe = lt.estrai_consumi_giornalieri(
        [
            {"usageFromDate": 1790121600000, "totalUsage": 4.2, "readType": "REAL"},
            {"usageFromDate": 1790035200000, "totalUsage": 3.5, "readType": "REAL"},
            {"usageFromDate": None, "totalUsage": 1.0},
        ]
    )
    assert righe == [
        {"giorno": "2026-09-22", "consumo": 3.5, "tipo": "REAL"},
        {"giorno": "2026-09-23", "consumo": 4.2, "tipo": "REAL"},
    ]


def test_periodi():
    periodi = lt.periodi(_letture())
    assert len(periodi) == 9
    assert periodi[0]["dal"] == date(2025, 11, 28)
    assert periodi[0]["al"] == date(2026, 1, 29)
    assert sum(p["consumo"] for p in periodi) == 28.0
    assert periodi[-1] == lt.ultimo_periodo(_letture())


def test_autoletture_ko_in_charge_e_unknown_non_sono_reali():
    grezze = [
        {"date": 1790035200000, "type": "REAL", "status": "UNKNOWN", "measurements": [{"value": 10.0}]},
        {"date": 1790121600000, "type": "SELFREADING", "status": "OK", "measurements": [{"value": 12.0}]},
        {"date": 1790208000000, "type": "SELFREADING", "status": "KO", "measurements": [{"value": 999.0}]},
        {"date": 1790294400000, "type": "SELFREADING", "status": "IN_CHARGE", "measurements": [{"value": 15.0}]},
        {"date": 1790380800000, "type": "UNKNOWN", "status": "UNKNOWN", "measurements": [{"value": 20.0}]},
    ]
    letture = lt.estrai_letture(grezze)
    ancore = lt.ancore(letture)
    assert [(a.giorno, a.valore, a.tipo) for a in ancore] == [
        (date(2026, 9, 22), 10.0, "REAL"),
        (date(2026, 9, 23), 12.0, "SELFREADING"),
    ]


def test_valori_non_validi_e_booleani_ignorati():
    assert lt.giorno_da_ms(True) is None
    assert lt.giorno_da_ms(False) is None
    elemento = {
        "date": 1790035200000,
        "type": "REAL",
        "measurements": [
            {"correttore": False, "value": "n/d"},
            {"correttore": False, "value": float("nan")},
            {"correttore": False, "value": True},
            {"correttore": False, "value": -5.0},
            {"correttore": False, "value": 14.0},
        ],
    }
    assert lt.estrai_letture([elemento])[0].valore == 14.0


def test_stesso_giorno_stesso_valore_real_batte_selfreading():
    letture = [
        lt.Lettura(date(2026, 9, 22), 28.0, "SELFREADING", "WEB", "M1", "OK"),
        lt.Lettura(date(2026, 9, 22), 28.0, "REAL", "DEALER", "M1", "UNKNOWN"),
    ]
    [unica] = lt.ancore(letture)
    assert unica.tipo == "REAL"


def test_statistic_id_sempre_valido():
    from homeassistant.components.recorder.statistics import valid_statistic_id

    from custom_components.acegasapsamga.statistics import statistic_id

    for servizio in ("WATER", "GAS", "ELECTRIC", "HEATING"):
        for codice in ("-0500001-", "IT  001--E", "  ABC_123  ", "---"):
            sid = statistic_id(servizio, codice)
            assert valid_statistic_id(sid), sid
