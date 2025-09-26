/* Dashboard / modali orari + special + impostazioni + riepilogo
   - Compat con ID vecchi/nuovi (weekly/special/settings/state)
   - Retry su 400 con payload alternativo
   - Toast bottom per conferme/errori
*/
(() => {
  // ---------- mini query ----------
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // ---------- toast ----------
  function ensureToastHost() {
    if (!$('#toast-host')) {
      const host = document.createElement('div');
      host.id = 'toast-host';
      Object.assign(host.style, {
        position: 'fixed', left: '50%', bottom: '22px', transform: 'translateX(-50%)',
        zIndex: '9999', display: 'flex', flexDirection: 'column', gap: '8px'
      });
      document.body.appendChild(host);
    }
  }
  function toast(msg, kind = 'ok') {
    ensureToastHost();
    const t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    Object.assign(t.style, {
      padding: '10px 14px', borderRadius: '10px',
      background: kind === 'ok' ? '#16a34a' : '#e11d48',
      color: '#fff', boxShadow: '0 8px 22px rgba(0,0,0,.25)', fontWeight: '700'
    });
    $('#toast-host').appendChild(t);
    setTimeout(() => t.remove(), 2200);
  }

  // ---------- Modal helpers ----------
  function openModal(sel) {
    const m = $(sel);
    if (!m) return;
    m.setAttribute('aria-hidden', 'false');
    m.dataset.open = '1';
    const onBackdrop = (e) => { if (e.target === m) closeModal(sel); };
    const onKey = (e) => { if (e.key === 'Escape') closeModal(sel); };
    m._closers = { onBackdrop, onKey };
    m.addEventListener('click', onBackdrop);
    document.addEventListener('keydown', onKey);
  }
  function closeModal(sel) {
    const m = $(sel);
    if (!m) return;
    m.setAttribute('aria-hidden', 'true');
    m.dataset.open = '';
    if (m._closers) {
      m.removeEventListener('click', m._closers.onBackdrop);
      document.removeEventListener('keydown', m._closers.onKey);
      m._closers = null;
    }
  }
  $$('.modal .js-close').forEach((b) => {
    b.addEventListener('click', (e) => {
      const modal = e.target.closest('.modal-backdrop');
      if (modal) closeModal('#' + modal.id);
    });
  });

  // ---------- Kebab menu ----------
  const kebabBtn = $('#btn-kebab');
  const kebabMenu = $('#kebab-menu');
  function kebabOpen() {
    if (!kebabMenu) return;
    kebabMenu.hidden = false;
    kebabMenu.classList.add('open');
    kebabBtn?.classList.add('kebab-active');
    kebabBtn?.setAttribute('aria-expanded', 'true');
    const onDoc = (e) => { if (!kebabMenu.contains(e.target) && e.target !== kebabBtn) kebabClose(); };
    const onKey = (e) => { if (e.key === 'Escape') kebabClose(); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    kebabMenu._off = () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }
  function kebabClose() {
    if (!kebabMenu) return;
    kebabMenu.classList.remove('open');
    kebabBtn?.classList.remove('kebab-active');
    kebabBtn?.setAttribute('aria-expanded', 'false');
    setTimeout(() => { if (kebabMenu) kebabMenu.hidden = true; }, 100);
    if (kebabMenu._off) kebabMenu._off();
  }
  kebabBtn?.addEventListener('click', () => {
    if (kebabMenu.hidden) kebabOpen(); else kebabClose();
  });

  // ---------- helpers orari ----------
  const dayNames = ["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"];
  const isHHMM = (s) => /^\d{1,2}:\d{2}$/.test(s);
  function rangesToString(arr) {
    return (arr || []).map(r => `${r.start}-${r.end}`).join(', ');
  }
  function parseRanges(s) {
    const out = [];
    (s || '').split(',').forEach(part => {
      const p = part.trim();
      if (!p) return;
      const m = p.match(/^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$/);
      if (!m) throw new Error(`Intervallo non valido: "${p}" (usa HH:MM-HH:MM)`);
      if (!isHHMM(m[1]) || !isHHMM(m[2])) throw new Error(`Formato orario non valido in "${p}"`);
      out.push({ start: m[1], end: m[2] });
    });
    return out;
  }
  function normalizeWeekly(weekly) {
    // Accetta sia {0:[..],1:[..]} che [{weekday:0,ranges:[..]},..]
    const out = new Array(7).fill(0).map(() => []);
    if (Array.isArray(weekly)) {
      weekly.forEach(d => {
        const w = Number(d.weekday);
        (d.ranges || []).forEach(r => out[w].push({ start: r.start, end: r.end }));
      });
    } else if (weekly && typeof weekly === 'object') {
      Object.keys(weekly).forEach(k => {
        const w = Number(k);
        (weekly[k] || []).forEach(r => out[w].push({ start: r.start, end: r.end }));
      });
    }
    return out;
  }
  function weeklyToMap(weeklyArr) {
    const m = {};
    weeklyArr.forEach((ranges, idx) => { m[idx] = ranges.map(r => ({ start: r.start, end: r.end })); });
    return m;
  }

  // ---------- API ----------
  async function getState() {
    const r = await fetch('/api/admin/schedule/state', { credentials: 'same-origin', headers: { 'Accept': 'application/json' }});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  // tenta list-shape poi map-shape
  async function saveWeeklySmart(weeklyArr) {
    // 1) list payload
    let r = await fetch('/api/admin/schedule/weekly', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify({ weekly: weeklyArr.map((ranges, weekday) => ({ weekday, ranges })) })
    });
    if (r.ok) return r.json();

    // 2) retry: map payload
    r = await fetch('/api/admin/schedule/weekly', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify({ weekly: weeklyToMap(weeklyArr) })
    });
    if (!r.ok) {
      let msg = 'HTTP ' + r.status;
      try { const j = await r.json(); if (j && j.error) msg = j.error; } catch {}
      throw new Error(msg);
    }
    return r.json();
  }

  async function saveSettings(payload) {
    const r = await fetch('/api/admin/schedule/settings', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  async function listSpecials() {
    const r = await fetch('/api/admin/special-days/list', { credentials: 'same-origin' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  async function upsertSpecialSmart(payload) {
    // tenta come già costruito, se 400 ritenta con shape minimale
    let r = await fetch('/api/admin/special-days/upsert', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify(payload),
    });
    if (r.ok) return r.json();

    // retry: se non è closed invia solo ranges con chiavi {start,end}
    if (!payload.closed && Array.isArray(payload.ranges)) {
      const retry = {
        date: payload.date,
        closed: false,
        ranges: payload.ranges.map(x => ({ start: x.start, end: x.end })),
      };
      r = await fetch('/api/admin/special-days/upsert', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type':'application/json' },
        body: JSON.stringify(retry),
      });
      if (r.ok) return r.json();
    }
    let msg = 'HTTP ' + r.status;
    try { const j = await r.json(); if (j && j.error) msg = j.error; } catch {}
    throw new Error(msg);
  }

  async function deleteSpecial(date) {
    const r = await fetch('/api/admin/special-days/delete', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify({ date }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  // ---------- WEEKLY UI ----------
  function buildWeeklyForm(weeklyArr) {
    const box = $('#weekly-form');
    if (!box) return;
    box.innerHTML = '';
    for (let i = 0; i < 7; i++) {
      const row = document.createElement('div');
      row.className = 'w-row';
      row.innerHTML = `
        <div><strong>${dayNames[i]}</strong></div>
        <input class="input" data-wd="${i}" placeholder="12:00-15:00, 19:00-23:30">
      `;
      box.appendChild(row);
      box.querySelector(`input[data-wd="${i}"]`).value = rangesToString(weeklyArr[i]);
    }
  }
  async function actionWeekly() {
    try {
      const st = await getState();
      const weeklyArr = normalizeWeekly(st.weekly);
      buildWeeklyForm(weeklyArr);
      openModal('#modal-weekly');
    } catch (e) {
      toast('Errore caricamento orari', 'err');
      console.error(e);
    }
  }
  $('#weekly-save')?.addEventListener('click', async () => {
    try {
      const weeklyArr = [];
      $$('#weekly-form input[data-wd]').forEach(inp => {
        weeklyArr[Number(inp.dataset.wd)] = parseRanges(inp.value);
      });
      await saveWeeklySmart(weeklyArr);
      toast('Orari settimanali aggiornati ✅', 'ok');
      closeModal('#modal-weekly');
    } catch (e) {
      toast(e.message || 'Errore salvataggio orari', 'err');
      console.error(e);
    }
  });

  // ---------- SPECIAL DAYS UI ----------
  async function refreshSpecialList() {
    const cont = $('#sp-list');
    if (!cont) return;
    cont.textContent = 'Carico...';
    const { ok, items } = await listSpecials();
    if (!ok) { cont.textContent = 'Errore caricamento'; return; }
    if (!items || items.length === 0) { cont.innerHTML = '<em>Nessuna regola</em>'; return; }
    const ul = document.createElement('div');
    ul.className = 'list';
    items.forEach(it => {
      const li = document.createElement('div');
      li.className = 'list-item';
      const ranges = (it.ranges || []).map(r => `${r.start}-${r.end}`).join(', ');
      li.textContent = `${it.date} — ${it.closed ? 'CHIUSO' : (ranges || 'aperto')}`;
      ul.appendChild(li);
    });
    cont.innerHTML = '';
    cont.appendChild(ul);
  }
  async function actionSpecial() {
    try {
      await refreshSpecialList();
      openModal('#modal-special');
    } catch (e) {
      toast('Errore caricamento giorni speciali', 'err');
      console.error(e);
    }
  }
  $('#sp-add')?.addEventListener('click', async () => {
    try {
      const date = $('#sp-date').value;
      const closed = $('#sp-closed').checked;
      if (!date) throw new Error('Seleziona una data');
      if (closed) {
        await upsertSpecialSmart({ date, closed: true });
      } else {
        const ranges = parseRanges($('#sp-ranges').value);
        await upsertSpecialSmart({ date, closed: false, ranges });
      }
      await refreshSpecialList();
      toast('Regola salvata ✅', 'ok');
    } catch (e) {
      toast(e.message || 'Errore salvataggio', 'err');
      console.error(e);
    }
  });
  $('#sp-del')?.addEventListener('click', async () => {
    try {
      const date = $('#sp-date').value;
      if (!date) throw new Error('Seleziona una data');
      await deleteSpecial(date);
      await refreshSpecialList();
      toast('Regola eliminata 🗑️', 'ok');
    } catch (e) {
      toast(e.message || 'Errore eliminazione', 'err');
      console.error(e);
    }
  });

  // ---------- SETTINGS UI ----------
  async function actionSettings() {
    try {
      const st = await getState();
      const s = st.settings || {};
      $('#st-step').value = s.slot_step_min ?? 15;
      $('#st-last').value = s.last_order_min ?? 15;
      $('#st-cap').value  = s.capacity_per_slot ?? 6;
      $('#st-minp').value = s.min_party ?? 1;
      $('#st-maxp').value = s.max_party ?? 12;
      $('#st-tz').value   = s.tz || 'Europe/Rome';
      openModal('#modal-settings');
    } catch (e) {
      toast('Errore caricamento impostazioni', 'err');
      console.error(e);
    }
  }
  $('#settings-save')?.addEventListener('click', async () => {
    try {
      const payload = {
        slot_step_min: Number($('#st-step').value) || 15,
        last_order_min: Number($('#st-last').value) || 15,
        capacity_per_slot: Number($('#st-cap').value) || 6,
        min_party: Number($('#st-minp').value) || 1,
        max_party: Number($('#st-maxp').value) || 12,
        tz: ($('#st-tz').value || 'Europe/Rome').trim(),
      };
      await saveSettings(payload);
      toast('Impostazioni salvate ✅', 'ok');
      closeModal('#modal-settings');
    } catch (e) {
      toast(e.message || 'Errore salvataggio impostazioni', 'err');
      console.error(e);
    }
  });

  // ---------- STATE (riepilogo) ----------
  async function actionState() {
    try {
      const st = await getState();
      // se c’è <pre id="state-json"> mostro JSON grezzo (fallback)
      const pre = $('#state-json');
      if (pre) pre.textContent = JSON.stringify(st, null, 2);

      // Se hai un contenitore strutturato, riempilo qui (opzionale):
      // es: #state-weekly, #state-settings, #state-specials (se presenti nel template)
      openModal('#modal-state');
    } catch (e) {
      toast('Errore lettura stato', 'err');
      console.error(e);
    }
  }

  // ---------- HELP ----------
  function actionHelp() {
    openModal('#modal-help');
  }

  // Wire menu items
  kebabMenu?.addEventListener('click', (e) => {
    const btn = e.target.closest('.k-item');
    if (!btn) return;
    const act = btn.dataset.act;
    kebabClose();
    if (act === 'weekly') return actionWeekly();
    if (act === 'special') return actionSpecial();
    if (act === 'settings') return actionSettings();
    if (act === 'state') return actionState();
    if (act === 'help') return actionHelp();
  });
})();
