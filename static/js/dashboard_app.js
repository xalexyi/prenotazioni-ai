// static/js/dashboard_app.js

(function () {
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ---------------------------
  // Helpers
  // ---------------------------
  function itDateToISO(value) {
    // accetta "YYYY-MM-DD" oppure "DD/MM/YYYY"
    if (!value) return "";
    const v = value.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v;
    const m = v.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (m) {
      const [, d, mth, y] = m;
      return `${y}-${mth}-${d}`;
    }
    return v; // lascio stare, backend valida comunque
  }

  function mapStatusToDB(v) {
    if (!v) return "PENDING";
    const s = v.toString().trim().toUpperCase();
    if (["CONFERMATA", "CONFERMATO", "CONFIRMED"].includes(s)) return "CONFIRMED";
    if (["ANNULLATA", "ANNULLATO", "RIFIUTATA", "RIFIUTA", "CANCELLED"].includes(s)) return "CANCELLED";
    return "PENDING";
  }

  async function jsonFetch(url, opts = {}) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      const msg = data.error || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  }

  // ---------------------------
  // UI: Modale nuova prenotazione
  // ---------------------------
  function openNewReservationModal() {
    const modal = $("#modal-new-reservation");
    if (!modal) return;
    modal.classList.add("open");
    $("input[name=date]", modal).focus();
  }

  function closeNewReservationModal() {
    const modal = $("#modal-new-reservation");
    if (!modal) return;
    modal.classList.remove("open");
  }

  function serializeReservationForm(modal) {
    return {
      date: itDateToISO($("input[name=date]", modal).value),
      time: $("input[name=time]", modal).value.trim(), // HH:MM
      name: $("input[name=name]", modal).value.trim(),
      phone: $("input[name=phone]", modal).value.trim(),
      people: parseInt($("input[name=people]", modal).value || "2", 10),
      status: mapStatusToDB($("select[name=status]", modal).value),
      note: $("textarea[name=note]", modal).value.trim(),
    };
  }

  async function saveReservation() {
    const modal = $("#modal-new-reservation");
    try {
      const payload = serializeReservationForm(modal);
      const data = await jsonFetch("/api/reservations", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      closeNewReservationModal();
      alert("Prenotazione salvata ✅");
      // TODO: ricarica lista
      loadReservations();
    } catch (e) {
      alert("Errore salvataggio prenotazione: " + e.message);
    }
  }

  async function loadReservations() {
    try {
      const dayInput = $("#filter-date");
      const day = itDateToISO(dayInput ? dayInput.value : "");
      const qs = day ? `?date=${encodeURIComponent(day)}` : "";
      const data = await jsonFetch(`/api/reservations${qs}`);
      const list = data.items || [];
      renderReservations(list);
    } catch (e) {
      console.warn("Errore caricamento prenotazioni:", e);
    }
  }

  function renderReservations(items) {
    const body = $("#reservations-body");
    if (!body) return;
    body.innerHTML = items
      .map(
        (r) => `
      <tr>
        <td>${r.date} ${r.time}</td>
        <td>${r.name || ""}</td>
        <td>${r.phone || ""}</td>
        <td>${r.people || "-"}</td>
        <td>${r.status || "-"}</td>
        <td>${r.note || "-"}</td>
        <td><!-- azioni --></td>
      </tr>`
      )
      .join("");
  }

  // ---------------------------
  // Bind
  // ---------------------------
  function bind() {
    const btnNew = $("#btn-new-reservation");
    if (btnNew) btnNew.addEventListener("click", openNewReservationModal);

    const btnClose = $("#modal-new-reservation .btn-close");
    if (btnClose) btnClose.addEventListener("click", closeNewReservationModal);

    const btnSave = $("#modal-new-reservation .btn-save");
    if (btnSave) btnSave.addEventListener("click", saveReservation);

    const filterDate = $("#filter-date");
    if (filterDate) filterDate.addEventListener("change", loadReservations);
  }

  // Init
  bind();
  loadReservations();
})();
