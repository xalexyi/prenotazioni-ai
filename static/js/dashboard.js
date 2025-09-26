/* static/js/dashboard.js — complete, verified */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

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
  const kebabBtn = $("#btn-kebab");
  const kebabMenu = $("#kebab-menu");
  function kebabOpen() {
    if (!kebabMenu) return;
    kebabMenu.hidden = false;
    kebabMenu.classList.add("open");
    kebabBtn?.classList.add("kebab-active");
    kebabBtn?.setAttribute("aria-expanded", "true");
    const onDoc = (e) => {
      if (!kebabMenu.contains(e.target) && e.target !== kebabBtn) kebabClose();
    };
    const onKey = (e) => { if (e.key === "Escape") kebabClose(); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    kebabMenu._off = () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }
  function kebabClose() {
    if (!kebabMenu) return;
    kebabMenu.classList.remove("open");
    kebabBtn?.classList.remove("kebab-active");
    kebabBtn?.setAttribute("aria-expanded", "false");
    setTimeout(() => { if (kebabMenu) kebabMenu.hidden = true; }, 100);
    if (kebabMenu._off) kebabMenu._off();
  }
  kebabBtn?.addEventListener("click", () => {
    if (kebabMenu.hidden) kebabOpen(); else kebabClose();
  });

  // ---------- Generic helpers ----------
  const dayNames = ["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"];
  const isHHMM = (s) => /^\d{1,2}:\d{2}$/.test(s);

  function rangesToString(arr) {
    return (arr || []).map(r => `${r.start}-${r.end}`).join(", ");
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
  function normalizeWeekly(weekly) {
    // Accept: dict {0:[{start,end}],..} OR list [{weekday,ranges:[..]},..]
    const out = new Array(7).fill(0).map(() => []);
    if (Array.isArray(weekly)) {
      weekly.forEach(d => {
        const w = Number(d.weekday);
        (d.ranges || []).forEach(r => out[w].push({ start: r.start, end: r.end }));
      });
    } else if (weekly && typeof weekly === "object") {
      Object.keys(weekly).forEach(k => {
        const w = Number(k);
        (weekly[k] || []).forEach(r => out[w].push({ start: r.start, end: r.end }));
      });
    }
    return out;
  }
  function weeklyArrToDict(weeklyArr){
    // Converti [[range...], ...] → {"0":[...],"1":[...],...}
    const dict = {};
    for (let i=0;i<7;i++) dict[String(i)] = weeklyArr[i] || [];
    return dict;
  }

  // ---------- API ----------
  async function getState() {
    const r = await fetch("/api/admin/schedule/state", { credentials: "same-origin", headers: { "Accept": "application/json" }});
    if (!r.ok) throw new Error("HTTP " + r.status);
    try { return await r.json(); }
    catch { throw new Error("Risposta non valida (probabile login scaduto)"); }
  }
  async function saveWeekly(weeklyDict) {
    const r = await fetch("/api/admin/schedule/weekly", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weekly: weeklyDict }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function saveSettings(payload) {
    const r = await fetch("/api/admin/schedule/settings", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function listSpecials() {
    const r = await fetch("/api/admin/special-days/list", { credentials: "same-origin" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function upsertSpecial(payload) {
    const r = await fetch("/api/admin/special-days/upsert", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function deleteSpecial(date) {
    const r = await fetch("/api/admin/special-days/delete", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  // ---------- WEEKLY UI ----------
  function buildWeeklyForm(weeklyArr) {
    const box = $("#weekly-form");
    if (!box) return;
    box.innerHTML = "";
    for (let i = 0; i < 7; i++) {
      const row = document.createElement("div");
      row.className = "w-row";
      row.innerHTML = `
        <div><strong>${dayNames[i]}</strong></div>
        <input class="input" data-wd="${i}" placeholder="12:00-15:00, 19:00-23:30">
      `;
      box.appendChild(row);
      box.querySelector(`input[data-wd="${i}"]`).value = rangesToString(weeklyArr[i]);
    }
  }
  async function actionWeekly() {
    try {
      const st = await getState();
      const weeklyArr = normalizeWeekly(st.weekly);
      buildWeeklyForm(weeklyArr);
      openModal("#modal-weekly");
    } catch (e) {
      alert("Errore caricamento orari: " + (e.message || e));
      console.error(e);
    }
  }
  $("#weekly-save")?.addEventListener("click", async () => {
    try {
      const inputs = $$("#weekly-form input[data-wd]");
      const weeklyArr = new Array(7).fill(0).map(()=>[]);
      for (const inp of inputs) {
        const wd = Number(inp.dataset.wd);
        const ranges = parseRanges(inp.value);
        weeklyArr[wd] = ranges;
      }
      // Il backend si aspetta un DIZIONARIO con chiavi 0..6
      const weeklyDict = weeklyArrToDict(weeklyArr);
      await saveWeekly(weeklyDict);
      alert("Orari settimanali aggiornati ✅");
      closeModal("#modal-weekly");
    } catch (e) {
      alert(e.message || "Errore salvataggio orari");
      console.error(e);
    }
  });

  // ---------- SPECIAL DAYS UI ----------
  async function refreshSpecialList() {
    const cont = $("#sp-list");
    if (!cont) return;
    cont.textContent = "Carico...";
    const { ok, items } = await listSpecials();
    if (!ok) throw new Error("Errore elenco giorni speciali");
    if (!items || items.length === 0) {
      cont.innerHTML = "<em>Nessuna regola</em>";
      return;
    }
    const ul = document.createElement("div");
    ul.className = "list";
    items.forEach(it => {
      const li = document.createElement("div");
      li.className = "list-item";
      const ranges = (it.ranges || []).map(r => `${r.start}-${r.end}`).join(", ");
      li.textContent = `${it.date} — ${it.closed ? "CHIUSO" : ranges || "aperto (nessuna fascia?)"}`;
      ul.appendChild(li);
    });
    cont.innerHTML = "";
    cont.appendChild(ul);
  }
  async function actionSpecial() {
    try {
      await refreshSpecialList();
      openModal("#modal-special");
    } catch (e) {
      alert("Errore caricamento giorni speciali: " + (e.message || e));
      console.error(e);
    }
  }
  $("#sp-add")?.addEventListener("click", async () => {
    try {
      const date = $("#sp-date").value;            // YYYY-MM-DD da <input type="date">
      const closed = $("#sp-closed").checked;
      if (!date) throw new Error("Seleziona una data");
      if (closed) {
        await upsertSpecial({ date, closed: true });
      } else {
        const ranges = parseRanges($("#sp-ranges").value);
        await upsertSpecial({ date, closed: false, ranges });
      }
      await refreshSpecialList();
      alert("Regola salvata ✅");
    } catch (e) {
      alert(e.message || "Errore salvataggio");
      console.error(e);
    }
  });
  $("#sp-del")?.addEventListener("click", async () => {
    try {
      const date = $("#sp-date").value;
      if (!date) throw new Error("Seleziona una data");
      await deleteSpecial(date);
      await refreshSpecialList();
      alert("Regola eliminata 🗑️");
    } catch (e) {
      alert(e.message || "Errore eliminazione");
      console.error(e);
    }
  });

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
    } catch (e) {
      alert("Errore caricamento impostazioni: " + (e.message || e));
      console.error(e);
    }
  }
  $("#settings-save")?.addEventListener("click", async () => {
    try {
      const payload = {
        slot_step_min: Number($("#st-step").value) || 15,
        last_order_min: Number($("#st-last").value) || 15,
        capacity_per_slot: Number($("#st-cap").value) || 6,
        min_party: Number($("#st-minp").value) || 1,
        max_party: Number($("#st-maxp").value) || 12,
        tz: $("#st-tz").value.trim() || "Europe/Rome",
      };
      await saveSettings(payload);
      alert("Impostazioni salvate ✅");
      closeModal("#modal-settings");
    } catch (e) {
      alert(e.message || "Errore salvataggio impostazioni");
      console.error(e);
    }
  });

  // ---------- STATE (debug) ----------
  async function actionState() {
    try {
      const st = await getState();
      const box = $("#state-json");
      if (box) {
        box.textContent = JSON.stringify(st, null, 2);
      }
      openModal("#modal-state");
    } catch (e) {
      alert("Errore lettura stato: " + (e.message || e));
      console.error(e);
    }
  }

  // ---------- HELP ----------
  function actionHelp() {
    openModal("#modal-help");
  }

  // Wire menu items
  kebabMenu?.addEventListener("click", (e) => {
    const btn = e.target.closest(".k-item");
    if (!btn) return;
    const act = btn.dataset.act;
    kebabClose();
    if (act === "weekly") return actionWeekly();
    if (act === "special") return actionSpecial();
    if (act === "settings") return actionSettings();
    if (act === "state") return actionState();
    if (act === "help") return actionHelp();
  });
})();
