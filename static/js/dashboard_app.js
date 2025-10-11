// --------- Utilities
const $ = (s, r=document)=> r.querySelector(s);
const $$ = (s, r=document)=> [...r.querySelectorAll(s)];
const j = (url, opts={}) =>
  fetch(url, Object.assign({headers:{'Content-Type':'application/json'}}, opts)).then(r=>r.json());

function ymd_from_it(it){ // "gg/mm/aaaa" -> "YYYY-MM-DD"
  if(!it) return "";
  const [g,m,a] = it.split("/"); if(!g||!m||!a) return "";
  return `${a}-${m.padStart(2,"0")}-${g.padStart(2,"0")}`;
}
function it_from_ymd(ymd){ // "YYYY-MM-DD" -> "gg/mm/aaaa"
  if(!ymd) return "";
  const [a,m,g] = ymd.split("-");
  return `${g}/${m}/${a}`;
}

// --------- Prenotazioni
async function loadReservations(){
  const q = $("#f-q")?.value?.trim() || "";
  const dateIt = $("#f-date")?.value?.trim() || "";
  const date = dateIt ? ymd_from_it(dateIt) : "";
  const url = `/api/reservations${q || date ? `?${new URLSearchParams({q, date}).toString()}`:""}`;
  const res = await j(url);
  const list = $("#res-list");
  list.innerHTML = "";
  if(!res.ok || !res.items?.length){
    list.innerHTML = `<div class="empty">Nessuna prenotazione trovata</div>`;
    $("#kpi-today").textContent = "0";
    $("#kpi-rev").textContent = "0 €";
    return;
  }
  res.items.forEach(r=>{
    const row = document.createElement("div");
    row.className = "item";
    row.innerHTML = `
      <div>${it_from_ymd(r.date)}</div>
      <div>${r.time}</div>
      <div>${r.name}</div>
      <div>${r.phone || "-"}</div>
      <div>${r.people}</div>
      <div>${r.status}</div>
      <div>${r.note || "-"}</div>
      <div></div>
      <div><button class="btn btn-ghost" data-id="${r.id}" data-act="del">Elimina</button></div>
    `;
    list.appendChild(row);
  });
  // small kpi from list size (today filtered)
  $("#kpi-today").textContent = String(res.items.length);
  // revenue estimated -> /api/stats for accuracy
  refreshStatsMini();
}

async function refreshStatsMini(){
  const stat = await j("/api/stats");
  if(stat?.ok){
    $("#kpi-rev").textContent = `${Number(stat.estimated_revenue||0).toFixed(2)} €`;
  }
}

async function createReservation(data){
  const res = await j("/api/reservations", {method:"POST", body: JSON.stringify(data)});
  if(!res.ok) throw new Error(res.error || "Errore creazione");
}

// --------- Modale prenotazione
const modal = $("#res-modal");
function openModal(){ modal.classList.add("is-open"); }
function closeModal(){ modal.classList.remove("is-open"); }
$$("[data-close]", modal).forEach(b => b.addEventListener("click", closeModal));
$(".modal__overlay", modal)?.addEventListener("click", closeModal);

$("#btn-new")?.addEventListener("click", ()=>{
  $("#m-date").value = new Date().toLocaleDateString("it-IT"); // gg/mm/aaaa
  $("#m-time").value = "20:00";
  $("#m-name").value = "";
  $("#m-phone").value = "";
  $("#m-people").value = "2";
  $("#m-status").value = "Confermata";
  $("#m-note").value = "";
  openModal();
});

$("#m-save")?.addEventListener("click", async ()=>{
  try{
    const payload = {
      date: ymd_from_it($("#m-date").value.trim()),
      time: $("#m-time").value.trim(),
      name: $("#m-name").value.trim(),
      phone: $("#m-phone").value.trim(),
      people: Number($("#m-people").value || 2),
      status: $("#m-status").value,
      note: $("#m-note").value.trim(),
    };
    if(!payload.date || !payload.time || !payload.name) return toast("Compila data, ora e nome");
    await createReservation(payload);
    closeModal();
    toast("Prenotazione creata");
    loadReservations();
  }catch(e){ toast("Errore: " + e.message); }
});

// Delete reservation (delegation)
$("#res-list")?.addEventListener("click", async (ev)=>{
  const btn = ev.target.closest("[data-act='del']");
  if(!btn) return;
  const id = btn.dataset.id;
  if(!confirm("Eliminare la prenotazione?")) return;
  const res = await fetch(`/api/reservations/${id}`, {method:"DELETE"});
  const js = await res.json();
  if(js.ok){ toast("Eliminata"); loadReservations(); }
  else toast(js.error || "Errore eliminazione");
});

// Filtri
$("#btn-filter")?.addEventListener("click", loadReservations);
$("#btn-clear")?.addEventListener("click", ()=>{
  $("#f-date").value = ""; $("#f-q").value = ""; loadReservations();
});
$("#btn-today")?.addEventListener("click", ()=>{
  $("#f-date").value = new Date().toLocaleDateString("it-IT"); loadReservations();
});

// --------- Orari settimanali
const DAYS = ["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"];

function buildHoursGrid(){
  const box = $("#hours-grid");
  box.innerHTML = "";
  for(let d=0; d<7; d++){
    const l = document.createElement("div");
    l.className = "dow";
    l.textContent = DAYS[d];
    const inp = document.createElement("input");
    inp.className = "input win";
    inp.dataset.day = String(d);
    inp.placeholder = d<=5 ? "12:00-15:00, 19:00-23:00" : "12:00-15:00, 19:00-23:00";
    box.appendChild(l); box.appendChild(inp);
  }
}
buildHoursGrid();

$("[data-action='save-hours']")?.addEventListener("click", async ()=>{
  const hours = {};
  $$(".win").forEach(i=> hours[i.dataset.day] = i.value.trim());
  const res = await j("/api/hours", {method:"POST", body: JSON.stringify({hours})});
  if(res.ok) toast("Orari salvati"); else toast(res.error || "Errore orari");
});

// --------- Giorni speciali
$("[data-action='save-special']")?.addEventListener("click", async ()=>{
  const day = $("[name='special-date']").value.trim();
  const closed = $("#special-closed").checked;
  const windows = $("#special-windows").value.trim();
  if(!day){ toast("Inserisci una data (YYYY-MM-DD)"); return; }
  const res = await j("/api/special-days", {method:"POST", body: JSON.stringify({day, closed, windows})});
  if(res.ok){ toast("Giorno speciale salvato"); renderSpecialRow({day, closed, windows}); }
  else toast(res.error || "Errore salvataggio");
});

function renderSpecialRow(r){
  const list = $("#special-list");
  const row = document.createElement("div");
  row.className = "item";
  row.innerHTML = `
    <div style="grid-column:1/3"><strong>${r.day}</strong></div>
    <div>${r.closed ? "Chiuso" : (r.windows||"-")}</div>
  `;
  list.prepend(row);
}

// --------- Prezzi & coperti
$("[data-action='save-pricing']")?.addEventListener("click", async ()=>{
  const payload = {
    avg_price: $("[name='avg_price']").value,
    cover: $("[name='cover']").value,
    seats_cap: $("[name='seats_cap']").value,
    min_people: $("[name='min_people']").value,
  };
  const res = await j("/api/pricing", {method:"POST", body: JSON.stringify(payload)});
  if(res.ok) toast("Impostazioni prezzi salvate");
  else toast(res.error || "Errore prezzi");
});

// --------- Menu digitale
$("[data-action='save-menu']")?.addEventListener("click", async ()=>{
  const payload = {
    menu_url: $("[name='menu_url']").value,
    menu_desc: $("[name='menu_desc']").value,
  };
  const res = await j("/api/menu", {method:"POST", body: JSON.stringify(payload)});
  if(res.ok) toast("Menu salvato");
  else toast(res.error || "Errore menu");
});

// --------- Statistiche
async function loadStats(){
  const st = await j("/api/stats");
  const box = $("#stats-box");
  if(!st.ok){ box.textContent = "Errore caricamento"; return; }
  box.innerHTML = `
    <div class="list">
      <div class="item"><div>Prenotazioni</div><div>${st.total_reservations}</div></div>
      <div class="item"><div>Persone per prenotazione (media)</div><div>${Number(st.avg_people||0).toFixed(2)}</div></div>
      <div class="item"><div>Prezzo medio (impostazioni)</div><div>${Number(st.avg_price||0).toFixed(2)} €</div></div>
      <div class="item"><div>Incasso stimato</div><div>${Number(st.estimated_revenue||0).toFixed(2)} €</div></div>
    </div>
  `;
}
$("#stats-refresh")?.addEventListener("click", loadStats);

// --------- Bootstrap
window.addEventListener("DOMContentLoaded", ()=>{
  loadReservations();
  loadStats();
});
