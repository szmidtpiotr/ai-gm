// Stage 8 D6 — Admin Panel v2 Debug section.
// Surfaces the existing backend/app/routers/debug.py endpoints as a UI:
//   GET  /api/debug/player_state?character_id=X
//   GET  /api/debug/gm_decisions?campaign_id=X&limit=N
//   GET  /api/debug/validation_flags?test_run_id=X
//   GET  /api/debug/settings/feature_flags
//   POST /api/debug/reset_test_env

import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const LABELS = {
  title:           "🐛 Debug — diagnostyka silnika",
  playerState:     "Stan bohatera",
  playerStateHint: "Pełny snapshot postaci, sesji i ostatniego stanu walki.",
  gmDecisions:     "Decyzje GM",
  gmDecisionsHint: "Lista ostatnich decyzji narratora w kampanii (typ + powód).",
  validation:      "Validation flags",
  validationHint:  "Flagi walidacji dla konkretnego test_run_id.",
  featureFlags:    "Feature flags",
  featureFlagsHint:"Bieżące przełączniki silnika (read-only).",
  resetTestEnv:    "Reset test env",
  resetHint:       "Czyści środowisko testowe (kampanie testowe, sesje). Wymaga potwierdzenia.",
  charIdLabel:     "character_id",
  campaignIdLabel: "campaign_id",
  limitLabel:      "limit",
  runIdLabel:      "test_run_id",
  refresh:         "↻ Odśwież",
  fetch:           "Pobierz",
  fire:            "⚠ Wykonaj reset",
  loading:         "Wczytywanie…",
  emptyResult:     "Brak danych. Wprowadź parametr i kliknij «Pobierz».",
};

function _h(strings, ...vals) {
  // Tiny template helper for HTML strings.
  return strings.reduce((a, s, i) => a + s + (vals[i] ?? ""), "");
}
function _esc(s) {
  return String(s ?? "").replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function _renderJson(obj) {
  try { return _esc(JSON.stringify(obj, null, 2)); }
  catch { return _esc(String(obj)); }
}

export async function init(panel) {
  panel.innerHTML = _h`
    <header class="section-header">
      <h2 class="section-title">${LABELS.title}</h2>
    </header>

    <!-- User → Character picker (auto-fills all ID fields) -->
    <div class="card debug-picker">
      <h3 class="card-title">🎯 Wybierz gracza i postać</h3>
      <p class="card-hint">Wybór wypełnia automatycznie wszystkie pola <code>character_id</code> i <code>campaign_id</code> poniżej.</p>
      <div class="debug-picker-row">
        <label>
          <span class="debug-picker-label">Gracz</span>
          <select id="dbg-user-select" class="debug-picker-select">
            <option value="">— ładowanie graczy… —</option>
          </select>
        </label>
        <label>
          <span class="debug-picker-label">Postać</span>
          <select id="dbg-char-select" class="debug-picker-select" disabled>
            <option value="">— wybierz najpierw gracza —</option>
          </select>
        </label>
        <span class="debug-picker-ids" id="dbg-picker-ids"></span>
      </div>
    </div>

    <div class="section-body debug-section-grid">

      <!-- Player State -->
      <div class="card debug-card">
        <h3 class="card-title">${LABELS.playerState}</h3>
        <p class="card-hint">${LABELS.playerStateHint}</p>
        <div class="debug-row">
          <label>${LABELS.charIdLabel}</label>
          <input type="number" id="dbg-player-state-id" min="1" placeholder="np. 1064" />
          <button type="button" class="primary-btn" id="dbg-player-state-go">${LABELS.fetch}</button>
        </div>
        <pre class="debug-output" id="dbg-player-state-out">${LABELS.emptyResult}</pre>
      </div>

      <!-- GM Decisions -->
      <div class="card debug-card">
        <h3 class="card-title">${LABELS.gmDecisions}</h3>
        <p class="card-hint">${LABELS.gmDecisionsHint}</p>
        <div class="debug-row">
          <label>${LABELS.campaignIdLabel}</label>
          <input type="number" id="dbg-gm-campaign-id" min="1" placeholder="np. 1057" />
          <label>${LABELS.limitLabel}</label>
          <input type="number" id="dbg-gm-limit" min="1" max="200" value="20" />
          <button type="button" class="primary-btn" id="dbg-gm-go">${LABELS.fetch}</button>
        </div>
        <pre class="debug-output" id="dbg-gm-out">${LABELS.emptyResult}</pre>
      </div>

      <!-- Validation Flags -->
      <div class="card debug-card">
        <h3 class="card-title">${LABELS.validation}</h3>
        <p class="card-hint">${LABELS.validationHint}</p>
        <div class="debug-row">
          <label>${LABELS.runIdLabel}</label>
          <input type="text" id="dbg-val-run-id" placeholder="np. abc-123" />
          <button type="button" class="primary-btn" id="dbg-val-go">${LABELS.fetch}</button>
        </div>
        <pre class="debug-output" id="dbg-val-out">${LABELS.emptyResult}</pre>
      </div>

      <!-- Feature Flags -->
      <div class="card debug-card">
        <h3 class="card-title">${LABELS.featureFlags}</h3>
        <p class="card-hint">${LABELS.featureFlagsHint}</p>
        <div class="debug-row">
          <button type="button" class="primary-btn" id="dbg-ff-go">${LABELS.refresh}</button>
        </div>
        <pre class="debug-output" id="dbg-ff-out">${LABELS.emptyResult}</pre>
      </div>

      <!-- Reset Test Env -->
      <div class="card debug-card debug-card--danger">
        <h3 class="card-title">${LABELS.resetTestEnv}</h3>
        <p class="card-hint">${LABELS.resetHint}</p>
        <div class="debug-row">
          <button type="button" class="danger-btn" id="dbg-reset-go">${LABELS.fire}</button>
        </div>
        <pre class="debug-output" id="dbg-reset-out">${LABELS.emptyResult}</pre>
      </div>

    </div>
  `;

  const get = (id) => panel.querySelector(`#${id}`);

  async function call(out, fn) {
    out.textContent = LABELS.loading;
    try {
      const data = await fn();
      out.textContent = _renderJson(data);
    } catch (e) {
      out.textContent = `Błąd: ${e?.message || e}`;
      showToast(`Debug: ${e?.message || e}`, "error");
    }
  }

  get("dbg-player-state-go").addEventListener("click", () => {
    const id = parseInt(get("dbg-player-state-id").value, 10);
    if (!id) { showToast(`Podaj ${LABELS.charIdLabel}`, "error"); return; }
    call(get("dbg-player-state-out"), () => adminFetch(`/api/debug/player_state?character_id=${id}`));
  });

  get("dbg-gm-go").addEventListener("click", () => {
    const cid = parseInt(get("dbg-gm-campaign-id").value, 10);
    const limit = parseInt(get("dbg-gm-limit").value, 10) || 20;
    if (!cid) { showToast(`Podaj ${LABELS.campaignIdLabel}`, "error"); return; }
    call(get("dbg-gm-out"), () => adminFetch(`/api/debug/gm_decisions?campaign_id=${cid}&limit=${limit}`));
  });

  get("dbg-val-go").addEventListener("click", () => {
    const runId = get("dbg-val-run-id").value.trim();
    if (!runId) { showToast(`Podaj ${LABELS.runIdLabel}`, "error"); return; }
    call(get("dbg-val-out"), () => adminFetch(`/api/debug/validation_flags?test_run_id=${encodeURIComponent(runId)}`));
  });

  get("dbg-ff-go").addEventListener("click", () => {
    call(get("dbg-ff-out"), () => adminFetch(`/api/debug/settings/feature_flags`));
  });

  get("dbg-reset-go").addEventListener("click", async () => {
    if (!confirm("Reset środowiska testowego? Operacja nieodwracalna.")) return;
    await call(get("dbg-reset-out"), () => adminFetch(`/api/debug/reset_test_env`, { method: "POST" }));
    showToast("Test env reset wysłany.", "success");
  });

  // Auto-fetch feature flags on first load — gives a non-empty screen immediately.
  call(get("dbg-ff-out"), () => adminFetch(`/api/debug/settings/feature_flags`));

  // ── User → Character picker ────────────────────────────────────────────
  const userSel = get("dbg-user-select");
  const charSel = get("dbg-char-select");
  const idsEl   = get("dbg-picker-ids");
  let _users = [];
  let _allChars = [];

  async function loadPicker() {
    try {
      const [accountsResp, charsResp] = await Promise.all([
        adminFetch("/api/admin/accounts"),
        adminFetch("/api/admin/characters"),
      ]);
      _users = (accountsResp.items || []).filter(u => u && u.id);
      _allChars = (charsResp.items || []).filter(c => c && c.id);

      // Group characters by owner; sort users with characters first
      const userHasChars = new Set(_allChars.map(c => c.user_id));
      const sorted = [..._users].sort((a, b) => {
        const ha = userHasChars.has(a.id) ? 0 : 1;
        const hb = userHasChars.has(b.id) ? 0 : 1;
        if (ha !== hb) return ha - hb;
        return String(a.username || "").localeCompare(String(b.username || ""));
      });

      userSel.innerHTML = `<option value="">— wybierz gracza —</option>` + sorted.map(u => {
        const label = u.display_name && u.display_name !== u.username
          ? `${u.display_name} (@${u.username})`
          : `@${u.username}`;
        const count = _allChars.filter(c => c.user_id === u.id).length;
        return `<option value="${u.id}">${_esc(label)}${count ? ` — ${count} postaci` : ""}</option>`;
      }).join("");
    } catch (err) {
      userSel.innerHTML = `<option value="">— błąd: ${_esc(err.message || err)} —</option>`;
      console.error("[debug picker] load failed:", err);
    }
  }

  userSel.addEventListener("change", () => {
    const uid = parseInt(userSel.value, 10);
    if (!uid) {
      charSel.innerHTML = `<option value="">— wybierz najpierw gracza —</option>`;
      charSel.disabled = true;
      idsEl.textContent = "";
      return;
    }
    const myChars = _allChars.filter(c => c.user_id === uid);
    if (!myChars.length) {
      charSel.innerHTML = `<option value="">— ten gracz nie ma postaci —</option>`;
      charSel.disabled = true;
      idsEl.textContent = "";
      return;
    }
    charSel.innerHTML = `<option value="">— wybierz postać —</option>` + myChars.map(c => {
      const camp = c.campaign_title ? ` · ${_esc(c.campaign_title)}` : "";
      return `<option value="${c.id}" data-campaign-id="${c.campaign_id ?? ""}">${_esc(c.name)} (#${c.id})${camp}</option>`;
    }).join("");
    charSel.disabled = false;
    idsEl.textContent = "";
  });

  charSel.addEventListener("change", () => {
    const cid = parseInt(charSel.value, 10);
    if (!cid) { idsEl.textContent = ""; return; }
    const opt = charSel.options[charSel.selectedIndex];
    const campId = parseInt(opt?.dataset.campaignId, 10) || "";

    // Auto-fill all matching inputs
    const psId = get("dbg-player-state-id");
    const gmCampId = get("dbg-gm-campaign-id");
    if (psId) psId.value = cid;
    if (gmCampId) gmCampId.value = campId;

    idsEl.innerHTML = `character_id: <code>${cid}</code>` +
                      (campId ? ` · campaign_id: <code>${campId}</code>` : ` · <em>brak aktywnej kampanii</em>`);
  });

  loadPicker();
}
