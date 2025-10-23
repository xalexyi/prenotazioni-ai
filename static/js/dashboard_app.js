(function () {
  const $ = (q) => document.querySelector(q);
  const fmtIT = (d) => {
    const [y, m, day] = d.split("-");
    return `${day}/${m}/${y}`;
  };

  // Drawer
  const drawer = $("#drawer");
  $("#sidebarBtn")?.addEventListener("click", () => drawer.classList.remove("hidden"));
  $("#drawerClose")?.addEventListener("click", () => drawer.classList.add("hidden"));

  // Modal
  const modal = $("#modal");
  const openModal = () => modal.classList.remove("hidden");
  const closeModal = () => modal.classList.add("hidden");
  $("#btnNew")?.addEventListener("click", () => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    const d = String(today.getDate()).padStart(2, "0");
    $("#mDate").value = `${y}-${m}-${d}`;
    $("#mTime").value = "20:00";
    $("#mName").value = "";
    $("#mPhone").value = "";
    $("#mPeople").value = 2;
    $("#mStatus").value = "PENDING";
    $("#mNote").value = "";
    openModal();
  });
  $("#modalClose")?.addEventListener("click", closeModal);
  $("#modalCancel")?.addEventListener("click", closeModal);

  // Filtri
  const inputDate = $("#fDate");
  const rows = $("#rows");

  const todayStr = () => {
    const t = new Date();
    return `${String(t.getDate()).padStart(2, "0")}/${String(t.getMonth() + 1).padStart(2, "0")}/${t.getFullYear()}`;
  };
  inputDate.value = todayStr();

  $("#btnToday")?.addEventListener("click", () => {
    inputDate.value = todayStr();
    load();
  });
  $("#btnClear")?.addEventListener("click", () => {
    $("#fSearch").value = "";
    inputDate.value = todayStr();
    load();
  });
  $("#btnFilter")?.addEventListener("click", load);

  // Load prenotazioni
  async function load() {
    const v = inputDate.value.trim();
    const ddmmyyyy = v.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    let param = v;
    if (ddmmyyyy) {
      param = `${ddmmyyyy[3]}-${ddmmyyyy[2]}-${ddmmyyyy[1]}`;
    }
    const res = await fetch(`/api/reservations?date=${encodeURIComponent(param)}`);
    const js = await res.json();
    rows.innerHTML = "";
    if (!js.ok) {
      rows.innerHTML = `<div class="tr"><div class="td col2">Errore caricamento</div></div>`;
      return;
    }
    js.items.forEach((r) => {
      const tr = document.createElement("div");
      tr.className = "tr";
      tr.innerHTML = `
        <div class="td">${fmtIT(r.date)} ${r.time}</div>
        <div class="td">${r.name}</div>
        <div class="td">${r.phone || ""}</div>
        <div class="td">${r.people}</div>
        <div class="td">${r.status}</div>
        <div class="td">${r.note || ""}</div>
        <div class="td">
          <button class="btn btn-xs">Conferma</button>
          <button class="btn btn-xs btn-danger">Elimina</button>
        </div>`;
      rows.appendChild(tr);
    });
    // contatori semplici
    $("#statBookings").textContent = js.items.length;
  }

  load();

  // Salvataggio nuova prenotazione
  $("#modalSave")?.addEventListener("click", async () => {
    const payload = {
      date: $("#mDate").value.trim(),
      time: $("#mTime").value.trim(),
      name: $("#mName").value.trim(),
      phone: $("#mPhone").value.trim(),
      people: $("#mPeople").value.trim(),
      status: $("#mStatus").value.trim(),
      note: $("#mNote").value.trim(),
    };
    try {
      const res = await fetch("/api/reservations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const js = await res.json();
      if (!js.ok) throw new Error(js.error || "Errore salvataggio prenotazione");
      closeModal();
      alert("Prenotazione salvata");
      load();
    } catch (e) {
      alert(e.message);
    }
  });
})();
