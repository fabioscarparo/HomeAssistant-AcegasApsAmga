/*
 * AcegasApsAmga meter card.
 *
 * Served by the integration (lovelace_card.py), no resource to add by hand.
 *
 * Built around how a water meter is read: about once a month. The main
 * number is the daily consumption of the last period between two real
 * readings, compared with the period before. The chart shows either those
 * periods (each bar as wide as its days) or the months, from the same
 * statistics the Energy dashboard reads.
 *
 * Periods come from the sensors' attributes, computed by the integration;
 * months from the Recorder. Every color and size comes from Home Assistant's
 * tokens. A plain web component in one file, no dependencies.
 */

const CARD_TYPE = "acegasapsamga-contatore-card";
const EDITOR_TYPE = "acegasapsamga-contatore-card-editor";
const VERSION = "0.1.0";
const DOMAIN = "acegasapsamga";
const VISTE = ["readings", "months"];
const VISTA_PREDEFINITA = "readings";
const MAX_DECIMALI = 3;
const DAY_MS = 24 * 3600000;
const URL_CONFIGURA = "/_my_redirect/config_flow_start?domain=acegasapsamga";

const STRINGS = {
  it: {
    card_name: "AcegasApsAmga · Contatore",
    card_description: "Consumo giornaliero tra una lettura e l'altra e consumi mensili del contatore dell'acqua.",
    water: "Acqua",
    gas: "Gas",
    meter_line: "Contatore {value} · letto il {date}",
    waiting: "In attesa di due letture reali",
    per_day_water: "litri al giorno",
    per_day_gas: "m³ al giorno",
    period_line: "{from} - {to} · {value} in {days} giorni",
    trend: "{value} sul periodo prima",
    readings: "Per lettura",
    months: "Per mese",
    daily_average: "Media",
    consumption: "Consumo",
    days: "Giorni",
    in_year: "Nel {year}",
    average_year: "Media {year}",
    per_day_short: "{value}/giorno",
    reading_of: "Lettura del {date}",
    previous: "Precedente",
    next: "Successivo",
    no_data: "Non ci sono dati per questo periodo.",
    empty_title: "Ancora nessun consumo",
    empty_text: "Per calcolare i consumi servono almeno due letture reali del contatore. AcegasApsAmga legge il contatore circa una volta al mese.",
    not_configured_title: "Integrazione non configurata",
    not_configured_text: "Aggiungi l'integrazione AcegasApsAmga per vedere qui i consumi del tuo contatore.",
    ask_admin: "Chiedi a un amministratore di farlo.",
    configure: "Configura",
    load_error: "Impossibile leggere le statistiche: {error}",
    chart_readings: "Consumo medio giornaliero per periodo di lettura",
    chart_months: "{period}: consumo {value}",
    ed_device: "Contatore",
    ed_name: "Nome",
    ed_icon: "Icona",
    ed_view: "Grafico iniziale",
    ed_decimals: "Cifre decimali",
    ed_decimals_helper: "Da 0 a 3, per i valori in m³. Se vuoto dipendono dal valore.",
  },
  en: {
    card_name: "AcegasApsAmga · Meter",
    card_description: "Daily consumption between readings and monthly consumption of the water meter.",
    water: "Water",
    gas: "Gas",
    meter_line: "Meter {value} · read on {date}",
    waiting: "Waiting for two real readings",
    per_day_water: "litres a day",
    per_day_gas: "m³ a day",
    period_line: "{from} - {to} · {value} in {days} days",
    trend: "{value} vs the previous period",
    readings: "By reading",
    months: "By month",
    daily_average: "Average",
    consumption: "Consumption",
    days: "Days",
    in_year: "In {year}",
    average_year: "{year} average",
    per_day_short: "{value}/day",
    reading_of: "Reading of {date}",
    previous: "Previous",
    next: "Next",
    no_data: "There is no data for this period.",
    empty_title: "No consumption yet",
    empty_text: "Consumption needs at least two real meter readings. AcegasApsAmga reads the meter about once a month.",
    not_configured_title: "Integration not set up",
    not_configured_text: "Add the AcegasApsAmga integration to see your meter's consumption here.",
    ask_admin: "Ask an administrator to do it.",
    configure: "Set up",
    load_error: "Unable to read statistics: {error}",
    chart_readings: "Average daily consumption by reading period",
    chart_months: "{period}: consumption {value}",
    ed_device: "Meter",
    ed_name: "Name",
    ed_icon: "Icon",
    ed_view: "Initial chart",
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
  for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
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
// The Recorder groups days and months in Home Assistant's time zone, so every
// boundary is computed there. A day is {y, m, d} with a 0-based month.

const _dtfCache = new Map();
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

const civile = (date, tz) => {
  const p = partiNelFuso(date, tz);
  return { y: p.y, m: p.m, d: p.d };
};

const addGiorni = (c, n) => {
  const d = new Date(Date.UTC(c.y, c.m, c.d + n));
  return { y: d.getUTCFullYear(), m: d.getUTCMonth(), d: d.getUTCDate() };
};

const addMesi = (c, n) => {
  const d = new Date(Date.UTC(c.y, c.m + n, 1));
  return { y: d.getUTCFullYear(), m: d.getUTCMonth(), d: 1 };
};

const daIso = (s) => {
  const [y, m, d] = String(s).split("-").map(Number);
  return { y, m: m - 1, d };
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
    this._vista = VISTA_PREDEFINITA;
    this._anno = null;
    this._estremi = null;
    this._mesi = null;
    this._caricamento = false;
    this._errore = null;
    this._larghezza = 0;
    this._hover = null;
    this._richiesta = 0;
    this._firma = "";
    this._firmaSerie = null;
  }

  setConfig(config) {
    if (config.view && !VISTE.includes(config.view)) {
      throw new Error(`view: ${VISTE.join(", ")}`);
    }
    const decimali = config.decimals;
    if (decimali !== undefined && decimali !== null
      && !(Number.isInteger(decimali) && decimali >= 0 && decimali <= MAX_DECIMALI)) {
      throw new Error(`decimals: 0-${MAX_DECIMALI}`);
    }
    const dispositivoPrima = this._config.device_id;
    this._config = { ...config };
    this._vista = this._config.view || VISTA_PREDEFINITA;
    if (this._hass && dispositivoPrima !== this._config.device_id) {
      this._ricomincia();
    } else {
      this._render();
    }
  }

  set hass(hass) {
    const primo = !this._hass;
    if (this._contatoriDa !== hass.entities) {
      this._contatori = trovaContatori(hass);
      this._contatoriDa = hass.entities;
    }
    this._hass = hass;
    // A new reading (or the series appearing) means new statistics: load again.
    const serie = this._firmaLettura();
    if (primo || serie !== this._firmaSerie) {
      this._firmaSerie = serie;
      this._firma = this._firmaVista();
      this._ricomincia();
      return;
    }
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
      const w = Math.floor(entries[0].contentRect.width);
      if (w && w !== this._larghezza) {
        this._larghezza = w;
        this._renderGrafico();
      }
    });
    const chart = this.shadowRoot.querySelector(".chart");
    if (chart) this._ro.observe(chart);
    if (this._staccata && this._hass) {
      this._staccata = false;
      this._ricomincia();
    }
  }

  disconnectedCallback() {
    this._ro?.disconnect();
    this._staccata = true;
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
    return contatori.find((c) => c.deviceId === this._config.device_id) || contatori[0] || null;
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

  _firmaLettura() {
    const lettura = this._stato("lettura");
    return `${this._contatore?.deviceId}|${lettura?.state}|${lettura?.attributes.giorno}|${lettura?.attributes.statistic_id}`;
  }

  _firmaVista() {
    const h = this._hass;
    const stati = ["consumo_periodo"].map((k) => this._stato(k)?.last_updated);
    return [h.themes?.darkMode, h.locale?.language, h.locale?.number_format, h.config?.time_zone,
      h.user?.is_admin, ...stati].join("|");
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

  // Real readings, for the dots under the monthly bars.
  _letture() {
    return (this._stato("lettura")?.attributes.letture || []).filter((l) => l.tipo !== "ESTIMATED" && l.giorno);
  }

  _ricomincia() {
    this._estremi = null;
    this._anno = null;
    this._mesi = null;
    this._avvia();
  }

  async _avvia() {
    this._render();
    const id = this._stato("lettura")?.attributes.statistic_id;
    if (!id) return;
    try {
      if (!this._estremi) this._estremi = await this._leggiEstremi(id);
      if (this._anno === null) {
        const ultimo = this._estremi.ultimo ? new Date(this._estremi.ultimo - 1) : new Date();
        this._anno = civile(ultimo, this._tz).y;
      }
      await this._caricaAnno();
    } catch (err) {
      this._errore = err?.message || String(err);
      this._render();
    }
  }

  async _statistiche(id, inizio, fine, period) {
    const res = await this._hass.callWS({
      type: "recorder/statistics_during_period",
      start_time: inizio.toISOString(),
      end_time: fine ? fine.toISOString() : undefined,
      statistic_ids: [id],
      period,
      types: ["change"],
      units: { volume: "m³" },
    });
    const norm = (t) => (typeof t === "number" ? t : Date.parse(t));
    return (res[id] || []).map((r) => ({ start: norm(r.start), change: r.change }));
  }

  async _leggiEstremi(id) {
    // The months with data, then the first day and the last hour: they bound
    // the navigation and the yearly average.
    const mesi = await this._statistiche(id, new Date(Date.UTC(2015, 0, 1)), null, "month");
    if (!mesi.length) return { primo: null, ultimo: null };
    const fineMese = (m) => mezzanotte(addMesi(civile(new Date(m.start), this._tz), 1), this._tz);
    const giorni = await this._statistiche(id, new Date(mesi[0].start), fineMese(mesi[0]), "day");
    const ore = await this._statistiche(id, new Date(mesi[mesi.length - 1].start), null, "hour");
    return {
      primo: giorni.length ? giorni[0].start : mesi[0].start,
      ultimo: ore.length ? ore[ore.length - 1].start + 3600000 : fineMese(mesi[mesi.length - 1]).getTime(),
    };
  }

  _inizioAnno(anno = this._anno) {
    return mezzanotte({ y: anno, m: 0, d: 1 }, this._tz).getTime();
  }

  async _caricaAnno() {
    const id = this._stato("lettura")?.attributes.statistic_id;
    if (!id || this._anno === null) return;
    const richiesta = ++this._richiesta;
    const anno = this._anno;
    this._caricamento = true;
    this._hover = null;
    this._render();
    try {
      const righe = await this._statistiche(id, new Date(this._inizioAnno(anno)), new Date(this._inizioAnno(anno + 1)), "month");
      if (richiesta !== this._richiesta) return; // the user already moved on
      const valori = Array(12).fill(null);
      for (const r of righe) {
        if (r.change === null || r.change === undefined) continue;
        const c = civile(new Date(r.start), this._tz);
        if (c.y === anno) valori[c.m] = (valori[c.m] || 0) + r.change;
      }
      this._mesi = { anno, valori };
      this._errore = null;
    } catch (err) {
      if (richiesta !== this._richiesta) return;
      this._errore = err?.message || String(err);
    }
    this._caricamento = false;
    this._render();
  }

  _sposta(direzione) {
    this._anno += direzione;
    this._caricaAnno();
  }

  _puoTornare() {
    return !!this._estremi?.primo && this._anno !== null && this._inizioAnno() > this._estremi.primo;
  }

  _puoAvanzare() {
    return !!this._estremi?.ultimo && this._anno !== null && this._inizioAnno(this._anno + 1) < this._estremi.ultimo;
  }

  _cambiaVista(vista) {
    if (vista === this._vista) return;
    this._vista = vista;
    this._hover = null;
    this._render();
  }

  // Days of [inizio, fine) covered by the data, for averages.
  _giorniConDati(inizio, fine) {
    const e = this._estremi;
    if (!e?.primo || !e?.ultimo) return 0;
    const da = Math.max(inizio, e.primo);
    const a = Math.min(fine, e.ultimo);
    return a > da ? Math.round((a - da) / DAY_MS) : 0;
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
    return new Intl.NumberFormat(this._locale, {
      minimumFractionDigits: d, maximumFractionDigits: d,
      useGrouping: this._hass?.locale?.number_format !== "none",
    }).format(v);
  }

  _metriCubi(v) {
    // Whole cubic metres, as the meter shows them, stay whole.
    const intero = Number.isInteger(v) && this._config.decimals == null;
    return `${this._numero(v, intero ? 0 : undefined)} m³`;
  }

  // A daily value: litres with no decimals, or cubic metres for gas.
  _giornaliero(v) {
    return this._gas ? this._numero(v) : this._numero(v, 0);
  }

  _data(date, opzioni) {
    const lang = this._hass?.locale?.language || "it";
    return new Intl.DateTimeFormat(lang, { timeZone: this._tz, ...opzioni }).format(date);
  }

  _giorno(iso, opzioni = { day: "numeric", month: "short" }) {
    return this._data(mezzanotte(daIso(iso), this._tz), opzioni);
  }

  _percentuale(v) {
    return new Intl.NumberFormat(this._locale, { style: "percent", maximumFractionDigits: 0, signDisplay: "exceptZero" }).format(v);
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
      this._renderVuota("not_configured");
      return;
    }
    const periodi = this._periodi();
    if (!periodi.length) {
      this._renderVuota("empty");
      return;
    }
    if (this._modo !== "card") this._struttura();

    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    $("ha-card").style.setProperty("--acegas-accent", rgbCss(this._colore()));

    this._renderIntestazione();
    this._renderProtagonista(periodi);
    $(".error").innerHTML = this._errore
      ? `<ha-alert alert-type="error">${escapeHtml(t("load_error", { error: this._errore }))}</ha-alert>` : "";

    // Chart selector, and navigation by year in the monthly chart only
    this.shadowRoot.querySelectorAll("[data-vista]").forEach((el) => {
      const scelta = el.dataset.vista === this._vista;
      el.classList.toggle("selected", scelta);
      el.setAttribute("aria-checked", String(scelta));
      el.firstElementChild.textContent = t(el.dataset.vista);
    });
    const mesi = this._vista === "months";
    const prev = $('[data-azione="prev"]');
    const next = $('[data-azione="next"]');
    prev.classList.toggle("nascosta", !mesi);
    next.classList.toggle("nascosta", !mesi);
    prev.toggleAttribute("disabled", !mesi || !this._puoTornare());
    next.toggleAttribute("disabled", !mesi || !this._puoAvanzare());
    prev.setAttribute("label", this._hass.localize?.("ui.panel.lovelace.components.energy_period_selector.previous") || t("previous"));
    next.setAttribute("label", this._hass.localize?.("ui.panel.lovelace.components.energy_period_selector.next") || t("next"));
    const primo = periodi[0];
    const ultimo = periodi[periodi.length - 1];
    const meseAnno = { month: "short", year: "numeric" };
    $(".period").textContent = mesi
      ? String(this._anno ?? " ")
      : `${this._giorno(primo.dal, meseAnno)} - ${this._giorno(ultimo.al, meseAnno)}`;

    this._renderRiepilogo();
    $(".chart").classList.toggle("loading", mesi && this._caricamento);
    this._larghezza = $(".chart").clientWidth || this._larghezza;
    this._renderGrafico();
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
    // The daily consumption of the last period, and how it compares with the one before.
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
    const trend = $(".trend");
    const variazione = prima && prima.media > 0 ? (ultimo.media - prima.media) / prima.media : null;
    trend.hidden = variazione === null || Math.abs(variazione) < 0.01;
    if (trend.hidden) return;
    const su = variazione > 0;
    trend.classList.toggle("su", su);
    trend.querySelector("ha-icon").setAttribute("icon", su ? "mdi:arrow-top-right" : "mdi:arrow-bottom-right");
    trend.querySelector("span").textContent = t("trend", { value: this._percentuale(variazione) });
  }

  _renderRiepilogo() {
    // Year total and year average.
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    // While the statistics load, the year of the last reading already names the stats.
    const ultimo = this._periodi().at(-1);
    const anno = this._mesi?.anno ?? this._anno ?? (ultimo ? daIso(ultimo.al).y : null);
    const valori = this._mesi?.anno === anno ? this._mesi.valori : [];
    const conDati = valori.filter((v) => v !== null);
    const totale = conDati.length ? conDati.reduce((a, v) => a + v, 0) : null;
    const giorni = anno !== null ? this._giorniConDati(this._inizioAnno(anno), this._inizioAnno(anno + 1)) : 0;
    const media = totale !== null && giorni ? (totale / giorni) * this._fattoreGiorno : null;
    const imposta = (chiave, etichetta, valore) => {
      const el = $(`[data-stat="${chiave}"]`);
      el.querySelector(".stat-label").textContent = etichetta;
      el.querySelector(".stat-value").textContent = valore;
    };
    imposta("anno", t("in_year", { year: anno ?? "" }), totale === null ? "-" : this._metriCubi(totale));
    imposta("media", t("average_year", { year: anno ?? "" }),
      media === null ? "-" : t("per_day_short", { value: `${this._giornaliero(media)} ${this._unitaGiorno}` }));
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
    // Integration missing, or set up without two real readings yet.
    const configurata = (this._hass.config?.components || []).includes(DOMAIN);
    const quale = chiave === "not_configured" && configurata ? "empty" : chiave;
    const firma = `vuota-${quale}-${lingua(this._hass)}-${this._hass.user?.is_admin}`;
    if (this._modo === firma) return;
    this._modo = firma;
    const t = (k) => traduci(this._hass, k);
    const contenuto = quale === "not_configured"
      ? this._alertConAzione(t("not_configured_title"), t("not_configured_text"), t("configure"), URL_CONFIGURA)
      : `<ha-alert alert-type="info" title="${escapeHtml(t("empty_title"))}">${escapeHtml(t("empty_text"))}</ha-alert>`;
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
        <div class="header" role="button" tabindex="0" data-apri="lettura">
          <div class="icon"><ha-icon></ha-icon></div>
          <div class="info">
            <div class="primary"></div>
            <div class="secondary"></div>
          </div>
        </div>
        <div class="content">
          <div class="hero" role="button" tabindex="0" data-apri="media_giornaliera">
            <div class="hero-text">
              <div class="hero-main"><span class="hero-value"></span><span class="hero-unit"></span></div>
              <div class="hero-sub"></div>
            </div>
            <div class="trend" hidden><ha-icon></ha-icon><span></span></div>
          </div>
          <div class="error"></div>
          <div class="segmented" role="radiogroup">
            ${VISTE.map((v) => `<button class="option" role="radio" data-vista="${v}"><span></span></button>`).join("")}
          </div>
          <div class="nav">
            <ha-icon-button data-azione="prev"><ha-icon icon="mdi:chevron-left"></ha-icon></ha-icon-button>
            <div class="period"></div>
            <ha-icon-button data-azione="next"><ha-icon icon="mdi:chevron-right"></ha-icon></ha-icon-button>
          </div>
          <div class="chart">
            <div class="svg-host"></div>
            <div class="tooltip" hidden></div>
          </div>
          <div class="stats">
            <div class="stat" data-stat="anno"><div class="stat-label"></div><div class="stat-value"></div></div>
            <div class="stat" data-stat="media"><div class="stat-label"></div><div class="stat-value"></div></div>
          </div>
        </div>
      </ha-card>`;

    const root = this.shadowRoot;
    root.querySelectorAll("[data-vista]").forEach((el) =>
      el.addEventListener("click", () => this._cambiaVista(el.dataset.vista)));
    root.querySelector('[data-azione="prev"]').addEventListener("click", () => this._sposta(-1));
    root.querySelector('[data-azione="next"]').addEventListener("click", () => this._sposta(1));
    // Header and main number open the details of their sensor, like a tile.
    root.querySelectorAll("[data-apri]").forEach((el) => {
      const apri = () => this._moreInfo(this._contatore?.entita[el.dataset.apri]);
      el.addEventListener("click", apri);
      el.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          apri();
        }
      });
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

  _renderGrafico() {
    const host = this.shadowRoot.querySelector(".svg-host");
    if (!host) return;
    const W = this._larghezza || host.clientWidth;
    const barre = W ? (this._vista === "months" ? this._barreMesi() : this._barrePeriodi()) : null;
    if (!barre) {
      host.innerHTML = "";
      return;
    }
    const t = (k, v) => traduci(this._hass, k, v);
    const colore = this._colore();
    const vuoto = barre.voci.every((b) => b.valore === null);
    const scala = scalaArrotondata(Math.max(0, ...barre.voci.map((b) => b.valore || 0)), 4);

    // Room above the top value for the unit label.
    const H = 192;
    const top = 34;
    const bottom = 22;
    const cifre = barre.cifreAsse ?? (scala.ticks.some((v) => v % 1) ? 1 : 0);
    const etichetteY = scala.ticks.map((v) => this._numero(v, cifre));
    const left = Math.max(24, Math.ceil(Math.max(...etichetteY.map((s) => s.length)) * 7) + 10);
    const right = 4;
    const plotW = Math.max(10, W - left - right);
    const plotH = H - top - bottom;
    const y = (v) => top + ((scala.max - v) / scala.max) * plotH;
    const x = (f) => left + f * plotW; // f goes from 0 to 1 across the plot

    const parti = [];
    scala.ticks.forEach((v, i) => {
      const yy = Math.round(y(v)) + 0.5;
      parti.push(`<line class="grid" x1="${left}" x2="${W - right}" y1="${yy}" y2="${yy}"/>`);
      parti.push(`<text class="ylab" x="${left - 8}" y="${yy + 4}">${escapeHtml(etichetteY[i])}</text>`);
    });
    // The unit starts at the left edge: "L/giorno" is wider than the axis labels.
    parti.push(`<text class="unita" x="0" y="12">${escapeHtml(barre.unita)}</text>`);
    parti.push(`<rect class="hover-band" x="0" y="${top}" width="0" height="${plotH}" />`);

    // Like the energy cards: 50% fill, solid 1.5px border, top corners rounded to 4px.
    const barra = (x0, x1, v) => {
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
    for (const b of barre.voci) {
      if (b.valore === null) continue;
      const margine = Math.min(barre.margine * (b.f1 - b.f0) * plotW, 4);
      parti.push(barra(x(b.f0) + margine, x(b.f1) - margine, b.valore));
      if (b.lettura) parti.push(`<circle class="reading" cx="${x((b.f0 + b.f1) / 2)}" cy="${top + plotH + 5}" r="2.5"/>`);
    }
    for (const e of barre.etichette) {
      parti.push(`<text class="xlab" x="${x(e.f)}" y="${H - 3}">${escapeHtml(e.testo)}</text>`);
    }

    host.innerHTML = `
      <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeHtml(barre.aria)}">
        ${parti.join("")}
        <rect class="hit" x="${left}" y="${top}" width="${plotW}" height="${plotH + 10}"/>
      </svg>
      ${vuoto ? `<div class="no-data">${escapeHtml(this._hass.localize?.("ui.panel.lovelace.cards.energy.no_data_period") || t("no_data"))}</div>` : ""}`;

    const svg = host.querySelector("svg");
    const banda = svg.querySelector(".hover-band");
    const tip = this.shadowRoot.querySelector(".tooltip");
    const indice = (ev) => {
      const r = svg.getBoundingClientRect();
      const f = (ev.clientX - r.left - left) / plotW;
      const i = barre.voci.findIndex((b) => f >= b.f0 && f < b.f1);
      return i >= 0 ? i : null;
    };
    const nascondi = () => {
      this._hover = null;
      banda.setAttribute("width", 0);
      tip.hidden = true;
    };
    const mostra = (i) => {
      if (i === null || barre.voci[i].valore === null) return nascondi();
      const b = barre.voci[i];
      this._hover = i;
      banda.setAttribute("x", x(b.f0));
      banda.setAttribute("width", (b.f1 - b.f0) * plotW);
      tip.innerHTML = barre.tooltip(i, colore);
      tip.hidden = false;
      const cx = x((b.f0 + b.f1) / 2);
      const meta = ((b.f1 - b.f0) * plotW) / 2;
      const tw = tip.offsetWidth;
      const lx = cx < W / 2 ? cx + meta + 8 : cx - meta - 8 - tw;
      tip.style.left = `${Math.max(0, Math.min(W - tw, lx))}px`;
      tip.style.top = `${Math.min(top, H - tip.offsetHeight)}px`;
    };
    svg.addEventListener("pointermove", (ev) => ev.pointerType === "mouse" && mostra(indice(ev)));
    svg.addEventListener("pointerleave", (ev) => ev.pointerType === "mouse" && nascondi());
    svg.addEventListener("click", (ev) => {
      const i = indice(ev);
      if (i === this._hover && ev.pointerType !== "mouse") nascondi();
      else mostra(i);
    });
    if (this._hover !== null && this._hover < barre.voci.length) mostra(this._hover);
  }

  // Bars by reading period: each as wide as its days, as high as its daily average.
  _barrePeriodi() {
    const t = (k, v) => traduci(this._hass, k, v);
    const periodi = this._periodi();
    if (!periodi.length) return null;
    const t0 = periodi[0].inizio;
    const t1 = periodi[periodi.length - 1].fine;
    const f = (ms) => (ms - t0) / (t1 - t0);
    const voci = periodi.map((p) => ({ f0: f(p.inizio), f1: f(p.fine), valore: p.media }));

    // Month labels in the middle of each month, thinned out so they never overlap.
    const tz = this._tz;
    const mesi = [];
    for (let c = addMesi(civile(new Date(t0), tz), 0); mezzanotte(c, tz).getTime() < t1; c = addMesi(c, 1)) mesi.push(c);
    const larghezzaMese = ((30 * DAY_MS) / (t1 - t0)) * Math.max(1, this._larghezza - 40);
    const passo = [1, 2, 3, 4, 6, 12].find((p) => p * larghezzaMese >= 34) || 12;
    const etichette = mesi
      .filter((c) => c.m % passo === 0)
      .map((c) => {
        const inizio = mezzanotte(c, tz);
        const centro = (inizio.getTime() + mezzanotte(addMesi(c, 1), tz).getTime()) / 2;
        // January shows the year, so the axis says where one year ends.
        const testo = c.m === 0 ? this._data(inizio, { year: "numeric" }) : this._data(inizio, { month: "short" });
        return { f: f(centro), testo };
      })
      .filter((e) => e.f > 0.02 && e.f < 0.98);

    return {
      voci,
      etichette,
      margine: 0.04,
      unita: `${this._unitaGiorno}/${lingua(this._hass) === "it" ? "giorno" : "day"}`,
      cifreAsse: this._gas ? undefined : 0,
      aria: t("chart_readings"),
      tooltip: (i, colore) => {
        const p = periodi[i];
        const riga = (nome, valore, puntino) => `<div class="tip-row">${puntino ? `<span class="tip-marker" style="background:${rgbCss(colore)}"></span>` : ""}
          <span class="tip-name">${escapeHtml(nome)}</span><span class="tip-value">${escapeHtml(valore)}</span></div>`;
        const titolo = `${this._giorno(p.dal)} - ${this._giorno(p.al, { day: "numeric", month: "short", year: "numeric" })}`;
        return `<div class="tip-title">${escapeHtml(titolo)}</div>`
          + riga(t("daily_average"), t("per_day_short", { value: `${this._giornaliero(p.media)} ${this._unitaGiorno}` }), true)
          + riga(t("consumption"), this._metriCubi(p.consumo))
          + riga(t("days"), String(p.giorni));
      },
    };
  }

  // Bars by month of the selected year, in cubic metres.
  _barreMesi() {
    const t = (k, v) => traduci(this._hass, k, v);
    if (this._anno === null) return null;
    const anno = this._anno;
    const valori = this._mesi?.anno === anno ? this._mesi.valori : Array(12).fill(null);
    const tz = this._tz;
    const letture = this._letture();
    const lettureDelMese = (m) => letture.filter((l) => l.giorno.startsWith(`${anno}-${String(m + 1).padStart(2, "0")}`));
    const voci = valori.map((v, m) => ({ f0: m / 12, f1: (m + 1) / 12, valore: v, lettura: lettureDelMese(m).length > 0 }));
    const stretta = this._larghezza < 360;
    const etichette = valori.map((_, m) => ({
      f: (m + 0.5) / 12,
      testo: this._data(mezzanotte({ y: anno, m, d: 1 }, tz), { month: stretta ? "narrow" : "short" }),
    }));
    const totale = valori.reduce((a, v) => a + (v || 0), 0);
    return {
      voci,
      etichette,
      margine: 0.15,
      unita: "m³",
      aria: t("chart_months", { period: String(anno), value: this._metriCubi(totale) }),
      tooltip: (m, colore) => {
        const v = valori[m];
        const inizio = mezzanotte({ y: anno, m, d: 1 }, tz).getTime();
        const giorni = this._giorniConDati(inizio, mezzanotte(addMesi({ y: anno, m, d: 1 }, 1), tz).getTime());
        const righe = [`<div class="tip-row"><span class="tip-marker" style="background:${rgbCss(colore)}"></span>
          <span class="tip-name">${escapeHtml(t("consumption"))}</span><span class="tip-value">${this._metriCubi(v)}</span></div>`];
        if (giorni) {
          const media = `${this._giornaliero((v / giorni) * this._fattoreGiorno)} ${this._unitaGiorno}`;
          righe.push(`<div class="tip-row"><span class="tip-name">${escapeHtml(t("daily_average"))}</span>
            <span class="tip-value">${escapeHtml(t("per_day_short", { value: media }))}</span></div>`);
        }
        for (const l of lettureDelMese(m)) {
          righe.push(`<div class="tip-row tip-reading"><span class="tip-name">${escapeHtml(t("reading_of", { date: this._giorno(l.giorno) }))}</span>
            <span class="tip-value">${this._metriCubi(l.valore)}</span></div>`);
        }
        const titolo = this._data(new Date(inizio), { month: "long", year: "numeric" });
        return `<div class="tip-title">${escapeHtml(titolo)}</div>${righe.join("")}`;
      },
    };
  }
}

const STILE = `
  :host { display: block; }
  ha-card { height: 100%; overflow: hidden; }
  .empty-card { padding: var(--ha-space-4, 16px); }
  .error:empty { display: none; }
  ha-alert { display: block; }

  .header {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 16px 0; cursor: pointer; outline: none;
    border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
  }
  .header:focus-visible, .hero:focus-visible { box-shadow: inset 0 0 0 2px var(--acegas-accent); }
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
  .hero {
    display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 8px 12px;
    cursor: pointer; outline: none; border-radius: var(--ha-border-radius-md, 8px);
  }
  .hero-text { min-width: 0; }
  .hero-main { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; }
  .hero-value {
    font-size: var(--ha-font-size-4xl, 32px); font-weight: var(--ha-font-weight-normal, 400);
    line-height: var(--ha-line-height-condensed, 1.2); color: var(--primary-text-color);
    font-variant-numeric: tabular-nums;
  }
  .hero-unit { font-size: var(--ha-font-size-m, 14px); color: var(--secondary-text-color); }
  .hero-sub {
    margin-top: 2px; font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px;
    color: var(--secondary-text-color);
  }

  /* Comparison with the previous period, tinted like ha-alert */
  .trend {
    --trend-color: var(--success-color, #43a047);
    position: relative; display: inline-flex; align-items: center; gap: 4px; overflow: hidden;
    height: 28px; padding: 0 10px 0 8px; box-sizing: border-box;
    border-radius: var(--ha-border-radius-pill, 9999px);
    font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500);
    color: var(--primary-text-color); white-space: nowrap;
  }
  .trend.su { --trend-color: var(--warning-color, #ffa600); }
  .trend[hidden] { display: none; }
  .trend::before { content: ""; position: absolute; inset: 0; background: var(--trend-color); opacity: 0.15; }
  .trend ha-icon { position: relative; --mdc-icon-size: 16px; color: var(--trend-color); }
  .trend span { position: relative; }

  /* like ha-control-select */
  .segmented {
    --control-select-color: var(--primary-color);
    position: relative; display: flex; gap: 4px; padding: 4px; box-sizing: border-box;
    height: 40px; border-radius: var(--ha-border-radius-lg, 12px);
  }
  .segmented::before {
    content: ""; position: absolute; inset: 0; border-radius: inherit;
    background: var(--disabled-color, #bdbdbd); opacity: 0.2;
  }
  .option {
    position: relative; flex: 1; min-width: 0; height: 100%; padding: 0 4px;
    display: flex; align-items: center; justify-content: center;
    border: none; background: none; cursor: pointer; outline: 0;
    border-radius: calc(var(--ha-border-radius-lg, 12px) - 4px);
    font-family: inherit; font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500); color: var(--primary-text-color);
    transition: box-shadow 180ms ease-in-out; -webkit-tap-highlight-color: transparent;
  }
  .option::before {
    content: ""; position: absolute; inset: 0; border-radius: inherit;
    background-color: var(--control-select-color); opacity: 0;
    transition: background-color 180ms ease-in-out, opacity 80ms ease-in-out;
  }
  .option:hover::before { opacity: 0.2; }
  .option:focus-visible { box-shadow: 0 0 0 2px var(--control-select-color); }
  .option.selected { color: var(--text-primary-color, #fff); }
  .option.selected::before { opacity: 1; }
  .option span { position: relative; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .nav { display: flex; align-items: center; margin: -8px -12px -4px; }
  .nav ha-icon-button { --mdc-icon-button-size: 40px; color: var(--primary-text-color); }
  .nav ha-icon-button[disabled] { color: var(--disabled-text-color); }
  .nav ha-icon-button.nascosta { visibility: hidden; }
  .period {
    flex: 1; text-align: center; font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500); color: var(--primary-text-color);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .period::first-letter { text-transform: uppercase; }

  .chart { position: relative; min-height: 192px; margin: 0 -4px; touch-action: pan-y; }
  .chart.loading svg { opacity: 0.4; transition: opacity 120ms ease-in-out; }
  svg { display: block; overflow: visible; }
  svg text { font-size: 12px; fill: var(--primary-text-color); }
  svg .ylab { text-anchor: end; }
  svg .unita { fill: var(--secondary-text-color); }
  svg .xlab { text-anchor: middle; }
  svg .grid { stroke: var(--divider-color); stroke-width: 1; }
  svg .hover-band { fill: var(--secondary-text-color); opacity: 0.1; }
  svg .reading { fill: var(--secondary-text-color); }
  svg .hit { fill: transparent; cursor: default; }
  .no-data {
    position: absolute; inset: 0 0 22px 32px; display: flex; align-items: center; justify-content: center;
    text-align: center; color: var(--secondary-text-color); font-size: var(--ha-font-size-m, 14px);
    pointer-events: none;
  }

  /* Year total and year average */
  .stats {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px;
    padding-top: 12px; border-top: 1px solid var(--divider-color);
  }
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
  .tip-reading { border-top: 1px solid var(--divider-color); margin-top: 4px; padding-top: 4px; color: var(--secondary-text-color); }
  .tip-reading .tip-value { color: var(--primary-text-color); }

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
  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  connectedCallback() {
    caricaHaForm().then(() => customElements.whenDefined("ha-form")).then(() => this._render());
  }

  _schema() {
    const t = (k) => traduci(this._hass, k);
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
      {
        name: "view",
        selector: { select: { mode: "dropdown", options: VISTE.map((v) => ({ value: v, label: t(v) })) } },
      },
      { name: "decimals", selector: { number: { min: 0, max: MAX_DECIMALI, step: 1, mode: "box" } } },
    ];
  }

  _render() {
    if (!this._hass || !this._config || !customElements.get("ha-form")) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...ev.detail.value };
        // An emptied field leaves the option out; the default chart is not written.
        for (const k of Object.keys(config)) if (config[k] === "" || config[k] == null) delete config[k];
        if (config.view === VISTA_PREDEFINITA) delete config.view;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    const etichette = {
      device_id: "ed_device", name: "ed_name", icon: "ed_icon", view: "ed_view", decimals: "ed_decimals",
    };
    this._form.hass = this._hass;
    this._form.data = {
      device_id: trovaContatori(this._hass)[0]?.deviceId,
      view: VISTA_PREDEFINITA,
      ...this._config,
    };
    this._form.schema = this._schema();
    this._form.computeLabel = (s) => traduci(this._hass, etichette[s.name] || s.name);
    this._form.computeHelper = (s) => (s.name === "decimals" ? traduci(this._hass, "ed_decimals_helper") : undefined);
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
