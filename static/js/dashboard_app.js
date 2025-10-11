// =========================================================================
// dashboard_app.js - wiring pagina dashboard
// Dipendenze: main.js (import ES module)
// Assicurati che in base.html i <script> siano type="module"
// =========================================================================
import { $, $$, h, toast, showModal, closeModal, fmtDateISO, safeNumber, API } from "./main.js";

(function () {
  // ---------- NAV laterale: mostra pannelli ----------
  function showPage(id) {
    const pages = $$(".page");
    pages.forEach(p => p.classList.toggle("active", p.id === id));

    const links = $$(".side-nav [data-nav]");
    links.forEach(a => a.classList.toggle("active", a.dataset.nav === id));
  }

  function initSideNav() {
    $$(".side-nav [data-nav]").forEach(a => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const id = a.dataset.nav;
        if (id) showPage(id);
      });
    });
    // apertura di default
    const first = $(".side-nav [data-nav]");
    if (first) showPage(first.dataset.nav);
  }

  // ---------- Prenotazioni ----------
  function reservationModal(data = {}) {
    const today = fmtDateISO(new Date());
    const form = h("form", { class: "form-grid", onsubmit: (e) => e.preventDefault() },
      h("label", { class: "lbl" }, "Data",
        h("input", { class: "input", type: "date", name: "date", value: data.date || today })
      ),
      h("label", { class: "lbl" }, "Ora",
        h("input", { class: "input", type: "time", name: "time", value: data.time || "20:00" })
      ),
      h("label", { class: "lbl full" }, "Nome",
        h("input", { class: "input", name: "name", value: data.name || "" })
      ),
      h("label", { class: "lbl full" }, "Telefono",
        h("input", { class: "input", name: "phone", value: data.phone || "" })
      ),
      h("label", { class: "lbl" }, "Persone",
        h("input", { class: "input", type: "number", min: "1", step: "1", name: "people", value: data.people || 2 })
      ),
      h("label", { class: "lbl" }, "Stato",
        h("select", { class: "input", name: "status" },
          h("option", { value: "Confermata", selected: (data.status || "Confermata") === "Confermata" }, "Confermata"),
          h("option", { value: "In attesa",  selected: data.status === "In attesa"  }, "In attesa"),
          h("option", { value: "Annullata", selected: data.status === "Annullata" }, "Annullata"),
        )
      ),
      h("label", { class: "lbl full" }, "Note",
        h("input", { class: "input", name: "note", value: data.note || "", placeholder: "Allergie, tavolo, ecc." })
      ),
    );

    const read = () => Object.fromEntries(new FormData(form));

    showModal(data.id ? "Modifica prenotazione" : "Crea prenotazione", form, [
      { label: "Chiudi", onClick: closeModal },
      {
        label: data.id ? "Salva modifiche" : "Crea prenotazione",
        primary: true,
        onClick: async () => {
          try {
            const payload = read();
            payload.people = safeNumber(payload.people, 2);
            if (!data.id) {
              await API.createReservation(payload);
              toast("Prenotazione creata");
            } else {
              await API.updateReservation(data.id, payload);
              toast("Prenotazione aggiornata");
            }
            closeModal();
            await refreshReservations();
          } catch (e) {
            toast(`Errore: ${e.message}`, "err");
          }
        },
      },
    ]);
  }

  async function refreshReservations() {
    const day = $("#filter-date")?.value || "";
    const q   = $("#filter-q")?.value || "";
    let res;
    try {
      res = await API.listReservations({ date: day, q });
    } catch (e) {
      toast(`Errore caricamento: ${e.message}`, "err");
      return;
    }

    const list = $("#reservations-list");
    if (!list) return;

    list.innerHTML = "";
    (res.items || []).forEach(r => {
      const row = h("div", { class: "res-card" },
        h("div", { class: "res-main" },
          h("div", { class: "res-title" }, `${r.date} ${r.time} — ${r.name}`),
          h("div", { class: "res-sub" }, `${r.phone || "-"} • ${r.people} p • ${r.status}`)
        ),
        h("div", { class: "res-actions" },
          h("button", { class: "btn", onClick: () => reservationModal(r) }, "Modifica"),
          h("button", {
            class: "btn btn-danger",
            onClick: async () => {
              if (!confirm("Eliminare la prenotazione?")) return;
              try {
                await API.deleteReservation(r.id);
                toast("Eliminata");
                await refreshReservations();
              } catch (e) {
                toast(`Errore: ${e.message}`, "err");
              }
            },
          }, "Elimina")
        )
      );
      list.appendChild(row);
    });

    if (!res.items || res.items.length === 0) {
      list.appendChild(h("div", { class: "empty" }, "Nessuna prenotazione trovata"));
    }
  }

  function wireReservations() {
    $("#btn-new-reservation")?.addEventListener("click", () => reservationModal());

    $("#btn-filter")?.addEventListener("click", refreshReservations);
    $("#btn-clear")?.addEventListener("click", () => {
      if ($("#filter-date")) $("#filter-date").value = "";
      if ($("#filter-q")) $("#filter-q").value = "";
      refreshReservations();
    });

    // caricamento iniziale
    refreshReservations();
  }

  // ---------- Orari settimanali ----------
  async function saveWeeklyHours(map) {
    try {
      await API.saveHours(map);
      toast("Orari salvati");
    } catch (e) {
      toast(`Errore: ${e.message}`, "err");
    }
  }

  function wireWeeklyHours() {
    $$('.btn[data-action="save-hours"]').forEach(btn => {
      btn.addEventListener("click", async () => {
        const inputs = $$(".weekly-hours [data-day]");
        const payload = {};
        inputs.forEach(inp => (payload[String(inp.dataset.day)] = inp.value || ""));
        await saveWeeklyHours(payload);
      });
    });
  }

  // ---------- Giorni speciali ----------
  async function saveSpecialDay(payload) {
    try {
      await API.saveSpecialDay(payload);
      toast("Giorno speciale salvato");
      await refreshSpecialDaysList();
    } catch (e) {
      toast(`Errore: ${e.message}`, "err");
    }
  }

  async function refreshSpecialDaysList() {
    const container = $("#special-days-list");
    if (!container) return;
    container.innerHTML = "";

    let data = [];
    try {
      // se il backend non ha GET /api/special-days, mostriamo solo “ultimo salvato”
      data = await API.listSpecialDays("", ""); // se 404 lato server, verrà catchato
      if (Array.isArray(data.items)) data = data.items;
      else if (Array.isArray(data))  data = data;
      else data = [];
    } catch {
      // ignora: niente endpoint GET → non rompiamo la pagina
    }

    if (data.length === 0) {
      container.appendChild(h("div", { class: "empty" }, "Nessun giorno speciale aggiunto"));
      return;
    }

    data.forEach(d => {
      const line = h("div", { class: "line" },
        h("div", { class: "k" }, d.date || d.day || "-"),
        h("div", { class: "v" }, (d.closed ? "Chiuso tutto il giorno" : (d.windows || "-")))
      );
      container.appendChild(line);
    });
  }

  function wireSpecialDays() {
    $$('.btn[data-action="save-special"]').forEach(btn => {
      btn.addEventListener("click", async () => {
        const day     = ($('[name="special-date"]')?.value || "").trim();
        const closed  = !!$('#special-closed')?.checked;
        const windows = ($('[name="special-windows"]')?.value || "").trim();
        if (!day) { toast("Inserisci una data (YYYY-MM-DD)", "err"); return; }
        await saveSpecialDay({ day, closed, windows });
      });
    });

    refreshSpecialDaysList();
  }

  // ---------- Prezzi & coperti ----------
  function wirePricing() {
    $$('.btn[data-action="save-pricing"]').forEach(btn => {
      btn.addEventListener("click", async () => {
        const avg_price = $('[name="avg_price"]')?.value ?? "";
        const cover     = $('[name="cover"]')?.value ?? "";
        const seats_cap = $('[name="seats_cap"]')?.value ?? "";
        const min_people= $('[name="min_people"]')?.value ?? "";
        try {
          await API.savePricing({ avg_price, cover, seats_cap, min_people });
          toast("Impostazioni prezzi salvate");
        } catch (e) {
          toast(`Errore: ${e.message}`, "err");
        }
      });
    });
  }

  // ---------- Menu digitale ----------
  function wireMenu() {
    $$('.btn[data-action="save-menu"]').forEach(btn => {
      btn.addEventListener("click", async () => {
        const menu_url  = $('[name="menu_url"]')?.value ?? "";
        const menu_desc = $('[name="menu_desc"]')?.value ?? "";
        try {
          await API.saveMenu({ menu_url, menu_desc });
          toast("Menu digitale salvato");
        } catch (e) {
          toast(`Errore: ${e.message}`, "err");
        }
      });
    });
  }

  // ---------- Statistiche ----------
  async function refreshStats() {
    try {
      const date = $("#stats-date")?.value || "";
      const s = await API.stats({ date });
      $("#stats-total") && ($("#stats-total").textContent = String(s.total_reservations ?? 0));
      $("#stats-avgp")  && ($("#stats-avgp").textContent  = String(Number(s.avg_people ?? 0).toFixed(1)));
      $("#stats-avgpr") && ($("#stats-avgpr").textContent = `${Number(s.avg_price ?? 0).toFixed(0)}€`);
      $("#stats-rev")   && ($("#stats-rev").textContent   = `${Number(s.estimated_revenue ?? 0).toFixed(0)}€`);
    } catch (e) {
      toast(`Errore stats: ${e.message}`, "err");
    }
  }
  function wireStats() {
    $("#stats-refresh")?.addEventListener("click", refreshStats);
    refreshStats();
  }

  // ---------- Init ----------
  document.addEventListener("DOMContentLoaded", () => {
    initSideNav();
    wireReservations();
    wireWeeklyHours();
    wireSpecialDays();
    wirePricing();
    wireMenu();
    wireStats();
  });
})();
