/* static/js/reservations.js — lista/filtri prenotazioni */
(() => {
  const $  = (s, r=document) => r.querySelector(s);

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

  const pad2 = n => String(n).padStart(2,'0');
  const todayISO = () => { const d=new Date(); return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`; };
  const getRid = ()=> window.RESTAURANT_ID || window.restaurant_id || 1;

  const SID_KEY='session_id';
  function sid(){ let s = localStorage.getItem(SID_KEY) || window.SESSION_ID;
    if(!s){ s=Math.random().toString(36).slice(2); localStorage.setItem(SID_KEY,s); } return s; }
  async function getAdminToken(){
    const r = await fetch(`/api/public/sessions/${encodeURIComponent(sid())}`, { credentials:'same-origin', cache:'no-store' });
    const j = await r.json();
    const t = j.admin_token || j.token || j.session?.admin_token;
    if(!t) throw new Error('admin_token mancante'); return t;
  }
  async function adminFetch(path, init={}){
    const headers = new Headers(init.headers || {}); headers.set('Content-Type','application/json');
    headers.set('X-Admin-Token', await getAdminToken());
    const r = await fetch(`/api/admin-token${path}`, { ...init, headers, credentials:'same-origin' });
    if(!r.ok){ let err={message:`HTTP ${r.status}`}; try{ err=await r.json(); }catch(_){}
      throw err; }
    return r.json();
  }

  async function listReservations(params={}){
    const q = new URLSearchParams(); q.set('restaurant_id', String(getRid()));
    if (params.date)      q.set('date', params.date);
    if (params.last_days) q.set('last_days', String(params.last_days));
    if (params.q)         q.set('q', params.q);
    return adminFetch(`/reservations?${q.toString()}`);
  }

  function escapeHtml(s){ return String(s||'').replace(/[&<>"']/g,c=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c])); }

  function renderList(items){
    const box = $('#list'); if(!box) return;
    if(!items || !items.length){ box.innerHTML = `<div class="muted">Nessuna prenotazione</div>`; return; }
    items.sort((a,b)=> (a.date+a.time).localeCompare(b.date+b.time));
    const rows = items.map(it=>`
      <div class="tr">
        <div class="td mono">${escapeHtml(it.time)}</div>
        <div class="td">${escapeHtml(it.name)}</div>
        <div class="td">${escapeHtml(it.phone||'')}</div>
        <div class="td">${it.party_size||it.people||''}</div>
        <div class="td"><span class="chip">${escapeHtml(it.status||'confirmed')}</span></div>
        <div class="td">${escapeHtml(it.notes||'')}</div>
      </div>`).join('');
    box.innerHTML = `
      <div class="table">
        <div class="thead">
          <div class="th">Ora</div><div class="th">Nome</div><div class="th">Telefono</div>
          <div class="th">Persone</div><div class="th">Stato</div><div class="th">Note</div>
        </div>
        <div class="tbody">${rows}</div>
      </div>`;
  }

  async function refreshFromUI(){
    const d = document.getElementById('resv-date')?.value || '';
    const q = document.getElementById('resv-q')?.value?.trim() || '';
    try{
      const res = await listReservations({ date: d || undefined, q: q || undefined });
      renderList(res.items || []);
    }catch(e){ console.error(e); toast(e.message || 'Errore caricamento','err'); }
  }

  document.getElementById('resv-filter')?.addEventListener('click', refreshFromUI);
  document.getElementById('resv-clear')?.addEventListener('click', async ()=>{
    const q = document.getElementById('resv-q'); if(q) q.value=''; await refreshFromUI();
  });
  document.getElementById('resv-last30')?.addEventListener('click', async ()=>{
    try{ const r = await listReservations({ last_days:30 }); renderList(r.items||[]); }catch(e){ toast(e.message||'Errore','err'); }
  });
  document.getElementById('resv-today')?.addEventListener('click', async ()=>{
    const t = todayISO(); const d = document.getElementById('resv-date'); if(d) d.value=t;
    try{ const r = await listReservations({ date:t }); renderList(r.items||[]); }catch(e){ toast(e.message||'Errore','err'); }
  });
  document.getElementById('resv-refresh')?.addEventListener('click', refreshFromUI);

  (async ()=>{ try{ await getAdminToken(); await refreshFromUI(); }catch(e){ toast('admin_token mancante','err'); } })();
})();
