// static/js/dashboard.js
(function () {
  // === Trova badge da aggiornare ===
  function findBadge() {
    // Caso migliore: hai messo un id o un data-attr
    const direct = document.querySelector('#active-calls,[data-active-calls]');
    if (direct) {
      return {
        el: direct,
        set(active, max) { direct.textContent = `${active}/${max}`; },
      };
    }

    // Fallback: cerca un elemento che contiene "Chiamate attive"
    const all = Array.from(document.querySelectorAll('div,span,strong,b,h1,h2,h3,h4,h5,h6,p'));
    const cand = all.find(n => (n.textContent || '').toLowerCase().includes('chiamate attive'));
    if (!cand) return null;

    // Dentro la card prova a prendere lo span/strong col numero, altrimenti aggiorna in place usando regex x/y
    const numEl = cand.querySelector('span, strong, b, .badge, .pill') || cand;
    return {
      el: numEl,
      set(active, max) {
        // prova a sostituire pattern "x/y"
        const html = numEl.innerHTML;
        if (/\d+\s*\/\s*\d+/.test(html)) {
          numEl.innerHTML = html.replace(/\d+\s*\/\s*\d+/, `${active}/${max}`);
        } else {
          numEl.textContent = `${active}/${max}`;
        }
      },
    };
  }

  // === ID ristorante ===
  function getRestaurantId() {
    const a = document.body?.dataset?.restaurantId;
    if (a) return Number(a);
    const meta = document.querySelector('meta[name="restaurant-id"]');
    if (meta?.content) return Number(meta.content);
    if (window.__RESTAURANT_ID__) return Number(window.__RESTAURANT_ID__);
    return 1; // fallback (Haru)
  }

  async function fetchActive(rid) {
    const r = await fetch(`/api/public/voice/active/${rid}`, { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  const badge = findBadge();
  if (!badge) return; // non siamo nella dashboard o non c'è la card

  const rid = getRestaurantId();

  async function tick() {
    try {
      const data = await fetchActive(rid);
      if (data?.ok) badge.set(data.active, data.max);
    } catch (e) {
      // silenzioso
    }
  }

  tick();
  setInterval(tick, 5000);
})();
