// Combat Sandbox — admin harness for testing combat mechanics
// without going through the narrative pipeline.
import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const TIER_LABEL = { minion: "Sługa", standard: "Standard", elite: "Elita", boss: "Boss" };
const ZONE_LABEL = { engaged: "Zwarcie", ranged: "Dystans" };

let state = {
  heroes: [],
  enemies: [],
  selectedHero: null,
  selectedEnemies: new Set(),
  campaignId: null,
  characterId: null,
  combatState: null,
  busy: false,
  d20Mode: "auto", // "auto" | "manual"
  d20Manual: 10,
  log: [],
};

export async function init(panel) {
  panel.innerHTML = layout();
  await refreshLookups(panel);
  bind(panel);
  renderHeroPicker(panel);
  renderEnemyPicker(panel);
  renderCombat(panel);
}

function layout() {
  return `
    <div class="sandbox-root">
      <header class="sandbox-header">
        <h2>⚔ Combat Sandbox</h2>
        <p class="section-note">Testowanie mechaniki walki bez przechodzenia narracji. Używa prawdziwego silnika walki — co tu działa, działa też w grze.</p>
      </header>

      <div class="sandbox-grid">
        <!-- Column 1: setup -->
        <section class="sandbox-col sandbox-setup">
          <h3>1. Bohater</h3>
          <div class="sandbox-hero-picker" id="sbx-hero-picker"></div>

          <h3 style="margin-top:18px">2. Przeciwnicy</h3>
          <input type="search" id="sbx-enemy-search" class="sandbox-input" placeholder="Szukaj przeciwnika…" autocomplete="off" />
          <div class="sandbox-enemy-picker" id="sbx-enemy-picker"></div>
          <div class="sandbox-enemy-summary" id="sbx-enemy-summary"></div>

          <h3 style="margin-top:18px">3. Rzut d20</h3>
          <div class="sandbox-d20-mode">
            <label><input type="radio" name="sbx-d20" value="auto" checked /> Automatyczny</label>
            <label><input type="radio" name="sbx-d20" value="manual" /> Ręczny</label>
            <input type="number" id="sbx-d20-val" min="1" max="20" value="10" disabled />
          </div>

          <div class="sandbox-setup-actions">
            <button class="primary-btn" id="sbx-setup-btn">Przygotuj sandbox</button>
            <button class="primary-btn" id="sbx-start-btn" disabled>Rozpocznij walkę</button>
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
            <button class="combat-btn combat-btn--flee" id="sbx-enemy-btn">⏭ Wymuś turę wroga</button>
          </div>
          <div class="sandbox-meta-actions" id="sbx-meta-actions" hidden>
            <button id="sbx-reset-btn">↻ Pełne HP/Mana</button>
            <button id="sbx-end-btn">⏹ Zakończ walkę</button>
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
      </button>
    `;
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
        </label>
      `;
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
  const n = state.selectedEnemies.size;
  el.textContent = n === 0 ? "Wybierz co najmniej jednego." : `Wybrano: ${n}`;
}

function updateStartButton(panel) {
  const btn = panel.querySelector("#sbx-start-btn");
  if (!btn) return;
  const ready = state.campaignId && state.characterId && state.selectedEnemies.size > 0 && !state.busy;
  btn.disabled = !ready;
}

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
  panel.querySelector("#sbx-move-btn")?.addEventListener("click", () => doZoneChange(panel));
  panel.querySelector("#sbx-enemy-btn")?.addEventListener("click", () => doEnemyTurn(panel));
  panel.querySelector("#sbx-reset-btn")?.addEventListener("click", () => doResetHero(panel));
  panel.querySelector("#sbx-end-btn")?.addEventListener("click", () => doEndCombat(panel));
}

async function doSetup(panel) {
  if (!state.selectedHero) { showToast("Wybierz bohatera.", "error"); return; }
  try {
    state.busy = true;
    const res = await adminFetch("/api/admin/sandbox/setup", { method: "POST", body: JSON.stringify({ hero_id: state.selectedHero }) });
    state.campaignId = res.campaign_id;
    state.characterId = res.character_id;
    logMsg(panel, `Setup ✓ — campaign #${res.campaign_id}, hero #${res.character_id} (${res.hero?.name}, ${res.hero?.archetype} Lv${res.hero?.level})`);
    showToast("Sandbox gotowy.", "success");
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
  try {
    state.busy = true;
    const res = await adminFetch("/api/admin/sandbox/start-combat", {
      method: "POST",
      body: JSON.stringify({ campaign_id: state.campaignId, character_id: state.characterId, enemy_keys: enemies }),
    });
    state.combatState = res.combat_state;
    logMsg(panel, `Walka rozpoczęta — rund ${res.combat_state?.round || 1}, kolejność: ${(res.combat_state?.turn_order || []).join(" → ")}`);
    renderCombat(panel);
  } catch (e) {
    showToast("Start error: " + (e.message || "?"), "error");
  } finally {
    state.busy = false;
  }
}

async function refreshCombatState(panel) {
  if (!state.campaignId) return;
  try {
    const res = await adminFetch(`/api/campaigns/${state.campaignId}/combat`);
    state.combatState = res?.active ? res.combat : null;
  } catch {}
  renderCombat(panel);
}

async function doAttack(panel) {
  if (!state.combatState) return;
  const d20 = state.d20Mode === "manual" ? state.d20Manual : (Math.floor(Math.random() * 20) + 1);
  // Player attack uses /combat/resolve-attack with raw_d20 and total
  // Total = d20 + STR mod (we don't have it; backend re-computes from sheet, so send d20 as raw + same as total)
  const body = { roll_result: d20, raw_d20: d20, attacker: "player" };
  try {
    state.busy = true;
    const res = await adminFetch(`/api/campaigns/${state.campaignId}/combat/resolve-attack`, { method: "POST", body: JSON.stringify(body) });
    state.combatState = res.combat_state;
    const line = res.blocked ? `BLOKADA: ${res.message || res.block_reason}`
               : res.hit ? `Trafienie! ${res.damage || 0} obrażeń → ${res.target_name || "wróg"} (rzut ${d20})`
               : `Pudło (rzut ${d20})${res.player_nat1 ? " — Nat 1!" : ""}`;
    logMsg(panel, `[Atak] ${line}`);
    if (res.combat_state?.status === "ended") logMsg(panel, `Walka: ${res.combat_state.ended_reason}.`);
    renderCombat(panel);
  } catch (e) {
    logMsg(panel, "Błąd ataku: " + (e.message || "?"));
  } finally {
    state.busy = false;
  }
}

async function doZoneChange(panel) {
  try {
    state.busy = true;
    const res = await adminFetch(`/api/campaigns/${state.campaignId}/combat/zone-change`, { method: "POST" });
    state.combatState = res.combat_state;
    logMsg(panel, `[Zone] ${res.from} → ${res.to}`);
    renderCombat(panel);
  } catch (e) {
    logMsg(panel, "Zone error: " + (e.message || "?"));
  } finally {
    state.busy = false;
  }
}

async function doEnemyTurn(panel) {
  try {
    state.busy = true;
    const res = await adminFetch(`/api/campaigns/${state.campaignId}/combat/enemy-turn`, { method: "POST" });
    state.combatState = res.combat_state || state.combatState;
    if (res.zone_change) {
      logMsg(panel, `[Wróg] ${res.enemy_name || "?"} szarżuje (${res.zone_change.from} → ${res.zone_change.to})`);
    } else if (res.hit) {
      logMsg(panel, `[Wróg] ${res.enemy_name || "?"} trafia za ${res.damage || 0} (rzut ${res.raw_d20 || "?"})`);
    } else if (res.blocked) {
      logMsg(panel, `[Wróg] zablokowany — ${res.message || "?"}`);
    } else {
      logMsg(panel, `[Wróg] ${res.enemy_name || "?"} pudłuje (rzut ${res.raw_d20 || "?"})`);
    }
    await refreshCombatState(panel);
  } catch (e) {
    logMsg(panel, "Enemy turn error: " + (e.message || "?"));
  } finally {
    state.busy = false;
  }
}

async function doResetHero(panel) {
  try {
    const res = await adminFetch("/api/admin/sandbox/reset-hero", { method: "POST", body: JSON.stringify({ character_id: state.characterId }) });
    logMsg(panel, `Reset HP ${res.hp}/${res.max_hp}${res.max_mana ? ` · Mana ${res.mana}/${res.max_mana}` : ""}`);
    await refreshCombatState(panel);
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

function renderCombat(panel) {
  const host = panel.querySelector("#sbx-combat-state");
  const actions = panel.querySelector("#sbx-actions");
  const meta = panel.querySelector("#sbx-meta-actions");
  if (!host) return;
  const cs = state.combatState;
  if (!cs || cs.status !== "active") {
    host.innerHTML = `<p class="section-note sandbox-idle">${cs?.status === "ended" ? `Walka zakończona (${esc(cs.ended_reason || "?")}).` : "Brak aktywnej walki."}</p>`;
    actions.hidden = !cs;
    meta.hidden = !state.characterId;
    return;
  }
  actions.hidden = false;
  meta.hidden = false;

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
      </div>
    `;
  };

  host.innerHTML = `
    <div class="sandbox-summary">
      <span><b>Runda ${cs.round || 1}</b></span>
      <span class="${playerTurn ? "sandbox-tag-good" : "sandbox-tag-bad"}">${playerTurn ? "Tura gracza" : `Tura: ${esc(cur)}`}</span>
      <span class="sandbox-order">${order.map((id) => `<code${String(id) === cur ? ' class="active"' : ""}>${esc(id)}</code>`).join(" → ")}</span>
    </div>
    <div class="sandbox-roster">
      ${renderRow(player)}
      ${enemies.map(renderRow).join("")}
    </div>
  `;

  // Move button label
  const moveBtn = panel.querySelector("#sbx-move-btn");
  if (moveBtn) {
    moveBtn.textContent = player.zone === "engaged" ? "← Cofnij się" : "→ Zbliż się";
    moveBtn.disabled = !playerTurn || state.busy;
  }
  const atkBtn = panel.querySelector("#sbx-attack-btn");
  if (atkBtn) atkBtn.disabled = !playerTurn || state.busy;
  const enemyBtn = panel.querySelector("#sbx-enemy-btn");
  if (enemyBtn) enemyBtn.disabled = playerTurn || state.busy;
}

function logMsg(panel, line) {
  state.log.unshift(`[${new Date().toLocaleTimeString("pl-PL")}] ${line}`);
  if (state.log.length > 60) state.log.pop();
  const el = panel.querySelector("#sbx-log");
  if (el) el.textContent = state.log.join("\n");
}
