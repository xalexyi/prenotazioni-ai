/* static/js/admin_schedule.js */
(function () {
  const BASE = '';
  const el  = (s, r=document) => r.querySelector(s);
  const els = (s, r=document) => Array.from(r.querySelectorAll(s));

  // -------------------- session helper --------------------
  const SESSION_KEY = 'admin_token';
  let SESSION_ID = window.SESSION_ID || window.localStorage.getItem('session_id');
  if (!SESSION_ID) {
    try {
      SESSION_ID = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());
    } catch {
      SESSION_ID = String(Date.now());
    }
    window.localStorage.setItem('session_id', SESSION_ID);
  }

  async function loadSession() {
    const r = await fetch(`${BASE}/api/public/sessions/${SESSION_ID}`, { cache:'no-store' });
    if (!r.ok) return {};
    return await r.json();
  }
  async function saveSession(partial) {
    await fetch(`${BASE}/api/public/sessions/${SESSION_ID}`, {
      method: 'PATCH',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ update: partial }),
    });
  }
  async function getAdminToken() {
    const s = await loadSession();
    return (s.session && s.session[SESSION_KEY]) || '';
  }
  async function setAdminToken(token) {
    await saveSession({ session: { [SESSION_KEY]: token } });
  }

  // -------------------- fetch wrapper --------------------
  async function adminFetch(url, opts={}) {
    const token = await getAdminToken();
    if (!token) throw new Error('Token admin mancante: clicca “Imposta token”.');
    const baseHeaders = {
      'X-Admin-Token': token,
      'Accept': 'application/json'
    };
    const headers = Object.assign({}, baseHeaders, opts.headers || {});
    const r = await fetch(url, { ...opts, headers });
    return r;
  }

  // -------------------- UI helpers --------------------
  function toast(msg, type='ok') {
    const t = document.createElement('div');
    t.textContent = msg;
    t.style.position='fixed'; t.style.right='16px'; t.style.bottom='16px';
    t.style.padding='10px 14px'; t.style.borderRadius='10px'; t.style.zIndex='99999';
    t.style.color='#fff'; t.style.fontWeight='700';
    t.style.background = type==='ok'? '#0ea5e9' : (type==='warn'? '#f59e0b' : '#ef4444');
    t.style.boxShadow='0 6px 24px rgba(0,0,0,.25)';
    document.body.appendChild(t);
    setTimeout(()=>t.remove(), 2200);
  }

  function setBusy(btn, busy){
    if(!btn) return;
    btn.disabled = !!busy;
    if (busy) {
      btn.dataset._txt = btn.textContent;
      btn.textContent = 'Attendi…';
    } else if (btn.dataset._txt) {
      btn.textContent = btn.dataset._txt;
      delete btn.dataset._txt;
    }
  }

  function addTimeRow(container, start='', end='') {
    const row = document.createElement('div');
    row.className = 'time-row';
    row.innerHTML = `
      <input type="time" class="start" value="${start}" required/> —
      <input type="time" class="end" value="${end}" required/>
      <button type="button" class="btn-remove" aria-label="Rimuovi">×</button>
    `;
    row.querySelector('.btn-remove').onclick = () => row.remove();
    container.appendChild(row);
  }

  function collectDayRows(dayBox){
    return els('.time-row', dayBox).map(r => {
      const s = (el('.start', r).value || '').trim();
      const e = (el('.end', r).value || '').trim();
      if (!s || !e) return null;
      return { start: s, end: e };
    }).filter(Boolean);
  }

  // -------------------- token modal --------------------
  async function prefillToken() {
    try{
      const tk = await getAdminToken();
      const input = el('#adminTokenInput');
      if (input && !input.value) input.value = tk || '';
    }catch(_){}
  }
  async function saveToken() {
    const token = (el('#adminTokenInput')?.value || '').trim();
    await setAdminToken(token);
    toast('Token salvato');
    try { el('#modalToken')?.close?.(); } catch(_){}
  }

  // -------------------- weekly --------------------
  const DAYS = ['mon','tue','wed','thu','fri','sat','sun'];
  function openWeekly() {
    DAYS.forEach(d => {
      const c = el(`#w-${d}`); if (!c) return;
      c.innerHTML = '';
      addTimeRow(c, '12:00', '15:00');
      addTimeRow(c, '19:00', '23:30');
    });
  }

  async function saveWeekly() {
    const btn = el('#btn-save-weekly');
    setBusy(btn, true);
    try{
      const rid = Number(document.body.dataset.restaurantId || '1');
      const cmds = [];
      cmds.push(`RID=${rid}`);
      DAYS.forEach(d => {
        const rows = collectDayRows(el(`#w-${d}`));
        const segments = rows.map(r => `${r.start}-${r.end}`).join(',');
        cmds.push(`WEEK ${d} ${segments}`);
      });
      const step = Number(el('#set-step').value || '15');
      const last = Number(el('#set-last').value || '15');
      const capacity = Number(el('#set-capacity').value || '6');
      const pmin = Number(el('#set-party-min').value || '1');
      const pmax = Number(el('#set-party-max').value || '12');
      const tz   = (el('#set-tz').value || 'Europe/Rome').trim();
      cmds.push(`SETTINGS step=${step} last=${last} capacity=${capacity} party=${pmin}-${pmax} tz=${tz}`);

      const body = cmds.join('\n');
      const r = await adminFetch(`/api/admin/schedule/commands`, {
        method:'POST',
        headers:{'Content-Type':'text/plain'},
        body
      });
      if (!r.ok) {
        const txt = await r.text().catch(()=>String(r.status));
        throw new Error(txt || ('HTTP '+r.status));
      }
      toast('Orari settimanali salvati');
      try { el('#modalWeekly')?.close?.(); } catch(_){}
    }catch(e){
      toast((e && e.message) ? e.message : 'Errore salvataggio', 'err');
    }finally{
      setBusy(btn, false);
    }
  }

  // -------------------- special days --------------------
  function openSpecial() {
    el('#sp-date').value = '';
    el('#sp-closed').checked = true;
    const rowsBox = el('#sp-rows');
    if (rowsBox) {
      rowsBox.innerHTML = '';
      addTimeRow(rowsBox, '19:00', '23:00');
    }
    toggleSpecial();
  }

  function toggleSpecial() {
    const closed = el('#sp-closed')?.checked;
    const box = el('#sp-rows');
    if (box) box.style.display = closed ? 'none' : 'block';
  }

  async function saveSpecial() {
    const btn = el('#btn-save-special');
    setBusy(btn, true);
    try{
      const rid = Number(document.body.dataset.restaurantId || '1');
      const date = el('#sp-date').value;
      const closed = el('#sp-closed').checked;
      if (!date) { toast('Scegli una data','warn'); return; }

      const payload = { restaurant_id: rid, date, closed };
      if (!closed) {
        const rows = collectDayRows(el('#sp-rows'));
        if (!rows.length) { toast('Aggiungi almeno una fascia','warn'); return; }
        // invia come array strutturato [{start,end}]
        payload.ranges = rows.map(r => ({ start: r.start, end: r.end }));
      } else {
        payload.ranges = [];
      }

      const r = await adminFetch(`/api/admin/special-days/upsert`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      if (!r.ok) {
        let msg = 'Errore salvataggio';
        try { const j = await r.json(); msg = j.error || msg; } catch { msg = await r.text() || msg; }
        throw new Error(msg);
      }
      toast('Giorno speciale salvato');
      try { el('#modalSpecial')?.close?.(); } catch(_){}
    }catch(e){
      toast((e && e.message) ? e.message : 'Errore salvataggio', 'err');
    }finally{
      setBusy(btn, false);
    }
  }

  async function deleteSpecial() {
    const btn = el('#btn-del-special');
    setBusy(btn, true);
    try{
      const rid = Number(document.body.dataset.restaurantId || '1');
      const date = el('#sp-date').value;
      if (!date) { toast('Scegli una data','warn'); return; }
      const r = await adminFetch(`/api/admin/special-days/delete`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ restaurant_id: rid, date })
      });
      if (!r.ok) {
        let msg = 'Errore eliminazione';
        try { const j = await r.json(); msg = j.error || msg; } catch { msg = await r.text() || msg; }
        throw new Error(msg);
      }
      toast('Giorno speciale eliminato');
      try { el('#modalSpecial')?.close?.(); } catch(_){}
    }catch(e){
      toast((e && e.message) ? e.message : 'Errore eliminazione', 'err');
    }finally{
      setBusy(btn, false);
    }
  }

  // -------------------- bind --------------------
  function bind() {
    prefillToken().catch(()=>{});

    el('#btn-save-token')?.addEventListener('click', ()=>saveToken().catch(e=>toast(e.message,'err')));
    el('#adminTokenInput')?.addEventListener('keydown', (ev)=>{
      if (ev.key === 'Enter') { ev.preventDefault(); saveToken().catch(e=>toast(e.message,'err')); }
    });

    el('#btn-weekly')?.addEventListener('click', openWeekly);
    el('#btn-save-weekly')?.addEventListener('click', ()=>saveWeekly().catch(e=>toast(e.message,'err')));

    el('#btn-special')?.addEventListener('click', openSpecial);
    el('#btn-save-special')?.addEventListener('click', ()=>saveSpecial().catch(e=>toast(e.message,'err')));
    el('#btn-del-special')?.addEventListener('click', ()=>deleteSpecial().catch(e=>toast(e.message,'err')));
    el('#sp-closed')?.addEventListener('change', toggleSpecial);

    // add rows
    el('#btn-add-w-mon')?.addEventListener('click', ()=>addTimeRow(el('#w-mon')));
    el('#btn-add-w-tue')?.addEventListener('click', ()=>addTimeRow(el('#w-tue')));
    el('#btn-add-w-wed')?.addEventListener('click', ()=>addTimeRow(el('#w-wed')));
    el('#btn-add-w-thu')?.addEventListener('click', ()=>addTimeRow(el('#w-thu')));
    el('#btn-add-w-fri')?.addEventListener('click', ()=>addTimeRow(el('#w-fri')));
    el('#btn-add-w-sat')?.addEventListener('click', ()=>addTimeRow(el('#w-sat')));
    el('#btn-add-w-sun')?.addEventListener('click', ()=>addTimeRow(el('#w-sun')));
    el('#btn-add-sp-row')?.addEventListener('click', ()=>addTimeRow(el('#sp-rows')));
  }

  window.addEventListener('DOMContentLoaded', bind);
})();
