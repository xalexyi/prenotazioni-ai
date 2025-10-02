/* static/js/dashboard.js — completo */
(() => {
  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // ---------- Toast ----------
  function showToast(msg, type = "ok") {
    let bar = $("#toast-bar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "toast-bar";
      bar.style.position = "fixed";
      bar.style.left = "50%";
      bar.style.bottom = "24px";
      bar.style.transform = "translateX(-50%)";
      bar.style.zIndex = "9999";
      document.body.appendChild(bar);
    }
    const pill = document.createElement("div");
    pill.textContent = msg;
    pill.style.padding = "10px 14px";
    pill.style.borderRadius = "999px";
    pill.style.color = "#fff";
    pill.style.fontWeight = "700";
    pill.style.boxShadow = "0 10px 30px rgba(0,0,0,.35)";
    pill.style.marginTop = "8px";
    pill.style.background =
      type === "ok"   ? "linear-gradient(135deg,#16a34a,#059669)" :
      type === "warn" ? "linear-gradient(135deg,#f59e0b,#d97706)" :
                        "linear-gradient(135deg,#dc2626,#b91c1c)";
    bar.appendChild(pill);
    setTimeout(() => pill.remove(), 2600);
  }

  // ---------- Modal helpers ----------
  function openModal(sel) {
    const m = $(sel);
    if (!m) return;
    m.setAttribute("aria-hidden", "false");
    m.dataset.open = "1";
    const onBackdrop = (e) => { if (e.target === m) closeModal(sel); };
    const onKey = (e) => { if (e.key === "Escape") closeModal(sel); };
    m._closers = { onBackdrop, onKey };
    m.addEventListener("click", onBackdrop);
    document.addEventListener("keydown", onKey);
  }
  function closeModal(sel) {
    const m = $(sel);
    if (!m) return;
    m.setAttribute("aria-hidden", "true");
    m.dataset.open = "";
    if (m._closers) {
      m.removeEventListener("click", m._closers.onBackdrop);
      document.removeEventListener("keydown", m._closers.onKey);
      m._closers = null;
    }
  }
  $$(".modal .js-close").forEach((b) => {
    b.addEventListener("click", (e) => {
      const modal = e.target.closest(".modal-backdrop");
      if (modal) closeModal("#" + modal.id);
    });
  });

  // ---------- Kebab menu ----------
  const kebabBtn  = $("#btn-kebab");
  const kebabMenu = $("#kebab-menu");
  function kebabOpen() {
    if (!kebabMenu) return;
    kebabMenu.hidden = false;
    kebabMenu.classList.add("open");
    kebabBtn?.classList.add("kebab-active");
    kebabBtn?.setAttribute("aria-expanded", "true");
  }
  function kebabClose() {
    if (!kebabMenu) return;
    kebabMenu.classList.remove("open");
    kebabBtn?.classList.remove("kebab-active");
    kebabBtn?.setAttribute("aria-expanded", "false");
    setTimeout(() => (kebabMenu.hidden = true), 120);
  }
  kebabBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (kebabMenu.hidden || !kebabMenu.classList.contains("open")) kebabOpen();
    else kebabClose();
  });
  document.addEventListener("click", (e) => {
    if (!kebabMenu) return;
    if (!kebabMenu.contains(e.target) && e.target !== kebabBtn) kebabClose();
  });
  kebabMenu?.addEventListener("click", (e) => {
    const b = e.target.closest(".k-item"); if (!b) return;
    const act = b.dataset.act;
    kebabClose();
    if (act === "weekly")   actionWeekly();
    if (act === "special")  actionSpecial();
    if (act === "settings") actionSettings();
    if (act === "state")    actionState();
    if (act === "help")     openModal("#modal-help");
  });

  // ---------- Helpers ----------
  const dayNames = ["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"];
  const isHHMM = (s) => /^\d{1,2}:\d{2}$/.test(s);
  const pad2 = (n) => String(n).padStart(2, "0");
  function todayISO() {
    const d = new Date();
    return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`;
  }
  function parseRanges(s) {
    const out = [];
    (s || "").split(",").forEach(part => {
      const p = part.trim();
      if (!p) return;
      const m = p.match(/^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$/);
      if (!m) throw new Error(`Intervallo non valido: "${p}" (usa HH:MM-HH:MM)`);
      if (!isHHMM(m[1]) || !isHHMM(m[2])) throw new Error(`Formato orario non valido in "${p}"`);
      out.push({ start: m[1], end: m[2] });
    });
    return out;
  }
  function rangesToString(arr) {
    return (arr || []).map(r => `${r.start}-${r.end}`).join(", ");
  }
  function normalizeWeeklyToArray(weekly) {
    const out = new Array(7).fill(0).map(() => []);
    if (Array.isArray(weekly)) {
      weekly.forEach(d => {
        const w = Number(d.weekday);
        (d.ranges || []).forEach(r => out[w].push({ start: r.start, end: r.end }));
      });
    }
    return out;
  }

  // ---------- Admin token / fetch ----------
  const SID_KEY='session_id';
  const getRid = ()=> window.RESTAURANT_ID || window.restaurant_id || 1;
  function sid(){
    let s = localStorage.getItem(SID_KEY) || window.SESSION_ID;
    if(!s){ s = Math.random().toString(36).slice(2); localStorage.setItem(SID_KEY, s); }
    return s;
  }
  async function getAdminToken(){
    const r = await fetch(`/api/public/sessions/${encodeURIComponent(sid())}`, { credentials:'same-origin', cache:'no-store' });
    const j = await r.json();
    const t = j.admin_token || j.token || j.session?.admin_token;
    if(!t) throw new Error('admin_token mancante');
    return t;
  }
  async function adminFetch(path, init={}){
    const headers = new Headers(init.headers || {});
    const token = await getAdminToken();
    headers.set('X-Admin-Token', token);
    if (!headers.has('Content-Type') && !(init.body instanceof FormData)) headers.set('Content-Type','application/json');
    const r = await fetch(`/api/admin-token${path}`, { ...init, headers, credentials:'same-origin' });
    if(!r.ok){
      let err = { message: `HTTP ${r.status}` };
      try { const j = await r.json(); err = j || err; } catch(_){}
      throw err;
    }
    return r.json();
  }

  // ---------- API wrappers ----------
  async function getState(){
    const q = new URLSearchParams({ restaurant_id: String(getRid()) });
    return adminFetch(`/schedule/state?${q.toString()}`);
  }
  async function saveWeeklyBulk(weekday, ranges){
    return adminFetch("/opening-hours/bulk", {
      method:"POST",
      body: JSON.stringify({ restaurant_id: getRid(), weekday, ranges })
    });
  }
  async function saveSettings(payload){
    return adminFetch("/settings/update", { method:"POST", body: JSON.stringify({ ...payload, restaurant_id: getRid() }) });
  }
  async function listSpecials(){
    return adminFetch(`/special-days/list?restaurant_id=${getRid()}`);
  }
  async function upsertSpecial(payload){
    return adminFetch("/special-days/upsert", { method:"POST", body: JSON.stringify({ ...payload, restaurant_id: getRid() }) });
  }
  async function deleteSpecial(date){
    return adminFetch("/special-days/delete", { method:"POST", body: JSON.stringify({ restaurant_id: getRid(), date }) });
  }
  async function createReservation(payload){
    return adminFetch("/reservations/create", {
      method: "POST",
      body: JSON.stringify({ ...payload, restaurant_id: getRid() })
    });
  }

  // ---------- WEEKLY UI ----------
  function buildWeeklyForm(weeklyArr) {
    const box = $("#weekly-form");
    if (!box) return;
    box.innerHTML = "";
    for (let i = 0; i < 7; i++) {
      const row = document.createElement("div");
      row.className = "w-row";
      const ranges = weeklyArr[i] || [];
      row.innerHTML = `
        <div class="w-day">${dayNames[i]}</div>
        <div class="w-ranges" data-day="${i}"></div>
        <div><button class="btn btn-xs btn-outline js-add" data-day="${i}">+ Fascia</button></div>
      `;
      box.appendChild(row);
      const holder = row.querySelector(".w-ranges");
      ranges.forEach(r => holder.appendChild(rangeElem(r.start, r.end)));
    }
  }
  function rangeElem(a="12:00", b="15:00"){
    const div = document.createElement("div");
    div.className = "w-range";
    div.innerHTML = `
      <input type="time" class="w-start" value="${a}">
      <span>–</span>
      <input type="time" class="w-end" value="${b}">
      <button class="btn btn-xs btn-outline-danger js-del">×</button>
    `;
    div.querySelector(".js-del").addEventListener("click", ()=> div.remove());
    return div;
  }
  function collectWeeklyDay(dayIdx){
    const box = $(`.w-ranges[data-day="${dayIdx}"]`);
    const arr = [];
    box?.querySelectorAll(".w-range").forEach(r=>{
      const a = r.querySelector(".w-start").value;
      const b = r.querySelector(".w-end").value;
      if(a && b) arr.push({ start:a, end:b });
    });
    return arr;
  }

  async function actionWeekly(){
    try{
      const st = await getState();
      const weekly = normalizeWeeklyToArray(st.weekly || []);
      buildWeeklyForm(weekly);
      $("#weekly-form")?.addEventListener("click", (e)=>{
        const b = e.target.closest(".js-add");
        if(!b) return;
        const day = Number(b.dataset.day);
        const holder = $(`.w-ranges[data-day="${day}"]`);
        holder?.appendChild(rangeElem("19:00","23:00"));
      }, { once: true });

      $("#btn-save-weekly")?.addEventListener("click", async ()=>{
        try{
          for(let wd=0; wd<7; wd++){
            const ranges = collectWeeklyDay(wd);
            // validazione veloce
            ranges.forEach(r=>{
              if(!isHHMM(r.start) || !isHHMM(r.end)) throw new Error("Formato orario non valido");
            });
            await saveWeeklyBulk(wd, ranges);
          }
          showToast("Orari settimanali salvati","ok");
          closeModal("#modal-weekly");
        }catch(e){
          console.error(e); showToast(e.detail || e.message || "Errore salvataggio","err");
        }
      }, { once: true });

      openModal("#modal-weekly");
    }catch(e){
      console.error(e);
      showToast(e.message || "Errore caricamento orari","err");
    }
  }

  // ---------- SPECIAL DAYS UI ----------
  function isoFromInput(v){ return (v||"").trim(); }
  async function refreshSpecialList(){
    const res = await listSpecials();
    const items = res.items || [];
    const box = $("#sp-list");
    if(!box) return;
    if(!items.length){ box.innerHTML = `<div class="muted">Nessuna regola</div>`; return; }
    items.sort((a,b)=> a.date.localeCompare(b.date));
    box.innerHTML = items.map(it=>{
      const tag = it.is_closed ? `<span class="chip chip-red">Chiuso</span>` : `<span class="chip">${rangesToString(it.ranges||[])}</span>`;
      return `<div class="li"><span class="mono">${it.date}</span> ${tag}</div>`;
    }).join("");
  }

  async function actionSpecial(){
    try{
      await refreshSpecialList();
      $("#sp-add")?.addEventListener("click", async ()=>{
        try{
          const date = isoFromInput($("#sp-date").value);
          if(!date) throw new Error("Seleziona una data");
          const is_closed = $("#sp-closed").checked;
          const ranges = is_closed ? [] : parseRanges($("#sp-ranges").value);
          await upsertSpecial({ date, is_closed, ranges });
          await refreshSpecialList();
          showToast("Giorno speciale salvato","ok");
        }catch(e){
          console.error(e);
          showToast(e.message || "Errore salvataggio","err");
        }
      }, { once: true });
      $("#sp-del")?.addEventListener("click", async () => {
        try {
          const date = isoFromInput($("#sp-date").value);
          if (!date) throw new Error("Seleziona una data");
          await deleteSpecial(date);
          await refreshSpecialList();
          showToast("Regola eliminata","ok");
        } catch (e) {
          console.error(e);
          showToast(e.message || "Errore eliminazione","err");
        }
      }, { once: true });

      openModal("#modal-special");
    }catch(e){
      console.error(e);
      showToast(e.message || "Errore caricamento giorni speciali","err");
    }
  }

  // ---------- SETTINGS UI ----------
  async function actionSettings() {
    try {
      const st = await getState();
      const s = st.settings || {};
      $("#st-step").value = s.slot_step_min ?? 15;
      $("#st-last").value = s.last_order_min ?? 15;
      $("#st-cap").value  = s.capacity_per_slot ?? 6;
      $("#st-minp").value = s.min_party ?? 1;
      $("#st-maxp").value = s.max_party ?? 12;
      $("#st-tz").value   = s.tz || "Europe/Rome";
      openModal("#modal-settings");

      $("#settings-save")?.addEventListener("click", async ()=>{
        try{
          const payload = {
            slot_step_min: Number($("#st-step").value || 15),
            last_order_min: Number($("#st-last").value || 15),
            capacity_per_slot: Number($("#st-cap").value || 6),
            min_party: Number($("#st-minp").value || 1),
            max_party: Number($("#st-maxp").value || 12),
            tz: ($("#st-tz").value || "Europe/Rome").trim(),
          };
          await saveSettings(payload);
          showToast("Impostazioni salvate","ok");
          closeModal("#modal-settings");
        }catch(e){
          console.error(e);
          showToast(e.message || "Errore salvataggio","err");
        }
      }, { once: true });

    } catch (e) {
      console.error(e);
      showToast(e.message || "Errore caricamento impostazioni", "err");
    }
  }

  // ---------- STATE UI ----------
  async function actionState(){
    try{
      const st = await getState();
      const human = $("#state-human");
      const weekly = normalizeWeeklyToArray(st.weekly || []);
      const specials = st.special_days || [];
      const s = st.settings || {};
      const lines = [];
      lines.push(`<div><strong>Orari settimanali</strong></div>`);
      weekly.forEach((arr, i)=>{
        lines.push(`<div class="mono">${dayNames[i]}: ${arr.length? arr.map(r=>`${r.start}-${r.end}`).join(", ") : '—'}</div>`);
      });
      lines.push(`<hr>`);
      lines.push(`<div><strong>Giorni speciali</strong></div>`);
      if(specials.length){
        specials.forEach(it=>{
          lines.push(`<div class="mono">${it.date}: ${it.is_closed? 'Chiuso' : rangesToString(it.ranges||[])}</div>`);
        });
      }else{
        lines.push(`<div class="mono">Nessuna regola</div>`);
      }
      lines.push(`<hr>`);
      lines.push(`<div><strong>Impostazioni</strong></div>`);
      lines.push(`<div class="mono">step=${s.slot_step_min ?? '—'} last=${s.last_order_min ?? '—'} capacity=${s.capacity_per_slot ?? '—'} party=${(s.min_party ?? '—')}-${(s.max_party ?? '—')} tz=${s.tz || '—'}</div>`);
      human.innerHTML = lines.join("");

      const pre = $("#state-json");
      pre.textContent = JSON.stringify(st, null, 2);

      openModal("#modal-state");
    }catch(e){
      console.error(e);
      showToast(e.message || "Errore caricamento stato","err");
    }
  }

  // ---------- CREA PRENOTAZIONE ----------
  $("#btn-open-create")?.addEventListener("click", ()=>{
    $("#cr-date").value = $("#resv-date")?.value || todayISO();
    $("#cr-time").value = "20:00";
    $("#cr-party").value = "2";
    $("#cr-name").value = "";
    $("#cr-phone").value = "";
    $("#cr-status").value = "confirmed";
    $("#cr-notes").value = "";
    openModal("#modal-create");
  });

  $("#create-save")?.addEventListener("click", async ()=>{
    try{
      const payload = {
        date: ($("#cr-date").value || "").trim(),
        time: ($("#cr-time").value || "").trim(),
        name: ($("#cr-name").value || "").trim(),
        phone: ($("#cr-phone").value || "").trim(),
        party_size: Number($("#cr-party").value || 2),
        status: ($("#cr-status").value || "confirmed").trim(),
        notes: ($("#cr-notes").value || "").trim(),
      };
      if(!payload.date || !payload.time || !payload.name) throw new Error("Compila data, ora, nome");
      await createReservation(payload);
      showToast("Prenotazione creata","ok");
      closeModal("#modal-create");
      $("#resv-refresh")?.click();
    }catch(e){
      console.error(e);
      showToast(e.message || "Errore creazione", "err");
    }
  });

  // --------- bootstrap token (silenzioso) ---------
  (async () => { try { await getAdminToken(); } catch(_){/* no-op */} })();
})();
