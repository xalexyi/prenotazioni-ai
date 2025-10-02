/* static/js/dashboard.js — weekly, special days, settings, create reservation */
(() => {
  const $  = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));

  function toast(msg, type='ok'){
    let bar = document.getElementById('toast-bar');
    if(!bar){ bar = document.createElement('div'); bar.id='toast-bar';
      bar.style.position='fixed'; bar.style.left='50%'; bar.style.bottom='24px';
      bar.style.transform='translateX(-50%)'; bar.style.zIndex='9999'; document.body.appendChild(bar); }
    const p = document.createElement('div'); p.textContent = msg;
    p.style.padding='10px 14px'; p.style.color='#fff'; p.style.fontWeight='700';
    p.style.borderRadius='999px'; p.style.marginTop='8px'; p.style.boxShadow='0 10px 30px rgba(0,0,0,.35)';
    p.style.background = type==='ok' ? '#0ea765' : (type==='warn' ? '#d97706' : '#dc2626');
    bar.appendChild(p); setTimeout(()=>p.remove(), 2400);
  }

  const dayNames=["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"];
  const pad2=n=>String(n).padStart(2,'0');
  const todayISO=()=>{const d=new Date();return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`;};
  const isHHMM=s=>/^\d{1,2}:\d{2}$/.test(s);
  const getRid=()=> window.RESTAURANT_ID || window.restaurant_id || 1;

  // ---- token admin via /api/public/sessions/<sid> ----
  const SID_KEY='session_id';
  function sid(){ let s=localStorage.getItem(SID_KEY)||window.SESSION_ID; if(!s){ s=Math.random().toString(36).slice(2); localStorage.setItem(SID_KEY,s);} return s; }
  async function getAdminToken(){
    const r = await fetch(`/api/public/sessions/${encodeURIComponent(sid())}`, { credentials:'same-origin', cache:'no-store' });
    const j = await r.json(); const t = j.admin_token || j.token || j.session?.admin_token;
    if(!t) throw new Error('admin_token mancante'); return t;
  }
  async function adminFetch(path, init={}){
    const headers = new Headers(init.headers||{}); if(!headers.has('Content-Type') && !(init.body instanceof FormData)) headers.set('Content-Type','application/json');
    headers.set('X-Admin-Token', await getAdminToken());
    const r = await fetch(`/api/admin-token${path}`, { ...init, headers, credentials:'same-origin' });
    if(!r.ok){ let e={message:`HTTP ${r.status}`}; try{ e=await r.json(); }catch(_){} throw e; }
    return r.json();
  }

  // ---- API wrappers ----
  async function getState(){ return adminFetch(`/schedule/state?restaurant_id=${getRid()}`); }
  async function saveWeeklyByDay(weekday, ranges){ return adminFetch(`/opening-hours/bulk`, { method:"POST", body: JSON.stringify({ restaurant_id:getRid(), weekday, ranges })}); }
  async function listSpecials(){ return adminFetch(`/special-days/list?restaurant_id=${getRid()}`); }
  async function upsertSpecial(payload){ return adminFetch(`/special-days/upsert`, { method:"POST", body: JSON.stringify({ ...payload, restaurant_id:getRid() }) }); }
  async function deleteSpecial(date){ return adminFetch(`/special-days/delete`, { method:"POST", body: JSON.stringify({ restaurant_id:getRid(), date }) }); }
  async function saveSettings(payload){ return adminFetch(`/settings/update`, { method:"POST", body: JSON.stringify({ ...payload, restaurant_id:getRid() }) }); }
  async function createReservation(payload){ return adminFetch(`/reservations/create`, { method:"POST", body: JSON.stringify({ ...payload, restaurant_id:getRid() }) }); }

  // ---- UI: Weekly ----
  function weeklyCard(dayIndex, ranges){
    const card=document.createElement('div'); card.className='card';
    card.innerHTML=`
      <div class="card-h">
        <strong>${dayNames[dayIndex]}</strong>
        <button class="btn btn-xs btn-outline js-add" data-day="${dayIndex}">+ Fascia</button>
      </div>
      <div class="card-b ranges" data-day="${dayIndex}"></div>`;
    const body = card.querySelector('.ranges');
    (ranges||[]).forEach(r => addRangeRow(body, r.start, r.end));
    return card;
  }
  function addRangeRow(container, start='', end=''){
    const row=document.createElement('div'); row.className='row gap';
    row.innerHTML=`
      <input class="input hhmm js-start" placeholder="HH:MM" value="${start||''}">
      <span>—</span>
      <input class="input hhmm js-end" placeholder="HH:MM" value="${end||''}">
      <button class="btn btn-xs btn-outline js-del">x</button>`;
    row.querySelector('.js-del').addEventListener('click', ()=> row.remove());
    container.appendChild(row);
  }

  async function actionWeekly(){
    const cont=document.getElementById('weekly'); cont.innerHTML='Carico…';
    const st = await getState();
    cont.innerHTML='';
    (st.weekly||[]).forEach((ranges, idx)=> cont.appendChild(weeklyCard(idx, ranges)));
    document.getElementById('weekly-save')?.addEventListener('click', async ()=>{
      try{
        // Salva giorno per giorno (robusto)
        for(const box of $$('.ranges', cont)){
          const wd = Number(box.dataset.day);
          const ranges = $$('.row', box).map(r=>{
            const a=r.querySelector('.js-start').value.trim(); const b=r.querySelector('.js-end').value.trim();
            if(a && b){ if(!isHHMM(a)||!isHHMM(b)) throw new Error(`Formato non valido (${a}-${b})`); return {start:a, end:b}; }
            return null;
          }).filter(Boolean);
          await saveWeeklyByDay(wd, ranges);
        }
        toast('Orari settimanali salvati');
      }catch(e){ toast(e.message||'Errore salvataggio','err'); }
    });
  }

  // ---- UI: Special days ----
  function renderSpecialList(items){
    const cont=document.getElementById('special-list'); cont.innerHTML='';
    if(!items || !items.length){ cont.innerHTML='<div class="muted">Nessun giorno speciale</div>'; return; }
    items.forEach(it=>{
      const li=document.createElement('div'); li.className='list-item';
      const ranges=(it.ranges||[]).map(r=>`${r.start}-${r.end}`).join(', ');
      li.innerHTML=`${it.date} — ${it.closed ? '<strong>CHIUSO</strong>' : (ranges||'aperto') }
        <button class="btn btn-xs js-del" data-date="${it.date}" style="float:right">Elimina</button>`;
      li.querySelector('.js-del').addEventListener('click', async (ev)=>{
        const d=ev.currentTarget.getAttribute('data-date');
        try{ await deleteSpecial(d); toast('Giorno rimosso'); await runSpecial(); }catch(e){ toast(e.message||'Errore','err'); }
      });
      cont.appendChild(li);
    });
  }
  async function runSpecial(){
    const list = await listSpecials(); renderSpecialList(list.items||[]);
    document.getElementById('special-add')?.addEventListener('click', async ()=>{
      const date = document.getElementById('sp-date').value;
      const closed = document.getElementById('sp-closed').checked;
      const ranges = document.getElementById('sp-ranges').value;
      try{
        let payload = { date, is_closed: closed };
        if(!closed){ payload.ranges = (ranges||'').split(',').map(s=>s.trim()).filter(Boolean).map(s=>{
          const m=s.match(/^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$/);
          if(!m) throw new Error(`Intervallo non valido: "${s}"`); return {start:m[1], end:m[2]};
        });}
        await upsertSpecial(payload); toast('Giorno salvato'); await runSpecial();
      }catch(e){ toast(e.message||'Errore','err'); }
    });
  }

  // ---- UI: Settings ----
  async function actionSettings(){
    const tz = document.getElementById('set-tz').value.trim();
    const step = parseInt(document.getElementById('set-step').value||'15',10);
    const last = parseInt(document.getElementById('set-last').value||'15',10);
    const minp = parseInt(document.getElementById('set-min').value||'1',10);
    const maxp = parseInt(document.getElementById('set-max').value||'12',10);
    const cap = parseInt(document.getElementById('set-cap').value||'6',10);
    try{ await saveSettings({ tz, slot_step_min: step, last_order_min:last, min_party:minp, max_party:maxp, capacity_per_slot:cap });
      toast('Impostazioni salvate'); }catch(e){ toast(e.message||'Errore','err'); }
  }

  // ---- UI: Create reservation ----
  async function actionCreate(){
    const date = document.getElementById('cr-date').value;
    const time = document.getElementById('cr-time').value;
    const name = document.getElementById('cr-name').value;
    const phone= document.getElementById('cr-phone').value;
    const party= parseInt(document.getElementById('cr-party').value||'1',10);
    const notes= document.getElementById('cr-notes').value;
    if(!date||!time||!name||!party){ toast('Compila data, ora, nome e persone','warn'); return; }
    try{ await createReservation({ date, time, name, phone, party_size: party, notes, status:'confirmed' });
      toast('Prenotazione creata'); }catch(e){ toast(e.message||'Errore','err'); }
  }

  // ---- Kebab menu routing ----
  document.getElementById('btn-kebab')?.addEventListener('click', ()=>{
    const m = document.getElementById('kebab-menu');
    if(m.hidden){ m.hidden=false; setTimeout(()=>m.classList.add('open'), 0); } else { m.classList.remove('open'); setTimeout(()=>m.hidden=true,120); }
  });
  document.querySelector('[data-act="weekly"]')?.addEventListener('click', actionWeekly);
  document.querySelector('[data-act="special"]')?.addEventListener('click', runSpecial);
  document.querySelector('[data-act="settings"]')?.addEventListener('click', actionSettings);
  document.querySelector('[data-act="state"]')?.addEventListener('click', async ()=>{
    try{ const j = await getState(); console.log('STATE', j); toast('Stato aggiornato (console)'); }catch(e){ toast(e.message||'Errore','err'); }
  });

  // ---- Init ----
  (async ()=>{ try{
    // Precarico token per evitare 401
    await getAdminToken();
  }catch(e){ toast('admin_token mancante','err'); }})();
})();
