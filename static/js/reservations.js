/* static/js/reservations.js — completo */
(() => {
  const $  = (s, r=document) => r.querySelector(s);

  // ------- Toast -------
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

  // ------- Helpers -------
  const pad2 = (n)=>String(n).padStart(2,'0');
  const todayISO = ()=>{
    const d = new Date();
    return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`;
  };
  const getRid = ()=> window.RESTAURANT_ID || window.restaurant_id || 1;

  // ------- Admin token -------
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
      let err = { message: `HTTP ${r.status}` };
      try { const j = await r.json(); err = j || err; } catch(_){}
      throw err;
    }
    return r.json();
  }

  // ------- API -------
  async function listReservations(params={}){
    const q = new URLSearchParams();
    q.set('restaurant_id', String(getRid()));
    if (params.date)      q.set('date', params.date);
    if (params.last_days) q.set('last_days', String(params.last_days));
    if (params.q)         q.set('q', params.q);
    return adminFetch(`/reservations?${q.toString()}`);
  }

  // ------- Render -------
  function escapeHtml(s){ return String(s||'').replace(/[&<>"']/g,(c)=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c])); }

  function renderList(items){
    const box = $('#list');
    if(!box) return;
    if(!items || !items.length){
      box.innerHTML = `<div class="muted">Nessuna prenotazione</div>`;
      const k = document.getElementById('kpi-today'); if(k) k.textContent = '0';
      const rev = document.getElementById('kpi-revenue'); if(rev) rev.textContent = '€ 0';
      return;
    }
    items.sort((a,b)=> (a.date+a.time).localeCompare(b.date+b.time));
    const rows = items.map(it=>{
      const time = it.time || '—';
      const name = it.name || '—';
      const phone= it.phone || '—';
      const party= it.party_size ?? '—';
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
      <div class="table">
        <div class="thead">
          <div class="th">Ora</div>
          <div class="th">Nome</div>
          <div class="th">Telefono</div>
          <div class="th">Persone</div>
          <div class="th">Stato</div>
          <div class="th">Note</div>
        </div>
        <div class="tbody">${rows}</div>
      </div>`;
    // KPI oggi simple: count items matching today
    const today = todayISO();
    const k = document.getElementById('kpi-today');
    if(k) k.textContent = String(items.filter(x=>x.date===today).length);
  }

  // ------- Filtri / Bind -------
  async function refreshFromUI(){
    const d = $('#resv-date')?.value || '';
    const q = $('#resv-q')?.value?.trim() || '';
    try{
      const res = await listReservations({ date: d || undefined, q: q || undefined });
      renderList(res.items || []);
    }catch(e){
      console.error(e);
      $('#list').innerHTML = `<div class="err">Errore nel caricamento.</div>`;
      toast(e.message || 'Errore caricamento','err');
    }
  }

  document.getElementById('resv-filter')?.addEventListener('click', refreshFromUI);
  document.getElementById('resv-clear')?.addEventListener('click', async ()=>{
    const q = document.getElementById('resv-q'); if(q) q.value='';
    await refreshFromUI();
  });
  document.getElementById('resv-last30')?.addEventListener('click', async ()=>{
    try{
      const res = await listReservations({ last_days:30 });
      renderList(res.items || []);
    }catch(e){
      console.error(e); toast(e.message || 'Errore caricamento','err');
    }
  });
  document.getElementById('resv-today')?.addEventListener('click', async ()=>{
    if(document.getElementById('resv-date')) document.getElementById('resv-date').value = todayISO();
    try{
      const res = await listReservations({ date: todayISO() });
      renderList(res.items || []);
    }catch(e){
      console.error(e); toast(e.message || 'Errore caricamento','err');
    }
  });
  document.getElementById('resv-refresh')?.addEventListener('click', refreshFromUI);

  (async ()=>{
    try{
      await loadAdminToken();
      await refreshFromUI();
    }catch(e){
      console.warn(e);
      const list = document.getElementById('list');
      if(list) list.innerHTML = `<div class="err">Errore nel caricamento.</div>`;
      toast('admin_token mancante','err');
    }
  })();
})();
