// ===========================================================
// Prenotazioni-AI Frontend Main Script
// ===========================================================

// ---------------- Sidebar ----------------
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");
if (sidebar && sidebarToggle) {
  sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("hidden");
  });
}

// ---------------- Sezioni ----------------
const sections = document.querySelectorAll(".section");
document.querySelectorAll(".nav-link").forEach(link => {
  link.addEventListener("click", e => {
    e.preventDefault();
    document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
    link.classList.add("active");
    const sec = link.dataset.section;
    sections.forEach(s => s.classList.remove("visible"));
    document.getElementById(sec).classList.add("visible");
    if (window.innerWidth < 900) sidebar.classList.add("hidden");
    if (sec === "reservations") loadReservations();
    if (sec === "hours") loadHours();
    if (sec === "special-days") loadSpecialDays();
    if (sec === "menu") loadMenu();
    if (sec === "settings") loadSettings();
    if (sec === "stats") loadStats();
  });
});

// ---------------- Tema ----------------
const themeBtn = document.getElementById("themeToggle");
if (themeBtn) {
  themeBtn.addEventListener("click", async () => {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    await fetch("/api/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: next })
    });
  });
}

// ---------------- Toast ----------------
function showToast(msg, type = "ok") {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2500);
}

// ===========================================================
// Prenotazioni
// ===========================================================

const listBox = document.getElementById("reservationsList");
const addBtn = document.getElementById("addReservation");

async function loadReservations() {
  const res = await fetch("/api/reservations");
  const data = await res.json();
  if (!data.length) {
    listBox.innerHTML = `<p class='text-muted'>Nessuna prenotazione.</p>`;
    return;
  }
  listBox.innerHTML = `
    <table class="table">
      <thead>
        <tr><th>Nome</th><th>Data</th><th>Ora</th><th>Persone</th><th>Note</th><th class="col-actions">Azioni</th></tr>
      </thead>
      <tbody>
        ${data.map(r => `
          <tr>
            <td>${r.name}</td>
            <td>${r.date}</td>
            <td>${r.time}</td>
            <td>${r.people}</td>
            <td>${r.note || ""}</td>
            <td>
              <div class="actions">
                <button class="btn btn-outline btn-sm" onclick="editReservation(${r.id})">✏️</button>
                <button class="btn btn-danger btn-sm" onclick="deleteReservation(${r.id})">🗑️</button>
              </div>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

if (addBtn) addBtn.addEventListener("click", () => openReservationModal());

function openReservationModal(resv = null) {
  const html = `
  <div class="modal-backdrop">
    <div class="modal">
      <div class="modal-header">
        <h3>${resv ? "Modifica Prenotazione" : "Nuova Prenotazione"}</h3>
        <button class="modal-close" onclick="closeModal()">✖</button>
      </div>
      <div class="modal-body">
        <label>Nome</label><input id="r-name" value="${resv?.name || ""}">
        <label>Telefono</label><input id="r-phone" value="${resv?.phone || ""}">
        <label>Persone</label><input id="r-people" type="number" value="${resv?.people || 2}">
        <label>Data</label><input id="r-date" type="date" value="${resv?.date || ""}">
        <label>Ora</label><input id="r-time" type="time" value="${resv?.time || ""}">
        <label>Note</label><textarea id="r-note">${resv?.note || ""}</textarea>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline" onclick="closeModal()">Annulla</button>
        <button class="btn btn-primary" onclick="saveReservation(${resv?.id || ""})">Salva</button>
      </div>
    </div>
  </div>`;
  document.body.insertAdjacentHTML("beforeend", html);
}

async function saveReservation(id = null) {
  const payload = {
    name: document.getElementById("r-name").value,
    phone: document.getElementById("r-phone").value,
    people: +document.getElementById("r-people").value,
    date: document.getElementById("r-date").value,
    time: document.getElementById("r-time").value,
    note: document.getElementById("r-note").value,
  };
  await fetch(id ? `/api/reservations/${id}` : "/api/reservations", {
    method: id ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  closeModal();
  showToast("Prenotazione salvata ✅");
  loadReservations();
}

async function deleteReservation(id) {
  if (!confirm("Vuoi eliminare questa prenotazione?")) return;
  await fetch(`/api/reservations/${id}`, { method: "DELETE" });
  showToast("Prenotazione eliminata 🗑️");
  loadReservations();
}

function editReservation(id) {
  const row = document.querySelector(`button[onclick='editReservation(${id})']`).closest("tr");
  openReservationModal({
    id,
    name: row.children[0].textContent,
    date: row.children[1].textContent,
    time: row.children[2].textContent,
    people: row.children[3].textContent,
    note: row.children[4].textContent
  });
}

function closeModal() {
  document.querySelectorAll(".modal-backdrop").forEach(m => m.remove());
}

// ===========================================================
// Orari Settimanali
// ===========================================================
async function loadHours() {
  const res = await fetch("/api/hours");
  const data = await res.json();
  const box = document.getElementById("hoursEditor");
  const giorni = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];
  box.innerHTML = giorni.map((g, i) => `
    <div class="form-row">
      <label>${g}</label>
      <input id="h-${i}" value="${data[i] || ""}" placeholder="12:00-15:00, 19:00-23:00">
    </div>
  `).join("") + `<button class="btn btn-primary mt-2" onclick="saveHours()">Salva</button>`;
}

async function saveHours() {
  const data = {};
  for (let i = 0; i < 7; i++) data[i] = document.getElementById(`h-${i}`).value;
  await fetch("/api/hours", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  showToast("Orari salvati ✅");
}

// ===========================================================
// Giorni speciali
// ===========================================================
async function loadSpecialDays() {
  const res = await fetch("/api/special-days");
  const data = await res.json();
  const box = document.getElementById("specialDays");
  box.innerHTML = data.map(d => `
    <div class="form-row">
      <label>${d.date}</label>
      <input value="${d.windows || ""}" placeholder="12:00-15:00, 19:00-23:00">
      <input type="checkbox" ${d.closed ? "checked" : ""}> Chiuso
    </div>
  `).join("") + `<button class="btn btn-primary mt-2" onclick="showToast('Giorni speciali salvati ✅')">Salva</button>`;
}

// ===========================================================
// Impostazioni / Prezzi
// ===========================================================
async function loadSettings() {
  const res = await fetch("/api/settings");
  const s = await res.json();
  const box = document.getElementById("settingsBox");
  box.innerHTML = `
    <div class="form-row"><label>Prezzo Medio</label><input id="set-price" type="number" value="${s.avg_price || ""}"></div>
    <div class="form-row"><label>Coperto (€)</label><input id="set-cover" type="number" value="${s.cover || ""}"></div>
    <div class="form-row"><label>Capienza</label><input id="set-seats" type="number" value="${s.seats_cap || ""}"></div>
    <div class="form-row"><label>Min. Persone</label><input id="set-min" type="number" value="${s.min_people || ""}"></div>
    <div class="form-row"><label>Menu URL</label><input id="set-url" value="${s.menu_url || ""}"></div>
    <div class="form-row"><label>Descrizione</label><textarea id="set-desc">${s.menu_desc || ""}</textarea></div>
    <button class="btn btn-primary mt-2" onclick="saveSettings()">Salva</button>
  `;
}

async function saveSettings() {
  const data = {
    avg_price: +document.getElementById("set-price").value,
    cover: +document.getElementById("set-cover").value,
    seats_cap: +document.getElementById("set-seats").value,
    min_people: +document.getElementById("set-min").value,
    menu_url: document.getElementById("set-url").value,
    menu_desc: document.getElementById("set-desc").value,
  };
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  showToast("Impostazioni salvate ✅");
}

// ===========================================================
// Menu
// ===========================================================
async function loadMenu() {
  const res = await fetch("/api/menu");
  const data = await res.json();
  const box = document.getElementById("menuList");
  if (!data.length) {
    box.innerHTML = `<p class='text-muted'>Nessun piatto nel menu.</p>`;
  } else {
    box.innerHTML = data.map(i => `
      <div class="form-row">
        <span>${i.name}</span>
        <span>€${i.price.toFixed(2)}</span>
        <button class="btn btn-danger btn-sm" onclick="deleteMenuItem(${i.id})">🗑️</button>
      </div>
    `).join("");
  }
}

const addMenu = document.getElementById("addMenuItem");
if (addMenu) addMenu.addEventListener("click", () => openMenuModal());

function openMenuModal() {
  const html = `
  <div class="modal-backdrop">
    <div class="modal">
      <div class="modal-header">
        <h3>Nuovo Piatto</h3>
        <button class="modal-close" onclick="closeModal()">✖</button>
      </div>
      <div class="modal-body">
        <label>Nome</label><input id="m-name">
        <label>Prezzo</label><input id="m-price" type="number" step="0.01">
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline" onclick="closeModal()">Annulla</button>
        <button class="btn btn-primary" onclick="saveMenuItem()">Salva</button>
      </div>
    </div>
  </div>`;
  document.body.insertAdjacentHTML("beforeend", html);
}

async function saveMenuItem() {
  const payload = {
    name: document.getElementById("m-name").value,
    price: document.getElementById("m-price").value,
  };
  await fetch("/api/menu", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  closeModal();
  showToast("Piatto aggiunto 🍽️");
  loadMenu();
}

async function deleteMenuItem(id) {
  if (!confirm("Vuoi eliminare questo piatto?")) return;
  await fetch(`/api/menu?id=${id}`, { method: "DELETE" });
  showToast("Piatto eliminato 🗑️");
  loadMenu();
}

// ===========================================================
// Statistiche
// ===========================================================
async function loadStats() {
  const res = await fetch("/api/stats");
  const stats = await res.json();
  const box = document.getElementById("statsBox");
  box.innerHTML = `
    <p>Prenotazioni oggi: <b>${stats.today_count}</b></p>
    <p>Prenotazioni totali: <b>${stats.total_count}</b></p>
    <p>Persone totali: <b>${stats.total_people}</b></p>
    <p>Incasso stimato: <b>€${stats.estimated_revenue.toFixed(2)}</b></p>
  `;
}
// ... (tutto il codice che ti ho dato prima, resta uguale fino alla fine)

// ===========================================================
// Statistiche con grafici dinamici
// ===========================================================
let chartBookings, chartPeople;

async function loadStats() {
  const res = await fetch("/api/stats");
  const stats = await res.json();
  const box = document.getElementById("statsBox");
  box.innerHTML = `
    <p>Prenotazioni oggi: <b>${stats.today_count}</b></p>
    <p>Prenotazioni totali: <b>${stats.total_count}</b></p>
    <p>Persone totali: <b>${stats.total_people}</b></p>
    <p>Incasso stimato: <b>€${stats.estimated_revenue.toFixed(2)}</b></p>
  `;

  // Simuliamo dati giornalieri (nel backend poi li genereremo)
  const days = stats.trend?.map(d => d.day) || ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"];
  const bookings = stats.trend?.map(d => d.count) || [3,5,2,6,8,7,4];
  const people = stats.trend?.map(d => d.people) || [10,15,8,20,25,30,18];

  const ctx1 = document.getElementById("chartBookings");
  const ctx2 = document.getElementById("chartPeople");

  if (chartBookings) chartBookings.destroy();
  if (chartPeople) chartPeople.destroy();

  chartBookings = new Chart(ctx1, {
    type: "line",
    data: {
      labels: days,
      datasets: [{
        label: "Prenotazioni",
        data: bookings,
        borderColor: "#4c82ff",
        backgroundColor: "rgba(76,130,255,0.2)",
        fill: true,
        tension: 0.3
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#aaa" } },
        y: { ticks: { color: "#aaa" } }
      }
    }
  });

  chartPeople = new Chart(ctx2, {
    type: "bar",
    data: {
      labels: days,
      datasets: [{
        label: "Persone totali",
        data: people,
        backgroundColor: "#1fc772"
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#aaa" } },
        y: { ticks: { color: "#aaa" } }
      }
    }
  });
}
