// =========================================================================
// main.js - helpers di rete, dom e tema (RIUSABILE IN TUTTE LE PAGINE)
// =========================================================================

// ---------- DOM helpers ----------
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// Crea element con props e children
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  Object.entries(props || {}).forEach(([k, v]) => {
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) el.setAttribute(k, v);
  });
  for (const c of children.flat()) {
    if (c == null) continue;
    el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return el;
}

// ---------- fetch wrapper ----------
async function api(url, { method = "GET", json, headers } = {}) {
  const opt = { method, credentials: "include", headers: { ...headers } };
  if (json !== undefined) {
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(json);
  }
  const r = await fetch(url, opt);
  let data = null;
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("application/json")) data = await r.json();
  else data = await r.text();
  if (!r.ok) {
    const msg = typeof data === "object" && data?.error ? data.error : r.statusText;
    throw new Error(msg || "Errore richiesta");
  }
  return data;
}

export const getJSON  = (url)       => api(url);
export const postJSON = (url, body) => api(url, { method: "POST", json: body });
export const putJSON  = (url, body) => api(url, { method: "PUT",  json: body });
export const delJSON  = (url)       => api(url, { method: "DELETE" });

// ---------- toast ----------
let toastTimer;
export function toast(msg, type = "ok") {
  let box = $("#toast");
  if (!box) {
    box = h("div", { id: "toast" });
    document.body.appendChild(box);
  }
  box.textContent = msg;
  box.className = `show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (box.className = ""), 2400);
}

// ---------- modal ----------
let modalRoot;
export function showModal(title, content, actions = []) {
  closeModal();

  const header = h("div", { class: "modal-header" },
    h("div", { class: "modal-title" }, title),
    h("button", { class: "modal-x", onClick: closeModal, "aria-label": "Chiudi" }, "✕")
  );
  const body   = h("div", { class: "modal-body"  }, content);
  const footer = h("div", { class: "modal-footer" },
    actions.map(a => h("button", { class: `btn ${a.primary ? "btn-primary" : ""}`, onClick: a.onClick }, a.label))
  );

  const card = h("div", { class: "modal-card" }, header, body, footer);

  modalRoot = h(
    "div",
    { class: "modal-backdrop", onClick: (e) => (e.target === modalRoot ? closeModal() : null) },
    card
  );
  document.body.appendChild(modalRoot);
  setTimeout(() => modalRoot.classList.add("open"), 10);
}
export function closeModal() {
  if (modalRoot) {
    modalRoot.classList.remove("open");
    modalRoot.addEventListener("transitionend", () => modalRoot && modalRoot.remove(), { once: true });
    modalRoot = null;
  }
}

// ---------- tema ----------
const THEME_KEY = "ai-ris-theme";
export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
}
export function initTheme() {
  let t = localStorage.getItem(THEME_KEY);
  if (!t) {
    // default scuro
    t = "dark";
    localStorage.setItem(THEME_KEY, t);
  }
  applyTheme(t);
  const toggles = $$('[data-theme-toggle], #theme-toggle');
  toggles.forEach(sw => {
    // stato grafico opzionale
    if ("checked" in sw) sw.checked = t === "dark";
    sw.addEventListener("click", () => {
      const cur = localStorage.getItem(THEME_KEY) || "dark";
      const next = cur === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
    });
  });
}

// ---------- utilità ----------
export function fmtDateISO(d) {
  // accetta Date o string "YYYY-MM-DD"
  if (d instanceof Date) return d.toISOString().slice(0, 10);
  return (d || "").slice(0, 10);
}

export function safeNumber(v, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

// Esporta API grezze usate dal dashboard
export const API = {
  listReservations: (params) => {
    const q = new URLSearchParams(params || {}).toString();
    return getJSON(`/api/reservations${q ? "?" + q : ""}`);
  },
  createReservation: (payload) => postJSON("/api/reservations", payload),
  updateReservation: (id, payload) => putJSON(`/api/reservations/${id}`, payload),
  deleteReservation: (id) => delJSON(`/api/reservations/${id}`),

  saveHours: (hours) => postJSON("/api/hours", { hours }),
  saveSpecialDay: (day) => postJSON("/api/special-days", day),
  // opzionale: elenco giorni salvati (se esiste lato backend)
  listSpecialDays: (from = "", to = "") => getJSON(`/api/special-days?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`),

  savePricing: (p) => postJSON("/api/pricing", p),
  saveMenu: (p) => postJSON("/api/menu", p),

  stats: (params) => {
    const q = new URLSearchParams(params || {}).toString();
    return getJSON(`/api/stats${q ? "?" + q : ""}`);
  },
};

// auto-init del tema
document.addEventListener("DOMContentLoaded", initTheme);
