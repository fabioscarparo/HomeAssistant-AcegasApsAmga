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

    def sottoclassi(classe):
        for figlia in classe.__subclasses__():
            yield figlia
            yield from sottoclassi(figlia)

    chiavi_sensori = {c.chiave for c in sottoclassi(sensor._SensoreContratto) if hasattr(c, "chiave")}
    for chiave in ("lettura", "consumo_periodo", "media_giornaliera", "bolletta", "da_pagare", "scadenza_bolletta"):
        assert chiave in chiavi_sensori
        assert f'"{chiave}"' in CONTENUTO
    for attributo in ("periodi", "bollette", "domiciliata"):
        assert f"attributes.{attributo}" in CONTENUTO


def test_la_card_conosce_gli_stati_da_pagare():
    # The card adds up the open bills with the same statuses as the integration.
    from custom_components.acegasapsamga.bollette import STATI_DA_PAGARE

    elenco = re.search(r"const STATI_DA_PAGARE = \[([^\]]*)\]", CONTENUTO).group(1)
    assert set(re.findall(r'"(\w+)"', elenco)) == STATI_DA_PAGARE


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


async def test_file_mancante_non_blocca_setup(hass, tmp_path):
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")
    with patch.object(lovelace_card, "PERCORSO_FILE", tmp_path / "inesistente.js"):
        await lovelace_card.async_registra_card(hass)
    assert not hass.data.get(lovelace_card._CHIAVE_REGISTRATA)
    hass.http.async_register_static_paths.assert_not_awaited()


@pytest.mark.skipif(which("node") is None, reason="node non installato")
def test_logica_card_runtime():
    script = f"""
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync({str(lovelace_card.PERCORSO_FILE)!r}, "utf8");
const defined = new Map();
const sandbox = {{
  console, Intl, Date, Math, Number, String, Array, Object, Map, Set, Promise, JSON,
  setTimeout, clearTimeout,
  HTMLElement: class {{ attachShadow() {{ return {{ innerHTML: "", querySelector: () => null, querySelectorAll: () => [] }}; }} }},
  CustomEvent: class {{ constructor(t, d) {{ this.type = t; this.detail = d; }} }},
  ResizeObserver: class {{ observe() {{}} disconnect() {{}} }},
  document: {{ addEventListener() {{}}, removeEventListener() {{}}, createElement: () => ({{}}) }},
  navigator: {{ language: "it" }},
  history: {{ pushState() {{}} }},
  getComputedStyle: () => ({{ getPropertyValue: () => "#00bcd4" }}),
  window: {{
    customElements: {{ get: (k) => k === "home-assistant" ? true : defined.get(k), define: (k, v) => defined.set(k, v), whenDefined: () => Promise.resolve() }},
    dispatchEvent() {{}},
  }},
}};
sandbox.globalThis = sandbox;
vm.runInNewContext(code + "\\n;globalThis.__exp = {{ traduci, AcegasContatoreCard }};", sandbox);
const {{ traduci, AcegasContatoreCard }} = sandbox.__exp;

// 1. traduci safely handles '$' replacement sequences
const t = traduci({{ locale: {{ language: "it" }} }}, "period_line", {{ from: "1 gen", to: "2 gen", value: "$& 5 m³", days: "2" }});
if (!t.includes("$& 5 m³")) throw new Error("traduci mangled $&: " + t);

// 2. _daPagare reads domiciliata per unpaid bill, not from the newest bill
const card = new AcegasContatoreCard();
card._config = {{}};
card._contatori = [{{ deviceId: "d1", entita: {{ lettura: "s.l", bolletta: "s.b", da_pagare: "s.dp", scadenza_bolletta: "s.sc" }} }}];
card._hass = {{
  config: {{ time_zone: "Europe/Rome" }},
  locale: {{ language: "it" }},
  states: {{
    "s.l": {{ state: "10", attributes: {{ device_class: "water" }} }},
    "s.b": {{
      state: "30",
      attributes: {{
        domiciliata: true,
        bollette: [
          {{ numero: "2", emissione: "2026-10-01", scadenza: "2026-10-20", importo: 30, residuo: 0, stato: "paid", domiciliata: true }},
          {{ numero: "1", emissione: "2026-06-01", scadenza: "2026-12-20", importo: 40, residuo: 40, stato: "unpaid", domiciliata: false }},
        ],
      }},
    }},
    "s.dp": {{ state: "40", attributes: {{}} }},
    "s.sc": {{ state: "2026-12-20", attributes: {{}} }},
  }},
}};
const conto = card._daPagare();
if (conto.domiciliata !== false) throw new Error("domiciliata should be false for unpaid bill");

// 3. Explicit missing device_id returns null instead of falling back to another meter
card._config = {{ device_id: "rimosso" }};
if (card._contatore !== null) throw new Error("missing device_id must not fall back");
"""
    esito = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
