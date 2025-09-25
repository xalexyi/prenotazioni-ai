(function () {
  // ---------------- util ----------------
  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
  const host = window.location.origin;

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

  // ---------------- API ----------------
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
    return r.json(); // [{id,name,price}]
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

  // ---------------- state ----------------
  const State = {
    params: { date: $('#f-date')?.value || '', q: '', range: '' },
    menuMap: new Map(),   // pizzaId -> {name, price}
    items: []             // prenotazioni correnti
  };

  // ---------------- KPI ----------------
  function computeKPIs(){
    // Prenotazioni oggi
    const today = $('#f-date')?.value || '';
    let countToday = 0;
    let pizzas = 0;
    let revenue = 0;

    const isPizzeria = !!window.IS_PIZZERIA;

    State.items.forEach(res=>{
      if (today && res.date === today) countToday++;
      // Pizze ordinate + ricavi (solo pizzeria)
      if (isPizzeria && Array.isArray(res.pizzas)) {
        res.pizzas.forEach(p=>{
          const qty = Number(p.qty||0);
          pizzas += qty;
          const m = State.menuMap.get(p.id);
          if (m && m.price != null) revenue += qty * Number(m.price||0);
        });
      }
    });

    const kToday = $('#kpi-today');
    if (kToday) kToday.textContent = String(countToday);

    const kPizzas = $('#kpi-pizzas');
    if (kPizzas) kPizzas.textContent = String(pizzas);

    const kRevenue = $('#kpi-revenue');
    if (kRevenue) kRevenue.textContent = fmtEuro(revenue);
  }

  // ---------------- UI: render list ----------------
  function renderList(){
    const box = $('#list');
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
      const row = el('div','list-row');

      const left = el('div','lr-left');
      const name = el('div','lr-title', `${res.customer_name || '—'}`);
      const sub = el('div','lr-sub', `${res.phone || ''}`);
      left.appendChild(name);
      left.appendChild(sub);

      const mid = el('div','lr-mid');
      mid.appendChild(el('div','badge', `${res.date || ''}`));
      mid.appendChild(el('div','badge', `${res.time || ''}`));
      mid.appendChild(el('div','badge', `${res.people || 2} px`));

      // status
      const status = String(res.status||'pending');
      const st = el('div','lr-status');
      const stSpan = el('span','tag ' + (
        status === 'confirmed' ? 'tag-green' :
        status === 'rejected' ? 'tag-red' : 'tag-gray'
      ), status);
      st.appendChild(stSpan);

      // pizzas summary (se presente)
      const pWrap = el('div','lr-extra');
      if (Array.isArray(res.pizzas) && res.pizzas.length){
        const txt = res.pizzas.map(p=>{
          const n = State.menuMap.get(p.id)?.name || p.name || 'Pizza';
          return `${n} ×${p.qty}`;
        }).join(' · ');
        pWrap.textContent = txt;
      }

      const right = el('div','lr-right');
      const bConf = el('button','btn btn-xs btn-green','Conferma');
      const bRej  = el('button','btn btn-xs btn-yellow','Rifiuta');
      const bDel  = el('button','btn btn-xs btn-outline','Elimina');

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

      right.appendChild(bConf);
      right.appendChild(bRej);
      right.appendChild(bDel);

      row.appendChild(left);
      row.appendChild(mid);
      row.appendChild(st);
      if (pWrap.textContent) row.appendChild(pWrap);
      row.appendChild(right);

      box.appendChild(row);
    });

    computeKPIs();
  }

  // ---------------- load & reload ----------------
  async function ensureMenu(){
    if (State.menuMap.size) return;
    try{
      const menu = await apiMenu(); // [{id,name,price}]
      menu.forEach(p => State.menuMap.set(p.id, {name:p.name, price:p.price}));
    }catch(e){
      // se fallisce, continuiamo senza prezzi
      State.menuMap.clear();
    }
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

  // ---------------- filters ----------------
  function initFilters(){
    const fDate = $('#f-date');
    const fText = $('#f-text');
    const bFilter = $('#btn-filter');
    const bClear = $('#btn-clear');
    const b30 = $('#btn-30');
    const bToday = $('#btn-today');
    const bNew = $('#btn-new');

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
        if (fDate) fDate.value = '';
        if (fText) fText.value = '';
        State.params = { date:'', q:'', range:'' };
        await reload();
      });
    }

    if (b30){
      b30.addEventListener('click', async ()=>{
        State.params = { date:'', q:'', range:'30days' };
        if (fDate) fDate.value = '';
        if (fText) fText.value = '';
        await reload();
      });
    }

    if (bToday){
      bToday.addEventListener('click', async ()=>{
        State.params = { date:'', q:'', range:'today' };
        await reload();
      });
    }

    if (bNew){
      bNew.addEventListener('click', async ()=>{
        // Modal “nuova prenotazione” non è nel template: uso prompt snello.
        try{
          const name = prompt('Nome cliente?'); if(!name) return;
          const phone = prompt('Telefono?') || '';
          const date = prompt('Data (YYYY-MM-DD)?'); if(!date) return;
          const time = prompt('Ora (HH:MM)?'); if(!time) return;
          const people = Number(prompt('Persone?') || '2') || 2;

          // opzionale: se pizzeria, chiedi pizze in formato id:qty,id:qty
          let pizzas = [];
          if (window.IS_PIZZERIA) {
            await ensureMenu();
            const guide = Array.from(State.menuMap.entries()).map(([id, m])=>`${id}=${m.name}`).join(' | ');
            const raw = prompt('Pizze (formato id:qty,id:qty). Disponibili: '+guide+'\nLascia vuoto per nessuna.');
            if (raw){
              pizzas = raw.split(',').map(s=>s.trim()).filter(Boolean).map(pair=>{
                const [pid, q] = pair.split(':').map(x=>x.trim());
                return { pizza_id: Number(pid), qty: Number(q||1) };
              }).filter(x => x.pizza_id && x.qty>0);
            }
          }

          await apiCreateReservation({
            customer_name: name,
            phone, date, time, people,
            pizzas
          });
          await reload();
        }catch(e){
          alert('Errore creazione prenotazione');
        }
      });
    }
  }

  // ---------------- init ----------------
  document.addEventListener('DOMContentLoaded', async ()=>{
    try{
      initFilters();
      await reload();
    }catch(e){
      // fallback UI
      const list = $('#list');
      if (list) list.innerHTML = '<div class="muted">Errore nel caricamento.</div>';
    }
  });
})();
