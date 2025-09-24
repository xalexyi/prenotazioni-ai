// static/js/dashboard.js
(function () {
  // Esegue solo dopo che il DOM è pronto
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    bootstrap();
  }

  function bootstrap() {
    const rid = getRestaurantId();
    const badge = ensureBadge();
    if (!badge) return;

    async function tick() {
      try {
        const r = await fetch(`/api/public/voice/active/${rid}`, { cache: 'no-store' });
        if (!r.ok) return;
        const data = await r.json();
        if (data && data.ok) badge.set(data.active, data.max);
      } catch (_) {}
    }

    tick();
    setInterval(tick, 5000);
  }

  // Ricava restaurant_id da vari punti. Fallback: 1 (Haru)
  function getRestaurantId() {
    const a = document.body?.dataset?.restaurantId;
    if (a) return Number(a);
    const meta = document.querySelector('meta[name="restaurant-id"]');
    if (meta?.content) return Number(meta.content);
    if (window.__RESTAURANT_ID__) return Number(window.__RESTAURANT_ID__);
    return 1;
  }

  // Crea/aggancia <span id="active-calls">x/y</span> dentro la scritta "Chiamate attive"
  function ensureBadge() {
    // 1) Caso semplice: esiste già
    let el = document.querySelector('#active-calls,[data-active-calls]');
    if (el) {
      return { el, set: (a, m) => { el.textContent = `${a}/${m}`; } };
    }

    // 2) Cerca il contenitore che contiene la dicitura
    const all = Array.from(document.querySelectorAll('div,section,header,span,strong,b,h1,h2,h3,h4,h5,p,li'));
    const container = all.find(n => (n.textContent || '').toLowerCase().includes('chiamate attive'));
    if (!container) return null;

    // 3) Prova a sostituire direttamente "x/y" con lo span
    const injected = injectSpan(container);
    if (injected) {
      el = document.getElementById('active-calls');
      return { el, set: (a, m) => { el.textContent = `${a}/${m}`; } };
    }

    // 4) Se non c'era "x/y" nello stesso nodo, aggiungi uno span subito dopo il testo
    const span = document.createElement('span');
    span.id = 'active-calls';
    span.textContent = '0/3';
    span.style.marginLeft = '4px';
    container.appendChild(span);
    return { el: span, set: (a, m) => { span.textContent = `${a}/${m}`; } };
  }

  // Sostituisce la prima occorrenza "x / y" nel markup con <span id="active-calls">x/y</span>
  function injectSpan(container) {
    // Lavora sulla HTML string del container
    const html = container.innerHTML;
    // Pattern: numero/numero con eventuali spazi
    const re = /(\b[Cc]hiamate\s+[Aa]ttive\s*:\s*)(\d+\s*\/\s*\d+)/;
    if (re.test(html)) {
      container.innerHTML = html.replace(re, (m, prefix, num) => {
        return `${prefix}<span id="active-calls">${num.replace(/\s*/g, '')}</span>`;
      });
      return true;
    }

    // Secondo tentativo: solo "x/y" senza prefisso nello stesso nodo
    const re2 = /(\d+\s*\/\s*\d+)/;
    if (re2.test(html)) {
      container.innerHTML = html.replace(re2, (num) => {
        return `<span id="active-calls">${num.replace(/\s*/g, '')}</span>`;
      });
      return true;
    }
    return false;
  }
})();
