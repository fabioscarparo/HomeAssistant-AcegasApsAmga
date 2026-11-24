"""All Lovelace cards served by the integration."""
from __future__ import annotations

import re
import subprocess
from shutil import which
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.acegasapsamga import lovelace_card

TUTTE_LE_CARD = [(nome, percorso) for nome, percorso in lovelace_card.percorsi_card()]


@pytest.mark.parametrize(("url", "percorso"), TUTTE_LE_CARD)
def test_la_card_aspetta_il_registro_di_home_assistant(url, percorso):
    contenuto = percorso.read_text(encoding="utf-8")
    assert 'whenDefined("home-assistant")' in contenuto
    assert "registro.define(CARD_TYPE" in contenuto
    assert "customElements.define(" not in contenuto


@pytest.mark.parametrize(("url", "percorso"), TUTTE_LE_CARD)
def test_testi_nelle_due_lingue(url, percorso):
    contenuto = percorso.read_text(encoding="utf-8")
    inizio = contenuto.index("const STRINGS = {")
    blocco = contenuto[inizio : contenuto.index("\n};\n", inizio)]
    italiano, inglese = blocco.split("\n  en: {")
    chiavi = lambda testo: set(re.findall(r"^    (\w+):", testo, re.MULTILINE))  # noqa: E731
    assert chiavi(italiano) == chiavi(inglese)
    usate = set(re.findall(r'\bt\("(\w+)"', contenuto)) | set(
        re.findall(r'traduci\(this\._hass, "(\w+)"', contenuto)
    )
    assert usate <= chiavi(italiano)


@pytest.mark.parametrize(("url", "percorso"), TUTTE_LE_CARD)
def test_la_card_conosce_gli_stati_da_pagare(url, percorso):
    from custom_components.acegasapsamga.bollette import STATI_DA_PAGARE

    contenuto = percorso.read_text(encoding="utf-8")
    elenco = re.search(r"const STATI_DA_PAGARE = \[([^\]]*)\]", contenuto).group(1)
    assert set(re.findall(r'"(\w+)"', elenco)) == STATI_DA_PAGARE


def test_le_card_usano_le_chiavi_dei_sensori():
    from custom_components.acegasapsamga import sensor

    def sottoclassi(classe):
        for figlia in classe.__subclasses__():
            yield figlia
            yield from sottoclassi(figlia)

    chiavi_sensori = {
        c.chiave
        for base in (sensor._SensoreContratto, sensor._SensoreAccount)
        for c in sottoclassi(base)
        if hasattr(c, "chiave")
    }
    contatore = lovelace_card.PERCORSO_FILE.read_text(encoding="utf-8")
    for chiave in ("lettura", "consumo_periodo", "media_giornaliera", "autolettura", "bolletta", "da_pagare", "scadenza_bolletta"):
        assert chiave in chiavi_sensori
        assert f'"{chiave}"' in contatore

    rifiuti = (lovelace_card.PERCORSO_FILE.parent / "acegasapsamga-rifiuti-card.js").read_text(encoding="utf-8")
    for chiave in ("svuotamenti_rifiuti", "volume_rifiuti", "dotazioni_rifiuti", "bolletta", "da_pagare"):
        assert chiave in chiavi_sensori
        assert f'"{chiave}"' in rifiuti

    bollette = (lovelace_card.PERCORSO_FILE.parent / "acegasapsamga-bollette-card.js").read_text(encoding="utf-8")
    for chiave in ("bolletta", "da_pagare", "scadenza_bolletta", "scadenza_password", "notifiche"):
        assert chiave in chiavi_sensori
        assert f'"{chiave}"' in bollette


@pytest.mark.skipif(which("node") is None, reason="node non installato")
@pytest.mark.parametrize(("url", "percorso"), TUTTE_LE_CARD)
def test_sintassi_javascript(url, percorso):
    esito = subprocess.run(["node", "--check", str(percorso)], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr


async def test_senza_http_non_registra_nulla(hass):
    hass.http = None
    await lovelace_card.async_registra_card(hass)
    assert not hass.data.get(lovelace_card._CHIAVE_REGISTRATA)


async def test_registra_tutte_le_card_una_sola_volta(hass):
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")

    with patch("homeassistant.components.frontend.add_extra_js_url") as aggiungi:
        await lovelace_card.async_registra_card(hass)
        await lovelace_card.async_registra_card(hass)

    hass.http.async_register_static_paths.assert_awaited_once()
    configs = hass.http.async_register_static_paths.await_args.args[0]
    assert len(configs) == len(lovelace_card.CARDS)
    assert [c.url_path for c in configs] == [u for u, _ in lovelace_card.percorsi_card()]
    assert aggiungi.call_count == len(lovelace_card.CARDS)


def test_l_impronta_cambia_col_file(tmp_path):
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
def test_logica_tutte_le_card_runtime():
    cartella = lovelace_card.PERCORSO_FILE.parent
    script = f"""
const fs = require("fs");
const vm = require("vm");

function loadCard(filename, exportNames) {{
  const code = fs.readFileSync({str(cartella)!r} + "/" + filename, "utf8");
  const defined = new Map();
  const sandbox = {{
    console, Intl, Date, Math, Number, String, Array, Object, Map, Set, Promise, JSON,
    setTimeout, clearTimeout,
    HTMLElement: class {{ attachShadow() {{ this.shadowRoot = {{ innerHTML: "", querySelector: () => null, querySelectorAll: () => [] }}; return this.shadowRoot; }} }},
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
  vm.runInNewContext(code + "\\n;globalThis.__exp = {{ " + exportNames.join(", ") + " }};", sandbox);
  return sandbox.__exp;
}}

// 1. Contatore card: traduci, domiciliata per unpaid bill, heating support, missing device_id
const {{ traduci, AcegasContatoreCard }} = loadCard("acegasapsamga-contatore-card.js", ["traduci", "AcegasContatoreCard"]);
const t = traduci({{ locale: {{ language: "it" }} }}, "period_line", {{ from: "1 gen", to: "2 gen", value: "$& 5 m³", days: "2" }});
if (!t.includes("$& 5 m³")) throw new Error("traduci mangled $&: " + t);

const card = new AcegasContatoreCard();
card._config = {{}};
card._contatori = [{{ deviceId: "d1", entita: {{ lettura: "s.l", bolletta: "s.b", da_pagare: "s.dp", scadenza_bolletta: "s.sc" }} }}];
card._hass = {{
  config: {{ time_zone: "Europe/Rome" }},
  locale: {{ language: "it" }},
  states: {{
    "s.l": {{ state: "10", attributes: {{ device_class: "energy", servizio: "HEATING", unit_of_measurement: "MWh" }} }},
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
if (card._tipoServizio !== "heating" || card._unitaConsumo !== "MWh") throw new Error("heating unit failed");
if (card._daPagare().domiciliata !== false) throw new Error("domiciliata should be false");
card._config = {{ device_id: "rimosso" }};
if (card._contatore !== null) throw new Error("missing device_id must not fall back");

// 2. Luce card: finds ELECTRIC meter, reads F1/F2/F3 bands and aggregates year bands + CIELAB shades
const {{ AcegasLuceCard, trovaContatoriLuce, sfumatura }} = loadCard("acegasapsamga-luce-card.js", ["AcegasLuceCard", "trovaContatoriLuce", "sfumatura"]);
const luceHass = {{
  entities: {{
    e1: {{ platform: "acegasapsamga", device_id: "d_el", translation_key: "lettura", entity_id: "sensor.el_l" }},
    e2: {{ platform: "acegasapsamga", device_id: "d_el", translation_key: "consumo_periodo", entity_id: "sensor.el_p" }},
    w1: {{ platform: "acegasapsamga", device_id: "d_w", translation_key: "lettura", entity_id: "sensor.w_l" }},
  }},
  devices: {{ d_el: {{ name: "Luce POD1" }}, d_w: {{ name: "Acqua 1" }} }},
  states: {{
    "sensor.el_l": {{ state: "780", attributes: {{ servizio: "ELECTRIC", device_class: "energy" }} }},
    "sensor.w_l": {{ state: "28", attributes: {{ servizio: "WATER", device_class: "water" }} }},
    "sensor.el_p": {{ state: "180", attributes: {{ periodi: [{{ dal: "2026-08-01", al: "2026-08-31", giorni: 31, consumo: 180, fasce: {{ F1: 40, F2: 50, F3: 90 }} }}] }} }},
  }},
  config: {{ time_zone: "Europe/Rome" }},
  locale: {{ language: "it" }},
}};
const luceList = trovaContatoriLuce(luceHass);
if (luceList.length !== 1 || luceList[0].deviceId !== "d_el") throw new Error("trovaContatoriLuce failed");
const luceCard = new AcegasLuceCard();
luceCard._config = {{}};
luceCard._contatori = luceList;
luceCard._hass = luceHass;
const perLuce = luceCard._periodi();
if (perLuce[0].fasce.F3 !== 90) throw new Error("luce fasce missing");
const datiLuceAnno = luceCard._datiAnno(perLuce, 2026);
if (!datiLuceAnno.fasce || Math.round(datiLuceAnno.fasce.F1) !== 40 || Math.round(datiLuceAnno.fasce.F3) !== 90) {{
  throw new Error("luce year bands aggregation failed");
}}
const baseRgb = [72, 143, 194];
const lightF2 = sfumatura(baseRgb, 1, false);
const darkF2 = sfumatura(baseRgb, 1, true);
if (lightF2[0] >= baseRgb[0] || darkF2[0] <= baseRgb[0]) throw new Error("LAB shading direction invalid");

// 3. Rifiuti card: finds ENVIRONMENT device, localized date formatting, stacked tooltip, empty/error states
const {{ AcegasRifiutiCard, trovaUtenzeRifiuti }} = loadCard("acegasapsamga-rifiuti-card.js", ["AcegasRifiutiCard", "trovaUtenzeRifiuti"]);
const rifList = trovaUtenzeRifiuti({{
  entities: {{ r1: {{ platform: "acegasapsamga", device_id: "d_r", translation_key: "svuotamenti_rifiuti", entity_id: "sensor.r_s" }} }},
  devices: {{ d_r: {{ name: "Rifiuti TARI" }} }},
}});
if (rifList.length !== 1 || rifList[0].deviceId !== "d_r") throw new Error("trovaUtenzeRifiuti failed");
const rifCard = new AcegasRifiutiCard();
rifCard._hass = {{ locale: {{ language: "it" }}, user: {{ is_admin: true }} }};
const formattedDate = rifCard._giorno("2026-12-02");
if (formattedDate.includes("2026-12-02") || !formattedDate.includes("2")) throw new Error("rifiuti _giorno failed: " + formattedDate);
const rifTip = rifCard._tooltip(
  {{ mese: 5, svuotamenti: 3, volume: 360, per_tipo: {{ RSU: 2, CARTA: 1 }} }},
  ["RSU", "CARTA"],
  rifCard._colori()
);
if (!rifTip.includes("Indifferenziato") || !rifTip.includes("Carta") || !rifTip.includes("360 L")) {{
  throw new Error("rifiuti stacked tooltip missing fractions: " + rifTip);
}}
rifCard._renderVuota("device_not_found");
if (!rifCard.shadowRoot.innerHTML.includes('alert-type="warning"') || !rifCard.shadowRoot.innerHTML.includes('class="header static"')) {{
  throw new Error("rifiuti empty state missing native header/alert");
}}

// 4. Bollette card: deduplicates grouped PLICO bills across multiple contracts + empty/error states
const {{ AcegasBolletteCard, trovaEntita }} = loadCard("acegasapsamga-bollette-card.js", ["AcegasBolletteCard", "trovaEntita"]);
const bolHass = {{
  entities: {{
    b1: {{ platform: "acegasapsamga", device_id: "d1", translation_key: "bolletta", entity_id: "sensor.b1" }},
    b2: {{ platform: "acegasapsamga", device_id: "d2", translation_key: "bolletta", entity_id: "sensor.b2" }},
  }},
  devices: {{ d1: {{ name: "Acqua" }}, d2: {{ name: "Gas" }} }},
  states: {{
    "sensor.b1": {{ state: "100", attributes: {{ bollette: [{{ numero: "PLICO1", emissione: "2026-11-01", importo: 100, residuo: 100, stato: "unpaid" }}] }} }},
    "sensor.b2": {{ state: "100", attributes: {{ bollette: [{{ numero: "PLICO1", emissione: "2026-11-01", importo: 100, residuo: 100, stato: "unpaid" }}, {{ numero: "GAS2", emissione: "2026-10-01", importo: 50, residuo: 0, stato: "paid" }}] }} }},
  }},
  config: {{ components: ["acegasapsamga"] }},
  user: {{ is_admin: true }},
  locale: {{ language: "it" }},
}};
const bolCard = new AcegasBolletteCard();
bolCard._config = {{}};
bolCard._mappa = trovaEntita(bolHass);
bolCard._hass = bolHass;
const agg = bolCard._bolletteAggregate();
if (agg.length !== 2 || agg[0].numero !== "PLICO1") throw new Error("bill deduplication failed: " + agg.length);
const perSvc = bolCard._spesaPerServizio([
  {{ stato: "unpaid", importo: 100, importi_servizi: {{ WATER: 40, GAS: 60 }} }},
  {{ stato: "paid", importo: 50, importi_servizi: {{ GAS: 50 }} }},
  {{ stato: "paid", importo: 70, _servizio: "HEATING" }},
  {{ stato: "reversed", importo: 99, importi_servizi: {{ WATER: 99 }} }},
]);
if (perSvc.WATER !== 40 || perSvc.GAS !== 110 || perSvc.HEATING !== 70) throw new Error("bollette service split failed: " + JSON.stringify(perSvc));
if (bolCard._categoriaBolletta({{ importi_servizi: {{ ELECTRIC: 90 }} }}) !== "ELECTRIC") throw new Error("single service category failed");
// A bill that groups several utilities is filed under all of them, named after them.
if (bolCard._categoriaBolletta({{ importi_servizi: {{ GAS: 60, WATER: 40 }} }}) !== "WATER+GAS") throw new Error("combined category failed");
const nomeGruppoIt = bolCard._nomeServizio("WATER+GAS+ENVIRONMENT");
if (nomeGruppoIt !== "Acqua, gas e TARI") throw new Error("Italian combined group name failed: " + nomeGruppoIt);
bolCard._hass = {{ ...bolHass, locale: {{ language: "en" }} }};
const nomeGruppoEn = bolCard._nomeServizio("WATER+GAS+ENVIRONMENT");
if (nomeGruppoEn !== "Water, gas and waste") throw new Error("English combined group name failed: " + nomeGruppoEn);
bolCard._hass = bolHass;
if (traduci(bolHass, "direct_debit_on", {{ date: "1 dic" }}) !== "Addebito l'1 dic") throw new Error("Italian elision (1) failed");
if (traduci(bolHass, "direct_debit_on", {{ date: "8 dic" }}) !== "Addebito l'8 dic") throw new Error("Italian elision (8) failed");
if (traduci(bolHass, "direct_debit_on", {{ date: "11 dic" }}) !== "Addebito l'11 dic") throw new Error("Italian elision (11) failed");
if (traduci(bolHass, "direct_debit_on", {{ date: "10 dic" }}) !== "Addebito il 10 dic") throw new Error("Italian non-elision (10) failed");
if (bolCard._categoriaBolletta({{ _servizio: "HEATING" }}) !== "HEATING") throw new Error("fallback service category failed");
bolCard._renderVuota("not_configured");
if (!bolCard.shadowRoot.innerHTML.includes("Nessuna bolletta disponibile")) {{
  throw new Error("bollette configured empty state failed");
}}
bolCard._hass = {{ ...bolHass, config: {{ components: [] }}, user: {{ is_admin: false }} }};
bolCard._renderVuota("not_configured");
if (!bolCard.shadowRoot.innerHTML.includes("amministratore") || bolCard.shadowRoot.innerHTML.includes("<ha-button")) {{
  throw new Error("bollette non-admin state failed");
}}
card._renderVuota("device_not_found");
if (!card.shadowRoot.innerHTML.includes('alert-type="warning"') || !card.shadowRoot.innerHTML.includes('class="icon"')) {{
  throw new Error("contatore empty state missing native header/alert");
}}
luceCard._renderVuota("empty");
if (!luceCard.shadowRoot.innerHTML.includes('alert-type="info"') || !luceCard.shadowRoot.innerHTML.includes('data-apri="lettura"')) {{
  throw new Error("luce empty state missing clickable header/alert");
}}
"""
    esito = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
