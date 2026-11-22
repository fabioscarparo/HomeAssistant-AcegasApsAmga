/*
 * AcegasApsAmga electricity card (Luce / ELECTRIC).
 *
 * Served by the integration (lovelace_card.py), no resource to add by hand.
 *
 * Displays daily electricity consumption for the latest reading period,
 * the previous period, and optionally (show_bills: true) any unpaid bill.
 * Selecting a calendar year drives the F1/F2/F3 breakdown bar, the stacked
 * period chart (or single series for mono-band contracts), and the annual
 * summary.
 *
 * All data comes from the integration's sensor attributes. Plain web component
 * in one file, zero dependencies.
 */

const CARD_TYPE = "acegasapsamga-luce-card";
const EDITOR_TYPE = "acegasapsamga-luce-card-editor";
const VERSION = "0.4.0-beta.4";
const DOMAIN = "acegasapsamga";
const MAX_DECIMALI = 3;
const DAY_MS = 24 * 3600000;
const URL_CONFIGURA = "/_my_redirect/config_flow_start?domain=acegasapsamga";
const STATI_DA_PAGARE = ["unpaid", "expired", "paid_partial"];
const FASCE = ["F1", "F2", "F3"];

const STRINGS = {
  it: {
    card_name: "AcegasApsAmga · Luce (Fasce F1/F2/F3)",
    card_description: "Consumi elettrici giornalieri, ripartizione F1/F2/F3 e grafico annuale per fascia.",
    electricity: "Luce",
    meter_line: "Contatore {value} · letto il {date}",
    waiting: "In attesa di due letture reali",
    per_day: "kWh al giorno",
    period_line: "{from} - {to} · {value} in {days} giorni",
    previous_period: "Periodo precedente",
    bill_due: "Bolletta da pagare",
    bills_due: "{count} bollette da pagare",
    bill_overdue: "Bolletta scaduta",
    bills_overdue: "{count} bollette scadute",
    due_by: "Entro il {date}",
    direct_debit_on: "Addebito il {date}",
    overdue_since: "Scadeva il {date}",
    daily_average: "Media",
    consumption: "Totale",
    days: "Giorni",
    in_year: "Nel {year}",
    average_year: "Media {year}",
    bills_year: "Bollette {year}",
    per_day_short: "{value}/giorno",
    unit_per_day: "kWh/giorno",
    previous: "Anno precedente",
    next: "Anno successivo",
    no_data: "Nessuna lettura in quest'anno.",
    empty_title: "Ancora nessun consumo luce",
    empty_text: "Per calcolare i consumi elettrici servono almeno due letture reali del contatore.",
    not_configured_title: "Nessun contratto luce",
    not_configured_text: "Configura un contratto luce nell'integrazione AcegasApsAmga per usare questa card.",
    not_configured_sub: "Non configurata",
    device_not_found_title: "Contatore luce non trovato",
    device_not_found_text: "Il contatore luce selezionato non è più disponibile. Scegline un altro dalle impostazioni.",
    device_not_found_sub: "Dispositivo non disponibile",
    ask_admin: "Chiedi a un amministratore di farlo.",
    configure: "Configura",
    chart: "Consumo elettrico giornaliero per fascia nel {year}",
    ed_device: "Contatore luce",
    ed_name: "Nome",
    ed_icon: "Icona",
    ed_decimals: "Cifre decimali",
    ed_decimals_helper: "Da 0 a 3. Se vuoto dipende dal valore.",
    ed_show_bills: "Mostra riepilogo bollette nella card",
  },
  en: {
    card_name: "AcegasApsAmga · Electricity (F1/F2/F3)",
    card_description: "Daily electricity usage, F1/F2/F3 split and stacked annual chart.",
    electricity: "Electricity",
    meter_line: "Meter {value} · read on {date}",
    waiting: "Waiting for two real readings",
    per_day: "kWh a day",
    period_line: "{from} - {to} · {value} in {days} days",
    previous_period: "Previous period",
    bill_due: "Bill to pay",
    bills_due: "{count} bills to pay",
    bill_overdue: "Bill overdue",
    bills_overdue: "{count} bills overdue",
    due_by: "Due by {date}",
    direct_debit_on: "Direct debit on {date}",
    overdue_since: "Was due on {date}",
    daily_average: "Average",
    consumption: "Total",
    days: "Days",
    in_year: "In {year}",
    average_year: "{year} average",
    bills_year: "{year} bills",
    per_day_short: "{value}/day",
    unit_per_day: "kWh/day",
    previous: "Previous year",
    next: "Next year",
    no_data: "No readings in this year.",
    empty_title: "No electricity consumption yet",
    empty_text: "Electricity consumption needs at least two real meter readings.",
    not_configured_title: "No electricity contract",
    not_configured_text: "Configure an electricity contract in the AcegasApsAmga integration to use this card.",
    not_configured_sub: "Not configured",
    device_not_found_title: "Electricity meter not found",
    device_not_found_text: "The selected electricity meter is no longer available. Pick another in card settings.",
    device_not_found_sub: "Device unavailable",
    ask_admin: "Ask an administrator to do it.",
    configure: "Set up",
    chart: "Daily electricity consumption by band in {year}",
    ed_device: "Electricity meter",
    ed_name: "Name",
    ed_icon: "Icon",
    ed_decimals: "Decimal places",
    ed_decimals_helper: "From 0 to 3. When empty it depends on the value.",
    ed_show_bills: "Show bill summary in card",
  },
};

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

// --- Bounded Intl caches ---------------------------------------------------------

const _dtfCache = new Map();
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

const dateFormatter = (lang, tz, opzioni) => {
  const chiave = `${lang}|${tz}|${opzioni.day || ""}|${opzioni.month || ""}|${opzioni.year || ""}`;
  let df = _dfCache.get(chiave);
  if (!df) {
    if (_dfCache.size >= 64) _dfCache.clear();
    df = new Intl.DateTimeFormat(lang, { timeZone: tz, ...opzioni });
    _dfCache.set(chiave, df);
  }
  return df;
};

// --- Civil dates in Home Assistant's time zone -----------------------------------

const partiNelFuso = (date, tz) => {
  let dtf = _dtfCache.get(tz);
  if (!dtf) {
    dtf = new Intl.DateTimeFormat("en-US", {
      timeZone: tz, hourCycle: "h23", year: "numeric", month: "numeric", day: "numeric",
      hour: "numeric", minute: "numeric", second: "numeric",
    });
    _dtfCache.set(tz, dtf);
  }
  const p = {};
  for (const { type, value } of dtf.formatToParts(date)) p[type] = Number(value);
  return { y: p.year, m: p.month - 1, d: p.day, h: p.hour % 24, min: p.minute, s: p.second };
};

const offsetMs = (date, tz) => {
  const p = partiNelFuso(date, tz);
  return Date.UTC(p.y, p.m, p.d, p.h, p.min, p.s) - Math.floor(date.getTime() / 1000) * 1000;
};

const mezzanotte = (c, tz) => {
  const guess = Date.UTC(c.y, c.m, c.d);
  const t = guess - offsetMs(new Date(guess), tz);
  return new Date(guess - offsetMs(new Date(t), tz));
};

const addGiorni = (c, n) => {
  const d = new Date(Date.UTC(c.y, c.m, c.d + n));
  return { y: d.getUTCFullYear(), m: d.getUTCMonth(), d: d.getUTCDate() };
};

const daIso = (s) => {
  const [y, m, d] = String(s).split("-").map(Number);
  return { y, m: m - 1, d };
};

const oggiIso = (tz) => {
  const p = partiNelFuso(new Date(), tz);
  return `${p.y}-${String(p.m + 1).padStart(2, "0")}-${String(p.d).padStart(2, "0")}`;
};

// --- Colours and axis ------------------------------------------------------------

const parseColore = (str, riserva = [72, 143, 194]) => {
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

const _lin = (c) => ((c /= 255) <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const _gam = (c) => 255 * (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);
const _f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
const _fi = (t) => (t > 0.206893 ? t ** 3 : (t - 16 / 116) / 7.787);

const rgbToLab = ([r, g, b]) => {
  [r, g, b] = [_lin(r), _lin(g), _lin(b)];
  const x = _f((0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047);
  const y = _f(0.2126 * r + 0.7152 * g + 0.0722 * b);
  const z = _f((0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883);
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
};

const labToRgb = ([l, a, bb]) => {
  const y = (l + 16) / 116;
  const X = 0.95047 * _fi(a / 500 + y);
  const Y = _fi(y);
  const Z = 1.08883 * _fi(y - bb / 200);
  const r = _gam(3.2406 * X - 1.5372 * Y - 0.4986 * Z);
  const g = _gam(-0.9689 * X + 1.8758 * Y + 0.0415 * Z);
  const b = _gam(0.0557 * X - 0.204 * Y + 1.057 * Z);
  return [r, g, b].map((v) => Math.round(Math.min(255, Math.max(0, v))));
};

// Shifts CIELAB lightness by 18 per band step: darker in light theme, lighter in dark theme.
const sfumatura = (rgb, indice, scuro) => {
  if (!indice) return rgb;
  const lab = rgbToLab(rgb);
  lab[0] += (scuro ? 18 : -18) * indice;
  return labToRgb(lab);
};

const rgbCss = (rgb, alpha) => (alpha === undefined ? `rgb(${rgb.join(",")})` : `rgba(${rgb.join(",")},${alpha})`);

const scalaArrotondata = (max, passi = 4) => {
  if (max <= 0) max = 1;
  const grezzo = max / passi;
  const mag = 10 ** Math.floor(Math.log10(grezzo));
  const n = grezzo / mag;
  const passo = (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * mag;
  const hi = Math.ceil(max / passo - 1e-9) * passo;
  const ticks = [];
  for (let v = 0; v <= hi + passo / 2; v += passo) ticks.push(v);
  return { max: hi, ticks };
};

// --- Discover electricity meters -------------------------------------------------

const trovaContatoriLuce = (hass) => {
  const perDispositivo = new Map();
  for (const e of Object.values(hass?.entities || {})) {
    if (e.platform !== DOMAIN || !e.device_id || !e.translation_key) continue;
    if (!perDispositivo.has(e.device_id)) perDispositivo.set(e.device_id, {});
    perDispositivo.get(e.device_id)[e.translation_key] = e.entity_id;
  }
  const risultato = [];
  for (const [deviceId, entita] of perDispositivo) {
    if (!entita.lettura) continue;
    const stato = hass.states?.[entita.lettura];
    const servizio = stato?.attributes?.servizio;
    const dc = stato?.attributes?.device_class;
    if (servizio && servizio !== "ELECTRIC") continue;
    if (!servizio && dc !== "energy") continue;
    const device = hass.devices?.[deviceId];
    risultato.push({ deviceId, entita, nome: device?.name_by_user || device?.name || deviceId });
  }
  return risultato.sort((a, b) => a.nome.localeCompare(b.nome));
};

const valido = (stato) => !!stato && !["unavailable", "unknown", ""].includes(stato.state);
const SENSORI_MOSTRATI = ["lettura", "consumo_periodo", "bolletta", "da_pagare", "scadenza_bolletta"];

// --- Card ------------------------------------------------------------------------

class AcegasLuceCard extends HTMLElement {
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
    this._anno = null;
    this._larghezza = 0;
    this._hover = null;
    this._firma = "";
    this._chiudiEsterno = null;
  }

  setConfig(config) {
    const decimali = config.decimals;
    if (decimali !== undefined && decimali !== null
      && !(Number.isInteger(decimali) && decimali >= 0 && decimali <= MAX_DECIMALI)) {
      throw new Error(`decimals: 0-${MAX_DECIMALI}`);
    }
    if (config.device_id !== this._config.device_id) this._anno = null;
    this._config = { ...config };
    this._firma = "";
    this._render();
  }

  set hass(hass) {
    if (this._contatoriDa !== hass.entities) {
      this._contatori = trovaContatoriLuce(hass);
      this._contatoriDa = hass.entities;
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

  get _tz() {
    return this._hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  }

  get _contatore() {
    const contatori = this._contatori || [];
    if (this._config.device_id) {
      return contatori.find((c) => c.deviceId === this._config.device_id) || null;
    }
    return contatori[0] || null;
  }

  _stato(chiave) {
    const id = this._contatore?.entita[chiave];
    return id ? this._hass?.states[id] : undefined;
  }

  _firmaVista() {
    const h = this._hass;
    const stati = SENSORI_MOSTRATI.map((k) => {
      const s = this._stato(k);
      return s ? `${s.state}@${s.last_updated}` : "";
    });
    return [
      this._contatore?.deviceId,
      this._config.device_id,
      !!this._config.show_bills,
      h.themes?.theme,
      h.themes?.darkMode,
      h.locale?.language || h.language,
      h.locale?.number_format,
      h.config?.time_zone,
      (h.config?.components || []).includes(DOMAIN),
      h.user?.is_admin,
      ...stati,
    ].join("|");
  }

  _periodi() {
    const tz = this._tz;
    const grezzi = this._stato("consumo_periodo")?.attributes.periodi || [];
    return grezzi
      .filter((p) => p.dal && p.al && p.giorni > 0)
      .map((p) => ({
        dal: p.dal,
        al: p.al,
        giorni: p.giorni,
        consumo: Number(p.consumo) || 0,
        media: (Number(p.consumo) || 0) / p.giorni,
        fasce: p.fasce || null,
        inizio: mezzanotte(daIso(p.dal), tz).getTime(),
        fine: mezzanotte(addGiorni(daIso(p.al), 1), tz).getTime(),
      }));
  }

  _inizioAnno(anno) {
    return mezzanotte({ y: anno, m: 0, d: 1 }, this._tz).getTime();
  }

  // Year totals and F1/F2/F3 band totals, apportioned by overlapping days.
  _datiAnno(periodi, anno) {
    const inizio = this._inizioAnno(anno);
    const fine = this._inizioAnno(anno + 1);
    let consumo = 0;
    let giorni = 0;
    const fasce = { F1: 0, F2: 0, F3: 0 };
    let haFasce = false;
    for (const p of periodi) {
      const dentro = Math.round((Math.min(p.fine, fine) - Math.max(p.inizio, inizio)) / DAY_MS);
      if (dentro <= 0) continue;
      const quota = dentro / p.giorni;
      consumo += p.consumo * quota;
      giorni += dentro;
      if (p.fasce) {
        const sommaF = FASCE.reduce((s, k) => s + (Number(p.fasce[k]) || 0), 0);
        if (sommaF > 0) {
          haFasce = true;
          for (const k of FASCE) fasce[k] += (Number(p.fasce[k]) || 0) * quota;
        }
      }
    }
    return giorni
      ? { consumo, giorni, media: consumo / giorni, fasce: haFasce ? fasce : null }
      : null;
  }

  _bollette() {
    return this._stato("bolletta")?.attributes.bollette || [];
  }

  _daPagare() {
    const totale = this._stato("da_pagare");
    const importo = valido(totale) ? Number(totale.state) : 0;
    if (!(importo > 0)) return null;
    const oggi = oggiIso(this._tz);
    const aperte = this._bollette().filter((b) => STATI_DA_PAGARE.includes(b.stato) && b.residuo > 0);
    const scadenzaSensore = this._stato("scadenza_bolletta");
    const scadenza = valido(scadenzaSensore)
      ? scadenzaSensore.state
      : aperte.map((b) => b.scadenza).filter(Boolean).sort()[0] || null;
    const eScaduta = (b) => b.stato === "expired" || (!!b.scadenza && b.scadenza < oggi);
    const scaduta = aperte.some(eScaduta) || (!!scadenza && scadenza < oggi);
    const tutteScadute = aperte.length > 0 ? aperte.every(eScaduta) : scaduta;
    const conFlag = aperte.filter((b) => typeof b.domiciliata === "boolean");
    const domiciliata = conFlag.length > 0
      ? conFlag.every((b) => b.domiciliata)
      : !!this._stato("bolletta")?.attributes.domiciliata;
    return { importo, scadenza, quante: Math.max(aperte.length, 1), scaduta, tutteScadute, domiciliata };
  }

  // --- Formatting & theme colours -------------------------------------------------

  get _locale() {
    const lang = this._hass?.locale?.language || this._hass?.language || "it";
    const fmt = this._hass?.locale?.number_format;
    return { comma_decimal: "en-US", decimal_comma: "de", space_comma: "fr", quote_decimal: "de-CH", system: undefined }[fmt] ?? lang;
  }

  _numero(v, cifre) {
    if (v === null || v === undefined || Number.isNaN(v)) return "-";
    const a = Math.abs(v);
    const d = cifre ?? this._config.decimals ?? (a >= 100 ? 0 : a >= 10 ? 1 : 2);
    return numberFormatter(this._locale, {
      minimumFractionDigits: d, maximumFractionDigits: d,
      useGrouping: this._hass?.locale?.number_format !== "none",
    }).format(v);
  }

  _percentuale(v, tot) {
    if (!tot) return "-";
    return numberFormatter(this._locale, {
      style: "percent", maximumFractionDigits: 0, useGrouping: false,
    }).format(v / tot);
  }

  _kwh(v) {
    const intero = Number.isInteger(v) && this._config.decimals == null;
    return `${this._numero(v, intero ? 0 : undefined)} kWh`;
  }

  _euro(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "-";
    return numberFormatter(this._locale, {
      style: "currency", currency: "EUR", useGrouping: this._hass?.locale?.number_format !== "none",
    }).format(v);
  }

  _alGiorno(v) {
    return traduci(this._hass, "per_day_short", { value: `${this._numero(v)} kWh` });
  }

  _data(date, opzioni) {
    const lang = this._hass?.locale?.language || this._hass?.language || "it";
    return dateFormatter(lang, this._tz, opzioni).format(date);
  }

  _giorno(iso, opzioni = { day: "numeric", month: "short" }) {
    return this._data(mezzanotte(daIso(iso), this._tz), opzioni);
  }

  _colori() {
    const cs = getComputedStyle(this);
    const scuro = !!this._hass?.themes?.darkMode;
    const base = parseColore(cs.getPropertyValue("--energy-grid-consumption-color"), [72, 143, 194]);
    return {
      totale: base,
      F1: sfumatura(base, 0, scuro),
      F2: sfumatura(base, 1, scuro),
      F3: sfumatura(base, 2, scuro),
    };
  }

  // --- Rendering ------------------------------------------------------------------

  _render() {
    if (!this._hass) return;
    if (!this._contatore) {
      this._renderVuota(this._config.device_id ? "device_not_found" : "not_configured");
      return;
    }
    const periodi = this._periodi();
    if (!periodi.length) {
      this._renderVuota("empty");
      return;
    }
    if (this._modo !== "card") this._struttura();

    const primoAnno = daIso(periodi[0].dal).y;
    const ultimoAnno = daIso(periodi[periodi.length - 1].al).y;
    if (this._anno === null || this._anno < primoAnno || this._anno > ultimoAnno) this._anno = ultimoAnno;

    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const colori = this._colori();
    $("ha-card").style.setProperty("--acegas-accent", rgbCss(colori.totale));

    this._renderIntestazione();
    this._renderProtagonista(periodi);
    this._renderBolletta();

    const prev = $('[data-azione="prev"]');
    const next = $('[data-azione="next"]');
    prev.toggleAttribute("disabled", this._anno <= primoAnno);
    next.toggleAttribute("disabled", this._anno >= ultimoAnno);
    prev.setAttribute("label", t("previous"));
    next.setAttribute("label", t("next"));
    $(".period").textContent = String(this._anno);

    const datiAnno = this._datiAnno(periodi, this._anno);
    this._renderFasce(datiAnno?.fasce || null, colori);
    this._renderRiepilogo(datiAnno);
    this._larghezza = $(".chart").clientWidth || this._larghezza;
    this._renderGrafico(periodi, colori);
  }

  _renderIntestazione() {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const icona = this._config.icon || "mdi:lightning-bolt";
    if ($(".icon ha-icon").getAttribute("icon") !== icona) $(".icon ha-icon").setAttribute("icon", icona);
    $(".primary").textContent = this._config.name || t("electricity");
    const lettura = this._stato("lettura");
    const potenza = lettura?.attributes?.potenza ? ` · ${lettura.attributes.potenza}` : "";
    $(".secondary").textContent = valido(lettura) && lettura.attributes.giorno
      ? `${t("meter_line", {
        value: this._hass.formatEntityState ? this._hass.formatEntityState(lettura) : `${lettura.state} kWh`,
        date: this._giorno(lettura.attributes.giorno),
      })}${potenza}`
      : t("waiting");
  }

  _renderProtagonista(periodi) {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const ultimo = periodi[periodi.length - 1];
    const prima = periodi[periodi.length - 2];
    $(".hero-value").textContent = this._numero(ultimo.media);
    $(".hero-unit").textContent = t("per_day");
    $(".hero-sub").textContent = t("period_line", {
      from: this._giorno(ultimo.dal),
      to: this._giorno(ultimo.al),
      value: this._kwh(ultimo.consumo),
      days: String(ultimo.giorni),
    });

    const fatto = $('[data-fatto="prima"]');
    fatto.hidden = !prima;
    if (!prima) return;
    fatto.querySelector(".fact-label").textContent = t("previous_period");
    fatto.querySelector(".fact-value").textContent = this._alGiorno(prima.media);
    fatto.querySelector(".fact-sub span").textContent = `${this._giorno(prima.dal)} - ${this._giorno(prima.al)}`;
  }

  // Renders the proportional F1/F2/F3 split bar and per-band annual totals.
  _renderFasce(fasce, colori) {
    const blocco = this.shadowRoot.querySelector(".fasce");
    if (!fasce) {
      blocco.hidden = true;
      return;
    }
    const valori = FASCE.map((k) => Number(fasce[k]) || 0);
    const sommaTot = valori.reduce((a, b) => a + b, 0);
    if (!(sommaTot > 0)) {
      blocco.hidden = true;
      return;
    }
    blocco.hidden = false;
    const split = blocco.querySelector(".split");
    split.setAttribute(
      "aria-label",
      FASCE.map((k, i) => `${k} ${this._percentuale(valori[i], sommaTot)}`).join(", ")
    );
    split.innerHTML = FASCE.map((k, i) => (valori[i] > 0
      ? `<span style="flex-grow:${valori[i]};background:${rgbCss(colori[k])}"></span>`
      : "")).join("");

    blocco.querySelector(".legend").innerHTML = FASCE.map((k, i) => `
      <div class="legend-item">
        <div class="legend-name">
          <span class="dot" style="background:${rgbCss(colori[k])}"></span>${k}
          <span class="legend-pct">${escapeHtml(this._percentuale(valori[i], sommaTot))}</span>
        </div>
        <div class="legend-kwh">${escapeHtml(this._numero(valori[i]))} kWh</div>
      </div>`).join("");
  }

  _renderBolletta() {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const fatto = $('[data-fatto="bolletta"]');
    const conto = this._config.show_bills ? this._daPagare() : null;
    fatto.hidden = !conto;
    $(".facts").hidden = fatto.hidden && $('[data-fatto="prima"]').hidden;
    if (!conto) return;
    fatto.classList.toggle("scaduta", conto.scaduta);
    fatto.querySelector(".fact-label").textContent = conto.quante > 1
      ? conto.tutteScadute
        ? t("bills_overdue", { count: String(conto.quante) })
        : t("bills_due", { count: String(conto.quante) })
      : conto.scaduta ? t("bill_overdue") : t("bill_due");
    fatto.querySelector(".fact-value").textContent = this._euro(conto.importo);
    const data = conto.scadenza ? this._giorno(conto.scadenza) : null;
    fatto.querySelector(".fact-sub span").textContent = !data
      ? ""
      : conto.scaduta
        ? t("overdue_since", { date: data })
        : conto.domiciliata ? t("direct_debit_on", { date: data }) : t("due_by", { date: data });
  }

  _renderRiepilogo(dati) {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const anno = this._anno;
    const imposta = (chiave, etichetta, valore) => {
      const el = $(`[data-stat="${chiave}"]`);
      el.querySelector(".stat-label").textContent = etichetta;
      el.querySelector(".stat-value").textContent = valore;
    };
    imposta("anno", t("in_year", { year: anno }), dati ? this._kwh(Math.round(dati.consumo * 10) / 10) : "-");
    imposta("media", t("average_year", { year: anno }), dati ? this._alGiorno(dati.media) : "-");

    const conBollette = !!this._config.show_bills && !!this._contatore?.entita.bolletta;
    $(".stats").classList.toggle("tre", conBollette);
    $('[data-stat="bollette"]').hidden = !conBollette;
    if (conBollette) {
      const dellAnno = this._bollette().filter(
        (b) => String(b.emissione).startsWith(`${anno}-`) && b.stato !== "reversed"
      );
      const totale = dellAnno.reduce((s, b) => {
        const importo = Number(b.importo_servizio ?? b.importo) || 0;
        return s + (b.stato === "credit" ? -Math.abs(importo) : importo);
      }, 0);
      imposta("bollette", t("bills_year", { year: anno }), dellAnno.length ? this._euro(totale) : "-");
    }
  }

  _renderVuota(chiave) {
    this._ro?.disconnect();
    this._staccaChiusuraEsterna();
    const lettura = this._stato("lettura");
    const firma = [
      "vuota",
      chiave,
      lingua(this._hass),
      this._hass.locale?.number_format || "",
      this._hass.themes?.theme || "",
      !!this._hass.themes?.darkMode,
      this._hass.user?.is_admin,
      this._contatore?.deviceId || "",
      this._config.name || "",
      this._config.icon || "",
      lettura ? `${lettura.state}@${lettura.attributes?.giorno || ""}` : "",
    ].join("|");
    if (this._modo === firma) return;
    this._modo = firma;
    const t = (k, v) => traduci(this._hass, k, v);
    const admin = !!this._hass.user?.is_admin;
    const icona = this._config.icon || "mdi:lightning-bolt";
    const titoloCard = this._config.name || t("electricity");
    let accent = "var(--state-inactive-color, var(--disabled-text-color, #9e9e9e))";
    let sottotitolo = t("waiting");
    let contenuto;
    if (chiave === "not_configured") {
      sottotitolo = t("not_configured_sub");
      contenuto = `<ha-alert alert-type="info" title="${escapeHtml(t("not_configured_title"))}">
        ${escapeHtml(t("not_configured_text"))}${admin ? "" : ` ${escapeHtml(t("ask_admin"))}`}
        ${admin ? `<ha-button slot="action" data-percorso="${escapeHtml(URL_CONFIGURA)}">${escapeHtml(t("configure"))}</ha-button>` : ""}
      </ha-alert>`;
    } else if (chiave === "device_not_found") {
      accent = "var(--warning-color, #ffa600)";
      sottotitolo = t("device_not_found_sub");
      contenuto = `<ha-alert alert-type="warning" title="${escapeHtml(t("device_not_found_title"))}">${escapeHtml(t("device_not_found_text"))}</ha-alert>`;
    } else {
      accent = rgbCss(this._colori().totale);
      const lettura = this._stato("lettura");
      if (valido(lettura) && lettura.attributes.giorno) {
        sottotitolo = t("meter_line", {
          value: this._hass.formatEntityState ? this._hass.formatEntityState(lettura) : `${lettura.state} kWh`,
          date: this._giorno(lettura.attributes.giorno),
        });
      }
      contenuto = `<ha-alert alert-type="info" title="${escapeHtml(t("empty_title"))}">${escapeHtml(t("empty_text"))}</ha-alert>`;
    }
    const headerTag = this._contatore ? 'button type="button" class="header" data-apri="lettura"' : 'div class="header static"';
    const headerEnd = this._contatore ? "</button>" : "</div>";
    this.shadowRoot.innerHTML = `<style>${STILE}</style>
      <ha-card style="--acegas-accent:${accent}">
        <article class="card">
          <${headerTag}>
            <div class="icon"><ha-icon icon="${escapeHtml(icona)}"></ha-icon></div>
            <div class="info">
              <div class="primary">${escapeHtml(titoloCard)}</div>
              <div class="secondary">${escapeHtml(sottotitolo)}</div>
            </div>
          ${headerEnd}
          <div class="content empty-content">${contenuto}</div>
        </article>
      </ha-card>`;
    this.shadowRoot.querySelectorAll("[data-percorso]").forEach((el) =>
      el.addEventListener("click", () => naviga(el.dataset.percorso)));
    this.shadowRoot.querySelectorAll("[data-apri]").forEach((el) =>
      el.addEventListener("click", () => this._moreInfo(this._contatore?.entita[el.dataset.apri])));
  }

  _struttura() {
    this._modo = "card";
    this.shadowRoot.innerHTML = `
      <style>${STILE}</style>
      <ha-card>
        <article class="card">
          <button type="button" class="header" data-apri="lettura">
            <div class="icon"><ha-icon></ha-icon></div>
            <div class="info">
              <div class="primary"></div>
              <div class="secondary"></div>
            </div>
          </button>
          <div class="content">
            <button type="button" class="hero" data-apri="media_giornaliera">
              <div class="hero-main"><span class="hero-value"></span><span class="hero-unit"></span></div>
              <div class="hero-sub"></div>
            </button>
            <div class="facts">
              <button type="button" class="fact" data-fatto="prima" data-apri="consumo_periodo" hidden>
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
            <div class="nav">
              <ha-icon-button data-azione="prev"><ha-icon icon="mdi:chevron-left"></ha-icon></ha-icon-button>
              <div class="period"></div>
              <ha-icon-button data-azione="next"><ha-icon icon="mdi:chevron-right"></ha-icon></ha-icon-button>
            </div>
            <div class="fasce" hidden>
              <div class="split" role="img"></div>
              <div class="legend"></div>
            </div>
            <div class="chart">
              <div class="svg-host"></div>
              <div id="chart-tooltip" class="tooltip" role="tooltip" hidden></div>
            </div>
            <footer class="stats">
              <div class="stat" data-stat="anno"><div class="stat-label"></div><div class="stat-value"></div></div>
              <div class="stat" data-stat="media"><div class="stat-label"></div><div class="stat-value"></div></div>
              <div class="stat" data-stat="bollette" hidden><div class="stat-label"></div><div class="stat-value"></div></div>
            </footer>
          </div>
        </article>
      </ha-card>`;

    const root = this.shadowRoot;
    const sposta = (direzione) => {
      this._anno += direzione;
      this._hover = null;
      this._render();
    };
    root.querySelector('[data-azione="prev"]').addEventListener("click", () => sposta(-1));
    root.querySelector('[data-azione="next"]').addEventListener("click", () => sposta(1));
    root.querySelectorAll("[data-apri]").forEach((el) => {
      el.addEventListener("click", () => this._moreInfo(this._contatore?.entita[el.dataset.apri]));
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

  // --- Chart ----------------------------------------------------------------------

  _renderGrafico(periodi = this._periodi(), colori = this._colori()) {
    const host = this.shadowRoot.querySelector(".svg-host");
    if (!host || this._anno === null) return;
    this._staccaChiusuraEsterna();
    const W = this._larghezza || host.clientWidth;
    if (!W) {
      host.innerHTML = "";
      return;
    }
    const t = (k, v) => traduci(this._hass, k, v);
    const tz = this._tz;
    const anno = this._anno;
    const inizioAnno = this._inizioAnno(anno);
    const fineAnno = this._inizioAnno(anno + 1);
    const f = (ms) => (ms - inizioAnno) / (fineAnno - inizioAnno);

    const voci = periodi
      .filter((p) => p.fine > inizioAnno && p.inizio < fineAnno)
      .map((p) => ({ p, f0: Math.max(0, f(p.inizio)), f1: Math.min(1, f(p.fine)) }));
    const sogliaFrazione = 4 / Math.max(10, W - 40);
    const perScala = voci.filter((v) => v.f1 - v.f0 >= sogliaFrazione);
    const scala = scalaArrotondata(Math.max(0, ...(perScala.length ? perScala : voci).map((v) => v.p.media)), 4);

    const H = 192;
    const top = 34;
    const bottom = 22;
    const cifre = scala.ticks.some((v) => v % 1) ? 1 : 0;
    const etichetteY = scala.ticks.map((v) => this._numero(v, cifre));
    const left = Math.max(24, Math.ceil(Math.max(...etichetteY.map((s) => s.length)) * 7) + 10);
    const right = 4;
    const plotW = Math.max(10, W - left - right);
    const plotH = H - top - bottom;
    const y = (v) => top + ((scala.max - v) / scala.max) * plotH;
    const x = (fr) => left + fr * plotW;

    const parti = [];
    scala.ticks.forEach((v, i) => {
      const yy = Math.round(y(v)) + 0.5;
      parti.push(`<line class="grid" x1="${left}" x2="${W - right}" y1="${yy}" y2="${yy}"/>`);
      parti.push(`<text class="ylab" x="${left - 8}" y="${yy + 4}">${escapeHtml(etichetteY[i])}</text>`);
    });
    parti.push(`<text class="unita" x="0" y="12">${escapeHtml(t("unit_per_day"))}</text>`);
    parti.push(`<rect class="hover-band" x="0" y="${top}" width="0" height="${plotH}" />`);

    // Draws one stacked bar segment with translucent fill, inset stroke and top rounding on the cap.
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

    for (const v of voci) {
      if ((v.f1 - v.f0) * plotW < 4) continue;
      const margine = Math.min(0.04 * (v.f1 - v.f0) * plotW, 2);
      const x0 = x(v.f0) + margine;
      const w = Math.max(1, x(v.f1) - margine - x0);
      const fasce = v.p.fasce;
      const sommaFasce = fasce ? FASCE.reduce((s, k) => s + (Number(fasce[k]) || 0), 0) : 0;
      if (fasce && sommaFasce > 0) {
        const presenti = FASCE.filter((k) => (Number(fasce[k]) || 0) > 0);
        let acc = 0;
        presenti.forEach((k, j) => {
          const valGiorno = ((Number(fasce[k]) || 0) / sommaFasce) * v.p.media;
          parti.push(segmento(x0, w, y(acc), y(acc + valGiorno), colori[k], j === presenti.length - 1));
          acc += valGiorno;
        });
      } else if (v.p.media > 0) {
        parti.push(segmento(x0, w, y(0), y(v.p.media), colori.totale, true));
      }
    }

    const stretta = W < 360;
    for (let m = 0; m < 12; m++) {
      const inizio = mezzanotte({ y: anno, m, d: 1 }, tz).getTime();
      const fine = m === 11 ? fineAnno : mezzanotte({ y: anno, m: m + 1, d: 1 }, tz).getTime();
      const testo = this._data(new Date(inizio), { month: stretta ? "narrow" : "short" });
      parti.push(`<text class="xlab" x="${x(f((inizio + fine) / 2))}" y="${H - 3}">${escapeHtml(testo)}</text>`);
    }

    host.innerHTML = `
      <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" tabindex="0" aria-label="${escapeHtml(t("chart", { year: anno }))}">
        ${parti.join("")}
        <rect class="hit" x="${left}" y="${top}" width="${plotW}" height="${plotH + 10}"/>
      </svg>
      ${voci.length ? "" : `<div class="no-data">${escapeHtml(t("no_data"))}</div>`}`;

    const svg = host.querySelector("svg");
    const banda = svg.querySelector(".hover-band");
    const tip = this.shadowRoot.querySelector(".tooltip");
    const indice = (ev) => {
      const r = svg.getBoundingClientRect();
      const fr = (ev.clientX - r.left - left) / plotW;
      const i = voci.findIndex((v) => fr >= v.f0 && fr < v.f1);
      return i >= 0 ? i : null;
    };
    const nascondi = () => {
      this._hover = null;
      banda.setAttribute("width", 0);
      tip.hidden = true;
      svg.removeAttribute("aria-describedby");
      this._staccaChiusuraEsterna();
    };
    const mostra = (i) => {
      if (i === null || !voci[i]) return nascondi();
      const v = voci[i];
      this._hover = i;
      banda.setAttribute("x", x(v.f0));
      banda.setAttribute("width", (v.f1 - v.f0) * plotW);
      tip.innerHTML = this._tooltip(v.p, colori);
      tip.hidden = false;
      svg.setAttribute("aria-describedby", "chart-tooltip");
      const cx = x((v.f0 + v.f1) / 2);
      const meta = ((v.f1 - v.f0) * plotW) / 2;
      const tw = tip.offsetWidth;
      const lx = cx < W / 2 ? cx + meta + 8 : cx - meta - 8 - tw;
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
      if (!voci.length) return;
      if (ev.key === "Escape") nascondi();
      else if (ev.key === "ArrowRight") {
        ev.preventDefault();
        mostra(this._hover === null ? 0 : Math.min(voci.length - 1, this._hover + 1));
      } else if (ev.key === "ArrowLeft") {
        ev.preventDefault();
        mostra(this._hover === null ? voci.length - 1 : Math.max(0, this._hover - 1));
      }
    });
    svg.addEventListener("blur", nascondi);
    if (this._hover !== null && this._hover < voci.length) mostra(this._hover);
    else nascondi();
  }

  // Lists bands in top-to-bottom stack order (F3, F2, F1), followed by totals and days.
  _tooltip(p, colori) {
    const t = (k, v) => traduci(this._hass, k, v);
    const riga = (nome, valore, rgb, extraClass = "") => `<div class="tip-row ${extraClass}">${rgb ? `<span class="tip-marker" style="background:${rgbCss(rgb)}"></span>` : ""}
      <span class="tip-name">${escapeHtml(nome)}</span><span class="tip-value">${escapeHtml(valore)}</span></div>`;
    const titolo = `${this._giorno(p.dal)} - ${this._giorno(p.al, { day: "numeric", month: "short", year: "numeric" })}`;
    const righe = [];
    if (p.fasce) {
      const presenti = [...FASCE].reverse().filter((k) => (Number(p.fasce[k]) || 0) > 0);
      for (const k of presenti) {
        righe.push(riga(k, this._kwh(Number(p.fasce[k])), colori[k]));
      }
      righe.push(riga(t("consumption"), this._kwh(p.consumo), null, "tip-total"));
      righe.push(riga(t("daily_average"), this._alGiorno(p.media)));
      righe.push(riga(t("days"), String(p.giorni)));
    } else {
      righe.push(riga(t("daily_average"), this._alGiorno(p.media), colori.totale));
      righe.push(riga(t("consumption"), this._kwh(p.consumo)));
      righe.push(riga(t("days"), String(p.giorni)));
    }
    return `<div class="tip-title">${escapeHtml(titolo)}</div>${righe.join("")}`;
  }
}

const STILE = `
  :host { display: block; }
  ha-card { height: 100%; overflow: hidden; }
  .card { display: block; }
  ha-alert { display: block; }
  [hidden] { display: none !important; }

  .header, .hero, .fact {
    appearance: none; background: none; border: 0; font: inherit; color: inherit;
    text-align: start; padding: 0; margin: 0; width: 100%; box-sizing: border-box;
  }
  .header {
    display: flex; align-items: center; gap: 10px;
    padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px) 0; cursor: pointer; outline: none;
    border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
  }
  .header.static { cursor: default; }
  .empty-content { padding-top: var(--ha-space-3, 12px); }
  .header:focus-visible, .hero:focus-visible, .fact:focus-visible, svg:focus-visible {
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
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .secondary {
    font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-normal, 400);
    line-height: 16px; letter-spacing: 0.4px; color: var(--secondary-text-color);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  .content { display: flex; flex-direction: column; gap: var(--ha-space-3, 12px); padding: var(--ha-space-4, 16px); container-type: inline-size; }
  .hero { cursor: pointer; outline: none; border-radius: var(--ha-border-radius-md, 8px); }
  .hero-main {
    display: flex; align-items: baseline; gap: 4px; flex-wrap: wrap;
    line-height: var(--ha-line-height-condensed, 1.2);
  }
  .hero-value {
    font-size: var(--ha-font-size-3xl, 28px); font-weight: var(--ha-font-weight-normal, 400);
    color: var(--primary-text-color); font-variant-numeric: tabular-nums;
  }
  .hero-unit { font-size: var(--ha-font-size-l, 16px); color: var(--secondary-text-color); }
  .hero-sub {
    margin-top: 2px; font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px;
    color: var(--secondary-text-color);
  }

  .facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px; }
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

  .nav { display: flex; align-items: center; margin: -4px -12px; }
  .nav ha-icon-button { --mdc-icon-button-size: 40px; color: var(--primary-text-color); }
  .nav ha-icon-button[disabled] { color: var(--disabled-text-color); }
  .period {
    flex: 1; text-align: center; font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500); color: var(--primary-text-color);
    font-variant-numeric: tabular-nums;
  }

  /* F1 / F2 / F3 split bar and legend */
  .fasce { display: flex; flex-direction: column; gap: 8px; }
  .split {
    display: flex; gap: 2px; height: 8px; overflow: hidden; flex: none;
    border-radius: var(--ha-border-radius-pill, 9999px);
  }
  .split span { min-width: 2px; }
  .legend { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .legend-item { min-width: 0; }
  .legend-name {
    display: flex; align-items: center; gap: 6px; font-size: var(--ha-font-size-s, 12px);
    font-weight: var(--ha-font-weight-medium, 500); line-height: 16px; color: var(--primary-text-color);
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
  .legend-pct { font-weight: var(--ha-font-weight-normal, 400); color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
  .legend-kwh {
    font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px;
    color: var(--secondary-text-color); padding-inline-start: 14px; font-variant-numeric: tabular-nums;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  .chart { position: relative; min-height: 192px; margin: 0 -4px; touch-action: pan-y; }
  svg { display: block; overflow: visible; outline: none; border-radius: var(--ha-border-radius-md, 8px); }
  svg text { font-size: var(--ha-font-size-s, 12px); fill: var(--primary-text-color); }
  svg .ylab { text-anchor: end; }
  svg .unita { fill: var(--secondary-text-color); }
  svg .xlab { text-anchor: middle; }
  svg .grid { stroke: var(--divider-color); stroke-width: 1; }
  svg .hover-band { fill: var(--secondary-text-color); opacity: 0.1; }
  svg .hit { fill: transparent; cursor: default; }
  .no-data {
    position: absolute; inset: 34px 0 22px 32px; display: flex; align-items: center; justify-content: center;
    text-align: center; color: var(--secondary-text-color); font-size: var(--ha-font-size-m, 14px);
    pointer-events: none;
  }

  .stats {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px;
    padding-top: var(--ha-space-3, 12px); border-top: 1px solid var(--divider-color);
  }
  .stats.tre { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .stat { min-width: 0; }
  .stat-label {
    font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px;
    color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .stat-value {
    margin-top: 2px; font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500);
    line-height: 20px; color: var(--primary-text-color); font-variant-numeric: tabular-nums;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
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

  @container (max-width: 280px) {
    .facts { grid-template-columns: 1fr; }
    .stats.tre { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }

  @media (prefers-reduced-motion: reduce) {
    * { transition-duration: 1ms !important; }
  }
`;

// --- Visual editor ---------------------------------------------------------------

const caricaHaForm = async () => {
  if (customElements.get("ha-form")) return;
  const helpers = await window.loadCardHelpers?.();
  const card = await helpers?.createCardElement({ type: "entities", entities: [] });
  await card?.constructor?.getConfigElement?.();
};

class AcegasLuceCardEditor extends HTMLElement {
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
      { name: "decimals", selector: { number: { min: 0, max: MAX_DECIMALI, step: 1, mode: "box" } } },
      { name: "show_bills", selector: { boolean: {} } },
    ];
  }

  _render() {
    if (!this._connected || !this._hass || !this._config || !customElements.get("ha-form")) return;
    const etichette = { device_id: "ed_device", name: "ed_name", icon: "ed_icon", decimals: "ed_decimals", show_bills: "ed_show_bills" };
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.schema = this._schemaCache;
      this._form.computeLabel = (s) => traduci(this._hass, etichette[s.name] || s.name);
      this._form.computeHelper = (s) => (s.name === "decimals" ? traduci(this._hass, "ed_decimals_helper") : undefined);
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...ev.detail.value };
        for (const k of Object.keys(config)) if (config[k] === "" || config[k] == null || config[k] === false) delete config[k];
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    const predefinito = trovaContatoriLuce(this._hass)[0]?.deviceId || "";
    const firma = `${lingua(this._hass)}|${predefinito}|${JSON.stringify(this._config)}`;
    if (firma !== this._ultimoStatoForm) {
      this._ultimoStatoForm = firma;
      this._form.data = { device_id: predefinito || undefined, show_bills: false, ...this._config };
    }
  }
}

// --- Registration ----------------------------------------------------------------

const registraElementi = () => {
  const registro = window.customElements;
  if (!registro.get(CARD_TYPE)) registro.define(CARD_TYPE, AcegasLuceCard);
  if (!registro.get(EDITOR_TYPE)) registro.define(EDITOR_TYPE, AcegasLuceCardEditor);
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

console.info(`%c ACEGASAPSAMGA LUCE CARD %c ${VERSION} `,
  "color:#fff;background:#488fc2;font-weight:500", "color:#488fc2;background:transparent");
