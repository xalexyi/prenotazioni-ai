const $ = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));
const api = async (url, opts={})=>{
  opts.credentials='include';
  opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers||{});
  const res = await fetch(url, opts);
  let data=null; try{ data=await res.json(); }catch(_){}
  if(!res.ok || (data && data.ok===false)){
    throw new Error((data && data.error) || res.statusText || 'Errore API');
  }
  return data || {ok:true};
};
function toast(msg){
  let t = $('#toast');
  if(!t){ t=document.createElement('div'); t.id='toast'; t.className='toast'; document.body.appendChild(t); }
  t.textContent = msg; t.hidden=false; setTimeout(()=>{t.hidden=true;}, 2000);
}

// -------- Stato UI --------
let editingId = null;

// -------- Utility --------
const todayISO = ()=> (new Date()).toISOString().slice(0,10);

// Ricarica KPI e tabella
async function loadStatsAndReservations(){
  const day = $('#fltDate').value;
  const q = $('#fltQ').value.trim();

  // KPI
  try{
    const st = await api('/api/stats?date='+(encodeURIComponent(day||'')));
    $('#kpiToday').textContent = String(st.total_reservations);
    const rev = (st.estimated_revenue || 0).toFixed(2).replace('.', ',');
    $('#kpiRevenue').textContent = `${rev} €`;
  }catch(e){ /* ignora */ }

  // Tabella prenotazioni
  const params = new URLSearchParams();
  if(day) params.set('date', day);
  if(q) params.set('q', q);
  const data = await api('/api/reservations?'+params.toString(), {method:'GET'});

  const body = $('#resBody');
  body.innerHTML='';
  if(!data.items.length){
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="6" class="text-muted">Nessuna prenotazione trovata.</td>`;
    body.appendChild(tr);
    return;
  }
  data.items.forEach(r=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="col-time">
        <span class="time-dot"></span>
        ${r.date} ${r.time}
      </td>
      <td><strong>${r.name}</strong><div class="text-muted">${r.phone||''}</div></td>
      <td class="col-people">${r.people}</td>
      <td class="col-state">
        <span class="badge ${r.status==='Confermata'?'badge-success': (r.status==='Rifiutata'?'badge-warning':'badge-muted')}">${r.status}</span>
      </td>
      <td>${r.note||''}</td>
      <td class="col-actions">
        <div class="actions">
          <button class="btn btn-sm" data-edit="${r.id}">✏️ Modifica</button>
          <button class="btn btn-success btn-sm" data-confirm="${r.id}">✅ Conferma</button>
          <button class="btn btn-outline btn-sm" data-reject="${r.id}">⛔ Rifiuta</button>
          <button class="btn btn-danger btn-sm" data-del="${r.id}">🗑️ Elimina</button>
        </div>
      </td>`;
    body.appendChild(tr);
  });

  // bind azioni
  $$('#resBody [data-edit]').forEach(b=> b.addEventListener('click', ()=> openModalEdit(b.dataset.edit)));
  $$('#resBody [data-confirm]').forEach(b=> b.addEventListener('click', ()=> quickSetStatus(b.dataset.confirm,'Confermata')));
  $$('#resBody [data-reject]').forEach(b=> b.addEventListener('click', ()=> quickSetStatus(b.dataset.reject,'Rifiutata')));
  $$('#resBody [data-del]').forEach(b=> b.addEventListener('click', ()=> confirmDelete(b.dataset.del)));
}

async function quickSetStatus(id, status){
  try{
    await api('/api/reservations/'+id, {method:'PUT', body: JSON.stringify({status})});
    toast('Stato aggiornato');
    await loadStatsAndReservations();
  }catch(e){ toast('Errore: '+e.message); }
}

// -------- Modal prenotazione --------
function openModalNew(){
  editingId = null;
  $('#resModalTitle').textContent = 'Nuova prenotazione';
  $('#mDate').value = $('#fltDate').value || todayISO();
  $('#mTime').value = '20:00';
  $('#mPeople').value = '2';
  $('#mName').value = '';
  $('#mPhone').value = '';
  $('#mStatus').value = 'Confermata';
  $('#mNote').value = '';
  $('#resModal').hidden = false;
}
async function openModalEdit(id){
  try{
    // prendo lista e trovo record (già in tabella). Per semplicità rileggo.
    const list = await api('/api/reservations?date='+encodeURIComponent($('#fltDate').value||''), {method:'GET'});
    const r = list.items.find(x=> String(x.id)===String(id));
    if(!r){ toast('Prenotazione non trovata'); return; }
    editingId = id;
    $('#resModalTitle').textContent = 'Modifica prenotazione';
    $('#mDate').value = r.date;
    $('#mTime').value = r.time;
    $('#mPeople').value = r.people;
    $('#mName').value = r.name;
    $('#mPhone').value = r.phone || '';
    $('#mStatus').value = r.status || 'Pendente';
    $('#mNote').value = r.note || '';
    $('#resModal').hidden = false;
  }catch(e){ toast('Errore: '+e.message); }
}

function closeModal(){ $('#resModal').hidden = true; }
function closeConfirm(){ $('#confirmDlg').hidden = true; }

async function saveReservation(){
  const payload = {
    date: $('#mDate').value,
    time: $('#mTime').value,
    people: parseInt($('#mPeople').value || '2', 10),
    name: $('#mName').value.trim(),
    phone: $('#mPhone').value.trim(),
    status: $('#mStatus').value,
    note: $('#mNote').value.trim(),
  };
  if(!payload.name || !payload.date || !payload.time){
    toast('Compila i campi obbligatori');
    return;
  }
  try{
    if(editingId){
      await api('/api/reservations/'+editingId, {method:'PUT', body: JSON.stringify(payload)});
      toast('Prenotazione aggiornata');
    }else{
      await api('/api/reservations', {method:'POST', body: JSON.stringify(payload)});
      toast('Prenotazione creata');
    }
    closeModal();
    await loadStatsAndReservations();
  }catch(e){ toast('Errore: '+e.message); }
}

function confirmDelete(id){
  $('#confirmMsg').textContent = 'Vuoi cancellare la prenotazione?';
  $('#btnConfirmYes').onclick = async ()=>{
    try{
      await api('/api/reservations/'+id, {method:'DELETE'});
      toast('Eliminata');
      closeConfirm();
      await loadStatsAndReservations();
    }catch(e){ toast('Errore: '+e.message); }
  };
  $('#confirmDlg').hidden = false;
}

// -------- Navigazione pannelli della sidebar (placeholder azioni) --------
window.addEventListener('app:navigate', (ev)=>{
  const page = ev.detail; // 'dashboard' | 'hours' | 'special' | 'pricing' | 'menu' | 'stats'
  // Qui puoi collegare eventuali sezioni o aprire modali dedicate; per ora manteniamo dashboard unica
  if(page==='hours') toast('Apri impostazioni Orari (salvataggio via /api/hours)');
  else if(page==='special') toast('Apri Giorni speciali (salvataggio via /api/special-days)');
  else if(page==='pricing') toast('Apri Prezzi & Coperti (/api/pricing)');
  else if(page==='menu') toast('Apri Menu digitale (/api/menu)');
  else if(page==='stats') toast('Apri Statistiche');
});

// -------- Bind iniziali --------
window.addEventListener('DOMContentLoaded', async ()=>{
  $('#fltDate').value = todayISO();

  $('#btnFilter').onclick = ()=> loadStatsAndReservations();
  $('#btnClear').onclick = ()=>{ $('#fltDate').value=''; $('#fltQ').value=''; loadStatsAndReservations(); };
  $('#btnNew').onclick = openModalNew;

  // Modal close
  $$('#resModal [data-close]').forEach(b=> b.addEventListener('click', closeModal));
  $$('#confirmDlg [data-close]').forEach(b=> b.addEventListener('click', closeConfirm));
  $('#btnSaveRes').onclick = saveReservation;

  await loadStatsAndReservations();
});
