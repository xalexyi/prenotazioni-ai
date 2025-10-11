// ========= Tema =========
function setupThemeToggle() {
  const root = document.documentElement;
  const saved = localStorage.getItem("theme") || "dark";
  root.setAttribute("data-theme", saved);
  const toggle = document.getElementById("theme-toggle");
  if (toggle) toggle.checked = saved === "light";
  toggle?.addEventListener("change", () => {
    const next = toggle.checked ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  });
}

// ========= Utils UI =========
function toast(msg, ok=true) {
  const box = document.getElementById("toasts");
  const el = document.createElement("div");
  el.className = `toast ${ok ? "ok":"err"}`;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(()=> el.remove(), 2600);
}

function openModal({title, bodyHTML, actions=[]}) {
  const bd = document.querySelector('.modal-backdrop[data-modal="generic"]');
  bd.hidden = false;
  document.getElementById("modal-title").textContent = title || "";
  const body = document.getElementById("modal-body");
  const acts = document.getElementById("modal-actions");
  body.innerHTML = bodyHTML || "";
  acts.innerHTML = "";
  actions.forEach(a=>{
    const b = document.createElement("button");
    b.className = `btn ${a.variant || ""}`;
    b.textContent = a.label;
    b.addEventListener("click", () => a.onClick?.(bd));
    acts.appendChild(b);
  });
  document.querySelector('[data-modal-close="generic"]').onclick = ()=> bd.hidden = true;
  return bd;
}

function formatDateYMD(d){ // Date -> 'YYYY-MM-DD'
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,'0');
  const day = String(d.getDate()).padStart(2,'0');
  return `${y}-${m}-${day}`;
}
function formatDateIT(d){ // 'sab 11/10/2025'
  const opts = {weekday:'short', day:'2-digit', month:'2-digit', year:'numeric'};
  return d.toLocaleDateString('it-IT', opts);
}
function parseYMD(s){ // 'YYYY-MM-DD' -> Date locale safe
  const [y,m,d] = (s||"").split("-").map(Number);
  if(!y||!m||!d) return null;
  const dt = new Date(Date.UTC(y, m-1, d));
  return new Date(dt.getUTCFullYear(), dt.getUTCMonth(), dt.getUTCDate());
}

// ========= Navigazione sezioni (sidebar) =========
function setupSections() {
  const links = document.querySelectorAll(".nav-link");
  const sections = document.querySelectorAll(".section");
  links.forEach(btn=>{
    btn.addEventListener("click", ()=>{
      links.forEach(b=>b.classList.remove("active"));
      btn.classList.add("active");
      const id = btn.getAttribute("data-section");
      sections.forEach(s=> s.classList.toggle("is-visible", s.id === id));
    });
  });
}
