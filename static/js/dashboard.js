(function () {
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));

  const state = {
    all: [],
    filtered: [],
    range: 'today', // today | last30 | all
    timer: null
  };

  // ===== Live clock
  function tickClock() {
    const el = $('#liveClock');
    if (!el) return;
    const d = new Date();
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    el.textContent = `${hh}:${mm}`;
  }
  setInterval(tickClock, 1000);
  tickClock();

  // ===== Fetch helpers
  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(url);
    return r.json();
  }
  async function postJSON(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(url);
    return r.json();
  }

  // ===== Load reservations (with range)
  async function loadReservations() {
    let url = '/api/reservations';
    if (state.range === 'today') url += '?range=today';
    else if (state.range === 'last30') url += '?range=last30';
    // else all

    const data = await getJSON(url);
    state.all = Array.isArray(data) ? data : [];
    applySearch();
    refreshSummaryCards();
    loadAISummary();
  }

  // ===== Apply search filter
  function applySearch() {
    const q = ($('#searchBox')?.value || '').toLowerCase().trim();
    if (!q) {
      state.filtered = [...state.all];
    } else {
      state.filtered = state.all.filter(b => {
        const s = `${b.name} ${b.phone} ${b.date} ${b.time} ${b.status}`.toLowerCase();
        return s.includes(q);
      });
    }
    renderTable();
  }

  // ===== Render reservations table
  function badgeClass(status) {
    const s = (status || '').toLowerCase();
    if (s.includes('confer')) return 'badge badge--ok';
    if (s.includes('att')) return 'badge badge--wait';
    if (s.includes('rifi') || s.includes('canc')) return 'badge badge--ko';
    return 'badge';
  }

  function renderTable() {
    const wrap = $('#reservationsTable');
    if (!wrap) return;
    const list = state.filtered;

    if (!list.length) {
      wrap.innerHTML = `<div class="muted">Nessuna prenotazione</div>`;
      return;
    }

    let html = `
      <div class="tbl">
        <div class="tr th">
          <div>Nome</div><div>Telefono</div><div>Data</div><div>Ora</div><div>Persone</div><div>Stato</div>
        </div>
    `;
    for (const b of list) {
      html += `
        <div class="tr">
          <div><strong>${escapeHTML(b.name || '')}</strong></div>
          <div>${escapeHTML(b.phone || '')}</div>
          <div>${escapeHTML(b.date || '')}</div>
          <div>${escapeHTML(b.time || '')}</div>
          <div>${b.people ?? ''}</div>
          <div><span class="${badgeClass(b.status)}">${escapeHTML(b.status || '')}</span></div>
        </div>
      `;
    }
    html += `</div>`;
    wrap.innerHTML = html;
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }

  // ===== Summary cards
  function refreshSummaryCards() {
    const todayList = state.range === 'today' ? state.filtered : state.filtered.filter(x => isToday(x.date));
    const bookings = todayList.length;
    const people = todayList.reduce((a, b) => a + (parseInt(b.people, 10) || 0), 0);
    // occupancy stimata: supponiamo 6 persone/slot * 10 slot = 60 (esempio)
    const capacity = 60;
    const occ = capacity ? Math.min(100, Math.round((people / capacity) * 100)) : 0;

    $('#sumBookings').textContent = bookings;
    $('#sumPeople').textContent = people;
    $('#sumOcc').textContent = `${occ}%`;
  }

  function isToday(iso) {
    if (!iso) return false;
    // accetta 'YYYY-MM-DD'
    const d = new Date();
    const t = d.toISOString().slice(0, 10);
    return iso === t;
  }

  // ===== AI Summary (backend)
  async function loadAISummary() {
    try {
      const payload = {
        total: state.filtered.length,
        people: state.filtered.reduce((a, b) => a + (parseInt(b.people, 10) || 0), 0),
        confirmed: state.filtered.filter(b => (b.status || '').toLowerCase().includes('confer')).length
      };
      const res = await postJSON('/api/ai/summary', payload);
      $('#aiSummary').textContent = res.summary || '—';
    } catch (e) {
      console.warn('ai/summary', e);
      $('#aiSummary').textContent = '—';
    }
  }

  // ===== Analyze hours (backend)
  $('#btnAnalyzeHours')?.addEventListener('click', async () => {
    try {
      const res = await getJSON('/api/admin/hours/insights');
      $('#hoursInsights').innerHTML = (res?.insights || []).map(li => `• ${escapeHTML(li)}`).join('<br>') || '—';
    } catch (e) {
      console.warn('hours/insights', e);
      $('#hoursInsights').textContent = '—';
    }
  });

  // ===== Search & Tabs
  $('#searchBox')?.addEventListener('input', applySearch);

  $$('.tab').forEach(t => {
    t.addEventListener('click', () => {
      $$('.tab').forEach(x => x.classList.remove('is-active'));
      t.classList.add('is-active');
      state.range = t.dataset.range;
      loadReservations();
    });
  });

  $('#btnToday')?.addEventListener('click', () => {
    state.range = 'today';
    $$('.tab').forEach(x => x.classList.remove('is-active'));
    $('.tab[data-range="today"]').classList.add('is-active');
    loadReservations();
  });

  $('#btnLast30')?.addEventListener('click', () => {
    state.range = 'last30';
    $$('.tab').forEach(x => x.classList.remove('is-active'));
    $('.tab[data-range="last30"]').classList.add('is-active');
    loadReservations();
  });

  $('#btnRefresh')?.addEventListener('click', loadReservations);

  // ===== Export CSV
  $('#btnExport')?.addEventListener('click', () => {
    const rows = state.filtered;
    if (!rows.length) return alert('Niente da esportare');
    const head = ['Nome', 'Telefono', 'Data', 'Ora', 'Persone', 'Stato'];
    const csv = [head.join(',')].concat(
      rows.map(b => [b.name, b.phone, b.date, b.time, b.people, b.status].map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(','))
    ).join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'prenotazioni.csv'; a.click();
    URL.revokeObjectURL(url);
  });

  // ===== Polling quasi realtime
  async function schedulePoll() {
    clearTimeout(state.timer);
    state.timer = setTimeout(async () => {
      try {
        await loadReservations();
      } catch (e) {
        console.warn('poll', e);
      }
      schedulePoll();
    }, 15000); // 15s
  }

  // init
  loadReservations().then(schedulePoll).catch(e => console.error(e));
})();
