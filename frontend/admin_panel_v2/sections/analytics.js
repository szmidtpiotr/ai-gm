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
