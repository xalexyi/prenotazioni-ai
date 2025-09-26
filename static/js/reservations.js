/* Prenotazioni: lista, filtri e azioni
   - Compat con ID vecchi/nuovi (resv-*)
   - KPI aggiornati
*/
(function () {
  // ---------- util ----------
  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
  const host = window.location.origin;

  // compat: primo selettore che esiste
  function firstSel(...sels){ for(const s of sels){ const n=$(s); if(n) return n; } return null; }

  function fmtEuro(n){
    try{
      return (n || 0).toLocaleString('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
    }catch(e){ return "€ " + Math.round(n||0); }
  }
  function el(tag, cls, text){
    const x = document.createElement(tag);
    if (cls) x.className = cls;
    if (text != null) x.textContent = text;
    return x;
  }

  // ---------- API ----------
  async function apiList(params = {}){
    const u = new URL(`${host}/api/reservations`);
    Object.entries(params).forEach(([k,v])=>{
      if (v != null && v !== '') u.searchParams.set(k, v);
    });
    const r = await fetch(u.toString(), { credentials:'same-origin' });
    if(!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }
  async function apiMenu(){
    const r = await fetch(`${host}/api/menu`, { credentials:'same-origin' });
    if(!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }
  async function apiUpdateReservation(id, status){
    const r = await fetch(`${host}/api/reservations/${id}`, {
      method:'PATCH',
      headers:{'Content-Type':'application/json'},
      credentials:'same-origin',
      body: JSON.stringify({status})
    });
    if(!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }
  async function apiDeleteReservation(id){
    const r = await fetch(`${host}/api/reservations/${id}`, {
      method:'DELETE',
      credentials:'same-origin'
    });
    if(!r.ok && r.status !== 204) throw new Error('HTTP '+r.status);
    return true;
  }
  async function apiCreateReservation(payload){
    const r = await fetch(`${host}/api/reservations`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'same-origin',
      body: JSON.stringify(payload)
    });
    if(!r.ok){
      const j = await r.json().catch(()=>({}));
      throw new Error(j.error || ('HTTP '+r.status));
    }
    return r.json();
  }

  // ---------- state ----------
  const State = {
    params: { date: '', q: '', range: '' },
    menuMap: new Map(),
    items: []
  };

  // ---------- KPI ----------
  function computeKPIs(){
    const today = firstSel('#resv-date', '#f-date')?.value || '';
    let countToday = 0, pizzas = 0, revenue = 0;
    const isPizzeria = !!window.IS_PIZZERIA;

    State.items.forEach(res=>{
      if (today && res.date === today) countToday++;
      if (isPizzeria && Array.isArray(res.pizzas)) {
        res.pizzas.forEach(p=>{
          const qty = Number(p.qty||0);
          pizzas += qty;
          const m = State.menuMap.get(p.id) || State.menuMap.get(p.pizza_id);
          if (m && m.price != null) revenue += qty * Number(m.price||0);
        });
      }
    });

    const kToday = $('#kpi-today'); if (kToday) kToday.textContent = String(countToday);
    const kPizzas = $('#kpi-pizzas'); if (kPizzas) kPizzas.textContent = String(pizzas);
    const kRevenue = $('#kpi-revenue'); if (kRevenue) kRevenue.textContent = fmtEuro(revenue);
  }

  // ---------- render ----------
  function renderList(){
    const box = firstSel('#resv-table', '#list');
    if (!box) return;
    box.innerHTML = '';

    if (!State.items.length){
      const empty = el('div','muted','Nessuna prenotazione trovata.');
      empty.style.padding = '12px';
      box.appendChild(empty);
      computeKPIs();
      return;
    }

    State.items.forEach(res=>{
      const row = el('div','reservation-row');

      const left = el('div','res-left');
      const name = el('div','res-name', res.customer_name || '—');
      const sub = el('div','res-meta', res.phone || '');
      left.appendChild(name); left.appendChild(sub);

      const mid = el('div','res-meta');
      mid.appendChild(el('span','pill', res.date || ''));
      mid.appendChild(document.createTextNode(' '));
      mid.appendChild(el('span','pill', res.time || ''));
      mid.appendChild(document.createTextNode(' '));
      mid.appendChild(el('span','pill people', (res.people || 2)+' px'));

      const status = String(res.status||'pending');
      const st = el('div','res-meta');
      const stSpan = el('span','badge ' + (
        status === 'confirmed' ? 'badge-green' :
        status === 'rejected' ? 'badge-red' : 'badge-gray'
      ), status.toUpperCase());
      st.appendChild(stSpan);

      const right = el('div','res-actions');
      const bConf = el('button','btn btn-outline','Conferma');
      const bRej  = el('button','btn btn-gray','Rifiuta');
      const bDel  = el('button','btn btn-red','Elimina');

      bConf.addEventListener('click', async ()=>{
        try{ await apiUpdateReservation(res.id,'confirmed'); await reload(); }catch(e){ alert('Errore aggiornamento'); }
      });
      bRej.addEventListener('click', async ()=>{
        try{ await apiUpdateReservation(res.id,'rejected'); await reload(); }catch(e){ alert('Errore aggiornamento'); }
      });
      bDel.addEventListener('click', async ()=>{
        if(!confirm('Eliminare la prenotazione?')) return;
        try{ await apiDeleteReservation(res.id); await reload(); }catch(e){ alert('Errore eliminazione'); }
      });

      right.appendChild(bConf); right.appendChild(bRej); right.appendChild(bDel);

      row.appendChild(left);
      row.appendChild(mid);
      row.appendChild(st);
      row.appendChild(right);

      box.appendChild(row);
    });

    computeKPIs();
  }

  // ---------- load ----------
  async function ensureMenu(){
    if (State.menuMap.size) return;
    try{
      const menu = await apiMenu();
      menu.forEach(p => State.menuMap.set(p.id, {name:p.name, price:p.price}));
    }catch{ State.menuMap.clear(); }
  }
  async function reload(){
    await ensureMenu();
    const params = {};
    if (State.params.date) params.date = State.params.date;
    if (State.params.q) params.q = State.params.q;
    if (State.params.range) params.range = State.params.range;
    const items = await apiList(params);
    State.items = Array.isArray(items) ? items : [];
    renderList();
  }

  // ---------- filters ----------
  function initFilters(){
    const fDate   = firstSel('#resv-date', '#f-date');
    const fText   = firstSel('#resv-search', '#f-text');
    const bFilter = firstSel('#resv-filter', '#btn-filter');
    const bClear  = firstSel('#resv-clear',  '#btn-clear');
    const b30     = firstSel('#resv-last30', '#btn-30');
    const bToday  = firstSel('#resv-today',  '#btn-today');
    const bRefresh= firstSel('#resv-refresh', '#btn-refresh');

    if (bFilter){
      bFilter.addEventListener('click', async ()=>{
        State.params = {
          date: fDate?.value || '',
          q: fText?.value || '',
          range: ''
        };
        await reload();
      });
    }
    if (bClear){
      bClear.addEventListener('click', async ()=>{
        if (fDate) fDate.value = (fDate.type==='date' ? '' : '');
        if (fText) fText.value = '';
        State.params = { date:'', q:'', range:'' };
        await reload();
      });
    }
    if (b30){
      b30.addEventListener('click', async ()=>{
        if (fDate) fDate.value = '';
        if (fText) fText.value = '';
        State.params = { date:'', q:'', range:'30days' };
        await reload();
      });
    }
    if (bToday){
      bToday.addEventListener('click', async ()=>{
        State.params = { date:'', q:'', range:'today' };
        await reload();
      });
    }
    if (bRefresh){
      bRefresh.addEventListener('click', reload);
    }
  }

  // ---------- init ----------
  document.addEventListener('DOMContentLoaded', async ()=>{
    try{
      initFilters();
      // inizializza date dal campo pagina se presente
      const d = firstSel('#resv-date', '#f-date'); State.params.date = d?.value || '';
      await reload();
    }catch{
      const list = firstSel('#resv-table', '#list');
      if (list) list.innerHTML = '<div class="muted">Errore nel caricamento.</div>';
    }
  });
})();
