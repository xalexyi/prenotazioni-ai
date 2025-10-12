(function () {
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  // ------------- Helpers -------------
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

  // ------------- Reservations table -------------
  const tbody = $("#reservations-tbody");
  const dateFilter = $("#filter-date");
  const qFilter = $("#filter-q");

  async function loadReservations() {
    const params = new URLSearchParams();
    if (dateFilter && dateFilter.value) params.set("date", dateFilter.value);
    if (qFilter && qFilter.value) params.set("q", qFilter.value);
    const data = await api(`/api/reservations?${params.toString()}`);
    renderReservations(data.items || []);
  }

  function renderReservations(items) {
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!items.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 8;
      td.textContent = "Nessuna prenotazione trovata";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    for (const r of items) {
      const tr = document.createElement("tr");

      const tdDate = document.createElement("td");
      tdDate.className = "col-time";
      tdDate.innerHTML = `<span class="time-dot"></span>${r.date} <div style="opacity:.7">${r.time}</div>`;
      tr.appendChild(tdDate);

      const tdName = document.createElement("td");
      tdName.textContent = r.name;
      tr.appendChild(tdName);

      const tdPhone = document.createElement("td");
      tdPhone.textContent = r.phone || "-";
      tr.appendChild(tdPhone);

      const tdPeople = document.createElement("td");
      tdPeople.className = "col-people";
      tdPeople.textContent = r.people;
      tr.appendChild(tdPeople);

      const tdStatus = document.createElement("td");
      tdStatus.className = "col-state";
      tdStatus.innerHTML = `<span class="badge badge-success">${r.status}</span>`;
      tr.appendChild(tdStatus);

      const tdNote = document.createElement("td");
      tdNote.textContent = r.note || "—";
      tr.appendChild(tdNote);

      const tdActions = document.createElement("td");
      tdActions.className = "col-actions";
      tdActions.innerHTML = `
        <div class="actions">
          <button class="btn btn-outline btn-sm" data-act="edit">Modifica</button>
          <button class="btn btn-success btn-sm" data-act="confirm">Conferma</button>
          <button class="btn btn-outline btn-sm" data-act="reject">Rifiuta</button>
          <button class="btn btn-danger btn-sm" data-act="del">Elimina</button>
        </div>`;
      tdActions.addEventListener("click", async (e) => {
        const act = e.target.closest("button")?.dataset?.act;
        if (!act) return;
        if (act === "del") {
          if (!confirm("Eliminare la prenotazione?")) return;
          await api(`/api/reservations/${r.id}`, { method: "DELETE" });
          toast("Prenotazione eliminata");
          loadReservations();
        } else if (act === "confirm") {
          await api(`/api/reservations/${r.id}`, {
            method: "PUT",
            body: JSON.stringify({ status: "Confermata" }),
          });
          toast("Prenotazione confermata");
          loadReservations();
        } else if (act === "reject") {
          await api(`/api/reservations/${r.id}`, {
            method: "PUT",
            body: JSON.stringify({ status: "Rifiutata" }),
          });
          toast("Prenotazione rifiutata");
          loadReservations();
        } else if (act === "edit") {
          // semplice prompt di esempio
          const newNote = prompt("Nota:", r.note || "");
          if (newNote !== null) {
            await api(`/api/reservations/${r.id}`, {
              method: "PUT",
              body: JSON.stringify({ note: newNote }),
            });
            toast("Prenotazione aggiornata");
            loadReservations();
          }
        }
      });
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    }
  }

  // Bind filtri
  $("#btn-filter")?.addEventListener("click", () => loadReservations());
  $("#btn-clear")?.addEventListener("click", () => {
    if (dateFilter) dateFilter.value = "";
    if (qFilter) qFilter.value = "";
    loadReservations();
  });
  $("#btn-today")?.addEventListener("click", () => {
    const d = new Date();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    if (dateFilter) dateFilter.value = `${d.getFullYear()}-${mm}-${dd}`;
    loadReservations();
  });

  // Modal "nuova prenotazione" (semplificato)
  $("#btn-new")?.addEventListener("click", () => {
    $("#modal-new")?.removeAttribute("hidden");
  });
  $("[data-close='modal-new']")?.addEventListener("click", () => {
    $("#modal-new")?.setAttribute("hidden", "true");
  });
  $("#form-new")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    const payload = {
      date: f.date.value,
      time: f.time.value,
      name: f.name.value,
      phone: f.phone.value,
      people: Number(f.people.value || 2),
      status: f.status.value || "Confermata",
      note: f.note.value || "",
    };
    await api("/api/reservations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast("Prenotazione creata");
    $("#modal-new")?.setAttribute("hidden", "true");
    loadReservations();
  });

  // First load
  window.addEventListener("DOMContentLoaded", () => {
    loadReservations().catch((e) => console.error(e));
  });
})();
