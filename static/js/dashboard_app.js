/* global showToast */
window.Dashboard = (function () {
  let EP = {};
  const qs = (sel) => document.querySelector(sel);

  function formatDateToISO(d) {
    if (!d) return "";
    if (d.includes("/")) {
      const [gg, mm, aa] = d.split("/");
      return `${aa}-${mm.padStart(2, "0")}-${gg.padStart(2, "0")}`;
    }
    return d;
  }

  function formatISOtoIT(iso) {
    if (!iso) return "";
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
  }

  async function fetchJSON(url, opts = {}) {
    const res = await fetch(url, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!res.ok) {
      const t = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText} — ${t}`);
    }
    return res.json().catch(() => ({}));
  }

  function fillKPIs({ today = 0, revenue = 0, calls = "0/3" } = {}) {
    qs("#kpi-today").textContent = today;
    qs("#kpi-rev").textContent = `${revenue} €`;
    qs("#kpi-calls").textContent = calls;
  }

  function renderRows(items) {
    const body = qs("#resBody");
    if (!body) return;
    body.innerHTML = "";

    if (!items || !items.length) {
      body.innerHTML = `<tr class="empty"><td colspan="7">Nessuna prenotazione trovata</td></tr>`;
      return;
    }

    for (const r of items) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${formatISOtoIT(r.date)} <span class="text-muted">${r.time || ""}</span></td>
        <td>${r.name || ""}</td>
        <td>${r.phone || ""}</td>
        <td>${r.people || "-"}</td>
        <td><span class="badge ${r.status || "pending"}">${(r.status || "").toUpperCase()}</span></td>
        <td>${r.note ? r.note : "—"}</td>
        <td class="col-actions">
          <div class="actions" style="display:flex;gap:4px;flex-wrap:nowrap">
            <button class="btn btn-outline" data-act="edit" data-id="${r.id}">Modifica</button>
            <button class="btn" data-act="confirm" data-id="${r.id}">Conferma</button>
            <button class="btn" data-act="reject" data-id="${r.id}">Rifiuta</button>
            <button class="btn btn-danger" data-act="delete" data-id="${r.id}">Elimina</button>
          </div>
        </td>`;
      body.appendChild(tr);
    }
  }

  async function loadList() {
    const date = formatDateToISO(qs("#f-date")?.value || "");
    const q = qs("#f-query")?.value || "";
    const url = new URL(EP.list, window.location.origin);
    if (date) url.searchParams.set("date", date);
    if (q) url.searchParams.set("query", q);

    try {
      const data = await fetchJSON(url.toString());
      renderRows(data.items || []);
      fillKPIs(data.kpis || {});
    } catch (e) {
      console.error(e);
      showToast("Errore nel caricamento prenotazioni", "error", true);
    }
  }

  function todayStr() {
    const d = new Date();
    const gg = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const aa = d.getFullYear();
    return `${gg}/${mm}/${aa}`;
  }

  // ===== Modal =====
  function openModal() {
    const m = qs("#newModal");
    if (m) m.hidden = false;
  }

  function closeModal() {
    const m = qs("#newModal");
    if (m) m.hidden = true;
  }

  async function saveReservation() {
    const payload = {
      date: qs("#m-date").value.trim(),
      time: qs("#m-time").value.trim(),
      name: qs("#m-name").value.trim(),
      phone: qs("#m-phone").value.trim(),
      people: Number(qs("#m-people").value || 0),
      status: qs("#m-status").value,
      note: qs("#m-note").value.trim(),
    };

    if (!payload.date || !payload.name) {
      showToast("Data e Nome sono obbligatori", "error", true);
      return;
    }

    try {
      await fetchJSON(EP.create, { method: "POST", body: JSON.stringify(payload) });
      closeModal();
      showToast("Prenotazione salvata ✅", "success");
      await loadList();
    } catch (e) {
      console.error(e);
      showToast("Errore nel salvataggio prenotazione", "error", true);
    }
  }

  // ===== Impostazioni =====
  async function saveHours() {
    const payload = {
      lun: qs("#d-lun").value.trim(),
      mar: qs("#d-mar").value.trim(),
      mer: qs("#d-mer").value.trim(),
      gio: qs("#d-gio").value.trim(),
      ven: qs("#d-ven").value.trim(),
      sab: qs("#d-sab").value.trim(),
      dom: qs("#d-dom").value.trim(),
    };
    try {
      await fetchJSON(EP.hours, { method: "POST", body: JSON.stringify(payload) });
      showToast("Orari salvati ✅", "success");
    } catch (e) {
      console.error(e);
      showToast("Errore salvataggio orari", "error", true);
    }
  }

  async function saveSpecial() {
    const payload = {
      date: qs("#sp-date").value.trim(),
      closed: qs("#sp-closed").checked,
      slots: qs("#sp-slots").value.trim(),
    };
    if (!payload.date) {
      showToast("Inserisci la data", "error", true);
      return;
    }
    try {
      await fetchJSON(EP.special, { method: "POST", body: JSON.stringify(payload) });
      showToast("Giorno speciale salvato ✅", "success", true);
    } catch (e) {
      console.error(e);
      showToast("Errore salvataggio giorno speciale", "error", true);
    }
  }

  async function savePricing() {
    const payload = {
      avg_lunch: Number(qs("#pr-lunch").value || 0),
      avg_dinner: Number(qs("#pr-dinner").value || 0),
      capacity: Number(qs("#pr-cap").value || 0),
      min_people: Number(qs("#pr-minp").value || 0),
    };
    try {
      await fetchJSON(EP.pricing, { method: "POST", body: JSON.stringify(payload) });
      showToast("Prezzi salvati ✅", "success");
    } catch (e) {
      console.error(e);
      showToast("Errore salvataggio prezzi", "error", true);
    }
  }

  async function saveMenu() {
    const payload = {
      url: qs("#menu-url").value.trim(),
      description: qs("#menu-desc").value.trim(),
    };
    try {
      await fetchJSON(EP.menu, { method: "POST", body: JSON.stringify(payload) });
      showToast("Menu salvato ✅", "success");
    } catch (e) {
      console.error(e);
      showToast("Errore salvataggio menu", "error", true);
    }
  }

  async function refreshStats() {
    try {
      const d = await fetchJSON(EP.stats);
      qs("#st-res").textContent = d.reservations ?? 0;
      qs("#st-avg").textContent = d.avg_people ?? 0;
      qs("#st-price").textContent = (d.avg_price ?? 0) + " €";
      showToast("Statistiche aggiornate ✅", "success");
    } catch (e) {
      console.error(e);
      showToast("Errore caricamento statistiche", "error", true);
    }
  }

  function bind() {
    const el = (id) => qs(id);

    el("#btn-filter")?.addEventListener("click", loadList);
    el("#btn-clear")?.addEventListener("click", () => {
      qs("#f-date").value = "";
      qs("#f-query").value = "";
      loadList();
    });
    el("#btn-today")?.addEventListener("click", () => {
      qs("#f-date").value = todayStr();
      loadList();
    });

    el("#btn-new")?.addEventListener("click", () => {
      const now = new Date();
      const iso = now.toISOString().slice(0, 10);
      qs("#m-date").value = iso;
      qs("#m-time").value = "20:00";
      qs("#m-name").value = "";
      qs("#m-phone").value = "";
      qs("#m-people").value = "2";
      qs("#m-status").value = "confirmed";
      qs("#m-note").value = "";
      openModal();
    });

    el("#mClose")?.addEventListener("click", closeModal);
    el("#mCancel")?.addEventListener("click", closeModal);
    el("#mSave")?.addEventListener("click", saveReservation);

    el("#btn-hours")?.addEventListener("click", saveHours);
    el("#btn-special")?.addEventListener("click", saveSpecial);
    el("#btn-pricing")?.addEventListener("click", savePricing);
    el("#btn-menu")?.addEventListener("click", saveMenu);

    el("#btn-stats")?.addEventListener("click", refreshStats);

    qs("#f-query")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") loadList();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
  }

  return {
    init(cfg) {
      EP = cfg.endpoints || {};
      const d = todayStr();
      const f = qs("#f-date");
      if (f && !f.value) f.value = d;
      bind();
      loadList();
    },
  };
})();
