(function () {
  const ROOT = document.documentElement;
  const KEY = 'ui.theme';

  function apply(theme) {
    ROOT.setAttribute('data-theme', theme);
    const icon = document.querySelector('#themeToggle .icon-moon');
    if (icon) icon.style.opacity = theme === 'dark' ? '1' : '0.5';
  }

  function load() {
    const saved = localStorage.getItem(KEY);
    return saved === 'dark' ? 'dark' : 'light';
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
