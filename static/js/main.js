// Dropdown 3 puntini (apre sotto il bottone)
(function () {
  const btn = document.getElementById('kebabBtn');
  const menu = document.getElementById('kebabMenu');

  if (!btn || !menu) return;

  function close() {
    menu.classList.remove('is-open');
    btn.setAttribute('aria-expanded', 'false');
  }

  function open() {
    // Posiziona sotto il bottone
    const r = btn.getBoundingClientRect();
    menu.style.minWidth = r.width + 'px';
    menu.style.left = r.left + 'px';
    menu.style.top = r.bottom + 6 + 'px';
    menu.classList.add('is-open');
    btn.setAttribute('aria-expanded', 'true');
  }

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (menu.classList.contains('is-open')) close();
    else open();
  });

  document.addEventListener('click', (e) => {
    if (!menu.contains(e.target) && e.target !== btn) close();
  });

  // Apri modali dai comandi della tendina
  menu.querySelectorAll('[data-open]').forEach(el => {
    el.addEventListener('click', () => {
      const id = el.getAttribute('data-open');
      const modal = document.getElementById(id);
      if (modal) {
        modal.classList.add('is-open');
        close();
      }
    });
  });

  // Chiudi modali
  document.querySelectorAll('.modal [data-close], .modal .modal__close').forEach(x => {
    x.addEventListener('click', () => x.closest('.modal').classList.remove('is-open'));
  });
})();
