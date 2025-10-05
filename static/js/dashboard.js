// Helpers UI
const $ = (s, p=document) => p.querySelector(s);
const $$ = (s, p=document) => Array.from(p.querySelectorAll(s));
const show = el => el && (el.hidden = false);
const hide = el => el && (el.hidden = true);
const toast = (msg, kind="ok") => {
  const t = $("#toast");
  if (!t) return;
  t.textContent = msg;
  t.className = `toast ${kind}`;
  show(t);
  setTimeout(() => hide(t), 2500);
};

// Menu 3 puntini
(() => {
  const btn = $("#menu-dots");
  const panel = $("#menu-panel");
  if (!btn || !panel) return;
  btn.addEventListener("click", () => {
    panel.style.display = panel.style.display === "none" || !panel.style.display ? "block" : "none";
  });
  document.addEventListener("click", (e) => {
    if (!panel.contains(e.target) && e.target !== btn) panel.style.display = "none";
  });
  $$("#menu-panel .panel-item").forEach(i => {
    i.addEventListener("click", () => {
      panel.style.display = "none";
      const target = i.getAttribute("data-open");
      const m = $(target);
      if (m) show(m);
    });
  });
})();

// Modali: chiudi
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-close], .modal .x");
  if (!btn) return;
  const m = e.target.closest(".modal");
  if (m) hide(m);
});

// Pulsante "Crea prenotazione"
$("#btn-new")?.addEventListener("click", () => show($("#modal-create")));

// Token
$("#token-save")?.addEventListener("click", () => {
  const v = $("#token-input").value.trim();
  if (!v) return toast("Token vuoto", "warn");
  localStorage.setItem("admin_api_token", v);
  toast("Token salvato ✅", "ok");
  hide($("#modal-token"));
});

// Carica prenotazioni
async function loadReservations() {
  const date = $("#resv-date").value || new Date().toISOString().slice(0,10);
  const q = $("#resv-search").value.trim();
  const url = new URL("/api/reservations", window.location.origin);
  url.searchParams.set("date", date);
  if (q) url.searchParams.set("q", q);

  try {
    const r = await fetch(url.toString(), {credentials: "same-origin"});
    const js = await r.json();
    const list = $("#reservations-list");
    list.innerHTML = "";
    if (!js.items || js.items.length === 0) {
      $("#resv-empty").style.display = "block";
      return;
    }
    $("#resv-empty").style.display = "none";
    js.items.forEach(it => {
      const div = document.createElement("div");
      div.className = "resv-row";
      div.innerHTML = `
        <div><b>${it.time}</b> — ${it.name || "—"} (${it.people})</div>
        <div class="muted">${it.phone || ""}</div>
      `;
      list.appendChild(div);
    });
    // mini-stat
    $("#stat-resv-today").textContent = js.items.filter(x => x.date === date).length || 0;
  } catch (err) {
    toast("db_error", "error"); // coerente con le tue schermate
  }
}
$("#btn-refresh")?.addEventListener("click", loadReservations);
$("#btn-today")?.addEventListener("click", () => {
  $("#resv-date").value = new Date().toISOString().slice(0,10);
  loadReservations();
});
$("#btn-filter")?.addEventListener("click", loadReservations);
$("#btn-reset")?.addEventListener("click", () => {
  $("#resv-search").value = "";
  loadReservations();
});
$("#btn-30d")?.addEventListener("click", () => {
  toast("Storico 30gg non ancora implementato", "warn");
});

// Salva prenotazione
$("#create-save")?.addEventListener("click", async () => {
  const f = $("#create-form");
  const data = Object.fromEntries(new FormData(f).entries());
  try {
    const r = await fetch("/api/reservations", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      credentials: "same-origin",
      body: JSON.stringify(data),
    });
    const js = await r.json();
    if (!js.ok) throw new Error("bad");
    toast("Prenotazione creata ✅", "ok");
    hide($("#modal-create"));
    loadReservations();
  } catch (e) {
    toast("db_error", "error");
  }
});

// Orari settimanali
$("#save-hours")?.addEventListener("click", async () => {
  const hours = {};
  $$(".hours-input").forEach(i => hours[i.dataset.day] = i.value.trim());
  try {
    const r = await fetch("/api/hours", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      credentials: "same-origin",
      body: JSON.stringify({hours}),
    });
    if (!r.ok) throw new Error();
    toast("Orari salvati ✅", "ok");
    hide($("#modal-hours"));
  } catch {
    toast("db_error", "error");
  }
});

// Giorni speciali
$("#sp-save")?.addEventListener("click", async () => {
  const date = $("#sp-date").value;
  const closed = $("#sp-closed").checked;
  const windows = $("#sp-windows").value.trim();
  try {
    const r = await fetch("/api/special-days", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      credentials: "same-origin",
      body: JSON.stringify({date, closed, windows}),
    });
    if (!r.ok) throw new Error();
    toast("Aggiornato ✅", "ok");
  } catch {
    toast("db_error", "error");
  }
});
$("#sp-delete")?.addEventListener("click", async () => {
  const date = $("#sp-date").value;
  try {
    const r = await fetch(`/api/special-days?date=${encodeURIComponent(date)}`, {
      method: "DELETE", credentials: "same-origin"
    });
    if (!r.ok) throw new Error();
    toast("Eliminato ✅", "ok");
  } catch {
    toast("db_error", "error");
  }
});

// Riepilogo (fittizio: mostra ciò che hai impostato a form)
$("#modal-status")?.addEventListener("click", (e) => {
  if (e.target !== e.currentTarget) return;
});
function refreshSummary() {
  const list = $("#sum-hours");
  list.innerHTML = "";
  $$(".hours-input").forEach(i => {
    const day = i.dataset.day;
    const label = day.charAt(0).toUpperCase()+day.slice(1);
    const v = (i.value || "").trim();
    const li = document.createElement("li");
    li.textContent = `${label}: ${v ? v : "CHIUSO"}`;
    list.appendChild(li);
  });
  $("#sum-special").innerHTML = "<li>2025-12-25: CHIUSO</li>";
  $("#sum-json").textContent = JSON.stringify({ok:true}, null, 2);
}
$("#modal-status")?.addEventListener("transitionend", refreshSummary);

// inicializzazione
loadReservations();
