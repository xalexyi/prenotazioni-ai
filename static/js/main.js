// static/js/main.js
(function () {
  function _resolveTarget(target) {
    if (!target) return null;
    if (target instanceof Element) return target;
    // prova per id (senza #), poi come selettore
    return document.getElementById(String(target)) || document.querySelector(String(target));
  }

  function _showModal(el) {
    // Coerenza con CSS: usa "hidden"
    el.hidden = false;
    // Retro-compatibilità con vecchio CSS basato su aria-hidden
    el.removeAttribute('aria-hidden');
    // piccolo aiuto per accessibilità
    if (!el.hasAttribute('role')) el.setAttribute('role', 'dialog');
    if (!el.hasAttribute('aria-modal')) el.setAttribute('aria-modal', 'true');
    // focus iniziale
    const focusable = el.querySelector(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    (focusable || el).focus?.();
  }

  function _hideModal(el) {
    el.hidden = true;
    el.setAttribute('aria-hidden', 'true'); // retro-compatibilità
  }

  window.UI = {
    moneyEUR(v) {
      const n = Number(v || 0);
      try {
        return n.toLocaleString('it-IT', {
          style: 'currency',
          currency: 'EUR',
          maximumFractionDigits: 0
        });
      } catch (e) {
        return '€ ' + Math.round(n);
      }
    },

    /**
     * Apri un modal-backdrop.
     * @param {string|Element} target - id senza # (es. 'modal-weekly') oppure selettore (es. '#modal-weekly') o Element
     */
    openModal(target = 'modal') {
      const el = _resolveTarget(target);
      if (el) _showModal(el);
    },

    /**
     * Chiudi un modal-backdrop.
     * @param {string|Element} target - id/selettore/Element
     */
    closeModal(target = 'modal') {
      const el = _resolveTarget(target);
      if (el) _hideModal(el);
    }
  };
})();
