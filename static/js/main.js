// Helpers
const $ = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => [...root.querySelectorAll(sel)];

function toast(msg){
  const el = $('#toast'); if(!el) return;
  el.textContent = msg; el.classList.add('is-show');
  setTimeout(()=>el.classList.remove('is-show'), 1800);
}

// THEME
(function themeInit(){
  const root = document.documentElement;
  const saved = localStorage.getItem('theme') || 'dark';
  if(saved === 'light') root.setAttribute('data-theme','light');
  const tgl = $('#theme-toggle');
  if(tgl){
    tgl.checked = (saved === 'dark') ? true : false;
    tgl.addEventListener('change', ()=>{
      const isDark = tgl.checked;
      if(isDark){ root.removeAttribute('data-theme'); localStorage.setItem('theme','dark'); }
      else      { root.setAttribute('data-theme','light'); localStorage.setItem('theme','light'); }
    });
  }
})();

// LEFT NAV switching
export function wireLeftMenu(){
  $$('.sidebar .navlink').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      $$('.sidebar .navlink').forEach(b=>b.classList.remove('is-active'));
      btn.classList.add('is-active');
      const id = btn.getAttribute('data-section');
      $$('.panel').forEach(p=>p.classList.remove('is-active'));
      $('#'+id).classList.add('is-active');
    });
  });
}

// Modal helpers
export function openModal(id){ const m = $(id); if(m) m.classList.add('is-open'); }
export function closeModal(id){ const m = $(id); if(m) m.classList.remove('is-open'); }
export function wireModalClose(id){
  const m = $(id); if(!m) return;
  $$('[data-close]', m).forEach(x=> x.addEventListener('click', ()=> closeModal(id)));
  $('.modal__overlay', m)?.addEventListener('click', ()=> closeModal(id));
}

// Date utils
export function todayISO(){
  const d = new Date(); const m=String(d.getMonth()+1).padStart(2,'0'); const day=String(d.getDate()).padStart(2,'0');
  return `${d.getFullYear()}-${m}-${day}`;
}
export function fmtForInput(dISO){ // YYYY-MM-DD -> dd/mm/yyyy
  const [y,m,d]=dISO.split('-'); return `${d}/${m}/${y}`;
}
export function parseFromInput(s){ // dd/mm/yyyy -> YYYY-MM-DD
  const [d,m,y] = s.split('/'); if(!y) return '';
  return `${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;
}
