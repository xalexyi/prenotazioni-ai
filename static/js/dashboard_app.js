/* Dashboard wiring — tutto in un unico file */

(function () {
  // ---------- Helpers ----------
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));
  const fmtMoney = (n) => `${Number(n || 0).toFixed(2)} €`;

  function showToast(msg, ok = true) {
    let t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2500);
  }

  // ---------- Tema (toggle solo in alto a destra) ----------
  (function themeInit() {
    const key = "ui:theme";
    const btn = $("#themeToggle");
    const apply = (t) => {
      document.documentElement.setAttribute("data-theme", t);
      btn.setAttribute("data-state", t === "light" ? "on" : "off");
    };
    apply(localStorage.getItem(key) || "dark");
    btn.addEventListener("click", () => {
      const next = btn.getAttribute("data-state") === "on" ? "dark" : "light";
      localStorage.setItem(key, next);
      apply(next);
    });
  })();

  // ---------- Navigazione (sidebar) ----------
  (function sidebarNav() {
    const links = $$("#side-nav .nav-link");
    const panels = $$("[data-panel]");

    links.forEach((a) =>
      a.addEventListener("click", (e) => {
        e.preventDefault();
        links.forEach((l) => l.classList.remove("active"));
        a.classList.add("active");
        const id = a.getAttribute("data-panel");
        panels.forEach((p) => {
          p.hidden = p.id !== `panel-${id}`;
        });
      })
    );
  })();

  // ---------- API ----------
  async function apiListReservations(params = {}) {
    const url = new URL("/api/reservations", window.location.origin);
    if (params.date) url.searchParams.set("date", params.date);
    if (params.q) url.searchParams.set("q", params.q);
    const r = await fetch(url, { credentials: "same-origin" });
    return r.json();
  }
  async function apiCreateReservation(payload) {
    const r = await fetch("/api/reservations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    return r.json();
  }
  async function apiUpdateReservation(id, payload) {
    const r = await fetch(`/api/reservations/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    return r.json();
  }
  async function apiDeleteReservation(id) {
    const r = await fetch(`/api/reservations/${id}`, {
      method: "DELETE",
      credentials: "same-origin",
    });
    return r.json();
  }
  async function apiSavePricing(payload) {
    const r = await fetch("/api/pricing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    return r.json();
  }
  async function apiSaveMenu(payload) {
    const r = await fetch("/api/menu", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    return r.json();
  }
  async function apiSaveHours(payload) {
    const r = await fetch("/api/hours", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    return r.json();
  }
  async function apiSaveSpecial(payload) {
    const r = await fetch("/api/special-days", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    return r.json();
  }
  async function apiStats(date) {
    const url = new URL("/api/stats", window.location.origin);
    if (date) url.searchParams.set("date", date);
    const r = await fetch(url, { credentials: "same-origin" });
    return r.json();
  }

  // ---------- Tabella prenotazioni ----------
  const tbody = $("#res-tbody");

  function renderReservations(items) {
    tbody.innerHTML = "";
    if (!items || !items.length) {
      tbody.innerHTML =
        '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:18px;">Nessuna prenotazione trovata</td></tr>';
      return;
    }
    for (const it of items) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${it.date || "-"}</td>
        <td>${it.time || "-"}</td>
        <td>${it.name || "-"}</td>
        <td>${it.phone || "-"}</td>
        <td>${it.people ?? "-"}</td>
        <td><span class="badge ${it.status==='Confermata'?'badge-success': (it.status==='Rifiutata'?'badge-muted':'badge-info')}">${it.status||'-'}</span></td>
        <td class="col-actions">
          <div class="actions">
            <button class="btn btn-sm" data-act="edit"   data-id="${it.id}">Modifica</button>
            <button class="btn btn-sm" data-act="ok"     data-id="${it.id}">Conferma</button>
            <button class="btn btn-sm" data-act="ko"     data-id="${it.id}">Rifiuta</button>
            <button class="btn btn-sm btn-danger" data-act="del" data-id="${it.id}">Elimina</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    }
  }

  // ---------- Caricamento iniziale ----------
  async function loadReservations() {
    const dateStr = $("#flt-date").value.trim();
    const q = $("#flt-q").value.trim();
    const res = await apiListReservations({ date: normalizeDate(dateStr), q });
    if (!res.ok) {
      showToast("Errore caricamento prenotazioni", false);
      return;
    }
    renderReservations(res.items);
    // KPI semplici
    $("#kpi-today").textContent = String(res.items.filter(i => i.date === todayISO()).length);
    $("#kpi-revenue").textContent = fmtMoney(0);
  }

  // helper date
  function todayISO() {
    const d = new Date();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${m}-${day}`;
  }
  function normalizeDate(input) {
    // accetta gg/mm/aaaa e restituisce aaaa-mm-gg
    if (!input) return "";
    const m = input.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (m) return `${m[3]}-${m[2]}-${m[1]}`;
    return input; // già ISO?
  }

  // ---------- Eventi filtri ----------
  $("#btn-filter").addEventListener("click", loadReservations);
  $("#btn-clear").addEventListener("click", () => {
    $("#flt-date").value = "";
    $("#flt-q").value = "";
    loadReservations();
  });
  $("#btn-today").addEventListener("click", () => {
    const d = new Date();
    $("#flt-date").value = `${String(d.getDate()).padStart(2, "0")}/${String(
      d.getMonth() + 1
    ).padStart(2, "0")}/${d.getFullYear()}`;
    loadReservations();
  });

  // ---------- Modale prenotazione ----------
  const modal = $("#res-modal");
  let editId = null;

  function openModal(title = "Crea prenotazione", data = null) {
    $("#res-modal-title").textContent = title;
    editId = data?.id ?? null;
    $("#f-date").value = data?.date || todayISO();
    $("#f-time").value = data?.time || "20:00";
    $("#f-name").value = data?.name || "";
    $("#f-phone").value = data?.phone || "";
    $("#f-people").value = data?.people || 2;
    $("#f-status").value = data?.status || "Confermata";
    $("#f-note").value = data?.note || "";
    modal.hidden = false;
  }
  function closeModal() {
    modal.hidden = true;
  }

  $("#btn-new").addEventListener("click", () => openModal("Crea prenotazione"));
  $("#res-modal-close").addEventListener("click", closeModal);
  $("#res-modal-cancel").addEventListener("click", closeModal);

  $("#res-modal-save").addEventListener("click", async () => {
    const payload = {
      date: $("#f-date").value.trim(),
      time: $("#f-time").value.trim(),
      name: $("#f-name").value.trim(),
      phone: $("#f-phone").value.trim(),
      people: Number($("#f-people").value || 2),
      status: $("#f-status").value,
      note: $("#f-note").value.trim(),
    };
    let out;
    if (editId) out = await apiUpdateReservation(editId, payload);
    else out = await apiCreateReservation(payload);

    if (out.ok) {
      closeModal();
      showToast("Prenotazione salvata ✅");
      loadReservations();
    } else showToast(out.error || "Errore salvataggio", false);
  });

  // Azioni riga (edit/confirm/refuse/delete)
  tbody.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const id = btn.getAttribute("data-id");
    const act = btn.getAttribute("data-act");

    if (act === "del") {
      if (!confirm("Eliminare la prenotazione?")) return;
      const out = await apiDeleteReservation(id);
      if (out.ok) {
        showToast("Eliminata 🗑️");
        loadReservations();
      } else showToast(out.error || "Errore eliminazione", false);
      return;
    }
    if (act === "ok") {
      const out = await apiUpdateReservation(id, { status: "Confermata" });
      out.ok ? loadReservations() : showToast("Errore aggiornamento", false);
      return;
    }
    if (act === "ko") {
      const out = await apiUpdateReservation(id, { status: "Rifiutata" });
      out.ok ? loadReservations() : showToast("Errore aggiornamento", false);
      return;
    }
    if (act === "edit") {
      // recupero dati dalla riga
      const tr = btn.closest("tr");
      const data = {
        id,
        date: tr.children[0].textContent.trim(),
        time: tr.children[1].textContent.trim(),
        name: tr.children[2].textContent.trim(),
        phone: tr.children[3].textContent.trim(),
        people: Number(tr.children[4].textContent.trim() || 2),
        status: tr.children[5].textContent.trim(),
      };
      openModal("Modifica prenotazione", data);
      return;
    }
  });

  // ---------- Salvataggi altri pannelli ----------
  $("#btn-save-pricing")?.addEventListener("click", async () => {
    const out = await apiSavePricing({
      avg_price: $("#avg_price_lunch").value || "",
      avg_price_dinner: $("#avg_price_dinner").value || "",
      cover: $("#cover").value || "",
      seats_cap: $("#seats_cap").value || "",
      min_people: $("#min_people").value || "",
    });
    out.ok ? showToast("Impostazioni salvate ✅") : showToast(out.error || "Errore", false);
  });

  $("#btn-save-menu")?.addEventListener("click", async () => {
    const out = await apiSaveMenu({
      menu_url: $("#menu_url").value,
      menu_desc: $("#menu_desc").value,
    });
    out.ok ? showToast("Menu aggiornato ✅") : showToast(out.error || "Errore", false);
  });

  $("#btn-save-hours")?.addEventListener("click", async () => {
    // qui dovresti leggere i campi orari. Per ora mando vuoto per mantenere compatibilità
    const out = await apiSaveHours({ hours: {} });
    out.ok ? showToast("Orari salvati ✅") : showToast(out.error || "Errore", false);
  });

  $("#btn-save-special")?.addEventListener("click", async () => {
    const out = await apiSaveSpecial({
      day: $("#special-date").value,
      windows: $("#special-windows").value,
      closed: $("#special-closed").checked,
    });
    out.ok ? showToast("Giorno speciale salvato ✅") : showToast(out.error || "Errore", false);
  });

  $("#btn-stats-update")?.addEventListener("click", async () => {
    const d = normalizeDate($("#stats-date").value.trim());
    const out = await apiStats(d);
    if (!out.ok) return showToast("Errore stats", false);
    $("#s-total").textContent = out.total_reservations ?? 0;
    $("#s-avg-people").textContent = Number(out.avg_people || 0).toFixed(1);
    $("#s-avg-price").textContent = fmtMoney(out.avg_price || 0);
    $("#s-revenue").textContent = fmtMoney(out.estimated_revenue || 0);
  });

  // Start
  loadReservations();
})();
