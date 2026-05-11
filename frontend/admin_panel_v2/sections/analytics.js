import { adminFetch } from "/admin_panel_v2/shared/api.js?v=2";
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
};

const RANGE_OPTIONS = [
  { value: 7, label: LABELS.days7 },
  { value: 30, label: LABELS.days30 },
  { value: 90, label: LABELS.days90 },
];

let currentDays = 30;

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
      <div class="analytics-body" id="analytics-body">
        <div class="analytics-loading">${LABELS.loading}</div>
      </div>
    </div>
  `;

  panel.querySelectorAll(".range-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      currentDays = Number(btn.dataset.days);
      panel.querySelectorAll(".range-btn").forEach(b => b.classList.toggle("active", b === btn));
      loadAll();
    });
  });

  await loadAll();

  async function loadAll() {
    const body = panel.querySelector("#analytics-body");
    body.innerHTML = `<div class="analytics-loading">${LABELS.loading}</div>`;
    try {
      const [overview, dice, combat, economy] = await Promise.all([
        adminFetch(`/api/admin/analytics/overview?days=${currentDays}`),
        adminFetch(`/api/admin/analytics/dice?days=${currentDays}`),
        adminFetch(`/api/admin/analytics/combat?days=${currentDays}`),
        adminFetch(`/api/admin/analytics/economy?days=${currentDays}`),
      ]);
      renderAll(body, overview, dice, combat, economy);
    } catch (e) {
      body.innerHTML = `<div class="analytics-loading" style="color:var(--accent-red)">${e.message}</div>`;
    }
  }
}

// ── Render ────────────────────────────────────────────────────────────────────

function renderAll(body, overview, dice, combat, economy) {
  body.innerHTML = `
    <!-- Stat cards row -->
    <div class="an-cards-row" id="stat-cards"></div>

    <!-- Charts row -->
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

    <!-- Combat + Economy row -->
    <div class="an-bottom-row">
      <div class="an-card">
        <div class="an-card-title">${LABELS.combatTitle}</div>
        <div id="combat-content"></div>
      </div>
      <div class="an-card">
        <div class="an-card-title">${LABELS.econTitle}</div>
        <div id="economy-content"></div>
      </div>
    </div>
  `;

  renderStatCards(body.querySelector("#stat-cards"), overview, combat);
  renderTurnsChart(body.querySelector("#turns-chart"), overview);
  renderDiceChart(body.querySelector("#dice-chart"), body.querySelector("#dice-meta"), dice);
  renderCombatSection(body.querySelector("#combat-content"), combat);
  renderEconomySection(body.querySelector("#economy-content"), economy);
}

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
