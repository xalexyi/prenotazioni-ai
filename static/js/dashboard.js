// Helpers
const $  = (sel, ctx=document) => ctx.querySelector(sel);
const $$ = (sel, ctx=document) => [...ctx.querySelectorAll(sel)];
const openModal  = (id) => { const m = $(id); if (m){ m.classList.add('open'); m.setAttribute('aria-hidden','false'); } };
const closeModal = (el) => { const m = el.closest('.modal'); if (m){ m.classList.remove('open'); m.setAttribute('aria-hidden','true'); } };
const toast = (msg, ok=true) => {
  const t = document.createElement('div');
  t.textContent = msg;
  t.style.cssText = `
    position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
    background:${ok?'#2f6dff':'#e35a66'};color:#fff;padding:10px 14px;border-radius:12px;z-index:120;font:600 13px/1 Inter;box-shadow:0 6px 18px rgba(0,0,0,.3)
  `;
  document.body.appendChild(t);
  setTimeout(()=>t.remove(), 1800);
};

// Dropdown 3 puntini
(() => {
  const root = $('#actions');
  const btn  = $('#actionsBtn');
  const menu = $('#actionsMenu');
  if (!root || !btn || !menu) return;

  const toggle = (open) => {
    root.classList[open ? 'add' : 'remove']('open');
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  };

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggle(!root.classList.contains('open'));
  });

  // Chiudi click fuori
  document.addEventListener('click', (e) => {
    if (!root.contains(e.target)) toggle(false);
  });

  // Open modals from dropdown
  menu.addEventListener('click', (e) => {
    const item = e.target.closest('[data-open]');
    if (!item) return;
    toggle(false);
    openModal(item.getAttribute('data-open'));
  });
})();

// Chiudi modali con [data-close] e Esc
$$('.modal [data-close]').forEach(b => b.addEventListener('click', (e)=> closeModal(e.currentTarget)));
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') $$('.modal.open').forEach(m => m.classList.remove('open'));
});

// ======= DATI / API =======
async function api(path, opts={}) {
  const r = await fetch(path, { headers:{'Content-Type':'application/json'}, credentials:'same-origin', ...opts });
  if (!r.ok) throw new Error((await r.text()) || 'Errore');
  return r.json().catch(()=> ({}));
}

// Precarica stato per summary e per compilare i form
async function loadState() {
  try {
    const data = await api('/api/admin/state');
    window.__STATE__ = data;
    renderSummary(data);
    initHoursForm(data.weekly_hours || {});
    initSettingsForm(data.settings || {});
    initSpecialList(data.special_days || []);
  } catch (e) {
    console.error(e);
  }
}
loadState();

// ======= RENDER SUMMARY =======
function renderSummary(data){
  const el = $('#summaryBody');
  if (!el) return;
  const hours = data.weekly_hours || {};
  const days = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica'];
  const map  = ['mon','tue','wed','thu','fri','sat','sun'];
  let html = `<h4>Orari settimanali</h4><ul>`;
  map.forEach((k,i)=>{
    const v = hours[k] || '';
    html += `<li>${days[i]}: ${v ? v : 'CHIUSO'}</li>`;
  });
  html += `</ul><h4>Giorni speciali</h4><ul>`;
  (data.special_days||[]).forEach(g=>{
    html += `<li>${g.date} — ${g.closed ? 'CHIUSO' : (g.windows||'-')}</li>`;
  });
  html += `</ul>`;
  el.innerHTML = html;
}

// ======= ORARI SETTIMANALI =======
function initHoursForm(weekly){
  const grid = $('#hoursForm'); if (!grid) return;
  const labels = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica'];
  const keys   = ['mon','tue','wed','thu','fri','sat','sun'];
  grid.innerHTML = '';
  keys.forEach((k, i) => {
    const row = document.createElement('div');
    row.className = 'row gap-8';
    row.innerHTML = `
      <div style="width:150px;align-self:center">${labels[i]}</div>
      <div class="input grow"><input data-day="${k}" value="${weekly[k] || ''}" placeholder="12:00-15:00, 19:00-23:30"></div>
    `;
    grid.appendChild(row);
  });
}

$('#saveHoursBtn')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget;
  btn.disabled = true;
  try {
    const obj = {};
    $$('[data-day]').forEach(i => obj[i.dataset.day] = i.value.trim());
    await api('/api/admin/weekly_hours', { method:'POST', body:JSON.stringify(obj) });
    toast('Orari salvati');
    closeModal(btn);
    loadState();
  } catch (err) {
    console.error(err); toast('Errore salvataggio orari', false);
  } finally { btn.disabled = false; }
});

// ======= GIORNI SPECIALI =======
function initSpecialList(list){
  const wrap = $('#specialList'); if (!wrap) return;
  if (!list.length){ wrap.innerHTML = `<div class="muted">Nessun giorno speciale</div>`; return; }
  wrap.innerHTML = list.map(g => `
    <div class="row gap-8">
      <div class="input" style="width:160px"><input value="${g.date}" disabled></div>
      <div class="input grow"><input value="${g.closed ? 'CHIUSO' : (g.windows || '-')}" disabled></div>
    </div>
  `).join('');
}

$('#saveSpecialBtn')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget; btn.disabled = true;
  try {
    const payload = {
      date: ($('#specialDate')?.value||'').trim(),
      closed: $('#specialClosed')?.checked || false,
      windows: ($('#specialWindows')?.value||'').trim()
    };
    await api('/api/admin/special_day', { method:'POST', body: JSON.stringify(payload) });
    toast('Giorno speciale salvato');
    closeModal(btn); loadState();
  } catch(err){ console.error(err); toast('Errore giorni speciali', false); }
  finally { btn.disabled = false; }
});

$('#deleteSpecialBtn')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget; btn.disabled = true;
  try {
    const d = ($('#specialDate')?.value||'').trim();
    if (!d){ toast('Inserisci una data', false); btn.disabled = false; return; }
    await api('/api/admin/special_day', { method:'DELETE', body: JSON.stringify({ date:d }) });
    toast('Giorno rimosso');
    closeModal(btn); loadState();
  } catch(err){ console.error(err); toast('Errore eliminazione', false); }
  finally { btn.disabled = false; }
});

// ======= IMPOSTAZIONI =======
function inputRow(label, id, val, type='text'){
  return `<label class="input"><div class="muted">${label}</div><input id="${id}" type="${type}" value="${val ?? ''}"></label>`;
}
function initSettingsForm(s){
  const el = $('#settingsForm'); if (!el) return;
  el.innerHTML = [
    inputRow('Timezone','set_tz', s.timezone || 'Europe/Rome'),
    inputRow('Step (min)','set_step', s.step || 15, 'number'),
    inputRow('Ultimo ordine (min)','set_last_order', s.last_order || 15, 'number'),
    inputRow('Min persone','set_min_pax', s.min_people || 1, 'number'),
    inputRow('Max persone','set_max_pax', s.max_people || 12, 'number'),
    inputRow('Capacità/slot','set_capacity', s.capacity || 6, 'number'),
  ].join('');
}

$('#saveSettingsBtn')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget; btn.disabled = true;
  try {
    const payload = {
      timezone:  $('#set_tz')?.value,
      step:      +($('#set_step')?.value||15),
      last_order:+($('#set_last_order')?.value||15),
      min_people:+($('#set_min_pax')?.value||1),
      max_people:+($('#set_max_pax')?.value||12),
      capacity:  +($('#set_capacity')?.value||6),
    };
    await api('/api/admin/settings', { method:'POST', body: JSON.stringify(payload) });
    toast('Impostazioni salvate');
    closeModal(btn);
    loadState();
  } catch(err){ console.error(err); toast('Errore impostazioni', false); }
  finally { btn.disabled = false; }
});

// ======= TOKEN =======
$('#saveTokenBtn')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget; btn.disabled = true;
  try {
    const token = ($('#tokenInput')?.value||'').trim();
    await api('/api/admin/token', { method:'POST', body: JSON.stringify({ token }) });
    toast('Token salvato');
    closeModal(btn);
  } catch(err){ console.error(err); toast('Errore salvataggio token', false); }
  finally { btn.disabled = false; }
});

// ======= CREA PRENOTAZIONE =======
function initCreateForm(){
  const el = $('#createForm'); if (!el) return;
  el.innerHTML = `
    <label class="input"><div class="muted">Data</div><input id="c_date" type="text" placeholder="gg/mm/aaaa"></label>
    <label class="input"><div class="muted">Ora</div><input id="c_time" type="text" value="20:00"></label>
    <label class="input"><div class="muted">Nome</div><input id="c_name" type="text"></label>
    <label class="input"><div class="muted">Telefono</div><input id="c_phone" type="text"></label>
    <label class="input"><div class="muted">Persone</div><input id="c_pax" type="number" value="2"></label>
    <label class="input"><div class="muted">Stato</div>
      <select id="c_status">
        <option value="Confermata">Confermata</option>
        <option value="In attesa">In attesa</option>
        <option value="Cancellata">Cancellata</option>
      </select>
    </label>
    <label class="input" style="grid-column:1/-1"><div class="muted">Note</div><textarea id="c_notes" rows="2" placeholder="Allergie, tavolo, ecc."></textarea></label>
  `;
}
initCreateForm();

$('#saveBookingBtn')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget; btn.disabled = true;
  try {
    const payload = {
      date:  ($('#c_date')?.value||'').trim(),
      time:  ($('#c_time')?.value||'').trim(),
      name:  ($('#c_name')?.value||'').trim(),
      phone: ($('#c_phone')?.value||'').trim(),
      pax:   +($('#c_pax')?.value||2),
      status:($('#c_status')?.value||'Confermata'),
      notes: ($('#c_notes')?.value||'').trim(),
    };
    await api('/api/admin/booking', { method:'POST', body: JSON.stringify(payload) });
    toast('Prenotazione creata');
    closeModal(btn);
    // refresh lista prenotazioni se serve
  } catch(err){ console.error(err); toast('Errore creazione prenotazione', false); }
  finally { btn.disabled = false; }
});

// Aprire modali dai bottoni data-open anche fuori dal menu
$$('[data-open]')?.forEach(b => b.addEventListener('click', (e)=>{
  const sel = e.currentTarget.getAttribute('data-open');
  openModal(sel);
}));
