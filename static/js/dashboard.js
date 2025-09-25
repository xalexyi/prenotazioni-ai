// static/js/dashboard.js
(function () {
  const rid = window.RESTAURANT_ID;
  const maxDefault = Number(window.ACTIVE_MAX || 3);

  const countEl = document.getElementById('activeCallsCount');
  const maxEl   = document.getElementById('activeCallsMax');
  const dotEl   = document.getElementById('availabilityDot');
  const labelEl = document.getElementById('availabilityLabel');

  if (maxEl) maxEl.textContent = String(maxDefault);

  async function refreshActive() {
    try {
      const res = await fetch(`/api/public/voice/active/${rid}`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json(); // { ok:true, active:N, max:3 }
      const active = Number(data.active || 0);
      const mx = Number(data.max || maxDefault);

      if (countEl) countEl.textContent = String(active);
      if (maxEl)   maxEl.textContent   = String(mx);

      const overload = active >= mx;

      if (dotEl) {
        dotEl.style.background = overload ? '#e74c3c' : '#2ecc71';
      }
      if (labelEl) {
        labelEl.textContent = overload ? 'Occupato' : 'Disponibile';
        labelEl.style.color = overload ? '#f2c1bc' : '#bfead0';
      }
    } catch (err) {
      if (dotEl) dotEl.style.background = '#7f8c8d';
      if (labelEl) labelEl.textContent = 'N/D';
      console.warn('refreshActive failed', err);
    }
  }

  refreshActive();
  setInterval(refreshActive, 5000);
})();
