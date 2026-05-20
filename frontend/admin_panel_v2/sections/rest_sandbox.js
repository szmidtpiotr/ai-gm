// Rest Sandbox — Stage 2C+ admin harness for testing the full rest loop.
// Mirrors Combat Sandbox (sandbox.js / issue #21).
// 3-column layout: Setup + Sheet | Rest Controls | Event Log + Kopiuj raport
import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

let rsb = {
  heroes: [],
  selectedHero: null,
  campaignId: null,
  characterId: null,
  hero: null,        // last /character snapshot
  log: [],           // event log entries [{ts, msg, type}]
  busy: false,
};

export async function init(panel) {
  panel.innerHTML = layout();
  await loadHeroes(panel);
  bindEvents(panel);
  renderHeroPicker(panel);
  renderSheet(panel);
  renderLog(panel);
}

// ── Layout ────────────────────────────────────────────────────────────────────

function layout() {
  return `
<div class="rsb-root">
  <header class="sandbox-header">
    <h2>💤 Rest Sandbox</h2>
    <p class="section-note">Testuj pełny cykl odpoczynku: Rozbij obóz → Krótki odpoczynek → Długi odpoczynek → HP/mana/PD. Działa na klonie bohatera — oryginał nienaruszony.</p>
  </header>

  <div class="rsb-grid">

    <!-- Col 1: Setup + Sheet -->
    <section class="rsb-col">
      <details class="sandbox-setup-details" open>
        <summary><h3 style="display:inline">1. Bohater</h3></summary>
        <div class="sandbox-subblock">
          <div id="rsb-hero-picker" class="sandbox-hero-picker"></div>
        </div>
        <div class="sandbox-setup-actions">
          <button class="primary-btn" id="rsb-setup-btn" disabled>Przygotuj sandbox</button>
          <button class="secondary-btn" id="rsb-end-btn" style="display:none">Zakończ sesję</button>
        </div>
      </details>

      <div id="rsb-sheet-card" class="rsb-sheet-card" style="display:none">
        <div class="rsb-sheet-name" id="rsb-sheet-name"></div>
        <div class="rsb-stat-row">
          <div class="rsb-stat">
            <div class="rsb-stat__label">HP</div>
            <div class="rsb-stat__val" id="rsb-hp">—</div>
            <div class="stat-card__bar rsb-bar"><div class="stat-card__bar-fill rsb-bar__fill" id="rsb-hp-bar" style="width:0%;background:var(--success)"></div></div>
          </div>
          <div class="rsb-stat" id="rsb-mana-block" style="display:none">
            <div class="rsb-stat__label">Mana</div>
            <div class="rsb-stat__val" id="rsb-mana">—</div>
            <div class="stat-card__bar rsb-bar"><div class="stat-card__bar-fill rsb-bar__fill" id="rsb-mana-bar" style="width:0%;background:#9b59b6"></div></div>
          </div>
          <div class="rsb-stat">
            <div class="rsb-stat__label">XP wolne</div>
            <div class="rsb-stat__val" id="rsb-xp">—</div>
          </div>
          <div class="rsb-stat">
            <div class="rsb-stat__label">XP oczekujące</div>
            <div class="rsb-stat__val" id="rsb-pending-xp" style="color:#c9a54a">—</div>
          </div>
          <div class="rsb-stat">
            <div class="rsb-stat__label">☽ Krótkie</div>
            <div class="rsb-stat__val" id="rsb-short-charges">—</div>
          </div>
        </div>
        <div id="rsb-conditions" class="conditions-list" style="margin-top:6px"></div>
      </div>
    </section>

    <!-- Col 2: Controls -->
    <section class="rsb-col">
      <h3 class="sandbox-label">2. Kontrolki</h3>

      <div class="rsb-controls" id="rsb-controls">
        <p class="section-note" style="margin-top:8px">Najpierw wybierz bohatera i kliknij „Przygotuj sandbox".</p>
      </div>
    </section>

    <!-- Col 3: Log + Raport -->
    <section class="rsb-col">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <h3 class="sandbox-label" style="margin:0">3. Log</h3>
        <button class="secondary-btn" id="rsb-copy-btn" style="font-size:0.78rem;padding:4px 10px" title="Kopiuj raport do schowka">📋 Kopiuj raport</button>
      </div>
      <div id="rsb-log" class="rsb-log"></div>
    </section>

  </div>
</div>`;
}

// ── Data loading ──────────────────────────────────────────────────────────────

async function loadHeroes(panel) {
  try {
    const data = await adminFetch("/api/admin/rest-sandbox/heroes");
    rsb.heroes = data.heroes || [];
  } catch (e) {
    rsb.heroes = [];
  }
}

// ── Rendering ─────────────────────────────────────────────────────────────────

function renderHeroPicker(panel) {
  const el = panel.querySelector("#rsb-hero-picker");
  if (!el) return;
  if (!rsb.heroes.length) { el.innerHTML = '<p class="section-note">Brak bohaterów.</p>'; return; }
  el.innerHTML = rsb.heroes.map(h => `
    <div class="sandbox-hero-chip ${rsb.selectedHero?.id === h.id ? "selected" : ""}" data-hero-id="${h.id}">
      <strong>${esc(h.name)}</strong>
      <span class="rsb-hero-meta">${esc(h.archetype || "?")} · HP ${h.hp ?? "?"}/${h.max_hp ?? "?"}</span>
    </div>`).join("");

  el.querySelectorAll("[data-hero-id]").forEach(chip => {
    chip.addEventListener("click", () => {
      rsb.selectedHero = rsb.heroes.find(h => h.id === Number(chip.dataset.heroId)) || null;
      renderHeroPicker(panel);
      const btn = panel.querySelector("#rsb-setup-btn");
      if (btn) btn.disabled = !rsb.selectedHero;
    });
  });
}

function renderSheet(panel) {
  const card = panel.querySelector("#rsb-sheet-card");
  if (!card) return;
  if (!rsb.hero) { card.style.display = "none"; return; }
  card.style.display = "";

  const h = rsb.hero;
  panel.querySelector("#rsb-sheet-name").textContent = h.name;
  panel.querySelector("#rsb-hp").textContent = `${h.hp}/${h.max_hp}`;
  panel.querySelector("#rsb-hp-bar").style.width = `${h.max_hp > 0 ? (h.hp / h.max_hp) * 100 : 0}%`;

  const manaBlock = panel.querySelector("#rsb-mana-block");
  if (h.max_mana > 0) {
    manaBlock.style.display = "";
    panel.querySelector("#rsb-mana").textContent = `${h.mana}/${h.max_mana}`;
    panel.querySelector("#rsb-mana-bar").style.width = `${(h.mana / h.max_mana) * 100}%`;
  } else {
    manaBlock.style.display = "none";
  }

  panel.querySelector("#rsb-xp").textContent = h.xp_available ?? 0;
  panel.querySelector("#rsb-pending-xp").textContent = h.pending_xp > 0 ? `+${h.pending_xp}` : "0";
  panel.querySelector("#rsb-short-charges").textContent = `${2 - (h.short_rests_used ?? 0)}/2`;

  const conds = panel.querySelector("#rsb-conditions");
  const cs = h.conditions || [];
  conds.innerHTML = cs.length
    ? cs.map(c => `<span class="condition-chip">${esc(typeof c === "string" ? c : c.key)}</span>`).join("")
    : "";
}

function renderControls(panel) {
  const el = panel.querySelector("#rsb-controls");
  if (!el || !rsb.campaignId) return;
  const short = 2 - (rsb.hero?.short_rests_used ?? 0);
  el.innerHTML = `
    <div class="rsb-control-group">
      <button class="rsb-ctrl-btn" id="rsb-build-camp">🏕 Rozbij obóz</button>
      <button class="rsb-ctrl-btn rsb-ctrl-safe" id="rsb-set-safe">🔒 Bezpieczne miejsce</button>
      <button class="rsb-ctrl-btn rsb-ctrl-unsafe" id="rsb-set-unsafe">🔓 Niebezpieczne</button>
    </div>
    <div class="rsb-control-group">
      <button class="rsb-ctrl-btn rsb-ctrl-short" id="rsb-short-rest" ${short <= 0 ? "disabled" : ""}>
        ☽ Krótki odpoczynek <span class="rest-charges">${short}/2</span>
      </button>
      <button class="rsb-ctrl-btn rsb-ctrl-long" id="rsb-long-rest">★ Długi odpoczynek</button>
    </div>
    <div class="rsb-control-group">
      <button class="rsb-ctrl-btn" id="rsb-roll-encounter">🎲 Rzut na spotkanie</button>
      <button class="rsb-ctrl-btn rsb-ctrl-reset" id="rsb-reset-hero">↺ Reset bohatera</button>
    </div>`;

  el.querySelector("#rsb-build-camp").addEventListener("click",   () => doAction("build-camp", panel));
  el.querySelector("#rsb-set-safe").addEventListener("click",     () => doSafeToggle(true, panel));
  el.querySelector("#rsb-set-unsafe").addEventListener("click",   () => doSafeToggle(false, panel));
  el.querySelector("#rsb-short-rest").addEventListener("click",   () => doAction("short-rest", panel));
  el.querySelector("#rsb-long-rest").addEventListener("click",    () => doAction("long-rest", panel));
  el.querySelector("#rsb-roll-encounter").addEventListener("click",() => doAction("roll-encounter", panel));
  el.querySelector("#rsb-reset-hero").addEventListener("click",   () => doAction("reset-hero", panel));
}

function renderLog(panel) {
  const el = panel.querySelector("#rsb-log");
  if (!el) return;
  if (!rsb.log.length) { el.innerHTML = '<p class="section-note" style="margin:8px 0">Brak zdarzeń.</p>'; return; }
  el.innerHTML = rsb.log.slice().reverse().map(e =>
    `<div class="rsb-log-entry rsb-log-${e.type}">[${e.ts}] ${esc(e.msg)}</div>`
  ).join("");
}

function addLog(msg, type = "info") {
  const ts = new Date().toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  rsb.log.push({ ts, msg, type });
}

// ── Event binding ─────────────────────────────────────────────────────────────

function bindEvents(panel) {
  panel.querySelector("#rsb-setup-btn")?.addEventListener("click", () => doSetup(panel));
  panel.querySelector("#rsb-end-btn")?.addEventListener("click",   () => doEnd(panel));
  panel.querySelector("#rsb-copy-btn")?.addEventListener("click",  () => copyReport());
}

// ── Actions ───────────────────────────────────────────────────────────────────

async function doSetup(panel) {
  if (!rsb.selectedHero || rsb.busy) return;
  rsb.busy = true;
  try {
    const data = await adminFetch("/api/admin/rest-sandbox/setup", {
      method: "POST",
      body: JSON.stringify({ hero_id: rsb.selectedHero.id }),
    });
    rsb.campaignId = data.campaign_id;
    rsb.characterId = data.character_id;
    rsb.log = [];
    addLog(`Sandbox gotowy. Klon: ${data.hero.name} (HP ${data.hero.hp}/${data.hero.max_hp})`, "ok");
    showToast("Sandbox przygotowany.", "success");
    await refreshHero(panel);
    renderControls(panel);

    const setupBtn = panel.querySelector("#rsb-setup-btn");
    const endBtn = panel.querySelector("#rsb-end-btn");
    if (setupBtn) setupBtn.textContent = "↺ Resetuj sandbox";
    if (endBtn) endBtn.style.display = "";
  } catch (e) {
    showToast("Błąd setup: " + e.message, "error");
    addLog("Błąd setup: " + e.message, "error");
  } finally {
    rsb.busy = false;
    renderLog(panel);
  }
}

async function doEnd(panel) {
  if (!rsb.campaignId || rsb.busy) return;
  rsb.busy = true;
  try {
    await adminFetch("/api/admin/rest-sandbox/end", {
      method: "POST",
      body: JSON.stringify({ campaign_id: rsb.campaignId }),
    });
    addLog("Sesja zakończona.", "info");
    rsb.campaignId = null;
    rsb.characterId = null;
    rsb.hero = null;
    panel.querySelector("#rsb-end-btn").style.display = "none";
    panel.querySelector("#rsb-setup-btn").textContent = "Przygotuj sandbox";
    panel.querySelector("#rsb-controls").innerHTML = '<p class="section-note">Sesja zakończona.</p>';
    renderSheet(panel);
    showToast("Sesja zakończona.", "success");
  } catch (e) {
    showToast("Błąd: " + e.message, "error");
  } finally {
    rsb.busy = false;
    renderLog(panel);
  }
}

async function doSafeToggle(safe, panel) {
  if (!rsb.campaignId || rsb.busy) return;
  rsb.busy = true;
  try {
    const data = await adminFetch("/api/admin/rest-sandbox/set-hex-safe", {
      method: "POST",
      body: JSON.stringify({ campaign_id: rsb.campaignId, safe }),
    });
    const msg = data.ok
      ? `Miejsce: ${safe ? "🔒 bezpieczne" : "🔓 niebezpieczne"} (${data.location_key ?? "brak lokacji"})`
      : `Nie ustawiono: ${data.detail}`;
    addLog(msg, data.ok ? "ok" : "warn");
    showToast(msg, data.ok ? "success" : "warning");
  } catch (e) {
    addLog("Błąd toggle: " + e.message, "error");
  } finally {
    rsb.busy = false;
    renderLog(panel);
  }
}

async function doAction(action, panel) {
  if (!rsb.campaignId || !rsb.characterId || rsb.busy) return;
  rsb.busy = true;
  try {
    const body = { campaign_id: rsb.campaignId, character_id: rsb.characterId };
    const data = await adminFetch(`/api/admin/rest-sandbox/${action}`, {
      method: "POST",
      body: JSON.stringify(body),
    });

    let msg = "";
    if (action === "build-camp") {
      msg = data.already_camped
        ? `Obóz już istnieje: ${data.location?.key}`
        : `Obóz rozbity: ${data.location?.key ?? "?"} (safe_for_rest=1)`;
    } else if (action === "short-rest") {
      msg = `☽ Krótki: HP ${data.hp_before}→${data.hp_after} (kość ${data.roll}+${data.con_mod}), ładunki: ${data.short_rests_remaining}/2`;
    } else if (action === "long-rest") {
      const xpMsg = data.xp_unlocked > 0 ? `, odblokowano ${data.xp_unlocked} PD` : "";
      msg = `★ Długi: HP ${data.hp_after}/${rsb.hero?.max_hp ?? "?"}, +8h${xpMsg}`;
    } else if (action === "roll-encounter") {
      msg = `🎲 ${data.detail} (rzut ${data.roll} vs próg ${data.chance})`;
    } else if (action === "reset-hero") {
      msg = `↺ Reset: HP ${data.hp}/${data.max_hp}, ładunki 2/2`;
    }

    addLog(msg, action === "roll-encounter" && data.triggered ? "warn" : "ok");
    await refreshHero(panel);
    renderControls(panel);
  } catch (e) {
    const detail = e?.data?.detail || e.message;
    const friendly = {
      not_safe_for_rest: "Nie jesteś w bezpiecznym miejscu. Rozbij obóz lub włącz tryb bezpieczny.",
      short_rest_exhausted: "Brak ładunków krótkiego odpoczynku. Wykonaj długi odpoczynek.",
    }[detail] || detail;
    addLog(`✗ ${action}: ${friendly}`, "error");
    showToast(friendly, "error");
  } finally {
    rsb.busy = false;
    renderLog(panel);
  }
}

async function refreshHero(panel) {
  if (!rsb.characterId) return;
  try {
    const data = await adminFetch(`/api/admin/rest-sandbox/character/${rsb.characterId}`);
    rsb.hero = data;
    renderSheet(panel);
  } catch (_e) {}
}

// ── RSB4: Kopiuj raport ───────────────────────────────────────────────────────

function copyReport() {
  const h = rsb.hero;
  const lines = [
    `## Rest Sandbox — Raport`,
    `**Bohater:** ${h?.name ?? "brak"}`,
    `**HP:** ${h?.hp ?? "?"}/${h?.max_hp ?? "?"}`,
    h?.max_mana > 0 ? `**Mana:** ${h?.mana ?? "?"}/${h?.max_mana ?? "?"}` : null,
    `**XP wolne:** ${h?.xp_available ?? 0}`,
    `**XP oczekujące:** ${h?.pending_xp ?? 0}`,
    `**Krótkie odpoczynki:** ${h ? 2 - (h.short_rests_used ?? 0) : "?"}${"/2 dostępnych"}`,
    `**Stany:** ${(h?.conditions || []).join(", ") || "brak"}`,
    ``,
    `### Log zdarzeń`,
    ...rsb.log.map(e => `- [${e.ts}] ${e.msg}`),
  ].filter(l => l !== null).join("\n");

  navigator.clipboard.writeText(lines).then(
    () => showToast("Raport skopiowany do schowka.", "success"),
    () => showToast("Błąd: clipboard niedostępny.", "error"),
  );
}
