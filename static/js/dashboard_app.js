// Helpers
const $ = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));

async function api(url, opts = {}) {
  opts.credentials = 'include';
  opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers||{});
  const res = await fetch(url, opts);
  let data = null;
  try { data = await res.json(); } catch(_){ data = {ok:false}; }
  if (!res.ok || data.ok === false) {
    const msg = (data && data.error) ? data.error : res.statusText;
    throw new Error(msg);
  }
  return data;
}

// THEME toggle (save in localStorage)
(function initTheme(){
  const root = document.documentElement;
  const btn = $('#themeToggle');
  if (!btn) return;
  const apply = (mode) => {
    root.dataset.theme = mode;
    btn.dataset.state = (mode === 'light' ? 'on' : 'off');
    try { localStorage.setItem('theme', mode); } catch(e){}
  };
  // click
  btn.addEventListener('click', () => {
    const next = (root.dataset.theme === 'light') ? 'dark' : 'light';
    apply(next);
  });
})();

// SIDEBAR a scomparsa
(function initSidebar(){
  const aside = $('#sidebar');
  const back = $('#sidebarBackdrop');
  const openBtn = $('#btnSidebar');
  const closeBtn = $('#btnCloseSidebar');

  const open = () => { aside.hidden = false; back.hidden = false; };
  const close = () => { aside.hidden = true; back.hidden = true; };

  if (openBtn) openBtn.addEventListener('click', open);
  if (closeBtn) closeBtn.addEventListener('click', close);
  if (back) back.addEventListener('click', close);

  // navigate sections
  $$('.nav-link', aside).forEach(a => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      const id = a.getAttribute('data-open');
      if (!id) return;
      showSection(id);
      close();
    });
  });
})();

function showSection(id) {
  $$('.dash-section').forEach(s => s.hidden = true);
  const target = document.getElementById(id);
  if (target) {
    target.hidden = false;
    target.setAttribute('active','');
  }
}

// ----------------------------------------------------------------------------
// DASHBOARD: Reservations list
// ----------------------------------------------------------------------------

async function loadReservations(){
  const d = $('#flt-date')?.value || '';
  const q = $('#flt-q')?.value?.trim() || '';
  const params = new URLSearchParams();
  if (d) params.set('date', d);
  if (q) params.set('q', q);

  const res = await api('/api/reservations?'+params.toString(), {method:'GET'});
  const tbody = $('#res-tbody');
  const empty = $('#list-empty');
  if (!tbody) return;

  tbody.innerHTML = '';
  const items = res.items || [];

  // KPI semplici
  $('#kpiToday') && ($('#kpiToday').textContent = items.length.toString());

  if (items.length === 0) {
    if (empty) empty.hidden = false;
    return;
  }
  if (empty) empty.hidden = true;

  for (const r of items) {
    const tr = document.createElement('tr');

    const dateStr = r.date; // stringa "YYYY-MM-DD" già pronta
    const timeStr = r.time; // "HH:MM"
    tr.innerHTML = `
      <td class="col-time"><span class="time-dot"></span>${dateStr} ${timeStr}</td>
      <td>${escapeHtml(r.name)}</td>
      <td>${escapeHtml(r.phone||'')}</td>
      <td class="col-people">${r.people}</td>
      <td class="col-state"><span class="badge ${badgeByState(r.status)}">${escapeHtml(r.status||'')}</span></td>
      <td>${escapeHtml(r.note||'')}</td>
      <td class="col-actions">
        <div class="actions-row">
          <button class="btn btn-sm" data-edit="${r.id}">Modifica ✏️</button>
          <button class="btn btn-success btn-sm" data-confirm="${r.id}">Conferma ✅</button>
          <button class="btn btn-outline btn-sm" data-reject="${r.id}">Rifiuta ❌</button>
          <button class="btn btn-danger btn-sm" data-del="${r.id}">Elimina 🗑️</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }

  // Bind azioni
  $$('[data-del]', tbody).forEach(b=>{
    b.addEventListener('click', () => {
      const id = b.getAttribute('data-del');
      openConfirm('Vuoi cancellare la prenotazione?', async () => {
        await api('/api/reservations/'+id, {method:'DELETE'});
        await loadReservations();
      });
    });
  });

  $$('[data-confirm]', tbody).forEach(b=>{
    b.addEventListener('click', async () => {
      const id = b.getAttribute('data-confirm');
      await api('/api/reservations/'+id, {method:'PUT', body: JSON.stringify({status:'Confermata'})});
      await loadReservations();
    });
  });

  $$('[data-reject]', tbody).forEach(b=>{
    b.addEventListener('click', async () => {
      const id = b.getAttribute('data-reject');
      await api('/api/reservations/'+id, {method:'PUT', body: JSON.stringify({status:'Rifiutata'})});
      await loadReservations();
    });
  });

  $$('[data-edit]', tbody).forEach(b=>{
    b.addEventListener('click', async () => {
      const id = b.getAttribute('data-edit');
      openReservationModal((form) => updateReservation(id, form));
      // prefill: inutile fare GET singola, riusiamo r renderizzato
      $('#res-date').value = r.date;
      $('#res-time').value = r.time;
      $('#res-name').value = r.name;
      $('#res-phone').value = r.phone || '';
      $('#res-people').value = r.people;
      $('#res-status').value = r.status || 'Confermata';
      $('#res-note').value = r.note || '';
    });
  });
}

function badgeByState(s){
  const v = (s||'').toLowerCase();
  if (v.includes('confer')) return 'badge-success';
  if (v.includes('attesa')) return 'badge-info';
  if (v.includes('rifiut')) return 'badge-warning';
  return 'badge-muted';
}

function escapeHtml(x){
  return (x||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

// ----------------------------------------------------------------------------
// Reservation Modal
// ----------------------------------------------------------------------------
function openReservationModal(onSave){
  const modal = $('#modalReservation');
  const saveBtn = $('#btnSaveReservation');

  // reset
  $('#res-date').value = todayStr();
  $('#res-time').value = '20:00';
  $('#res-name').value = '';
  $('#res-phone').value = '';
  $('#res-people').value = 2;
  $('#res-status').value = 'Confermata';
  $('#res-note').value = '';

  modal.hidden = false;
  const closeAll = () => { modal.hidden = true; };

  $$('[data-close-modal]').forEach(btn => btn.onclick = closeAll);

  saveBtn.onclick = async () => {
    const form = {
      date: $('#res-date').value,
      time: $('#res-time').value,
      name: $('#res-name').value.trim(),
      phone: $('#res-phone').value.trim(),
      people: parseInt($('#res-people').value||'2',10),
      status: $('#res-status').value,
      note: $('#res-note').value.trim(),
    };
    await onSave(form);
    closeAll();
  };
}

async function updateReservation(id, form){
  await api('/api/reservations/'+id, {method:'PUT', body: JSON.stringify(form)});
  await loadReservations();
}

async function createReservation(form){
  if (!form.name || !form.date || !form.time) return;
  await api('/api/reservations', {method:'POST', body: JSON.stringify(form)});
  await loadReservations();
}

function todayStr(){
  const d = new Date();
  const m = (d.getMonth()+1).toString().padStart(2,'0');
  const day = d.getDate().toString().padStart(2,'0');
  return `${d.getFullYear()}-${m}-${day}`;
}

// ----------------------------------------------------------------------------
// Sections: Hours / Special Days / Pricing / Menu / Stats
// ----------------------------------------------------------------------------

function renderHoursGrid(){
  const grid = $('#hours-grid');
  if (!grid) return;
  const days = ['Lun','Mar','Mer','Gio','Ven','Sab','Dom'];
  grid.innerHTML = '';
  for (let i=0;i<7;i++){
    const card = document.createElement('div');
    card.className = 'card pad';
    card.innerHTML = `
      <div style="font-weight:600;margin-bottom:6px">${days[i]}</div>
      <input class="input" id="wh-${i}" placeholder="12:00-15:00, 19:00-22:30">
    `;
    grid.appendChild(card);
  }
}

async function saveWeeklyHours(){
  const hours = {};
  for (let i=0;i<7;i++){
    hours[String(i)] = ($('#wh-'+i)?.value || '').trim();
  }
  await api('/api/hours', {method:'POST', body: JSON.stringify({hours})});
  toast('Orari settimanali salvati ✅');
}

async function saveSpecialDay(){
  const day = $('#sp-day').value;
  const closed = $('#sp-closed').value === 'true';
  const windows = $('#sp-windows').value.trim();
  if (!day) return toast('Seleziona una data');
  await api('/api/special-days', {method:'POST', body: JSON.stringify({day, closed, windows})});
  toast('Giorno speciale salvato ✅');
}

async function savePricing(){
  const payload = {
    avg_price: $('#pr-avg').value,
    cover: $('#pr-cover').value,
    seats_cap: $('#pr-seats').value,
    min_people: $('#pr-min').value,
  };
  await api('/api/pricing', {method:'POST', body: JSON.stringify(payload)});
  toast('Prezzi & coperti salvati ✅');
}

async function saveMenu(){
  const payload = {
    menu_url: $('#mn-url').value,
    menu_desc: $('#mn-desc').value,
  };
  await api('/api/menu', {method:'POST', body: JSON.stringify(payload)});
  toast('Menu digitale salvato ✅');
}

async function loadStats(){
  const d = $('#st-date').value;
  const params = d ? '?date='+encodeURIComponent(d) : '';
  const s = await api('/api/stats'+params, {method:'GET'});
  $('#st-total').textContent = s.total_reservations.toString();
  $('#st-avgp').textContent = s.avg_people.toFixed(2);
  $('#st-rev').textContent = s.estimated_revenue.toFixed(2) + ' €';
}

// ----------------------------------------------------------------------------
// Confirm modal & toast
// ----------------------------------------------------------------------------
function openConfirm(message, onOk){
  const modal = $('#confirmModal');
  $('#confirmText').textContent = message || 'Sei sicuro?';
  modal.hidden = false;
  const close = () => { modal.hidden = true; };
  $$('[data-close-confirm]').forEach(b => b.onclick = close);
  $('#confirmOk').onclick = async () => {
    try { await onOk(); } finally { close(); }
  };
}

function toast(msg){
  let t = $('#toast');
  if (!t){
    t = document.createElement('div');
    t.id = 'toast'; t.className = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.hidden = false;
  setTimeout(()=>{ t.hidden = true; }, 2200);
}

// ----------------------------------------------------------------------------
// Init
// ----------------------------------------------------------------------------
window.addEventListener('DOMContentLoaded', async () => {
  // Se esiste la dashboard, inizializza filtri e lista
  if ($('#section-dashboard')){
    renderHoursGrid(); // prepara griglia orari (usata in sezione dedicata)

    // Filtri
    const dt = $('#flt-date');
    if (dt) dt.value = todayStr();

    $('#btn-filter')?.addEventListener('click', loadReservations);
    $('#btn-clear')?.addEventListener('click', () => {
      $('#flt-q').value=''; $('#flt-date').value=''; loadReservations();
    });
    $('#btn-today')?.addEventListener('click', () => {
      $('#flt-date').value = todayStr(); loadReservations();
    });
    $('#btn-new')?.addEventListener('click', () => {
      openReservationModal(createReservation);
    });

    // Sezioni salvataggio
    $('#btn-save-hours')?.addEventListener('click', saveWeeklyHours);
    $('#btn-save-special')?.addEventListener('click', saveSpecialDay);
    $('#btn-save-pricing')?.addEventListener('click', savePricing);
    $('#btn-save-menu')?.addEventListener('click', saveMenu);
    $('#btn-load-stats')?.addEventListener('click', loadStats);

    await loadReservations();
  }
});
