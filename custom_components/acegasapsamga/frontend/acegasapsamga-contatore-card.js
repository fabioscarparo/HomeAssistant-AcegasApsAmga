/*
 * AcegasApsAmga meter card (Water, Gas, District Heating).
 *
 * Served by the integration (lovelace_card.py), no resource to add by hand.
 *
 * Built around periodic meter readings (about once a month). The main number
 * is the daily consumption of the last period between two real readings. Under
 * it: the previous period, any open or upcoming self-reading window, and
 * optionally (show_bills: true) any unpaid bill. The chart shows the periods
 * of one calendar year, each bar as wide as its days and as high as its daily
 * average; below it, the year's total and daily average.
 *
 * Everything comes from the sensors' attributes, computed by the integration.
 * A plain web component in one file, no dependencies.
 */

const CARD_TYPE = "acegasapsamga-contatore-card";
const EDITOR_TYPE = "acegasapsamga-contatore-card-editor";
const VERSION = "0.4.0-beta.3";
const DOMAIN = "acegasapsamga";
const MAX_DECIMALI = 3;
const DAY_MS = 24 * 3600000;
const URL_CONFIGURA = "/_my_redirect/config_flow_start?domain=acegasapsamga";
// Bill statuses that leave something to pay, as the integration names them.
const STATI_DA_PAGARE = ["unpaid", "expired", "paid_partial"];

const STRINGS = {
  it: {
    card_name: "AcegasApsAmga · Contatore (Acqua / Gas / TLR)",
    card_description: "Consumo giornaliero tra una lettura e l'altra, andamento annuale e finestra di autolettura.",
    water: "Acqua",
    gas: "Gas",
    heating: "Teleriscaldamento",
    meter_line: "Contatore {value} · letto il {date}",
    waiting: "In attesa di due letture reali",
    per_day_water: "litri al giorno",
    per_day_gas: "m³ al giorno",
    per_day_heating: "{unit} al giorno",
    period_line: "{from} - {to} · {value} in {days} giorni",
    previous_period: "Periodo precedente",
    self_reading: "Autolettura",
    self_reading_open: "Finestra aperta",
    self_reading_until: "Fino al {date}",
    self_reading_in: "Tra {days} giorni",
    self_reading_starts: "Dal {date}",
    bill_due: "Bolletta da pagare",
    bills_due: "{count} bollette da pagare",
    bill_overdue: "Bolletta scaduta",
    bills_overdue: "{count} bollette scadute",
    due_by: "Entro il {date}",
    direct_debit_on: "Addebito il {date}",
    overdue_since: "Scadeva il {date}",
    daily_average: "Media",
    consumption: "Consumo",
    days: "Giorni",
    in_year: "Nel {year}",
    average_year: "Media {year}",
    bills_year: "Bollette {year}",
    per_day_short: "{value}/giorno",
    unit_per_day: "{unit}/giorno",
    previous: "Anno precedente",
    next: "Anno successivo",
    no_data: "Nessuna lettura in quest'anno.",
    empty_title: "Ancora nessun consumo",
    empty_text: "Per calcolare i consumi servono almeno due letture reali del contatore. AcegasApsAmga legge il contatore circa una volta al mese.",
    not_configured_title: "Integrazione non configurata",
    not_configured_text: "Aggiungi l'integrazione AcegasApsAmga per vedere qui i consumi del tuo contatore.",
    not_configured_sub: "Non configurata",
    device_not_found_title: "Contatore non trovato",
    device_not_found_text: "Il contatore configurato per questa card non è più disponibile. Scegline un altro dalle impostazioni della card.",
    device_not_found_sub: "Dispositivo non disponibile",
    ask_admin: "Chiedi a un amministratore di farlo.",
    configure: "Configura",
    chart: "Consumo medio giornaliero per periodo di lettura nel {year}",
    ed_device: "Contatore",
    ed_name: "Nome",
    ed_icon: "Icona",
    ed_decimals: "Cifre decimali",
    ed_decimals_helper: "Da 0 a 3. Se vuoto dipende dal valore.",
    ed_show_bills: "Mostra riepilogo bollette nella card",
  },
  en: {
    card_name: "AcegasApsAmga · Meter (Water / Gas / Heating)",
    card_description: "Daily consumption between readings, annual chart and self-reading window.",
    water: "Water",
    gas: "Gas",
    heating: "District heating",
    meter_line: "Meter {value} · read on {date}",
    waiting: "Waiting for two real readings",
    per_day_water: "litres a day",
    per_day_gas: "m³ a day",
    per_day_heating: "{unit} a day",
    period_line: "{from} - {to} · {value} in {days} days",
    previous_period: "Previous period",
    self_reading: "Self-reading",
    self_reading_open: "Window open",
    self_reading_until: "Until {date}",
    self_reading_in: "In {days} days",
    self_reading_starts: "From {date}",
    bill_due: "Bill to pay",
    bills_due: "{count} bills to pay",
    bill_overdue: "Bill overdue",
    bills_overdue: "{count} bills overdue",
    due_by: "Due by {date}",
    direct_debit_on: "Direct debit on {date}",
    overdue_since: "Was due on {date}",
    daily_average: "Average",
    consumption: "Consumption",
    days: "Days",
    in_year: "In {year}",
    average_year: "{year} average",
    bills_year: "{year} bills",
    per_day_short: "{value}/day",
    unit_per_day: "{unit}/day",
    previous: "Previous year",
    next: "Next year",
    no_data: "No readings in this year.",
    empty_title: "No consumption yet",
    empty_text: "Consumption needs at least two real meter readings. AcegasApsAmga reads the meter about once a month.",
    not_configured_title: "Integration not set up",
    not_configured_text: "Add the AcegasApsAmga integration to see your meter's consumption here.",
    not_configured_sub: "Not configured",
    device_not_found_title: "Meter not found",
    device_not_found_text: "The meter configured for this card is no longer available. Choose another one in the card settings.",
    device_not_found_sub: "Device unavailable",
    ask_admin: "Ask an administrator to do it.",
    configure: "Set up",
    chart: "Average daily consumption by reading period in {year}",
    ed_device: "Meter",
    ed_name: "Name",
    ed_icon: "Icon",
    ed_decimals: "Decimal places",
    ed_decimals_helper: "From 0 to 3. When empty it depends on the value.",
    ed_show_bills: "Show bill summary in card",
  },
};

const lingua = (hass) => {
  const lang = hass?.locale?.language || hass?.language || "en";
  return lang.toLowerCase().startsWith("it") ? "it" : "en";
};

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

// --- Calendar days in the server's time zone -----------------------------------

const _dtfCache = new Map();
const _nfCache = new Map();
const _dfCache = new Map();

const numberFormatter = (locale, opzioni) => {
  const chiave = `${locale || ""}|${opzioni.style || "decimal"}|${opzioni.currency || ""}|${opzioni.minimumFractionDigits ?? ""}|${opzioni.useGrouping}`;
  let nf = _nfCache.get(chiave);
  if (!nf) {
    nf = new Intl.NumberFormat(locale, opzioni);
    _nfCache.set(chiave, nf);
  }
  return nf;
};

const dateFormatter = (lang, tz, opzioni) => {
  const chiave = `${lang}|${tz}|${opzioni.day || ""}|${opzioni.month || ""}|${opzioni.year || ""}`;
  let df = _dfCache.get(chiave);
  if (!df) {
    df = new Intl.DateTimeFormat(lang, { timeZone: tz, ...opzioni });
    _dfCache.set(chiave, df);
  }
  return df;
};

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

// --- Colors and axis -------------------------------------------------------------

const parseColore = (str, riserva) => {
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

// --- The meters of the integration ----------------------------------------------

const trovaContatori = (hass) => {
  const perDispositivo = new Map();
  for (const e of Object.values(hass?.entities || {})) {
    if (e.platform !== DOMAIN || !e.device_id || !e.translation_key) continue;
    if (!perDispositivo.has(e.device_id)) perDispositivo.set(e.device_id, {});
    perDispositivo.get(e.device_id)[e.translation_key] = e.entity_id;
  }
  const contatori = [];
  for (const [deviceId, entita] of perDispositivo) {
    if (!entita.lettura) continue;
    const device = hass.devices?.[deviceId];
    contatori.push({ deviceId, entita, nome: device?.name_by_user || device?.name || deviceId });
  }
  return contatori.sort((a, b) => a.nome.localeCompare(b.nome));
};

const valido = (stato) => !!stato && !["unavailable", "unknown", ""].includes(stato.state);

// Sensors whose changes are shown by the card.
const SENSORI_MOSTRATI = ["lettura", "consumo_periodo", "autolettura", "bolletta", "da_pagare", "scadenza_bolletta"];

// --- Card ------------------------------------------------------------------------

class AcegasContatoreCard extends HTMLElement {
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
      this._contatori = trovaContatori(hass);
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

  // --- Data -----------------------------------------------------------------------

  get _tz() {
    return this._hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  }

  get _contatore() {
    const contatori = this._contatori || [];
    if (this._config.device_id) {
      return contatori.find((c) => c.deviceId === this._config.device_id) || null;
    }
    // Prefer water, gas or heating meters when no device_id is pinned.
    const nonLuce = contatori.find((c) => {
      const s = this._hass?.states?.[c.entita.lettura];
      return s?.attributes?.servizio !== "ELECTRIC";
    });
    return nonLuce || contatori[0] || null;
  }

  _stato(chiave) {
    const id = this._contatore?.entita[chiave];
    return id ? this._hass?.states[id] : undefined;
  }

  get _tipoServizio() {
    const attrs = this._stato("lettura")?.attributes || {};
    if (attrs.servizio === "HEATING") return "heating";
    if (attrs.servizio === "GAS" || attrs.device_class === "gas") return "gas";
    if (attrs.servizio === "ELECTRIC" || attrs.device_class === "energy") return "heating";
    return "water";
  }

  get _gas() {
    return this._tipoServizio === "gas";
  }

  get _heating() {
    return this._tipoServizio === "heating";
  }

  get _unitaConsumo() {
    const u = this._stato("lettura")?.attributes?.unit_of_measurement;
    if (u) return u;
    return this._heating ? "kWh" : "m³";
  }

  // Values per day in litres for water, native units for gas and heating.
  get _fattoreGiorno() {
    return this._tipoServizio === "water" ? 1000 : 1;
  }

  get _unitaGiorno() {
    return this._tipoServizio === "water" ? "L" : this._unitaConsumo;
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
        consumo: p.consumo,
        media: (p.consumo / p.giorni) * this._fattoreGiorno,
        inizio: mezzanotte(daIso(p.dal), tz).getTime(),
        fine: mezzanotte(addGiorni(daIso(p.al), 1), tz).getTime(),
      }));
  }

  _inizioAnno(anno) {
    return mezzanotte({ y: anno, m: 0, d: 1 }, this._tz).getTime();
  }

  _datiAnno(periodi, anno) {
    const inizio = this._inizioAnno(anno);
    const fine = this._inizioAnno(anno + 1);
    let consumo = 0;
    let giorni = 0;
    for (const p of periodi) {
      const dentro = Math.round((Math.min(p.fine, fine) - Math.max(p.inizio, inizio)) / DAY_MS);
      if (dentro <= 0) continue;
      consumo += (p.consumo * dentro) / p.giorni;
      giorni += dentro;
    }
    return giorni ? { consumo, giorni, media: (consumo / giorni) * this._fattoreGiorno } : null;
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

  _autolettura() {
    const s = this._stato("autolettura");
    if (!valido(s)) return null;
    const aperta = s.attributes.aperta === true;
    const giorni = s.attributes.giorni_mancanti;
    if (!aperta && !(typeof giorni === "number" && giorni <= 14)) return null;
    return { inizio: s.state, fine: s.attributes.fine, aperta, giorni };
  }

  // --- Formatting -----------------------------------------------------------------

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

  _quantita(v) {
    const intero = Number.isInteger(v) && this._config.decimals == null;
    return `${this._numero(v, intero ? 0 : undefined)} ${this._unitaConsumo}`;
  }

  _euro(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "-";
    return numberFormatter(this._locale, {
      style: "currency", currency: "EUR", useGrouping: this._hass?.locale?.number_format !== "none",
    }).format(v);
  }

  _giornaliero(v) {
    return this._tipoServizio === "water" ? this._numero(v, 0) : this._numero(v);
  }

  _alGiorno(v) {
    return traduci(this._hass, "per_day_short", { value: `${this._giornaliero(v)} ${this._unitaGiorno}` });
  }

  _data(date, opzioni) {
    const lang = this._hass?.locale?.language || this._hass?.language || "it";
    return dateFormatter(lang, this._tz, opzioni).format(date);
  }

  _giorno(iso, opzioni = { day: "numeric", month: "short" }) {
    return this._data(mezzanotte(daIso(iso), this._tz), opzioni);
  }

  _colore() {
    const cs = getComputedStyle(this);
    if (this._gas) return parseColore(cs.getPropertyValue("--energy-gas-color"), [142, 2, 27]);
    if (this._heating) return parseColore(cs.getPropertyValue("--energy-heating-color"), [249, 115, 22]);
    return parseColore(cs.getPropertyValue("--energy-water-color"), [0, 188, 212]);
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
    $("ha-card").style.setProperty("--acegas-accent", rgbCss(this._colore()));

    this._renderIntestazione();
    this._renderProtagonista(periodi);
    this._renderAutoletturaEBolletta();

    const prev = $('[data-azione="prev"]');
    const next = $('[data-azione="next"]');
    prev.toggleAttribute("disabled", this._anno <= primoAnno);
    next.toggleAttribute("disabled", this._anno >= ultimoAnno);
    prev.setAttribute("label", t("previous"));
    next.setAttribute("label", t("next"));
    $(".period").textContent = String(this._anno);

    this._renderRiepilogo(periodi);
    this._larghezza = $(".chart").clientWidth || this._larghezza;
    this._renderGrafico(periodi);
  }

  _renderIntestazione() {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const defaultIcon = this._gas ? "mdi:fire" : this._heating ? "mdi:radiator" : "mdi:water";
    const icona = this._config.icon || defaultIcon;
    if ($(".icon ha-icon").getAttribute("icon") !== icona) $(".icon ha-icon").setAttribute("icon", icona);
    $(".primary").textContent = this._config.name || t(this._tipoServizio);
    const lettura = this._stato("lettura");
    $(".secondary").textContent = valido(lettura) && lettura.attributes.giorno
      ? t("meter_line", {
        value: this._hass.formatEntityState ? this._hass.formatEntityState(lettura) : `${lettura.state} ${this._unitaConsumo}`,
        date: this._giorno(lettura.attributes.giorno),
      })
      : t("waiting");
  }

  _renderProtagonista(periodi) {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const ultimo = periodi[periodi.length - 1];
    const prima = periodi[periodi.length - 2];
    $(".hero-value").textContent = this._giornaliero(ultimo.media);
    $(".hero-unit").textContent = this._heating
      ? t("per_day_heating", { unit: this._unitaConsumo })
      : t(this._gas ? "per_day_gas" : "per_day_water");
    $(".hero-sub").textContent = t("period_line", {
      from: this._giorno(ultimo.dal),
      to: this._giorno(ultimo.al),
      value: this._quantita(ultimo.consumo),
      days: String(ultimo.giorni),
    });

    const fatto = $('[data-fatto="prima"]');
    fatto.hidden = !prima;
    if (!prima) return;
    fatto.querySelector(".fact-label").textContent = t("previous_period");
    fatto.querySelector(".fact-value").textContent = this._alGiorno(prima.media);
    fatto.querySelector(".fact-sub span").textContent = `${this._giorno(prima.dal)} - ${this._giorno(prima.al)}`;
  }

  _renderAutoletturaEBolletta() {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);

    const fattoBolletta = $('[data-fatto="bolletta"]');
    const conto = this._config.show_bills ? this._daPagare() : null;
    fattoBolletta.hidden = !conto;
    if (conto) {
      fattoBolletta.classList.toggle("scaduta", conto.scaduta);
      fattoBolletta.querySelector(".fact-label").textContent = conto.quante > 1
        ? conto.tutteScadute
          ? t("bills_overdue", { count: String(conto.quante) })
          : t("bills_due", { count: String(conto.quante) })
        : conto.scaduta ? t("bill_overdue") : t("bill_due");
      fattoBolletta.querySelector(".fact-value").textContent = this._euro(conto.importo);
      const data = conto.scadenza ? this._giorno(conto.scadenza) : null;
      fattoBolletta.querySelector(".fact-sub span").textContent = !data
        ? ""
        : conto.scaduta
          ? t("overdue_since", { date: data })
          : conto.domiciliata ? t("direct_debit_on", { date: data }) : t("due_by", { date: data });
    }

    const fattoAuto = $('[data-fatto="autolettura"]');
    const auto = this._autolettura();
    fattoAuto.hidden = !auto;
    if (auto) {
      fattoAuto.classList.toggle("aperta", auto.aperta);
      fattoAuto.querySelector(".fact-label").textContent = t("self_reading");
      fattoAuto.querySelector(".fact-value").textContent = auto.aperta
        ? t("self_reading_open")
        : t("self_reading_in", { days: String(auto.giorni) });
      fattoAuto.querySelector(".fact-sub span").textContent = auto.aperta && auto.fine
        ? t("self_reading_until", { date: this._giorno(auto.fine) })
        : t("self_reading_starts", { date: this._giorno(auto.inizio) });
    }

    const visibili = [
      !$('[data-fatto="prima"]').hidden,
      !fattoBolletta.hidden,
      !fattoAuto.hidden,
    ].filter(Boolean).length;
    $(".facts").hidden = visibili === 0;
    $(".facts").classList.toggle("tre", visibili === 3);
  }

  _renderRiepilogo(periodi) {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const anno = this._anno;
    const dati = this._datiAnno(periodi, anno);
    const imposta = (chiave, etichetta, valore) => {
      const el = $(`[data-stat="${chiave}"]`);
      el.querySelector(".stat-label").textContent = etichetta;
      el.querySelector(".stat-value").textContent = valore;
    };
    imposta("anno", t("in_year", { year: anno }), dati ? this._quantita(Math.round(dati.consumo * 10) / 10) : "-");
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

  _alertConAzione(titolo, testo, etichetta, percorso) {
    const admin = !!this._hass.user?.is_admin;
    return `<ha-alert alert-type="info" title="${escapeHtml(titolo)}">
      ${escapeHtml(testo)}${admin ? "" : ` ${escapeHtml(traduci(this._hass, "ask_admin"))}`}
      ${admin ? `<ha-button slot="action" data-percorso="${escapeHtml(percorso)}">${escapeHtml(etichetta)}</ha-button>` : ""}
    </ha-alert>`;
  }

  _renderVuota(chiave) {
    this._ro?.disconnect();
    this._staccaChiusuraEsterna();
    const configurata = (this._hass.config?.components || []).includes(DOMAIN);
    const quale = chiave === "not_configured" && configurata ? "empty" : chiave;
    const lettura = this._stato("lettura");
    const firma = [
      "vuota",
      quale,
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
    const defaultIcon = this._contatore
      ? (this._gas ? "mdi:fire" : this._heating ? "mdi:radiator" : "mdi:water")
      : "mdi:water";
    const icona = this._config.icon || defaultIcon;
    const titoloCard = this._config.name || (this._contatore ? t(this._tipoServizio) : t("water"));
    let accent = "var(--state-inactive-color, var(--disabled-text-color, #9e9e9e))";
    let sottotitolo = t("waiting");
    let contenuto;
    if (quale === "not_configured") {
      sottotitolo = t("not_configured_sub");
      contenuto = this._alertConAzione(t("not_configured_title"), t("not_configured_text"), t("configure"), URL_CONFIGURA);
    } else if (quale === "device_not_found") {
      accent = "var(--warning-color, #ffa600)";
      sottotitolo = t("device_not_found_sub");
      contenuto = `<ha-alert alert-type="warning" title="${escapeHtml(t("device_not_found_title"))}">${escapeHtml(t("device_not_found_text"))}</ha-alert>`;
    } else {
      accent = rgbCss(this._colore());
      const lettura = this._stato("lettura");
      if (valido(lettura) && lettura.attributes.giorno) {
        sottotitolo = t("meter_line", {
          value: this._hass.formatEntityState ? this._hass.formatEntityState(lettura) : `${lettura.state} ${this._unitaConsumo}`,
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
              <button type="button" class="fact" data-fatto="autolettura" data-apri="autolettura" hidden>
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

  _renderGrafico(periodi = this._periodi()) {
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
    const colore = this._colore();
    const sogliaFrazione = 4 / Math.max(10, W - 40);
    const perScala = voci.filter((v) => v.f1 - v.f0 >= sogliaFrazione);
    const scala = scalaArrotondata(Math.max(0, ...(perScala.length ? perScala : voci).map((v) => v.p.media)), 4);

    const H = 192;
    const top = 34;
    const bottom = 22;
    const cifre = this._tipoServizio === "water" ? 0 : (scala.ticks.some((v) => v % 1) ? 1 : 0);
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
    parti.push(`<text class="unita" x="0" y="12">${escapeHtml(t("unit_per_day", { unit: this._unitaGiorno }))}</text>`);
    parti.push(`<rect class="hover-band" x="0" y="${top}" width="0" height="${plotH}" />`);

    const barra = (x0, x1, v) => {
      if (v <= 0) return "";
      const w = x1 - x0;
      const y0 = y(0);
      const y1 = y(v);
      const h = y0 - y1;
      if (h < 2 || w < 3) {
        return `<rect x="${x0}" y="${y0 - Math.max(h, 1)}" width="${Math.max(w, 1)}" height="${Math.max(h, 1)}" fill="${rgbCss(colore)}"/>`;
      }
      const i = 0.75;
      const L = x0 + i;
      const R = x1 - i;
      const T = y1 + i;
      const B = y0 - i;
      const r = Math.max(0, Math.min(4, (R - L) / 2, (B - T) / 2));
      const d = `M${L},${B}L${L},${T + r}Q${L},${T} ${L + r},${T}L${R - r},${T}Q${R},${T} ${R},${T + r}L${R},${B}Z`;
      return `<path d="${d}" fill="${rgbCss(colore, 0.5)}" stroke="${rgbCss(colore)}" stroke-width="1.5" stroke-linejoin="round"/>`;
    };
    for (const v of voci) {
      if ((v.f1 - v.f0) * plotW < 4) continue;
      const margine = Math.min(0.04 * (v.f1 - v.f0) * plotW, 2);
      parti.push(barra(x(v.f0) + margine, x(v.f1) - margine, v.p.media));
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
      tip.innerHTML = this._tooltip(v.p, colore);
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
      if (ev.key === "Escape") {
        nascondi();
      } else if (ev.key === "ArrowRight") {
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

  _tooltip(p, colore) {
    const t = (k, v) => traduci(this._hass, k, v);
    const riga = (nome, valore, puntino) => `<div class="tip-row">${puntino ? `<span class="tip-marker" style="background:${rgbCss(colore)}"></span>` : ""}
      <span class="tip-name">${escapeHtml(nome)}</span><span class="tip-value">${escapeHtml(valore)}</span></div>`;
    const titolo = `${this._giorno(p.dal)} - ${this._giorno(p.al, { day: "numeric", month: "short", year: "numeric" })}`;
    return `<div class="tip-title">${escapeHtml(titolo)}</div>`
      + riga(t("daily_average"), this._alGiorno(p.media), true)
      + riga(t("consumption"), this._quantita(p.consumo))
      + riga(t("days"), String(p.giorni));
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
  .fact.aperta .fact-label, .fact.aperta .fact-value { color: var(--acegas-accent); }

  .nav { display: flex; align-items: center; margin: -4px -12px -4px; }
  .nav ha-icon-button { --mdc-icon-button-size: 40px; color: var(--primary-text-color); }
  .nav ha-icon-button[disabled] { color: var(--disabled-text-color); }
  .period {
    flex: 1; text-align: center; font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500); color: var(--primary-text-color);
    font-variant-numeric: tabular-nums;
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

  @container (max-width: 300px) {
    .facts, .facts.tre { grid-template-columns: 1fr; }
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

class AcegasContatoreCardEditor extends HTMLElement {
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
      .then(() => {
        if (this._connected) this._render();
      })
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
        delete config.view;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    const predefinito = trovaContatori(this._hass)[0]?.deviceId || "";
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
  if (!registro.get(CARD_TYPE)) registro.define(CARD_TYPE, AcegasContatoreCard);
  if (!registro.get(EDITOR_TYPE)) registro.define(EDITOR_TYPE, AcegasContatoreCardEditor);
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
    documentationURL: "https://github.com/fabioscarparo/HomeAssistant-AcegasApsAmga#meter-card",
  });
}

console.info(`%c ACEGASAPSAMGA CARD %c ${VERSION} `,
  "color:#fff;background:#00bcd4;font-weight:500", "color:#00bcd4;background:transparent");
