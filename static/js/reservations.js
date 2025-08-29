/* =======================================================
   Prenotazioni — Frontend
   - Filtri + CRUD AJAX
   - Prezzi fascia oraria (12–15 => 20€, 19–23:30 => 30€)
   - Incasso solo "confirmed"
   - PIZZERIA: menù, pizze in prenotazione, KPI "Pizze ordinate"
   ======================================================= */

const state = { range: "today", date: null, q: "" };
let MENU = []; // caricato da /api/menu quando serve

/* ---------------------- Util ---------------------- */
const UI = {
  moneyEUR(v) {
    try { return new Intl.NumberFormat("it-IT",{style:"currency",currency:"EUR",maximumFractionDigits:0}).format(v); }
    catch { return `€ ${Math.round(v)}`; }
  },
  el(tag, cls, html){ const e=document.createElement(tag); if(cls) e.className=cls; if(html!=null) e.innerHTML=html; return e;},
  openModal(){ document.getElementById("modal").setAttribute("aria-hidden","false"); },
  closeModal(){ document.getElementById("modal").setAttribute("aria-hidden","true"); },
  toast(m){ console.log(m); }
};

async function fetchJSON(url, opts={}) {
  const res = await fetch(url,{ headers:{"Content-Type":"application/json"}, credentials:"same-origin", ...opts });
  if (!res.ok){ throw new Error(await res.text().catch(()=>`HTTP ${res.status}`)); }
  if (res.status===204) return null;
  return res.json();
}

/* ---------------- Prezzi dinamici ----------------- */
function toMinutes(hhmm){ const [h,m]=(hhmm||"0:0").split(":").map(n=>parseInt(n,10)||0); return h*60+m; }
function priceFor(timeHHMM){
  const t=toMinutes(timeHHMM);
  if (t>=12*60 && t<=15*60) return 20;
  if (t>=19*60 && t<=23*60+30) return 30;
  return 0;
}

/* --------------- Rendering lista/KPI --------------- */
function renderList(items){
  const list = document.getElementById("list");
  list.innerHTML="";

  const todayISO = new Date().toISOString().slice(0,10);
  let kpiToday=0, revenue=0, pizzasTotal=0;

  items.forEach(it=>{
    if (it.date===todayISO) kpiToday++;

    if (it.status==="confirmed"){
      revenue += (it.people||0) * priceFor(it.time);
      // somma pizze (se presenti)
      (it.pizzas||[]).forEach(p=> pizzasTotal += (p.qty||0));
    }

    const row = UI.el("div","reservation-row");
    const left = UI.el("div","res-left");
    const pill = UI.el("span","pill people", `${it.people} pers.`);
    const name = UI.el("div","res-name", it.customer_name);
    const meta = UI.el("div","res-meta", `${it.date} • ${it.time} • ${it.phone}`);

    left.appendChild(pill); left.appendChild(name); left.appendChild(meta);

    // righe pizze ordinate (se ci sono)
    if (it.pizzas && it.pizzas.length){
      const pizzasLine = it.pizzas.map(p=> `${p.name} ×${p.qty}`).join(", ");
      left.appendChild(UI.el("div","res-meta", `🍕 ${pizzasLine}`));
    }

    const status = UI.el("span", "badge " + (
      it.status==="confirmed" ? "badge-green" :
      it.status==="rejected"  ? "badge-red"   : "badge-gray"
    ), it.status);

    const actions = UI.el("div","res-actions");
    const bC = UI.el("button","btn btn-outline","Conferma");
    const bR = UI.el("button","btn btn-outline","Rifiuta");
    const bD = UI.el("button","btn btn-outline","Elimina");

    bC.onclick = async()=>{ try{ await fetchJSON(`/api/reservations/${it.id}`,{method:"PATCH",body:JSON.stringify({status:"confirmed"})}); await load(); }catch(e){UI.toast(e.message);} };
    bR.onclick = async()=>{ try{ await fetchJSON(`/api/reservations/${it.id}`,{method:"PATCH",body:JSON.stringify({status:"rejected"})}); await load(); }catch(e){UI.toast(e.message);} };
    bD.onclick = async()=>{ try{ await fetchJSON(`/api/reservations/${it.id}`,{method:"DELETE"}); await load(); }catch(e){UI.toast(e.message);} };

    actions.append(bC,bR,bD);
    row.append(left,status,actions);
    list.appendChild(row);
  });

  document.getElementById("kpi-today").textContent = kpiToday;
  document.getElementById("kpi-revenue").textContent = UI.moneyEUR(revenue);
  const kpiPizze = document.getElementById("kpi-pizzas");
  if (kpiPizze) kpiPizze.textContent = pizzasTotal;
}

/* -------------------- Load & filtri -------------------- */
async function load(){
  const p=new URLSearchParams();
  if (state.range) p.set("range",state.range);
  if (state.date)  p.set("date",state.date);
  if (state.q)     p.set("q",state.q);
  try{
    const data=await fetchJSON(`/api/reservations?${p.toString()}`);
    renderList(data);
  }catch(e){ UI.toast("Errore caricamento: "+e.message); }
}

function setupFilters(){
  const fDate = document.getElementById("f-date");
  const fText = document.getElementById("f-text");
  const bFilter = document.getElementById("btn-filter");
  const bClear  = document.getElementById("btn-clear");
  const b30     = document.getElementById("btn-30");
  const bToday  = document.getElementById("btn-today");

  bFilter.onclick = ()=>{ state.date=fDate.value||null; state.q=(fText.value||"").trim(); state.range=null; load(); };
  bClear.onclick  = ()=>{ fDate.value=""; fText.value=""; state.date=null; state.q=""; state.range=null; load(); };
  b30.onclick     = ()=>{ state.range="30days"; state.date=null; load(); };
  bToday.onclick  = ()=>{ state.range="today";  state.date=null; load(); };
}

/* -------------------- Modale & Pizze -------------------- */
function pizzaRowTemplate(options){
  const row = UI.el("div","pizza-row");
  const select = UI.el("select","input pizza-select");
  (options||[]).forEach(o=>{
    const opt=document.createElement("option");
    opt.value=o.id; opt.textContent=`${o.name} (${o.price}€)`;
    select.appendChild(opt);
  });
  const qty = UI.el("input","input pizza-qty");
  qty.type="number"; qty.min="1"; qty.value="1";
  const remove = UI.el("button","btn btn-outline","Rimuovi");
  remove.type="button";
  remove.onclick=()=> row.remove();
  row.append(select, qty, remove);
  return row;
}

async function ensureMenu(){
  try{
    if (!MENU.length) MENU = await fetchJSON("/api/menu");
  }catch{ /* se non è pizzeria o non ha menu, MENU resta [] */ }
}

function setupModal(){
  const openBtn=document.getElementById("btn-new");
  const closeBtn=document.getElementById("modalClose");
  const saveBtn=document.getElementById("modalSave");
  const addPizza=document.getElementById("pizzaAdd");
  const rowsBox=document.getElementById("pizzaRows");

  openBtn.onclick = async ()=>{
    await ensureMenu();
    rowsBox.innerHTML="";
    if (MENU.length){ rowsBox.appendChild(pizzaRowTemplate(MENU)); }
    UI.openModal();
  };
  closeBtn.onclick = ()=> UI.closeModal();
  addPizza.onclick = ()=>{ if (MENU.length) rowsBox.appendChild(pizzaRowTemplate(MENU)); };

  saveBtn.onclick = async ()=>{
    const body={
      customer_name: document.getElementById("m-name").value.trim(),
      phone: document.getElementById("m-phone").value.trim(),
      date: document.getElementById("m-date").value,
      time: document.getElementById("m-time").value,
      people: Number(document.getElementById("m-people").value||1),
      pizzas: []
    };

    // raccogli pizze (se ci sono righe)
    document.querySelectorAll(".pizza-row").forEach(r=>{
      const pid = Number(r.querySelector(".pizza-select")?.value||0);
      const qty = Number(r.querySelector(".pizza-qty")?.value||0);
      if (pid>0 && qty>0) body.pizzas.push({ pizza_id: pid, qty });
    });

    if (!body.customer_name || !body.phone || !body.date || !body.time || body.people < 1){
      UI.toast("Compila tutti i campi correttamente."); return;
    }

    try{
      await fetchJSON("/api/reservations",{method:"POST", body:JSON.stringify(body)});
      UI.closeModal();
      document.getElementById("m-name").value="";
      document.getElementById("m-phone").value="";
      await load();
    }catch(e){ UI.toast("Errore salvataggio: "+e.message); }
  };
}

/* -------------------- Init -------------------- */
document.addEventListener("DOMContentLoaded", ()=>{
  setupFilters();
  setupModal();
  load();
});
