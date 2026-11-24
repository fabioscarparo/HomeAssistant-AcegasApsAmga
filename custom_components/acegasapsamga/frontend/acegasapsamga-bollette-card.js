/*
 * AcegasApsAmga bills and account overview card.
 *
 * Served by the integration (lovelace_card.py), no resource to add by hand.
 *
 * Aggregates bills across all AcegasApsAmga contracts (deduplicating grouped
 * PLICO bills by number) or scopes to one device_id. Shows the current balance
 * due, a calendar year selector with utility filter chips, bills organized by
 * utility service (Water, Gas, Electricity, District heating, Waste / TARI,
 * Combined bills) or chronologically, annual totals, unread portal
 * notifications, and password expiration warnings.
 *
 * All data comes from the integration's sensor attributes. Plain web component
 * in one file, zero dependencies.
 */

const CARD_TYPE = "acegasapsamga-bollette-card";
const EDITOR_TYPE = "acegasapsamga-bollette-card-editor";
const VERSION = "0.4.2";
const DOMAIN = "acegasapsamga";
const DEFAULT_MAX_BILLS = 8;
const URL_CONFIGURA = "/_my_redirect/config_flow_start?domain=acegasapsamga";
const STATI_DA_PAGARE = ["unpaid", "expired", "paid_partial"];
const ORDINE_SERVIZI = ["WATER", "GAS", "ELECTRIC", "HEATING", "ENVIRONMENT"];

const STRINGS = {
  it: {
    card_name: "AcegasApsAmga · Bollette e Account",
    card_description: "Saldo da pagare, bollette ordinate per servizio (acqua, gas, luce, TLR, TARI), notifiche e scadenza password.",
    title: "Bollette",
    all_paid: "Tutto pagato",
    all_paid_sub: "Nessuna bolletta aperta",
    due_total: "da pagare",
    bills_open: "{count} aperte",
    bill_open: "1 aperta",
    overdue_summary: "{count} scaduta ({amount})",
    overdue_summary_many: "{count} scadute ({amount})",
    next_due: "Entro il {date}",
    direct_debit_on: "Addebito il {date}",
    overdue_since: "Scaduta il {date}",
    all_services: "Tutte",
    total_year: "Totale {year}",
    total_service_year: "{service} {year}",
    bills_year_label: "Bollette {year}",
    bills_count: "{count} bollette",
    bill_count_one: "1 bolletta",
    previous: "Anno precedente",
    next: "Anno successivo",
    group_service: "Per servizio",
    group_date: "Cronologico",
    no_bills_year: "Nessuna bolletta nel {year}.",
    no_bills_filter: "Nessuna bolletta {service} nel {year}.",
    paid_on: "Pagata il {date}",
    paid_plain: "Pagata",
    due_on: "Da pagare entro il {date}",
    due_plain: "Da pagare",
    partly_paid: "Pagata in parte",
    issued_on: "Emessa il {date}",
    credit_label: "A credito",
    installment_label: "Rateizzata",
    reversed_label: "Stornata",
    not_to_pay_label: "Non da pagare",
    share_of_bill: "Quota su plico {total}",
    show_more: "Mostra altre {count}",
    show_more_one: "Mostra un'altra",
    show_less: "Mostra meno",
    pwd_warning: "Password portale in scadenza tra {days} giorni",
    pwd_expired: "Password portale scaduta o da rinnovare",
    notif_unread: "{count} notifiche non lette",
    notif_unread_one: "1 notifica non letta",
    not_configured_title: "Integrazione non configurata",
    not_configured_text: "Aggiungi l'integrazione AcegasApsAmga per vedere qui bollette e stato account.",
    not_configured_sub: "Non configurata",
    empty_title: "Nessuna bolletta disponibile",
    empty_text: "L'integrazione è configurata ma non ci sono ancora bollette associate ai contratti.",
    empty_sub: "In attesa di bollette",
    device_not_found_title: "Contratto non trovato",
    device_not_found_text: "Il contratto selezionato per questa card non è più disponibile. Scegline un altro dalle impostazioni.",
    device_not_found_sub: "Dispositivo non disponibile",
    ask_admin: "Chiedi a un amministratore di farlo.",
    configure: "Configura",
    svc_WATER: "Acqua",
    svc_GAS: "Gas",
    svc_ELECTRIC: "Luce",
    svc_HEATING: "Teleriscaldamento",
    svc_ENVIRONMENT: "TARI",
    svc_OTHER: "Altre",
    ed_device: "Contratto (opzionale, vuoto = tutti)",
    ed_name: "Nome",
    ed_icon: "Icona",
    ed_group_by: "Ordine bollette",
    ed_max_bills: "Bollette visibili per anno",
  },
  en: {
    card_name: "AcegasApsAmga · Bills & Account",
    card_description: "Amount due, bills grouped by utility (water, gas, electricity, heating, waste), notifications and password expiry.",
    title: "Bills",
    all_paid: "All paid",
    all_paid_sub: "No open bills",
    due_total: "due",
    bills_open: "{count} open",
    bill_open: "1 open",
    overdue_summary: "{count} overdue ({amount})",
    overdue_summary_many: "{count} overdue ({amount})",
    next_due: "Due {date}",
    direct_debit_on: "Direct debit {date}",
    overdue_since: "Overdue since {date}",
    all_services: "All",
    total_year: "{year} total",
    total_service_year: "{service} {year}",
    bills_year_label: "{year} bills",
    bills_count: "{count} bills",
    bill_count_one: "1 bill",
    previous: "Previous year",
    next: "Next year",
    group_service: "By service",
    group_date: "Chronological",
    no_bills_year: "No bills in {year}.",
    no_bills_filter: "No {service} bills in {year}.",
    paid_on: "Paid {date}",
    paid_plain: "Paid",
    due_on: "Due {date}",
    due_plain: "Unpaid",
    partly_paid: "Partly paid",
    issued_on: "Issued {date}",
    credit_label: "Credit",
    installment_label: "Installment",
    reversed_label: "Reversed",
    not_to_pay_label: "Not to pay",
    share_of_bill: "Share of {total} bill",
    show_more: "Show {count} more",
    show_more_one: "Show 1 more",
    show_less: "Show less",
    pwd_warning: "Portal password expires in {days} days",
    pwd_expired: "Portal password expired or renewal required",
    notif_unread: "{count} unread notifications",
    notif_unread_one: "1 unread notification",
    not_configured_title: "Integration not set up",
    not_configured_text: "Add the AcegasApsAmga integration to see bills and account alerts here.",
    not_configured_sub: "Not configured",
    empty_title: "No bills available yet",
    empty_text: "The integration is set up, but no bills have been found for your contracts yet.",
    empty_sub: "Waiting for bills",
    device_not_found_title: "Contract not found",
    device_not_found_text: "The contract selected for this card is no longer available. Choose another in card settings.",
    device_not_found_sub: "Device unavailable",
    ask_admin: "Ask an administrator to do it.",
    configure: "Set up",
    svc_WATER: "Water",
    svc_GAS: "Gas",
    svc_ELECTRIC: "Electricity",
    svc_HEATING: "District heating",
    svc_ENVIRONMENT: "Waste",
    svc_OTHER: "Other",
    ed_device: "Contract (optional, empty = all)",
    ed_name: "Name",
    ed_icon: "Icon",
    ed_group_by: "Bill grouping",
    ed_max_bills: "Bills shown per year",
  },
};

const ICONE_SERVIZI = {
  WATER: "mdi:water",
  GAS: "mdi:fire",
  ELECTRIC: "mdi:lightning-bolt",
  HEATING: "mdi:radiator",
  ENVIRONMENT: "mdi:trash-can",
  COMBINED: "mdi:layers-outline",
  OTHER: "mdi:receipt-text-outline",
};

const lingua = (hass) => ((hass?.locale?.language || hass?.language || "en").toLowerCase().startsWith("it") ? "it" : "en");

const traduci = (hass, key, vars = {}) => {
  let s = STRINGS[lingua(hass)][key] ?? STRINGS.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, () => String(v));
  return lingua(hass) === "it" ? elidi(s) : s;
};

// "il 1 dic" / "il 8 dic" becomes "l'1 dic" / "l'8 dic": Italian elides the article before 1, 8 and 11.
const ELISIONI = { il: "l'", Il: "L'", al: "all'", Al: "All'", dal: "dall'", Dal: "Dall'" };
const elidi = (s) => s.replace(/\b(il|Il|al|Al|dal|Dal) (?=(?:1|8|11)(?!\d))/g, (_, articolo) => ELISIONI[articolo]);

const naviga = (percorso) => {
  history.pushState(null, "", percorso);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
};

const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const valido = (stato) => !!stato && !["unavailable", "unknown", ""].includes(stato.state);
const _nfCache = new Map();
const _dfCache = new Map();

const numberFormatter = (locale, opzioni) => {
  const chiave = `${locale || ""}|${opzioni.style || "decimal"}|${opzioni.currency || ""}|${opzioni.useGrouping}`;
  let nf = _nfCache.get(chiave);
  if (!nf) {
    if (_nfCache.size >= 64) _nfCache.clear();
    nf = new Intl.NumberFormat(locale, opzioni);
    _nfCache.set(chiave, nf);
  }
  return nf;
};

const dateFormatter = (lang, tz, opzioni) => {
  const chiave = `${lang}|${tz || ""}|${opzioni.day || ""}|${opzioni.month || ""}|${opzioni.year || ""}`;
  let df = _dfCache.get(chiave);
  if (!df) {
    if (_dfCache.size >= 64) _dfCache.clear();
    df = new Intl.DateTimeFormat(lang, tz ? { timeZone: tz, ...opzioni } : opzioni);
    _dfCache.set(chiave, df);
  }
  return df;
};

const oggiNelFuso = (tz) => {
  const parti = {};
  for (const { type, value } of dateFormatter("en-US", tz, { year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date())) {
    parti[type] = value;
  }
  return `${parti.year}-${parti.month}-${parti.day}`;
};

const ordinaChiavi = (chiavi, ordine) => {
  const set = new Set(chiavi);
  const principali = ordine.filter((k) => set.has(k));
  const extra = [...set].filter((k) => !ordine.includes(k)).sort();
  return [...principali, ...extra];
};

const trovaEntita = (hass) => {
  const perDispositivo = new Map();
  const account = {};
  for (const e of Object.values(hass?.entities || {})) {
    if (e.platform !== DOMAIN || !e.translation_key) continue;
    if (e.translation_key === "scadenza_password" || e.translation_key === "notifiche") {
      account[e.translation_key] = e.entity_id;
      continue;
    }
    if (!e.device_id) continue;
    if (["bolletta", "da_pagare", "scadenza_bolletta", "lettura", "svuotamenti_rifiuti"].includes(e.translation_key)) {
      if (!perDispositivo.has(e.device_id)) perDispositivo.set(e.device_id, {});
      perDispositivo.get(e.device_id)[e.translation_key] = e.entity_id;
    }
  }
  const contratti = [];
  for (const [deviceId, entita] of perDispositivo) {
    if (!entita.bolletta) continue;
    const device = hass.devices?.[deviceId];
    contratti.push({ deviceId, entita, nome: device?.name_by_user || device?.name || deviceId });
  }
  return { contratti: contratti.sort((a, b) => a.nome.localeCompare(b.nome)), account };
};

class AcegasBolletteCard extends HTMLElement {
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
    this._filtroServizio = null;
    this._espanso = false;
    this._firma = "";
  }

  setConfig(config) {
    const max = config.max_bills;
    if (max !== undefined && max !== null && !(Number.isInteger(max) && max >= 1 && max <= 50)) {
      throw new Error("max_bills: 1-50");
    }
    if (config.group_by !== undefined && config.group_by !== null && !["service", "date"].includes(config.group_by)) {
      throw new Error("group_by: service | date");
    }
    if (config.device_id !== this._config.device_id) {
      this._anno = null;
      this._filtroServizio = null;
      this._espanso = false;
    }
    if (config.group_by !== this._config.group_by) {
      this._espanso = false;
    }
    this._config = { ...config };
    this._firma = "";
    this._render();
  }

  set hass(hass) {
    if (this._da !== hass.entities) {
      this._mappa = trovaEntita(hass);
      this._da = hass.entities;
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

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  get _contrattiAttivi() {
    const lista = this._mappa?.contratti || [];
    if (this._config.device_id) {
      return lista.filter((c) => c.deviceId === this._config.device_id);
    }
    return lista;
  }

  // How many utilities the card covers: with one, rows need not name it.
  get _serviziCarta() {
    return new Set(this._contrattiAttivi.map((c) => this._servizioContratto(c)).filter(Boolean)).size;
  }

  get _modalitaGruppo() {
    return this._config.group_by || "service";
  }

  _servizioContratto(c) {
    const bol = this._hass?.states?.[c.entita.bolletta];
    if (bol?.attributes?.servizio) return bol.attributes.servizio;
    const letStato = c.entita.lettura ? this._hass?.states?.[c.entita.lettura] : null;
    if (letStato?.attributes?.servizio) return letStato.attributes.servizio;
    if (letStato?.attributes?.device_class === "water") return "WATER";
    if (letStato?.attributes?.device_class === "gas") return "GAS";
    if (c.entita.svuotamenti_rifiuti) return "ENVIRONMENT";
    return null;
  }

  _firmaVista() {
    const h = this._hass;
    const ids = [
      ...this._contrattiAttivi.flatMap((c) => Object.values(c.entita)),
      ...Object.values(this._mappa?.account || {}),
    ];
    const stati = ids.map((id) => {
      const s = h.states?.[id];
      return s ? `${s.state}@${s.last_updated}` : "";
    });
    return [
      this._config.device_id,
      this._config.max_bills,
      this._config.group_by,
      h.themes?.theme,
      h.themes?.darkMode,
      h.locale?.language || h.language,
      h.locale?.number_format,
      (h.config?.components || []).includes(DOMAIN),
      h.user?.is_admin,
      ...stati,
    ].join("|");
  }

  _bolletteAggregate() {
    const perNumero = new Map();
    for (const c of this._contrattiAttivi) {
      const stato = this._hass?.states?.[c.entita.bolletta];
      const servizioContratto = this._servizioContratto(c);
      const lista = stato?.attributes?.bollette || [];
      for (const b of lista) {
        if (!b.numero) continue;
        if (!perNumero.has(b.numero)) {
          perNumero.set(b.numero, {
            ...b,
            _entityId: c.entita.bolletta,
            _servizio: servizioContratto,
          });
        }
      }
    }
    return [...perNumero.values()].sort((a, b) =>
      String(b.emissione || "").localeCompare(String(a.emissione || "")) || String(b.numero).localeCompare(String(a.numero))
    );
  }

  // The utility of a bill; a bill that groups several is filed under all of them
  // together ("WATER+GAS"), OTHER when nothing says.
  _categoriaBolletta(b) {
    const mappa = b.importi_servizi;
    if (mappa && typeof mappa === "object") {
      const attivi = ordinaChiavi(
        Object.entries(mappa).filter(([, v]) => Math.abs(Number(v) || 0) > 0).map(([k]) => k),
        ORDINE_SERVIZI
      );
      if (attivi.length === 1) return attivi[0];
      if (attivi.length > 1) return attivi.join("+");
    }
    return b._servizio || "OTHER";
  }

  // Aggregates annual spend by utility service using companyServices splits or the contract's service.
  _spesaPerServizio(bolletteAnno) {
    const perServizio = {};
    for (const b of bolletteAnno) {
      if (b.stato === "reversed") continue;
      const segno = b.stato === "credit" ? -1 : 1;
      const mappa = b.importi_servizi;
      if (mappa && Object.keys(mappa).length) {
        for (const [k, v] of Object.entries(mappa)) {
          const val = Number(v) || 0;
          if (val !== 0) perServizio[k] = (perServizio[k] || 0) + segno * Math.abs(val);
        }
      } else if (b._servizio) {
        const val = Number(b.importo) || 0;
        if (val !== 0) perServizio[b._servizio] = (perServizio[b._servizio] || 0) + segno * Math.abs(val);
      }
    }
    const positivi = {};
    for (const k of ordinaChiavi(Object.keys(perServizio), ORDINE_SERVIZI)) {
      if (perServizio[k] > 0) positivi[k] = Math.round(perServizio[k] * 100) / 100;
    }
    return positivi;
  }

  get _tz() {
    return this._hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  }

  get _locale() {
    const lang = this._hass?.locale?.language || this._hass?.language || "it";
    const fmt = this._hass?.locale?.number_format;
    return { comma_decimal: "en-US", decimal_comma: "de", space_comma: "fr", quote_decimal: "de-CH", system: undefined }[fmt] ?? lang;
  }

  _euro(v) {
    return numberFormatter(this._locale, {
      style: "currency", currency: "EUR", useGrouping: this._hass?.locale?.number_format !== "none",
    }).format(Number(v) || 0);
  }

  _giorno(iso) {
    if (!iso) return "";
    const lang = this._hass?.locale?.language || this._hass?.language || "it";
    const [y, m, d] = String(iso).split("-").map(Number);
    return dateFormatter(lang, "UTC", { day: "numeric", month: "short", year: "numeric" }).format(new Date(Date.UTC(y, m - 1, d)));
  }

  _giornoBreve(iso) {
    if (!iso) return "";
    const lang = this._hass?.locale?.language || this._hass?.language || "it";
    const [y, m, d] = String(iso).split("-").map(Number);
    return dateFormatter(lang, "UTC", { day: "numeric", month: "short" }).format(new Date(Date.UTC(y, m - 1, d)));
  }

  _nomeServizio(codice) {
    if (String(codice).includes("+")) {
      // "Acqua e gas", "Water, gas and electricity": acronyms like TARI keep their case.
      const nomi = codice.split("+").map((k, i) => {
        const nome = this._nomeServizio(k);
        return i && nome !== nome.toUpperCase() ? nome.toLowerCase() : nome;
      });
      const e = lingua(this._hass) === "it" ? " e " : " and ";
      return `${nomi.slice(0, -1).join(", ")}${e}${nomi[nomi.length - 1]}`;
    }
    return STRINGS[lingua(this._hass)][`svc_${codice}`] || codice;
  }

  _render() {
    if (!this._hass) return;
    const contratti = this._contrattiAttivi;
    if (!contratti.length) {
      this._renderVuota(this._config.device_id ? "device_not_found" : "not_configured");
      return;
    }
    if (this._modo !== "card") this._struttura();

    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);

    const bollette = this._bolletteAggregate();
    const oggi = oggiNelFuso(this._tz);
    const aperte = bollette.filter((b) => STATI_DA_PAGARE.includes(b.stato) && (Number(b.residuo) || 0) > 0);
    const eScaduta = (b) => b.stato === "expired" || (!!b.scadenza && b.scadenza < oggi);
    const scadute = aperte.filter(eScaduta);
    const inScadenza = aperte.filter((b) => !eScaduta(b));
    const totaleDue = aperte.reduce((s, b) => s + (Number(b.residuo) || 0), 0);
    const tutteDom = aperte.length > 0 && aperte.every((b) => b.domiciliata);

    const accent = scadute.length > 0
      ? "var(--error-color, #db4437)"
      : "var(--primary-color, #03a9f4)";
    $("ha-card").style.setProperty("--acegas-bill", accent);

    const icona = this._config.icon || "mdi:receipt-text-outline";
    if ($(".icon ha-icon").getAttribute("icon") !== icona) $(".icon ha-icon").setAttribute("icon", icona);
    $(".header").dataset.entityId = contratti[0].entita.bolletta;
    $(".primary").textContent = this._config.name || (this._config.device_id ? contratti[0].nome : t("title"));

    const ultima = bollette[0];
    // Which utilities the card covers; for a single contract, how many bills it has.
    const servizi = ordinaChiavi(contratti.map((c) => this._servizioContratto(c)).filter(Boolean), ORDINE_SERVIZI);
    $(".secondary").textContent = !this._config.device_id && servizi.length
      ? servizi.map((k) => this._nomeServizio(k)).join(" · ")
      : bollette.length === 1 ? t("bill_count_one") : t("bills_count", { count: String(bollette.length) });

    // Balance hero
    const hero = $(".hero");
    hero.dataset.entityId = contratti[0].entita.da_pagare || contratti[0].entita.bolletta;
    if (totaleDue > 0) {
      $(".hero-value").textContent = this._euro(totaleDue);
      $(".hero-unit").textContent = t("due_total");
      const parti = [];
      if (scadute.length > 0) {
        const impScad = scadute.reduce((s, b) => s + (Number(b.residuo) || 0), 0);
        const key = scadute.length === 1 ? "overdue_summary" : "overdue_summary_many";
        parti.push(`<span class="overdue">${escapeHtml(t(key, { count: String(scadute.length), amount: this._euro(impScad) }))}</span>`);
        if (inScadenza.length > 0) {
          const dPross = inScadenza.map((b) => b.scadenza).filter(Boolean).sort()[0];
          const prossDom = inScadenza.every((b) => b.domiciliata);
          if (dPross) {
            parti.push(escapeHtml(prossDom
              ? t("direct_debit_on", { date: this._giornoBreve(dPross) })
              : t("next_due", { date: this._giornoBreve(dPross) })));
          }
        }
      } else {
        parti.push(escapeHtml(aperte.length === 1 ? t("bill_open") : t("bills_open", { count: String(aperte.length) })));
        const prossima = aperte.map((b) => b.scadenza).filter(Boolean).sort()[0];
        if (prossima) {
          parti.push(escapeHtml(tutteDom
            ? t("direct_debit_on", { date: this._giornoBreve(prossima) })
            : t("next_due", { date: this._giornoBreve(prossima) })));
        }
      }
      $(".hero-sub").innerHTML = parti.join(" · ");
    } else {
      $(".hero-value").textContent = t("all_paid");
      $(".hero-unit").textContent = "";
      $(".hero-sub").textContent = ultima?.data_pagamento
        ? `${t("all_paid_sub")} · ${t("paid_on", { date: this._giornoBreve(ultima.data_pagamento) })}`
        : t("all_paid_sub");
    }

    this._renderAvvisoPassword();

    const anni = [...new Set(bollette.map((b) => Number(String(b.emissione || "").slice(0, 4))).filter(Boolean))].sort((a, b) => a - b);
    const primoAnno = anni[0] || new Date().getFullYear();
    const ultimoAnno = anni[anni.length - 1] || new Date().getFullYear();
    if (this._anno === null || this._anno < primoAnno || this._anno > ultimoAnno) this._anno = ultimoAnno;

    const prev = $('[data-azione="prev"]');
    const next = $('[data-azione="next"]');
    prev.toggleAttribute("disabled", this._anno <= primoAnno);
    next.toggleAttribute("disabled", this._anno >= ultimoAnno);
    prev.setAttribute("label", t("previous"));
    next.setAttribute("label", t("next"));
    $(".period").textContent = String(this._anno);

    const dellAnno = bollette.filter((b) => String(b.emissione || "").startsWith(`${this._anno}-`));
    const perServizio = this._spesaPerServizio(dellAnno);
    if (this._filtroServizio && !perServizio[this._filtroServizio]) this._filtroServizio = null;

    this._renderFiltriServizio(perServizio, dellAnno);
    this._renderElenco(dellAnno, perServizio);
    this._renderNotifiche();
  }

  _renderAvvisoPassword() {
    const t = (k, v) => traduci(this._hass, k, v);
    const box = this.shadowRoot.querySelector(".pwd-alert");
    const pwdId = this._mappa?.account?.scadenza_password;
    const pwd = pwdId ? this._hass.states?.[pwdId] : null;
    if (!pwd || !valido(pwd)) {
      box.hidden = true;
      box.innerHTML = "";
      return;
    }
    const giorni = pwd.attributes?.giorni_rimanenti;
    const rinnovo = pwd.attributes?.rinnovo_richiesto === true;
    if (!rinnovo && !(typeof giorni === "number" && giorni <= 15)) {
      box.hidden = true;
      box.innerHTML = "";
      return;
    }
    const testo = rinnovo || giorni <= 0 ? t("pwd_expired") : t("pwd_warning", { days: String(giorni) });
    box.hidden = false;
    box.innerHTML = `<button type="button" class="pwd-btn" data-entity="${escapeHtml(pwdId)}">
      <ha-alert alert-type="warning">${escapeHtml(testo)}</ha-alert>
    </button>`;
    box.querySelector(".pwd-btn").addEventListener("click", () => this._moreInfo(pwdId));
  }

  _renderFiltriServizio(perServizio, dellAnno) {
    const barra = this.shadowRoot.querySelector(".chips");
    const servizi = Object.keys(perServizio);
    if (servizi.length < 2) {
      barra.hidden = true;
      barra.innerHTML = "";
      return;
    }
    barra.hidden = false;
    const t = (k) => traduci(this._hass, k);
    const attivo = this._filtroServizio;

    const voci = [
      { id: "", label: t("all_services") },
      ...servizi.map((k) => ({ id: k, label: this._nomeServizio(k) })),
    ];
    barra.innerHTML = voci.map((v) => {
      const selected = (attivo || "") === v.id;
      return `<button type="button" class="chip${selected ? " active" : ""}" data-svc="${escapeHtml(v.id)}" aria-pressed="${selected}">${escapeHtml(v.label)}</button>`;
    }).join("");

    barra.querySelectorAll(".chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        const prossimo = btn.dataset.svc || null;
        this._filtroServizio = this._filtroServizio === prossimo ? null : prossimo;
        this._espanso = false;
        this._renderFiltriServizio(perServizio, dellAnno);
        this._renderElenco(dellAnno, perServizio);
      });
    });
  }

  _statoTesto(b, oggi) {
    const t = (k, v) => traduci(this._hass, k, v);
    const scaduta = b.stato === "expired" || (STATI_DA_PAGARE.includes(b.stato) && !!b.scadenza && b.scadenza < oggi);
    if (scaduta) {
      return {
        testo: b.scadenza ? t("overdue_since", { date: this._giornoBreve(b.scadenza) }) : t("due_plain"),
        classe: "overdue",
      };
    }
    if (b.stato === "unpaid" || b.stato === "paid_partial") {
      if (b.domiciliata && b.scadenza) {
        return { testo: t("direct_debit_on", { date: this._giornoBreve(b.scadenza) }), classe: "" };
      }
      if (b.stato === "paid_partial") {
        return { testo: t("partly_paid"), classe: "due" };
      }
      return {
        testo: b.scadenza ? t("due_on", { date: this._giornoBreve(b.scadenza) }) : t("due_plain"),
        classe: "due",
      };
    }
    if (b.stato === "paid") {
      return {
        testo: b.data_pagamento ? t("paid_on", { date: this._giornoBreve(b.data_pagamento) }) : t("paid_plain"),
        classe: "",
      };
    }
    if (b.stato === "credit") return { testo: t("credit_label"), classe: "" };
    if (b.stato === "installment") return { testo: t("installment_label"), classe: "" };
    if (b.stato === "reversed") return { testo: t("reversed_label"), classe: "muted" };
    if (b.stato === "not_to_pay") return { testo: t("not_to_pay_label"), classe: "" };
    return { testo: t("issued_on", { date: this._giornoBreve(b.emissione) }), classe: "" };
  }

  _rigaBollettaHtml(b, oggi, { mostraServizi, filtro }) {
    const t = (k, v) => traduci(this._hass, k, v);
    const stato = this._statoTesto(b, oggi);
    const dettaglio = [];

    if (filtro && b.importi_servizi && Object.keys(b.importi_servizi).length > 1) {
      dettaglio.push(t("share_of_bill", { total: this._euro(b.importo) }));
    } else if (mostraServizi && b.importi_servizi && Object.keys(b.importi_servizi).length > 1) {
      dettaglio.push(
        ordinaChiavi(Object.keys(b.importi_servizi), ORDINE_SERVIZI)
          .map((k) => `${this._nomeServizio(k)} ${this._euro(b.importi_servizi[k])}`)
          .join(" · ")
      );
    } else if (mostraServizi && this._serviziCarta > 1) {
      const solo = Object.keys(b.importi_servizi || {})[0] || b._servizio;
      if (solo) dettaglio.push(this._nomeServizio(solo));
    }

    const valoreBase = filtro && b.importi_servizi?.[filtro] !== undefined
      ? Number(b.importi_servizi[filtro])
      : Number(b.importo) || 0;
    const valoreFirmato = b.stato === "credit" ? -Math.abs(valoreBase) : valoreBase;
    const classeImporto = b.stato === "reversed" ? " reversed" : "";
    const extraMeta = dettaglio.length ? ` · ${escapeHtml(dettaglio.join(" · "))}` : "";

    return `<li>
      <button type="button" class="bill-row" data-entity="${escapeHtml(b._entityId)}">
        <span class="row-main">
          <span class="bill-date">${escapeHtml(this._giorno(b.emissione))}</span>
          <span class="bill-meta"><span class="st ${stato.classe}">${escapeHtml(stato.testo)}</span>${extraMeta}</span>
        </span>
        <span class="bill-amount${classeImporto}">${escapeHtml(this._euro(valoreFirmato))}</span>
      </button>
    </li>`;
  }

  // Distributes visible slots round-robin across service groups so every utility stays represented.
  _selezionaPerGruppi(gruppi, limite) {
    const budget = Math.max(limite, gruppi.length);
    const quote = gruppi.map(() => 0);
    let presi = 0;
    let giro = 0;
    while (presi < budget) {
      let avanzato = false;
      for (let i = 0; i < gruppi.length && presi < budget; i++) {
        if (quote[i] < gruppi[i].bollette.length) {
          quote[i] += 1;
          presi += 1;
          avanzato = true;
        }
      }
      if (!avanzato || ++giro > budget) break;
    }
    return gruppi.map((g, i) => ({ ...g, visibili: g.bollette.slice(0, quote[i]) }));
  }

  _renderElenco(dellAnno, perServizio) {
    const t = (k, v) => traduci(this._hass, k, v);
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    const oggi = oggiNelFuso(this._tz);
    const filtro = this._filtroServizio;

    const filtrate = filtro
      ? dellAnno.filter((b) =>
        (b.importi_servizi && Object.prototype.hasOwnProperty.call(b.importi_servizi, filtro))
        || b._servizio === filtro)
      : dellAnno;

    const host = $(".bills-container");
    const moreBtn = $(".toggle-more");

    // Footer reflects current filter or full year.
    const totaleVisibile = filtro
      ? (perServizio[filtro] ?? 0)
      : dellAnno
        .filter((b) => b.stato !== "reversed")
        .reduce((s, b) => s + (b.stato === "credit" ? -Math.abs(Number(b.importo) || 0) : (Number(b.importo) || 0)), 0);
    $('[data-stat="totale"] .stat-label').textContent = filtro
      ? t("total_service_year", { service: this._nomeServizio(filtro), year: String(this._anno) })
      : t("total_year", { year: String(this._anno) });
    $('[data-stat="totale"] .stat-value').textContent = filtrate.length ? this._euro(totaleVisibile) : "-";
    $('[data-stat="conteggio"] .stat-label').textContent = t("bills_year_label", { year: String(this._anno) });
    $('[data-stat="conteggio"] .stat-value').textContent = String(filtrate.length);

    if (!filtrate.length) {
      host.innerHTML = `<div class="empty-year">${escapeHtml(
        filtro
          ? t("no_bills_filter", { service: this._nomeServizio(filtro), year: String(this._anno) })
          : t("no_bills_year", { year: String(this._anno) })
      )}</div>`;
      moreBtn.hidden = true;
      return;
    }

    const categorieUniche = new Set(filtrate.map((b) => this._categoriaBolletta(b)));
    const raggruppaPerServizio = !filtro && this._modalitaGruppo === "service" && categorieUniche.size >= 2;
    const limiteBase = this._config.max_bills || DEFAULT_MAX_BILLS;
    let nascoste = 0;

    if (raggruppaPerServizio) {
      const mappa = new Map();
      for (const b of filtrate) {
        const cat = this._categoriaBolletta(b);
        if (!mappa.has(cat)) mappa.set(cat, []);
        mappa.get(cat).push(b);
      }
      // Single utilities first, then bills that group several, then the rest.
      const chiavi = [...mappa.keys()];
      const ordine = [
        ...ordinaChiavi(chiavi.filter((k) => !k.includes("+") && k !== "OTHER"), ORDINE_SERVIZI),
        ...chiavi.filter((k) => k.includes("+")).sort(),
        ...chiavi.filter((k) => k === "OTHER"),
      ];
      const gruppi = ordine.map((cat) => {
        const lista = mappa.get(cat);
        const subtot = lista
          .filter((b) => b.stato !== "reversed")
          .reduce((s, b) => s + (b.stato === "credit" ? -Math.abs(Number(b.importo) || 0) : (Number(b.importo) || 0)), 0);
        return { cat, bollette: lista, subtot };
      });
      const resi = this._espanso
        ? gruppi.map((g) => ({ ...g, visibili: g.bollette }))
        : this._selezionaPerGruppi(gruppi, limiteBase);
      nascoste = filtrate.length - resi.reduce((s, g) => s + g.visibili.length, 0);

      host.innerHTML = resi.map((g) => {
        const combinata = g.cat.includes("+");
        const icona = ICONE_SERVIZI[g.cat] || (combinata ? ICONE_SERVIZI.COMBINED : ICONE_SERVIZI.OTHER);
        const mostraServizi = combinata || g.cat === "OTHER";
        return `<section class="cat-group">
          <div class="cat-header">
            <ha-icon class="cat-icon" icon="${icona}"></ha-icon>
            <span class="cat-name">${escapeHtml(this._nomeServizio(g.cat))}</span>
            <span class="cat-total">${escapeHtml(this._euro(g.subtot))}</span>
          </div>
          <ul class="bills-list">
            ${g.visibili.map((b) => this._rigaBollettaHtml(b, oggi, { mostraServizi, filtro: null })).join("")}
          </ul>
        </section>`;
      }).join("");
    } else {
      const visibili = this._espanso ? filtrate : filtrate.slice(0, limiteBase);
      nascoste = filtrate.length - visibili.length;
      const mostraServizi = !this._config.device_id && !filtro;
      host.innerHTML = `<ul class="bills-list">
        ${visibili.map((b) => this._rigaBollettaHtml(b, oggi, { mostraServizi, filtro })).join("")}
      </ul>`;
    }

    host.querySelectorAll(".bill-row").forEach((btn) => {
      btn.addEventListener("click", () => this._moreInfo(btn.dataset.entity));
    });

    const eccedenti = filtrate.length - Math.min(filtrate.length, limiteBase);
    moreBtn.hidden = (!this._espanso && nascoste <= 0) || (this._espanso && eccedenti <= 0);
    if (!moreBtn.hidden) {
      moreBtn.setAttribute("aria-expanded", String(this._espanso));
      moreBtn.querySelector("span").textContent = this._espanso
        ? t("show_less")
        : nascoste === 1 ? t("show_more_one") : t("show_more", { count: String(nascoste) });
      moreBtn.querySelector("ha-icon").setAttribute("icon", this._espanso ? "mdi:chevron-up" : "mdi:chevron-down");
    }
  }

  _renderNotifiche() {
    const t = (k, v) => traduci(this._hass, k, v);
    const wrap = this.shadowRoot.querySelector(".notif-wrap");
    const btn = this.shadowRoot.querySelector(".notif-row");
    const notifId = this._mappa?.account?.notifiche;
    const notif = notifId ? this._hass.states?.[notifId] : null;
    if (!notif || !valido(notif) || !(Number(notif.state) > 0)) {
      wrap.hidden = true;
      return;
    }
    const n = Number(notif.state);
    wrap.hidden = false;
    btn.dataset.entityId = notifId;
    btn.querySelector(".notif-title").textContent = n === 1
      ? t("notif_unread_one")
      : t("notif_unread", { count: String(n) });
    const sub = btn.querySelector(".notif-sub");
    const anteprima = notif.attributes?.ultima_notifica || "";
    sub.textContent = anteprima;
    sub.hidden = !anteprima;
  }

  _renderVuota(chiave = "not_configured") {
    const configurata = (this._hass.config?.components || []).includes(DOMAIN);
    const quale = chiave === "not_configured" && configurata ? "empty" : chiave;
    const firma = `vuota-${quale}-${lingua(this._hass)}-${this._hass.user?.is_admin}-${this._config.name || ""}-${this._config.icon || ""}`;
    if (this._modo === firma) return;
    this._modo = firma;
    const t = (k) => traduci(this._hass, k);
    const admin = !!this._hass.user?.is_admin;
    const icona = this._config.icon || "mdi:receipt-text-outline";
    const titoloCard = this._config.name || t("title");
    const accent = quale === "device_not_found"
      ? "var(--warning-color, #ffa600)"
      : quale === "empty"
        ? "var(--primary-color, #03a9f4)"
        : "var(--state-inactive-color, var(--disabled-text-color, #9e9e9e))";
    const sottotitolo = quale === "device_not_found"
      ? t("device_not_found_sub")
      : quale === "empty" ? t("empty_sub") : t("not_configured_sub");
    const contenuto = quale === "device_not_found"
      ? `<ha-alert alert-type="warning" title="${escapeHtml(t("device_not_found_title"))}">${escapeHtml(t("device_not_found_text"))}</ha-alert>`
      : quale === "empty"
        ? `<ha-alert alert-type="info" title="${escapeHtml(t("empty_title"))}">${escapeHtml(t("empty_text"))}</ha-alert>`
        : `<ha-alert alert-type="info" title="${escapeHtml(t("not_configured_title"))}">
            ${escapeHtml(t("not_configured_text"))}${admin ? "" : ` ${escapeHtml(t("ask_admin"))}`}
            ${admin ? `<ha-button slot="action" data-percorso="${escapeHtml(URL_CONFIGURA)}">${escapeHtml(t("configure"))}</ha-button>` : ""}
          </ha-alert>`;
    this.shadowRoot.innerHTML = `<style>${STILE}</style>
      <ha-card style="--acegas-bill:${accent}">
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
          <button type="button" class="header">
            <div class="icon"><ha-icon></ha-icon></div>
            <div class="info">
              <div class="primary"></div>
              <div class="secondary"></div>
            </div>
          </button>
          <div class="content">
            <button type="button" class="hero">
              <div class="hero-main"><span class="hero-value"></span><span class="hero-unit"></span></div>
              <div class="hero-sub"></div>
            </button>
            <div class="pwd-alert" hidden></div>
            <div class="nav">
              <ha-icon-button data-azione="prev"><ha-icon icon="mdi:chevron-left"></ha-icon></ha-icon-button>
              <div class="period"></div>
              <ha-icon-button data-azione="next"><ha-icon icon="mdi:chevron-right"></ha-icon></ha-icon-button>
            </div>
            <div class="chips" hidden></div>
            <div class="bills-container"></div>
            <button type="button" class="toggle-more" hidden aria-expanded="false">
              <span></span><ha-icon icon="mdi:chevron-down"></ha-icon>
            </button>
            <div class="notif-wrap" hidden>
              <button type="button" class="notif-row">
                <ha-icon class="notif-ic" icon="mdi:bell-badge-outline"></ha-icon>
                <span class="notif-body">
                  <span class="notif-title"></span>
                  <span class="notif-sub"></span>
                </span>
                <ha-icon class="notif-chev" icon="mdi:chevron-right"></ha-icon>
              </button>
            </div>
            <footer class="stats">
              <div class="stat" data-stat="totale"><div class="stat-label"></div><div class="stat-value"></div></div>
              <div class="stat" data-stat="conteggio"><div class="stat-label"></div><div class="stat-value"></div></div>
            </footer>
          </div>
        </article>
      </ha-card>`;

    const root = this.shadowRoot;
    const sposta = (direzione) => {
      this._anno += direzione;
      this._filtroServizio = null;
      this._espanso = false;
      this._render();
    };
    root.querySelector('[data-azione="prev"]').addEventListener("click", () => sposta(-1));
    root.querySelector('[data-azione="next"]').addEventListener("click", () => sposta(1));
    root.querySelector(".header").addEventListener("click", (ev) => {
      this._moreInfo(ev.currentTarget.dataset.entityId);
    });
    root.querySelector(".hero").addEventListener("click", (ev) => {
      this._moreInfo(ev.currentTarget.dataset.entityId);
    });
    root.querySelector(".notif-row").addEventListener("click", (ev) => {
      this._moreInfo(ev.currentTarget.dataset.entityId);
    });
    root.querySelector(".toggle-more").addEventListener("click", () => {
      this._espanso = !this._espanso;
      const dellAnno = this._bolletteAggregate().filter((b) => String(b.emissione || "").startsWith(`${this._anno}-`));
      this._renderElenco(dellAnno, this._spesaPerServizio(dellAnno));
    });
  }

  _moreInfo(entityId) {
    if (!entityId) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
  }
}

const STILE = `
  :host { display: block; --acegas-bill: var(--primary-color, #03a9f4); }
  ha-card { height: 100%; overflow: hidden; }
  .card { display: block; }
  ha-alert { display: block; }
  [hidden] { display: none !important; }

  .header, .hero, .chip, .bill-row, .pwd-btn, .notif-row, .toggle-more {
    appearance: none; background: none; border: 0; font: inherit; color: inherit;
    text-align: start; padding: 0; margin: 0; width: 100%; box-sizing: border-box;
  }

  .header {
    display: flex; align-items: center; gap: 10px;
    padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px) 0; cursor: pointer; outline: none;
    border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
  }
  .header.static { cursor: default; }
  .header:focus-visible, .hero:focus-visible, .chip:focus-visible,
  .bill-row:focus-visible, .pwd-btn:focus-visible, .notif-row:focus-visible, .toggle-more:focus-visible {
    box-shadow: inset 0 0 0 2px var(--acegas-bill);
  }
  .icon {
    position: relative; flex: none; display: flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; overflow: hidden;
    border-radius: var(--ha-tile-icon-border-radius, var(--ha-border-radius-pill, 9999px));
    color: var(--acegas-bill); --mdc-icon-size: 24px;
  }
  .icon::before {
    content: ""; position: absolute; inset: 0;
    background-color: var(--acegas-bill); opacity: 0.2; transition: opacity 180ms ease-in-out;
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

  /* Balance hero */
  .hero { cursor: pointer; outline: none; border-radius: var(--ha-border-radius-md, 8px); }
  .hero-main { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; line-height: var(--ha-line-height-condensed, 1.2); }
  .hero-value { font-size: var(--ha-font-size-3xl, 28px); font-weight: var(--ha-font-weight-normal, 400); color: var(--primary-text-color); font-variant-numeric: tabular-nums; }
  .hero-unit { font-size: var(--ha-font-size-l, 16px); color: var(--secondary-text-color); }
  .hero-sub { margin-top: 2px; font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px; color: var(--secondary-text-color); }
  .hero-sub .overdue { color: var(--error-color, #db4437); font-weight: var(--ha-font-weight-medium, 500); }

  .pwd-btn { display: block; cursor: pointer; outline: none; border-radius: var(--ha-border-radius-md, 8px); }

  /* Year navigation */
  .nav { display: flex; align-items: center; margin: -4px -12px; }
  .nav ha-icon-button { --mdc-icon-button-size: 40px; color: var(--primary-text-color); }
  .nav ha-icon-button[disabled] { color: var(--disabled-text-color); }
  .period {
    flex: 1; text-align: center; font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500); color: var(--primary-text-color);
    font-variant-numeric: tabular-nums;
  }

  /* Neutral utility filter chips */
  .chips { display: flex; flex-wrap: wrap; gap: 8px 6px; }
  .chip, .bill-row, .toggle-more, .notif-row { position: relative; isolation: isolate; }
  .chip::before, .bill-row::before, .toggle-more::before, .notif-row::before {
    content: ""; position: absolute; inset: 0; z-index: -1; border-radius: inherit; pointer-events: none;
    background: var(--primary-text-color); opacity: 0; transition: opacity 140ms ease;
  }
  .chip {
    width: auto; min-height: 32px; padding: 0 12px; cursor: pointer; outline: none;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: var(--ha-border-radius-pill, 9999px);
    font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500);
    color: var(--secondary-text-color); transition: color 140ms ease;
  }
  /* 40px to tap, 32px to see */
  .chip::after { content: ""; position: absolute; inset: -4px 0; }
  .chip::before { background: var(--disabled-color, #bdbdbd); opacity: 0.2; }
  .chip:hover { color: var(--primary-text-color); }
  .chip:hover::before { opacity: 0.32; }
  .chip.active { color: var(--primary-color, #03a9f4); }
  .chip.active::before { background: var(--primary-color, #03a9f4); opacity: 0.16; }

  /* Categorized bill sections */
  .bills-container { display: flex; flex-direction: column; gap: var(--ha-space-4, 16px); }
  .cat-group { display: flex; flex-direction: column; }
  .cat-header {
    display: flex; align-items: center; gap: 6px; padding-bottom: 6px;
    color: var(--secondary-text-color);
  }
  .cat-icon { flex: none; --mdc-icon-size: 16px; color: var(--secondary-text-color); }
  .cat-name {
    font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500);
    line-height: 16px; letter-spacing: 0.4px; color: var(--secondary-text-color);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .cat-total {
    margin-inline-start: auto; font-size: var(--ha-font-size-s, 12px); line-height: 16px;
    color: var(--secondary-text-color); font-variant-numeric: tabular-nums; white-space: nowrap;
  }

  /* Clean typography-first bill rows */
  .bills-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
  .bills-list li { border-top: 1px solid var(--divider-color); }
  .empty-year { padding: 14px 0; text-align: center; font-size: var(--ha-font-size-m, 14px); color: var(--secondary-text-color); }

  .bill-row {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    min-height: 48px; padding: 8px 6px; margin: 0 -6px; width: calc(100% + 12px);
    cursor: pointer; outline: none; border-radius: var(--ha-border-radius-md, 8px);
  }
  .bill-row:hover::before, .notif-row:hover::before { opacity: 0.06; }

  .row-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .bill-date {
    font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500);
    line-height: 20px; color: var(--primary-text-color);
  }
  .bill-meta {
    font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--secondary-text-color);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .st.overdue { color: var(--error-color, #db4437); font-weight: var(--ha-font-weight-medium, 500); }
  .st.due { color: var(--primary-text-color); font-weight: var(--ha-font-weight-medium, 500); }
  .st.muted { color: var(--disabled-text-color); }

  .bill-amount {
    flex: none; font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500);
    line-height: 20px; color: var(--primary-text-color); font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .bill-amount.reversed { color: var(--disabled-text-color); text-decoration: line-through; }

  /* Neutral expand button */
  .toggle-more {
    display: flex; align-items: center; justify-content: center; gap: 6px;
    min-height: 42px; padding: 0 12px; cursor: pointer; outline: none;
    border-radius: var(--ha-card-features-border-radius, var(--ha-border-radius-md, 8px));
    font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500);
    color: var(--primary-text-color); --mdc-icon-size: 18px;
  }
  .toggle-more::before { background: var(--disabled-color, #bdbdbd); opacity: 0.2; }
  .toggle-more:hover::before { opacity: 0.32; }

  /* Quiet notifications link row */
  .notif-wrap {
    padding-top: var(--ha-space-2, 8px);
    border-top: 1px solid var(--divider-color);
  }
  .notif-row {
    display: flex; align-items: center; gap: 10px; min-height: 44px;
    padding: 6px; margin: 0 -6px; width: calc(100% + 12px);
    cursor: pointer; outline: none;
    border-radius: var(--ha-border-radius-md, 8px);
  }
  .notif-ic { flex: none; --mdc-icon-size: 20px; color: var(--secondary-text-color); }
  .notif-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .notif-title {
    font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500);
    line-height: 16px; color: var(--primary-text-color);
  }
  .notif-sub {
    font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--secondary-text-color);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .notif-chev { flex: none; --mdc-icon-size: 18px; color: var(--secondary-text-color); }

  /* Annual footer summary */
  .stats {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px;
    padding-top: var(--ha-space-3, 12px); border-top: 1px solid var(--divider-color);
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

class AcegasBolletteCardEditor extends HTMLElement {
  constructor() {
    super();
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
        name: "group_by",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "service", label: t("group_service") },
              { value: "date", label: t("group_date") },
            ],
          },
        },
      },
      { name: "max_bills", selector: { number: { min: 1, max: 50, step: 1, mode: "box" } } },
    ];
  }

  _render() {
    if (!this._connected || !this._hass || !this._config || !customElements.get("ha-form")) return;
    const etichette = {
      device_id: "ed_device", name: "ed_name", icon: "ed_icon",
      group_by: "ed_group_by", max_bills: "ed_max_bills",
    };
    const lang = lingua(this._hass);
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => traduci(this._hass, etichette[s.name] || s.name);
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...ev.detail.value };
        for (const k of Object.keys(config)) if (config[k] === "" || config[k] == null) delete config[k];
        if (config.group_by === "service") delete config.group_by;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    const firma = `${lang}|${JSON.stringify(this._config)}`;
    if (firma !== this._ultimoStatoForm) {
      this._ultimoStatoForm = firma;
      this._form.schema = this._schema();
      this._form.data = { group_by: "service", ...this._config };
    }
  }
}

const registraElementi = () => {
  const registro = window.customElements;
  if (!registro.get(CARD_TYPE)) registro.define(CARD_TYPE, AcegasBolletteCard);
  if (!registro.get(EDITOR_TYPE)) registro.define(EDITOR_TYPE, AcegasBolletteCardEditor);
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

console.info(`%c ACEGASAPSAMGA BOLLETTE CARD %c ${VERSION} `,
  "color:#fff;background:#03a9f4;font-weight:500", "color:#03a9f4;background:transparent");
