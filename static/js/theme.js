(() => {
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  const root = document.documentElement;
  const current = localStorage.getItem("theme") || "dark";
  root.classList.toggle("theme-light", current === "light");
  root.classList.toggle("theme-dark", current !== "light");
  btn.textContent = current === "light" ? "☀️" : "🌙";
  btn.addEventListener("click", () => {
    const newTheme = root.classList.contains("theme-light") ? "dark" : "light";
    localStorage.setItem("theme", newTheme);
    root.classList.toggle("theme-light");
    root.classList.toggle("theme-dark");
    btn.textContent = newTheme === "light" ? "☀️" : "🌙";
  });
})();
