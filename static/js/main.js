// Helpers
async function jsonFetch(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    const msg = (data && (data.error || data.message)) || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

// ---------------- Dashboard wiring (only if the elements exist) ----------------
document.addEventListener("click", (ev) => {
  const id = ev.target && ev.target.id;
  if (id === "btn-weekly-hours") openWeeklyHoursModal();
  if (id === "btn-special-days") openSpecialDayModal();
});

// ---------------- Prenotazioni ----------------
async function saveReservationFromModal() {
  try {
    const date = document.querySelector("#res-date").value.trim();   // "DD/MM/YYYY"
    const time = document.querySelector("#res-time").value.trim();   // "HH:MM"
    const name = document.querySelector("#res-name").value.trim();
    const phone = document.querySelector("#res-phone").value.trim();
    const people = parseInt(document.querySelector("#res-people").value || "2", 10);
    const status = document.querySelector("#res-status").value || "confirmed";
    const notes = document.querySelector("#res-notes").value || "";

    const payload = { date, time, name, phone, people, status, notes };
    await jsonFetch("/api/reservations", { method: "POST", body: JSON.stringify(payload) });

    alert("Prenotazione salvata ✅");
    location.reload();
  } catch (e) {
    console.error(e);
    alert("Errore salvataggio: " + e.message);
  }
}

// ---------------- Orari settimanali ----------------
function openWeeklyHoursModal() {
  // Questa funzione può aprire il tuo modal esistente.
  // Qui assumiamo che nel tuo HTML ci siano 7 <input> con id hours-0 ... hours-6
  // e un bottone che chiama saveWeeklyHours().
  document.dispatchEvent(new CustomEvent("open-weekly-hours-modal"));
}

async function saveWeeklyHours() {
  try {
    const days = {};
    for (let i = 0; i < 7; i++) {
      const el = document.querySelector(`#hours-${i}`);
      if (el) days[i] = el.value.trim(); // es. "12:00-15:00, 19:00-22:30" oppure "" = chiuso
    }
    await jsonFetch("/api/hours/weekly", {
      method: "POST",
      body: JSON.stringify({ days }),
    });
    alert("Orari settimanali salvati ✅");
    location.reload();
  } catch (e) {
    console.error(e);
    alert("Errore salvataggio orari: " + e.message);
  }
}

// ---------------- Giorni speciali ----------------
function openSpecialDayModal() {
  document.dispatchEvent(new CustomEvent("open-special-day-modal"));
}

async function saveSpecialDay() {
  try {
    const day = document.querySelector("#sd-day").value.trim(); // "DD/MM/YYYY"
    const closed = !!document.querySelector("#sd-closed")?.checked;
    const windows = document.querySelector("#sd-windows").value.trim(); // "18:00-23:00, 12:00-15:00"

    await jsonFetch("/api/special-days", {
      method: "POST",
      body: JSON.stringify({ day, closed, windows }),
    });
    alert("Giorno speciale salvato ✅");
    location.reload();
  } catch (e) {
    console.error(e);
    alert("Errore salvataggio giorno speciale: " + e.message);
  }
}

async function deleteSpecialDay() {
  try {
    const day = document.querySelector("#sd-day").value.trim(); // "DD/MM/YYYY"
    await jsonFetch("/api/special-days", {
      method: "DELETE",
      body: JSON.stringify({ day }),
    });
    alert("Giorno speciale eliminato ✅");
    location.reload();
  } catch (e) {
    console.error(e);
    alert("Errore eliminazione giorno speciale: " + e.message);
  }
}

// Esponi global per gli handler inline già presenti nei template
window.saveReservationFromModal = saveReservationFromModal;
window.saveWeeklyHours = saveWeeklyHours;
window.saveSpecialDay = saveSpecialDay;
window.deleteSpecialDay = deleteSpecialDay;
