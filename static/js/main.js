// --------- helpers
const $  = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));

async function api(url, opts = {}) {
  const opt = {
    method: 'GET',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opts
  };
  const res = await fetch(url, opt);
  let data = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok || (data && data.ok === false)) {
    const msg = (data && (data.error || data.message)) || res.statusText || 'Errore';
    throw new Error(msg);
  }
  return data || { ok: true };
}

// --------- THEME TOGGLE (persistenza)
function applyTheme(mode) {
  const body = document.body;
  body.classList.remove('theme-dark', 'theme-light');
  body.classList.add(mode === 'light' ? 'theme-light' : 'theme-dark');
}
function initThemeToggle() {
  const sw = $('#themeSwitch');
  if (!sw) return;

  // carica preferenza
  const saved = localStorage.getItem('theme') || 'dark';
  sw.checked = (saved === 'light');
  applyTheme(saved);

  sw.addEventListener('change', () => {
    const mode = sw.checked ? 'light' : 'dark';
    localStorage.setItem('theme', mode);
    applyTheme(mode);
  });
}

// --------- DASH: Filtri & lista prenotazioni (se i nodi esistono)
async function loadReservations() {
  const dateEl = $('#flt-date');
  const qEl    = $('#flt-q');
  const list   = $('#list');
  const empty  = $('#list-empty');

  if (!list) return; // pagina non è la dashboard "lista"

  const params = new URLSearchParams();
  if (dateEl && dateEl.value) params.set('date', dateEl.value);
  if (qEl && qEl.value.trim()) params.set('q', qEl.value.trim());

  const res = await api('/api/reservations?'+params.toString());
  list.innerHTML = '';
  if (empty) empty.style.display = res.items.length ? 'none' : 'block';

  res.items.forEach(r => {
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `
      <div class="row" style="gap:12px;align-items:center;padding:12px">
        <b>${r.date} ${r.time}</b>
        <span>${r.name}</span>
        <span>${r.phone || ''}</span>
        <span>👥 ${r.people}</span>
        <span class="chip">${r.status || ''}</span>
        <span class="grow"></span>
        <button class="btn" data-edit="${r.id}">Modifica</button>
        <button class="btn" data-del="${r.id}">Elimina</button>
      </div>
      ${r.note ? `<div style="margin:8px 12px 12px;color:#9bb1c7">Note: ${r.note}</div>` : ''}
    `;
    list.appendChild(el);
  });

  // azioni
  $$('#list [data-del]').forEach(b=>{
    b.onclick = async ()=> {
      if (!confirm('Eliminare la prenotazione?')) return;
      await api('/api/reservations/'+b.dataset.del, { method:'DELETE' });
      await loadReservations();
    };
  });
  $$('#list [data-edit]').forEach(b=>{
    b.onclick = async ()=> {
      const id = b.dataset.edit;
      const when = prompt('Nuova data (YYYY-MM-DD) o lascia vuoto', '');
      const at   = prompt('Nuova ora (HH:MM) o lascia vuoto', '');
      const payload = {};
      if (when) payload.date = when;
      if (at)   payload.time = at;
      if (!Object.keys(payload).length) return;
      await api('/api/reservations/'+id, { method:'PUT', body: JSON.stringify(payload) });
      await loadReservations();
    };
  });
}

async function createReservation() {
  const today = new Date().toISOString().slice(0,10);
  const dateStr = prompt('Data (YYYY-MM-DD)', today);
  const timeStr = prompt('Ora (HH:MM)', '20:00');
  const name    = prompt('Nome', '');
  const phone   = prompt('Telefono', '');
  const people  = parseInt(prompt('Persone', '2') || '2', 10);
  if (!dateStr || !timeStr || !name) return;
  const payload = { date: dateStr, time: timeStr, name, phone, people, status:'Confermata', note:'' };
  await api('/api/reservations', { method:'POST', body: JSON.stringify(payload) });
  await loadReservations();
}

// --------- Orari settimanali
async function saveWeeklyHours(map) {
  // map: { "0": "12:00-15:00, 19:00-22:30", ... }
  await api('/api/hours', { method:'POST', body: JSON.stringify({ hours: map }) });
  // verifica lettura
  const check = await api('/api/weekly-hours');
  console.info('[WEEKLY-HOURS SAVED]', check.hours);
  alert('Orari salvati.\n' + JSON.stringify(check.hours, null, 2));
}
async function fetchWeeklyHoursAndFill(targetId) {
  const data = await api('/api/weekly-hours');
  const box = targetId ? $('#'+targetId) : null;
  if (box) box.textContent = JSON.stringify(data.hours, null, 2);
  return data.hours;
}

// --------- Giorni speciali
async function saveSpecialDay({ day, closed, windows }) {
  await api('/api/special-days', { method:'POST', body: JSON.stringify({ day, closed, windows }) });
  const check = await api('/api/special-days');
  console.info('[SPECIAL-DAYS]', check.items);
  alert('Giorno speciale salvato.\n' + JSON.stringify(check.items, null, 2));
}
async function fetchSpecialDaysAndFill(targetId) {
  const data = await api('/api/special-days');
  const box = targetId ? $('#'+targetId) : null;
  if (box) box.textContent = JSON.stringify(data.items, null, 2);
  return data.items;
}

// --------- Prezzi & coperti
async function savePricing({ avg_price, cover, seats_cap, min_people }) {
  await api('/api/pricing', { method:'POST', body: JSON.stringify({ avg_price, cover, seats_cap, min_people }) });
  const check = await api('/api/pricing');
  console.info('[PRICING]', check);
  alert('Prezzi & coperti salvati.\n' + JSON.stringify(check, null, 2));
}
async function fetchPricingAndFill(targetId) {
  const data = await api('/api/pricing');
  const box = targetId ? $('#'+targetId) : null;
  if (box) box.textContent = JSON.stringify(data, null, 2);
  return data;
}

// --------- Menu digitale
async function saveMenu({ menu_url, menu_desc }) {
  await api('/api/menu', { method:'POST', body: JSON.stringify({ menu_url, menu_desc }) });
  const check = await api('/api/menu');
  console.info('[MENU]', check);
  alert('Menu digitale salvato.\n' + JSON.stringify(check, null, 2));
}
async function fetchMenuAndFill(targetId) {
  const data = await api('/api/menu');
  const box = targetId ? $('#'+targetId) : null;
  if (box) box.textContent = JSON.stringify(data, null, 2);
  return data;
}

// --------- Wiring automatico se i bottoni/inputs esistono
function wireDashboard() {
  // filtri
  const btnFilter = $('#btn-filter');
  const btnClear  = $('#btn-clear');
  const btn30d    = $('#btn-30d');
  const btnToday  = $('#btn-today');
  const btnNew    = $('#btn-new');
  const fltDate   = $('#flt-date');

  if (btnFilter) btnFilter.onclick = loadReservations;
  if (btnClear)  btnClear.onclick  = () => {
    const q = $('#flt-q'); if (q) q.value = '';
    if (fltDate) fltDate.value = '';
    loadReservations();
  };
  if (btn30d)    btn30d.onclick    = () => alert('Storico 30gg — (disattivato su richiesta)');
  if (btnToday)  btnToday.onclick  = () => {
    if (fltDate) fltDate.value = new Date().toISOString().slice(0,10);
    loadReservations();
  };
  if (btnNew)    btnNew.onclick    = createReservation;

  if (fltDate && !fltDate.value) fltDate.value = new Date().toISOString().slice(0,10);
  loadReservations().catch(()=>{/* pagina senza lista, ignora */});

  // Se nella pagina sono presenti aree "preview" JSON, le popolo
  fetchWeeklyHoursAndFill('hoursPreview').catch(()=>{});
  fetchSpecialDaysAndFill('specialDaysPreview').catch(()=>{});
  fetchPricingAndFill('pricingPreview').catch(()=>{});
  fetchMenuAndFill('menuPreview').catch(()=>{});

  // Se esistono pulsanti azione con data-action li collego:
  // data-action="save-hours"    → raccoglie 7 input con name="day-0".. "day-6"
  // data-action="save-special"  → input name="special-date", #special-closed, #special-windows
  // data-action="save-pricing"  → input name avg_price, cover, seats_cap, min_people
  // data-action="save-menu"     → input name menu_url, menu_desc
  $$('.btn[data-action="save-hours"]').forEach(btn=>{
    btn.onclick = async ()=>{
      const map = {};
      for (let d=0; d<7; d++) {
        const inp = document.querySelector(`[name="day-${d}"]`);
        map[String(d)] = inp ? (inp.value || '') : '';
      }
      await saveWeeklyHours(map);
    };
  });

  $$('.btn[data-action="save-special"]').forEach(btn=>{
    btn.onclick = async ()=>{
      const day     = ($('[name="special-date"]')   || {}).value || '';
      const closed  = ($('#special-closed')         || {}).checked || false;
      const windows = ($('#special-windows')        || {}).value || '';
      if (!day) { alert('Inserisci una data (YYYY-MM-DD)'); return; }
      await saveSpecialDay({ day, closed, windows });
    };
  });

  $$('.btn[data-action="save-pricing"]').forEach(btn=>{
    btn.onclick = async ()=>{
      const avg_price  = ($('[name="avg_price"]')  || {}).value ?? '';
      const cover      = ($('[name="cover"]')      || {}).value ?? '';
      const seats_cap  = ($('[name="seats_cap"]')  || {}).value ?? '';
      const min_people = ($('[name="min_people"]') || {}).value ?? '';
      await savePricing({ avg_price, cover, seats_cap, min_people });
    };
  });

  $$('.btn[data-action="save-menu"]').forEach(btn=>{
    btn.onclick = async ()=>{
      const menu_url  = ($('[name="menu_url"]')  || {}).value ?? '';
      const menu_desc = ($('[name="menu_desc"]') || {}).value ?? '';
      await saveMenu({ menu_url, menu_desc });
    };
  });
}

// --------- bootstrap
window.addEventListener('DOMContentLoaded', ()=>{
  initThemeToggle();
  wireDashboard();
});
