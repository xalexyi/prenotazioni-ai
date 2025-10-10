// ---------- helpers ----------
const $  = (s)=>document.querySelector(s);
const $$ = (s)=>Array.from(document.querySelectorAll(s));

const api = async (url, opts={})=>{
  opts.credentials = 'include';
  opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers||{});
  const res = await fetch(url, opts);
  let data = null;
  try { data = await res.json(); } catch(e){ /* no json */ }
  if (!res.ok || (data && data.ok===false)) {
    const msg = (data && (data.error||data.message)) || res.statusText || 'Errore richiesta';
    throw new Error(msg);
  }
  return data ?? {};
};

// ---------- theme ----------
(function initTheme(){
  const sw = $('#themeSwitch');
  if (!sw) return;
  const apply = (mode)=>{
    document.body.classList.toggle('theme-dark',  mode==='dark');
    document.body.classList.toggle('theme-light', mode==='light');
    sw.checked = (mode==='light');
    localStorage.setItem('theme', mode);
  };
  // init
  const saved = localStorage.getItem('theme') || 'dark';
  apply(saved);
  sw.addEventListener('change', ()=> apply(sw.checked ? 'light' : 'dark'));
})();

// ---------- reservations ----------
const fmtDateInput = (d)=> d.toISOString().slice(0,10);

async function loadReservations(){
  const d = $('#flt-date')?.value;
  const q = $('#flt-q')?.value?.trim();
  const params = new URLSearchParams();
  if (d) params.set('date', d);
  if (q) params.set('q', q);
  const res = await api('/api/reservations?'+params.toString(), {method:'GET'});
  const list = $('#list'); if (!list) return;

  list.innerHTML = '';
  $('#list-empty').style.display = (res.items && res.items.length) ? 'none' : 'block';

  (res.items||[]).forEach(r=>{
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `
      <div class="row" style="gap:12px;align-items:center;padding:12px">
        <b>${r.date} ${r.time}</b>
        <span>${r.name}</span>
        <span>${r.phone||''}</span>
        <span>👥 ${r.people}</span>
        <span class="chip">${r.status||''}</span>
        <span class="grow"></span>
        <button class="btn" data-edit="${r.id}">Modifica</button>
        <button class="btn" data-del="${r.id}">Elimina</button>
      </div>
      ${r.note? `<div style="margin:0 12px 12px;color:#9bb1c7">Note: ${r.note}</div>`:''}
    `;
    list.appendChild(el);
  });

  list.querySelectorAll('[data-del]').forEach(b=>{
    b.onclick = async ()=>{
      if (!confirm('Eliminare la prenotazione?')) return;
      await api('/api/reservations/'+b.dataset.del, {method:'DELETE'});
      await loadReservations();
    };
  });

  list.querySelectorAll('[data-edit]').forEach(b=>{
    b.onclick = async ()=>{
      const id = b.dataset.edit;
      const date = prompt('Nuova data (YYYY-MM-DD) o vuoto per lasciare', '');
      const time = prompt('Nuova ora (HH:MM) o vuoto per lasciare', '');
      const payload = {};
      if (date) payload.date = date;
      if (time) payload.time = time;
      if (!Object.keys(payload).length) return;
      await api('/api/reservations/'+id, {method:'PUT', body:JSON.stringify(payload)});
      await loadReservations();
    };
  });
}

// ---------- weekly hours ----------
async function saveWeeklyHours(){
  const hours = {};
  for (let i=0;i<7;i++){
    hours[i] = $(`input[name="wh-${i}"]`)?.value?.trim() || '';
  }
  await api('/api/hours', {method:'POST', body:JSON.stringify({hours})});
  alert('Orari aggiornati');
}

// ---------- special days ----------
async function saveSpecialDay(){
  const day = $('#spc-date').value;
  if (!day) return alert('Seleziona una data');
  const closed = $('#spc-closed').checked;
  const windows = $('#spc-windows').value.trim();
  await api('/api/special-days', {method:'POST', body:JSON.stringify({day,closed,windows})});
  alert('Giorno speciale salvato');
}
async function deleteSpecialDay(){
  const day = $('#spc-date').value;
  if (!day) return;
  await api('/api/special-days/'+day, {method:'DELETE'});
  alert('Giorno speciale eliminato');
}

// ---------- create reservation (modal) ----------
function openModal(id){ const el = $('#'+id); if (el) el.setAttribute('aria-hidden','false'); }
function closeModal(id){ const el = $('#'+id); if (el) el.setAttribute('aria-hidden','true'); }
$$('[data-close]').forEach(b=> b.addEventListener('click', ()=> closeModal(b.getAttribute('data-close'))));
$$('.modal').forEach(m=> m.addEventListener('click', (e)=>{ if(e.target===m) m.setAttribute('aria-hidden','true'); }));

async function saveCreate(){
  const payload = {
    date:   $('#cr-date').value,
    time:   $('#cr-time').value,
    name:   $('#cr-name').value.trim(),
    phone:  $('#cr-phone').value.trim(),
    people: parseInt($('#cr-people').value,10)||1,
    status: $('#cr-status').value,
    note:   $('#cr-note').value.trim()
  };
  if (!payload.date || !payload.time || !payload.name) return alert('Compila data, ora e nome.');
  await api('/api/reservations', {method:'POST', body:JSON.stringify(payload)});
  closeModal('dlgCreate');
  await loadReservations();
}

// ---------- init ----------
window.addEventListener('DOMContentLoaded', async ()=>{
  // drawer chiudi
  $('#btn-drawer-close')?.addEventListener('click', ()=> $('#drawer')?.classList.remove('open'));

  // filtri
  if ($('#flt-date')) $('#flt-date').value = fmtDateInput(new Date());
  $('#btn-filter')?.addEventListener('click', loadReservations);
  $('#btn-clear')?.addEventListener('click', ()=>{ if($('#flt-q')) $('#flt-q').value=''; if($('#flt-date')) $('#flt-date').value=''; loadReservations(); });
  $('#btn-today')?.addEventListener('click', ()=>{ if($('#flt-date')) $('#flt-date').value=fmtDateInput(new Date()); loadReservations(); });

  // nuova prenotazione -> modale
  $('#btn-new')?.addEventListener('click', ()=>{
    $('#cr-date').value = $('#flt-date')?.value || fmtDateInput(new Date());
    $('#cr-time').value = '20:00';
    $('#cr-name').value = '';
    $('#cr-phone').value = '';
    $('#cr-people').value = 2;
    $('#cr-status').value = 'Confermata';
    $('#cr-note').value = '';
    openModal('dlgCreate');
  });
  $('#btn-save-create')?.addEventListener('click', saveCreate);

  // menu laterale
  $('#nav-hours')?.addEventListener('click', ()=> openModal('dlgHours'));
  $('#nav-special')?.addEventListener('click', ()=> openModal('dlgSpecial'));
  $('#nav-pricing')?.addEventListener('click', ()=> alert('Impostazioni prezzi in arrivo'));
  $('#nav-menu')?.addEventListener('click', ()=> alert('Menu digitale in arrivo'));
  $('#nav-stats')?.addEventListener('click', ()=> alert('Statistiche e report in arrivo'));

  // pulsanti modali orari/speciali
  $('#btn-save-hours')?.addEventListener('click', saveWeeklyHours);
  $('#btn-save-special')?.addEventListener('click', saveSpecialDay);
  $('#btn-del-special')?.addEventListener('click', deleteSpecialDay);

  // carica lista
  await loadReservations();
});
