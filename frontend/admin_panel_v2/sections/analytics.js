import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const LABELS = {
  title: "Statystyki",
  loading: "Ładowanie…",
  noData: "Brak danych w wybranym okresie",
  days7: "7 dni",
  days30: "30 dni",
  days90: "90 dni",
  // Overview
  turns: "Tury",
  activeCampaigns: "Aktywne kampanie",
  newCampaigns: "Nowe kampanie",
  newUsers: "Nowi gracze",
  combats: "Walki",
  turnsPerDay: "Tury / dzień",
  // Dice
  diceTitle: "Rozkład rzutów k20",
  totalRolls: "Rzutów łącznie",
  critRate: "Crit (20)",
  fumbleRate: "Fumble (1)",
  avgRoll: "Średnia",
  playerRolls: "Gracz",
  enemyRolls: "Wróg",
  // Combat
  combatTitle: "Statystyki walki",
  totalCombats: "Walki łącznie",
  victories: "Zwycięstwa",
  deaths: "Śmierci gracza",
  avgRounds: "Śr. rund",
  topEnemies: "Najczęściej zabijani",
  playerKillers: "Najgroźniejsi wrogowie",
  // Economy
  econTitle: "Gospodarka",
  topItems: "Najczęstsze przedmioty",
  bySource: "Źródło łupów",
  goldLeaders: "Bogaci gracze",
  // Events
  eventsTitle: "Zdarzenia gry",
  // LLM
  llmTitle: "LLM",
};

const RANGE_OPTIONS = [
  { value: 7, label: LABELS.days7 },
  { value: 30, label: LABELS.days30 },
  { value: 90, label: LABELS.days90 },
];

const TABS = [
  { id: "overview", label: "Przegląd" },
  { id: "dice", label: "Kości" },
  { id: "combat", label: "Walka" },
  { id: "economy", label: "Gospodarka" },
  { id: "events", label: "Zdarzenia" },
  { id: "llm", label: "LLM" },
  { id: "mcp", label: "MCP" },
];

const EVENT_ICONS = {
  combat_victory: "⚔",
  player_death: "💀",
  long_rest: "😴",
  short_rest: "🔋",
  level_up: "⬆",
  spell_cast: "✨",
};

function eventIcon(type) {
  return EVENT_ICONS[type] || "📌";
}

let currentDays = 30;
let currentTab = "overview";
let _cache = {};

export async function init(panel) {
  panel.innerHTML = `
    <div class="analytics-layout">
      <div class="analytics-header">
        <h2 class="section-heading">${LABELS.title}</h2>
        <div class="analytics-range-btns" id="range-btns">
          ${RANGE_OPTIONS.map(o => `
            <button type="button" class="range-btn${o.value === currentDays ? " active" : ""}" data-days="${o.value}">${o.label}</button>
          `).join("")}
        </div>
      </div>
      <div class="an-tabs" id="an-tabs">
        ${TABS.map(t => `
          <button type="button" class="an-tab${t.id === currentTab ? " active" : ""}" data-tab="${t.id}">${t.label}</button>
        `).join("")}
      </div>
      <div class="analytics-body" id="analytics-body">
        <div class="analytics-loading">${LABELS.loading}</div>
      </div>
    </div>
  `;

  panel.querySelectorAll(".range-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      currentDays = Number(btn.dataset.days);
      panel.querySelectorAll(".range-btn").forEach(b => b.classList.toggle("active", b === btn));
      _cache = {};
      loadAll();
    });
  });

  panel.querySelectorAll(".an-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      currentTab = btn.dataset.tab;
      panel.querySelectorAll(".an-tab").forEach(b => b.classList.toggle("active", b === btn));
      renderCurrentTab(panel.querySelector("#analytics-body"));
    });
  });

  await loadAll();

  async function loadAll() {
    const body = panel.querySelector("#analytics-body");
    body.innerHTML = `<div class="analytics-loading">${LABELS.loading}</div>`;
    try {
      const [overview, dice, combat, economy, events, llm] = await Promise.all([
        adminFetch(`/api/admin/analytics/overview?days=${currentDays}`),
        adminFetch(`/api/admin/analytics/dice?days=${currentDays}`),
        adminFetch(`/api/admin/analytics/combat?days=${currentDays}`),
        adminFetch(`/api/admin/analytics/economy?days=${currentDays}`),
        adminFetch(`/api/admin/analytics/events?days=${currentDays}&limit=200`),
        adminFetch(`/api/admin/analytics/llm?days=${currentDays}`),
      ]);
      _cache = { overview, dice, combat, economy, events, llm };
      renderCurrentTab(body);
    } catch (e) {
      body.innerHTML = `<div class="analytics-loading" style="color:var(--accent-red)">${e.message}</div>`;
    }
  }

  function renderCurrentTab(body) {
    if (currentTab === "mcp") { renderMcpTab(body); return; }
    if (!_cache.overview) return;
    const { overview, dice, combat, economy, events, llm } = _cache;
    switch (currentTab) {
      case "overview": renderOverviewTab(body, overview, combat); break;
      case "dice":     renderDiceTab(body, dice); break;
      case "combat":   renderCombatTab(body, combat); break;
      case "economy":  renderEconomyTab(body, economy); break;
      case "events":   renderEventsTab(body, events); break;
      case "llm":      renderLlmTab(body, llm); break;
    }
  }
}

// ── Overview tab ──────────────────────────────────────────────────────────────

function renderOverviewTab(body, overview, combat) {
  body.innerHTML = `
    <div class="an-cards-row" id="stat-cards"></div>
    <div class="an-charts-row">
      <div class="an-card an-chart-wrap">
        <div class="an-card-title">${LABELS.turnsPerDay}</div>
        <canvas id="turns-chart" height="180"></canvas>
      </div>
      <div class="an-card an-chart-wrap">
        <div class="an-card-title">${LABELS.diceTitle}</div>
        <div class="an-dice-meta" id="dice-meta"></div>
        <canvas id="dice-chart" height="180"></canvas>
      </div>
    </div>
  `;
  renderStatCards(body.querySelector("#stat-cards"), overview, combat);
  renderTurnsChart(body.querySelector("#turns-chart"), overview);
}

// ── Dice tab ──────────────────────────────────────────────────────────────────

function renderDiceTab(body, dice) {
  body.innerHTML = `
    <div class="an-card an-chart-wrap">
      <div class="an-card-title">${LABELS.diceTitle}</div>
      <div class="an-dice-meta" id="dice-meta"></div>
      <canvas id="dice-chart" height="200"></canvas>
    </div>
  `;
  renderDiceChart(body.querySelector("#dice-chart"), body.querySelector("#dice-meta"), dice);
}

// ── Combat tab ────────────────────────────────────────────────────────────────

function renderCombatTab(body, combat) {
  body.innerHTML = `
    <div class="an-card">
      <div class="an-card-title">${LABELS.combatTitle}</div>
      <div id="combat-content"></div>
    </div>
  `;
  renderCombatSection(body.querySelector("#combat-content"), combat);
}

// ── Economy tab ───────────────────────────────────────────────────────────────

function renderEconomyTab(body, economy) {
  body.innerHTML = `
    <div class="an-card">
      <div class="an-card-title">${LABELS.econTitle}</div>
      <div id="economy-content"></div>
    </div>
  `;
  renderEconomySection(body.querySelector("#economy-content"), economy);
}

// ── Events tab ────────────────────────────────────────────────────────────────

function renderEventsTab(body, data) {
  const types = data.event_types || [];
  const events = data.events || [];

  body.innerHTML = `
    <div class="an-card">
      <div class="an-card-title">${LABELS.eventsTitle}</div>
      <div class="an-event-filters">
        <select id="ev-type-filter" class="an-filter-select">
          <option value="">Wszystkie typy</option>
          ${types.map(t => `<option value="${escHtml(t)}">${escHtml(t)}</option>`).join("")}
        </select>
        <select id="ev-sev-filter" class="an-filter-select">
          <option value="">Wszystkie poziomy</option>
          <option value="info">info</option>
          <option value="warning">warning</option>
          <option value="error">error</option>
          <option value="debug">debug</option>
        </select>
      </div>
      <div id="ev-list" class="an-event-list">
        ${renderEventRows(events)}
      </div>
    </div>
  `;

  const typeFilter = body.querySelector("#ev-type-filter");
  const sevFilter = body.querySelector("#ev-sev-filter");

  function applyFilters() {
    const t = typeFilter.value;
    const s = sevFilter.value;
    const filtered = events.filter(ev =>
      (!t || ev.event_type === t) && (!s || ev.severity === s)
    );
    body.querySelector("#ev-list").innerHTML = renderEventRows(filtered);
    wireEventRows(body.querySelector("#ev-list"));
  }

  typeFilter.addEventListener("change", applyFilters);
  sevFilter.addEventListener("change", applyFilters);
  wireEventRows(body.querySelector("#ev-list"));
}

function renderEventRows(events) {
  if (!events || !events.length) {
    return `<div class="an-no-data">${LABELS.noData}</div>`;
  }
  return events.map(ev => {
    const ts = (ev.created_at || "").slice(0, 16).replace("T", " ");
    const icon = eventIcon(ev.event_type);
    const sevClass = `an-ev-sev-${ev.severity || "info"}`;
    let dataPreview = "";
    try {
      const d = typeof ev.event_data === "string" ? JSON.parse(ev.event_data) : ev.event_data;
      dataPreview = Object.entries(d || {}).map(([k, v]) => `${k}: ${v}`).join(" · ");
    } catch (_) {
      dataPreview = String(ev.event_data || "");
    }
    return `
      <div class="an-event-row" data-ev='${escAttr(ev.event_data)}' data-expanded="0">
        <span class="an-ev-icon">${icon}</span>
        <span class="an-ev-ts">${ts}</span>
        <span class="an-ev-type">${escHtml(ev.event_type)}</span>
        <span class="an-ev-sev ${sevClass}">${escHtml(ev.severity || "info")}</span>
        <span class="an-ev-camp">${ev.campaign_id != null ? `#${ev.campaign_id}` : "—"}</span>
        <span class="an-ev-data">${escHtml(dataPreview)}</span>
      </div>
    `;
  }).join("");
}

function wireEventRows(container) {
  container.querySelectorAll(".an-event-row").forEach(row => {
    row.addEventListener("click", () => {
      const expanded = row.dataset.expanded === "1";
      if (expanded) {
        const detail = row.querySelector(".an-ev-detail");
        if (detail) detail.remove();
        row.dataset.expanded = "0";
      } else {
        try {
          const raw = row.dataset.ev || "{}";
          const d = typeof raw === "string" ? JSON.parse(raw) : raw;
          const pre = document.createElement("pre");
          pre.className = "an-ev-detail";
          pre.textContent = JSON.stringify(d, null, 2);
          row.appendChild(pre);
        } catch (_) {
          // ignore
        }
        row.dataset.expanded = "1";
      }
    });
  });
}

// ── LLM tab ───────────────────────────────────────────────────────────────────

function renderLlmTab(body, llm) {
  const byType = llm.by_type || [];
  const slowest = llm.slowest || [];

  body.innerHTML = `
    <div class="an-cards-row">
      <div class="an-stat-card an-stat-blue">
        <div class="an-stat-value">${llm.total ?? 0}</div>
        <div class="an-stat-label">Wywołania LLM</div>
      </div>
      <div class="an-stat-card an-stat-gold">
        <div class="an-stat-value">${llm.avg_latency_ms ?? 0}</div>
        <div class="an-stat-label">Śr. czas (ms)</div>
      </div>
      <div class="an-stat-card an-stat-green">
        <div class="an-stat-value">${llm.cache_hit_pct ?? 0}%</div>
        <div class="an-stat-label">Cache hit</div>
      </div>
      <div class="an-stat-card an-stat-red">
        <div class="an-stat-value">${llm.errors ?? 0}</div>
        <div class="an-stat-label">Błędy</div>
      </div>
    </div>
    <div class="an-bottom-row">
      <div class="an-card">
        <div class="an-card-title">Wg typu wywołania</div>
        ${renderSmallTable(
          byType,
          ["call_type", "n", "avg_ms", "cache_hits"],
          ["Typ", "Wywołania", "Śr. ms", "Cache"]
        )}
      </div>
      <div class="an-card">
        <div class="an-card-title">Najwolniejsze wywołania</div>
        ${renderSmallTable(
          slowest.map(r => ({ ...r, latency_ms: r.latency_ms + " ms", error: r.error ? "⚠" : "—" })),
          ["call_type", "model", "latency_ms", "created_at", "error"],
          ["Typ", "Model", "Czas", "Kiedy", "Błąd"]
        )}
      </div>
    </div>
  `;
}

// ── MCP tab ───────────────────────────────────────────────────────────────────

const MCP_URL = "https://aigm-dev.studio-colorbox.com/mcp";

const MCP_TOOLS = [
  { name: "initialize_player_session", star: true,  write: true,  desc: "Loguje się jako gracz testowy i ładuje aktywną kampanię + postać. Wywołaj jako pierwsze." },
  { name: "submit_player_turn",        star: true,  write: true,  desc: "Wysyła akcję gracza do MG i zwraca narrację. Główna pętla rozgrywki." },
  { name: "change_player_zone",        star: false, write: true,  desc: "Przełącza strefę walki: zwarcie ↔ dystans. Zużywa akcję tury." },
  { name: "flee_from_combat",          star: false, write: true,  desc: "Próba ucieczki z walki (traci XP i łupy)." },
  { name: "get_campaign_summary",      star: true,  write: false, desc: "Pełny snapshot kampanii: postać, plan MG, tury, ekwipunek, NPCs, podsumowania AI" },
  { name: "get_full_campaign_context", star: false, write: false, desc: "Dump w markdown — idealny do wklejenia w Perplexity / ChatGPT" },
  { name: "get_system_health",         star: false, write: false, desc: "Aktywne kampanie, rozmiar DB, ostatni LLM call, błędy ostatniej godziny" },
  { name: "get_llm_performance",       star: false, write: false, desc: "Statystyki wywołań LLM wg okresu (24h / 7d / 30d) i typu" },
  { name: "get_player_stats",          star: false, write: false, desc: "Aktywność graczy: tury, śmierci, XP, aktywna kampania" },
  { name: "get_world_analytics",       star: false, write: false, desc: "Lokacje, wrogowie, pending review, hexes, bank pomysłów" },
  { name: "query_game_events",         star: false, write: false, desc: "Filtrowany log zdarzeń (combat_victory, player_death, long_rest…)" },
  { name: "query_action_log",          star: false, write: false, desc: "Paginowany log tur kampanii wg trasy / zakresu tur" },
  { name: "get_error_log",             star: false, write: false, desc: "Błędy i ostrzeżenia z game_events + llm_call_log" },
];

async function renderMcpTab(body) {
  const writeCount = MCP_TOOLS.filter(t => t.write).length;
  const readCount  = MCP_TOOLS.filter(t => !t.write).length;

  body.innerHTML = `
    <div class="mcp-tab">
      <div class="mcp-server-card">
        <div class="mcp-server-header">
          <div>
            <div class="mcp-server-name">🤖 AI-GM MCP Server</div>
            <div class="mcp-server-sub">Model Context Protocol — AI-queryable + playable game</div>
          </div>
          <span class="mcp-status-badge mcp-checking" id="mcp-tab-badge">⏳ Checking…</span>
        </div>
        <div class="mcp-url-row">
          <code class="mcp-url-code">${MCP_URL}</code>
          <button class="mcp-copy-btn" id="mcp-copy-btn" title="Kopiuj URL">📋 Kopiuj</button>
        </div>
        <div class="mcp-meta-row">
          <span>Transport: <strong>Streamable HTTP</strong></span>
          <span>·</span>
          <span>Narzędzia: <strong>${MCP_TOOLS.length}</strong> (${writeCount} write, ${readCount} read)</span>
          <span>·</span>
          <span>Dostęp: <strong>Read + Write</strong></span>
        </div>
      </div>

      <div class="mcp-two-col">
        <div class="mcp-connect-card">
          <div class="mcp-section-title">🔍 Perplexity</div>
          <div class="mcp-connect-steps">
            <div class="mcp-step"><span class="mcp-step-label">URL:</span><code>${MCP_URL}</code></div>
            <div class="mcp-step"><span class="mcp-step-label">Type:</span><code>Streamable HTTP</code></div>
          </div>
          <div class="mcp-examples-title">Prompt startowy dla Perplexity:</div>
          <ul class="mcp-examples">
            <li>„Wywołaj initialize_player_session, potem get_full_campaign_context i zagraj kilka tur."</li>
            <li>„Jesteś wojownikiem w polskim RPG. Zacznij od initialize_player_session."</li>
          </ul>
        </div>

        <div class="mcp-connect-card">
          <div class="mcp-section-title">⌨️ Claude Code / Desktop</div>
          <div class="mcp-connect-steps" style="margin-bottom:14px">
            <div class="mcp-step-label" style="margin-bottom:6px">Claude Code CLI:</div>
            <pre class="mcp-code-block">claude mcp add ai-gm \\
  --transport http \\
  ${MCP_URL}</pre>
          </div>
          <div class="mcp-connect-steps">
            <div class="mcp-step-label" style="margin-bottom:6px">claude_desktop_config.json:</div>
            <pre class="mcp-code-block">{ "mcpServers": {
  "ai-gm": {
    "url": "${MCP_URL}"
  }
}}</pre>
          </div>
        </div>
      </div>

      <div class="mcp-tools-card">
        <div class="mcp-section-title">🔧 ${MCP_TOOLS.length} dostępnych narzędzi</div>
        <div class="mcp-tools-list">
          ${MCP_TOOLS.map(t => `
            <div class="mcp-tool-row">
              <code class="mcp-tool-name${t.star ? " mcp-tool-star" : ""}">${t.star ? "★ " : ""}${t.name}</code>
              <span class="mcp-tool-badge${t.write ? " mcp-tool-write" : " mcp-tool-read"}">${t.write ? "write" : "read"}</span>
              <span class="mcp-tool-desc">${t.desc}</span>
            </div>
          `).join("")}
        </div>
      </div>

      <div class="mcp-config-section">
        <h4>Konfiguracja sesji MCP</h4>
        <div class="mcp-config-row">
          <label>Gracz:</label>
          <select id="mcp-cfg-user" class="mcp-live-sel" disabled>
            <option value="">Ładowanie…</option>
          </select>
          <label>Bohater:</label>
          <select id="mcp-cfg-hero" class="mcp-live-sel" disabled>
            <option value="">— wybierz gracza —</option>
          </select>
          <label>Kampania:</label>
          <span id="mcp-cfg-camp-display" class="mcp-cfg-camp-display">—</span>
          <button id="mcp-cfg-save" class="btn-primary" disabled>Zapisz</button>
        </div>
        <div id="mcp-cfg-status" class="mcp-cfg-status">Ładowanie aktywnej sesji…</div>
      </div>

      <div class="mcp-live-section">
        <div class="mcp-live-header">
          <span class="mcp-live-title">🎮 Podgląd na żywo</span>
          <select id="mcp-camp-sel" class="mcp-live-sel" disabled>
            <option value="">Ładowanie kampanii…</option>
          </select>
          <button id="mcp-iframe-reload" class="mcp-reload-btn" title="Odśwież">↺ Załaduj</button>
        </div>
        <div id="mcp-diag-bar" class="mcp-diag-bar" hidden></div>
        <div class="mcp-iframe-wrap">
          <iframe id="mcp-player-iframe" src="about:blank"></iframe>
        </div>
      </div>
    </div>
  `;

  body.querySelector("#mcp-copy-btn")?.addEventListener("click", () => {
    navigator.clipboard.writeText(MCP_URL).then(() => {
      const btn = body.querySelector("#mcp-copy-btn");
      btn.textContent = "✓ Skopiowano";
      setTimeout(() => { btn.textContent = "📋 Kopiuj"; }, 2000);
    }).catch(() => {});
  });

  body.querySelector("#mcp-iframe-reload")?.addEventListener("click", () => {
    _loadSelectedCampaign(body);
  });

  body.querySelector("#mcp-camp-sel")?.addEventListener("change", () => {
    _loadSelectedCampaign(body);
  });

  // Load campaign list then auto-load the most recent active campaign
  _initDemoCampaigns(body);

  // MCP config section wiring
  _initMcpConfig(body);

  const badge = body.querySelector("#mcp-tab-badge");
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 5000);
    const resp = await fetch("/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json, text/event-stream" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: {
        protocolVersion: "2025-03-26", capabilities: {}, clientInfo: { name: "admin-panel", version: "1" }
      }}),
      signal: ctrl.signal,
    });
    clearTimeout(t);
    badge.className = resp.ok ? "mcp-status-badge mcp-online" : "mcp-status-badge mcp-offline";
    badge.textContent = resp.ok ? "● Online" : "● Offline";
  } catch {
    badge.className = "mcp-status-badge mcp-offline";
    badge.textContent = "● Offline";
  }
}

// Direct fetch to /api/* — bypasses adminFetch URL-builder so it always works
// regardless of aigm_admin_baseurl value in localStorage.
async function _mcpApiFetch(path, options = {}) {
  const token = localStorage.getItem("aigm_admin_token") || "";
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const resp = await fetch(`/api${path}`, { ...options, headers });
  let body = null;
  try { body = await resp.json(); } catch { /* non-json */ }
  if (!resp.ok) {
    const msg = body?.detail || (Array.isArray(body?.detail) ? body.detail.map(e => e.msg).join("; ") : null) || `HTTP ${resp.status}`;
    throw new Error(String(msg).slice(0, 200));
  }
  return body;
}

async function _initMcpConfig(body) {
  const userSel   = body.querySelector("#mcp-cfg-user");
  const heroSel   = body.querySelector("#mcp-cfg-hero");
  const campDisp  = body.querySelector("#mcp-cfg-camp-display");
  const saveBtn   = body.querySelector("#mcp-cfg-save");
  const statusEl  = body.querySelector("#mcp-cfg-status");

  let _heroMap = {};  // heroId → full hero object
  let _pinnedHeroId = null;

  // Load current pinned config
  try {
    const cfg = await _mcpApiFetch("/admin/mcp/config");
    _pinnedHeroId = cfg.hero_id ?? null;
    statusEl.textContent = cfg.hero_name
      ? `Aktywna: bohater „${cfg.hero_name}" → kampania „${cfg.campaign_title ?? "—"}"`
      : "Brak przypietej sesji — MCP używa auto-wykrywania.";
  } catch (e) {
    statusEl.textContent = `Błąd ładowania: ${e.message}`;
  }

  const updateCampDisplay = () => {
    const hero = _heroMap[heroSel.value];
    campDisp.textContent = hero?.campaign_id
      ? `#${hero.campaign_id} ${hero.campaign_title || ""}`.trim()
      : "—";
    saveBtn.disabled = false;
  };

  const populateHeroes = async (userId) => {
    heroSel.innerHTML = `<option value="">— brak (auto) —</option>`;
    heroSel.disabled = true;
    campDisp.textContent = "—";
    saveBtn.disabled = true;
    if (!_demoToken) return;
    try {
      const url = userId ? `/api/characters?user_id=${userId}` : `/api/characters`;
      const resp = await fetch(url, { headers: { "Authorization": `Bearer ${_demoToken}` } });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      const heroes = data.heroes || (Array.isArray(data) ? data : []);
      _heroMap = {};
      heroes.forEach(h => {
        _heroMap[String(h.id)] = h;
        const opt = document.createElement("option");
        opt.value = String(h.id);
        opt.textContent = `${h.name}  (${h.campaign_title || `kampania #${h.campaign_id}` || "brak kampanii"})`;
        heroSel.appendChild(opt);
      });
      heroSel.disabled = false;
      saveBtn.disabled = false;
      if (_pinnedHeroId && _heroMap[String(_pinnedHeroId)]) {
        heroSel.value = String(_pinnedHeroId);
        updateCampDisplay();
        // Pre-select user matching the pinned hero
        const uid = _heroMap[String(_pinnedHeroId)]?.user_id;
        if (uid) userSel.value = String(uid);
      }
    } catch (e) {
      heroSel.innerHTML = `<option value="">⚠ ${e.message}</option>`;
      heroSel.disabled = false;
      saveBtn.disabled = false;
    }
  };

  // Populate players derived from characters (uses _demoToken — no admin token needed)
  const populateUsers = async () => {
    let waited = 0;
    const waitAndLoad = () => {
      if (_demoToken || waited >= 3000) {
        _doPopulate();
      } else {
        waited += 150;
        setTimeout(waitAndLoad, 150);
      }
    };
    const _doPopulate = async () => {
      try {
        const resp = await fetch("/api/characters", {
          headers: { "Authorization": `Bearer ${_demoToken}` },
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const heroes = data.heroes || (Array.isArray(data) ? data : []);
        // Deduplicate users from character list
        const seen = new Map();
        heroes.forEach(h => {
          if (h.user_id && !seen.has(h.user_id)) seen.set(h.user_id, h.user_id);
        });
        userSel.innerHTML = `<option value="">— wszyscy gracze —</option>`;
        seen.forEach((uid) => {
          const opt = document.createElement("option");
          opt.value = String(uid);
          opt.textContent = `Gracz #${uid}`;
          userSel.appendChild(opt);
        });
        userSel.disabled = false;
        // Load all heroes initially (no user filter)
        populateHeroes(null);
      } catch (e) {
        userSel.innerHTML = `<option value="">⚠ ${e.message}</option>`;
        userSel.disabled = false;
        populateHeroes(null);
      }
    };
    waitAndLoad();
  };

  userSel.addEventListener("change", () => {
    const userId = userSel.value ? parseInt(userSel.value) : null;
    _pinnedHeroId = null;
    populateHeroes(userId);
  });

  heroSel.addEventListener("change", updateCampDisplay);

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    saveBtn.textContent = "Zapisywanie…";
    const hero = _heroMap[heroSel.value] ?? null;
    const heroId  = hero ? parseInt(heroSel.value) : null;
    const campId  = hero?.campaign_id ?? null;
    try {
      await _mcpApiFetch("/admin/mcp/config", {
        method: "PUT",
        body: JSON.stringify({ campaign_id: campId, hero_id: heroId }),
      });
      statusEl.textContent = hero
        ? `Aktywna: bohater „${hero.name}" → kampania „${hero.campaign_title || campId}"`
        : "Brak przypietej sesji — MCP używa auto-wykrywania.";
      showToast("Konfiguracja MCP zapisana", "success");
      if (campId) {
        const liveSel = body.querySelector("#mcp-camp-sel");
        if (liveSel) { liveSel.value = String(campId); _loadSelectedCampaign(body); }
      }
    } catch (e) {
      showToast(`Błąd zapisu: ${e.message}`, "error");
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "Zapisz";
    }
  });

  populateUsers();
}

let _demoToken = null;
let _demoCamps = [];

async function _initDemoCampaigns(body) {
  const sel = body.querySelector("#mcp-camp-sel");
  const btn = body.querySelector("#mcp-iframe-reload");
  try {
    // Login as demo
    const loginResp = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "demo", password: "demo" }),
    });
    if (!loginResp.ok) throw new Error(`Login failed ${loginResp.status}`);
    const auth = await loginResp.json();
    _demoToken = auth.access_token;

    // Store player token in shared localStorage (both keys the player UI reads)
    localStorage.setItem("token", auth.access_token);
    localStorage.setItem("aigm_access_token", auth.access_token);
    if (auth.refresh_token) localStorage.setItem("aigm_refresh_token", auth.refresh_token);
    localStorage.setItem("user", JSON.stringify({
      id: auth.user_id, username: auth.username,
      display_name: auth.display_name, is_admin: auth.is_admin,
    }));

    // Fetch campaigns
    const campsResp = await fetch("/api/campaigns", {
      headers: { "Authorization": `Bearer ${_demoToken}` },
    });
    if (!campsResp.ok) throw new Error("Brak dostępu do kampanii");
    const campsData = await campsResp.json();
    const all = campsData.campaigns || (Array.isArray(campsData) ? campsData : []);
    _demoCamps = all.sort((a, b) => (b.id ?? 0) - (a.id ?? 0));

    // Populate selector
    sel.innerHTML = "";
    const active = _demoCamps.filter(c => c.status === "active");
    const ended = _demoCamps.filter(c => c.status !== "active");

    if (active.length) {
      const grp = document.createElement("optgroup");
      grp.label = "Aktywne";
      active.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = `#${c.id} ${c.title || "Kampania"}`;
        grp.appendChild(opt);
      });
      sel.appendChild(grp);
    }
    if (ended.length) {
      const grp = document.createElement("optgroup");
      grp.label = "Zakończone";
      ended.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = `#${c.id} ${c.title || "Kampania"}`;
        grp.appendChild(opt);
      });
      sel.appendChild(grp);
    }
    if (!_demoCamps.length) {
      sel.innerHTML = `<option value="">Brak kampanii</option>`;
    }

    sel.disabled = false;

    // Auto-load most recent active campaign
    if (active.length) sel.value = String(active[0].id);
    else if (_demoCamps.length) sel.value = String(_demoCamps[0].id);

    _loadSelectedCampaign(body);
  } catch (e) {
    if (sel) { sel.disabled = false; sel.innerHTML = `<option value="">⚠ ${e.message}</option>`; }
  }
}

function _loadSelectedCampaign(body) {
  const sel = body.querySelector("#mcp-camp-sel");
  const iframe = body.querySelector("#mcp-player-iframe");
  const diagBar = body.querySelector("#mcp-diag-bar");
  if (!iframe) return;
  const campId = sel?.value;
  if (!campId) return;

  const camp = _demoCamps.find(c => String(c.id) === String(campId));
  if (camp?.character_id) localStorage.setItem("aigm_hero_id", String(camp.character_id));
  localStorage.setItem("aigm_campaign_id", String(campId));

  if (diagBar) { diagBar.textContent = "⏳ Ładowanie…"; diagBar.hidden = false; }

  iframe.addEventListener("load", function _onLoad() {
    iframe.removeEventListener("load", _onLoad);
    // Wait for async init() to complete, then check iframe DOM state
    setTimeout(() => {
      try {
        const doc = iframe.contentDocument;
        if (!doc) { _setDiag(diagBar, "⚠ brak dostępu do iframe (cross-origin?)"); return; }
        const active = doc.querySelector(".screen--active");
        const screenId = active?.id || "none";
        const chatEl = doc.getElementById("chat-messages");
        const msgCount = chatEl?.childElementCount ?? 0;
        const heroName = doc.getElementById("character-name-display")?.textContent?.trim() || "—";
        _setDiag(diagBar, `Ekran: ${screenId} | Bohater: ${heroName} | Wiadomości w czacie: ${msgCount}`);
        // If game screen active but no messages, try to read the console log hints
        if (screenId === "game-screen" && msgCount === 0) {
          _setDiag(diagBar, `⚠ Ekran gry bez wiadomości! Bohater: ${heroName} — sprawdź console po błędy JS`);
        }
      } catch (e) {
        _setDiag(diagBar, `⚠ Błąd odczytu iframe: ${e.message}`);
      }
    }, 2500);
  });

  iframe.src = "/?_t=" + Date.now();
}

function _setDiag(el, msg) {
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
}

// ── Shared renderers ─────────────────────────────────────────────────────────

function renderStatCards(el, overview, combat) {
  const t = overview.totals || {};
  const c = combat || {};
  const cards = [
    { label: LABELS.turns, value: t.turns ?? 0, color: "gold" },
    { label: LABELS.activeCampaigns, value: t.active_campaigns ?? 0, color: "green" },
    { label: LABELS.newCampaigns, value: t.new_campaigns ?? 0, color: "blue" },
    { label: LABELS.newUsers, value: t.new_users ?? 0, color: "purple" },
    { label: LABELS.combats, value: t.combats ?? 0, color: "red" },
    { label: LABELS.avgRounds, value: c.avg_rounds ?? "—", color: "muted" },
  ];

  el.innerHTML = cards.map(card => `
    <div class="an-stat-card an-stat-${card.color}">
      <div class="an-stat-value">${card.value}</div>
      <div class="an-stat-label">${card.label}</div>
    </div>
  `).join("");
}

// ── Line chart: turns per day ──────────────────────────────────────────────

function renderTurnsChart(canvas, overview) {
  if (!canvas) return;
  const data = overview.turns_per_day || [];
  if (!data.length) {
    showNoData(canvas, LABELS.noData);
    return;
  }
  const ctx = canvas.getContext("2d");
  const W = canvas.offsetWidth || 400;
  const H = canvas.height;
  canvas.width = W;

  const PAD = { top: 16, right: 16, bottom: 32, left: 40 };
  const cW = W - PAD.left - PAD.right;
  const cH = H - PAD.top - PAD.bottom;

  const values = data.map(d => d.count);
  const maxV = Math.max(...values, 1);
  const labels = data.map(d => d.day.slice(5)); // MM-DD

  ctx.clearRect(0, 0, W, H);

  // Grid lines
  ctx.strokeStyle = "#2e3244";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = PAD.top + (cH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(PAD.left, y);
    ctx.lineTo(PAD.left + cW, y);
    ctx.stroke();
    ctx.fillStyle = "#5a6070";
    ctx.font = "10px monospace";
    ctx.textAlign = "right";
    ctx.fillText(Math.round(maxV - (maxV / 4) * i), PAD.left - 4, y + 3);
  }

  // Line
  const step = cW / Math.max(data.length - 1, 1);
  ctx.strokeStyle = "#c9a227";
  ctx.lineWidth = 2;
  ctx.beginPath();
  data.forEach((d, i) => {
    const x = PAD.left + i * step;
    const y = PAD.top + cH - (d.count / maxV) * cH;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Fill under line
  ctx.fillStyle = "rgba(201,162,39,0.08)";
  ctx.beginPath();
  data.forEach((d, i) => {
    const x = PAD.left + i * step;
    const y = PAD.top + cH - (d.count / maxV) * cH;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(PAD.left + (data.length - 1) * step, PAD.top + cH);
  ctx.lineTo(PAD.left, PAD.top + cH);
  ctx.closePath();
  ctx.fill();

  // Dots
  ctx.fillStyle = "#c9a227";
  data.forEach((d, i) => {
    if (data.length <= 20 || i % Math.ceil(data.length / 20) === 0) {
      const x = PAD.left + i * step;
      const y = PAD.top + cH - (d.count / maxV) * cH;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  });

  // X labels (sample)
  ctx.fillStyle = "#5a6070";
  ctx.font = "10px monospace";
  ctx.textAlign = "center";
  const labelStep = Math.ceil(labels.length / 7);
  labels.forEach((lbl, i) => {
    if (i % labelStep === 0) {
      const x = PAD.left + i * step;
      ctx.fillText(lbl, x, H - 6);
    }
  });
}

// ── Bar chart: d20 distribution ───────────────────────────────────────────

function renderDiceChart(canvas, metaEl, dice) {
  if (!canvas) return;
  const dist = dice.distribution || [];
  if (!dist.length || dice.total_rolls === 0) {
    showNoData(canvas, LABELS.noData);
    return;
  }

  // Meta pills
  if (metaEl) {
    metaEl.innerHTML = `
      <span class="an-dice-pill">${LABELS.totalRolls}: <strong>${dice.total_rolls}</strong></span>
      <span class="an-dice-pill an-dice-crit">${LABELS.critRate}: <strong>${dice.crit_rate}%</strong></span>
      <span class="an-dice-pill an-dice-fumble">${LABELS.fumbleRate}: <strong>${dice.fumble_rate}%</strong></span>
      <span class="an-dice-pill">Avg: <strong>${dice.avg_roll}</strong></span>
    `;
  }

  const ctx = canvas.getContext("2d");
  const W = canvas.offsetWidth || 400;
  const H = canvas.height;
  canvas.width = W;

  const PAD = { top: 16, right: 8, bottom: 28, left: 36 };
  const cW = W - PAD.left - PAD.right;
  const cH = H - PAD.top - PAD.bottom;
  const n = dist.length; // 20
  const barW = cW / n * 0.7;
  const gap = cW / n;

  const maxV = Math.max(...dist.map(d => d.total), 1);
  const expectedPct = 1 / 20;

  ctx.clearRect(0, 0, W, H);

  // Grid
  ctx.strokeStyle = "#2e3244";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = PAD.top + (cH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(PAD.left, y);
    ctx.lineTo(PAD.left + cW, y);
    ctx.stroke();
    ctx.fillStyle = "#5a6070";
    ctx.font = "10px monospace";
    ctx.textAlign = "right";
    ctx.fillText(Math.round(maxV - (maxV / 4) * i), PAD.left - 3, y + 3);
  }

  // Bars
  dist.forEach((d, i) => {
    const x = PAD.left + i * gap + gap * 0.15;
    const barH = (d.total / maxV) * cH;
    const y = PAD.top + cH - barH;

    // Player portion
    const pBarH = (d.player / maxV) * cH;
    const eBarH = (d.enemy / maxV) * cH;

    // Enemy (bottom)
    ctx.fillStyle = d.value === 20 ? "#27ae60" : d.value === 1 ? "#c0392b" : "#3b82f6";
    ctx.globalAlpha = 0.55;
    ctx.fillRect(x, PAD.top + cH - eBarH, barW, eBarH);

    // Player (on top)
    ctx.fillStyle = d.value === 20 ? "#4ade80" : d.value === 1 ? "#ef4444" : "#c9a227";
    ctx.globalAlpha = 0.85;
    ctx.fillRect(x, PAD.top + cH - barH, barW, pBarH);

    ctx.globalAlpha = 1;

    // X label
    ctx.fillStyle = "#5a6070";
    ctx.font = "9px monospace";
    ctx.textAlign = "center";
    ctx.fillText(d.value, x + barW / 2, H - 6);
  });

  // Expected flat line (5%)
  const expectedY = PAD.top + cH - (dice.total_rolls * expectedPct / maxV) * cH;
  ctx.strokeStyle = "rgba(255,255,255,0.2)";
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(PAD.left, expectedY);
  ctx.lineTo(PAD.left + cW, expectedY);
  ctx.stroke();
  ctx.setLineDash([]);
}

// ── Combat section ────────────────────────────────────────────────────────────

function renderCombatSection(el, combat) {
  if (!el) return;
  const o = combat.outcomes || {};
  const total = combat.total_combats || 0;

  el.innerHTML = `
    <div class="an-combat-outcomes">
      <div class="an-outcome-bar">
        ${total > 0 ? `
          <div class="an-outcome-seg an-seg-win" style="width:${pct(o.victory, total)}%"
               title="Zwycięstwa: ${o.victory}"></div>
          <div class="an-outcome-seg an-seg-death" style="width:${pct(o.player_dead, total)}%"
               title="Śmierci: ${o.player_dead}"></div>
          <div class="an-outcome-seg an-seg-fled" style="width:${pct(o.fled, total)}%"
               title="Ucieczki: ${o.fled}"></div>
        ` : `<div style="color:var(--text-muted);font-size:0.8rem;padding:8px">${LABELS.noData}</div>`}
      </div>
      <div class="an-outcome-legend">
        <span><span class="an-dot an-dot-win"></span>Zwycięstwa: ${o.victory ?? 0}</span>
        <span><span class="an-dot an-dot-death"></span>Śmierci: ${o.player_dead ?? 0}</span>
        <span><span class="an-dot an-dot-fled"></span>Ucieczki: ${o.fled ?? 0}</span>
      </div>
    </div>

    <div class="an-two-col">
      <div>
        <div class="an-section-label">${LABELS.topEnemies}</div>
        ${renderSmallTable(combat.top_enemies_killed, ["name", "kills"], ["Wróg", "Zabić"])}
      </div>
      <div>
        <div class="an-section-label">${LABELS.playerKillers}</div>
        ${renderSmallTable(combat.player_killers, ["name", "count"], ["Wróg", "Zabójstwa"])}
      </div>
    </div>
  `;
}

// ── Economy section ───────────────────────────────────────────────────────────

function renderEconomySection(el, economy) {
  if (!el) return;
  const t = economy.totals || {};
  el.innerHTML = `
    <div class="an-econ-totals">
      <span class="an-econ-stat"><strong>${t.items_acquired ?? 0}</strong> przedmiotów zdobytych</span>
    </div>
    <div class="an-two-col">
      <div>
        <div class="an-section-label">${LABELS.topItems}</div>
        ${renderSmallTable(
          economy.top_items?.slice(0, 8),
          ["name", "type", "total"],
          ["Przedmiot", "Typ", "Ilość"]
        )}
      </div>
      <div>
        <div class="an-section-label">${LABELS.bySource}</div>
        ${renderSmallTable(economy.by_source, ["source", "count"], ["Źródło", "Sztuk"])}
      </div>
    </div>
  `;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function renderSmallTable(rows, keys, headers) {
  if (!rows || !rows.length) {
    return `<div class="an-no-data">${LABELS.noData}</div>`;
  }
  return `<table class="an-small-table">
    <thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead>
    <tbody>
      ${rows.map(r => `<tr>${keys.map(k => `<td>${escHtml(String(r[k] ?? "—"))}</td>`).join("")}</tr>`).join("")}
    </tbody>
  </table>`;
}

function showNoData(canvas, msg) {
  const ctx = canvas.getContext("2d");
  const W = canvas.offsetWidth || 400;
  const H = canvas.height;
  canvas.width = W;
  ctx.fillStyle = "#5a6070";
  ctx.font = "13px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(msg, W / 2, H / 2);
}

function pct(v, total) {
  if (!total) return 0;
  return Math.round((v / total) * 100);
}

function escHtml(str) {
  return String(str ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escAttr(val) {
  return String(val ?? "").replace(/'/g, "&#39;").replace(/"/g, "&quot;");
}
