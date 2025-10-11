import { $, $$, toast, wireLeftMenu, openModal, closeModal, wireModalClose, todayISO, fmtForInput, parseFromInput } from "./main.js";

// --------------------------- API ---------------------------
async function getJSON(url){ const r=await fetch(url); return r.json(); }
async function postJSON(url, body){ 
  const r = await fetch(url,{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); 
  return r.json();
}
async function putJSON(url, body){ 
  const r = await fetch(url,{method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); 
  return r.json();
}

// ---------------------- RESERVATIONS -----------------------
function renderReservations(items){
  const box = $('#reservations-list');
  if(!items || !items.length){ box.innerHTML = `<div class="empty">Nessuna prenotazione trovata</div>`; return; }
  box.innerHTML = items.map(r=>`
    <div class="card">
      <div style="display:flex;gap:10px;align-items:center;justify-content:space-between;">
        <div>
          <div><strong>${r.date}</strong> ore <strong>${r.time}</strong> — ${r.name} (${r.people} pax)</div>
          <div class="muted">${r.phone || ''} — ${r.status}</div>
          <div class="muted">${r.note || ''}</div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn--ghost" data-edit="${r.id}">Modifica</button>
          <button class="btn btn--ghost" data-del="${r.id}">Elimina</button>
        </div>
      </div>
    </div>
  `).join('');
}

async function refreshReservations(){
  const q = $('#f-q').value.trim();
  const dateStr = $('#f-date').value.trim();
  const day = dateStr ? parseFromInput(dateStr) : '';
  const url = `/api/reservations?${new URLSearchParams({ q, date:day })}`;
  const js = await getJSON(url);
  if(js.ok){ renderReservations(js.items || []); }
}

function wireReservations(){
  // Oggi
  $('#btn-today')?.addEventListener('click', ()=>{
    $('#f-date').value = fmtForInput(todayISO());
    refreshReservations();
  });
  // Filtri
  $('#btn-filter')?.addEventListener('click', refreshReservations);
  $('#btn-clear')?.addEventListener('click', ()=>{
    $('#f-q').value=''; $('#f-date').value=''; refreshReservations();
  });

  // Nuova prenotazione (modal)
  wireModalClose('#reservation-modal');
  $('#btn-new')?.addEventListener('click', ()=>{
    $('#m-date').value = fmtForInput(todayISO());
    $('#m-time').value = '20:00';
    $('#m-name').value=''; $('#m-phone').value=''; $('#m-people').value='2';
    $('#m-status').value='Confermata'; $('#m-note').value='';
    openModal('#reservation-modal');
  });

  $('#m-save')?.addEventListener('click', async ()=>{
    const body = {
      date: parseFromInput($('#m-date').value.trim()),
      time: $('#m-time').value.trim(),
      name: $('#m-name').value.trim(),
      phone: $('#m-phone').value.trim(),
      people: Number($('#m-people').value || 2),
      status: $('#m-status').value,
      note: $('#m-note').value.trim()
    };
    const js = await postJSON('/api/reservations', body);
    if(js.ok){ toast('Prenotazione creata'); closeModal('#reservation-modal'); refreshReservations(); }
    else toast('Errore: '+(js.error||''));
  });
}

// ----------------------- SETTINGS -------------------------
function ensureHoursInputs(){
  const labels = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica'];
  const container = $('#hours-grid'); container.innerHTML='';
  for(let i=0;i<7;i++){
    const div = document.createElement('div');
    div.innerHTML = `<label>${labels[i]}</label><input class="input" data-dow="${i}" placeholder="12:00-15:00, 19:00-22:30">`;
    container.appendChild(div);
  }
}

function wireSettings(){
  // Salva orari
  $$('[data-action="save-hours"]').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const hours = {};
      $$('input[data-dow]').forEach(inp=> hours[String(inp.getAttribute('data-dow'))] = inp.value.trim());
      const js = await postJSON('/api/hours', { hours });
      if(js.ok) toast('Orari salvati'); else toast('Errore salvataggio orari');
    });
  });

  // Giorni speciali
  $$('[data-action="save-special"]').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const day = ($('[name="special-date"]').value || '').trim();
      if(!day){ toast('Inserisci data YYYY-MM-DD'); return; }
      const closed = $('#special-closed').checked;
      const windows = $('#special-windows').value.trim();
      const js = await postJSON('/api/special-days', { day, closed, windows });
      if(js.ok) { toast('Giorno speciale salvato'); addSpecialRow(day, closed, windows); }
      else toast('Errore giorno speciale');
    });
  });

  // Prezzi & coperti
  $$('[data-action="save-pricing"]').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const avg_price = $('[name="avg_price"]').value || '';
      const cover = $('[name="cover"]').value || '';
      const seats_cap = $('[name="seats_cap"]').value || '';
      const min_people = $('[name="min_people"]').value || '';
      const js = await postJSON('/api/pricing', { avg_price, cover, seats_cap, min_people });
      if(js.ok) toast('Impostazioni salvate'); else toast('Errore impostazioni');
    });
  });

  // Menu digitale
  $$('[data-action="save-menu"]').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const menu_url = $('[name="menu_url"]').value || '';
      const menu_desc = $('[name="menu_desc"]').value || '';
      const js = await postJSON('/api/menu', { menu_url, menu_desc });
      if(js.ok) toast('Menu digitale salvato'); else toast('Errore salvataggio');
    });
  });
}

function addSpecialRow(day, closed, windows){
  const el = document.createElement('div');
  el.textContent = `${day} — ${closed ? 'CHIUSO' : windows}`;
  $('#special-list').prepend(el);
}

// ------------------------- STATS --------------------------
async function refreshStats(){
  const d = $('#s-date').value.trim();
  const day = d ? parseFromInput(d) : '';
  const js = await getJSON('/api/stats?'+new URLSearchParams({date:day}));
  if(!js.ok) return;
  $('#s-total').textContent = js.total_reservations;
  $('#s-avgp').textContent = Number(js.avg_people).toFixed(1);
  $('#s-avgprice').textContent = Number(js.avg_price).toFixed(2);
  $('#s-rev').textContent = Number(js.estimated_revenue).toFixed(2);
  // header “widgets”
  $('#w-res-today').textContent = js.total_reservations;
  $('#w-rev').textContent = Number(js.estimated_revenue).toFixed(2);
}

function wireStats(){
  $('#s-refresh')?.addEventListener('click', refreshStats);
}

// ------------------------- BOOT ---------------------------
(function boot(){
  wireLeftMenu();
  ensureHoursInputs();
  wireSettings();
  wireReservations();
  wireStats();
  $('#btn-today')?.click();   // carica data di oggi + lista
  refreshStats();
})();
