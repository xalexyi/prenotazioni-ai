(function () {
  const root = document.documentElement;
  const btn = document.getElementById("themeToggle");

  function applyTheme(theme) {
    if (!["light", "dark"].includes(theme)) theme = "light";
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch(e) {}
  }

  function toggleTheme() {
    const cur = root.getAttribute("data-theme") || "light";
    applyTheme(cur === "light" ? "dark" : "light");
  }

  document.addEventListener("DOMContentLoaded", () => {
    const saved = (localStorage.getItem("theme") || "light");
    applyTheme(saved);
    if (btn) btn.addEventListener("click", toggleTheme);
  });
})();
