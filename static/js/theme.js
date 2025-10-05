(function () {
  const ROOT = document.documentElement;
  const KEY = 'ui.theme';

  function nowTheme() {
    const h = new Date().getHours();
    return (h >= 7 && h < 19) ? 'light' : 'dark';
  }

  function apply(theme) {
    ROOT.setAttribute('data-theme', theme);
  }

  function load() {
    const saved = localStorage.getItem(KEY);
    if (saved === 'light' || saved === 'dark') return saved;
    // auto (giorno/notte) se non hai scelto manualmente
    return nowTheme();
  }

  function save(theme) {
    localStorage.setItem(KEY, theme);
  }

  function toggle() {
    const current = ROOT.getAttribute('data-theme') || 'light';
    const next = current === 'light' ? 'dark' : 'light';
    apply(next);
    save(next);
  }

  // init
  apply(load());
  const btn = document.getElementById('themeToggle');
  if (btn) btn.addEventListener('click', toggle);
})();
