// Toggle menu 3 puntini + chiusura quando clicchi fuori
document.addEventListener('click', (e) => {
  const toggle = e.target.closest('[data-menu-toggle]');
  document.querySelectorAll('.menu').forEach(m => {
    if (!m.contains(e.target) && !toggle) m.classList.add('hidden');
  });
  if (toggle) {
    const menu = document.querySelector(toggle.dataset.menuToggle);
    if (menu) menu.classList.toggle('hidden');
  }
});

// Toast
window.showToast = function(msg, type=''){
  const el = document.getElementById('toast');
  if (!el) return;
  el.className = 'toast' + (type ? ' ' + type : '');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add('hidden'), 2200);
};
