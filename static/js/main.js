// utils
const $ = sel => document.querySelector(sel);
const $$ = sel => document.querySelectorAll(sel);

// API helper (con cookie di sessione)
async function api(url, opts = {}) {
  const options = {
    method: opts.method || 'GET',
    headers: Object.assign({'Content-Type':'application/json'}, opts.headers || {}),
    credentials: 'include',
    body: opts.body
  };
  const res = await fetch(url, options);
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = (data && (data.message || data.error)) || res.statusText;
    throw new Error(msg || 'Errore richiesta');
  }
  return data || {};
}

/* -----------------------------
   THEME TOGGLE (persistente)
------------------------------*/
(function initTheme() {
  const key = 'theme';
  const saved = localStorage.getItem(key); // 'dark' | 'light' | null
  const isDark = saved ? (saved === 'dark') : true;
  document.body.classList.toggle('theme-dark', isDark);
  document.body.classList.toggle('theme-light', !isDark);
  const sw = $('#themeSwitch');
  if (sw) {
    sw.checked = isDark; // giallo = dark
    sw.addEventListener('change', () => {
      const dark = sw.checked;
      document.body.classList.toggle('theme-dark', dark);
      document.body.classList.toggle('theme-light', !dark);
      localStorage.setItem(key, dark ? 'dark' : 'light');
    });
  }
})();

/* -----------------------------
   DRAWER laterale
------------------------------*/
(function initDrawer(){
  const drawer = $('#drawer');
  const overlay = $('#drawer-overlay');
  const openBtn = $('#btn-open-drawer');
  const closeBtn = $('#btn-close-drawer');

  const open = () => { drawer.classList.add('open'); overlay.classList.add('show'); };
  const close = () => { drawer.classList.remove('open'); overlay.classList.remove('show'); };

  if (openBtn) openBtn.addEventListener('click', open);
  if (closeBtn) closeBtn.addEventListener('click', close);
  if (overlay) overlay.addEventListener('click', close);

  // azioni voci drawer
  $$('#drawer .drawer-nav [data-action]').forEach(btn => {
    btn.addEventListener('click', () => {
      const act = btn.getAttribute('data-action');
      if (act === 'hours') openModal('dlgHours');
      else if (act === 'special') openModal('dlgSpecial');
      else if (act === 'pricing') alert('Impostazioni prezzi: in arrivo');
      else if (act === 'menu') alert('Menu digitale: in arrivo');
      else if (act === 'stats') alert('Statistiche: in arrivo');
      close();
    });
  });
})();

/* -----------------------------
   MODALI
------------------------------*/
function openModal(id){ const m = document.getElementById(id); if (m) m.classList.add('show'); }
function closeModal(id){ const m = document.getElementById(id); if (m) m.classList.remove('show'); }

document.addEventListener('click', (e) => {
  const t = e.target;
  const toClose = t.getAttribute && t.getAttribute('data-close');
  if (toClose) closeModal(toClose);
});

/* -----------------------------
   DASHBOARD LIST & FILTRI
------------------------------*/
const fmtDateInput = d => d.toISOString().slice(0,10);

async function loadReservations(){
  const d = $('#flt-date') ? $('#flt-date').value : '';
  const q = $('#flt-q') ? $('#flt-q').value.trim() : '';
  const params = new URLSearchParams();
  if (d) params.set('date', d);
  if (q) params.set('q', q);
  let res = { items: [] };
  try {
    res = await api('/api/reservations?' + params.toString(), { method:'GET' });
  } catch (err) {
    console.warn('API reservations:', err.message);
  }

  const list = $('#list');
  const empty = $('#list-empty');
  if (!list || !empty) return;

  list.innerHTML = '';
  empty.style.display = (res.items && res.items.length) ? 'none' : 'block';

  (res.items || []).forEach(r => {
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `
      <div class="row" style="gap:12px;align-items:center">
        <b>${r.date || ''} ${r.time || ''}</b>
        <span>${r.name || ''}</span>
        <span>${r.phone || ''}</span>
        <span>👥 ${r.people || 0}</span>
        <span class="chip">${r.status || ''}</span>
        <span class="grow"></span>
        <button class="btn" data-edit="${r.id}">Modifica</button>
        <button class="btn" data-del="${r.id}">Elimina</button>
      </div>
      ${r.note ? `<div style="margin-top:6px;color:#9bb1c7">Note: ${r.note}</div>` : ''}
    `;
    list.appendChild(el);
  });

  // azioni
  list.querySelectorAll('[data-del]').forEach(b => {
    b.onclick = async () => {
      if (!confirm('Eliminare la prenotazione?')) return;
      try {
        await api('/api/reservations/' + b.dataset.del, { method:'DELETE' });
      } catch (e) {
        alert('Errore: ' + e.message);
      }
      loadReservations();
    };
  });
  list.querySelectorAll('[data-edit]').forEach(b => {
    b.onclick = async () => {
      const id = b.dataset.edit;
      const when = prompt('Nuova data (YYYY-MM-DD) o lascia vuoto', '');
      const at = prompt('Nuova ora (HH:MM) o lascia vuoto', '');
      const payload = {};
      if (when) payload.date = when;
      if (at) payload.time = at;
      if (Object.keys(payload).length === 0) return;
      try {
        await api('/api/reservations/' + id, { method:'PUT', body: JSON.stringify(payload) });
      } catch (e) {
        alert('Errore: ' + e.message);
      }
      loadReservations();
    };
  });
}

async function createReservation(payload){
  try {
    await api('/api/reservations', { method:'POST', body: JSON.stringify(payload) });
  } catch (e) {
    throw e;
  }
}

/* -----------------------------
   ORARI SETTIMANALI
------------------------------*/
async function saveWeeklyHours(){
  const map = {};
  document.querySelectorAll('#dlgHours .hours').forEach(inp => {
    map[inp.dataset.day] = (inp.value || '');
  });
  try {
    await api('/api/hours', { method:'POST', body: JSON.stringify({ hours: map }) });
    alert('Orari aggiornati');
    closeModal('dlgHours');
  } catch (e) {
    alert('Errore: ' + e.message);
  }
}

/* -----------------------------
   GIORNI SPECIALI
------------------------------*/
async function saveSpecialDay(){
  const day = $('#sp-date')?.value;
  if (!day) { alert('Scegli una data'); return; }
  const closed = $('#sp-closed')?.checked;
  const windows = $('#sp-windows')?.value.trim();
  try {
    await api('/api/special-days', { method:'POST', body: JSON.stringify({ day, closed, windows }) });
    alert('Giorno speciale salvato');
    closeModal('dlgSpecial');
  } catch (e) {
    alert('Errore: ' + e.message);
  }
}

async function deleteSpecialDay(){
  const day = $('#sp-date')?.value;
  if (!day) { alert('Scegli una data'); return; }
  try {
    await api('/api/special-days/' + day, { method:'DELETE' });
    alert('Giorno speciale eliminato');
    closeModal('dlgSpecial');
  } catch (e) {
    alert('Errore: ' + e.message);
  }
}

/* -----------------------------
   MODALE NUOVA PRENOTAZIONE
------------------------------*/
function openNewReservation(){
  // preset data/ora
  const today = fmtDateInput(new Date());
  $('#nr-date').value = today;
  $('#nr-time').value = '20:00';
  $('#nr-name').value = '';
  $('#nr-phone').value = '';
  $('#nr-people').value = '2';
  $('#nr-status').value = 'Confermata';
  $('#nr-note').value = '';
  openModal('dlgNew');
}

/* -----------------------------
   INIT
------------------------------*/
window.addEventListener('DOMContentLoaded', () => {
  // default: oggi
  const today = fmtDateInput(new Date());
  if ($('#flt-date')) $('#flt-date').value = today;

  // filtri
  $('#btn-filter')?.addEventListener('click', loadReservations);
  $('#btn-clear')?.addEventListener('click', () => {
    if ($('#flt-q')) $('#flt-q').value = '';
    if ($('#flt-date')) $('#flt-date').value = '';
    loadReservations();
  });
  $('#btn-30d')?.addEventListener('click', () => alert('Storico 30gg — (placeholder UI)'));
  $('#btn-today')?.addEventListener('click', () => { if ($('#flt-date')) $('#flt-date').value = fmtDateInput(new Date()); loadReservations(); });
  $('#btn-new')?.addEventListener('click', openNewReservation);

  // modali
  $('#btn-save-hours')?.addEventListener('click', saveWeeklyHours);
  $('#btn-save-special')?.addEventListener('click', saveSpecialDay);
  $('#btn-del-special')?.addEventListener('click', deleteSpecialDay);

  // submit nuova prenotazione
  $('#newResForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      date: $('#nr-date').value,
      time: $('#nr-time').value,
      name: $('#nr-name').value.trim(),
      phone: $('#nr-phone').value.trim(),
      people: parseInt($('#nr-people').value, 10),
      status: $('#nr-status').value,
      note: $('#nr-note').value.trim()
    };
    if (!payload.date || !payload.time || !payload.name || !payload.people){
      alert('Compila i campi obbligatori');
      return;
    }
    try {
      await createReservation(payload);
      closeModal('dlgNew');
      await loadReservations();
    } catch (e) {
      alert('Errore: ' + e.message);
    }
  });

  // carica lista iniziale
  loadReservations();
});
