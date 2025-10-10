/* helpers */
const $  = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));

async function api(url, opts = {}) {
  opts.credentials = 'include';
  opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers||{});
  const res = await fetch(url, opts);
  let data = null;
  try { data = await res.json(); } catch { /* HTML or empty */ }
  if(!res.ok || (data && data.ok === false)){
    const msg = (data && (data.error || data.message)) || res.statusText || 'Errore richiesta';
    throw new Error(msg);
  }
  return data ?? {ok:true};
}

/* THEME toggle */
function applyTheme(mode){
  const body = document.body;
  if(mode === 'light'){
    body.classList.remove('theme-dark');
    body.classList.add('theme-light');
  } else {
    body.classList.remove('theme-light');
    body.classList.add('theme-dark');
  }
}
function initThemeToggle(){
  const sw = $('#themeSwitch');
  const saved = localStorage.getItem('theme') || 'dark';
  applyTheme(saved);
  if(sw) sw.checked = (saved === 'light');
  sw?.addEventListener('change', ()=>{
    const mode = sw.checked ? 'light' : 'dark';
    localStorage.setItem('theme', mode);
    applyTheme(mode);
  });
}

/* SIDEBAR */
function openSidebar(){ $('#sidebar')?.classList.add('open'); $('#sidebarBackdrop')?.classList.add('show'); }
function closeSidebar(){ $('#sidebar')?.classList.remove('open'); $('#sidebarBackdrop')?.classList.remove('show'); }
function initSidebar(){
  $('#sidebarOpen')?.addEventListener('click', openSidebar);
  $('#sidebarClose')?.addEventListener('click', closeSidebar);
  $('#sidebarBackdrop')?.addEventListener('click', closeSidebar);
}

/* RESERVATIONS */
const fmtDateInput = d => d.toISOString().slice(0,10);

async function loadReservations(){
  const d = $('#flt-date')?.value || '';
  const q = $('#flt-q')?.value?.trim() || '';
  const params = new URLSearchParams();
  if(d) params.set('date', d);
  if(q) params.set('q', q);

  const res = await api('/api/reservations?'+params.toString(), {method:'GET'});
  const list = $('#list'); if(!list) return;
  list.innerHTML = '';
  const empty = $('#list-empty');
  if(!res.items || !res.items.length){
    if(empty) empty.style.display = 'block';
    return;
  }
  if(empty) empty.style.display = 'none';

  res.items.forEach(r=>{
    const el = document.createElement('div');
    el.className = 'card';
    el.style.padding = '12px 14px';
    el.innerHTML = `
      <div class="row" style="gap:12px;align-items:center;display:flex;flex-wrap:wrap">
        <b>${r.date} ${r.time}</b>
        <span>${r.name}</span>
        <span>${r.phone||''}</span>
        <span>👥 ${r.people}</span>
        <span class="chip">${r.status||''}</span>
        <span class="grow"></span>
        <button class="btn" data-edit="${r.id}">Modifica</button>
        <button class="btn btn-danger" data-del="${r.id}">Elimina</button>
      </div>
      ${r.note? `<div style="margin-top:6px;color:#9bb1c7">Note: ${r.note}</div>`:''}
    `;
    list.appendChild(el);
  });

  // bind
  list.querySelectorAll('[data-del]').forEach(b=>{
    b.onclick = async () => {
      if(!confirm('Eliminare la prenotazione?')) return;
      await api('/api/reservations/'+b.dataset.del, {method:'DELETE'});
      await loadReservations();
    };
  });
  list.querySelectorAll('[data-edit]').forEach(b=>{
    b.onclick = async () => {
      const id = b.dataset.edit;
      openReservationModal('Modifica prenotazione');
      // carica record esistente
      try{
        const item = await api('/api/reservations/'+id, {method:'GET'});
        fillReservationForm(item);
        $('#mr-save').onclick = async () => {
          const payload = collectReservationForm();
          await api('/api/reservations/'+id, {method:'PUT', body:JSON.stringify(payload)});
          closeModal('modal-reservation');
          await loadReservations();
        };
      }catch(e){ alert('Errore: '+e.message); }
    };
  });
}

function collectReservationForm(){
  return {
    date:  $('#mr-date').value,
    time:  $('#mr-time').value,
    name:  $('#mr-name').value,
    phone: $('#mr-phone').value,
    people: parseInt($('#mr-people').value||'1',10),
    status: $('#mr-status').value,
    note:   $('#mr-note').value
  };
}
function fillReservationForm(r){
  $('#mr-date').value = r.date || fmtDateInput(new Date());
  $('#mr-time').value = r.time || '20:00';
  $('#mr-name').value = r.name || '';
  $('#mr-phone').value = r.phone || '';
  $('#mr-people').value = r.people || 2;
  $('#mr-status').value = r.status || 'Confermata';
  $('#mr-note').value = r.note || '';
}

/* MODAL utility */
function openModal(id){ const m = $('#'+id); if(m){ m.classList.add('show'); m.setAttribute('aria-hidden','false'); } }
function closeModal(id){ const m = $('#'+id); if(m){ m.classList.remove('show'); m.setAttribute('aria-hidden','true'); } }
function bindModalClose(){
  $$('[data-close]').forEach(btn=>{
    btn.addEventListener('click', ()=> closeModal(btn.getAttribute('data-close')));
  });
}

/* Reservation modal */
function openReservationModal(title='Crea prenotazione'){
  $('#mr-title').textContent = title;
  // default values
  fillReservationForm({date:fmtDateInput(new Date()), time:'20:00', people:2, status:'Confermata'});
  // salva = create
  $('#mr-save').onclick = async () => {
    try{
      const payload = collectReservationForm();
      if(!payload.name || !payload.date || !payload.time){ alert('Compila data, ora e nome'); return; }
      await api('/api/reservations', {method:'POST', body:JSON.stringify(payload)});
      closeModal('modal-reservation');
      await loadReservations();
    }catch(e){ alert('Errore: '+e.message); }
  };
  openModal('modal-reservation');
}

/* MENU voci (placeholders che aprono i modals reali già presenti nel progetto) */
function openWeeklyHours(){ window.showWeeklyHours?.(); }
function openSpecialDays(){ window.showSpecialDays?.(); }
function openPrices(){ alert('Impostazioni prezzi in arrivo'); }
function openDigitalMenu(){ alert('Menu digitale in arrivo'); }
function openStats(){ alert('Statistiche in arrivo'); }

/* INIT */
window.ui = {
  openReservationModal,
  openWeeklyHours,
  openSpecialDays,
  openPrices,
  openDigitalMenu,
  openStats
};

window.addEventListener('DOMContentLoaded', async ()=>{
  initThemeToggle();
  initSidebar();
  bindModalClose();

  // filtri
  const today = fmtDateInput(new Date());
  if($('#flt-date')) $('#flt-date').value = today;

  $('#btn-filter')?.addEventListener('click', loadReservations);
  $('#btn-clear')?.addEventListener('click', ()=>{ if($('#flt-q')) $('#flt-q').value=''; if($('#flt-date')) $('#flt-date').value=''; loadReservations(); });
  $('#btn-30d')?.addEventListener('click', ()=>alert('Storico 30gg — (placeholder UI)'));
  $('#btn-today')?.addEventListener('click', ()=>{ if($('#flt-date')) $('#flt-date').value = fmtDateInput(new Date()); loadReservations(); });
  $('#btn-new')?.addEventListener('click', ()=> openReservationModal());

  // carica lista
  try { await loadReservations(); } catch(e){ console.warn(e); }
});
