// Helpers
const $  = (sel, ctx=document) => ctx.querySelector(sel);
const $$ = (sel, ctx=document) => Array.from(ctx.querySelectorAll(sel));

const api = async (url, opts={}) => {
  opts.credentials = 'include';
  opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers||{});
  const res = await fetch(url, opts);
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : {}; } catch(e){ /* non-json */ }
  if(!res.ok){
    const msg = (data && (data.error||data.message)) || res.statusText || 'Errore richiesta';
    throw new Error(msg);
  }
  return data ?? {};
};

// ---------------- THEME TOGGLE ----------------
function applyTheme(theme){
  const body = document.body;
  if(theme === 'light'){
    body.classList.add('theme-light');
    $('#themeSwitch').checked = true;
  }else{
    body.classList.remove('theme-light');
    $('#themeSwitch').checked = false;
  }
}
function initTheme(){
  const saved = localStorage.getItem('theme') || 'dark';
  applyTheme(saved);
  const sw = $('#themeSwitch');
  if(sw){
    sw.addEventListener('change', () => {
      const t = sw.checked ? 'light' : 'dark';
      localStorage.setItem('theme', t);
      applyTheme(t);
    });
  }
}

// ---------------- SIDEPANEL ----------------
function sideOpen(){ $('#sidepanel')?.classList.add('open'); $('#sidepanel-backdrop')?.classList.add('show'); }
function sideClose(){ $('#sidepanel')?.classList.remove('open'); $('#sidepanel-backdrop')?.classList.remove('show'); }

function bindSidePanel(){
  $('#menuBtn')?.addEventListener('click', sideOpen);
  $('#sideClose')?.addEventListener('click', sideClose);
  $('#sidepanel-backdrop')?.addEventListener('click', sideClose);

  // voci menu
  $('#menu-orari')?.addEventListener('click', ()=>{ sideClose(); openModal('dlgHours'); });
  $('#menu-speciali')?.addEventListener('click', ()=>{ sideClose(); openModal('dlgSpecial'); });
  $('#menu-prezzi')?.addEventListener('click', ()=>{ sideClose(); alert('Impostazioni prezzi in arrivo'); });
  $('#menu-menu')?.addEventListener('click', ()=>{ sideClose(); alert('Menu digitale in arrivo'); });
  $('#menu-stats')?.addEventListener('click', ()=>{ sideClose(); alert('Statistiche e report in arrivo'); });
}

// ---------------- MODALS ----------------
function openModal(id){ const m = document.getElementById(id); if(m){ m.classList.add('show'); } }
function closeModal(id){ const m = document.getElementById(id); if(m){ m.classList.remove('show'); } }
function bindModals(){
  $$('[data-close]')?.forEach(b=>{
    b.addEventListener('click', ()=> closeModal(b.getAttribute('data-close')));
  });
}

// ---------------- HOURS / SPECIAL DAYS ----------------
async function saveWeeklyHours(){
  const hours = {};
  $$('.wh').forEach(inp => { hours[inp.dataset.dow] = inp.value.trim(); });
  await api('/api/hours', { method:'POST', body: JSON.stringify({ hours }) });
  alert('Orari aggiornati');
  closeModal('dlgHours');
}

async function saveSpecialDay(){
  const day = $('#sp-day').value.trim();
  const closed = $('#sp-closed').checked;
  const windows = $('#sp-windows').value.trim();
  if(!day){ alert('Inserisci una data (YYYY-MM-DD)'); return; }
  await api('/api/special-days', { method:'POST', body: JSON.stringify({ day, closed, windows }) });
  alert('Giorno speciale salvato');
  closeModal('dlgSpecial');
}

async function deleteSpecialDay(){
  const day = $('#sp-day').value.trim();
  if(!day){ alert('Inserisci la data da eliminare (YYYY-MM-DD)'); return; }
  await api('/api/special-days/'+day, { method:'DELETE' });
  alert('Giorno speciale eliminato');
  closeModal('dlgSpecial');
}

// ---------------- DASHBOARD BIND ONLY IF PRESENT ----------------
function fmtDateInput(d){
  const pad = n => String(n).padStart(2,'0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
}

async function loadReservations(){ /* placeholder: non tocchiamo backend/UX attuale */ }

function bindDashboard(){
  // Filtri (se esistono nella pagina)
  $('#btn-filter')?.addEventListener('click', loadReservations);
  $('#btn-clear')?.addEventListener('click', ()=>{
    const d = $('#flt-date'); const q = $('#flt-q');
    if(d) d.value = ''; if(q) q.value = '';
    loadReservations();
  });
  $('#btn-today')?.addEventListener('click', ()=>{
    const d = $('#flt-date'); if(d) d.value = fmtDateInput(new Date());
    loadReservations();
  });

  // Nuova prenotazione (lasciamo il comportamento attuale – prompt)
  $('#btn-new')?.addEventListener('click', async ()=>{
    try{
      const today = fmtDateInput(new Date());
      const dateStr = prompt('Data (YYYY-MM-DD)', today);
      if(!dateStr) return;
      const timeStr = prompt('Ora (HH:MM)', '20:00'); if(!timeStr) return;
      const name = prompt('Nome', ''); if(!name) return;
      const phone = prompt('Telefono', '');
      const people = parseInt(prompt('Persone','2')||'2',10);
      const payload = {date:dateStr,time:timeStr,name,phone,people,status:'Confermata',note:''};
      await api('/api/reservations', {method:'POST', body:JSON.stringify(payload)});
      alert('Prenotazione creata');
      loadReservations();
    }catch(e){
      alert('Errore: '+e.message);
    }
  });

  // Bottoni salvataggio modali
  $('#btn-save-hours')?.addEventListener('click', async ()=>{
    try{ await saveWeeklyHours(); }catch(e){ alert('Errore: '+e.message); }
  });
  $('#btn-save-special')?.addEventListener('click', async ()=>{
    try{ await saveSpecialDay(); }catch(e){ alert('Errore: '+e.message); }
  });
  $('#btn-del-special')?.addEventListener('click', async ()=>{
    try{ await deleteSpecialDay(); }catch(e){ alert('Errore: '+e.message); }
  });
}

// ---------------- INIT ----------------
window.addEventListener('DOMContentLoaded', ()=>{
  initTheme();
  bindSidePanel();
  bindModals();
  bindDashboard();
});
