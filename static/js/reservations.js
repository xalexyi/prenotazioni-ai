/* =======================================================
   Prenotazioni — Frontend
   - Filtri + CRUD AJAX
   - Prezzi fascia oraria (12–15 => 20€, 19–23:30 => 30€)
   - Incasso solo "confirmed"
   - PIZZERIA: menù, pizze in prenotazione (condizionale)
   ======================================================= */

(function(){
  "use strict";

  /* ---------------------- Stato ---------------------- */
  const state = { range: "today", date: null, q: "" };
  let MENU = []; // /api/menu (solo pizzeria)
  const IS_PIZZERIA = (typeof window !== "undefined" && window.IS_PIZZERIA === true);

  /* ---------------------- Util ----------------------- */
  const UI = {
    moneyEUR(v) {
      try {
        return new Intl.NumberFormat("it-IT", {
          style: "currency",
          currency: "EUR",
          maximumFractionDigits: 0,
        }).format(v || 0);
      } catch {
        return `€ ${Math.round(v || 0)}`;
      }
    },
    el(tag, cls, html) {
      const e = document.createElement(tag);
      if (cls) e.className = cls;
      if (html != null) e.innerHTML = html;
      return e;
    },
    openModal() {
      const m = document.getElementById("modal");
      if (!m) return;
      m.setAttribute("aria-hidden", "false");
      m.classList.add("is-open");
    },
    closeModal() {
      const m = document.getElementById("modal");
      if (!m) return;
      m.setAttribute("aria-hidden", "true");
      m.classList.remove("is-open");
    },
    toast(m) {
      console.log(m);
    },
  };

  async function fetchJSON(url, opts = {}) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      ...opts,
    });
    if (!res.ok) {
      let msg;
      try { msg = await res.text(); } catch { msg = `HTTP ${res.status}`; }
      throw new Error(msg || `HTTP ${res.status}`);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  /* --------------- Prezzi dinamici ------------------- */
  function toMinutes(hhmm) {
    const [h, m] = (hhmm || "0:0").split(":").map((n) => parseInt(n, 10) || 0);
    return h * 60 + m;
  }
  function priceFor(timeHHMM) {
    const t = toMinutes(timeHHMM);
    if (t >= 12 * 60 && t <= 15 * 60) return 20;
    if (t >= 19 * 60 && t <= 23 * 60 + 30) return 30;
    return 0;
  }

  /* --------- Rendering lista & KPI ------------------- */
  function renderEmptyState(container) {
    const box = UI.el("div", "reservation-row");
    const empty = UI.el("div", "res-left");
    empty.append(
      UI.el("div", "res-name", "Nessuna prenotazione trovata"),
      UI.el("div", "res-meta", "Prova a cambiare filtri o aggiungi una nuova prenotazione.")
    );
    box.append(empty, UI.el("span","badge badge-gray","—"), UI.el("div","res-actions"));
    container.appendChild(box);
  }

  function renderList(items) {
    const list = document.getElementById("list");
    if (!list) return;
    list.innerHTML = "";

    const todayISO = new Date().toISOString().slice(0, 10);
    let kpiToday = 0, revenue = 0, pizzasTotal = 0;

    (items || []).forEach((it) => {
      if (it.date === todayISO) kpiToday++;

      if (it.status === "confirmed") {
        revenue += (it.people || 0) * priceFor(it.time);
        (it.pizzas || []).forEach((p) => (pizzasTotal += p.qty || 0));
      }

      const row = UI.el("div", "reservation-row");

      const left = UI.el("div", "res-left");
      const pill = UI.el("span", "pill people", `${it.people || 1} pers.`);
      const name = UI.el("div", "res-name", it.customer_name || "");
      const meta = UI.el(
        "div",
        "res-meta",
        `${it.date || ""} • ${it.time || ""} • ${it.phone || ""}`
      );
      left.append(pill, name, meta);

      if (it.pizzas && it.pizzas.length) {
        const pizzasLine = it.pizzas.map((p) => `${p.name} ×${p.qty}`).join(", ");
        left.append(UI.el("div", "res-meta", `🍕 ${pizzasLine}`));
      }

      const status = UI.el(
        "span",
        "badge " +
          (it.status === "confirmed"
            ? "badge-green"
            : it.status === "rejected"
            ? "badge-red"
            : "badge-gray"),
        it.status
      );

      const actions = UI.el("div", "res-actions");
      const bC = UI.el("button", "btn btn-outline", "Conferma");
      const bR = UI.el("button", "btn btn-outline", "Rifiuta");
      const bD = UI.el("button", "btn btn-outline", "Elimina");

      bC.onclick = async () => {
        try {
          await fetchJSON(`/api/reservations/${it.id}`, {
            method: "PATCH",
            body: JSON.stringify({ status: "confirmed" }),
          });
          await load();
        } catch (e) { UI.toast(e.message); }
      };
      bR.onclick = async () => {
        try {
          await fetchJSON(`/api/reservations/${it.id}`, {
            method: "PATCH",
            body: JSON.stringify({ status: "rejected" }),
          });
          await load();
        } catch (e) { UI.toast(e.message); }
      };
      bD.onclick = async () => {
        try {
          await fetchJSON(`/api/reservations/${it.id}`, { method: "DELETE" });
          await load();
        } catch (e) { UI.toast(e.message); }
      };

      actions.append(bC, bR, bD);
      row.append(left, status, actions);
      list.appendChild(row);
    });

    if (!items || items.length === 0) renderEmptyState(list);

    const elToday = document.getElementById("kpi-today");
    if (elToday) elToday.textContent = String(kpiToday);

    const elRev = document.getElementById("kpi-revenue");
    if (elRev) elRev.textContent = UI.moneyEUR(revenue);

    const kpiPizze = document.getElementById("kpi-pizzas");
    if (kpiPizze) kpiPizze.textContent = String(pizzasTotal);
  }

  /* -------------------- Load & filtri -------------------- */
  async function load() {
    const p = new URLSearchParams();
    if (state.range) p.set("range", state.range);
    if (state.date)  p.set("date", state.date);
    if (state.q)     p.set("q", state.q);

    try {
      const data = await fetchJSON(`/api/reservations?${p.toString()}`);
      renderList(data);
    } catch (e) {
      UI.toast("Errore caricamento: " + e.message);
    }
  }

  function setupFilters() {
    const fDate = document.getElementById("f-date");
    const fText = document.getElementById("f-text");
    const bFilter = document.getElementById("btn-filter");
    const bClear  = document.getElementById("btn-clear");
    const b30     = document.getElementById("btn-30");
    const bToday  = document.getElementById("btn-today");

    if (bFilter)
      bFilter.onclick = (e)=> {
        e.preventDefault();
        state.date = fDate?.value || null;
        state.q = (fText?.value || "").trim();
        state.range = null; // passa a filtro libero
        load();
      };

    if (bClear)
      bClear.onclick  = (e)=> {
        e.preventDefault();
        if (fDate) fDate.value = "";
        if (fText) fText.value = "";
        state.date = null;
        state.q = "";
        state.range = null;
        load();
      };

    if (b30)
      b30.onclick     = (e)=> { e.preventDefault(); state.range = "30days"; state.date = null; load(); };

    if (bToday)
      bToday.onclick  = (e)=> { e.preventDefault(); state.range = "today";  state.date = null; load(); };

    // invio con Enter nel campo testo
    if (fText)
      fText.addEventListener("keydown",(ev)=>{
        if (ev.key === "Enter") { ev.preventDefault(); bFilter?.click(); }
      });
  }

  /* -------------------- Modale & Pizze -------------------- */
  function pizzaRowTemplate(options) {
    const row = UI.el("div", "pizza-row");
    row.style.display = "grid";
    row.style.gridTemplateColumns = "1fr 80px 90px";
    row.style.gap = "8px";
    row.style.marginTop = "8px";

    const select = UI.el("select", "input pizza-select");
    (options || []).forEach((o) => {
      const opt = document.createElement("option");
      opt.value = o.id;
      opt.textContent = `${o.name} (${o.price}€)`;
      select.appendChild(opt);
    });

    const qty = UI.el("input", "input pizza-qty");
    qty.type = "number";
    qty.min = "1";
    qty.value = "1";

    const remove = UI.el("button", "btn btn-outline", "Rimuovi");
    remove.type = "button";
    remove.onclick = () => row.remove();

    row.append(select, qty, remove);
    return row;
  }

  async function ensureMenu() {
    if (!IS_PIZZERIA) return; // niente menu per sushi
    try {
      if (!MENU.length) MENU = await fetchJSON("/api/menu");
    } catch {
      MENU = [];
    }
  }

  function setupModal() {
    const openBtn  = document.getElementById("btn-new");
    const closeBtn = document.getElementById("modalClose");
    const saveBtn  = document.getElementById("modalSave");

    // elementi "pizze" potrebbero NON esistere (sushi)
    const addPizza = document.getElementById("pizzaAdd");
    const rowsBox  = document.getElementById("pizzaRows");
    const modal    = document.getElementById("modal");

    if (openBtn)
      openBtn.onclick = async (e) => {
        e.preventDefault();
        await ensureMenu();
        if (IS_PIZZERIA && rowsBox) {
          rowsBox.innerHTML = "";
          if (MENU.length) rowsBox.appendChild(pizzaRowTemplate(MENU));
        }
        UI.openModal();
      };

    if (closeBtn)
      closeBtn.onclick = (e) => { e.preventDefault(); UI.closeModal(); };

    // click fuori modale = chiudi
    if (modal)
      modal.addEventListener("click", (e) => {
        if (e.target === modal) UI.closeModal();
      });

    // ESC chiude
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") UI.closeModal();
    });

    if (addPizza)
      addPizza.onclick = (e) => {
        e.preventDefault();
        if (!IS_PIZZERIA || !rowsBox) return;
        if (!MENU.length) { UI.toast("Nessun menu disponibile."); return; }
        rowsBox.appendChild(pizzaRowTemplate(MENU));
      };

    if (saveBtn)
      saveBtn.onclick = async (e) => {
        e.preventDefault();

        const body = {
          customer_name: (document.getElementById("m-name")?.value || "").trim(),
          phone: (document.getElementById("m-phone")?.value || "").trim(),
          date: document.getElementById("m-date")?.value || "",
          time: document.getElementById("m-time")?.value || "",
          people: Number(document.getElementById("m-people")?.value || 1),
          pizzas: [],
        };

        if (IS_PIZZERIA) {
          document.querySelectorAll(".pizza-row").forEach((r) => {
            const pid = Number(r.querySelector(".pizza-select")?.value || 0);
            const qty = Number(r.querySelector(".pizza-qty")?.value || 0);
            if (pid > 0 && qty > 0) body.pizzas.push({ pizza_id: pid, qty });
          });
        }

        if (!body.customer_name || !body.date || !body.time || body.people < 1) {
          UI.toast("Compila almeno Nome, Data, Ora e Persone.");
          return;
        }

        try {
          await fetchJSON("/api/reservations", {
            method: "POST",
            body: JSON.stringify(body),
          });
          UI.closeModal();

          // reset campi principali
          const nm = document.getElementById("m-name");
          const ph = document.getElementById("m-phone");
          if (nm) nm.value = "";
          if (ph) ph.value = "";
          if (IS_PIZZERIA && rowsBox) rowsBox.innerHTML = "";

          await load();
        } catch (err) {
          UI.toast("Errore salvataggio: " + err.message);
        }
      };
  }

  /* -------------------- Init -------------------- */
  document.addEventListener("DOMContentLoaded", () => {
    setupFilters();
    setupModal();
    load();
  });

})();
