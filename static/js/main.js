const $ = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));

const api = async (url, opts={}) => {
  opts.credentials = 'include';
  opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers||{});
  const res = await fetch(url, opts);
  let data = null;
  try { data = await res.json(); } catch { data = {ok:false, error:'bad_json'}; }
  if(!res.ok || data.ok === false){ throw new Error(data.error || res.statusText); }
  return data;
};

const fmtDateInput = d => d.toISOString().slice(0,10);

function toast(msg){
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(()=> el.classList.add('show'), 10);
  setTimeout(()=>{
    el.classList.remove('show');
    setTimeout(()=> el.remove(), 250);
  }, 2200);
}

/* -------------------- THEME TOGGLE -------------------- */
function applyTheme(){
  const theme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', theme);
  const sw = $('#themeSwitch');
  if(sw) sw.checked = (theme === 'light');
}
function setupThemeToggle(){
  const sw = $('#themeSwitch');
  if(!sw) return;
  applyTheme();
  sw.onchange = () => {
    const theme = sw.checked ? 'light' : 'dark';
    localStorage.setItem('theme', theme);
    applyTheme();
  };
}

/* -------------------- SIDEBAR NAV -------------------- */
function showView(name){
  const views = ['reservations','pricing','menu','hours','special','stats'];
  views.forEach(v => {
    const el = $('#view-'+v);
    if(el) el.style.display = (v === name ? 'block' : 'none');
  });
  // selezione visiva
  $$('.side-link').forEach(b => b.classList.toggle('active', b.dataset.view === name));
}
function setupSidebar(){
  $$('.side-link').forEach(btn=>{
    btn.onclick = ()=>{
      showView(btn.dataset.view);
      if(btn.dataset.view === 'reservations') loadReservations();
    };
  });
  // view di default
  showView('reservations');
}

/* -------------------- RESERVATIONS -------------------- */
async function loadReservations(){
  const d = $('#flt-date')?.value;
  const q = $('#flt-q')?.value?.trim();
  const params = new URLSearchParams();
  if(d) params.set('date', d);
  if(q) params.set('q', q);
  const res = await api('/api/reservations?'+params.toString(), {method:'GET'});

  const list = $('#list'); 
  if(!list) return;
  list.innerHTML = '';
  const empty = $('#list-empty');
  if(empty) empty.style.display = (res.items.length ? 'none' : 'block');

  res.items.forEach(r=>{
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

  // bind azioni
  list.querySelectorAll('[data-del]').forEach(b=>{
    b.onclick = async () => {
      if(!confirm('Eliminare la prenotazione?')) return;
      await api('/api/reservations/'+b.dataset.del, {method:'DELETE'});
      toast('Eliminato');
      await loadReservations();
    };
  });
  list.querySelectorAll('[data-edit]').forEach(b=>{
    b.onclick = async () => {
      const id = b.dataset.edit;
      const when = prompt('Nuova data (YYYY-MM-DD) o lascia vuoto', '');
      const at = prompt('Nuova ora (HH:MM) o lascia vuoto', '');
      const payload = {};
      if(when) payload.date = when;
      if(at) payload.time = at;
      if(Object.keys(payload).length===0) return;
      await api('/api/reservations/'+id, {method:'PUT', body:JSON.stringify(payload)});
      toast('Aggiornato');
      await loadReservations();
    };
  });

  // KPI semplici
  $('#kpiToday') && ($('#kpiToday').textContent = String(res.items.length));
  const avgPrice =  parseFloat(localStorage.getItem('avg_price_cache') || '25') || 25;
  $('#kpiRevenue') && ($('#kpiRevenue').textContent = (res.items.length*avgPrice).toFixed(2)+' €');
}

async function createReservation(){
  const today = $('#flt-date')?.value || fmtDateInput(new Date());
  const dateStr = prompt('Data (YYYY-MM-DD)', today);
  const timeStr = prompt('Ora (HH:MM)', '20:00');
  const name = prompt('Nome', '');
  const phone = prompt('Telefono', '');
  const people = parseInt(prompt('Persone', '2')||'2',10);
  if(!dateStr || !timeStr || !name) return;
  const payload = {date:dateStr,time:timeStr,name,phone,people,status:'Confermata',note:''};
  await api('/api/reservations', {method:'POST', body:JSON.stringify(payload)});
  toast('Prenotazione creata');
  await loadReservations();
}

/* -------------------- HOURS & SPECIAL DAYS -------------------- */
async function saveWeeklyHours(){
  const map = {};
  $$('.hour-win').forEach(inp=>{
    map[String(inp.dataset.dow)] = inp.value || '';
  });
  await api('/api/hours', {method:'POST', body:JSON.stringify({hours:map})});
  toast('Orari aggiornati');
}

async function addSpecialDay(){
  const day = $('#sp_day')?.value;
  const closed = $('#sp_closed')?.checked;
  const windows = $('#sp_windows')?.value || '';
  if(!day) return alert('Scegli una data');
  await api('/api/special-days', {method:'POST', body:JSON.stringify({day,closed,windows})});
  toast('Giorno speciale salvato');
}

/* -------------------- PRICING -------------------- */
async function savePricing(){
  const payload = {
    avg_price: $('#avg_price')?.value,
    cover: $('#cover')?.value,
    seats_cap: $('#seats_cap')?.value,
    min_people: $('#min_people')?.value
  };
  await api('/api/pricing', {method:'POST', body:JSON.stringify(payload)});
  // cache lato client per KPI rapidi
  if(payload.avg_price) localStorage.setItem('avg_price_cache', String(payload.avg_price));
  toast('Prezzi & coperti salvati');
}

/* -------------------- MENU DIGITALE -------------------- */
async function saveMenu(){
  const payload = {
    menu_url: $('#menu_url')?.value,
    menu_desc: $('#menu_desc')?.value
  };
  await api('/api/menu', {method:'POST', body:JSON.stringify(payload)});
  toast('Menu digitale salvato');
}

/* -------------------- STATS -------------------- */
async function loadStats(){
  const d = $('#st_date')?.value;
  const params = new URLSearchParams();
  if(d) params.set('date', d);
  const res = await api('/api/stats?'+params.toString(), {method:'GET'});
  $('#st_total').textContent = String(res.total_reservations);
  $('#st_avg_people').textContent = String(res.avg_people.toFixed(2));
  $('#st_avg_price').textContent = res.avg_price.toFixed(2)+' €';
  $('#st_revenue').textContent = res.estimated_revenue.toFixed(2)+' €';
}

/* -------------------- INIT -------------------- */
window.addEventListener('DOMContentLoaded', async ()=>{
  setupThemeToggle();
  setupSidebar();

  // Buttons
  $('#btn-filter') && ($('#btn-filter').onclick = loadReservations);
  $('#btn-clear') && ($('#btn-clear').onclick = ()=>{ $('#flt-q').value=''; $('#flt-date').value=''; loadReservations(); });
  $('#btn-today') && ($('#btn-today').onclick = ()=>{ $('#flt-date').value = fmtDateInput(new Date()); loadReservations(); });
  $('#btn-new') && ($('#btn-new').onclick = createReservation);

  $('#btn-save-hours') && ($('#btn-save-hours').onclick = saveWeeklyHours);
  $('#btn-save-special') && ($('#btn-save-special').onclick = addSpecialDay);

  $('#btn-save-pricing') && ($('#btn-save-pricing').onclick = savePricing);
  $('#btn-save-menu') && ($('#btn-save-menu').onclick = saveMenu);

  $('#btn-load-stats') && ($('#btn-load-stats').onclick = loadStats);

  // Defaults
  $('#flt-date') && ($('#flt-date').value = fmtDateInput(new Date()));
  if($('#view-reservations')) await loadReservations();
});
