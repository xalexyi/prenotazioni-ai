/* static/js/reservations.js — lista prenotazioni con filtri */
(() => {
  const $  = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
  const pad2 = (n) => String(n).padStart(2,'0');

  function getRid(){ return window.RESTAURANT_ID || window.restaurant_id || 1; }
  const SID_KEY = 'session_id';
  function sid(){
    let s = localStorage.getItem(SID_KEY) || window.SESSION_ID;
    if (!s){ s = Math.random().toString(36).slice(2); localStorage.setItem(SID_KEY, s); }
    return s;
  }
  async function loadAdminToken(){
    const r = await fetch(`/api/public/sessions/${encodeURIComponent(sid())}`, { credentials:'same-origin' });
    if(!r.ok) throw new Error('HTTP '+r.status);
    const j = await r.json();
    return j.admin_token || j.token || j.session?.admin_token || '';
  }
  async function adminFetch(url){
    const token = await loadAdminToken();
    const r = await fetch(url, { headers: { 'X-Admin-Token': token } , credentials:'same-origin' });
    if(!r.ok){
      let msg = 'HTTP '+r.status;
      try { const j = await r.json(); if (j && j.error) msg = j.error; } catch(_){}
      throw new Error(msg);
    }
    return r.json();
  }

  function qs(params){
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k,v])=>{
      if (v !== undefined && v !== null && v !== '') sp.set(k, v);
    });
    return sp.toString();
  }

  async function fetchList({ date, q, last_days, today }){
    const base = `/api/admin-token/reservations?` + qs({
      restaurant_id: getRid(),
      date, q, last_days, today
    });
    return adminFetch(base);
  }

  function render(items){
    const box = $("#list");
    if (!box) return;
    if (!items || !items.length){
      box.innerHTML = `<div class="muted">Nessuna prenotazione.</div>`;
      return;
    }
    const table = document.createElement("table");
    table.className = "tbl";
    table.innerHTML = `
      <thead>
        <tr>
          <th>Data</th><th>Ora</th><th>Nome</th><th>Telefono</th><th>Persone</th><th>Stato</th><th>Note</th>
        </tr>
      </thead>
      <tbody></tbody>
    `;
    const tb = table.querySelector("tbody");
    items.forEach(it=>{
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${it.date || ""}</td>
        <td>${it.time || ""}</td>
        <td>${it.name || ""}</td>
        <td>${it.phone || ""}</td>
        <td>${it.party_size || ""}</td>
        <td>${it.status || ""}</td>
        <td>${it.notes || ""}</td>
      `;
      tb.appendChild(tr);
    });
    box.innerHTML = "";
    box.appendChild(table);
  }

  async function applyFilters(mode){
    let date = $("#resv-date")?.value || "";
    let q    = $("#resv-q")?.value || "";
    let last_days, today;
    if (mode === "today"){ today = 1; }
    else if (mode === "last30"){ last_days = 30; }
    const data = await fetchList({ date, q, last_days, today });
    render(data.items || []);
  }

  $("#resv-filter") ?.addEventListener("click", () => applyFilters());
  $("#resv-clear")  ?.addEventListener("click", () => {
    if ($("#resv-q")) $("#resv-q").value = "";
    applyFilters();
  });
  $("#resv-last30") ?.addEventListener("click", () => applyFilters("last30"));
  $("#resv-today")  ?.addEventListener("click", () => applyFilters("today"));
  $("#resv-refresh")?.addEventListener("click", () => applyFilters());

  // primo load
  document.addEventListener("DOMContentLoaded", () => applyFilters().catch(console.error));
})();
