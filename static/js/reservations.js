/* static/js/reservations.js — completo, in sync con dashboard.js */
(() => {
  const $  = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));

  // ---------- Toast piccolo (riusa barra di dashboard se c'è) ----------
  function toast(msg, type='ok'){
    let bar = document.getElementById('toast-bar');
    if(!bar){
      bar = document.createElement('div');
      bar.id='toast-bar';
      bar.style.position='fixed';
      bar.style.left='50%';
      bar.style.bottom='24px';
      bar.style.transform='translateX(-50%)';
      bar.style.zIndex='9999';
      document.body.appendChild(bar);
    }
    const pill = document.createElement('div');
    pill.textContent = msg;
    pill.style.padding='10px 14px';
    pill.style.borderRadius='999px';
    pill.style.color='#fff';
    pill.style.fontWeight='700';
    pill.style.boxShadow='0 10px 30px rgba(0,0,0,.35)';
    pill.style.marginTop='8px';
    pill.style.background =
      type==='ok'   ? 'linear-gradient(135deg,#16a34a,#059669)' :
      type==='warn' ? 'linear-gradient(135deg,#f59e0b,#d97706)' :
                      'linear-gradient(135deg,#dc2626,#b91c1c)';
    bar.appendChild(pill);
    setTimeout(()=>pill.remove(),2600);
  }

  // ---------- Helpers ----------
  const pad2 = (n)=>String(n).padStart(2,'0');
  function todayISO(){
    const d=new Date();
    return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`;
  }
  function getRid(){ return window.RESTAURANT_ID || window.restaurant_id || 1; }

  // ---------- Admin token via public session (stesso di dashboard.js) ----------
  const SID_KEY='session_id';
  function sid(){
    let s = localStorage.getItem(SID_KEY) || window.SESSION_ID;
    if(!s){ s = Math.random().toString(36).slice(2); localStorage.setItem(SID_KEY, s); }
    return s;
  }
  async function loadPublicSession(){
    const r = await fetch(`/api/public/sessions/${encodeURIComponent(sid())}`, { credentials:'same-origin', cache:'no-store' });
    if(!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }
  async function loadAdminToken(){
    const j = await loadPublicSession();
    const t = j.admin_token || j.token || j.session?.admin_token;
    if(!t) throw new Error('admin_token mancante');
    return t;
  }
  async function adminFetch(path, init={}){
    const headers = new Headers(init.headers || {});
    const token = await loadAdminToken();
    headers.set('X-Admin-Token', token);
    if (!headers.has('Content-Type') && !(init.body instanceof FormData)) headers.set('Content-Type','application/json');
    const r = await fetch(`/api/admin-token${path}`, { ...init, headers, credentials:'same-origin' });
    if(!r.ok){
      let msg = 'HTTP '+r.status;
      try { const j = await r.json(); msg = j.error || msg; } catch {}
      throw new Error(msg);
    }
    return r.json();
  }

  // ---------- API ----------
  async function listReservations(params={}){
    const q = new URLSearchParams();
    q.set('restaurant_id', String(getRid()));
    if (params.today) q.set('today','1');
    if (params.date)  q.set('date', params.date);
    if (params.last_days) q.set('last_days', String(params.last_days));
    if (params.q) q.set('q', params.q);
    return adminFetch(`/reservations?${q.toString()}`);
  }

  // ---------- Render ----------
  function renderList(items){
    const box = $('#list');
    if(!box) return;
    if(!items || !items.length){
      box.innerHTML = `<div class="muted">Nessuna prenotazione</div>`;
      // KPI oggi
      const k = $('#kpi-today'); if(k) k.textContent = '0';
      const rev = $('#kpi-revenue'); if(rev) rev.textContent = '€ 0';
      return;
    }
    // ordina per ora asc
    items.sort((a,b)=>{
      const da=(a.date||'')+(a.time||''); const db=(b.date||'')+(b.time||'');
      return da.localeCompare(db);
    });

    const rows = items.map(it=>{
      const time = it.time || '—';
      const name = it.name || '—';
      const phone= it.phone || '—';
      const party= it.party_size != null ? it.party_size : '—';
      const status = it.status || '—';
      const notes = it.notes ? `<span class="muted">${escapeHtml(it.notes)}</span>` : '';
      return `
        <div class="tr">
          <div class="td mono">${time}</div>
          <div class="td">${escapeHtml(name)}</div>
          <div class="td">${escapeHtml(phone)}</div>
          <div class="td">${party}</div>
          <div class="td"><span class="chip">${escapeHtml(status)}</span></div>
          <div class="td">${notes}</div>
        </div>`;
    }).join('');

    box.innerHTML = `
      <div class="thead tr">
        <div class="th">Ora</div>
        <div class="th">Nome</div>
        <div class="th">Telefono</div>
        <div class="th">Persone</div>
        <div class="th">Stato</div>
        <div class="th">Note</div>
      </div>
      <div class="tbody">
        ${rows}
      </div>
    `;

    // KPI semplici
    const today = todayISO();
    const todayCount = items.filter(x=>x.date===today).length;
    const k = $('#kpi-today'); if(k) k.textContent = String(todayCount);
  }

  function escapeHtml(s){
    return String(s||'').replace(/[&<>"']/g,(c)=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  }

  // ---------- Filtri / Bind ----------
  async function refreshFromUI(){
    const d = $('#resv-date')?.value;
    const q = $('#resv-q')?.value?.trim();
    try{
      const res = await listReservations({ date: d, q });
      renderList(res.items || []);
    }catch(e){
      console.error(e);
      $('#list').innerHTML = `<div class="err">Errore nel caricamento.</div>`;
      toast(e.message || 'Errore caricamento','err');
    }
  }

  $('#resv-filter')?.addEventListener('click', refreshFromUI);

  $('#resv-clear')?.addEventListener('click', async ()=>{
    if($('#resv-q')) $('#resv-q').value='';
    await refreshFromUI();
  });

  $('#resv-last30')?.addEventListener('click', async ()=>{
    try{
      const res = await listReservations({ last_days:30 });
      renderList(res.items || []);
    }catch(e){
      console.error(e); toast(e.message || 'Errore caricamento','err');
    }
  });

  $('#resv-today')?.addEventListener('click', async ()=>{
    if($('#resv-date')) $('#resv-date').value = todayISO();
    try{
      const res = await listReservations({ date: todayISO() });
      renderList(res.items || []);
    }catch(e){
      console.error(e); toast(e.message || 'Errore caricamento','err');
    }
  });

  $('#resv-refresh')?.addEventListener('click', refreshFromUI);

  // auto-carica all’avvio
  (async ()=>{
    try{
      // prova anche a mostrare un hint se manca il token
      await loadAdminToken();
      await refreshFromUI();
    }catch(e){
      console.warn(e);
      $('#list').innerHTML = `<div class="err">Errore nel caricamento.</div>`;
      toast('admin_token mancante','err');
    }
  })();
})();
