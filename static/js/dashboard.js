function updateEstimatedIncome() {
  fetch('/api/estimated_income')
    .then(res => res.json())
    .then(data => {
      document.querySelector('.stat-card:nth-child(2) .stat-value').textContent = `€ ${data.estimated_income}`;
    });
}

// Quando si salva una nuova prenotazione
document.getElementById('saveReservation').addEventListener('click', function() {
  // ... codice salvataggio ...
  updateEstimatedIncome();
});

// Quando si conferma una prenotazione
document.querySelectorAll('.confirmBtn').forEach(btn => {
  btn.addEventListener('click', () => {
    // ... codice conferma ...
    updateEstimatedIncome();
  });
});
