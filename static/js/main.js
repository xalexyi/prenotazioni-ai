// tema
(function(){
  const btn = document.getElementById('themeToggle');
  if (!btn) return;
  const key = 'theme';
  const apply = (t)=> document.body.classList.toggle('theme-dark', t!=='light');
  apply(localStorage.getItem(key)||'dark');
  btn.addEventListener('click', ()=>{
    const cur = localStorage.getItem(key)||'dark';
    const next = cur==='light' ? 'dark' : 'light';
    localStorage.setItem(key,next); apply(next);
  });
})();

// dropdown azioni (solo quando autenticato)
(function(){
  const btn = document.getElementById('menuBtn');
  const dd  = document.getElementById('menuDd');
  if (!btn || !dd) return;
  const wrap = btn.parentElement;
  btn.addEventListener('click', ()=> wrap.classList.toggle('open'));
  document.addEventListener('click', (e)=>{
    if (!wrap.contains(e.target)) wrap.classList.remove('open');
  });
  dd.querySelectorAll('[data-open]').forEach(el=>{
    el.addEventListener('click', ()=>{
      wrap.classList.remove('open');
      const id = el.getAttribute('data-open');
      const dlg = document.getElementById(id);
      if (dlg) dlg.showModal();
    });
  });
})();
