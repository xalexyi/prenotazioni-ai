/* static/js/dashboard.js */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // ---------- helpers UI ----------
  function openModal(id) {
    const m = $(id);
    if (!m) return;
    m.setAttribute("aria-hidden", "false");
    m.dataset.open = "1";
    // close on backdrop click
    const onClick = (e) => { if (e.target === m) closeModal(id); };
    const onKey = (e) => { if (e.key === "Escape") closeModal(id); };
    m._closers = { onClick, onKey };
    m.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
  }
  function closeModal(id) {
    const m = $(id);
    if (!m) return;
    m.setAttribute("aria-hidden", "true");
    m.dataset.open = "";
    if (m._closers) {
      m.removeEventListener("click", m._closers.onClick);
      document.removeEventListener("keydown", m._closers.onKey);
      m._closers = null;
    }
  }
  $$(".modal .js-close").forEach((b) => {
    b.addEventListener("click", (e) => {
      const m = e.target.closest(".modal-backdrop");
      if (m) closeModal("#" + m.id);
    });
  });

  // ---------- kebab menu ----------
  const kebabBtn = $("#btn-kebab");
  const kebabMenu = $("#kebab-menu");
  function kebabOpen() {
    kebabMenu.hidden = false;
    kebabMenu.classList.add("open");
    kebabBtn.classList.add("kebab-active");
    kebabBtn.setAttribute("aria-expanded", "true");
    // close handlers
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
    kebabMenu.classList.remove("open");
    kebabBtn.classList.remove("kebab-active");
    kebabBtn.setAttribute("aria-expanded", "false");
    setTimeout(() => { kebabMenu.hidden = true; }, 120);
    if (kebabMenu._off) kebabMenu._off();
  }
  if (kebabBtn) {
    kebabBtn.addEventListener("click", () => {
      if (kebabMenu.hidden) kebabOpen(); else kebabClose();
    });
  }

  // ---------- API ----------
  async function getState() {
    const r = await fetch("/api/admin/schedule/state", { credentials: "same-origin" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function saveWeekly(payload) {
    const r = await fetch("/api/admin/schedule/weekly", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      credentials: "same-origin",
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function saveSettings(payload) {
    const r = await fetch("/api/admin/schedule/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      credentials: "same-origin",
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function listSpecialDays(range) {
    const qs = new URLSearchParams(range || {}).toString();
    const r = await fetch("/api/admin/special-days/list" + (qs ? "?" + qs : ""), {
      credentials: "same-origin",
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function upsertSpecial(payload) {
    const r = await fetch("/api/admin/special-days/upsert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      credentials: "same-origin",
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function deleteSpecial(date) {
    const r = await fetch("/api/admin/special-days/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
      credentials: "same-origin",
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  // ---------- WEEKLY UI ----------
  const dayNames = ["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"];
  function normalizeWeekly(weekly) {
    // Accept: dict {0:[{start,end}],..} OR list [{weekday:0,ranges:[..]},..]
    const out = new Array(7).fill(0).map(() => []);
    if (Array.isArray(weekly)) {
      weekly.forEach((d) => {
        const w = Number(d.weekday);
        (d.ranges || []).forEach((r) => out[w].push({ start: r.start, end: r.end }));
      });
    } else if (weekly && typeof weekly === "object") {
      Object.keys(weekly).forEach((k) => {
        const w = Number(k);
        (weekly[k] || []).forEach((r) => out[w].push({ start: r.start, end: r.end }));
      });
    }
    return out;
  }
  function rangesToString(ranges) {
    return (ranges || []).map(r => `${r.start}-${r.end}`).join(", ");
  }
  function parseRanges(str) {
    const clean = (str || "").trim();
    if (!clean) return [];
    return clean.split(",").map(s => s.trim()).filter(Boolean).map(seg => {
      const m = seg.match(/^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$/);
      if (!m) throw new Error(`Formato orario non valido: "${seg}"`);
      return { start: m[1], end: m[2] };
    });
  }
  function buildWeeklyForm(weeklyArr) {
    const box = $("#weekly-form");
    box.innerHTML = "";
    for (let i = 0; i < 7; i++) {
      const label = document.createElement("div");
      label.className = "w-row";
      label.innerHTML = `<div><strong>${dayNames[i]}</strong></div>
                         <input class="input" data-wd="${i}" placeholder="12:00-15:00, 19:00-23:30">`;
      box.appendChild(label);
      const input = box.querySelector(`input[data-wd="${i}"]`);
      input.value = rangesToString(weeklyArr[i]);
    }
  }

  async function actionWeekly() {
    try {
      const st = await getState();
      const weeklyArr = normalizeWeekly(st.weekly);
      buildWeeklyForm(weeklyArr);
      openModal("#modal-weekly");
    } catch (e) {
      alert("Errore caricamento orari");
      console.error(e);
    }
  }

  $("#weekly-save")?.addEventListener("click", async () => {
    try {
      const inputs = $$("#weekly-form input[data-wd]");
      const weekly = [];
      for (const inp of inputs) {
        const wd = Number(inp.dataset.wd);
        const ranges = parseRanges(inp.value);
        weekly.push({ weekday: wd, ranges });
      }
      await saveWeekly({ weekly });
      closeModal("#modal-weekly");
      alert("Orari settimanali salvati");
    } catch (e) {
      alert(e.message || "Errore salvataggio");
      console.error(e);
    }
  });

  // ---------- SPECIAL UI ----------
  async function refreshSpecialList() {
    const data = await listSpecialDays({});
    const target = $("#sp-list");
    target.innerHTML = "";
    (data.items || []).forEach((d) => {
      const row = document.createElement("div");
      row.className = "list-row";
      const txt = d.closed
        ? `${d.date} — CHIUSO`
        : `${d.date} — ${rangesToString(d.ranges)}`;
      row.textContent = txt;
      target.appendChild(row);
    });
  }
  async function actionSpecial() {
    $("#sp-date").value = "";
    $("#sp-closed").checked = false;
    $("#sp-ranges").value = "18:00-23:00, 12:00-15:00";
    await refreshSpecialList();
    openModal("#modal-special");
  }
  $("#sp-add")?.addEventListener("click", async () => {
    try {
      const date = $("#sp-date").value;
      const closed = $("#sp-closed").checked;
      if (!date) throw new Error("Seleziona una data");
      if (closed) {
        await upsertSpecial({ date, closed: true });
      } else {
        const ranges = parseRanges($("#sp-ranges").value);
        await upsertSpecial({ date, closed: false, ranges });
      }
      await refreshSpecialList();
      alert("Regola salvata");
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
      alert("Regola eliminata");
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
      alert("Errore caricamento impostazioni");
      console.error(e);
    }
  }
  $("#st-save")?.addEventListener("click", async () => {
    try {
      const payload = {
        slot_step_min: Number($("#st-step").value),
        last_order_min: Number($("#st-last").value),
        capacity_per_slot: Number($("#st-cap").value),
        min_party: Number($("#st-minp").value),
        max_party: Number($("#st-maxp").value),
        tz: $("#st-tz").value.trim() || "Europe/Rome",
      };
      await saveSettings(payload);
      closeModal("#modal-settings");
      alert("Impostazioni salvate");
    } catch (e) {
      alert("Errore salvataggio impostazioni");
      console.error(e);
    }
  });

  // ---------- STATE / HELP ----------
  async function actionState() {
    try {
      const st = await getState();
      $("#state-pre").textContent = JSON.stringify(st, null, 2);
      openModal("#modal-state");
    } catch (e) {
      alert("Errore caricamento stato");
      console.error(e);
    }
  }
  function actionHelp() {
    openModal("#modal-help");
  }

  // ---------- kebab actions ----------
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

  // (facoltativo) badge voce / altre parti della dashboard restano invariati
})();
