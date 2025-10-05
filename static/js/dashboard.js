// ===== Modali overlay =====
window.openModal = function(id){
  const modal = document.getElementById(id);
  if(!modal) return;
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.dataset.for = id;
  document.body.appendChild(backdrop);
  modal.classList.add('modal');
  backdrop.appendChild(modal);
  backdrop.addEventListener('click', (e) => {
    if (e.target === backdrop) closeModal(id);
  });
  document.body.style.overflow = 'hidden';
};

window.closeModal = function(id){
  const modal = document.getElementById(id);
  const backdrop = document.querySelector(`.modal-backdrop[data-for="${id}"]`);
  if(!modal) return;
  document.body.appendChild(modal);
  modal.classList.remove('modal');
  if (backdrop) backdrop.remove();
  document.body.style.overflow = '';
};

// ===== Azioni filtri/toolbar (wire minimal) =====
document.getElementById('btnClear')?.addEventListener('click', ()=>{
  const d = document.getElementById('flt-date'); if (d) d.value = '';
  const t = document.getElementById('flt-text'); if (t) t.value = '';
});

document.getElementById('btnToday')?.addEventListener('click', ()=>{
  const d = document.getElementById('flt-date');
  if (!d) return;
  const now = new Date(); const yyyy = now.getFullYear();
  const mm = String(now.getMonth()+1).padStart(2,'0');
  const dd = String(now.getDate()).padStart(2,'0');
  d.value = `${yyyy}-${mm}-${dd}`;
});

document.getElementById('btnRefresh')?.addEventListener('click', ()=>{
  showToast('Aggiornato', 'success');
});
