// Combat Sandbox — admin harness for testing combat mechanics.
// Reuses the production combat engine — anything verified here matches the game.
import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const TIER_LABEL = { minion: "Sługa", standard: "Standard", elite: "Elita", boss: "Boss" };
const ZONE_LABEL = { engaged: "Zwarcie", ranged: "Dystans" };
const STAT_LABEL = { STR: "SIŁ", DEX: "ZRC", CON: "KON", INT: "INT", WIS: "MĄD", CHA: "CHA", LCK: "SZC" };
const AUTO_ENEMY_DELAY_MS = 750;

let state = {
  heroes: [],
  enemies: [],
  selectedHero: null,
  selectedEnemies: new Set(),
  campaignId: null,
  characterId: null,
  combatState: null,
  characterFull: null,
  busy: false,
  autoEnemyTurnInFlight: false,
  d20Mode: "auto",
  d20Manual: 10,
  log: [],
  showSpellPicker: false,
};

export async function init(panel) {
  panel.innerHTML = layout();
  await refreshLookups(panel);
  bind(panel);
  renderHeroPicker(panel);
  renderEnemyPicker(panel);
  renderCombat(panel);
  renderSheet(panel);
}

function layout() {
  return `
    <div class="sandbox-root">
      <header class="sandbox-header">
        <h2>⚔ Combat Sandbox</h2>
        <p class="section-note">Testowanie mechaniki walki bez przechodzenia narracji. Używa prawdziwego silnika walki — co tu działa, działa też w grze. Tury wrogów odpalają się automatycznie.</p>
      </header>

      <div class="sandbox-grid">
        <!-- Column 1: setup + character sheet -->
        <section class="sandbox-col">
          <details class="sandbox-setup-details" id="sbx-setup-details" open>
            <summary><h3 style="display:inline">1. Konfiguracja</h3></summary>

            <div class="sandbox-subblock">
              <label class="sandbox-label">Bohater</label>
              <div class="sandbox-hero-picker" id="sbx-hero-picker"></div>
            </div>

            <div class="sandbox-subblock">
              <label class="sandbox-label">Przeciwnicy</label>
              <input type="search" id="sbx-enemy-search" class="sandbox-input" placeholder="Szukaj…" autocomplete="off" />
              <div class="sandbox-enemy-picker" id="sbx-enemy-picker"></div>
              <div class="sandbox-enemy-summary" id="sbx-enemy-summary"></div>
            </div>

            <div class="sandbox-subblock">
              <label class="sandbox-label">Rzut d20</label>
              <div class="sandbox-d20-mode">
                <label><input type="radio" name="sbx-d20" value="auto" checked /> Auto</label>
                <label><input type="radio" name="sbx-d20" value="manual" /> Ręczny</label>
                <input type="number" id="sbx-d20-val" min="1" max="20" value="10" disabled />
              </div>
            </div>

            <div class="sandbox-setup-actions">
              <button class="primary-btn" id="sbx-setup-btn">Przygotuj sandbox</button>
              <button class="primary-btn" id="sbx-start-btn" disabled>Rozpocznij walkę</button>
            </div>
          </details>

          <div class="sandbox-sheet-card" id="sbx-sheet-card" hidden>
            <h3>Karta bohatera</h3>
            <div id="sbx-sheet-body"></div>
          </div>
        </section>

        <!-- Column 2: live combat -->
        <section class="sandbox-col sandbox-combat" id="sbx-combat-pane">
          <h3>Stan walki</h3>
          <div id="sbx-combat-state" class="sandbox-combat-state">
            <p class="section-note sandbox-idle">Brak aktywnej walki. Wybierz bohatera + przeciwników i naciśnij <em>Rozpocznij walkę</em>.</p>
          </div>
          <div class="sandbox-actions" id="sbx-actions" hidden>
            <button class="combat-btn combat-btn--attack" id="sbx-attack-btn">⚔ Atak</button>
            <button class="combat-btn combat-btn--spell" id="sbx-spell-btn" hidden>✨ Czar</button>
            <button class="combat-btn combat-btn--move" id="sbx-move-btn">→ Zbliż się</button>
          </div>
          <div class="sandbox-spell-picker" id="sbx-spell-picker" hidden>
            <div class="sandbox-spell-header">
              <span>Wybierz zaklęcie</span>
              <button id="sbx-spell-close">✕</button>
            </div>
            <div id="sbx-spell-list"></div>
          </div>
          <div class="sandbox-meta-actions" id="sbx-meta-actions" hidden>
            <button id="sbx-enemy-btn">⏭ Tura wroga</button>
            <button id="sbx-end-btn">⏹ Zakończ</button>
          </div>
          <div class="sandbox-meta-actions sandbox-meta-actions--hero" id="sbx-hero-actions" hidden>
            <button id="sbx-reset-btn">↻ Pełne HP/Mana</button>
          </div>
        </section>

        <!-- Column 3: log -->
        <section class="sandbox-col sandbox-log-col">
          <h3>Log</h3>
          <pre class="sandbox-log" id="sbx-log"></pre>
        </section>
      </div>
    </div>
  `;
}

// ── Lookups ────────────────────────────────────────────────────────────────
async function refreshLookups(panel) {
  try {
    const [hRes, eRes] = await Promise.all([
      adminFetch("/api/admin/sandbox/heroes"),
      adminFetch("/api/admin/sandbox/enemies"),
    ]);
    state.heroes = hRes?.heroes || [];
    state.enemies = eRes?.enemies || [];
  } catch (e) {
    showToast("Błąd ładowania: " + (e.message || "?"), "error");
  }
}

function renderHeroPicker(panel) {
  const host = panel.querySelector("#sbx-hero-picker");
  if (!state.heroes.length) {
    host.innerHTML = `<p class="section-note">Brak aktywnych bohaterów.</p>`;
    return;
  }
  host.innerHTML = state.heroes.map((h) => {
    const sel = state.selectedHero === h.id ? " selected" : "";
    return `
      <button class="sandbox-hero-btn${sel}" data-hero-id="${h.id}">
        <div class="sandbox-hero-name">${esc(h.name)}</div>
        <div class="sandbox-hero-meta">${esc(h.archetype || "?")} · Lv${h.level || 1} · HP ${h.hp ?? "?"} / ${h.max_hp ?? "?"}</div>
      </button>`;
  }).join("");
  host.querySelectorAll(".sandbox-hero-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.selectedHero = Number(btn.dataset.heroId);
      renderHeroPicker(panel);
    });
  });
}

function renderEnemyPicker(panel) {
  const host = panel.querySelector("#sbx-enemy-picker");
  const q = (panel.querySelector("#sbx-enemy-search")?.value || "").trim().toLowerCase();
  const filtered = q
    ? state.enemies.filter((e) => (e.label || "").toLowerCase().includes(q) || (e.key || "").toLowerCase().includes(q))
    : state.enemies;
  if (!filtered.length) {
    host.innerHTML = `<p class="section-note">Brak dopasowań.</p>`;
  } else {
    host.innerHTML = filtered.map((e) => {
      const checked = state.selectedEnemies.has(e.key) ? " checked" : "";
      const tier = esc(TIER_LABEL[e.tier] || e.tier || "");
      return `
        <label class="sandbox-enemy-row" data-key="${esc(e.key)}">
          <input type="checkbox" data-key="${esc(e.key)}"${checked} />
          <span class="sandbox-enemy-label">${esc(e.label)}</span>
          <span class="sandbox-enemy-tier sandbox-enemy-tier--${esc(e.tier || "standard")}">${tier}</span>
          <span class="sandbox-enemy-stats">HP ${e.hp_base} · AC ${e.ac_base} · ${esc(e.damage_die)} +${e.attack_bonus}</span>
        </label>`;
    }).join("");
    host.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      cb.addEventListener("change", () => {
        const k = cb.dataset.key;
        if (cb.checked) state.selectedEnemies.add(k);
        else state.selectedEnemies.delete(k);
        renderEnemySummary(panel);
        updateStartButton(panel);
      });
    });
  }
  renderEnemySummary(panel);
}

function renderEnemySummary(panel) {
  const el = panel.querySelector("#sbx-enemy-summary");
  if (!el) return;
  el.textContent = state.selectedEnemies.size === 0 ? "Wybierz co najmniej jednego." : `Wybrano: ${state.selectedEnemies.size}`;
}

function updateStartButton(panel) {
  const btn = panel.querySelector("#sbx-start-btn");
  if (!btn) return;
  const ready = state.campaignId && state.characterId && state.selectedEnemies.size > 0 && !state.busy;
  btn.disabled = !ready;
  btn.classList.toggle("is-ready", !!ready);
}

// ── Bindings ──────────────────────────────────────────────────────────────
function bind(panel) {
  panel.querySelector("#sbx-enemy-search")?.addEventListener("input", () => renderEnemyPicker(panel));
  panel.querySelectorAll('input[name="sbx-d20"]').forEach((r) => {
    r.addEventListener("change", () => {
      state.d20Mode = r.value;
      const input = panel.querySelector("#sbx-d20-val");
      if (input) input.disabled = state.d20Mode !== "manual";
    });
  });
  panel.querySelector("#sbx-d20-val")?.addEventListener("input", (e) => {
    state.d20Manual = Math.max(1, Math.min(20, Number(e.target.value) || 10));
  });

  panel.querySelector("#sbx-setup-btn")?.addEventListener("click", () => doSetup(panel));
  panel.querySelector("#sbx-start-btn")?.addEventListener("click", () => doStartCombat(panel));
  panel.querySelector("#sbx-attack-btn")?.addEventListener("click", () => doAttack(panel));
  panel.querySelector("#sbx-spell-btn")?.addEventListener("click", () => toggleSpellPicker(panel, true));
  panel.querySelector("#sbx-spell-close")?.addEventListener("click", () => toggleSpellPicker(panel, false));
  panel.querySelector("#sbx-move-btn")?.addEventListener("click", () => doZoneChange(panel));
  panel.querySelector("#sbx-enemy-btn")?.addEventListener("click", () => doEnemyTurn(panel, /*manual*/ true));
  panel.querySelector("#sbx-reset-btn")?.addEventListener("click", () => doResetHero(panel));
  panel.querySelector("#sbx-end-btn")?.addEventListener("click", () => doEndCombat(panel));
}

// ── Setup / lifecycle ─────────────────────────────────────────────────────
async function doSetup(panel) {
  if (!state.selectedHero) { showToast("Wybierz bohatera.", "error"); return; }
  try {
    state.busy = true;
    // Clear any stale combat state from a prior session — backend ends it too
    state.combatState = null;
    state.autoEnemyTurnInFlight = false;
    const res = await adminFetch("/api/admin/sandbox/setup", { method: "POST", body: JSON.stringify({ hero_id: state.selectedHero }) });
    state.campaignId = res.campaign_id;
    state.characterId = res.character_id;
    logMsg(panel, `Setup ✓ — campaign #${res.campaign_id}, hero #${res.character_id} (${res.hero?.name}, ${res.hero?.archetype} Lv${res.hero?.level}). Wybierz wrogów i naciśnij Rozpocznij walkę.`);
    await refreshCharacterSheet(panel);
    renderCombat(panel);
    showToast("Sandbox gotowy. Wybierz przeciwników → Rozpocznij walkę.", "success");
  } catch (e) {
    showToast("Setup error: " + (e.message || "?"), "error");
  } finally {
    state.busy = false;
    updateStartButton(panel);
  }
}

async function doStartCombat(panel) {
  if (!state.campaignId || !state.characterId) { showToast("Najpierw setup.", "error"); return; }
  const enemies = Array.from(state.selectedEnemies);
  if (!enemies.length) { showToast("Wybierz przeciwników.", "error"); return; }
  state.busy = true;
  try {
    const res = await adminFetch("/api/admin/sandbox/start-combat", {
      method: "POST",
      body: JSON.stringify({ campaign_id: state.campaignId, character_id: state.characterId, enemy_keys: enemies }),
    });
    state.combatState = res.combat_state;
    logMsg(panel, `Walka rozpoczęta — runda ${res.combat_state?.round || 1}, kolejność: ${(res.combat_state?.turn_order || []).join(" → ")}`);
    const det = panel.querySelector("#sbx-setup-details");
    if (det) det.open = false;
    await refreshCharacterSheet(panel);
  } catch (e) {
    showToast("Start error: " + (e.message || "?"), "error");
  } finally {
    state.busy = false;
    renderCombat(panel);
    maybeAutoEnemyTurn(panel);
  }
}

async function refreshCombatState(panel) {
  if (!state.campaignId) return;
  try {
    const res = await adminFetch(`/api/campaigns/${state.campaignId}/combat`);
    state.combatState = res?.active ? res.combat : (state.combatState && state.combatState.status === "ended" ? state.combatState : null);
  } catch {}
  // Note: caller is responsible for triggering renderCombat after busy is
  // reset; we deliberately don't render here to avoid drawing stale
  // disabled-button states while busy=true.
}

async function refreshCharacterSheet(panel) {
  if (!state.characterId) return;
  try {
    state.characterFull = await adminFetch(`/api/admin/sandbox/character/${state.characterId}`);
  } catch (e) {
    state.characterFull = null;
  }
  renderSheet(panel);
}

// ── Combat actions ────────────────────────────────────────────────────────
function rollD20() {
  return state.d20Mode === "manual" ? state.d20Manual : (Math.floor(Math.random() * 20) + 1);
}

async function doAttack(panel, spellKey = null) {
  if (!state.combatState) return;
  const d20 = rollD20();
  const body = { roll_result: d20, raw_d20: d20, attacker: "player" };
  if (spellKey) body.spell_key = spellKey;
  state.busy = true;
  try {
    const res = await adminFetch(`/api/campaigns/${state.campaignId}/combat/resolve-attack`, { method: "POST", body: JSON.stringify(body) });
    state.combatState = res.combat_state;
    const kind = spellKey ? `Czar:${spellKey}` : "Atak";
    let line;
    if (res.blocked) line = `BLOKADA: ${res.message || res.block_reason}`;
    else if (res.miscast) line = `MISCAST! ${res.miscast.message || "spell failed"}`;
    else if (res.hit) line = `Trafienie! ${res.damage || 0} obrażeń → ${res.target_name || "wróg"} (rzut ${d20})`;
    else line = `Pudło (rzut ${d20})${res.player_nat1 ? " — Nat 1!" : ""}`;
    logMsg(panel, `[${kind}] ${line}`);
    if (res.combat_state?.status === "ended") logMsg(panel, `Walka: ${res.combat_state.ended_reason}.`);
    await refreshCharacterSheet(panel);
  } catch (e) {
    logMsg(panel, "Błąd: " + (e.message || "?"));
  } finally {
    state.busy = false;
    renderCombat(panel);
    maybeAutoEnemyTurn(panel);
  }
}

async function doZoneChange(panel) {
  state.busy = true;
  try {
    const res = await adminFetch(`/api/campaigns/${state.campaignId}/combat/zone-change`, { method: "POST" });
    state.combatState = res.combat_state;
    logMsg(panel, `[Zone] ${res.from} → ${res.to}`);
  } catch (e) {
    logMsg(panel, "Zone error: " + (e.message || "?"));
  } finally {
    state.busy = false;
    renderCombat(panel);
    maybeAutoEnemyTurn(panel);
  }
}

async function doEnemyTurn(panel, manual = false) {
  if (state.autoEnemyTurnInFlight && !manual) return;
  state.autoEnemyTurnInFlight = true;
  state.busy = true;
  try {
    const res = await adminFetch(`/api/campaigns/${state.campaignId}/combat/enemy-turn`, { method: "POST" });
    state.combatState = res.combat_state || state.combatState;
    if (res.zone_change) {
      logMsg(panel, `[Wróg] ${res.enemy_name || "?"} szarżuje (${res.zone_change.from} → ${res.zone_change.to})`);
    } else if (res.hit) {
      logMsg(panel, `[Wróg] ${res.enemy_name || "?"} trafia za ${res.damage || 0} (rzut ${res.raw_d20 ?? "?"})`);
    } else if (res.blocked) {
      logMsg(panel, `[Wróg] zablokowany — ${res.message || "?"}`);
    } else if (res.enemy_name) {
      logMsg(panel, `[Wróg] ${res.enemy_name} pudłuje (rzut ${res.raw_d20 ?? "?"})`);
    }
    await refreshCombatState(panel);
    await refreshCharacterSheet(panel);
  } catch (e) {
    logMsg(panel, "Enemy turn error: " + (e.message || "?"));
  } finally {
    state.autoEnemyTurnInFlight = false;
    state.busy = false;
    renderCombat(panel);
    maybeAutoEnemyTurn(panel);
  }
}

function maybeAutoEnemyTurn(panel) {
  const cs = state.combatState;
  if (!cs || cs.status !== "active") return;
  if (String(cs.current_turn) === "player") return;
  if (state.autoEnemyTurnInFlight) return;
  setTimeout(() => {
    // Re-check before firing — state may have changed
    const cur = state.combatState;
    if (cur && cur.status === "active" && String(cur.current_turn) !== "player" && !state.autoEnemyTurnInFlight) {
      doEnemyTurn(panel, /*manual*/ false);
    }
  }, AUTO_ENEMY_DELAY_MS);
}

async function doResetHero(panel) {
  try {
    const res = await adminFetch("/api/admin/sandbox/reset-hero", { method: "POST", body: JSON.stringify({ character_id: state.characterId }) });
    logMsg(panel, `Reset HP ${res.hp}/${res.max_hp}${res.max_mana ? ` · Mana ${res.mana}/${res.max_mana}` : ""}`);
    await refreshCombatState(panel);
    await refreshCharacterSheet(panel);
    showToast("Bohater zregenerowany.", "success");
  } catch (e) {
    showToast("Reset error: " + (e.message || "?"), "error");
  }
}

async function doEndCombat(panel) {
  if (!confirm("Zakończyć walkę?")) return;
  try {
    await adminFetch("/api/admin/sandbox/end-combat", { method: "POST", body: JSON.stringify({ campaign_id: state.campaignId }) });
    state.combatState = null;
    logMsg(panel, "Walka zakończona ręcznie.");
    renderCombat(panel);
  } catch (e) {
    showToast("End error: " + (e.message || "?"), "error");
  }
}

// ── Inventory / spell actions ──────────────────────────────────────────────
async function doEquip(panel, inventoryId, slot) {
  try {
    await adminFetch(`/api/inventory/${state.characterId}/equip`, { method: "POST", body: JSON.stringify({ inventory_id: inventoryId, slot }) });
    logMsg(panel, `[Ekwipunek] założono #${inventoryId} → slot ${slot || "(unequip)"}`);
    await refreshCharacterSheet(panel);
  } catch (e) {
    logMsg(panel, "Equip error: " + (e.message || "?"));
  }
}

async function doUseConsumable(panel, inventoryId, label) {
  try {
    const res = await adminFetch(`/api/inventory/${state.characterId}/use`, { method: "POST", body: JSON.stringify({ inventory_id: inventoryId }) });
    logMsg(panel, `[Mikstura] użyto ${esc(label)} — ${JSON.stringify(res?.data || {}).slice(0, 80)}`);
    await refreshCharacterSheet(panel);
    await refreshCombatState(panel);
  } catch (e) {
    logMsg(panel, "Use error: " + (e.message || "?"));
  }
}

function toggleSpellPicker(panel, open) {
  state.showSpellPicker = !!open;
  const el = panel.querySelector("#sbx-spell-picker");
  if (!el) return;
  el.hidden = !open;
  if (open) renderSpellPicker(panel);
}

function renderSpellPicker(panel) {
  const list = panel.querySelector("#sbx-spell-list");
  if (!list) return;
  const spells = state.characterFull?.spells || [];
  const curMana = state.characterFull?.mana ?? 0;
  if (!spells.length) {
    list.innerHTML = `<p class="section-note">Bohater nie zna żadnych zaklęć.</p>`;
    return;
  }
  list.innerHTML = spells.map((s) => {
    const cost = s.mana_cost ?? s.effective_mana_cost ?? 0;
    const enabled = curMana >= cost;
    const tag = s.spell_type === "attack" ? "atak" : (s.spell_type || "");
    return `
      <button class="sandbox-spell-btn" data-spell-key="${esc(s.spell_key || s.key)}" ${enabled ? "" : "disabled"}>
        <span class="sandbox-spell-name">${esc(s.label || s.spell_key || s.key)}</span>
        <span class="sandbox-spell-cost">${cost} M</span>
        <span class="sandbox-spell-tag">${esc(tag)}</span>
      </button>`;
  }).join("");
  list.querySelectorAll(".sandbox-spell-btn").forEach((b) => {
    b.addEventListener("click", () => {
      const k = b.dataset.spellKey;
      toggleSpellPicker(panel, false);
      doAttack(panel, k);
    });
  });
}

// ── Renderers ─────────────────────────────────────────────────────────────
function renderCombat(panel) {
  const host = panel.querySelector("#sbx-combat-state");
  const actions = panel.querySelector("#sbx-actions");
  const meta = panel.querySelector("#sbx-meta-actions");
  const sheetCard = panel.querySelector("#sbx-sheet-card");
  if (!host) return;
  const cs = state.combatState;

  if (sheetCard) sheetCard.hidden = !state.characterId;

  if (!cs || cs.status !== "active") {
    let hint;
    if (cs?.status === "ended") {
      hint = `Walka zakończona (${esc(cs.ended_reason || "?")}). Naciśnij <em>Rozpocznij walkę</em>, aby zacząć kolejną.`;
    } else if (state.characterId && state.selectedEnemies.size > 0) {
      hint = `<span class="sandbox-idle--ready">Sandbox gotowy. Naciśnij <em>Rozpocznij walkę</em> ↖</span>`;
    } else if (state.characterId) {
      hint = `Sandbox przygotowany. Wybierz przeciwników po lewej i naciśnij <em>Rozpocznij walkę</em>.`;
    } else {
      hint = `Brak aktywnej walki. Wybierz bohatera + przeciwników i naciśnij <em>Rozpocznij walkę</em>.`;
    }
    host.innerHTML = `<p class="section-note sandbox-idle">${hint}</p>`;
    // Combat-time buttons stay hidden until combat is genuinely active
    if (actions) actions.hidden = true;
    if (meta) meta.hidden = true;
    // Hero-action (Reset) is available whenever a hero is bound to the sandbox
    const heroActions = panel.querySelector("#sbx-hero-actions");
    if (heroActions) heroActions.hidden = !state.characterId;
    return;
  }
  actions.hidden = false;
  meta.hidden = false;
  const heroActions = panel.querySelector("#sbx-hero-actions");
  if (heroActions) heroActions.hidden = !state.characterId;

  const cmb = Array.isArray(cs.combatants) ? cs.combatants : [];
  const player = cmb.find((c) => c.type === "player") || {};
  const enemies = cmb.filter((c) => c.type === "enemy");
  const order = Array.isArray(cs.turn_order) ? cs.turn_order : [];
  const cur = String(cs.current_turn || "");
  const playerTurn = cur === "player";

  const renderRow = (c) => {
    const hp = `${c.hp_current ?? "?"}/${c.hp_max ?? "?"}`;
    const isCur = String(c.id) === cur;
    const zone = ZONE_LABEL[c.zone] || c.zone || "";
    const ini = c.initiative_roll != null ? `INI ${c.initiative_roll}` : "";
    const downed = (c.hp_current ?? 0) <= 0;
    return `
      <div class="sandbox-row${isCur ? " sandbox-row--active" : ""}${downed ? " sandbox-row--down" : ""}">
        <span class="sandbox-row-icon">${c.type === "player" ? "🛡" : (downed ? "💀" : "⚔")}</span>
        <span class="sandbox-row-name">${esc(c.name || c.id || "?")}</span>
        <span class="sandbox-row-meta">${ini} · ${esc(zone)} · AC ${c.defense ?? "?"}</span>
        <span class="sandbox-row-hp">${hp}</span>
      </div>`;
  };

  host.innerHTML = `
    <div class="sandbox-summary">
      <span><b>Runda ${cs.round || 1}</b></span>
      <span class="${playerTurn ? "sandbox-tag-good" : "sandbox-tag-bad"}">${playerTurn ? "Tura gracza" : `Tura: ${esc(cur)}…`}</span>
      <span class="sandbox-order">${order.map((id) => `<code${String(id) === cur ? ' class="active"' : ""}>${esc(id)}</code>`).join(" → ")}</span>
    </div>
    <div class="sandbox-roster">
      ${renderRow(player)}
      ${enemies.map(renderRow).join("")}
    </div>
  `;

  // Buttons
  const moveBtn = panel.querySelector("#sbx-move-btn");
  if (moveBtn) {
    moveBtn.textContent = player.zone === "engaged" ? "← Cofnij się" : "→ Zbliż się";
    moveBtn.disabled = !playerTurn || state.busy;
  }
  const atkBtn = panel.querySelector("#sbx-attack-btn");
  if (atkBtn) atkBtn.disabled = !playerTurn || state.busy;
  const spellBtn = panel.querySelector("#sbx-spell-btn");
  if (spellBtn) {
    spellBtn.hidden = String(state.characterFull?.archetype || "").toLowerCase() !== "scholar";
    spellBtn.disabled = !playerTurn || state.busy;
  }
  const enemyBtn = panel.querySelector("#sbx-enemy-btn");
  if (enemyBtn) enemyBtn.disabled = playerTurn || state.busy;
}

function renderSheet(panel) {
  const host = panel.querySelector("#sbx-sheet-body");
  const card = panel.querySelector("#sbx-sheet-card");
  if (!host || !card) return;
  if (!state.characterFull) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  const ch = state.characterFull;
  const hpPct = ch.max_hp ? Math.max(0, Math.min(100, Math.round((ch.hp / ch.max_hp) * 100))) : 0;
  const manaPct = ch.max_mana ? Math.max(0, Math.min(100, Math.round((ch.mana / ch.max_mana) * 100))) : 0;

  const statsRow = Object.keys(STAT_LABEL).map((k) => {
    const v = ch.stats?.[k] ?? "—";
    const mod = (typeof v === "number") ? Math.floor((v - 10) / 2) : null;
    const sign = mod !== null && mod >= 0 ? "+" : "";
    return `<div class="sbx-stat"><span class="sbx-stat-k">${STAT_LABEL[k]}</span><span class="sbx-stat-v">${v}</span><span class="sbx-stat-m">${mod === null ? "" : sign + mod}</span></div>`;
  }).join("");

  const conditions = Array.isArray(ch.conditions) ? ch.conditions : [];
  const condRow = conditions.length
    ? `<div class="sbx-conditions">${conditions.map((c) => `<span class="sbx-cond">${esc(typeof c === "string" ? c : (c.key || c.label || "?"))}</span>`).join("")}</div>`
    : `<div class="sbx-conditions sbx-conditions--empty">— brak —</div>`;

  // Inventory: flat list with item_type field. Group it client-side.
  const invList = Array.isArray(ch.inventory) ? ch.inventory : [];
  const groups = { weapon: [], armor: [], consumable: [], item: [], narrative: [] };
  for (const r of invList) {
    const t = String(r.item_type || "item");
    (groups[t] || groups.item).push(r);
  }
  const renderInvSection = (title, rows, type) => {
    if (!rows || !rows.length) return "";
    return `
      <div class="sbx-inv-section">
        <div class="sbx-inv-h">${title}</div>
        ${rows.map((r) => {
          const id = r.id;
          const lbl = esc(r.label || r.key || "?");
          const qty = r.quantity > 1 ? ` ×${r.quantity}` : "";
          const equippedSlot = r.equipped ? (r.slot || "—") : null;
          const equippedTag = equippedSlot ? `<span class="sbx-eq">${esc(equippedSlot)}</span>` : "";
          let actions = "";
          if (type === "weapon") {
            actions = r.equipped
              ? `<button data-action="unequip" data-id="${id}">Zdejmij</button>`
              : `<button data-action="equip" data-id="${id}" data-slot="main_hand">Załóż</button>`;
          } else if (type === "armor") {
            actions = r.equipped
              ? `<button data-action="unequip" data-id="${id}">Zdejmij</button>`
              : `<button data-action="equip" data-id="${id}" data-slot="${esc(r.slot || "body")}">Załóż</button>`;
          } else if (type === "consumable" && r.can_use !== false) {
            actions = `<button data-action="use" data-id="${id}" data-label="${esc(r.label || r.key)}">Użyj</button>`;
          }
          return `<div class="sbx-inv-row">${equippedTag}<span class="sbx-inv-name">${lbl}${qty}</span><span class="sbx-inv-actions">${actions}</span></div>`;
        }).join("")}
      </div>`;
  };

  host.innerHTML = `
    <div class="sbx-sheet-head">
      <div class="sbx-sheet-name">${esc(ch.name)} <small>${esc(ch.archetype || "?")} Lv${ch.level}</small></div>
      <div class="sbx-sheet-gold">💰 ${ch.gold_gp || 0} GP</div>
    </div>

    <div class="sbx-bars">
      <div class="sbx-bar">
        <div class="sbx-bar-label">HP <span>${ch.hp}/${ch.max_hp}</span></div>
        <div class="sbx-bar-track"><div class="sbx-bar-fill sbx-bar-fill--hp" style="width:${hpPct}%"></div></div>
      </div>
      ${ch.max_mana ? `
      <div class="sbx-bar">
        <div class="sbx-bar-label">Mana <span>${ch.mana}/${ch.max_mana}</span></div>
        <div class="sbx-bar-track"><div class="sbx-bar-fill sbx-bar-fill--mana" style="width:${manaPct}%"></div></div>
      </div>` : ""}
    </div>

    <div class="sbx-stats-grid">${statsRow}</div>

    <div class="sbx-section-title">Stany</div>
    ${condRow}

    <div class="sbx-section-title">Ekwipunek</div>
    ${renderInvSection("Broń", groups.weapon, "weapon")}
    ${renderInvSection("Pancerz", groups.armor, "armor")}
    ${renderInvSection("Mikstury / zwoje", groups.consumable, "consumable")}
    ${renderInvSection("Inne", groups.item, "item")}
    ${renderInvSection("Narracyjne", groups.narrative, "narrative")}
    ${invList.length === 0 ? `<div class="sbx-conditions sbx-conditions--empty">— pusty —</div>` : ""}

    ${(ch.spells && ch.spells.length) ? `
      <div class="sbx-section-title">Zaklęcia</div>
      <div class="sbx-spells-list">
        ${ch.spells.map((s) => `<span class="sbx-spell-chip" title="${esc(s.label || s.spell_key)} (${s.mana_cost ?? "?"} M)">${esc(s.label || s.spell_key)} <small>R${s.rank || 1}</small></span>`).join("")}
      </div>` : ""}
  `;

  host.querySelectorAll("button[data-action]").forEach((b) => {
    const action = b.dataset.action;
    const id = Number(b.dataset.id);
    if (action === "equip") b.addEventListener("click", () => doEquip(panel, id, b.dataset.slot));
    else if (action === "unequip") b.addEventListener("click", () => doEquip(panel, id, ""));
    else if (action === "use") b.addEventListener("click", () => doUseConsumable(panel, id, b.dataset.label));
  });
}

function logMsg(panel, line) {
  state.log.unshift(`[${new Date().toLocaleTimeString("pl-PL")}] ${line}`);
  if (state.log.length > 80) state.log.pop();
  const el = panel.querySelector("#sbx-log");
  if (el) el.textContent = state.log.join("\n");
}
