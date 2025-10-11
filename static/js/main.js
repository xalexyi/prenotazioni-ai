// Tema persistente
(function themeInit(){
  const root = document.documentElement;
  const key = "ui:theme";
  const saved = localStorage.getItem(key) || "dark";
  if(saved === "light") root.classList.add("light");
  const toggle = document.getElementById("theme-toggle");
  if(toggle){
    toggle.checked = saved === "light";
    toggle.addEventListener("change", ()=>{
      if(toggle.checked){ root.classList.add("light"); localStorage.setItem(key, "light"); }
      else{ root.classList.remove("light"); localStorage.setItem(key, "dark"); }
    });
  }
})();

// Toast helper
window.toast = (msg)=>{
  const el = document.getElementById("toast");
  if(!el) return;
  el.textContent = msg;
  el.classList.add("is-show");
  setTimeout(()=> el.classList.remove("is-show"), 2200);
};

// Switch pannelli
(function sideMenu(){
  const links = [...document.querySelectorAll(".menu__link")];
  const panels = [...document.querySelectorAll(".panel")];
  links.forEach(btn=>{
    btn.addEventListener("click", ()=>{
      links.forEach(b=>b.classList.remove("is-active"));
      btn.classList.add("is-active");
      const id = btn.dataset.section;
      panels.forEach(p=> p.classList.toggle("is-active", p.id === id));
      // Focus di cortesia
      const firstInput = document.querySelector(`#${id} .input`);
      if(firstInput) firstInput.focus({preventScroll:true});
    });
  });
})();
