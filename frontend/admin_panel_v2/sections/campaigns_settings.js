import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

export async function init(panel) {
  panel.innerHTML = `<div class="section-content" style="padding:24px;max-width:600px">
    <h2 style="margin:0 0 24px">Ustawienia kampanii</h2>

    <div class="settings-card" id="plan-config-card">
      <div class="settings-card-loading">Ładowanie…</div>
    </div>

    <div class="settings-card" id="clock-config-card" style="margin-top:20px">
      <div class="settings-card-loading">Ładowanie…</div>
    </div>
  </div>`;

  await Promise.all([_loadPlanConfig(panel), _loadClockConfig(panel)]);
}

async function _loadPlanConfig(panel) {
  const card = panel.querySelector("#plan-config-card");
  try {
    const { config } = await adminFetch("/api/admin/plan-config");
    card.innerHTML = _planConfigHtml(config);
    card.querySelector("#plan-save-btn").addEventListener("click", () => _savePlanConfig(card));
  } catch (e) {
    card.innerHTML = `<p style="color:var(--accent-red)">Błąd: ${e.message}</p>`;
  }
}

async function _loadClockConfig(panel) {
  const card = panel.querySelector("#clock-config-card");
  try {
    const { config } = await adminFetch("/api/admin/clock-config");
    card.innerHTML = _clockConfigHtml(config);
    card.querySelector("#clock-save-btn").addEventListener("click", () => _saveClockConfig(card));
  } catch (e) {
    card.innerHTML = `<p style="color:var(--accent-red)">Błąd: ${e.message}</p>`;
  }
}

async function _savePlanConfig(card) {
  const turns = parseInt(card.querySelector("#plan-force-turns").value, 10);
  if (isNaN(turns) || turns < 5 || turns > 200) {
    showToast("Wartość musi być liczbą 5–200", "error"); return;
  }
  try {
    await adminFetch("/api/admin/plan-config", { method: "PATCH", body: JSON.stringify({ force_update_turns: turns }) });
    showToast("Zapisano ustawienia planu", "success");
  } catch (e) {
    showToast("Błąd zapisu: " + e.message, "error");
  }
}

async function _saveClockConfig(card) {
  const nar = parseInt(card.querySelector("#clock-narrative").value, 10);
  const com = parseInt(card.querySelector("#clock-combat").value, 10);
  const trv = parseInt(card.querySelector("#clock-travel").value, 10);
  if ([nar, com, trv].some(v => isNaN(v) || v < 0 || v > 480)) {
    showToast("Wartości muszą być 0–480 minut", "error"); return;
  }
  try {
    await adminFetch("/api/admin/clock-config", { method: "PATCH", body: JSON.stringify({ narrative_min: nar, combat_min: com, travel_min: trv }) });
    showToast("Zapisano ustawienia zegara", "success");
  } catch (e) {
    showToast("Błąd zapisu: " + e.message, "error");
  }
}

function _planConfigHtml(cfg) {
  return `
    <h3 style="margin:0 0 8px">Plan MG — automatyczna aktualizacja</h3>
    <p style="margin:0 0 16px;color:var(--text-muted);font-size:13px">
      Jeśli plan MG nie był aktualizowany przez podaną liczbę tur, system przy następnej turze
      narracyjnej poprosi MG o zaktualizowanie planu kampanii (cele sceny, roadmap, postęp fabuły).
      Wartość 25 oznacza mniej więcej jedną sesję gry.
    </p>
    <div style="display:flex;align-items:center;gap:12px">
      <label style="font-size:14px;white-space:nowrap">Próg aktualizacji (tury):</label>
      <input id="plan-force-turns" type="number" min="5" max="200" value="${cfg.force_update_turns}"
        style="width:80px;padding:6px 8px;background:var(--bg-input,#1e2530);border:1px solid var(--border-color,#333);border-radius:4px;color:inherit;font-size:14px">
      <button id="plan-save-btn" class="btn-primary" style="padding:6px 16px">Zapisz</button>
    </div>`;
}

function _clockConfigHtml(cfg) {
  return `
    <h3 style="margin:0 0 8px">Zegar gry — przyrost czasu</h3>
    <p style="margin:0 0 16px;color:var(--text-muted);font-size:13px">
      Ile minut czasu fabularnego przybywa po każdej turze danego typu.
      MG może nadpisać wartość w górę polem <code>time_advance_minutes</code> w odpowiedzi JSON.
    </p>
    <div style="display:grid;grid-template-columns:auto 80px;gap:8px 12px;align-items:center">
      <label style="font-size:14px">Tura narracyjna (min):</label>
      <input id="clock-narrative" type="number" min="0" max="480" value="${cfg.narrative_min}"
        style="padding:6px 8px;background:var(--bg-input,#1e2530);border:1px solid var(--border-color,#333);border-radius:4px;color:inherit;font-size:14px">
      <label style="font-size:14px">Tura walki (min):</label>
      <input id="clock-combat" type="number" min="0" max="480" value="${cfg.combat_min}"
        style="padding:6px 8px;background:var(--bg-input,#1e2530);border:1px solid var(--border-color,#333);border-radius:4px;color:inherit;font-size:14px">
      <label style="font-size:14px">Tura podróży (min):</label>
      <input id="clock-travel" type="number" min="0" max="480" value="${cfg.travel_min}"
        style="padding:6px 8px;background:var(--bg-input,#1e2530);border:1px solid var(--border-color,#333);border-radius:4px;color:inherit;font-size:14px">
    </div>
    <div style="margin-top:12px">
      <button id="clock-save-btn" class="btn-primary" style="padding:6px 16px">Zapisz</button>
    </div>`;
}
