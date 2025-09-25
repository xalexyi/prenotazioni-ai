(function () {
  function qs(sel) { return document.querySelector(sel); }

  function setBadgeState(active, max, overload) {
    const elA = qs('#vb-active');
    const elM = qs('#vb-max');
    const dot = qs('#vb-dot');
    const lab = qs('#vb-label');

    if (!elA || !elM || !dot || !lab) return;

    elA.textContent = String(active);
    elM.textContent = String(max);

    // colori/pill
    dot.classList.remove('dot-green', 'dot-yellow', 'dot-red');
    if (overload || active >= max) {
      dot.classList.add('dot-red');
      lab.textContent = 'Linea piena';
    } else if (active >= Math.max(1, max - 1)) {
      dot.classList.add('dot-yellow');
      lab.textContent = 'Quasi piena';
    } else {
      dot.classList.add('dot-green');
      lab.textContent = 'Disponibile';
    }
  }

  async function refreshBadge() {
    const host = window.location.origin;
    const cont = qs('#voice-badge');
    if (!cont) return;
    const rid = cont.getAttribute('data-rid');
    if (!rid) return;

    try {
      const r = await fetch(`${host}/api/public/voice/active/${rid}`, { cache: 'no-store' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const j = await r.json();
      setBadgeState(j.active || 0, j.max || 3, !!j.overload);
    } catch (e) {
      // in errore mostro come "sconosciuto" ma non blocco la pagina
      setBadgeState(0, 3, false);
      // console.warn('voice badge error', e);
    }
  }

  // avvio e polling leggero
  document.addEventListener('DOMContentLoaded', () => {
    refreshBadge();
    // aggiorna ogni 8 secondi
    setInterval(refreshBadge, 8000);
  });
})();
