(function () {
  // ===== Helpers
  const $ = (sel, ctx=document) => ctx.querySelector(sel);
  const $$ = (sel, ctx=document) => Array.from(ctx.querySelectorAll(sel));

  // ===== Prenotazioni (placeholder UI rinfresco)
  $('#btnToday')?.addEventListener('click', () => {
    const d = new Date();
    const iso = d.toISOString().slice(0,10);
    $('#dateFilter').value = iso;
    // TODO: richiama lista prenotazioni di oggi
  });

  $('#btnRefresh')?.addEventListener('click', () => {
    // TODO: ricarica tabella prenotazioni
  });

  $('#btnCreateReservation')?.addEventListener('click', () => {
    // qui apriresti la modale di creazione (se ce l’hai separata)
    alert('Apri modale "Crea prenotazione" (non inclusa qui)');
  });

  // ===== Orari settimanali
  const WEEKLY_FIELDS = $('#weekly-fields');
  const DAYS = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica'];

  function renderWeekly(current = {}) {
    WEEKLY_FIELDS.innerHTML = '';
    DAYS.forEach((dayKey, idx) => {
      const key = ['mon','tue','wed','thu','fri','sat','sun'][idx];
      const val = current[key] || '';
      const row = document.createElement('div');
      row.className = 'weekly-row';
      row.innerHTML = `
        <div class="weekly-day">${dayKey}</div>
        <input class="input weekly-input" data-key="${key}" placeholder="12:00-15:00, 19:00-23:30" value="${val}">
      `;
      WEEKLY_FIELDS.appendChild(row);
    });
  }

  // carica valori iniziali (se li hai in pagina via context, mettili su window.INIT_WEEKLY)
  renderWeekly(window.INIT_WEEKLY || {});

  $('#saveWeekly')?.addEventListener('click', async () => {
    const payload = {};
    $$('.weekly-input', WEEKLY_FIELDS).forEach(i => payload[i.dataset.key] = i.value.trim());

    try {
      // 🔁 CAMBIA URL CON IL TUO ENDPOINT
      const res = await fetch('/api/admin/weekly-hours', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Errore salvataggio');
      alert('Orari settimanali salvati');
      $('#weekly-modal')?.classList.remove('is-open');
    } catch (e) {
      console.error(e);
      alert('Errore durante il salvataggio');
    }
  });

  // ===== Giorni speciali
  const list = $('#specials-list');
  function renderSpecials(items = []) {
    list.innerHTML = '';
    if (!items.length) {
      list.innerHTML = '<div class="muted">Nessun giorno speciale impostato.</div>';
      return;
    }
    items.forEach(it => {
      const li = document.createElement('div');
      li.className = 'special-item';
      li.textContent = `${it.date} — ${it.closed ? 'CHIUSO' : it.windows || ''}`;
      list.appendChild(li);
    });
  }
  renderSpecials(window.INIT_SPECIALS || []);

  $('#saveSpecial')?.addEventListener('click', async () => {
    const payload = {
      date: $('#specialDate').value || '',
      closed: $('#specialClosed').checked,
      windows: $('#specialWindows').value.trim()
    };
    if (!payload.date) { alert('Seleziona una data'); return; }

    try {
      // 🔁 CAMBIA URL CON IL TUO ENDPOINT
      const res = await fetch('/api/admin/special-day', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Errore salvataggio');
      alert('Giorno speciale salvato');
      $('#specials-modal')?.classList.remove('is-open');
      // TODO: ricarica elenco
    } catch (e) {
      console.error(e);
      alert('Errore durante il salvataggio');
    }
  });

  $('#deleteSpecial')?.addEventListener('click', async () => {
    const d = $('#specialDate').value;
    if (!d) { alert('Seleziona la data da eliminare'); return; }
    if (!confirm(`Eliminare giorno speciale ${d}?`)) return;

    try {
      // 🔁 CAMBIA URL CON IL TUO ENDPOINT
      const res = await fetch(`/api/admin/special-day/${encodeURIComponent(d)}`, { method:'DELETE' });
      if (!res.ok) throw new Error('Errore eliminazione');
      alert('Giorno speciale eliminato');
      $('#specials-modal')?.classList.remove('is-open');
      // TODO: ricarica elenco
    } catch (e) {
      console.error(e);
      alert('Errore durante l\'eliminazione');
    }
  });

  // ===== Impostazioni
  $('#saveSettings')?.addEventListener('click', async () => {
    const payload = {
      timezone: $('#tz').value.trim(),
      step_min: parseInt($('#stepMin').value,10) || 15,
      last_order_min: parseInt($('#lastOrder').value,10) || 15,
      min_people: parseInt($('#minPeople').value,10) || 1,
      max_people: parseInt($('#maxPeople').value,10) || 12,
      slot_capacity: parseInt($('#slotCapacity').value,10) || 6,
    };
    try {
      // 🔁 CAMBIA URL CON IL TUO ENDPOINT
      const res = await fetch('/api/admin/settings', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Errore salvataggio');
      alert('Impostazioni salvate');
      $('#settings-modal')?.classList.remove('is-open');
    } catch (e) {
      console.error(e);
      alert('Errore durante il salvataggio');
    }
  });

  // ===== Token
  $('#saveToken')?.addEventListener('click', () => {
    const t = $('#tokenField').value.trim();
    if (!t) return;
    localStorage.setItem('api.token', t);
    alert('Token salvato ✅');
    $('#token-modal')?.classList.remove('is-open');
  });

})();
