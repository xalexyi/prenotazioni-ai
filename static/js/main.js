window.UI = {
  moneyEUR(v) {
    const n = Number(v || 0);
    return "€ " + n.toLocaleString("it-IT", {minimumFractionDigits:0});
  },
  openModal(id="modal"){ const m=document.getElementById(id); if(m){m.setAttribute("aria-hidden","false");}},
  closeModal(id="modal"){ const m=document.getElementById(id); if(m){m.setAttribute("aria-hidden","true");}}
};
