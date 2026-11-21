/*
 * AcegasApsAmga meter card.
 *
 * Served by the integration (lovelace_card.py), no resource to add by hand.
 *
 * Built around how a water meter is read: about once a month. The main
 * number is the daily consumption of the last period between two real
 * readings. Under it, the period before and, while there is one, the bill to
 * pay. The chart shows the periods of one calendar year, each bar as wide as
 * its days and as high as its daily average; below it, the year's total, its
 * daily average and its bills.
 *
 * Everything comes from the sensors' attributes, computed by the
 * integration: the year's figures spread each period evenly over its days,
 * like the statistics of the Energy dashboard. Every color and size comes
 * from Home Assistant's tokens. A plain web component in one file, no
 * dependencies.
 */

const CARD_TYPE = "acegasapsamga-contatore-card";
const EDITOR_TYPE = "acegasapsamga-contatore-card-editor";
const VERSION = "0.3.0";
const DOMAIN = "acegasapsamga";
const MAX_DECIMALI = 3;
const DAY_MS = 24 * 3600000;
const URL_CONFIGURA = "/_my_redirect/config_flow_start?domain=acegasapsamga";
// Bill statuses that leave something to pay, as the integration names them.
const STATI_DA_PAGARE = ["unpaid", "expired", "paid_partial"];

const STRINGS = {
  it: {
    card_name: "AcegasApsAmga · Contatore",
    card_description: "Consumo giornaliero tra una lettura e l'altra, anno per anno, e bolletta da pagare.",
    water: "Acqua",
    gas: "Gas",
    meter_line: "Contatore {value} · letto il {date}",
    waiting: "In attesa di due letture reali",
    per_day_water: "litri al giorno",
    per_day_gas: "m³ al giorno",
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
    device_not_found_title: "Contatore non trovato",
    device_not_found_text: "Il contatore configurato per questa card non è più disponibile. Scegline un altro dalle impostazioni della card.",
    ask_admin: "Chiedi a un amministratore di farlo.",
    configure: "Configura",
    chart: "Consumo medio giornaliero per periodo di lettura nel {year}",
    ed_device: "Contatore",
    ed_name: "Nome",
    ed_icon: "Icona",
    ed_decimals: "Cifre decimali",
    ed_decimals_helper: "Da 0 a 3, per i valori in m³. Se vuoto dipendono dal valore.",
  },
  en: {
    card_name: "AcegasApsAmga · Meter",
    card_description: "Daily consumption between readings, year by year, and the bill to pay.",
    water: "Water",
    gas: "Gas",
    meter_line: "Meter {value} · read on {date}",
    waiting: "Waiting for two real readings",
    per_day_water: "litres a day",
    per_day_gas: "m³ a day",
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
    device_not_found_title: "Meter not found",
    device_not_found_text: "The meter configured for this card is no longer available. Choose another one in the card settings.",
    ask_admin: "Ask an administrator to do it.",
    configure: "Set up",
    chart: "Average daily consumption by reading period in {year}",
    ed_device: "Meter",
    ed_name: "Name",
    ed_icon: "Icon",
    ed_decimals: "Decimal places",
    ed_decimals_helper: "From 0 to 3, for values in m³. When empty they depend on the value.",
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

// Like the frontend's navigate(): no page reload.
const naviga = (percorso) => {
  history.pushState(null, "", percorso);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
};

const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// --- Calendar days in the server's time zone -----------------------------------
// Days and years follow Home Assistant's time zone, like the Recorder. A day
// is {y, m, d} with a 0-based month.

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

// One per device, from the entity registry: sensors are found by their
// translation_key, so renamed entities keep working.
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
const SENSORI_MOSTRATI = ["lettura", "consumo_periodo", "bolletta", "da_pagare", "scadenza_bolletta"];

// --- Card ------------------------------------------------------------------------

class AcegasContatoreCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig() {
    // No device: the card takes the first meter it finds.
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
    // 'view' belonged to the first version, with two charts: it is ignored.
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
    // hass changes on every state event: redraw only when something shown changed.
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
    return contatori[0] || null;
  }

  _stato(chiave) {
    const id = this._contatore?.entita[chiave];
    return id ? this._hass?.states[id] : undefined;
  }

  get _gas() {
    return this._stato("lettura")?.attributes.device_class === "gas";
  }

  // Values per day in litres for water, in cubic metres for gas.
  get _fattoreGiorno() {
    return this._gas ? 1 : 1000;
  }

  get _unitaGiorno() {
    return this._gas ? "m³" : "L";
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

  // Periods between real readings, oldest first, from the integration.
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

  // Consumption and days of a year: each period counts for the days it has in it.
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

  // What is still to pay, from the integration's sensors; null when nothing is.
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

  // --- Formatting -----------------------------------------------------------------

  get _locale() {
    const lang = this._hass?.locale?.language || this._hass?.language || "it";
    const fmt = this._hass?.locale?.number_format;
    return { comma_decimal: "en-US", decimal_comma: "de", space_comma: "fr", quote_decimal: "de-CH", system: undefined }[fmt] ?? lang;
  }

  _numero(v, cifre) {
    if (v === null || v === undefined || Number.isNaN(v)) return "-";
    const a = Math.abs(v);
    // Fewer digits as the value grows, unless the config or the caller says otherwise.
    const d = cifre ?? this._config.decimals ?? (a >= 100 ? 0 : a >= 10 ? 1 : 2);
    return numberFormatter(this._locale, {
      minimumFractionDigits: d, maximumFractionDigits: d,
      useGrouping: this._hass?.locale?.number_format !== "none",
    }).format(v);
  }

  _metriCubi(v) {
    // Whole cubic metres, as the meter shows them, stay whole.
    const intero = Number.isInteger(v) && this._config.decimals == null;
    return `${this._numero(v, intero ? 0 : undefined)} m³`;
  }

  _euro(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "-";
    return numberFormatter(this._locale, {
      style: "currency", currency: "EUR", useGrouping: this._hass?.locale?.number_format !== "none",
    }).format(v);
  }

  // A daily value: litres with no decimals, or cubic metres for gas.
  _giornaliero(v) {
    return this._gas ? this._numero(v) : this._numero(v, 0);
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
    return this._gas
      ? parseColore(cs.getPropertyValue("--energy-gas-color"), [142, 2, 27])
      : parseColore(cs.getPropertyValue("--energy-water-color"), [0, 188, 212]);
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

    // The year of the last reading, until the user picks another.
    const primoAnno = daIso(periodi[0].dal).y;
    const ultimoAnno = daIso(periodi[periodi.length - 1].al).y;
    if (this._anno === null || this._anno < primoAnno || this._anno > ultimoAnno) this._anno = ultimoAnno;

    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    $("ha-card").style.setProperty("--acegas-accent", rgbCss(this._colore()));

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

    this._renderRiepilogo(periodi);
    this._larghezza = $(".chart").clientWidth || this._larghezza;
    this._renderGrafico(periodi);
  }

  _renderIntestazione() {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const icona = this._config.icon || (this._gas ? "mdi:fire" : "mdi:water");
    if ($(".icon ha-icon").getAttribute("icon") !== icona) $(".icon ha-icon").setAttribute("icon", icona);
    $(".primary").textContent = this._config.name || t(this._gas ? "gas" : "water");
    const lettura = this._stato("lettura");
    $(".secondary").textContent = valido(lettura) && lettura.attributes.giorno
      ? t("meter_line", {
        value: this._hass.formatEntityState ? this._hass.formatEntityState(lettura) : `${lettura.state} m³`,
        date: this._giorno(lettura.attributes.giorno),
      })
      : t("waiting");
  }

  _renderProtagonista(periodi) {
    // The daily consumption of the last period, next to the one before.
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const ultimo = periodi[periodi.length - 1];
    const prima = periodi[periodi.length - 2];
    $(".hero-value").textContent = this._giornaliero(ultimo.media);
    $(".hero-unit").textContent = t(this._gas ? "per_day_gas" : "per_day_water");
    $(".hero-sub").textContent = t("period_line", {
      from: this._giorno(ultimo.dal),
      to: this._giorno(ultimo.al),
      value: this._metriCubi(ultimo.consumo),
      days: String(ultimo.giorni),
    });

    const fatto = $('[data-fatto="prima"]');
    fatto.hidden = !prima;
    if (!prima) return;
    fatto.querySelector(".fact-label").textContent = t("previous_period");
    fatto.querySelector(".fact-value").textContent = this._alGiorno(prima.media);
    // Its days, like the line under the main number: the two values are compared by reading them.
    fatto.querySelector(".fact-sub span").textContent = `${this._giorno(prima.dal)} - ${this._giorno(prima.al)}`;
  }

  _renderBolletta() {
    // Shown only while something is still to pay.
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const fatto = $('[data-fatto="bolletta"]');
    const conto = this._daPagare();
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

  _renderRiepilogo(periodi) {
    // The selected year: total, daily average and bills issued in it.
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const anno = this._anno;
    const dati = this._datiAnno(periodi, anno);
    const imposta = (chiave, etichetta, valore) => {
      const el = $(`[data-stat="${chiave}"]`);
      el.querySelector(".stat-label").textContent = etichetta;
      el.querySelector(".stat-value").textContent = valore;
    };
    imposta("anno", t("in_year", { year: anno }), dati ? this._metriCubi(Math.round(dati.consumo * 10) / 10) : "-");
    imposta("media", t("average_year", { year: anno }), dati ? this._alGiorno(dati.media) : "-");

    // Bills appear only with an integration that has the bill sensors.
    const conBollette = !!this._contatore?.entita.bolletta;
    $(".stats").classList.toggle("tre", conBollette);
    $('[data-stat="bollette"]').hidden = !conBollette;
    if (conBollette) {
      const dellAnno = this._bollette().filter(
        (b) => String(b.emissione).startsWith(`${anno}-`) && b.stato !== "reversed"
      );
      const totale = dellAnno.reduce((s, b) => {
        const importo = Number(b.importo) || 0;
        return s + (b.stato === "credit" ? -Math.abs(importo) : importo);
      }, 0);
      imposta("bollette", t("bills_year", { year: anno }), dellAnno.length ? this._euro(totale) : "-");
    }
  }

  _alertConAzione(titolo, testo, etichetta, percorso) {
    // Setup pages are for administrators: others get the text without a button.
    const admin = !!this._hass.user?.is_admin;
    return `<ha-alert alert-type="info" title="${escapeHtml(titolo)}">
      ${escapeHtml(testo)}${admin ? "" : ` ${escapeHtml(traduci(this._hass, "ask_admin"))}`}
      ${admin ? `<ha-button slot="action" data-percorso="${escapeHtml(percorso)}">${escapeHtml(etichetta)}</ha-button>` : ""}
    </ha-alert>`;
  }

  _renderVuota(chiave) {
    // Integration missing, meter removed, or set up without two real readings yet.
    this._ro?.disconnect();
    this._staccaChiusuraEsterna();
    const configurata = (this._hass.config?.components || []).includes(DOMAIN);
    const quale = chiave === "not_configured" && configurata ? "empty" : chiave;
    const firma = `vuota-${quale}-${lingua(this._hass)}-${this._hass.user?.is_admin}`;
    if (this._modo === firma) return;
    this._modo = firma;
    const t = (k) => traduci(this._hass, k);
    let contenuto;
    if (quale === "not_configured") {
      contenuto = this._alertConAzione(t("not_configured_title"), t("not_configured_text"), t("configure"), URL_CONFIGURA);
    } else if (quale === "device_not_found") {
      contenuto = `<ha-alert alert-type="warning" title="${escapeHtml(t("device_not_found_title"))}">${escapeHtml(t("device_not_found_text"))}</ha-alert>`;
    } else {
      contenuto = `<ha-alert alert-type="info" title="${escapeHtml(t("empty_title"))}">${escapeHtml(t("empty_text"))}</ha-alert>`;
    }
    this.shadowRoot.innerHTML = `<style>${STILE}</style><ha-card><div class="empty-card">${contenuto}</div></ha-card>`;
    this.shadowRoot.querySelectorAll("[data-percorso]").forEach((el) =>
      el.addEventListener("click", () => naviga(el.dataset.percorso)));
  }

  _struttura() {
    // Built once: updates only change texts and attributes, so nothing flickers.
    this._modo = "card";
    this.shadowRoot.innerHTML = `
      <style>${STILE}</style>
      <ha-card>
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
          <div class="chart">
            <div class="svg-host"></div>
            <div id="chart-tooltip" class="tooltip" role="tooltip" hidden></div>
          </div>
          <div class="stats">
            <div class="stat" data-stat="anno"><div class="stat-label"></div><div class="stat-value"></div></div>
            <div class="stat" data-stat="media"><div class="stat-label"></div><div class="stat-value"></div></div>
            <div class="stat" data-stat="bollette" hidden><div class="stat-label"></div><div class="stat-value"></div></div>
          </div>
        </div>
      </ha-card>`;

    const root = this.shadowRoot;
    const sposta = (direzione) => {
      this._anno += direzione;
      this._hover = null;
      this._render();
    };
    root.querySelector('[data-azione="prev"]').addEventListener("click", () => sposta(-1));
    root.querySelector('[data-azione="next"]').addEventListener("click", () => sposta(1));
    // Header, numbers and the bill open the details of their sensor, like a tile.
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

    // A bar for each period with days in the year, cut at the year's edges.
    const voci = periodi
      .filter((p) => p.fine > inizioAnno && p.inizio < fineAnno)
      .map((p) => ({ p, f0: Math.max(0, f(p.inizio)), f1: Math.min(1, f(p.fine)) }));
    const colore = this._colore();
    // Exclude sliver edges (< 4px) from the Y scale so an undrawn sliver cannot flatten the chart.
    const sogliaFrazione = 4 / Math.max(10, W - 40);
    const perScala = voci.filter((v) => v.f1 - v.f0 >= sogliaFrazione);
    const scala = scalaArrotondata(Math.max(0, ...(perScala.length ? perScala : voci).map((v) => v.p.media)), 4);

    // Room above the top value for the unit label.
    const H = 192;
    const top = 34;
    const bottom = 22;
    const cifre = this._gas ? (scala.ticks.some((v) => v % 1) ? 1 : 0) : 0;
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
    // The unit starts at the left edge: "L/giorno" is wider than the axis labels.
    parti.push(`<text class="unita" x="0" y="12">${escapeHtml(t("unit_per_day", { unit: this._unitaGiorno }))}</text>`);
    parti.push(`<rect class="hover-band" x="0" y="${top}" width="0" height="${plotH}" />`);

    // Like the energy cards: 50% fill, solid 1.5px border, top corners rounded to 4px.
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
      // A few days cut by the year's edge would be a sliver: they stay in the tooltip only.
      if ((v.f1 - v.f0) * plotW < 4) continue;
      // A small gap between periods, never more than 2px a side.
      const margine = Math.min(0.04 * (v.f1 - v.f0) * plotW, 2);
      parti.push(barra(x(v.f0) + margine, x(v.f1) - margine, v.p.media));
    }

    // Month names under the middle of each month.
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

  // The whole period, even when the year cuts its bar.
  _tooltip(p, colore) {
    const t = (k, v) => traduci(this._hass, k, v);
    const riga = (nome, valore, puntino) => `<div class="tip-row">${puntino ? `<span class="tip-marker" style="background:${rgbCss(colore)}"></span>` : ""}
      <span class="tip-name">${escapeHtml(nome)}</span><span class="tip-value">${escapeHtml(valore)}</span></div>`;
    const titolo = `${this._giorno(p.dal)} - ${this._giorno(p.al, { day: "numeric", month: "short", year: "numeric" })}`;
    return `<div class="tip-title">${escapeHtml(titolo)}</div>`
      + riga(t("daily_average"), this._alGiorno(p.media), true)
      + riga(t("consumption"), this._metriCubi(p.consumo))
      + riga(t("days"), String(p.giorni));
  }
}

const STILE = `
  :host { display: block; }
  ha-card { height: 100%; overflow: hidden; }
  .empty-card { padding: var(--ha-space-4, 16px); }
  ha-alert { display: block; }
  [hidden] { display: none !important; }

  .header, .hero, .fact {
    appearance: none; background: none; border: 0; font: inherit; color: inherit;
    text-align: start; padding: 0; margin: 0; width: 100%; box-sizing: border-box;
  }
  .header {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 16px 0; cursor: pointer; outline: none;
    border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
  }
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
  .header:hover .icon::before { opacity: 0.35; }
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

  .content { display: flex; flex-direction: column; gap: 12px; padding: 16px; container-type: inline-size; }

  /* The main number: daily consumption of the last period */
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

  /* The period before and the bill to pay: plain text, like the year's figures */
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
  svg text { font-size: 12px; fill: var(--primary-text-color); }
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

  /* The selected year: total, average and bills */
  .stats {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px;
    padding-top: 12px; border-top: 1px solid var(--divider-color);
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

  /* like the tooltip of Home Assistant's charts */
  .tooltip {
    position: absolute; z-index: 1; pointer-events: none; white-space: nowrap;
    background: var(--ha-card-background, var(--card-background-color, #fff));
    border: 1px solid var(--divider-color); border-radius: 4px;
    box-shadow: rgba(0, 0, 0, 0.2) 1px 2px 10px; padding: 8px 10px;
    font-size: 12px; line-height: 18px; color: var(--primary-text-color);
  }
  .tip-title { font-weight: var(--ha-font-weight-medium, 500); margin-bottom: 2px; }
  .tip-row { display: flex; align-items: center; gap: 6px; }
  .tip-marker { width: 10px; height: 10px; border-radius: 50%; flex: none; }
  .tip-name { flex: 1; }
  .tip-value { font-weight: var(--ha-font-weight-medium, 500); margin-inline-start: 16px; font-variant-numeric: tabular-nums; }

  @media (prefers-reduced-motion: reduce) {
    * { transition-duration: 1ms !important; }
  }
`;

// --- Visual editor (ha-form, like the core cards) ---------------------------------

// ha-form exists only once a core card editor has been loaded.
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
    ];
  }

  _render() {
    if (!this._connected || !this._hass || !this._config || !customElements.get("ha-form")) return;
    const etichette = { device_id: "ed_device", name: "ed_name", icon: "ed_icon", decimals: "ed_decimals" };
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.schema = this._schemaCache;
      this._form.computeLabel = (s) => traduci(this._hass, etichette[s.name] || s.name);
      this._form.computeHelper = (s) => (s.name === "decimals" ? traduci(this._hass, "ed_decimals_helper") : undefined);
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...ev.detail.value };
        // An emptied field leaves the option out; 'view' is from the first version.
        for (const k of Object.keys(config)) if (config[k] === "" || config[k] == null) delete config[k];
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
      this._form.data = { device_id: predefinito || undefined, ...this._config };
    }
  }
}

// --- Registration -------------------------------------------------------------------
// Home Assistant swaps window.customElements for its own registry while it
// starts, and this module can load earlier: define the elements once the app
// exists, reading window.customElements at that moment.

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
