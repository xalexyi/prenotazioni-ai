(function () {
  const $ = (sel, ctx=document) => ctx.querySelector(sel);
  const $$ = (sel, ctx=document) => Array.from(ctx.querySelectorAll(sel));

  // Router super-semplice: pannelli laterali
  const panels = {
    prices: "#panel-prices",
    menu: "#panel-menu",
    weekly: "#panel-weekly",
    special: "#panel-special",
    stats: "#panel-stats",
  };

  function showPanel(key){
    $$(".panel").forEach(p => p.classList.remove("visible"));
    if(!key){ $("#panel-reservations").classList.add("visible"); return; }
    const id = panels[key];
    if(id) $(id).classList.add("visible");
  }

  // attiva nav
  $$(".sidebar [data-panel]").forEach(a=>{
    a.addEventListener("click", (e)=>{
      e.preventDefault();
      showPanel(a.dataset.panel);
    });
  });

  // ---------------- Prenotazioni ----------------
  $("#btn-today").addEventListener("click", ()=>{
    const d = new Date();
    const pad = n=>String(n).padStart(2,"0");
    $("#flt-date").value = `${pad(d.getDate())}/${pad(d.getMonth()+1)}/${d.getFullYear()}`;
    loadReservations();
  });

  $("#btn-clear").addEventListener("click", ()=>{
    $("#flt-date").value = "";
    $("#flt-q").value = "";
    loadReservations();
  });

  $("#btn-filter").addEventListener("click", loadReservations);

  $("#btn-new").addEventListener("click", ()=>{
    $("#dlg-new").classList.remove("hidden");
  });
  $("#btn-dlg-close").addEventListener("click", ()=> $("#dlg-new").classList.add("hidden"));
  $("#btn-dlg-save").addEventListener("click", async ()=>{
    const payload = {
      date: $("#new-date").value.trim(),
      time: $("#new-time").value.trim(),
      name: $("#new-name").value.trim(),
      phone: $("#new-phone").value.trim(),
      people: +$("#new-people").value || 2,
      status: $("#new-status").value,
      note: $("#new-note").value.trim()
    };
    const r = await fetch("/api/reservations", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    const j = await r.json();
    if(j.ok){ $("#dlg-new").classList.add("hidden"); loadReservations(); }
    else alert("Errore salvataggio prenotazione");
  });

  async function loadReservations(){
    const params = new URLSearchParams();
    const v = $("#flt-date").value.trim();
    if(v){
      // accetta dd/mm/yyyy e yyyy-mm-dd
      let d = v;
      if(v.includes("/")){
        const [dd,mm,yy] = v.split("/");
        d = `${yy}-${mm.padStart(2,"0")}-${dd.padStart(2,"0")}`;
      }
      params.set("date", d);
    }
    const r = await fetch("/api/reservations?"+params.toString());
    const rows = await r.json();
    const box = $("#res-list");
    box.innerHTML = "";
    if(rows.length === 0){
      box.innerHTML = `<div class="empty">Nessuna prenotazione trovata</div>`;
      return;
    }
    rows.forEach(item=>{
      const el = document.createElement("div");
      el.className = "row";
      el.innerHTML = `<div><strong>${item.time}</strong> — ${item.name} (${item.people})</div><div class="muted">${item.phone||""}</div>`;
      box.appendChild(el);
    });
  }

  // ---------------- Prezzi & coperti (pranzo/cena) ----------------
  async function pricesLoad(){
    const j = await (await fetch("/api/settings/prices")).json();
    $("#price-lunch").value = j.avg_price_lunch || 0;
    $("#price-dinner").value = j.avg_price_dinner || 0;
    $("#cover-fee").value = j.cover_fee || 0;
    $("#seats-cap").value = j.seats_cap || "";
    $("#min-people").value = j.min_people || "";
  }
  $("#btn-prices-save").addEventListener("click", async ()=>{
    const payload = {
      avg_price_lunch: +$("#price-lunch").value || 0,
      avg_price_dinner: +$("#price-dinner").value || 0,
      cover_fee: +$("#cover-fee").value || 0,
      seats_cap: $("#seats-cap").value ? +$("#seats-cap").value : null,
      min_people: $("#min-people").value ? +$("#min-people").value : null
    };
    const r = await fetch("/api/settings/prices",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const j = await r.json();
    if(j.ok) alert("Impostazioni salvate");
    else alert("Errore salvataggio");
  });

  // ---------------- Menu digitale (CRUD semplice) ----------------
  async function menuLoad(){
    const items = await (await fetch("/api/menu-items")).json();
    const box = $("#menu-list");
    box.innerHTML = "";
    if(items.length===0){ box.innerHTML = `<div class="empty">Nessun piatto</div>`; return; }
    items.forEach(it=>{
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `
        <div class="grow"><input class="input inline name" value="${it.name}"></div>
        <div><input class="input inline price" type="number" step="0.01" value="${it.price}"></div>
        <button class="btn sm save">Salva</button>
        <button class="btn sm danger del">Elimina</button>
      `;
      row.querySelector(".save").addEventListener("click", async ()=>{
        const name = row.querySelector(".name").value.trim();
        const price = +row.querySelector(".price").value || 0;
        const r = await fetch(`/api/menu-items/${it.id}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,price})});
        const j = await r.json();
        if(!j.ok) alert("Errore salvataggio piatto");
      });
      row.querySelector(".del").addEventListener("click", async ()=>{
        if(!confirm("Eliminare questo piatto?")) return;
        const r = await fetch(`/api/menu-items/${it.id}`, {method:"DELETE"});
        const j = await r.json();
        if(j.ok) menuLoad();
      });
      $("#menu-list").appendChild(row);
    });
  }
  $("#btn-mi-add").addEventListener("click", async ()=>{
    const name = $("#mi-name").value.trim();
    const price = +$("#mi-price").value || 0;
    if(!name){ alert("Nome piatto obbligatorio"); return; }
    const r = await fetch("/api/menu-items",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,price})});
    const j = await r.json();
    if(j.ok){ $("#mi-name").value=""; $("#mi-price").value=""; menuLoad(); }
  });

  // ---------------- Orari settimanali ----------------
  const WEEK = ["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"];
  async function weeklyRender(){
    const grid = $("#wh-grid");
    grid.innerHTML = "";
    const arr = await (await fetch("/api/weekly-hours")).json(); // 7 stringhe
    WEEK.forEach((name, i)=>{
      const v = arr[i] || "";
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `
        <label class="lbl">${name}
          <input class="input wh" data-i="${i}" value="${v}" placeholder="12:00-15:00, 19:00-22:30">
        </label>
      `;
      grid.appendChild(row);
    });
  }
  $("#btn-wh-save").addEventListener("click", async ()=>{
    const vals = $$(".wh").map(i=>i.value.trim());
    const r = await fetch("/api/weekly-hours",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(vals)});
    const j = await r.json();
    $("#wh-saved").classList.toggle("hidden", !j.ok);
    if(j.ok){ setTimeout(()=>$("#wh-saved").classList.add("hidden"), 1500); }
  });

  // ---------------- Giorni speciali ----------------
  async function specialLoad(){
    const items = await (await fetch("/api/special-days")).json();
    const box = $("#sp-list");
    box.innerHTML = "";
    if(items.length===0){ box.innerHTML = `<div class="empty">Nessun giorno speciale</div>`; return; }
    items.forEach(it=>{
      const row = document.createElement("div");
      row.className = "row";
      const note = it.closed ? "CHIUSO" : (it.windows||"");
      row.innerHTML = `<div class="grow"><strong>${it.date}</strong> — ${note}</div>
        <button class="btn sm danger">Elimina</button>`;
      row.querySelector("button").addEventListener("click", async ()=>{
        if(!confirm("Eliminare questa data?")) return;
        const r = await fetch(`/api/special-days/${it.date}`, {method:"DELETE"});
        const j = await r.json();
        if(j.ok) specialLoad();
      });
      box.appendChild(row);
    });
  }

  $("#btn-sp-save").addEventListener("click", async ()=>{
    const d = $("#sp-date").value.trim();
    const closed = $("#sp-closed").checked;
    const win = $("#sp-win").value.trim();
    if(!d){ alert("Data obbligatoria (YYYY-MM-DD)"); return; }
    const r = await fetch("/api/special-days",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({date:d, closed, windows:win})});
    const j = await r.json();
    if(j.ok){ $("#sp-date").value=""; $("#sp-closed").checked=false; $("#sp-win").value=""; specialLoad(); }
  });

  // ---------------- Init ----------------
  (async function init(){
    showPanel(null);       // inizia su "Prenotazioni"
    await loadReservations();
    await pricesLoad();
    await menuLoad();
    await weeklyRender();
    await specialLoad();
  })();
})();
