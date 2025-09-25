// static/js/theme.js
(function () {
  const root = document.documentElement;

  function applyTheme(theme) {
    if (!["light", "dark"].includes(theme)) theme = "light";
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch(e) {}
    const btn = document.getElementById("themeToggle");
    if (btn) btn.setAttribute("aria-pressed", theme === "dark");
  }

  function toggleTheme() {
    const cur = root.getAttribute("data-theme") || "light";
    applyTheme(cur === "light" ? "dark" : "light");
  }

  document.addEventListener("DOMContentLoaded", () => {
    let saved = null;
    try { saved = localStorage.getItem("theme"); } catch(e) {}
    if (!saved) {
      // fallback alla preferenza di sistema
      saved = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    applyTheme(saved);

    const btn = document.getElementById("themeToggle");
    if (btn) btn.addEventListener("click", toggleTheme);
  });
})();
