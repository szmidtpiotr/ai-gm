import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

const LABELS = {
  usersTotal:       "Użytkownicy",
  campaignsActive:  "Aktywne kampanie",
  turnsToday:       "Tury dzisiaj",
  activeCombats:    "Aktywne walki",
  dbSize:           "Rozmiar bazy",
  llmModel:         "Model LLM",
  recentAudit:      "Ostatnie zmiany (admin)",
  recentTurns:      "Ostatnie tury gry",
  noAudit:          "Brak wpisów w logu",
  noTurns:          "Brak tur",
};

let _panel = null;
let _refreshTimer = null;

export async function init(panel) {
  _panel = panel;
  panel.innerHTML = `
    <div class="dashboard-wrap">
      <div class="stat-cards" id="dash-cards">
        ${_cardSkeleton("users_total",       LABELS.usersTotal,      "👤")}
        ${_cardSkeleton("campaigns_active",  LABELS.campaignsActive, "🗺")}
        ${_cardSkeleton("turns_today",       LABELS.turnsToday,      "🎲")}
        ${_cardSkeleton("active_combats",    LABELS.activeCombats,   "⚔")}
        ${_cardSkeleton("db_size_mb",        LABELS.dbSize,          "🗄")}
        ${_cardSkeleton("llm_preset_name",   LABELS.llmModel,        "⚡")}
      </div>

      <div class="dash-feeds">
        <section class="dash-feed">
          <h3 class="feed-title">${LABELS.recentAudit}</h3>
          <div id="dash-audit-list" class="feed-list"><div class="feed-loading">Loading…</div></div>
        </section>
        <section class="dash-feed">
          <h3 class="feed-title">${LABELS.recentTurns}</h3>
          <div id="dash-turns-list" class="feed-list"><div class="feed-loading">Loading…</div></div>
        </section>
      </div>
    </div>`;

  await _load();

  _refreshTimer = setInterval(() => { void _load(); }, 30_000);
  panel.addEventListener("section-deactivate", () => {
    clearInterval(_refreshTimer);
    _refreshTimer = null;
  }, { once: true });
}

async function _load() {
  try {
    const data = await adminFetch("/api/admin/overview");
    _renderCards(data);
    _renderAudit(data.recent_audit || []);
    _renderTurns(data.recent_turns || []);
  } catch (e) {
    showToast("Dashboard load failed: " + (e.message || "unknown error"), "error");
  }
}

function _cardSkeleton(id, label, icon) {
  return `
    <div class="stat-card" id="card-${id}">
      <div class="stat-card-icon">${icon}</div>
      <div class="stat-card-body">
        <div class="stat-card-value" id="val-${id}">—</div>
        <div class="stat-card-label">${label}</div>
      </div>
    </div>`;
}

function _renderCards(data) {
  const set = (id, val) => {
    const el = document.getElementById(`val-${id}`);
    if (el) el.textContent = val ?? "—";
  };
  set("users_total",      data.users_total);
  set("campaigns_active", data.campaigns_active);
  set("turns_today",      data.turns_today);
  set("active_combats",   data.active_combats);
  set("db_size_mb",       data.db_size_mb != null ? data.db_size_mb + " MB" : "—");
  set("llm_preset_name",  data.llm_preset_name);

  const combatCard = document.getElementById("card-active_combats");
  if (combatCard) {
    combatCard.classList.toggle("stat-card-alert", Number(data.active_combats) > 0);
  }
}

function _renderAudit(rows) {
  const el = document.getElementById("dash-audit-list");
  if (!el) return;
  if (!rows.length) {
    el.innerHTML = `<div class="feed-empty">${LABELS.noAudit}</div>`;
    return;
  }
  el.innerHTML = rows.map(r => `
    <div class="feed-row">
      <span class="feed-op feed-op-${(r.operation || "").toLowerCase()}">${r.operation || "?"}</span>
      <span class="feed-table">${r.table_name || "?"}</span>
      <span class="feed-key muted">${r.row_key || ""}</span>
      <span class="feed-time muted">${_relTime(r.performed_at)}</span>
    </div>`).join("");
}

function _renderTurns(rows) {
  const el = document.getElementById("dash-turns-list");
  if (!el) return;
  if (!rows.length) {
    el.innerHTML = `<div class="feed-empty">${LABELS.noTurns}</div>`;
    return;
  }
  el.innerHTML = rows.map(r => `
    <div class="feed-row feed-row-turn">
      <div class="feed-turn-campaign">${_esc(r.campaign_title || "?")}</div>
      <div class="feed-turn-text muted">${_esc(r.user_text || "")}</div>
      <div class="feed-time muted">${_relTime(r.created_at)}</div>
    </div>`).join("");
}

function _relTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    const sec = Math.round((Date.now() - d.getTime()) / 1000);
    if (sec < 60) return `${sec}s ago`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
    return `${Math.floor(sec / 86400)}d ago`;
  } catch { return iso; }
}

function _esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
