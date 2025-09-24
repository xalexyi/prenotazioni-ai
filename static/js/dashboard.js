// static/js/dashboard.js

(function () {
  // === Helper: trova il badge "Chiamate attive" e restituisce {el, set(value)} ===
  function findActiveCallsBadge() {
    // 1) Se esiste un id/class esplicito (mettilo se vuoi in futuro)
    let el = document.querySelector('#active-calls,[data-active-calls]');
    if (el) {
      return {
        el,
        set: (active, max) => { el.textContent = `${active}/${max}`; }
      };
    }

    // 2) Fallback robusto: cerca un elemento che contiene la stringa "Chiamate attive"
    //    e prova a trovare il numero vicino
    const tree = document.body;
    const walker = document.createTreeWalker(tree, NodeFilter.SHOW_ELEMENT, null);
    let candidate = null;
    while (walker.nextNode()) {
      const node = walker.currentNode;
      try {
        const txt = (node.innerText || node.textContent || '').toLowerCase();
        if (txt.includes('chiamate attive')) {
          candidate = node;
          break;
        }
      } catch (e) {}
    }
    if (!candidate) return null;

    // prova a trovare uno span con x/y nella stessa card/linea
    let numberEl = candidate.querySelector('span, strong, b, .badge, .pill');
    if (!numberEl) numberEl = candidate;

    return {
      el: numberEl,
      set: (active, max) => {
        const prefix = (candidate.innerText || candidate.textContent || '').split('\n')[0].includes('Chiamate attive')
          ? 'Chiamate attive: ' : '';
        numberEl.textContent = `${active}/${max}`;
        // se serve mostrare "Chiamate attive: x/y" senza toccare markup:
        if (candidate !== numberEl && candidate.firstChild && candidate.firstChild.nodeType === Node.TEXT_NODE) {
          candidate.firstChild.textContent = prefix;
        }
      }
    };
  }

  // === Helper: ricava restaurant_id ===
  function getRestaurantId() {
    // priorità: data-restaurant-id su <body>
    const a = document.body && document.body.dataset && document.body.dataset.restaurantId;
    if (a) return Number(a);
    // meta tag (se esiste)
    const meta = document.querySelector('meta[name="restaurant-id"]');
    if (meta && meta.content) return Number(meta.content);
    // variabile globale (se il template la definisce)
    if (window.__RESTAURANT_ID__) return Number(window.__RESTAURANT_ID__);
    // fallback: 1 (Haru)
    return 1;
  }

  async function fetchActive(rid) {
    const res = await fetch(`/api/public/voice/active/${rid}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  // === bootstrap ===
  const badge = findActiveCallsBadge();
  if (!badge) return; // non siamo nella dashboard o non c'è la card

  const rid = getRestaurantId();

  async function tick() {
    try {
      const data = await fetchActive(rid);
      if (data && data.ok) badge.set(data.active, data.max);
    } catch (e) {
      // silenzioso
    }
  }

  // primo aggiornamento subito, poi ogni 5s
  tick();
  setInterval(tick, 5000);
})();
