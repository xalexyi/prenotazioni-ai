// Helpers
const $ = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));

async function api(url, opts = {}) {
  const defaults = {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' }
  };
  const res = await fetch(url, Object.assign(defaults, opts));
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok || (data && data.ok === false)) {
    throw new Error((data && data.error) || res.statusText);
  }
  return data;
}

// ---------------- Theme toggle (persistente) ----------------
(function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  document.body.classList.toggle('theme-dark', saved === 'dark');
  const sw = $('#themeSwitch');
  if (sw) {
    sw.checked = saved !== 'dark'; // giallo (on) = light, grigio (off) = dark
    sw.addEventListener('change', () => {
      const next = sw.checked ? 'light' : 'dark';
      document.body.classList.toggle('theme-dark', next === 'dark');
      localStorage.setItem('theme', next);
    });
  }
})();

// ---------------- Drawer laterale ----------------
(function initDrawer() {
  const menu = $('#sideMenu');
  const overlay = $('#overlay');
  const openBtn = $('#btnOpenMenu');
  const closeBtn = $('#btnCloseMenu');

  if (!menu || !overlay || !openBtn || !closeBtn) return;

  const open = () => {
    menu.classList.add('open');
    overlay.hidden = false;
  };
  const close = () => {
    menu.classList.remove('open');
    overlay.hidden = true;
  };

  openBtn.addEventListener('click', open);
  closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', close);

  // Voci che aprono modali
  $$('.side-link[data-open]').forEach(b => {
    b.addEventListener('click', () => {
      const id = b.getAttribute('data-open');
      openModal(id);
      close();
    });
  });
})();

// ---------------- Modali generiche ----------------
function openModal(id) {
  const dlg = document.getElementById(id);
  if (!dlg) return;
  dlg.hidden = false;
  document.body.classList.add('modal-open');
}
function closeModal(id) {
  const dlg = document.getElementById(id);
  if (!dlg) return;
  dlg.hidden = true;
  document.body.classList.remove('modal-open');
}
document.addEventListener('click', (ev) => {
  const btn = ev.target.closest('[data-close-modal]');
  if (btn) {
    closeModal(btn.getAttribute('data-close-modal'));
  }
});

// ---------------- Dashboard behaviour ----------------
function fmtDateInput(d) {
  return d.toISOString().slice(0, 10);
}

async function loadReservations() {
  const date = $('#flt-date')?.value || '';
  const q = $('#flt-q')?.value.trim() || '';
  const params = new URLSearchParams();
  if (date) params.set('date', date);
  if (q) params.set('q', q);

  const list = $('#list');
  const empty = $('#list-empty');
  if (!list || !empty) return;

  list.innerHTML = '';
  try {
    const res = await api('/api/reservations?' + params.toString(), { method: 'GET' });
    if (!res.items || res.items.length === 0) {
      empty.style.display = 'block';
      return;
    }
    empty.style.display = 'none';

    res.items.forEach(r => {
      const el = document.createElement('div');
      el.className = 'card';
      el.style.padding = '12px 14px';
      el.innerHTML = `
        <div class="row" style="gap:12px;align-items:center">
          <b>${r.date} ${r.time}</b>
          <span>${r.name}</span>
          <span>${r.phone || ''}</span>
          <span>👥 ${r.people}</span>
          <span class="chip">${r.status || ''}</span>
          <span class="grow"></span>
          <button class="btn" data-edit="${r.id}">Modifica</button>
          <button class="btn" data-del="${r.id}">Elimina</button>
        </div>
        ${r.note ? `<div style="margin-top:6px;color:#9bb1c7">Note: ${r.note}</div>` : ''}
      `;
      list.appendChild(el);
    });

    // Bind azioni
    $$('#list [data-del]').forEach(b => {
      b.onclick = async () => {
        if (!confirm('Eliminare la prenotazione?')) return;
        await api('/api/reservations/' + b.dataset.del, { method: 'DELETE' });
        loadReservations();
      };
    });
    $$('#list [data-edit]').forEach(b => {
      b.onclick = async () => {
        const id = b.dataset.edit;
        const r = await api('/api/reservations/' + id, { method: 'GET' });
        fillReservationDialog(r.item || {});
        openModal('dlgReservation');
        $('#btn-save-reservation').onclick = async () => {
          const payload = readReservationDialog();
          await api('/api/reservations/' + id, { method: 'PUT', body: JSON.stringify(payload) });
          closeModal('dlgReservation');
          loadReservations();
        };
      };
    });

  } catch (e) {
    console.error(e);
    empty.style.display = 'block';
  }
}

function fillReservationDialog(r = {}) {
  $('#res-date').value = r.date || fmtDateInput(new Date());
  $('#res-time').value = r.time || '20:00';
  $('#res-name').value = r.name || '';
  $('#res-phone').value = r.phone || '';
  $('#res-people').value = r.people || 2;
  $('#res-status').value = r.status || 'Confermata';
  $('#res-note').value = r.note || '';
}

function readReservationDialog() {
  return {
    date: $('#res-date').value,
    time: $('#res-time').value,
    name: $('#res-name').value.trim(),
    phone: $('#res-phone').value.trim(),
    people: parseInt($('#res-people').value || '2', 10),
    status: $('#res-status').value,
    note: $('#res-note').value.trim()
  };
}

async function createReservation() {
  fillReservationDialog({});
  openModal('dlgReservation');
  $('#btn-save-reservation').onclick = async () => {
    const payload = readReservationDialog();
    if (!payload.date || !payload.time || !payload.name) return;
    await api('/api/reservations', { method: 'POST', body: JSON.stringify(payload) });
    closeModal('dlgReservation');
    loadReservations();
  };
}

// ------ Orari settimanali (invio semplice) ------
async function saveWeeklyHours() {
  const map = {};
  $$('.wh-input').forEach(inp => {
    map[inp.dataset.day] = inp.value.trim();
  });
  await api('/api/hours', { method: 'POST', body: JSON.stringify({ hours: map }) });
  closeModal('dlgHours');
  alert('Orari aggiornati');
}

// ------ Giorni speciali ------
async function saveSpecialDay() {
  const day = $('#sp-date').value;
  const closed = $('#sp-closed').checked;
  const windows = $('#sp-windows').value.trim();
  if (!day) return;
  await api('/api/special-days', { method: 'POST', body: JSON.stringify({ day, closed, windows }) });
  closeModal('dlgSpecial');
  alert('Giorno speciale salvato');
}

async function deleteSpecialDay() {
  const day = $('#sp-date').value;
  if (!day) return;
  await api('/api/special-days/' + day, { method: 'DELETE' });
  closeModal('dlgSpecial');
  alert('Giorno speciale eliminato');
}

// ---------------- Init ----------------
window.addEventListener('DOMContentLoaded', () => {
  // filtri
  const today = fmtDateInput(new Date());
  if ($('#flt-date')) $('#flt-date').value = today;

  $('#btn-filter')?.addEventListener('click', loadReservations);
  $('#btn-clear')?.addEventListener('click', () => {
    if ($('#flt-q')) $('#flt-q').value = '';
    if ($('#flt-date')) $('#flt-date').value = '';
    loadReservations();
  });
  $('#btn-30d')?.addEventListener('click', () => alert('Storico 30gg — (placeholder UI)'));
  $('#btn-today')?.addEventListener('click', () => {
    if ($('#flt-date')) $('#flt-date').value = fmtDateInput(new Date());
    loadReservations();
  });
  $('#btn-new')?.addEventListener('click', createReservation);

  // salvataggi dialog
  $('#btn-save-hours')?.addEventListener('click', saveWeeklyHours);
  $('#btn-save-special')?.addEventListener('click', saveSpecialDay);
  $('#btn-del-special')?.addEventListener('click', deleteSpecialDay);

  // carica lista iniziale
  loadReservations();
});
