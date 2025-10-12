// ========= Utilities =========
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...opts,
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

function toast(msg, kind = "info") {
  let el = $(".toast");
  if (!el) {
    el = document.createElement("div");
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.borderColor = kind === "error" ? "#ff5c5c" : "#29446b";
  el.style.display = "block";
  setTimeout(() => (el.style.display = "none"), 2600);
}

// ========= Tema =========
function setupThemeToggle() {
  const root = document.documentElement;
  const saved = localStorage.getItem("theme") || "dark";
  root.setAttribute("data-theme", saved);
  const toggle = $("#theme-toggle");
  if (toggle) toggle.checked = saved === "light";
  if (toggle) {
    toggle.addEventListener("change", () => {
      const next = toggle.checked ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
    });
  }
}

// ========= Router (sidebar) =========
const panels = {
  prices: "#panel-prices",
  menu: "#panel-menu",
  weekly: "#panel-weekly",
  special: "#panel-special",
  stats: "#panel-stats",
  reservations: "#panel-reservations",
};

function showPanel(key) {
  Object.values(panels).forEach((sel) => {
    const el = $(sel);
    if (el) el.hidden = true;
  });
  if (panels[key]) {
    const el = $(panels[key]);
    if (el) el.hidden = false;
  }
  $$(".nav .nav-link").forEach((a) => a.classList.remove("active"));
  const trigger = $(`.nav .nav-link[data-panel="${key}"]`);
  if (trigger) trigger.classList.add("active");
  history.replaceState(null, "", `#${key}`);
}

function bindSidebar() {
  $$(".nav .nav-link").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const key = a.getAttribute("data-panel");
      showPanel(key);
    });
  });
  const hash = (location.hash || "#reservations").replace("#", "");
  showPanel(hash in panels ? hash : "reservations");
}

window.addEventListener("DOMContentLoaded", () => {
  setupThemeToggle();
  bindSidebar();
});
