// File di utilità per evitare errori quando gli elementi non esistono (es. ristorante senza pizza).

function safelySetText(selector, value) {
  const el = document.querySelector(selector);
  if (el) el.textContent = value;
}

/** Aggiorna l'incasso stimato, se il widget esiste */
function updateEstimatedIncome() {
  fetch('/api/estimated_income')
    .then(res => res.ok ? res.json() : { estimated_income: 0 })
    .then(data => {
      const v = (data && typeof data.estimated_income !== 'undefined') ? data.estimated_income : 0;
      safelySetText('#kpi-revenue', `€ ${v}`);
    })
    .catch(() => safelySetText('#kpi-revenue', '€ 0'));
}

// Esempi: chiama in punti chiave, ma proteggi sempre gli accessi DOM
document.addEventListener('click', (e) => {
  if (e.target && e.target.id === 'modalSave') {
    // ... qui il tuo salvataggio ...
    updateEstimatedIncome();
  }
});

// Se la card "Pizze ordinate" non esiste (ristorante non pizzeria) questo non fa nulla.
function updatePizzasCount(v) {
  safelySetText('#kpi-pizzas', v);
}
