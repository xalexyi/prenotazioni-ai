(function(){
  const css = `
  .toast-wrap{position:fixed;right:16px;bottom:16px;display:flex;flex-direction:column;gap:8px;z-index:9999}
  .toast{padding:10px 14px;border-radius:10px;background:var(--surface-2);color:var(--fg);box-shadow:0 8px 20px rgba(0,0,0,.3);border:1px solid var(--border)}
  .toast.ok{border-color:rgba(58,199,120,.6)}
  .toast.err{border-color:rgba(242,84,84,.6)}
  `;
  const style = document.createElement('style'); style.textContent = css; document.head.appendChild(style);
  const wrap = document.createElement('div'); wrap.className='toast-wrap'; document.body.appendChild(wrap);
  function show(msg, cls){
    const el = document.createElement('div'); el.className = `toast ${cls}`; el.textContent = msg;
    wrap.appendChild(el); setTimeout(()=>{ el.style.opacity='0'; el.style.transform='translateY(10px)'; }, 2200);
    setTimeout(()=>wrap.removeChild(el), 2600);
  }
  window.toastOK  = (m)=>show(m||'Fatto', 'ok');
  window.toastERR = (m)=>show(m||'Errore', 'err');
})();
