"""The meter card served by the integration."""
from __future__ import annotations

import re
import subprocess
from shutil import which
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.acegasapsamga import lovelace_card

CONTENUTO = lovelace_card.PERCORSO_FILE.read_text(encoding="utf-8")


def test_la_card_aspetta_il_registro_di_home_assistant():
    # A define before the app starts ends in the wrong registry ("Custom element doesn't exist").
    assert 'whenDefined("home-assistant")' in CONTENUTO
    assert "registro.define(CARD_TYPE" in CONTENUTO
    assert "customElements.define(" not in CONTENUTO


def test_testi_nelle_due_lingue():
    inizio = CONTENUTO.index("const STRINGS = {")
    blocco = CONTENUTO[inizio : CONTENUTO.index("\n};\n", inizio)]
    italiano, inglese = blocco.split("\n  en: {")
    chiavi = lambda testo: set(re.findall(r"^    (\w+):", testo, re.MULTILINE))  # noqa: E731
    assert chiavi(italiano) == chiavi(inglese)
    usate = set(re.findall(r'\bt\("(\w+)"', CONTENUTO)) | set(re.findall(r'traduci\(this\._hass, "(\w+)"', CONTENUTO))
    assert usate <= chiavi(italiano)


def test_la_card_usa_le_chiavi_dei_sensori():
    # The card finds the sensors by translation_key: the names must match sensor.py.
    from custom_components.acegasapsamga import sensor

    chiavi_sensori = {c.chiave for c in sensor._SensoreContratto.__subclasses__()}
    for chiave in ("lettura", "consumo_periodo", "media_giornaliera"):
        assert chiave in chiavi_sensori
        assert f'"{chiave}"' in CONTENUTO
    assert "attributes.statistic_id" in CONTENUTO
    assert "attributes.periodi" in CONTENUTO


@pytest.mark.skipif(which("node") is None, reason="node non installato")
def test_sintassi_javascript():
    esito = subprocess.run(["node", "--check", str(lovelace_card.PERCORSO_FILE)], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr


async def test_senza_http_non_registra_nulla(hass):
    hass.http = None
    await lovelace_card.async_registra_card(hass)
    assert not hass.data.get(lovelace_card._CHIAVE_REGISTRATA)


async def test_registra_la_card_una_sola_volta(hass):
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")

    with patch("homeassistant.components.frontend.add_extra_js_url") as aggiungi:
        await lovelace_card.async_registra_card(hass)
        await lovelace_card.async_registra_card(hass)

    hass.http.async_register_static_paths.assert_awaited_once()
    (config,) = hass.http.async_register_static_paths.await_args.args[0]
    assert config.url_path == lovelace_card.URL_STATICO
    aggiungi.assert_called_once_with(hass, f"{lovelace_card.URL_STATICO}?v={lovelace_card.impronta_file()}")


def test_l_impronta_cambia_col_file(tmp_path):
    # The file is cached for a month: ?v= must change with every edit.
    card = tmp_path / "card.js"
    card.write_text("console.log(1);", encoding="utf-8")
    prima = lovelace_card.impronta_file(card)
    card.write_text("console.log(2);", encoding="utf-8")
    assert lovelace_card.impronta_file(card) != prima
