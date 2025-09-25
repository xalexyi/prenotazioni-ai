// static/js/dashboard.js
(function () {
  // ------------- util -------------
  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
  const host = window.location.origin;

  // ------------- badge chiamate -------------
  function setBadgeState(active, max, overload) {
    const a = $('#vb-active'), m = $('#vb-max'), dot = $('#vb-dot'), lab = $('#vb-label');
    if (!a || !m || !dot || !lab) return;
    a.textContent = String(active);
    m.textContent = String(max);
    dot.classList.remove('dot-green', 'dot-yellow', 'dot-red');
    if (overload || active >= max) { dot.classList.add('dot-red'); lab.textContent = 'Linea piena'; }
    else if (active >= Math.max(1, max-1)) { dot.classList.add('dot-yellow'); lab.textContent = 'Quasi piena'; }
    else { dot.classList.add('dot-green'); lab.textContent = 'Disponibile'; }
  }
  async function refreshBadge() {
    const cont = $('#voice-badge'); if (!cont) return;
    const rid = cont.getAttribute('data-rid'); if (!rid) return;
    try {
      const r = await fetch(`${host}/api/public/voice/active/${rid}`, {cache:'no-store'});
      if (!r.ok) throw 0; const j = await r.json();
      setBadgeState(j.active||0, j.max||3, !!j.overload);
    } catch(e) { setBadgeState(0,3,false); }
  }

  // ------------- kebab menu -------------
  function initKebab() {
    const wrap = $('.kebab-wrap');
    const btn = $('#btn-kebab'), menu = $('#kebab-menu');
    if (!btn || !menu) return;

    // stato iniziale
    menu.classList.remove('open');
    menu.hidden = false; // lasciamo gestire visibilità con CSS (.open)
    btn.setAttribute('aria-haspopup','menu');
    btn.setAttribute('aria-expanded','false');

    const show = () => {
      menu.classList.add('open');
      btn.setAttribute('aria-expanded','true');
      btn.classList.add('kebab-active');
    };
    const hide = () => {
      menu.classList.remove('open');
      btn.setAttribute('aria-expanded','false');
      btn.classList.remove('kebab-active');
    };
    const toggle = (e) => {
      e?.stopPropagation();
      if (menu.classList.contains('open')) hide(); else show();
    };

    btn.addEventListener('click', toggle);
    document.addEventListener('click', (e)=>{
      if (!menu.contains(e.target) && e.target !== btn) hide();
    });
    document.addEventListener('keydown', (e)=>{ if (e.key === 'Escape') hide(); });

    // azioni
    menu.querySelectorAll('.k-item').forEach(it => {
      it.addEventListener('click', async () => {
        const act = it.getAttribute('data-act');
        hide();
        if (act==='weekly') openWeekly();
        if (act==='special') openSpecial();
        if (act==='settings') openSettings();
        if (act==='state') openState();
        if (act==='help') openHelp();
      });
    });
  }

  // ------------- modals helpers -------------
  function openModal(id){ const m=$(id); if(m){ m.hidden=false; } }
  function closeModal(el){ el.closest('.modal-backdrop').hidden=true; }
  function initModalClose(){
    $$('.modal .js-close').forEach(b => b.addEventListener('click', ()=> closeModal(b)));
    $$('.modal-backdrop').forEach(b => b.addEventListener('click', (e)=>{
      if(e.target.classList.contains('modal-backdrop')) e.target.hidden=true;
    }));
  }

  // ------------- API helpers -------------
  async function getState(){
    const r = await fetch(`${host}/api/admin/schedule/state`, {credentials:'same-origin'});
    if (!r.ok) throw new Error('state http '+r.status);
    return r.json();
  }
  async function saveWeekly(payload){
    const r = await fetch(`${host}/api/admin/schedule/weekly`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({weekly: payload}), credentials:'same-origin'
    });
    if(!r.ok) throw new Error('weekly http '+r.status);
    return r.json();
  }
  async function saveSettings(data){
    const r = await fetch(`${host}/api/admin/schedule/settings`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(data), credentials:'same-origin'
    });
    if(!r.ok) throw new Error('settings http '+r.status);
    return r.json();
  }
  async function listSpecial(){
    const r = await fetch(`${host}/api/admin/special-days/list`, {credentials:'same-origin'});
    if(!r.ok) throw new Error('special list '+r.status);
    return r.json();
  }
  async function upsertSpecial(date, closed, ranges){
    const body = {date, closed:Boolean(closed)};
    if(!closed) body.ranges = ranges;
    const r = await fetch(`${host}/api/admin/special-days/upsert`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body), credentials:'same-origin'
    });
    if(!r.ok) throw new Error('special upsert '+r.status);
    return r.json();
  }
  async function deleteSpecial(date){
    const r = await fetch(`${host}/api/admin/special-days/delete`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({date}), credentials:'same-origin'
    });
    if(!r.ok) throw new Error('special delete '+r.status);
    return r.json();
  }

  // ------------- WEEKLY UI -------------
  const WD = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica'];
  function renderWeeklyForm(weekly){
    const wrap = $('#weekly-form'); if (!wrap) return;
    wrap.innerHTML='';
    for(let i=0;i<7;i++){
      const row = document.createElement('div'); row.className='w-row';
      const lab = document.createElement('div'); lab.textContent = WD[i];
      const inp = document.createElement('input'); inp.className='input';
      const ranges = (weekly[String(i)]||[]).map(r=>`${r.start}-${r.end}`).join(', ');
      inp.value = ranges;
      inp.setAttribute('data-wd', String(i));
      row.appendChild(lab); row.appendChild(inp);
      wrap.appendChild(row);
    }
  }
  function parseRanges(str){
    const out=[]; if(!str) return out;
    str.split(',').map(s=>s.trim()).filter(Boolean).forEach(p=>{
      const m = p.match(/^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$/); if(m) out.push({start:m[1], end:m[2]});
    });
    return out;
  }

  async function openWeekly(){
    try{
      const st = await getState();
      renderWeeklyForm(st.weekly||{});
      $('#weekly-save').onclick = async ()=>{
        const payload=[];
        $$('#weekly-form input').forEach(inp=>{
          payload.push({weekday: Number(inp.getAttribute('data-wd')), ranges: parseRanges(inp.value)});
        });
        await saveWeekly(payload);
        closeModal($('#weekly-save'));
      };
      openModal('#modal-weekly');
    }catch(e){ alert('Errore caricamento orari'); }
  }

  // ------------- SPECIAL DAYS UI -------------
  async function refreshSpecialList(){
    const box = $('#sp-list'); if (!box) return; box.innerHTML='';
    const items = (await listSpecial()).items || [];
    if(!items.length){ box.innerHTML='<div class="muted">Nessun giorno speciale</div>'; return; }
    items.forEach(it=>{
      const li = document.createElement('div');
      li.className='list-row';
      const rr = it.ranges?.map(r=>`${r.start}-${r.end}`).join(', ');
      li.textContent = `${it.date} — ${it.closed?'CHIUSO':(rr||'')} `;
      box.appendChild(li);
    });
  }
  async function openSpecial(){
    try{
      await refreshSpecialList();
      $('#sp-add').onclick = async ()=>{
        const d = $('#sp-date').value;
        if(!d) return alert('Seleziona la data');
        const closed = $('#sp-closed').checked;
        const ranges = parseRanges($('#sp-ranges').value);
        await upsertSpecial(d, closed, ranges);
        await refreshSpecialList();
      };
      $('#sp-del').onclick = async ()=>{
        const d = $('#sp-date').value;
        if(!d) return alert('Seleziona la data');
        await deleteSpecial(d);
        await refreshSpecialList();
      };
      openModal('#modal-special');
    }catch(e){ alert('Errore giorni speciali'); }
  }

  // ------------- SETTINGS UI -------------
  async function openSettings(){
    try{
      const st = await getState();
      const s = st.settings || {};
      $('#st-step').value = s.slot_step_min ?? 15;
      $('#st-last').value = s.last_order_min ?? 15;
      $('#st-cap').value  = s.capacity_per_slot ?? 6;
      $('#st-minp').value = s.min_party ?? 1;
      $('#st-maxp').value = s.max_party ?? 12;
      $('#st-tz').value   = s.tz || 'Europe/Rome';

      $('#st-save').onclick = async ()=>{
        await saveSettings({
          slot_step_min: Number($('#st-step').value),
          last_order_min: Number($('#st-last').value),
          capacity_per_slot: Number($('#st-cap').value),
          min_party: Number($('#st-minp').value),
          max_party: Number($('#st-maxp').value),
          tz: $('#st-tz').value
        });
        closeModal($('#st-save'));
      };

      openModal('#modal-settings');
    }catch(e){ alert('Errore impostazioni'); }
  }

  // ------------- STATO / HELP -------------
  async function openState(){
    try{
      const st = await getState();
      $('#state-pre').textContent = JSON.stringify(st, null, 2);
      openModal('#modal-state');
    }catch(e){ alert('Errore stato'); }
  }
  function openHelp(){ openModal('#modal-help'); }

  // ------------- init -------------
  document.addEventListener('DOMContentLoaded', ()=>{
    initKebab();
    initModalClose();
    refreshBadge();
    setInterval(refreshBadge, 8000);
  });
})();
