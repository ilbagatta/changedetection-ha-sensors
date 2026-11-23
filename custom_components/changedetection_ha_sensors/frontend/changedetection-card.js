/*
 * Changedetection card — Lovelace card (plain JS, no build), served by the `changedetection_ha_sensors` integration.
 *
 *   type: custom:changedetection-card
 *   entity: sensor.changedetection_io_recent_changes   # optional: found automatically (only this sensor works)
 *   title: Changedetection                             # optional, "" hides the header
 *   limit: 10                                          # optional
 *   show_text: true                                    # optional: text of watches without a price
 */
const CARD_VERSION = "0.1.3";

const I18N = {
  en: {
    product: "Product", price: "Price", when: "When", today: "today", yesterday: "yesterday",
    empty: "No changes yet", missing: "Entity not found", out: "out of stock", unviewed: "not viewed yet",
    title: "Title", entity: "Recent changes sensor", limit: "Rows", show_text: "Show text of watches without a price",
  },
  it: {
    product: "Prodotto", price: "Prezzo", when: "Quando", today: "oggi", yesterday: "ieri",
    empty: "Ancora nessuna modifica", missing: "Entità non trovata", out: "esaurito", unviewed: "non ancora visto",
    title: "Titolo", entity: "Sensore Ultime modifiche", limit: "Righe", show_text: "Mostra il testo dei watch senza prezzo",
  },
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const safeUrl = (url) => (/^https?:\/\//i.test(url || "") ? url : "");

// Solo il sensore "Recent changes" dell'integrazione ha la lista delle modifiche
const isListEntity = (hass, id) => Boolean(id && hass.states[id]?.attributes?.changedetection_card);

function listEntities(hass) {
  return Object.keys(hass.states).filter((id) => isListEntity(hass, id));
}

function findEntity(hass) {
  return listEntities(hass)[0];
}

class ChangedetectionCard extends HTMLElement {
  static getStubConfig(hass) {
    return { entity: findEntity(hass) || "", title: "Changedetection" };
  }

  static getConfigElement() {
    return document.createElement("changedetection-card-editor");
  }

  setConfig(config) {
    this._config = { title: "Changedetection", limit: 10, show_text: true, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._lastKey = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const id = this._entityId();
    const state = id ? hass.states[id] : undefined;
    // Ridisegna solo se cambiano i dati o la lingua (e una volta al giorno, per "oggi/ieri")
    const key = `${state?.last_updated}|${hass.locale?.language}|${new Date().toDateString()}`;
    if (key === this._lastKey) return;
    this._lastKey = key;
    this._render();
  }

  getCardSize() {
    return 1 + Math.min(this._config?.limit ?? 10, 10);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  _entityId() {
    const configured = this._config?.entity;
    if (!this._hass) return configured;
    // Un'entita' sbagliata (es. il prezzo di un watch) non svuota la card: si usa quella giusta
    if (isListEntity(this._hass, configured)) return configured;
    return findEntity(this._hass) || configured;
  }

  _t(key) {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").split("-")[0];
    return (I18N[lang] || I18N.en)[key];
  }

  _lang() {
    return this._hass?.locale?.language || this._hass?.language || "en";
  }

  _money(value, currency) {
    if (value === null || value === undefined) return "";
    try {
      return new Intl.NumberFormat(this._lang(), { style: "currency", currency: currency || "EUR" }).format(value);
    } catch (_err) {
      return `${value.toFixed(2)} ${currency || ""}`.trim();
    }
  }

  _when(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    const time = date.toLocaleTimeString(this._lang(), { hour: "2-digit", minute: "2-digit" });
    const day = (d) => d.toDateString();
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (day(date) === day(now)) return `${this._t("today")} ${time}`;
    if (day(date) === day(yesterday)) return `${this._t("yesterday")} ${time}`;
    const sameYear = date.getFullYear() === now.getFullYear();
    return date.toLocaleDateString(this._lang(), sameYear ? { day: "2-digit", month: "2-digit" } : { day: "2-digit", month: "2-digit", year: "2-digit" });
  }

  _row(item, currency) {
    const url = safeUrl(item.url);
    const name = url
      ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(item.title)}</a>`
      : esc(item.title);
    const isToday = item.last_changed && new Date(item.last_changed).toDateString() === new Date().toDateString();
    const flags = [];
    if (item.error) flags.push(`<ha-icon class="warn" icon="mdi:alert-circle-outline" title="${esc(item.error)}"></ha-icon>`);
    if (item.in_stock === false) flags.push(`<span class="badge">${esc(this._t("out"))}</span>`);

    let price = "";
    if (item.price !== null && item.price !== undefined) {
      const old = item.old_price !== null && item.old_price !== undefined
        ? `<span class="old">${esc(this._money(item.old_price, currency))}</span>` : "";
      price = `${old}<span class="now ${esc(item.trend || "")}">${esc(this._money(item.price, currency))}</span>`;
    }
    const text = !price && this._config.show_text && item.text ? `<div class="text">${esc(item.text)}</div>` : "";

    return `
      <tr class="${isToday ? "today" : ""}">
        <td class="dot">${item.viewed === false ? `<span title="${esc(this._t("unviewed"))}"></span>` : ""}</td>
        <td class="name"><div class="title">${name}${flags.join("")}</div>${text}</td>
        <td class="price">${price || "<span class=\"none\">—</span>"}</td>
        <td class="when">${esc(this._when(item.last_changed))}</td>
      </tr>`;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const id = this._entityId();
    const state = id && this._hass ? this._hass.states[id] : undefined;
    const title = this._config.title ? `<div class="header">${esc(this._config.title)}</div>` : "";

    let body;
    if (!state) {
      body = `<div class="empty">${esc(this._t("missing"))}${id ? `: ${esc(id)}` : ""}</div>`;
    } else {
      const items = (state.attributes.watches || []).slice(0, this._config.limit);
      const currency = state.attributes.currency;
      body = items.length
        ? `<table>
            <thead><tr><th></th><th>${esc(this._t("product"))}</th><th class="price">${esc(this._t("price"))}</th><th class="when">${esc(this._t("when"))}</th></tr></thead>
            <tbody>${items.map((item) => this._row(item, currency)).join("")}</tbody>
          </table>`
        : `<div class="empty">${esc(this._t("empty"))}</div>`;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 16px 16px 10px; }
        .header { font-size: 1.15em; font-weight: 400; color: var(--primary-text-color); margin-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; font-size: 0.92em; }
        th { font-size: 0.72em; font-weight: 500; text-transform: uppercase; letter-spacing: .07em;
             color: var(--secondary-text-color); text-align: left; padding: 0 0 6px; }
        td { padding: 8px 0; border-top: 1px solid var(--divider-color, rgba(127,127,127,.15)); vertical-align: baseline; }
        th.price, td.price, th.when, td.when { text-align: right; white-space: nowrap; }
        td.price { padding-left: 12px; font-variant-numeric: tabular-nums; }
        td.when { padding-left: 14px; color: var(--secondary-text-color); font-size: .88em; }
        tr.today td.when { color: var(--primary-text-color); }
        td.dot { width: 12px; padding-right: 4px; }
        td.dot span { display: inline-block; width: 6px; height: 6px; border-radius: 50%;
                      background: var(--accent-color, var(--primary-color)); transform: translateY(-1px); }
        td.name { width: 100%; max-width: 0; }
        .title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .title a { color: var(--primary-text-color); text-decoration: none; }
        .title a:hover { color: var(--accent-color, var(--primary-color)); }
        .text { color: var(--secondary-text-color); font-size: .85em; margin-top: 2px;
                overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .old { color: var(--secondary-text-color); text-decoration: line-through; opacity: .6; font-size: .85em; margin-right: 6px; }
        .now.down { color: var(--success-color, #43a047); }
        .now.up { color: var(--error-color, #e53935); }
        .none { color: var(--disabled-text-color, var(--secondary-text-color)); }
        .badge { margin-left: 6px; font-size: .72em; padding: 1px 6px; border-radius: 8px;
                 color: var(--error-color, #e53935); border: 1px solid currentColor; opacity: .8; }
        ha-icon.warn { --mdc-icon-size: 15px; color: var(--warning-color, #ffa000); margin-left: 4px; vertical-align: -2px; }
        .empty { color: var(--secondary-text-color); padding: 8px 0 6px; }
      </style>
      <ha-card>${title}${body}</ha-card>`;
  }
}

class ChangedetectionCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    const lang = (this._hass.locale?.language || "en").split("-")[0];
    const t = I18N[lang] || I18N.en;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => t[schema.name] || schema.name;
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = [
      { name: "entity", selector: { entity: { include_entities: listEntities(this._hass) } } },
      { name: "title", selector: { text: {} } },
      { name: "limit", selector: { number: { min: 1, max: 50, mode: "box" } } },
      { name: "show_text", selector: { boolean: {} } },
    ];
    this._form.data = { limit: 10, show_text: true, ...this._config };
  }
}

if (!customElements.get("changedetection-card")) {
  customElements.define("changedetection-card", ChangedetectionCard);
  customElements.define("changedetection-card-editor", ChangedetectionCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "changedetection-card",
    name: "Changedetection",
    description: "Recent changedetection.io changes with old and new price.",
    preview: true,
  });
  console.info(`%c CHANGEDETECTION-CARD %c ${CARD_VERSION} `, "background:#7b5ea7;color:#fff", "background:#ddd;color:#333");
}
