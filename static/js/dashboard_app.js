(function () {
  // ---- helpers
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const fmtDate = (d) => d.toISOString().slice(0, 10);

  // ---- drawer
  const drawer = $("#drawer");
  $("#btn-menu")?.addEventListener("click", () => drawer.hidden = false);
  $("#drawer-close")?.addEventListener("click", () => drawer.hidden = true);
  $$("#drawer .drawer-link").forEach(a => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      $$("#drawer .drawer-link").forEach(x => x.classList.remove("active"));
      a.classList.add("active");
      drawer.hidden = true;
      showSection(a.dataset.nav);
    });
  });

  // ---- theme
  const btnTheme = $("#btn-theme");
  const applyTheme = (t) => document.documentElement.setAttribute("data-theme", t);
  btnTheme?.addEventListener("click", async () => {
    const cur = document.documentElement.getAttribute("data-theme") || "dark";
    const next = cur === "dark" ? "light" : "dark";
    applyTheme(next);
    await fetch("/api/theme", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ theme: next })});
  });

  // ---- filters
  const fDate = $("#f-date");
  const today = new Date();
  if (fDate) fDate.value = [today.getDate().toString().padStart(2,"0"), (today.getMonth()+1).toString().padStart(2,"0"), today.getFullYear()].join("/");

  $("#btn-today")?.addEventListener("click", () => {
    const d = new Date();
    fDate.value = [d.getDate().toString().padStart(2,"0"), (d.getMonth()+1).toString().padStart(2,"0"), d.getFullYear()].join("/");
    loadReservations();
  });
  $("#btn-filter")?.addEventListener("click", loadReservations);
  $("#btn-clear")?.addEventListener("click", () => { $("#f-q").value = ""; loadReservations(); });

  // ---- reservations table
  async function loadReservations() {
    const d = parseInputDate($("#f-date").value);
    const url = d ? `/api/reservations?date=${d}` : "/api/reservations";
    const r = await fetch(url);
    if (!r.ok) return;
    const js = await r.json();
    const tbody = $("#res-body");
    tbody.innerHTML = "";
    if (!js.items || !js.items.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="muted">Nessuna prenotazione trovata.</td></tr>`;
      return;
    }
    for (const it of js.items) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><span class="time-dot"></span>${it.date} ${it.time}</td>
        <td>${it.name}</td>
        <td>${it.phone || ""}</td>
        <td class="center">${it.people}</td>
        <td>${it.status}</td>
        <td>${it.note || ""}</td>
        <td>
          <div class="actions">
            <button class="btn btn-outline btn-sm" data-act="edit" data-id="${it.id}">Modifica</button>
            <button class="btn btn-success btn-sm" data-act="confirm" data-id="${it.id}">Conferma</button>
            <button class="btn btn-outline btn-sm" data-act="reject" data-id="${it.id}">Rifiuta</button>
            <button class="btn btn-danger btn-sm" data-act="del" data-id="${it.id}">Elimina</button>
          </div>
        </td>`;
      tbody.appendChild(tr);
    }
  }

  function parseInputDate(it) {
    if (!it) return null;
    // expected "dd/mm/yyyy"
    const m = it.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!m) return null;
    return `${m[3]}-${m[2]}-${m[1]}`;
  }

  // ---- modal new reservation
  const modal = $("#modal");
  const openModal = () => modal.hidden = false;
  const closeModal = () => modal.hidden = true;
  $("#modal-x")?.addEventListener("click", closeModal);
  $("#modal-cancel")?.addEventListener("click", closeModal);
  $("#btn-new")?.addEventListener("click", () => {
    const d = parseInputDate($("#f-date").value) || fmtDate(new Date());
    $("#m-date").value = d;
    $("#m-time").value = "20:00";
    $("#m-name").value = "";
    $("#m-phone").value = "";
    $("#m-people").value = "2";
    $("#m-status").value = "CONFERMATA";
    $("#m-note").value = "";
    openModal();
  });
  $("#modal-save")?.addEventListener("click", async () => {
    const payload = {
      date: $("#m-date").value,
      time: $("#m-time").value,
      name: $("#m-name").value,
      phone: $("#m-phone").value,
      people: parseInt($("#m-people").value || "0", 10),
      status: $("#m-status").value,
      note: $("#m-note").value
    };
    const r = await fetch("/api/reservations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (r.ok) {
      closeModal();
      loadReservations();
    } else {
      alert("Errore salvataggio prenotazione");
    }
  });

  // ---- sections visibility
  function showSection(key) {
    for (const id of ["sec-hours","sec-special","sec-prices","sec-menu","sec-stats"]) {
      const el = document.getElementById(id);
      if (el) el.classList.add("hidden");
    }
    if (key === "dash") return;
    const map = { hours:"sec-hours", special:"sec-special", prices:"sec-prices", menu:"sec-menu", stats:"sec-stats" };
    const sec = document.getElementById(map[key]);
    if (sec) sec.classList.remove("hidden");
  }

  // ---- hours save
  $("#btn-save-hours")?.addEventListener("click", async () => {
    const obj = {};
    $$("#hours-grid input").forEach(inp => obj[inp.dataset.key] = inp.value.trim());
    const r = await fetch("/api/hours", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ hours: obj })});
    if (!r.ok) return alert("Errore salvataggio orari");
    toast("Orari salvati ✔");
  });

  // build hours inputs
  const days = [["mon","Lun"],["tue","Mar"],["wed","Mer"],["thu","Gio"],["fri","Ven"],["sat","Sab"],["sun","Dom"]];
  const grid = $("#hours-grid");
  if (grid) {
    for (const [k, label] of days) {
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `<label>${label}</label><input data-key="${k}" placeholder="12:00-15:00, 19:00-23:00">`;
      grid.appendChild(row);
    }
  }

  // ---- special days
  $("#btn-save-special")?.addEventListener("click", async () => {
    const payload = {
      date: $("#sp-date").value,
      closed_all_day: $("#sp-closed").value === "1",
      windows: $("#sp-windows").value
    };
    const r = await fetch("/api/special-days", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    if (!r.ok) return alert("Errore salvataggio giorno speciale");
    toast("Giorno speciale salvato ✔");
  });

  function toast(msg) {
    const t = $("#toast");
    if (!t) return alert(msg);
    t.textContent = msg;
    t.hidden = false;
    setTimeout(() => { t.hidden = true; }, 2500);
  }

  // initial load
  loadReservations();
})();
