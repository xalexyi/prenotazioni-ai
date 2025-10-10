/* Helpers -------------------------------------------------- */
const $  = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));

async function api(url, opts = {}) {
  opts.credentials = 'include';
  opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers || {});
  try {
    const res = await fetch(url, opts);
    const txt = await res.text();
    let data = {};
    try { data = txt ? JSON.parse(txt) : {}; } catch { data = { ok:false, error: txt || 'bad_json' }; }
    if(!res.ok || data.ok === false) throw new Error(data.error || res.statusText || 'Errore richiesta');
    return data;
  } catch (e) {
    alert('Errore: ' + (e.message || e));
    throw e;
  }
}

/* Theme toggle -------------------------------------------- */
(function themeInit(){
  const sw = $('#themeSwitch');
  if(!sw) return;
  const saved = localStorage.getItem('theme') || 'dark';
  document.body.classList.toggle('theme-dark', saved === 'dark');
  sw.checked = saved === 'dark';
  sw.addEventListener('change', () => {
    const dark = sw.checked;
    document.body.classList.toggle('theme-dark', dark);
    localStorage.setItem('theme', dark ? 'dark' : 'light');
  });
})();

/* Sidebar -------------------------------------------------- */
(function sidebar(){
  const open  = $('#btn-open-menu');
  const close = $('#btn-close-menu');
  const panel = $('#side-panel');
  const ovl   = $('#side-overlay');

  function show(){ panel.setAttribute('data-open','1'); ovl.classList.add('show'); }
  function hide(){ panel.removeAttribute('data-open'); ovl.classList.remove('show'); }

  open?.addEventListener('click', show);
  close?.addEventListener('click', hide);
  ovl?.addEventListener('click', hide);

  // open modal by data-open
  $$('.side-nav a').forEach(a=>{
    a.addEventListener('click', (e)=>{
      e.preventDefault();
      hide();
      const id = a.getAttribute('data-open');
      if(id) openModal(id);
    });
  });
})();

/* Modals --------------------------------------------------- */
function openModal(id){
  const m = document.getElementById(id);
  if(!m) return;
  m.removeAttribute('aria-hidden');
}
function closeModal(id){
  const m = document.getElementById(id);
  if(!m) return;
  m.setAttribute('aria-hidden','true');
}
document.addEventListener('click', (e)=>{
  const c = e.target.closest('[data-close]');
  if(c){
    e.preventDefault();
    closeModal(c.getAttribute('data-close'));
  }
});

/* Reservations -------------------------------------------- */
const fmtDateInput = d => d.toISOString().slice(0,10);

async function loadReservations(){
  const d = $('#flt-date')?.value;
  const q = $('#flt-q')?.value?.trim();
  const params = new URLSearchParams();
  if(d) params.set('date', d);
  if(q) params.set('q', q);
  const res = await api('/api/reservations?'+params.toString(), {method:'GET'});
  const list = $('#list'); list.innerHTML = '';
  $('#list-empty').style.display = (res.items && res.items.length ? 'none' : 'block');

  (res.items || []).forEach(r=>{
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `
      <div class="row" style="gap:12px;align-items:center;padding:12px;">
        <b>${r.date} ${r.time}</b>
        <span>${r.name}</span>
        <span>${r.phone||''}</span>
        <span>👥 ${r.people}</span>
        <span class="chip">${r.status||''}</span>
        <span class="grow"></span>
        <button class="btn" data-edit="${r.id}">Modifica</button>
        <button class="btn" data-del="${r.id}">Elimina</button>
      </div>
      ${r.note? `<div style="margin:-6px 12px 12px;color:#9bb1c7">Note: ${r.note}</div>`:''}
    `;
    list.appendChild(el);
  });

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
      const when = prompt('Nuova data (YYYY-MM-DD) o lascia vuoto', '');
      const at   = prompt('Nuova ora (HH:MM) o lascia vuoto', '');
      const payload = {};
      if(when) payload.date = when;
      if(at)   payload.time = at;
      if(Object.keys(payload).length===0) return;
      await api('/api/reservations/'+id, {method:'PUT', body:JSON.stringify(payload)});
      await loadReservations();
    };
  });
}

async function createReservation(){
  const today = $('#flt-date')?.value || fmtDateInput(new Date());
  const dateStr = prompt('Data (YYYY-MM-DD)', today);
  const timeStr = prompt('Ora (HH:MM)', '20:00');
  const name  = prompt('Nome', '');
  const phone = prompt('Telefono', '');
  const people = parseInt(prompt('Persone', '2')||'2',10);
  if(!dateStr || !timeStr || !name) return;
  const payload = {date:dateStr,time:timeStr,name,phone,people,status:'Confermata',note:''};
  await api('/api/reservations', {method:'POST', body:JSON.stringify(payload)});
  await loadReservations();
}

/* Weekly hours + special days ----------------------------- */
async function saveWeeklyHours(){
  const hours = {};
  $$('.hours').forEach((inp,idx)=>{ hours[idx] = inp.value.trim(); });
  await api('/api/hours', {method:'POST', body:JSON.stringify({hours})});
  alert('Orari aggiornati');
  closeModal('dlgHours');
}

async function saveSpecialDay(){
  const day    = $('#sp-day').value;
  const closed = $('#sp-closed').checked;
  const windows = $('#sp-windows').value.trim();
  if(!day){ alert('Seleziona una data'); return; }
  await api('/api/special-days', { method:'POST', body: JSON.stringify({ day, closed, windows }) });
  alert('Giorno speciale salvato');
  closeModal('dlgSpecial');
}
async function deleteSpecialDay(){
  const day = $('#sp-day').value;
  if(!day){ alert('Seleziona una data'); return; }
  await api('/api/special-days/'+day, { method:'DELETE' });
  alert('Giorno speciale eliminato');
  closeModal('dlgSpecial');
}

/* Pricing -------------------------------------------------- */
async function loadPricing(){
  try{
    const data = await api('/api/settings/pricing', {method:'GET'});
    $('#pr-avg').value = data.avg_price ?? '';
    $('#pr-cap').value = data.max_covers ?? '';
  }catch{ /* già gestito in api() */ }
}
async function savePricing(){
  const avg = parseFloat($('#pr-avg').value || '0');
  const cap = parseInt($('#pr-cap').value || '0', 10);
  await api('/api/settings/pricing', {
    method:'POST',
    body:JSON.stringify({ avg_price: avg, max_covers: cap })
  });
  alert('Impostazioni prezzi & coperti salvate');
  closeModal('dlgPricing');
}

/* Menu digitale ------------------------------------------- */
function renderMenuList(items){
  const box = $('#menu-list');
  if(!items || !items.length){
    box.innerHTML = `<div class="muted">Nessuna voce di menu.</div>`;
    return;
  }
  const rows = items.map(i=>`
    <div class="row table-row">
      <div class="cell grow"><b>${i.name}</b><div class="muted">${i.category||''}</div></div>
      <div class="cell" style="min-width:90px;text-align:right;">€ ${Number(i.price||0).toFixed(2)}</div>
      <div class="cell" style="min-width:100px;text-align:right;">
        <button class="btn" data-del-item="${i.id}">Elimina</button>
      </div>
    </div>`).join('');
  box.innerHTML = `<div class="table">${rows}</div>`;
  $$('#menu-list [data-del-item]').forEach(b=>{
    b.onclick = async () => {
      if(!confirm('Eliminare la voce di menu?')) return;
      await api('/api/menu-items/'+b.dataset.delItem, {method:'DELETE'});
      await loadMenu();
    };
  });
}
async function loadMenu(){
  try{
    const data = await api('/api/menu-items', {method:'GET'});
    renderMenuList(data.items || []);
  }catch{ /* gestito in api() */ }
}
async function addMenuItem(){
  const name = $('#mi-name').value.trim();
  const price = parseFloat($('#mi-price').value || '0');
  const category = $('#mi-cat').value.trim();
  if(!name){ $('#mi-hint').textContent = 'Inserisci un nome'; return; }
  await api('/api/menu-items', {method:'POST', body:JSON.stringify({name, price, category})});
  $('#mi-name').value = ''; $('#mi-price').value=''; $('#mi-cat').value='';
  $('#mi-hint').textContent = 'Aggiunto ✔';
  loadMenu();
}

/* Reports -------------------------------------------------- */
function getRange(){
  const from = $('#rp-from').value; const to = $('#rp-to').value;
  if(!from || !to){ alert('Seleziona un intervallo date'); return null; }
  return {from, to};
}
async function previewReport(){
  const rg = getRange(); if(!rg) return;
  const data = await api(`/api/reports/preview?from=${rg.from}&to=${rg.to}`, {method:'GET'});
  const items = data.items || [];
  const box = $('#rp-preview');
  if(!items.length){ box.innerHTML = `<div class="muted">Nessun dato nel periodo selezionato.</div>`; return; }
  const rows = items.map(i=>`
    <div class="row table-row">
      <div class="cell grow">${i.date}</div>
      <div class="cell" style="min-width:120px;text-align:right;">Prenotazioni: ${i.count}</div>
      <div class="cell" style="min-width:120px;text-align:right;">€ ${Number(i.revenue||0).toFixed(2)}</div>
    </div>`).join('');
  box.innerHTML = `<div class="table">${rows}</div>`;
  $('#rp-info').textContent = `Totale giorni: ${items.length}`;
}
async function downloadCSV(){
  const rg = getRange(); if(!rg) return;
  const url = `/api/reports/csv?from=${rg.from}&to=${rg.to}`;
  // download “grezzo” per compatibilità
  try{
    const res = await fetch(url, {credentials:'include'});
    if(!res.ok) throw new Error(res.statusText);
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `report_${rg.from}_${rg.to}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
  }catch(e){ alert('Errore: ' + (e.message||e)); }
}

/* Wire-up -------------------------------------------------- */
window.addEventListener('DOMContentLoaded', async ()=>{
  // filtri
  const today = fmtDateInput(new Date());
  if($('#flt-date')) $('#flt-date').value = today;

  $('#btn-filter')?.addEventListener('click', loadReservations);
  $('#btn-clear')?.addEventListener('click', ()=>{ $('#flt-q').value=''; $('#flt-date').value=''; loadReservations(); });
  $('#btn-30d')?.addEventListener('click', ()=>alert('Storico 30gg — (placeholder UI)'));
  $('#btn-today')?.addEventListener('click', ()=>{ $('#flt-date').value = fmtDateInput(new Date()); loadReservations(); });
  $('#btn-new')?.addEventListener('click', createReservation);

  // dialogs: save actions
  $('#btn-save-hours')?.addEventListener('click', saveWeeklyHours);
  $('#btn-save-special')?.addEventListener('click', saveSpecialDay);
  $('#btn-del-special')?.addEventListener('click', deleteSpecialDay);

  $('#btn-save-pricing')?.addEventListener('click', savePricing);
  $('#btn-add-item')?.addEventListener('click', addMenuItem);

  $('#btn-preview-report')?.addEventListener('click', previewReport);
  $('#btn-download-csv')?.addEventListener('click', downloadCSV);

  // quando apri i modali, fai eventuale preload
  document.addEventListener('click', (e)=>{
    const trg = e.target.closest('[data-open]');
    if(!trg) return;
    const id = trg.getAttribute('data-open');
    if(id === 'dlgPricing') loadPricing();
    if(id === 'dlgMenu')    loadMenu();
  });

  // prima lista prenotazioni
  await loadReservations();
});
