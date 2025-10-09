// Helper
const $ = sel => document.querySelector(sel);
const api = async (url, opts={}) => {
  opts.credentials = 'include'; // IMPORTANT: manda i cookie di sessione
  opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers||{});
  const res = await fetch(url, opts);
  const data = await res.json().catch(()=>({ok:false,error:'bad_json'}));
  if(!res.ok || data.ok===false){ throw new Error(data.error || res.statusText); }
  return data;
};
const fmtDateInput = d => d.toISOString().slice(0,10);

// THEME TOGGLE (persistenza + classi)
function applyTheme(theme){
  const body = document.body;
  if(theme === 'light'){
    body.classList.add('theme-light');
    body.classList.remove('theme-dark');
    const sw = $('#themeSwitch'); if(sw) sw.checked = true;
  }else{
    body.classList.add('theme-dark');
    body.classList.remove('theme-light');
    const sw = $('#themeSwitch'); if(sw) sw.checked = false;
  }
}

function initThemeToggle(){
  const saved = localStorage.getItem('theme') || 'dark';
  applyTheme(saved);
  const sw = $('#themeSwitch');
  if(sw){
    sw.addEventListener('change', ()=>{
      const next = sw.checked ? 'light' : 'dark';
      localStorage.setItem('theme', next);
      applyTheme(next);
    });
  }
}

// SIDEBAR TOGGLE
function initSidebar(){
  const btn = $('#menuToggle');
  const close = $('#sidebarClose');
  const body = document.body;
  if(btn){
    btn.onclick = ()=> body.classList.toggle('sidebar-open');
  }
  if(close){
    close.onclick = ()=> body.classList.remove('sidebar-open');
  }
}

// DASHBOARD
async function loadReservations(){
  const dateInput = $('#flt-date');
  const queryInput = $('#flt-q');
  if(!dateInput || !queryInput){ return; } // pagina non è la dashboard

  const d = dateInput.value;
  const q = queryInput.value.trim();
  const params = new URLSearchParams();
  if(d) params.set('date', d);
  if(q) params.set('q', q);
  const res = await api('/api/reservations?'+params.toString(), {method:'GET'});

  const list = $('#list'); if(!list) return;
  list.innerHTML = '';
  const empty = $('#list-empty'); if(empty) empty.style.display = (res.items.length ? 'none' : 'block');

  res.items.forEach(r=>{
    const el = document.createElement('div');
    el.className = 'card';
    el.style.padding = '14px';
    el.innerHTML = `
      <div class="row" style="gap:12px;align-items:center">
        <b>${r.date} ${r.time}</b>
        <span>${r.name}</span>
        <span>${r.phone||''}</span>
        <span>👥 ${r.people}</span>
        <span class="chip">${r.status||''}</span>
        <span class="grow"></span>
        <button class="btn" data-edit="${r.id}">Modifica</button>
        <button class="btn" data-del="${r.id}">Elimina</button>
      </div>
      ${r.note? `<div style="margin-top:6px;color:#9bb1c7">Note: ${r.note}</div>`:''}
    `;
    list.appendChild(el);
  });

  // bind azioni
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
      const at = prompt('Nuova ora (HH:MM) o lascia vuoto', '');
      const payload = {};
      if(when) payload.date = when;
      if(at) payload.time = at;
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
  const name = prompt('Nome', '');
  const phone = prompt('Telefono', '');
  const people = parseInt(prompt('Persone', '2')||'2',10);
  if(!dateStr || !timeStr || !name) return;
  const payload = {date:dateStr,time:timeStr,name,phone,people,status:'Confermata',note:''};
  await api('/api/reservations', {method:'POST', body:JSON.stringify(payload)});
  await loadReservations();
}

async function saveWeeklyHours(){
  const map = {};
  const days = ['0 Lun','1 Mar','2 Mer','3 Gio','4 Ven','5 Sab','6 Dom'];
  days.forEach(d=>{
    const val = prompt(`Finestre orarie per ${d} (es. 12:00-15:00, 19:00-22:30). Vuoto = chiuso`, '');
    if(val!==null) map[d.split(' ')[0]] = (val||'');
  });
  await api('/api/hours', {method:'POST', body:JSON.stringify({hours:map})});
  alert('Orari aggiornati');
}

async function addSpecialDay(){
  const day = prompt('Data speciale (YYYY-MM-DD)', fmtDateInput(new Date()));
  if(!day) return;
  const closed = confirm('Chiudi tutto il giorno? (OK = chiuso)');
  let windows = '';
  if(!closed){
    windows = prompt('Finestre (es. 12:00-15:00, 19:00-22:30)', '');
  }
  await api('/api/special-days', {method:'POST', body:JSON.stringify({day,closed,windows})});
  alert('Giorno speciale salvato');
}

window.addEventListener('DOMContentLoaded', async ()=>{
  initThemeToggle();
  initSidebar();

  // se siamo in dashboard, collega i bottoni
  if($('#btn-filter')){
    $('#btn-filter').onclick = loadReservations;
    $('#btn-clear').onclick = ()=>{ $('#flt-q').value=''; $('#flt-date').value=''; loadReservations(); };
    $('#btn-30d').onclick = ()=>alert('Storico 30gg — (placeholder UI)');
    $('#btn-today').onclick = ()=>{ $('#flt-date').value = fmtDateInput(new Date()); loadReservations(); };
    $('#btn-new').onclick = createReservation;

    // default: oggi
    $('#flt-date').value = fmtDateInput(new Date());
    await loadReservations();

    // opzionali scorciatoie
    window.saveWeeklyHours = saveWeeklyHours;
    window.addSpecialDay = addSpecialDay;
  }
});
