/*
 * AcegasApsAmga waste / TARI card (Rifiuti / ENVIRONMENT / TCP).
 *
 * Served by the integration (lovelace_card.py), no resource to add by hand.
 *
 * Displays annual waste disposals and conferred volume, year-over-year delta,
 * active equipment summary, discounts, and optionally (show_bills: true) the
 * TARI bill due. A proportional waste-fraction bar and clickable legend filter
 * the stacked monthly disposal chart by waste fraction.
 *
 * All data comes from the integration's sensor attributes. Plain web component
 * in one file, zero dependencies.
 */

const CARD_TYPE = "acegasapsamga-rifiuti-card";
const EDITOR_TYPE = "acegasapsamga-rifiuti-card-editor";
const VERSION = "0.4.0-beta.1";
const DOMAIN = "acegasapsamga";
const URL_CONFIGURA = "/_my_redirect/config_flow_start?domain=acegasapsamga";
const STATI_DA_PAGARE = ["unpaid", "expired", "paid_partial"];
const ORDINE_FRAZIONI = ["RSU", "CARTA", "PLASTICA", "VETRO", "ORGANICO"];

const STRINGS = {
  it: {
    card_name: "AcegasApsAmga · Rifiuti (TARI)",
    card_description: "Svuotamenti annui per frazione, grafico mensile impilato, confronto anno precedente e dotazioni.",
    waste: "Rifiuti · TARI",
    contract_line: "Utenza {code} · {active} dotazioni attive",
    disposals_unit: "svuotamenti quest'anno",
    volume_line: "{volume} L conferiti",
    vs_prev_label: "Rispetto all'anno scorso",
    prev_detail: "{count} svuot. · {volume} L",
    prev_count_only: "{count} svuotamenti",
    equipment_label: "Dotazioni",
    equipment_active: "{active} attive",
    equipment_active_one: "1 attiva",
    equipment_total: "{total} registrate",
    advantages_title: "Agevolazioni",
    bill_due: "TARI da pagare",
    bill_overdue: "TARI scaduta",
    due_by: "Entro il {date}",
    direct_debit_on: "Addebito il {date}",
    overdue_since: "Scadeva il {date}",
    disposals: "Svuotamenti",
    disposals_axis: "Svuotamenti",
    volume: "Volume",
    monthly_chart: "Svuotamenti mensili per frazione nell'anno corrente",
    no_disposals: "Nessuno svuotamento registrato quest'anno.",
    not_configured_title: "Nessuna utenza TARI / Rifiuti",
    not_configured_text: "Configura un contratto rifiuti nell'integrazione AcegasApsAmga per usare questa card.",
    not_configured_sub: "Non configurata",
    device_not_found_title: "Utenza rifiuti non trovata",
    device_not_found_text: "L'utenza rifiuti configurata non è più disponibile. Scegline un'altra dalle impostazioni.",
    device_not_found_sub: "Dispositivo non disponibile",
    ask_admin: "Chiedi a un amministratore di farlo.",
    configure: "Configura",
    type_RSU: "Indifferenziato",
    type_CARTA: "Carta",
    type_VETRO: "Vetro",
    type_PLASTICA: "Plastica",
    type_ORGANICO: "Organico",
    ed_device: "Utenza rifiuti",
    ed_name: "Nome",
    ed_icon: "Icona",
    ed_show_bills: "Mostra bolletta TARI nella card",
  },
  en: {
    card_name: "AcegasApsAmga · Waste (TARI)",
    card_description: "Annual waste disposals by fraction, stacked monthly chart, year-over-year and equipment.",
    waste: "Waste · TARI",
    contract_line: "Contract {code} · {active} active items",
    disposals_unit: "disposals this year",
    volume_line: "{volume} L conferred",
    vs_prev_label: "Vs last year",
    prev_detail: "{count} disp. · {volume} L",
    prev_count_only: "{count} disposals",
    equipment_label: "Equipment",
    equipment_active: "{active} active",
    equipment_active_one: "1 active",
    equipment_total: "{total} registered",
    advantages_title: "Discounts",
    bill_due: "TARI bill due",
    bill_overdue: "TARI bill overdue",
    due_by: "Due by {date}",
    direct_debit_on: "Direct debit on {date}",
    overdue_since: "Was due on {date}",
    disposals: "Disposals",
    disposals_axis: "Disposals",
    volume: "Volume",
    monthly_chart: "Monthly waste disposals by fraction this year",
    no_disposals: "No waste disposals recorded this year.",
    not_configured_title: "No waste / TARI contract",
    not_configured_text: "Configure an environment / TARI contract in AcegasApsAmga to use this card.",
    not_configured_sub: "Not configured",
    device_not_found_title: "Waste contract not found",
    device_not_found_text: "The configured waste contract is no longer available. Pick another in card settings.",
    device_not_found_sub: "Device unavailable",
    ask_admin: "Ask an administrator to do it.",
    configure: "Set up",
    type_RSU: "Residual",
    type_CARTA: "Paper",
    type_VETRO: "Glass",
    type_PLASTICA: "Plastic",
    type_ORGANICO: "Organic",
    ed_device: "Waste contract",
    ed_name: "Name",
    ed_icon: "Icon",
    ed_show_bills: "Show TARI bill in card",
  },
};

// Home Assistant named color palette variables + fallback RGBs for each fraction.
const PALETTE_FRAZIONI = {
  RSU: { var: "--grey-color", fallback: [158, 158, 158] },
  CARTA: { var: "--blue-color", fallback: [33, 150, 243] },
  PLASTICA: { var: "--amber-color", fallback: [255, 193, 7] },
  VETRO: { var: "--green-color", fallback: [76, 175, 80] },
  ORGANICO: { var: "--brown-color", fallback: [121, 85, 72] },
};
const PALETTE_DEFAULT = { var: "--blue-grey-color", fallback: [96, 125, 139] };

const lingua = (hass) => ((hass?.locale?.language || hass?.language || "en").toLowerCase().startsWith("it") ? "it" : "en");

const traduci = (hass, key, vars = {}) => {
  let s = STRINGS[lingua(hass)][key] ?? STRINGS.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, () => String(v));
  return s;
};

const naviga = (percorso) => {
  history.pushState(null, "", percorso);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
};

const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const parseColore = (str, riserva = [76, 175, 80]) => {
  const s = (str || "").trim();
  let m = s.match(/^#([0-9a-f]{3,8})$/i);
  if (m) {
    let h = m[1];
    if (h.length <= 4) h = [...h].map((c) => c + c).join("");
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  }
  m = s.match(/^rgba?\(([^)]+)\)$/i);
  if (m) return m[1].split(/[\s,/]+/).slice(0, 3).map(Number);
  return riserva;
};

const rgbCss = (rgb, alpha) => (alpha === undefined ? `rgb(${rgb.join(",")})` : `rgba(${rgb.join(",")},${alpha})`);

const scalaIntera = (max, passi = 4) => {
  const hi = Math.max(1, Math.ceil(max));
  if (hi <= passi) {
    const ticks = [];
    for (let v = 0; v <= hi; v++) ticks.push(v);
    return { max: hi, ticks };
  }
  const grezzo = hi / passi;
  const mag = 10 ** Math.floor(Math.log10(grezzo));
  const n = grezzo / mag;
  const passo = Math.max(1, (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag);
  const top = Math.ceil(hi / passo) * passo;
  const ticks = [];
  for (let v = 0; v <= top; v += passo) ticks.push(v);
  return { max: top, ticks };
};

const ordinaTipi = (chiavi) => {
  const set = new Set(chiavi);
  const ordinati = ORDINE_FRAZIONI.filter((k) => set.has(k));
  const extra = [...set].filter((k) => !ORDINE_FRAZIONI.includes(k)).sort();
  return [...ordinati, ...extra];
};

const trovaUtenzeRifiuti = (hass) => {
  const perDispositivo = new Map();
  for (const e of Object.values(hass?.entities || {})) {
    if (e.platform !== DOMAIN || !e.device_id || !e.translation_key) continue;
    if (!perDispositivo.has(e.device_id)) perDispositivo.set(e.device_id, {});
    perDispositivo.get(e.device_id)[e.translation_key] = e.entity_id;
  }
  const risultato = [];
  for (const [deviceId, entita] of perDispositivo) {
    if (!entita.svuotamenti_rifiuti) continue;
    const device = hass.devices?.[deviceId];
    risultato.push({ deviceId, entita, nome: device?.name_by_user || device?.name || deviceId });
  }
  return risultato.sort((a, b) => a.nome.localeCompare(b.nome));
};

const valido = (stato) => !!stato && !["unavailable", "unknown", ""].includes(stato.state);
const _nfCache = new Map();
const _dfCache = new Map();

const numberFormatter = (locale, opzioni) => {
  const chiave = `${locale || ""}|${opzioni.style || "decimal"}|${opzioni.currency || ""}|${opzioni.minimumFractionDigits ?? ""}|${opzioni.maximumFractionDigits ?? ""}|${opzioni.useGrouping}`;
  let nf = _nfCache.get(chiave);
  if (!nf) {
    if (_nfCache.size >= 64) _nfCache.clear();
    nf = new Intl.NumberFormat(locale, opzioni);
    _nfCache.set(chiave, nf);
  }
  return nf;
};

const dateFormatter = (lang, opzioni) => {
  const chiave = `${lang}|${opzioni.day || ""}|${opzioni.month || ""}|${opzioni.year || ""}`;
  let df = _dfCache.get(chiave);
  if (!df) {
    if (_dfCache.size >= 64) _dfCache.clear();
    df = new Intl.DateTimeFormat(lang, { timeZone: "UTC", ...opzioni });
    _dfCache.set(chiave, df);
  }
  return df;
};

const SENSORI_MOSTRATI = ["svuotamenti_rifiuti", "volume_rifiuti", "dotazioni_rifiuti", "bolletta", "da_pagare", "scadenza_bolletta"];

class AcegasRifiutiCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig() {
    return {};
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._larghezza = 0;
    this._hover = null;
    this._filtroTipo = null;
    this._firma = "";
    this._chiudiEsterno = null;
  }

  setConfig(config) {
    if (config.device_id !== this._config.device_id) this._filtroTipo = null;
    this._config = { ...config };
    this._firma = "";
    this._render();
  }

  set hass(hass) {
    if (this._utenzeDa !== hass.entities) {
      this._utenze = trovaUtenzeRifiuti(hass);
      this._utenzeDa = hass.entities;
    }
    this._hass = hass;
    const firma = this._firmaVista();
    if (firma !== this._firma) {
      this._firma = firma;
      this._render();
    }
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this._ro = new ResizeObserver((entries) => {
      const w = Math.floor(entries[0]?.contentRect.width || 0);
      if (w && w !== this._larghezza) {
        this._larghezza = w;
        this._renderGrafico();
      }
    });
    const chart = this.shadowRoot.querySelector(".chart");
    if (chart) this._ro.observe(chart);
  }

  disconnectedCallback() {
    this._ro?.disconnect();
    this._ro = null;
    this._staccaChiusuraEsterna();
  }

  _staccaChiusuraEsterna() {
    if (this._chiudiEsterno) {
      document.removeEventListener("pointerdown", this._chiudiEsterno);
      this._chiudiEsterno = null;
    }
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  get _utenza() {
    const utenze = this._utenze || [];
    if (this._config.device_id) {
      return utenze.find((u) => u.deviceId === this._config.device_id) || null;
    }
    return utenze[0] || null;
  }

  _stato(chiave) {
    const id = this._utenza?.entita[chiave];
    return id ? this._hass?.states[id] : undefined;
  }

  _firmaVista() {
    const h = this._hass;
    const stati = SENSORI_MOSTRATI.map((k) => {
      const s = this._stato(k);
      return s ? `${s.state}@${s.last_updated}` : "";
    });
    return [
      this._utenza?.deviceId,
      this._config.device_id,
      !!this._config.show_bills,
      h.themes?.theme,
      h.themes?.darkMode,
      h.locale?.language || h.language,
      h.locale?.number_format,
      h.user?.is_admin,
      ...stati,
    ].join("|");
  }

  get _locale() {
    const lang = this._hass?.locale?.language || this._hass?.language || "it";
    const fmt = this._hass?.locale?.number_format;
    return { comma_decimal: "en-US", decimal_comma: "de", space_comma: "fr", quote_decimal: "de-CH", system: undefined }[fmt] ?? lang;
  }

  _numero(v, cifre = 0) {
    if (v === null || v === undefined || Number.isNaN(v)) return "-";
    return numberFormatter(this._locale, {
      minimumFractionDigits: cifre, maximumFractionDigits: cifre,
      useGrouping: this._hass?.locale?.number_format !== "none",
    }).format(v);
  }

  _percentuale(v, tot) {
    if (!tot) return "-";
    return numberFormatter(this._locale, {
      style: "percent", maximumFractionDigits: 0, useGrouping: false,
    }).format(v / tot);
  }

  _euro(v) {
    return numberFormatter(this._locale, {
      style: "currency", currency: "EUR", useGrouping: this._hass?.locale?.number_format !== "none",
    }).format(v);
  }

  _nomeMese(m, narrow = false) {
    const lang = this._hass?.locale?.language || this._hass?.language || "it";
    return dateFormatter(lang, { month: narrow ? "narrow" : "short" }).format(new Date(Date.UTC(2026, m - 1, 15)));
  }

  _giorno(iso) {
    if (!iso) return "";
    const parti = String(iso).split("-").map(Number);
    if (parti.length !== 3 || parti.some(Number.isNaN)) return String(iso);
    const lang = this._hass?.locale?.language || this._hass?.language || "it";
    return dateFormatter(lang, { day: "numeric", month: "short" }).format(new Date(Date.UTC(parti[0], parti[1] - 1, parti[2])));
  }

  _nomeTipo(tipo) {
    return STRINGS[lingua(this._hass)][`type_${tipo}`] || tipo;
  }

  _colori() {
    const cs = getComputedStyle(this);
    const accent = parseColore(
      cs.getPropertyValue("--green-color") || cs.getPropertyValue("--success-color"),
      [76, 175, 80]
    );
    const perTipo = {};
    for (const [k, spec] of Object.entries(PALETTE_FRAZIONI)) {
      perTipo[k] = parseColore(cs.getPropertyValue(spec.var), spec.fallback);
    }
    const fallback = parseColore(cs.getPropertyValue(PALETTE_DEFAULT.var), PALETTE_DEFAULT.fallback);
    return { accent, perTipo, fallback };
  }

  _coloreTipo(tipo, colori) {
    return colori.perTipo[tipo] || colori.fallback;
  }

  _render() {
    if (!this._hass) return;
    if (!this._utenza) {
      this._renderVuota(this._config.device_id ? "device_not_found" : "not_configured");
      return;
    }
    if (this._modo !== "card") this._struttura();

    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const colori = this._colori();
    $("ha-card").style.setProperty("--acegas-accent", rgbCss(colori.accent));

    const icona = this._config.icon || "mdi:trash-can";
    if ($(".icon ha-icon").getAttribute("icon") !== icona) $(".icon ha-icon").setAttribute("icon", icona);
    $(".primary").textContent = this._config.name || t("waste");

    const svu = this._stato("svuotamenti_rifiuti");
    const vol = this._stato("volume_rifiuti");
    const dot = this._stato("dotazioni_rifiuti");
    const attive = valido(dot) ? Number(dot.state) : 0;
    const codice = svu?.attributes?.pod || this._utenza.nome;
    $(".secondary").textContent = t("contract_line", { code: codice, active: this._numero(attive, 0) });

    const conteggio = valido(svu) ? Number(svu.state) : 0;
    const litri = valido(vol) ? Number(vol.state) : 0;
    $(".hero-value").textContent = this._numero(conteggio, 0);
    $(".hero-unit").textContent = t("disposals_unit");
    $(".hero-sub").textContent = t("volume_line", { volume: this._numero(litri, 0) });

    this._renderFatti(conteggio, litri);

    const perTipo = svu?.attributes?.per_tipo || {};
    if (this._filtroTipo && !perTipo[this._filtroTipo]) this._filtroTipo = null;
    this._renderFrazioni(perTipo, colori);

    const vantaggi = svu?.attributes?.vantaggi || [];
    const advBox = $(".advantages-footer");
    advBox.hidden = !vantaggi.length;
    if (vantaggi.length) {
      $(".advantages-title").textContent = t("advantages_title");
      $(".advantages").innerHTML = vantaggi
        .map((v) => `<span class="adv-pill">${escapeHtml(v.descrizione || v.codice)}</span>`)
        .join("");
    }

    this._larghezza = $(".chart").clientWidth || this._larghezza;
    this._renderGrafico(colori);
  }

  _renderFatti(conteggio, litri) {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const svu = this._stato("svuotamenti_rifiuti");
    const vol = this._stato("volume_rifiuti");
    const dot = this._stato("dotazioni_rifiuti");

    // Fact 1: Year-over-year comparison
    const fattoPrev = $('[data-fatto="prev"]');
    const precVol = vol?.attributes?.anno_precedente;
    const precCont = svu?.attributes?.anno_precedente;
    const haPrev = (typeof precVol === "number" && precVol > 0) || (typeof precCont === "number" && precCont > 0);
    fattoPrev.hidden = !haPrev;
    if (haPrev) {
      fattoPrev.querySelector(".fact-label").textContent = t("vs_prev_label");
      if (typeof precVol === "number" && precVol > 0) {
        const diff = Math.round(((litri - precVol) / precVol) * 100);
        fattoPrev.querySelector(".fact-value").textContent = diff > 0 ? `+${diff}%` : `${diff}%`;
        fattoPrev.querySelector(".fact-sub span").textContent = typeof precCont === "number"
          ? t("prev_detail", { count: this._numero(precCont, 0), volume: this._numero(precVol, 0) })
          : `${this._numero(precVol, 0)} L`;
      } else {
        const diff = conteggio - precCont;
        fattoPrev.querySelector(".fact-value").textContent = diff > 0 ? `+${diff}` : `${diff}`;
        fattoPrev.querySelector(".fact-sub span").textContent = t("prev_count_only", { count: this._numero(precCont, 0) });
      }
    }

    // Fact 2: Active equipment summary (tapping opens dotazioni_rifiuti more-info with full details)
    const fattoDot = $('[data-fatto="dotazioni"]');
    const elencoDot = dot?.attributes?.dotazioni || [];
    const attiveNum = valido(dot) ? Number(dot.state) : 0;
    const totaleDot = Number(dot?.attributes?.totale) || elencoDot.length;
    const haDot = attiveNum > 0 || totaleDot > 0;
    fattoDot.hidden = !haDot;
    if (haDot) {
      fattoDot.querySelector(".fact-label").textContent = t("equipment_label");
      fattoDot.querySelector(".fact-value").textContent = attiveNum === 1
        ? t("equipment_active_one")
        : t("equipment_active", { active: this._numero(attiveNum, 0) });
      const nomiAttivi = elencoDot
        .filter((d) => String(d.stato || "").toUpperCase() === "ACTIVE")
        .map((d) => d.descrizione || d.tipo)
        .filter(Boolean);
      fattoDot.querySelector(".fact-sub span").textContent = nomiAttivi.length
        ? nomiAttivi.join(", ")
        : t("equipment_total", { total: this._numero(totaleDot, 0) });
    }

    // Fact 3: TARI bill due (optional, shown when show_bills is enabled)
    const fattoBol = $('[data-fatto="bolletta"]');
    const daPagare = this._config.show_bills ? this._stato("da_pagare") : null;
    const importoDue = valido(daPagare) ? Number(daPagare.state) : 0;
    fattoBol.hidden = !(importoDue > 0);
    if (importoDue > 0) {
      const scad = this._stato("scadenza_bolletta");
      const bol = this._stato("bolletta");
      const aperte = (bol?.attributes?.bollette || []).filter((b) => STATI_DA_PAGARE.includes(b.stato) && b.residuo > 0);
      const scaduta = aperte.some((b) => b.stato === "expired");
      const dom = aperte.length ? aperte.every((b) => b.domiciliata) : !!bol?.attributes?.domiciliata;
      fattoBol.classList.toggle("scaduta", scaduta);
      fattoBol.querySelector(".fact-label").textContent = scaduta ? t("bill_overdue") : t("bill_due");
      fattoBol.querySelector(".fact-value").textContent = this._euro(importoDue);
      const dataScad = valido(scad) ? this._giorno(scad.state) : "";
      fattoBol.querySelector(".fact-sub span").textContent = dataScad
        ? scaduta ? t("overdue_since", { date: dataScad })
          : dom ? t("direct_debit_on", { date: dataScad }) : t("due_by", { date: dataScad })
        : "";
    }

    const visibili = [!fattoPrev.hidden, !fattoDot.hidden, !fattoBol.hidden].filter(Boolean).length;
    $(".facts").hidden = visibili === 0;
    $(".facts").classList.toggle("tre", visibili === 3);
  }

  // Renders the proportional fraction split bar and clickable legend to filter the chart.
  _renderFrazioni(perTipo, colori) {
    const blocco = this.shadowRoot.querySelector(".frazioni");
    const tipi = ordinaTipi(Object.keys(perTipo)).filter((k) => (Number(perTipo[k]?.svuotamenti) || 0) > 0);
    if (!tipi.length) {
      blocco.hidden = true;
      return;
    }
    const totale = tipi.reduce((s, k) => s + (Number(perTipo[k].svuotamenti) || 0), 0);
    if (!(totale > 0)) {
      blocco.hidden = true;
      return;
    }
    blocco.hidden = false;
    const attivo = this._filtroTipo;

    const split = blocco.querySelector(".split");
    split.setAttribute(
      "aria-label",
      tipi.map((k) => `${this._nomeTipo(k)} ${this._percentuale(Number(perTipo[k].svuotamenti) || 0, totale)}`).join(", ")
    );
    split.innerHTML = tipi.map((k) => {
      const val = Number(perTipo[k].svuotamenti) || 0;
      const dim = attivo && attivo !== k ? " dim" : "";
      return `<span class="${dim.trim()}" style="flex-grow:${val};background:${rgbCss(this._coloreTipo(k, colori))}"></span>`;
    }).join("");

    const legend = blocco.querySelector(".legend");
    legend.innerHTML = tipi.map((k) => {
      const info = perTipo[k];
      const count = Number(info.svuotamenti) || 0;
      const vol = Number(info.volume) || 0;
      const selected = attivo === k;
      const dim = attivo && !selected ? " dim" : "";
      const rgb = this._coloreTipo(k, colori);
      return `<button type="button" class="legend-item${selected ? " active" : ""}${dim}" data-tipo="${escapeHtml(k)}" aria-pressed="${selected}">
        <div class="legend-name">
          <span class="dot" style="background:${rgbCss(rgb)}"></span>
          <span class="legend-label">${escapeHtml(this._nomeTipo(k))}</span>
          <span class="legend-pct">${escapeHtml(this._percentuale(count, totale))}</span>
        </div>
        <div class="legend-val">${escapeHtml(this._numero(count, 0))}${vol > 0 ? ` · ${escapeHtml(this._numero(vol, 0))} L` : ""}</div>
      </button>`;
    }).join("");

    legend.querySelectorAll("[data-tipo]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tipo = btn.dataset.tipo;
        this._filtroTipo = this._filtroTipo === tipo ? null : tipo;
        this._hover = null;
        this._renderFrazioni(perTipo, colori);
        this._renderGrafico(colori);
      });
    });
  }

  // Draws the stacked monthly disposal chart (or a single fraction when filtered).
  _renderGrafico(colori = this._colori()) {
    const host = this.shadowRoot.querySelector(".svg-host");
    if (!host) return;
    this._staccaChiusuraEsterna();
    const W = this._larghezza || host.clientWidth;
    if (!W) {
      host.innerHTML = "";
      return;
    }
    const t = (k) => traduci(this._hass, k);
    const svu = this._stato("svuotamenti_rifiuti");
    const mesi = svu?.attributes?.per_mese || Array.from({ length: 12 }, (_, i) => ({ mese: i + 1, svuotamenti: 0, volume: 0, per_tipo: {} }));
    const filtro = this._filtroTipo;

    const valoreMese = (m) => {
      if (filtro) return Number(m.per_tipo?.[filtro]) || 0;
      const sommaTipi = m.per_tipo
        ? Object.values(m.per_tipo).reduce((s, v) => s + (Number(v) || 0), 0)
        : 0;
      return sommaTipi > 0 ? sommaTipi : (Number(m.svuotamenti) || 0);
    };

    const tipiPresenti = ordinaTipi([
      ...Object.keys(svu?.attributes?.per_tipo || {}),
      ...mesi.flatMap((m) => Object.keys(m.per_tipo || {})),
    ]);
    const valori = mesi.map(valoreMese);
    const hasAny = valori.some((v) => v > 0);
    const scala = scalaIntera(Math.max(1, ...valori), 4);

    const H = 186;
    const top = 30;
    const bottom = 22;
    const etichetteY = scala.ticks.map((v) => this._numero(v, 0));
    const left = Math.max(24, Math.ceil(Math.max(...etichetteY.map((s) => s.length)) * 7) + 10);
    const right = 4;
    const plotW = Math.max(10, W - left - right);
    const plotH = H - top - bottom;
    const slotW = plotW / 12;
    const barW = Math.max(6, Math.min(28, slotW * 0.68));
    const y = (v) => top + ((scala.max - v) / scala.max) * plotH;

    const parti = [];
    scala.ticks.forEach((v, idx) => {
      const yy = Math.round(y(v)) + 0.5;
      parti.push(`<line class="grid" x1="${left}" x2="${W - right}" y1="${yy}" y2="${yy}"/>`);
      parti.push(`<text class="ylab" x="${left - 8}" y="${yy + 4}">${escapeHtml(etichetteY[idx])}</text>`);
    });
    const etichettaAsse = filtro ? `${t("disposals_axis")} · ${this._nomeTipo(filtro)}` : t("disposals_axis");
    parti.push(`<text class="unita" x="0" y="12">${escapeHtml(etichettaAsse)}</text>`);
    parti.push(`<rect class="hover-band" x="0" y="${top}" width="0" height="${plotH}"/>`);

    const segmento = (x0, w, yBot, yTop, rgb, arrotondaSopra) => {
      const h = Math.abs(yBot - yTop);
      const yy = Math.min(yBot, yTop);
      if (h < 2 || w < 3) {
        return `<rect x="${x0}" y="${yy}" width="${Math.max(w, 1)}" height="${Math.max(h, 0.5)}" fill="${rgbCss(rgb)}"/>`;
      }
      const i = 0.75;
      const L = x0 + i;
      const R = x0 + w - i;
      const T = yy + i;
      const B = yy + h - i;
      const r = arrotondaSopra ? Math.max(0, Math.min(4, (R - L) / 2, (B - T) / 2)) : 0;
      const d = `M${L},${T + r}`
        + (r ? `Q${L},${T} ${L + r},${T}` : "") + `L${R - r},${T}`
        + (r ? `Q${R},${T} ${R},${T + r}` : "") + `L${R},${B}L${L},${B}Z`;
      return `<path d="${d}" fill="${rgbCss(rgb, 0.5)}" stroke="${rgbCss(rgb)}" stroke-width="1.5" stroke-linejoin="round"/>`;
    };

    const stretta = W < 360;
    mesi.forEach((m, idx) => {
      const cx = left + (idx + 0.5) * slotW;
      const x0 = cx - barW / 2;
      if (filtro) {
        const val = Number(m.per_tipo?.[filtro]) || 0;
        if (val > 0) {
          parti.push(segmento(x0, barW, y(0), y(val), this._coloreTipo(filtro, colori), true));
        }
      } else {
        const perMeseTipo = m.per_tipo || {};
        const attiviMese = tipiPresenti.filter((k) => (Number(perMeseTipo[k]) || 0) > 0);
        if (attiviMese.length) {
          let acc = 0;
          attiviMese.forEach((k, j) => {
            const val = Number(perMeseTipo[k]) || 0;
            parti.push(segmento(x0, barW, y(acc), y(acc + val), this._coloreTipo(k, colori), j === attiviMese.length - 1));
            acc += val;
          });
        } else {
          const val = Number(m.svuotamenti) || 0;
          if (val > 0) {
            parti.push(segmento(x0, barW, y(0), y(val), colori.accent, true));
          }
        }
      }
      parti.push(`<text class="xlab" x="${cx}" y="${H - 4}">${escapeHtml(this._nomeMese(m.mese, stretta))}</text>`);
    });

    host.innerHTML = `
      <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" tabindex="0" aria-label="${escapeHtml(t("monthly_chart"))}">
        ${parti.join("")}
        <rect class="hit" x="${left}" y="${top}" width="${plotW}" height="${plotH + 10}"/>
      </svg>
      ${hasAny ? "" : `<div class="no-data">${escapeHtml(t("no_disposals"))}</div>`}`;

    const svg = host.querySelector("svg");
    const banda = svg.querySelector(".hover-band");
    const tip = this.shadowRoot.querySelector(".tooltip");
    const indice = (ev) => {
      const r = svg.getBoundingClientRect();
      const idx = Math.floor((ev.clientX - r.left - left) / slotW);
      return idx >= 0 && idx < 12 ? idx : null;
    };
    const nascondi = () => {
      this._hover = null;
      banda.setAttribute("width", 0);
      tip.hidden = true;
      svg.removeAttribute("aria-describedby");
      this._staccaChiusuraEsterna();
    };
    const mostra = (i) => {
      if (i === null || !mesi[i]) return nascondi();
      const m = mesi[i];
      this._hover = i;
      banda.setAttribute("x", left + i * slotW);
      banda.setAttribute("width", slotW);
      tip.innerHTML = this._tooltip(m, tipiPresenti, colori);
      tip.hidden = false;
      svg.setAttribute("aria-describedby", "chart-tooltip");
      const cx = left + (i + 0.5) * slotW;
      const tw = tip.offsetWidth;
      const lx = cx < W / 2 ? cx + slotW / 2 + 6 : cx - slotW / 2 - 6 - tw;
      tip.style.left = `${Math.max(0, Math.min(W - tw, lx))}px`;
      tip.style.top = `${Math.min(top, H - tip.offsetHeight)}px`;
      if (!this._chiudiEsterno) {
        this._chiudiEsterno = (ev) => {
          if (!ev.composedPath().includes(svg)) nascondi();
        };
        document.addEventListener("pointerdown", this._chiudiEsterno);
      }
    };
    svg.addEventListener("pointermove", (ev) => ev.pointerType === "mouse" && mostra(indice(ev)));
    svg.addEventListener("pointerleave", (ev) => ev.pointerType === "mouse" && nascondi());
    svg.addEventListener("pointerup", (ev) => {
      const i = indice(ev);
      if (i === this._hover && ev.pointerType !== "mouse") nascondi();
      else mostra(i);
    });
    svg.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") nascondi();
      else if (ev.key === "ArrowRight") {
        ev.preventDefault();
        mostra(this._hover === null ? 0 : Math.min(11, this._hover + 1));
      } else if (ev.key === "ArrowLeft") {
        ev.preventDefault();
        mostra(this._hover === null ? 11 : Math.max(0, this._hover - 1));
      }
    });
    svg.addEventListener("blur", nascondi);
    nascondi();
  }

  _tooltip(m, tipiPresenti, colori) {
    const t = (k) => traduci(this._hass, k);
    const riga = (nome, valore, rgb, extraClass = "") => `<div class="tip-row ${extraClass}">${rgb ? `<span class="tip-marker" style="background:${rgbCss(rgb)}"></span>` : ""}
      <span class="tip-name">${escapeHtml(nome)}</span><span class="tip-value">${escapeHtml(valore)}</span></div>`;
    const righe = [];
    const filtro = this._filtroTipo;
    if (filtro) {
      const val = Number(m.per_tipo?.[filtro]) || 0;
      righe.push(riga(this._nomeTipo(filtro), this._numero(val, 0), this._coloreTipo(filtro, colori)));
    } else {
      const perMeseTipo = m.per_tipo || {};
      const presenti = [...tipiPresenti].reverse().filter((k) => (Number(perMeseTipo[k]) || 0) > 0);
      for (const k of presenti) {
        righe.push(riga(this._nomeTipo(k), this._numero(Number(perMeseTipo[k]), 0), this._coloreTipo(k, colori)));
      }
      righe.push(riga(t("disposals"), this._numero(Number(m.svuotamenti) || 0, 0), null, presenti.length ? "tip-total" : ""));
      if ((Number(m.volume) || 0) > 0) {
        righe.push(riga(t("volume"), `${this._numero(Number(m.volume), 0)} L`));
      }
    }
    return `<div class="tip-title">${escapeHtml(this._nomeMese(m.mese))}</div>${righe.join("")}`;
  }

  _renderVuota(chiave) {
    this._ro?.disconnect();
    this._staccaChiusuraEsterna();
    const firma = `vuota-${chiave}-${lingua(this._hass)}-${this._hass.user?.is_admin}-${this._config.name || ""}-${this._config.icon || ""}`;
    if (this._modo === firma) return;
    this._modo = firma;
    const t = (k) => traduci(this._hass, k);
    const admin = !!this._hass.user?.is_admin;
    const icona = this._config.icon || "mdi:trash-can";
    const titoloCard = this._config.name || t("waste");
    const accent = chiave === "device_not_found"
      ? "var(--warning-color, #ffa600)"
      : "var(--state-inactive-color, var(--disabled-text-color, #9e9e9e))";
    const sottotitolo = chiave === "device_not_found" ? t("device_not_found_sub") : t("not_configured_sub");
    const contenuto = chiave === "not_configured"
      ? `<ha-alert alert-type="info" title="${escapeHtml(t("not_configured_title"))}">
          ${escapeHtml(t("not_configured_text"))}${admin ? "" : ` ${escapeHtml(t("ask_admin"))}`}
          ${admin ? `<ha-button slot="action" data-percorso="${escapeHtml(URL_CONFIGURA)}">${escapeHtml(t("configure"))}</ha-button>` : ""}
        </ha-alert>`
      : `<ha-alert alert-type="warning" title="${escapeHtml(t("device_not_found_title"))}">${escapeHtml(t("device_not_found_text"))}</ha-alert>`;
    this.shadowRoot.innerHTML = `<style>${STILE}</style>
      <ha-card style="--acegas-accent:${accent}">
        <article class="card">
          <div class="header static">
            <div class="icon"><ha-icon icon="${escapeHtml(icona)}"></ha-icon></div>
            <div class="info">
              <div class="primary">${escapeHtml(titoloCard)}</div>
              <div class="secondary">${escapeHtml(sottotitolo)}</div>
            </div>
          </div>
          <div class="content empty-content">${contenuto}</div>
        </article>
      </ha-card>`;
    this.shadowRoot.querySelectorAll("[data-percorso]").forEach((el) =>
      el.addEventListener("click", () => naviga(el.dataset.percorso)));
  }

  _struttura() {
    this._modo = "card";
    this.shadowRoot.innerHTML = `
      <style>${STILE}</style>
      <ha-card>
        <article class="card">
          <button type="button" class="header" data-apri="svuotamenti_rifiuti">
            <div class="icon"><ha-icon></ha-icon></div>
            <div class="info">
              <div class="primary"></div>
              <div class="secondary"></div>
            </div>
          </button>
          <div class="content">
            <button type="button" class="hero" data-apri="volume_rifiuti">
              <div class="hero-main"><span class="hero-value"></span><span class="hero-unit"></span></div>
              <div class="hero-sub"></div>
            </button>
            <div class="facts" hidden>
              <button type="button" class="fact" data-fatto="prev" data-apri="volume_rifiuti" hidden>
                <div class="fact-label"></div>
                <div class="fact-value"></div>
                <div class="fact-sub"><span></span></div>
              </button>
              <button type="button" class="fact" data-fatto="dotazioni" data-apri="dotazioni_rifiuti" hidden>
                <div class="fact-label"></div>
                <div class="fact-value"></div>
                <div class="fact-sub"><span></span></div>
              </button>
              <button type="button" class="fact" data-fatto="bolletta" data-apri="bolletta" hidden>
                <div class="fact-label"></div>
                <div class="fact-value"></div>
                <div class="fact-sub"><span></span></div>
              </button>
            </div>
            <div class="frazioni" hidden>
              <div class="split" role="img"></div>
              <div class="legend"></div>
            </div>
            <div class="chart">
              <div class="svg-host"></div>
              <div id="chart-tooltip" class="tooltip" role="tooltip" hidden></div>
            </div>
            <footer class="advantages-footer" hidden>
              <div class="advantages-title"></div>
              <div class="advantages"></div>
            </footer>
          </div>
        </article>
      </ha-card>`;

    const root = this.shadowRoot;
    root.querySelectorAll("[data-apri]").forEach((el) => {
      el.addEventListener("click", () => this._moreInfo(this._utenza?.entita[el.dataset.apri]));
    });
    if (this._ro) {
      this._ro.disconnect();
      this._ro.observe(root.querySelector(".chart"));
    }
  }

  _moreInfo(entityId) {
    if (!entityId) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
  }
}

const STILE = `
  :host { display: block; --acegas-accent: var(--green-color, var(--success-color, #4caf50)); }
  ha-card { height: 100%; overflow: hidden; }
  .card { display: block; }
  ha-alert { display: block; }
  [hidden] { display: none !important; }

  .header, .hero, .fact, .legend-item {
    appearance: none; background: none; border: 0; font: inherit; color: inherit;
    text-align: start; padding: 0; margin: 0; width: 100%; box-sizing: border-box;
  }
  .header {
    display: flex; align-items: center; gap: 10px;
    padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px) 0; cursor: pointer; outline: none;
    border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
  }
  .header.static { cursor: default; }
  .header:focus-visible, .hero:focus-visible, .fact:focus-visible, .legend-item:focus-visible, svg:focus-visible {
    box-shadow: inset 0 0 0 2px var(--acegas-accent);
  }
  .icon {
    position: relative; flex: none; display: flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; overflow: hidden;
    border-radius: var(--ha-tile-icon-border-radius, var(--ha-border-radius-pill, 9999px));
    color: var(--acegas-accent); --mdc-icon-size: 24px;
  }
  .icon::before {
    content: ""; position: absolute; inset: 0;
    background-color: var(--acegas-accent); opacity: 0.2; transition: opacity 180ms ease-in-out;
  }
  .header:not(.static):hover .icon::before { opacity: 0.35; }
  .icon ha-icon { position: relative; display: flex; }
  .info { min-width: 0; flex: 1; }
  .primary {
    font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500);
    line-height: 20px; letter-spacing: 0.1px; color: var(--primary-text-color);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .secondary {
    font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-normal, 400);
    line-height: 16px; letter-spacing: 0.4px; color: var(--secondary-text-color);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }

  .content { display: flex; flex-direction: column; gap: var(--ha-space-3, 12px); padding: var(--ha-space-4, 16px); container-type: inline-size; }
  .empty-content { padding-top: var(--ha-space-3, 12px); }

  .hero { cursor: pointer; outline: none; border-radius: var(--ha-border-radius-md, 8px); }
  .hero-main { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; line-height: var(--ha-line-height-condensed, 1.2); }
  .hero-value { font-size: var(--ha-font-size-3xl, 28px); font-weight: var(--ha-font-weight-normal, 400); color: var(--primary-text-color); font-variant-numeric: tabular-nums; }
  .hero-unit { font-size: var(--ha-font-size-l, 16px); color: var(--secondary-text-color); }
  .hero-sub { margin-top: 2px; font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px; color: var(--secondary-text-color); }

  .facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px; }
  .facts.tre { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .fact { min-width: 0; cursor: pointer; outline: none; border-radius: var(--ha-border-radius-md, 8px); }
  .fact-label, .fact-sub {
    font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px;
    color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .fact-value {
    margin-top: 2px; font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500);
    line-height: 20px; color: var(--primary-text-color); font-variant-numeric: tabular-nums;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .fact.scaduta .fact-label { color: var(--error-color, #db4437); }

  /* Waste-fraction split bar and interactive legend */
  .frazioni { display: flex; flex-direction: column; gap: 8px; }
  .split {
    display: flex; gap: 2px; height: 8px; overflow: hidden; flex: none;
    border-radius: var(--ha-border-radius-pill, 9999px);
  }
  .split span { min-width: 2px; transition: opacity 160ms ease; }
  .split span.dim { opacity: 0.22; }
  .legend { display: grid; grid-template-columns: repeat(auto-fit, minmax(112px, 1fr)); gap: 4px 8px; }
  .legend-item {
    min-width: 0; min-height: 40px; padding: 4px 6px; margin: -2px -6px; width: calc(100% + 12px);
    cursor: pointer; outline: none; border-radius: var(--ha-border-radius-md, 8px);
    transition: opacity 160ms ease, background-color 160ms ease;
  }
  .legend-item:hover { background: color-mix(in srgb, var(--primary-text-color) 6%, transparent); }
  .legend-item.active { background: color-mix(in srgb, var(--primary-text-color) 10%, transparent); }
  .legend-item.dim { opacity: 0.42; }
  .legend-name {
    display: flex; align-items: center; gap: 6px; font-size: var(--ha-font-size-s, 12px);
    font-weight: var(--ha-font-weight-medium, 500); line-height: 16px; color: var(--primary-text-color);
  }
  .legend-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
  .legend-pct { font-weight: var(--ha-font-weight-normal, 400); color: var(--secondary-text-color); font-variant-numeric: tabular-nums; flex: none; }
  .legend-val {
    font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px;
    color: var(--secondary-text-color); padding-inline-start: 14px; font-variant-numeric: tabular-nums;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  .chart { position: relative; min-height: 186px; margin: 0 -4px; touch-action: pan-y; }
  svg { display: block; overflow: visible; outline: none; border-radius: var(--ha-border-radius-md, 8px); }
  svg text { font-size: var(--ha-font-size-s, 12px); fill: var(--primary-text-color); }
  svg .ylab { text-anchor: end; }
  svg .unita { fill: var(--secondary-text-color); }
  svg .xlab { text-anchor: middle; }
  svg .grid { stroke: var(--divider-color); stroke-width: 1; }
  svg .hover-band { fill: var(--secondary-text-color); opacity: 0.1; }
  svg .hit { fill: transparent; }
  .no-data {
    position: absolute; inset: 30px 0 22px 28px; display: flex; align-items: center; justify-content: center;
    color: var(--secondary-text-color); font-size: var(--ha-font-size-m, 14px); pointer-events: none;
  }

  .advantages-footer {
    padding-top: var(--ha-space-3, 12px); border-top: 1px solid var(--divider-color);
    display: flex; flex-direction: column; gap: 6px;
  }
  .advantages-title {
    font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px;
    color: var(--secondary-text-color);
  }
  .advantages { display: flex; flex-wrap: wrap; gap: 6px; }
  .adv-pill {
    font-size: var(--ha-font-size-s, 12px); padding: 4px 10px;
    border-radius: var(--ha-border-radius-pill, 9999px);
    background: color-mix(in srgb, var(--acegas-accent) 12%, transparent);
    color: var(--primary-text-color);
  }

  .tooltip {
    position: absolute; z-index: 1; pointer-events: none; white-space: nowrap;
    background: var(--ha-card-background, var(--card-background-color, #fff));
    border: 1px solid var(--divider-color); border-radius: var(--ha-border-radius-sm, 4px);
    box-shadow: rgba(0, 0, 0, 0.2) 1px 2px 10px; padding: 8px 10px;
    font-size: var(--ha-font-size-s, 12px); line-height: 18px; color: var(--primary-text-color);
  }
  .tip-title { font-weight: var(--ha-font-weight-medium, 500); margin-bottom: 2px; }
  .tip-row { display: flex; align-items: center; gap: 6px; }
  .tip-marker { width: 10px; height: 10px; border-radius: 50%; flex: none; }
  .tip-name { flex: 1; }
  .tip-value { font-weight: var(--ha-font-weight-medium, 500); margin-inline-start: 16px; font-variant-numeric: tabular-nums; }
  .tip-total { border-top: 1px solid var(--divider-color); margin-top: 4px; padding-top: 4px; }

  @container (max-width: 300px) {
    .facts, .facts.tre { grid-template-columns: 1fr; }
    .legend { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }

  @media (prefers-reduced-motion: reduce) {
    * { transition-duration: 1ms !important; }
  }
`;

const caricaHaForm = async () => {
  if (customElements.get("ha-form")) return;
  const helpers = await window.loadCardHelpers?.();
  const card = await helpers?.createCardElement({ type: "entities", entities: [] });
  await card?.constructor?.getConfigElement?.();
};

class AcegasRifiutiCardEditor extends HTMLElement {
  constructor() {
    super();
    this._schemaCache = this._schema();
    this._connected = false;
    this._ultimoStatoForm = "";
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = config;
    this._ultimoStatoForm = "";
    this._render();
  }

  connectedCallback() {
    this._connected = true;
    caricaHaForm()
      .then(() => customElements.whenDefined("ha-form"))
      .then(() => { if (this._connected) this._render(); })
      .catch(() => {});
  }

  disconnectedCallback() {
    this._connected = false;
  }

  _schema() {
    return [
      { name: "device_id", selector: { device: { filter: { integration: DOMAIN } } } },
      {
        type: "grid",
        name: "",
        schema: [
          { name: "name", selector: { text: {} } },
          { name: "icon", selector: { icon: {} } },
        ],
      },
      { name: "show_bills", selector: { boolean: {} } },
    ];
  }

  _render() {
    if (!this._connected || !this._hass || !this._config || !customElements.get("ha-form")) return;
    const etichette = { device_id: "ed_device", name: "ed_name", icon: "ed_icon", show_bills: "ed_show_bills" };
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.schema = this._schemaCache;
      this._form.computeLabel = (s) => traduci(this._hass, etichette[s.name] || s.name);
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...ev.detail.value };
        for (const k of Object.keys(config)) if (config[k] === "" || config[k] == null || config[k] === false) delete config[k];
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    const predefinito = trovaUtenzeRifiuti(this._hass)[0]?.deviceId || "";
    const firma = `${lingua(this._hass)}|${predefinito}|${JSON.stringify(this._config)}`;
    if (firma !== this._ultimoStatoForm) {
      this._ultimoStatoForm = firma;
      this._form.data = { device_id: predefinito || undefined, show_bills: false, ...this._config };
    }
  }
}

const registraElementi = () => {
  const registro = window.customElements;
  if (!registro.get(CARD_TYPE)) registro.define(CARD_TYPE, AcegasRifiutiCard);
  if (!registro.get(EDITOR_TYPE)) registro.define(EDITOR_TYPE, AcegasRifiutiCardEditor);
};

if (window.customElements.get("home-assistant") || window.customElements.get("hc-main")) {
  registraElementi();
} else {
  Promise.race([
    window.customElements.whenDefined("home-assistant"),
    window.customElements.whenDefined("hc-main"),
    new Promise((resolve) => setTimeout(resolve, 30000)),
  ]).then(registraElementi);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === CARD_TYPE)) {
  const lang = (navigator.language || "en").toLowerCase().startsWith("it") ? "it" : "en";
  window.customCards.push({
    type: CARD_TYPE,
    name: STRINGS[lang].card_name,
    description: STRINGS[lang].card_description,
    preview: true,
    documentationURL: "https://github.com/fabioscarparo/HomeAssistant-AcegasApsAmga",
  });
}

console.info(`%c ACEGASAPSAMGA RIFIUTI CARD %c ${VERSION} `,
  "color:#fff;background:#4caf50;font-weight:500", "color:#4caf50;background:transparent");
