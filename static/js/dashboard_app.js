(() => {
  // ---------- QS HELPERS (safe) ----------
  const $  = (q, el = document) => el.querySelector(q);
  const $$ = (q, el = document) => Array.from(el.querySelectorAll(q));
  const on = (el, ev, fn) => el && el.addEventListener(ev, fn);

  // ---------- ELEMENTS ----------
  const fDate      = $('#fDate');
  const fQuery     = $('#fQuery');
  const btnFilter  = $('#btnFilter');
  const btnClear   = $('#btnClear');
  const btnToday   = $('#btnToday');
  const btnHistory = $('#btnHistory');
  const btnNew     = $('#btnNew');
  const list       = $('#reservations');
  const empty      = $('#empty');

  // Modals / form
  const dlgCreate  = $('#dlgCreate');
  const formCreate = $('#formCreate');
  const cId     = $('#cId');
  const cDate   = $('#cDate');
  const cTime   = $('#cTime');
  const cName   = $('#cName');
  const cPhone  = $('#cPhone');
  const cPeople = $('#cPeople');
  const cStatus = $('#cStatus');
  const cNote   = $('#cNote');

  const dlgConfirm    = $('#dlgConfirm');
  const btnConfirmYes = $('#btnConfirmYes');

  const dlgWeekly  = $('#dlgWeekly');
  const dlgSpecial = $('#dlgSpecial');
  const dlgStatus  = $('#dlgStatus');

  // compat: alcuni template usano statusBody, altri statusContent
  const statusBox = $('#statusContent') || $('#statusBody');

  // Topbar / dropdown (se presenti)
  const themeToggle = $('#themeToggle');
  const actionsWrap = $('#actionsMenu');
  const menuBtn     = $('#menuBtn');
  const menuDd      = $('#menuDd');
  const btnWeekly   = $('#btnWeekly');
  const btnSpecial  = $('#btnSpecial');
  const btnStatus   = $('#btnStatus');
  const btnMenu     = $('#btnMenuPricing');

  // Close [data-close]
  $$('[data-close]').forEach(b => on(b, 'click', e => {
    const d = e.target.closest('dialog');
    if (d) d.close();
  }));

  // ---------- HELPERS ----------
  const fmtTime = (t) => (t ? String(t).slice(0, 5) : '');
  const todayISO = () => new Date().toISOString().slice(0,10);

  if (fDate && !fDate.value) fDate.value = todayISO();

  function escapeHtml(s){
    return (s||'').replace(/[&<>"']/g, c => (
      {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
    ));
  }

  // Toast minimale
  let toastEl;
  function toast(msg){
    if (!toastEl){
      toastEl = document.createElement('div');
      toastEl.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#1e2938;border:1px solid #2c3e55;color:#e8eef5;padding:10px 14px;border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,.35);z-index:2000;transition:opacity .2s';
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.style.opacity = '1';
    setTimeout(()=>toastEl.style.opacity='0', 1800);
  }

  // ---------- LIST RENDER ----------
  async function loadList() {
    if (!list || !empty) return;

    const url = new URL('/api/reservations', location.origin);
    if (fDate?.value) url.searchParams.set('date', fDate.value);

    let data = [];
    try{
      data = await fetch(url).then(r => r.json());
    }catch(e){
      console.error('Errore /api/reservations', e);
      data = [];
    }

    // filtro client-side su fQuery (nome/telefono/note/orario)
    const q = (fQuery?.value || '').trim().toLowerCase();
    if (q){
      data = data.filter(r => {
        const hay = [
          r.name, r.phone, r.note, fmtTime(r.time), String(r.people), String(r.status)
        ].map(x => (x||'').toString().toLowerCase());
        return hay.some(x => x.includes(q));
      });
    }

    list.innerHTML = '';
    if (!data.length) {
      empty.style.display = 'block';
      return;
    }
    empty.style.display = 'none';

    for (const r of data) {
      const li = document.createElement('li');
      li.className = 'res-item';

      const left = document.createElement('div');
      left.className = 'res-left';
      left.innerHTML = `
        <span class="res-time">${fmtTime(r.time)}</span> —
        <span class="res-name">${escapeHtml(r.name)} <b>(${r.people})</b></span>
        ${r.phone ? `<span class="badge">📞 ${escapeHtml(r.phone)}</span>` : ''}
        <span class="badge">${escapeHtml(r.status)}</span>
        ${r.note ? `<div class="res-note">${escapeHtml(r.note)}</div>` : ''}
      `;

      const act = document.createElement('div');
      act.className = 'res-actions';
      act.innerHTML = `
        <button class="btn ghost" data-edit>Modifica</button>
        <button class="btn ghost" data-confirm>Conferma</button>
        <button class="btn ghost" data-reject>Rifiuta</button>
        <button class="btn btn-danger" data-del>Elimina</button>
      `;

      li.append(left, act);
      list.appendChild(li);

      // azioni (safe)
      const btnEdit = act.querySelector('[data-edit]');
      const btnDel  = act.querySelector('[data-del]');
      const btnOk   = act.querySelector('[data-confirm]');
      const btnNo   = act.querySelector('[data-reject]');

      on(btnEdit, 'click', () => openCreate(r));
      on(btnDel,  'click', () => askDelete(r.id));
      on(btnOk,   'click', () => quickStatus(r.id, 'confirmed'));
      on(btnNo,   'click', () => quickStatus(r.id, 'rejected'));
    }
  }

  // ---------- FILTER BAR ----------
  on(btnFilter,  'click', () => loadList());
  on(btnClear,   'click', () => { if (fQuery) fQuery.value = ''; loadList(); });
  on(btnToday,   'click', () => { if (fDate) fDate.value = todayISO(); loadList(); });
  on(btnHistory, 'click', () => { location.href = '?history=30'; });

  // ---------- CREATE / EDIT ----------
  on(btnNew, 'click', () => openCreate());

  function openCreate(r = null){
    if (!dlgCreate) return;
    const titleEl = $('#dlgCreateTitle');
    if (titleEl) titleEl.textContent = r?.id ? 'Modifica prenotazione' : 'Crea prenotazione';

    if (cId)     cId.value     = r?.id || '';
    if (cDate)   cDate.value   = r?.date || fDate?.value || todayISO();
    if (cTime)   cTime.value   = r?.time || '20:00';
    if (cName)   cName.value   = r?.name || '';
    if (cPhone)  cPhone.value  = r?.phone || '';
    if (cPeople) cPeople.value = r?.people ?? 2;
    if (cStatus) cStatus.value = r?.status || 'confirmed';
    if (cNote)   cNote.value   = r?.note || '';

    dlgCreate.showModal();
  }

  on(formCreate, 'submit', async (e) => {
    e.preventDefault();
    if (!cDate || !cTime || !cName || !cPeople || !cStatus || !cNote) return;

    const payload = {
      date:   cDate.value,
      time:   cTime.value,
      name:   cName.value.trim(),
      phone:  (cPhone?.value || '').trim(),
      people: Number(cPeople.value || 1),
      status: cStatus.value,
      note:   cNote.value.trim()
    };

    let resp;
    try{
      if (cId?.value) {
        resp = await fetch(`/api/reservations/${cId.value}`, {
          method:'PATCH',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        });
      } else {
        resp = await fetch('/api/reservations', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        });
      }
    }catch(e){
      toast('Errore rete');
      return;
    }

    if (resp.ok) {
      dlgCreate?.close();
      await loadList();
      toast('Prenotazione salvata');
    } else {
      toast('Errore salvataggio');
    }
  });

  // ---------- DELETE ----------
  function askDelete(id){
    if (!dlgConfirm || !btnConfirmYes) return;
    const t = $('#confirmText');
    if (t) t.textContent = 'Sei sicuro di eliminare questa prenotazione?';
    dlgConfirm.showModal();
    btnConfirmYes.onclick = async () => {
      try{
        const r = await fetch(`/api/reservations/${id}`, { method:'DELETE' });
        dlgConfirm.close();
        r.ok ? (loadList(), toast('Eliminata')) : toast('Errore eliminazione');
      }catch{
        dlgConfirm.close();
        toast('Errore eliminazione');
      }
    };
  }

  // ---------- QUICK STATUS ----------
  async function quickStatus(id, status){
    try{
      const r = await fetch(`/api/reservations/${id}`, {
        method:'PATCH', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ status })
      });
      r.ok ? (loadList(), toast('Aggiornata')) : toast('Errore aggiornamento');
    }catch{
      toast('Errore aggiornamento');
    }
  }

  // ---------- WEEKLY HOURS ----------
  async function openWeekly(){
    if (!dlgWeekly) return;
    try{
      const data = await fetch('/api/weekly-hours').then(r=>r.json());
      $$('.ww').forEach(inp => { inp.value = data[inp.dataset.day] || ''; });
    }catch{}
    dlgWeekly.showModal();
  }

  on($('#formWeekly'), 'submit', async (e)=>{
    e.preventDefault();
    const payload = {};
    $$('.ww').forEach(inp => payload[inp.dataset.day] = inp.value.trim());
    try{
      const r = await fetch('/api/weekly-hours', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      if (r.ok) { dlgWeekly?.close(); toast('Orari salvati'); }
      else toast('Errore salvataggio orari');
    }catch{ toast('Errore salvataggio orari'); }
  });

  // ---------- SPECIAL DAYS ----------
  async function openSpecial(){
    if (!dlgSpecial) return;
    try{
      const items = await fetch('/api/special-days').then(r=>r.json());
      const box = $('#spList'); if (!box) { dlgSpecial.showModal(); return; }
      box.innerHTML = '';
      if (!items.length){ box.textContent = 'Nessun giorno speciale impostato.'; }
      else {
        box.innerHTML = items.map(i => `• ${i.date} → ${i.closed ? 'CHIUSO' : (i.windows||'aperto')}`).join('<br/>');
      }
    }catch{}
    dlgSpecial.showModal();
  }

  on($('#formSpecial'), 'submit', async (e)=>{
    e.preventDefault();
    const payload = {
      date: $('#spDate')?.value,
      closed: $('#spClosed')?.checked || false,
      windows: ($('#spWindows')?.value || '').trim()
    };
    try{
      const r = await fetch('/api/special-days', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      if (r.ok) { dlgSpecial?.close(); toast('Giorno salvato'); }
      else toast('Errore salvataggio giorno');
    }catch{ toast('Errore salvataggio giorno'); }
  });

  on($('#btnSpecialDelete'), 'click', async ()=>{
    try{
      const payload = { date: $('#spDate')?.value };
      const r = await fetch('/api/special-days', {
        method:'DELETE', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      if (r.ok) { dlgSpecial?.close(); toast('Giorno eliminato'); }
      else toast('Errore eliminazione');
    }catch{ toast('Errore eliminazione'); }
  });

  // ---------- STATUS ----------
  async function openStatus(){
    if (!dlgStatus || !statusBox) return;
    let html = '';
    try{
      const weekly = await fetch('/api/weekly-hours').then(r=>r.json());
      const spec   = await fetch('/api/special-days').then(r=>r.json());
      html += `<div class="card" style="background:#0f1722;border:1px solid #223347">
        <b>Orari settimanali</b><br/>`+
        Object.entries(weekly).map(([d, v]) => `• ${d}: ${v || 'CHIUSO'}`).join('<br/>') +
        `<br/><br/><b>Giorni speciali</b><br/>`+
        (spec.length ? spec.map(i => `• ${i.date}: ${i.closed ? 'CHIUSO' : (i.windows||'aperto')}`).join('<br/>') : 'Nessuno')+
      `</div>`;
    }catch{
      html = '<div class="muted">Errore stato.</div>';
    }
    statusBox.innerHTML = html;
    dlgStatus.showModal();
  }

  // ---------- TOPBAR WIRING (se esistono) ----------
  on(btnWeekly,  'click', openWeekly);
  on(btnSpecial, 'click', openSpecial);
  on(btnStatus,  'click', openStatus);

  // Dropdown Azioni
  on(menuBtn, 'click', () => actionsWrap?.classList.toggle('open'));
  on(document, 'click', (e) => {
    if (!actionsWrap) return;
    if (!actionsWrap.contains(e.target)) actionsWrap.classList.remove('open');
  });

  // Toggle tema
  on(themeToggle, 'click', () => {
    const dark = !document.body.classList.contains('theme-dark');
    document.body.classList.toggle('theme-dark', dark);
    try{ localStorage.setItem('theme', dark ? 'dark' : 'light'); }catch{}
  });
  // init tema da localStorage
  try{
    const saved = localStorage.getItem('theme');
    if (saved) document.body.classList.toggle('theme-dark', saved === 'dark');
    else document.body.classList.add('theme-dark');
  }catch{
    document.body.classList.add('theme-dark');
  }

  // ---------- INIT ----------
  loadList();
})();
