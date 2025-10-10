// -------------------------------------------------------------
// Helpers base
// -------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function fmtDateInput(d) {
  // YYYY-MM-DD
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// -------------------------------------------------------------
// Client API: robusta contro risposte HTML (login/404/etc.)
// -------------------------------------------------------------
async function api(url, opts = {}) {
  opts.credentials = "include";
  opts.headers = Object.assign(
    { "Content-Type": "application/json" },
    opts.headers || {}
  );

  try {
    const res = await fetch(url, opts);

    // Se il server risponde HTML (redirect al login o 404 HTML),
    // evitiamo di fare JSON.parse e redirigiamo in modo pulito.
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    if (ct.includes("text/html")) {
      if (!location.pathname.startsWith("/login")) {
        location.href = "/login";
      }
      throw new Error("Non autenticato o endpoint inattivo");
    }

    // Leggi testo e prova a fare parse JSON (con messaggio chiaro in caso di errore)
    const text = await res.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      throw new Error("Risposta non valida dalle API");
    }

    if (!res.ok || data.ok === false) {
      throw new Error(data.error || res.statusText || "Errore richiesta");
    }
    return data;
  } catch (e) {
    alert("Errore: " + (e.message || e));
    throw e;
  }
}

// -------------------------------------------------------------
// Prenotazioni — lista / CRUD
// -------------------------------------------------------------
async function loadReservations() {
  const d = $("#flt-date")?.value || "";
  const q = $("#flt-q")?.value?.trim() || "";

  const params = new URLSearchParams();
  if (d) params.set("date", d);
  if (q) params.set("q", q);

  const res = await api("/api/reservations?" + params.toString(), {
    method: "GET",
  });

  const list = $("#list");
  const empty = $("#list-empty");
  if (!list) return; // difensivo, se non siamo nella dashboard completa

  list.innerHTML = "";
  if (!res.items || res.items.length === 0) {
    if (empty) empty.style.display = "block";
    return;
  }
  if (empty) empty.style.display = "none";

  res.items.forEach((r) => {
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = `
      <div class="row" style="gap:12px;align-items:center">
        <b>${r.date} ${r.time}</b>
        <span>${r.name}</span>
        <span>${r.phone || ""}</span>
        <span>👥 ${r.people}</span>
        <span class="chip">${r.status || ""}</span>
        <span class="grow"></span>
        <button class="btn" data-edit="${r.id}">Modifica</button>
        <button class="btn" data-del="${r.id}">Elimina</button>
      </div>
      ${
        r.note
          ? `<div style="margin-top:6px;color:#9bb1c7">Note: ${r.note}</div>`
          : ""
      }
    `;
    list.appendChild(el);
  });

  // bind azioni
  list.querySelectorAll("[data-del]").forEach((b) => {
    b.onclick = async () => {
      if (!confirm("Eliminare la prenotazione?")) return;
      await api("/api/reservations/" + b.dataset.del, { method: "DELETE" });
      await loadReservations();
    };
  });
  list.querySelectorAll("[data-edit]").forEach((b) => {
    b.onclick = async () => {
      const id = b.dataset.edit;
      const when = prompt("Nuova data (YYYY-MM-DD) o lascia vuoto", "");
      const at = prompt("Nuova ora (HH:MM) o lascia vuoto", "");
      const payload = {};
      if (when) payload.date = when;
      if (at) payload.time = at;
      if (Object.keys(payload).length === 0) return;
      await api("/api/reservations/" + id, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      await loadReservations();
    };
  });
}

async function createReservation() {
  const today = $("#flt-date")?.value || fmtDateInput(new Date());
  const dateStr = prompt("Data (YYYY-MM-DD)", today);
  const timeStr = prompt("Ora (HH:MM)", "20:00");
  const name = prompt("Nome", "");
  const phone = prompt("Telefono", "");
  const people = parseInt(prompt("Persone", "2") || "2", 10);
  if (!dateStr || !timeStr || !name) return;
  const payload = {
    date: dateStr,
    time: timeStr,
    name,
    phone,
    people,
    status: "Confermata",
    note: "",
  };
  await api("/api/reservations", { method: "POST", body: JSON.stringify(payload) });
  await loadReservations();
}

// -------------------------------------------------------------
// Orari settimanali
// (usa inputs con id #h-0..#h-6 tipo "12:00-15:00, 19:00-22:30")
// -------------------------------------------------------------
async function saveWeeklyHours() {
  // raccoglie i 7 campi se presenti nel DOM (lun=0..dom=6)
  const map = {};
  for (let i = 0; i < 7; i++) {
    const v = $(`#h-${i}`)?.value?.trim();
    map[i] = v || ""; // stringa vuota = chiuso
  }
  await api("/api/hours", { method: "POST", body: JSON.stringify({ hours: map }) });
  alert("Orari aggiornati");
}

// -------------------------------------------------------------
// Giorni speciali (chiusure/eccezioni)
// dipende da campi: #sp-day, #sp-closed, #sp-windows
// -------------------------------------------------------------
async function saveSpecialDay() {
  const day = $("#sp-day")?.value;
  if (!day) return alert("Seleziona una data");
  const closed = $("#sp-closed")?.checked;
  const windows = $("#sp-windows")?.value?.trim() || "";
  await api("/api/special-days", {
    method: "POST",
    body: JSON.stringify({ day, closed, windows }),
  });
  alert("Giorno speciale salvato");
}

async function deleteSpecialDay() {
  const day = $("#sp-day")?.value;
  if (!day) return alert("Seleziona una data");
  await api("/api/special-days/" + day, { method: "DELETE" });
  alert("Giorno speciale eliminato");
}

// -------------------------------------------------------------
// Prezzi & coperti (placeholder con wire pronto)
// campi attesi: #prz-average, #prz-capacity
// -------------------------------------------------------------
async function loadPricing() {
  try {
    const data = await api("/api/pricing", { method: "GET" });
    if ($("#prz-average")) $("#prz-average").value = data.average_price ?? "";
    if ($("#prz-capacity")) $("#prz-capacity").value = data.capacity ?? "";
  } catch (e) {
    // se non esiste l’endpoint mostriamo solo un alert amichevole
    alert("Impostazioni prezzi in arrivo");
  }
}
async function savePricing() {
  const average_price = parseFloat($("#prz-average")?.value || "0");
  const capacity = parseInt($("#prz-capacity")?.value || "0", 10);
  await api("/api/pricing", {
    method: "POST",
    body: JSON.stringify({ average_price, capacity }),
  });
  alert("Prezzi & coperti salvati");
}

// -------------------------------------------------------------
// Menu digitale (placeholder con wire pronto)
// elementi ripetuti in #menu-list, campi: #mi-name, #mi-price
// -------------------------------------------------------------
async function loadMenu() {
  try {
    const data = await api("/api/menu-items", { method: "GET" });
    const list = $("#menu-list");
    if (!list) return;
    list.innerHTML = "";
    (data.items || []).forEach((it) => {
      const row = document.createElement("div");
      row.className = "row";
      row.style.gap = "8px";
      row.innerHTML = `
        <div class="grow"><b>${it.name}</b></div>
        <div>${Number(it.price).toFixed(2)} €</div>
        <button class="btn" data-del-item="${it.id}">Elimina</button>
      `;
      list.appendChild(row);
    });
    list.querySelectorAll("[data-del-item]").forEach((b) => {
      b.onclick = async () => {
        await api("/api/menu-items/" + b.dataset.delItem, { method: "DELETE" });
        await loadMenu();
      };
    });
  } catch (e) {
    alert("Gestione menu in arrivo");
  }
}
async function addMenuItem() {
  const name = $("#mi-name")?.value?.trim();
  const price = parseFloat($("#mi-price")?.value || "0");
  if (!name || !(price > 0)) return alert("Nome e prezzo obbligatori");
  await api("/api/menu-items", {
    method: "POST",
    body: JSON.stringify({ name, price }),
  });
  $("#mi-name").value = "";
  $("#mi-price").value = "";
  await loadMenu();
}

// -------------------------------------------------------------
// Statistiche & report (placeholder con wire pronto)
// bottoni: #btn-preview-report, #btn-download-csv
// -------------------------------------------------------------
async function previewReport() {
  try {
    const data = await api("/api/reports/overview", { method: "GET" });
    alert(`Ultimi 30gg — prenotazioni: ${data.count || 0}, incasso: ${data.revenue || 0} €`);
  } catch (e) {
    alert("Report in arrivo");
  }
}
async function downloadCSV() {
  try {
    const res = await fetch("/api/reports/overview.csv", { credentials: "include" });
    if (!res.ok) throw new Error("Download fallito");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "report.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert("Report CSV in arrivo");
  }
}

// -------------------------------------------------------------
// Init sicuro: parte SOLO in dashboard
// (evita fetch su /login e riduce i popup con HTML)
// -------------------------------------------------------------
window.addEventListener("DOMContentLoaded", async () => {
  // Siamo nella dashboard se esiste la barra KPI
  const isDashboard = !!document.querySelector(".kpi-bar");
  if (!isDashboard) return;

  // Set default: oggi
  if ($("#flt-date")) $("#flt-date").value = fmtDateInput(new Date());

  // Filtri & azioni lista
  $("#btn-filter")?.addEventListener("click", loadReservations);
  $("#btn-clear")?.addEventListener("click", () => {
    if ($("#flt-q")) $("#flt-q").value = "";
    if ($("#flt-date")) $("#flt-date").value = "";
    loadReservations();
  });
  $("#btn-30d")?.addEventListener("click", () =>
    alert("Storico 30gg — (placeholder UI)")
  );
  $("#btn-today")?.addEventListener("click", () => {
    if ($("#flt-date")) $("#flt-date").value = fmtDateInput(new Date());
    loadReservations();
  });
  $("#btn-new")?.addEventListener("click", createReservation);

  // Dialogs — pulsanti “Salva”
  $("#btn-save-hours")?.addEventListener("click", saveWeeklyHours);
  $("#btn-save-special")?.addEventListener("click", saveSpecialDay);
  $("#btn-del-special")?.addEventListener("click", deleteSpecialDay);

  $("#btn-save-pricing")?.addEventListener("click", savePricing);
  $("#btn-add-item")?.addEventListener("click", addMenuItem);

  $("#btn-preview-report")?.addEventListener("click", previewReport);
  $("#btn-download-csv")?.addEventListener("click", downloadCSV);

  // Apri modali con data-open
  document.addEventListener("click", (e) => {
    const trg = e.target.closest("[data-open]");
    if (!trg) return;
    const id = trg.getAttribute("data-open");
    if (id === "dlgPricing") loadPricing();
    if (id === "dlgMenu") loadMenu();
  });

  // Prima popolazione
  await loadReservations();
});
