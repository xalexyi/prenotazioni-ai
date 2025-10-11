/* Dashboard – Prenotazioni (fix: data, azioni in riga, toggle tema, menu funzionante) */

(() => {
  // -------------------------
  // helpers
  // -------------------------
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // ---- robust date parsing (YYYY-MM-DD or DD/MM/YYYY)
  function parseDateSafe(s) {
    if (!s) return null;
    // ISO
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return new Date(`${s}T00:00:00`);
    // DMY
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(s)) {
      const [dd, mm, yyyy] = s.split("/");
      return new Date(`${yyyy}-${mm}-${dd}T00:00:00`);
    }
    // fallback
    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }

  const api = {
    async list(params = {}) {
      const qs = new URLSearchParams(params).toString();
      const r = await fetch(`/api/reservations?${qs}`, { credentials: "same-origin" });
      return r.json();
    },
    async create(payload) {
      const r = await fetch("/api/reservations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(payload)
      });
      return r.json();
    },
    async update(id, payload) {
      const r = await fetch(`/api/reservations/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(payload)
      });
      return r.json();
    },
    async remove(id) {
      const r = await fetch(`/api/reservations/${id}`, {
        method: "DELETE",
        credentials: "same-origin"
      });
      return r.json();
    },
    async stats(params = {}) {
      const qs = new URLSearchParams(params).toString();
      const r = await fetch(`/api/stats?${qs}`, { credentials: "same-origin" });
      return r.json();
    }
  };

  const fmt = {
    dayName(d) { return d.toLocaleDateString("it-IT", { weekday: "short" }); },
    date(d) { return d.toLocaleDateString("it-IT"); },
    statusBadge(status) {
      const map = {
        "Confermata": { cls: "badge ok", txt: "✅ Confermata" },
        "In attesa":   { cls: "badge wait", txt: "⏳ In attesa" },
        "Rifiutata":   { cls: "badge ko", txt: "❌ Rifiutata" }
      };
      const m = map[status] || map["In attesa"];
      return `<span class="${m.cls}">${m.txt}</span>`;
    }
  };

  // -------------------------
  // stato
  // -------------------------
  let state = {
    filterDate: "",
    filterQ: "",
    items: [],
    editId: null,
    pendingDeleteId: null
  };

  // -------------------------
  // rendering
  // -------------------------
  function escapeHtml(s) {
    return (s || "").replace(/[&<>"']/g, m => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[m]);
  }

  function renderList() {
    const box = $("#list");
    box.innerHTML = "";

    if (!state.items.length) {
      box.innerHTML = `<div class="empty">Nessuna prenotazione trovata<br><small>Prova a cambiare filtri o aggiungi una nuova prenotazione.</small></div>`;
      return;
    }

    const table = document.createElement("div");
    table.className = "res-table";

    table.innerHTML = `
      <div class="res-row head">
        <div class="c when">Data / Ora</div>
        <div class="c who">Cliente</div>
        <div class="c phone">Telefono</div>
        <div class="c ppl">Pers.</div>
        <div class="c status">Stato</div>
        <div class="c note">Note</div>
        <div class="c actions">Azioni</div>
      </div>
    `;

    for (const r of state.items) {
      const d = parseDateSafe(r.date);
      const datePart = d ? `${fmt.dayName(d)} ${fmt.date(d)}` : "—";
      const row = document.createElement("div");
      row.className = "res-row";
      row.dataset.id = r.id;

      row.innerHTML = `
        <div class="c when">
          <div class="when-date">${datePart}</div>
          <div class="when-time">🕒 ${escapeHtml(r.time || "—")}</div>
        </div>
        <div class="c who">👤 ${escapeHtml(r.name || "—")}</div>
        <div class="c phone">📞 ${escapeHtml(r.phone || "—")}</div>
        <div class="c ppl">👥 ${r.people}</div>
        <div class="c status">${fmt.statusBadge(r.status)}</div>
        <div class="c note">${escapeHtml(r.note || "—")}</div>
        <div class="c actions actions-inline">
          <button class="chip" data-act="edit">Modifica</button>
          <button class="chip" data-act="confirm">Conferma</button>
          <button class="chip" data-act="reject">Rifiuta</button>
          <button class="chip chip-danger" data-act="delete">Elimina</button>
        </div>
      `;

      table.appendChild(row);
    }

    box.appendChild(table);
  }

  async function refresh() {
    const params = {};
    if (state.filterDate) params.date = state.filterDate;
    if (state.filterQ) params.q = state.filterQ;

    const res = await api.list(params);
    state.items = (res && res.items) || [];
    renderList();

    const st = await api.stats(params);
    if (st && st.ok) {
      $("#card-today").textContent = String(st.total_reservations || 0);
      $("#card-revenue").textContent = `${(st.estimated_revenue || 0).toFixed(2)} €`;
    }
  }

  // -------------------------
  // Modal helpers
  // -------------------------
  function openModal(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove("hidden");
    el.setAttribute("aria-hidden", "false");
  }
  function closeModal(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add("hidden");
    el.setAttribute("aria-hidden", "true");
  }
  $$(".modal").forEach(m => {
    m.addEventListener("click", e => {
      if (e.target.classList.contains("modal-backdrop")) {
        m.classList.add("hidden");
      }
    });
  });
  $$('[data-close]').forEach(btn => {
    btn.addEventListener("click", () => closeModal(btn.dataset.close));
  });

  // -------------------------
  // wiring
  // -------------------------
  function wireToolbar() {
    $("#btn-today").addEventListener("click", () => {
      const d = new Date();
      const yyyy = d.getFullYear();
      const mm = String(d.getMonth() + 1).padStart(2, "0");
      const dd = String(d.getDate()).padStart(2, "0");
      $("#flt-date").value = `${yyyy}-${mm}-${dd}`;
      state.filterDate = $("#flt-date").value;
      refresh();
    });

    $("#btn-filter").addEventListener("click", () => {
      state.filterDate = $("#flt-date").value || "";
      state.filterQ = $("#flt-q").value.trim();
      refresh();
    });

    $("#btn-clear").addEventListener("click", () => {
      $("#flt-date").value = "";
      $("#flt-q").value = "";
      state.filterDate = "";
      state.filterQ = "";
      refresh();
    });

    $("#btn-new").addEventListener("click", () => {
      state.editId = null;
      $("#modal-title").textContent = "Crea prenotazione";
      $("#f-date").value = $("#flt-date").value || new Date().toISOString().slice(0, 10);
      $("#f-time").value = "20:00";
      $("#f-name").value = "";
      $("#f-phone").value = "";
      $("#f-people").value = "2";
      $("#f-status").value = "Confermata";
      $("#f-note").value = "";
      openModal("modal-res");
    });

    $("#btn-save-res").addEventListener("click", async () => {
      const payload = {
        date: $("#f-date").value,
        time: $("#f-time").value,
        name: $("#f-name").value.trim(),
        phone: $("#f-phone").value.trim(),
        people: Number($("#f-people").value || 2),
        status: $("#f-status").value,
        note: $("#f-note").value.trim()
      };
      let out;
      if (state.editId) out = await api.update(state.editId, payload);
      else out = await api.create(payload);

      if (out && out.ok) {
        closeModal("modal-res");
        await refresh();
      } else {
        alert("Errore: " + (out && out.error ? out.error : "impossibile salvare"));
      }
    });
  }

  function wireListActions() {
    $("#list").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      const row = e.target.closest(".res-row");
      if (!row) return;
      const id = Number(row.dataset.id);
      const act = btn.dataset.act;

      if (act === "edit") {
        const item = state.items.find(x => x.id === id);
        if (!item) return;
        state.editId = id;
        $("#modal-title").textContent = "Modifica prenotazione";
        $("#f-date").value = /^\d{4}-\d{2}-\d{2}$/.test(item.date) ? item.date : (function(){
          const d = parseDateSafe(item.date); if(!d) return "";
          const yyyy = d.getFullYear();
          const mm = String(d.getMonth()+1).padStart(2,"0");
          const dd = String(d.getDate()).padStart(2,"0");
          return `${yyyy}-${mm}-${dd}`;
        })();
        $("#f-time").value = item.time || "20:00";
        $("#f-name").value = item.name || "";
        $("#f-phone").value = item.phone || "";
        $("#f-people").value = item.people || 2;
        $("#f-status").value = item.status || "In attesa";
        $("#f-note").value = item.note || "";
        openModal("modal-res");
      }

      if (act === "confirm") {
        const out = await api.update(id, { status: "Confermata" });
        if (out && out.ok) refresh();
      }

      if (act === "reject") {
        const out = await api.update(id, { status: "Rifiutata" });
        if (out && out.ok) refresh();
      }

      if (act === "delete") {
        state.pendingDeleteId = id;
        openModal("modal-confirm");
      }
    });

    $("#btn-confirm-delete").addEventListener("click", async () => {
      const id = state.pendingDeleteId;
      if (!id) return;
      const out = await api.remove(id);
      closeModal("modal-confirm");
      state.pendingDeleteId = null;
      if (out && out.ok) refresh();
      else alert("Impossibile eliminare la prenotazione.");
    });
  }

  // --- menu laterale: non rompo logica esistente. Se c'è window.appSwitchSection lo uso,
  // altrimenti emetto un CustomEvent che eventuale altro script può intercettare.
  function wireSidebar() {
    $$(".nav-item").forEach(a => {
      a.addEventListener("click", () => {
        $$(".nav-item").forEach(x => x.classList.remove("active"));
        a.classList.add("active");
        const sec = a.dataset.section;
        if (typeof window.appSwitchSection === "function") {
          window.appSwitchSection(sec);
        } else {
          document.dispatchEvent(new CustomEvent("switch-section", { detail: sec }));
        }
      });
    });
  }

  // --- theme toggle (persistenza)
  function wireThemeToggle() {
    const key = "theme-mode";
    const saved = localStorage.getItem(key) || "dark";
    document.body.setAttribute("data-theme", saved);
    $("#theme-toggle").checked = saved === "light";
    $("#theme-toggle").addEventListener("change", () => {
      const next = $("#theme-toggle").checked ? "light" : "dark";
      document.body.setAttribute("data-theme", next);
      localStorage.setItem(key, next);
    });
  }

  // boot
  function boot() {
    wireThemeToggle();
    wireToolbar();
    wireListActions();
    wireSidebar();
    refresh();
  }
  document.addEventListener("DOMContentLoaded", boot);
})();
