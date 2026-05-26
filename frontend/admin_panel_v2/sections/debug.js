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
  viewHuman:       "📖 Czytelne",
  viewJson:        "⚙ JSON",
};

// ── Human-readable formatters per endpoint ─────────────────────────────────

function fmtPlayerState(d) {
  if (!d || typeof d !== "object") return _esc(String(d ?? "—"));
  const lines = [];
  lines.push(`<strong>👤 Postać #${d.character_id}</strong>`);
  if (d.location) lines.push(`📍 Lokacja: <code>${_esc(d.location)}</code>`);
  lines.push(`❤ HP: ${d.hp}/${d.max_hp}`);
  lines.push(`💰 Złoto: ${d.gold_gp} gp`);
  const inv = d.inventory || [];
  lines.push("");
  lines.push(`<strong>📦 Ekwipunek (${inv.length})</strong>`);
  if (!inv.length) lines.push("  <em>— pusto —</em>");
  else inv.forEach(it => lines.push(`  • ${_esc(it.item_key)}${it.slot ? ` <em>(${_esc(it.slot)})</em>` : ""}`));
  const qa = d.quests_active || [];
  if (qa.length) {
    lines.push("");
    lines.push(`<strong>⚡ Aktywne questy (${qa.length})</strong>`);
    qa.forEach(q => lines.push(`  • ${_esc(q)}`));
  }
  const qc = d.quests_completed || [];
  if (qc.length) {
    lines.push("");
    lines.push(`<strong>✓ Ukończone questy (${qc.length})</strong>`);
    qc.forEach(q => lines.push(`  • ${_esc(q)}`));
  }
  return lines.join("\n");
}

function fmtGmDecisions(d) {
  if (!d || !Array.isArray(d.decisions)) return _esc(String(d ?? "—"));
  const lines = [];
  lines.push(`<strong>Sesja #${_esc(d.session_id)} · ${d.decisions.length} decyzji</strong>`);
  lines.push("");
  if (!d.decisions.length) {
    lines.push("<em>— brak tur —</em>");
    return lines.join("\n");
  }
  d.decisions.forEach(dec => {
    const date = dec.created_at ? new Date(dec.created_at).toLocaleString("pl") : "?";
    lines.push(`<strong>Tura ${dec.turn_number ?? "?"}</strong> · <code>${_esc(dec.type || dec.route || "?")}</code> · <span style="color:var(--text-muted)">${_esc(date)}</span>`);
    if (dec.reason) lines.push(`  <em>powód: ${_esc(dec.reason)}</em>`);
    if (dec.user_text) lines.push(`  <span style="color:#7aa6e6">🗣 Gracz:</span> ${_esc(_truncate(dec.user_text, 180))}`);
    if (dec.assistant_text) lines.push(`  <span style="color:#c9a54a">📜 GM:</span> ${_esc(_truncate(dec.assistant_text, 220))}`);
    lines.push("");
  });
  return lines.join("\n");
}

function fmtValidation(d) {
  if (!d || typeof d !== "object") return _esc(String(d ?? "—"));
  const lines = [];
  if (d.test_run_id) lines.push(`<strong>test_run_id:</strong> <code>${_esc(d.test_run_id)}</code>`);
  const flags = Array.isArray(d.flags) ? d.flags : (d.validation_flags || []);
  lines.push(`<strong>Flagi (${flags.length})</strong>`);
  if (!flags.length) lines.push("  <em>— brak flag —</em>");
  else flags.forEach(f => {
    if (typeof f === "string") lines.push(`  • ${_esc(f)}`);
    else {
      const ok = f.passed === true || f.ok === true;
      const icon = ok ? "✓" : (f.passed === false || f.ok === false ? "✗" : "•");
      const color = ok ? "#4caf78" : (f.passed === false ? "#c94a4a" : "");
      lines.push(`  <span style="color:${color}">${icon}</span> ${_esc(f.name || f.flag || JSON.stringify(f))}${f.message ? ` — <em>${_esc(f.message)}</em>` : ""}`);
    }
  });
  return lines.join("\n");
}

function fmtFeatureFlags(d) {
  if (!d || typeof d !== "object") return _esc(String(d ?? "—"));
  const entries = Object.entries(d).filter(([k]) => k !== "ok" && !k.startsWith("_"));
  if (!entries.length) return "<em>— brak flag —</em>";
  const lines = [`<strong>Feature flags (${entries.length})</strong>`, ""];
  entries.forEach(([k, v]) => {
    let icon, color;
    if (v === true)       { icon = "✓"; color = "#4caf78"; }
    else if (v === false) { icon = "✗"; color = "#c94a4a"; }
    else                  { icon = "•"; color = "var(--text-muted)"; }
    const val = typeof v === "object" ? JSON.stringify(v) : String(v);
    lines.push(`  <span style="color:${color}">${icon}</span> <strong>${_esc(k)}</strong>: <code>${_esc(val)}</code>`);
  });
  return lines.join("\n");
}

function fmtGeneric(d) {
  if (!d || typeof d !== "object") return _esc(String(d ?? "—"));
  const lines = [];
  Object.entries(d).forEach(([k, v]) => {
    const valStr = typeof v === "object" ? JSON.stringify(v, null, 2) : String(v);
    lines.push(`<strong>${_esc(k)}:</strong> <code>${_esc(valStr)}</code>`);
  });
  return lines.join("\n");
}

function _truncate(s, n) {
  const str = String(s ?? "");
  return str.length > n ? str.slice(0, n) + "…" : str;
}

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
        <div class="debug-view-toggle" data-target="dbg-player-state-out">
          <button type="button" class="dvt-btn dvt-btn--active" data-mode="human">${LABELS.viewHuman}</button>
          <button type="button" class="dvt-btn" data-mode="json">${LABELS.viewJson}</button>
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
        <div class="debug-view-toggle" data-target="dbg-gm-out">
          <button type="button" class="dvt-btn dvt-btn--active" data-mode="human">${LABELS.viewHuman}</button>
          <button type="button" class="dvt-btn" data-mode="json">${LABELS.viewJson}</button>
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
        <div class="debug-view-toggle" data-target="dbg-val-out">
          <button type="button" class="dvt-btn dvt-btn--active" data-mode="human">${LABELS.viewHuman}</button>
          <button type="button" class="dvt-btn" data-mode="json">${LABELS.viewJson}</button>
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
        <div class="debug-view-toggle" data-target="dbg-ff-out">
          <button type="button" class="dvt-btn dvt-btn--active" data-mode="human">${LABELS.viewHuman}</button>
          <button type="button" class="dvt-btn" data-mode="json">${LABELS.viewJson}</button>
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
        <div class="debug-view-toggle" data-target="dbg-reset-out">
          <button type="button" class="dvt-btn dvt-btn--active" data-mode="human">${LABELS.viewHuman}</button>
          <button type="button" class="dvt-btn" data-mode="json">${LABELS.viewJson}</button>
        </div>
        <pre class="debug-output" id="dbg-reset-out">${LABELS.emptyResult}</pre>
      </div>

      <!-- Fallen Heroes → NPC promotion -->
      <div class="card debug-card" style="grid-column: 1 / -1">
        <h3 class="card-title">🪦 Fallen Heroes — promocja do NPC</h3>
        <p class="card-hint">Bohaterowie, których ostatnia kampania zakończyła się śmiercią. Można ich awansować na trwałe NPC dla ciągłości narracji.</p>
        <div class="debug-row">
          <button type="button" class="primary-btn" id="dbg-fallen-refresh">↻ Odśwież listę</button>
        </div>
        <div id="dbg-fallen-list" class="fallen-list">
          <em style="color:var(--text-muted)">Kliknij «Odśwież listę» aby załadować.</em>
        </div>
      </div>

    </div>
  `;

  const get = (id) => panel.querySelector(`#${id}`);

  // Per-output state: { data, formatter, mode }
  const outputs = new Map();

  function renderOutput(outId) {
    const state = outputs.get(outId);
    const out = get(outId);
    if (!out || !state) return;
    if (state.error) { out.textContent = state.error; return; }
    if (state.data == null) { out.textContent = LABELS.emptyResult; return; }
    if (state.mode === "human" && state.formatter) {
      out.innerHTML = state.formatter(state.data);
    } else {
      out.textContent = _renderJson(state.data);
    }
  }

  async function call(out, fn, formatter = fmtGeneric) {
    const outId = out.id;
    out.textContent = LABELS.loading;
    const prev = outputs.get(outId) || {};
    outputs.set(outId, { ...prev, data: null, error: null, formatter });
    try {
      const data = await fn();
      outputs.set(outId, { ...outputs.get(outId), data });
      renderOutput(outId);
    } catch (e) {
      outputs.set(outId, { ...outputs.get(outId), error: `Błąd: ${e?.message || e}` });
      renderOutput(outId);
      showToast(`Debug: ${e?.message || e}`, "error");
    }
  }

  // Wire up view-mode toggles for every output
  panel.querySelectorAll(".debug-view-toggle").forEach(group => {
    const targetId = group.dataset.target;
    // Initialize state with default mode = human
    outputs.set(targetId, { data: null, error: null, formatter: fmtGeneric, mode: "human" });
    group.querySelectorAll(".dvt-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        group.querySelectorAll(".dvt-btn").forEach(b => b.classList.toggle("dvt-btn--active", b === btn));
        const state = outputs.get(targetId) || {};
        outputs.set(targetId, { ...state, mode: btn.dataset.mode });
        renderOutput(targetId);
      });
    });
  });

  get("dbg-player-state-go").addEventListener("click", () => {
    const id = parseInt(get("dbg-player-state-id").value, 10);
    if (!id) { showToast(`Podaj ${LABELS.charIdLabel}`, "error"); return; }
    call(get("dbg-player-state-out"), () => adminFetch(`/api/debug/player_state?character_id=${id}`), fmtPlayerState);
  });

  get("dbg-gm-go").addEventListener("click", () => {
    const cid = parseInt(get("dbg-gm-campaign-id").value, 10);
    const limit = parseInt(get("dbg-gm-limit").value, 10) || 20;
    if (!cid) { showToast(`Podaj ${LABELS.campaignIdLabel}`, "error"); return; }
    call(get("dbg-gm-out"), () => adminFetch(`/api/debug/gm_decisions?session_id=${cid}&limit=${limit}`), fmtGmDecisions);
  });

  get("dbg-val-go").addEventListener("click", () => {
    const runId = get("dbg-val-run-id").value.trim();
    if (!runId) { showToast(`Podaj ${LABELS.runIdLabel}`, "error"); return; }
    call(get("dbg-val-out"), () => adminFetch(`/api/debug/validation_flags?test_run_id=${encodeURIComponent(runId)}`), fmtValidation);
  });

  get("dbg-ff-go").addEventListener("click", () => {
    call(get("dbg-ff-out"), () => adminFetch(`/api/debug/settings/feature_flags`), fmtFeatureFlags);
  });

  get("dbg-reset-go").addEventListener("click", async () => {
    if (!confirm("Reset środowiska testowego? Operacja nieodwracalna.")) return;
    await call(get("dbg-reset-out"), () => adminFetch(`/api/debug/reset_test_env`, { method: "POST" }), fmtGeneric);
    showToast("Test env reset wysłany.", "success");
  });

  // Auto-fetch feature flags on first load — gives a non-empty screen immediately.
  call(get("dbg-ff-out"), () => adminFetch(`/api/debug/settings/feature_flags`), fmtFeatureFlags);

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

    // Auto-fetch everything that has enough info
    get("dbg-player-state-go")?.click();
    if (campId) get("dbg-gm-go")?.click();
    // Feature flags don't depend on selection, but refresh too for a complete snapshot
    get("dbg-ff-go")?.click();
  });

  loadPicker();

  // ── Fallen Heroes → NPC promotion ─────────────────────────────────────────
  async function loadFallenHeroes() {
    const listEl = get("dbg-fallen-list");
    if (!listEl) return;
    listEl.innerHTML = `<em style="color:var(--text-muted)">Wczytywanie…</em>`;
    try {
      const { items } = await adminFetch("/api/admin/characters/fallen");
      if (!items.length) {
        listEl.innerHTML = `<em style="color:var(--text-muted)">— brak poległych bohaterów —</em>`;
        return;
      }
      listEl.innerHTML = items.map(h => `
        <div class="fallen-hero-row" data-char-id="${h.character_id}">
          <div class="fallen-hero-info">
            <strong>${_esc(h.name)}</strong>
            <span class="fallen-hero-campaign">📖 ${_esc(h.campaign_title || "—")}</span>
            <span class="fallen-hero-reason">⚔ ${_esc(h.death_reason || "—")}</span>
            ${h.epitaph ? `<em class="fallen-hero-epitaph">"${_esc(h.epitaph)}"</em>` : ""}
          </div>
          <div class="fallen-hero-actions">
            ${h.already_promoted
              ? `<span class="fallen-promoted-badge" title="NPC: ${_esc(h.npc_key || '')}">✓ NPC: <code>${_esc(h.npc_key || '')}</code></span>`
              : `<button type="button" class="primary-btn fallen-promote-btn" data-char-id="${h.character_id}" data-name="${_esc(h.name)}">🪦 Awansuj na NPC</button>`
            }
          </div>
        </div>
      `).join("");

      listEl.querySelectorAll(".fallen-promote-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          const cid = parseInt(btn.dataset.charId, 10);
          const name = btn.dataset.name;
          if (!confirm(`Awansować "${name}" na trwałe NPC?`)) return;
          btn.disabled = true; btn.textContent = "Przetwarzam…";
          try {
            const res = await adminFetch(`/api/admin/characters/${cid}/promote-to-npc`, { method: "POST" });
            showToast(`NPC utworzony: ${res.npc_key}`, "success");
            await loadFallenHeroes();
          } catch (e) {
            showToast(`Błąd: ${e?.message || e}`, "error");
            btn.disabled = false; btn.textContent = "🪦 Awansuj na NPC";
          }
        });
      });
    } catch (e) {
      listEl.innerHTML = `<em style="color:var(--danger,#c94a4a)">Błąd: ${_esc(e?.message || String(e))}</em>`;
    }
  }

  get("dbg-fallen-refresh")?.addEventListener("click", loadFallenHeroes);
}
