/**
 * O3 (#705) — sekcja „Statystyki i Logi".
 * KPI dashboard + 4 zakładki: Aktywność / Zdarzenia / Wydajność LLM / Błędy.
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

function _esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function _ago(iso) {
  if (!iso) return '—';
  const s = Math.round((Date.now() - new Date(iso)) / 1000);
  if (s < 60) return 'przed chwilą';
  if (s < 3600) return `${Math.floor(s / 60)} min temu`;
  if (s < 86400) return `${Math.floor(s / 3600)} godz. temu`;
  return `${Math.floor(s / 86400)} dni temu`;
}
function _ms(ms) {
  if (ms == null) return '—';
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}
function _loading(cols) {
  return `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr>`;
}
function _empty(cols, msg) {
  return `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">${_esc(msg)}</td></tr>`;
}

const EVENT_ICONS = {
  combat_victory: '⚔', combat_start: '⚔', combat_fled: '🏃',
  player_death: '💀', beat_complete: '📖', fear_triggered: '😱',
  miscast: '✨', death_save_success: '💚', death_save_fail: '🖤',
  xp_granted: '⭐', llm_error: '🔴', dungeon_cleared: '🗝',
};
function _evIcon(type) { return EVENT_ICONS[type] || '•'; }

function _html() {
  return `
<section class="section active" id="section-analytics">
  <div class="section-header">
    <div>
      <div class="section-heading">Statystyki i Logi</div>
      <div class="section-sub">Observability — dane z gry w czasie rzeczywistym</div>
    </div>
    <button class="btn btn-secondary btn-sm" id="ana-refresh">⟳ Odśwież</button>
  </div>
  <div class="stat-grid" id="ana-kpi" style="margin-bottom:20px">
    <div class="stat-card"><div class="stat-label">Aktywne kampanie</div><div class="stat-value" id="kpi-campaigns">—</div></div>
    <div class="stat-card"><div class="stat-label">Tury dziś</div><div class="stat-value" id="kpi-turns">—</div></div>
    <div class="stat-card"><div class="stat-label">Avg LLM latency</div><div class="stat-value" id="kpi-latency">—</div></div>
    <div class="stat-card"><div class="stat-label">Błędy 24h</div><div class="stat-value" id="kpi-errors">—</div></div>
  </div>
  <div class="section-tabs" id="ana-tabs">
    <button class="stab active" data-anatab="players">Aktywność graczy</button>
    <button class="stab" data-anatab="events">Zdarzenia gry</button>
    <button class="stab" data-anatab="llm">Wydajność LLM</button>
    <button class="stab" data-anatab="errors">Błędy</button>
  </div>
  <div class="stab-panel active" id="anatab-players">
    <table class="data-table"><thead><tr>
      <th>Gracz</th><th>Postać</th><th>Kampania</th>
      <th>Ostatnia aktywność</th><th>Tury</th><th>Śmierci</th>
    </tr></thead><tbody id="ana-players-body">${_loading(6)}</tbody></table>
  </div>
  <div class="stab-panel" id="anatab-events" style="display:none">
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <input class="form-input" id="ev-filter-type" placeholder="typ zdarzenia…" style="max-width:160px">
      <select class="form-input" id="ev-filter-sev" style="max-width:130px">
        <option value="">Severity: all</option>
        <option value="debug">debug</option>
        <option value="info">info</option>
        <option value="warning">warning</option>
        <option value="error">error</option>
      </select>
      <input class="form-input" id="ev-filter-camp" placeholder="campaign_id…" type="number" style="max-width:130px">
      <button class="btn btn-secondary btn-sm" id="ev-apply-btn">Filtruj</button>
    </div>
    <table class="data-table"><thead><tr>
      <th>Czas</th><th>Typ</th><th>Kampania</th><th>Severity</th><th>Dane</th>
    </tr></thead><tbody id="ana-events-body">${_loading(5)}</tbody></table>
  </div>
  <div class="stab-panel" id="anatab-llm" style="display:none">
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="chip on" data-llmperiod="24h">24h</button>
      <button class="chip" data-llmperiod="7d">7 dni</button>
      <button class="chip" data-llmperiod="30d">30 dni</button>
    </div>
    <div id="ana-llm-content"><p style="color:var(--t3)">Ładowanie…</p></div>
  </div>
  <div class="stab-panel" id="anatab-errors" style="display:none">
    <table class="data-table"><thead><tr>
      <th>Czas</th><th>Źródło</th><th>Typ</th><th>Kampania</th><th>Detal</th>
    </tr></thead><tbody id="ana-errors-body">${_loading(5)}</tbody></table>
  </div>
</section>`;
}

let _tabLoaded = new Set();
let _llmPeriod = '24h';

async function _loadKpi() {
  try {
    const d = await apiFetch('/api/admin/analytics/dashboard');
    document.getElementById('kpi-campaigns').textContent = d.active_campaigns ?? '—';
    document.getElementById('kpi-turns').textContent = d.turns_today ?? '—';
    document.getElementById('kpi-latency').textContent = _ms(d.avg_latency_ms);
    const errEl = document.getElementById('kpi-errors');
    errEl.textContent = d.errors_24h ?? '—';
    errEl.style.color = (d.errors_24h > 0) ? 'var(--red)' : 'var(--green)';
  } catch (_) {
    ['kpi-campaigns','kpi-turns','kpi-latency','kpi-errors'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = '!';
    });
  }
}

async function _loadPlayers() {
  const tbody = document.getElementById('ana-players-body');
  try {
    const d = await apiFetch('/api/admin/analytics/players');
    if (!d.players.length) { tbody.innerHTML = _empty(6, 'Brak aktywnych graczy.'); return; }
    tbody.innerHTML = d.players.map(p =>
      '<tr>' +
      '<td>' + _esc(p.display_name || p.username) + '</td>' +
      '<td>' + _esc(p.character_name) + '</td>' +
      '<td>' + _esc(p.campaign_title || '—') + '</td>' +
      '<td>' + _ago(p.last_active) + '</td>' +
      '<td>' + _esc(p.turns_count) + '</td>' +
      '<td>' + _esc(p.deaths) + '</td>' +
      '</tr>'
    ).join('');
  } catch (e) { tbody.innerHTML = _empty(6, 'Błąd: ' + e.message); }
}

async function _loadEvents() {
  const tbody = document.getElementById('ana-events-body');
  tbody.innerHTML = _loading(5);
  const params = new URLSearchParams({ limit: 50 });
  const typ = document.getElementById('ev-filter-type')?.value.trim();
  const sev = document.getElementById('ev-filter-sev')?.value;
  const cid = document.getElementById('ev-filter-camp')?.value.trim();
  if (typ) params.set('event_type', typ);
  if (sev) params.set('severity', sev);
  if (cid) params.set('campaign_id', cid);
  try {
    const d = await apiFetch('/api/admin/analytics/events?' + params);
    if (!d.events.length) { tbody.innerHTML = _empty(5, 'Brak zdarzeń.'); return; }
    tbody.innerHTML = d.events.map(e => {
      const ts = e.created_at ? new Date(e.created_at).toLocaleTimeString('pl-PL') : '—';
      const sColor = e.severity === 'error' ? 'var(--red)' : e.severity === 'warning' ? 'var(--amber)' : 'inherit';
      let dataCell;
      try {
        const parsed = JSON.parse(e.event_data || '{}');
        dataCell = '<details><summary style="cursor:pointer;color:var(--blue);font-size:0.75rem">JSON</summary><pre style="font-size:0.72rem;background:var(--page);padding:6px;border-radius:4px;white-space:pre-wrap">' + _esc(JSON.stringify(parsed, null, 2)) + '</pre></details>';
      } catch (_) { dataCell = _esc(e.event_data || ''); }
      return '<tr>' +
        '<td style="white-space:nowrap;font-size:0.8rem;color:var(--t3)">' + _esc(ts) + '</td>' +
        '<td>' + _evIcon(e.event_type) + ' <span style="font-size:0.82rem">' + _esc(e.event_type) + '</span></td>' +
        '<td style="font-size:0.8rem">' + _esc(e.campaign_id ?? '—') + '</td>' +
        '<td style="color:' + sColor + ';font-size:0.8rem">' + _esc(e.severity) + '</td>' +
        '<td>' + dataCell + '</td></tr>';
    }).join('');
  } catch (e) { tbody.innerHTML = _empty(5, 'Błąd: ' + e.message); }
}

async function _loadLlm() {
  const container = document.getElementById('ana-llm-content');
  container.innerHTML = '<p style="color:var(--t3)">Ładowanie…</p>';
  try {
    const d = await apiFetch('/api/admin/analytics/llm?period=' + _llmPeriod);
    let html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">';
    html += '<div><div style="font-weight:600;margin-bottom:8px;font-size:0.88rem">Wg typu wywołania</div>' +
      '<table class="data-table" style="font-size:0.82rem"><thead><tr><th>Typ</th><th>N</th><th>Avg</th><th>Cache</th></tr></thead><tbody>';
    if (!d.by_type.length) {
      html += _empty(4, 'Brak danych.');
    } else {
      html += d.by_type.map(r => {
        const hit = r.n ? Math.round((r.cache_hits / r.n) * 100) : 0;
        return '<tr><td>' + _esc(r.call_type) + '</td><td>' + r.n + '</td><td>' + _ms(r.avg_ms) + '</td><td>' + hit + '%</td></tr>';
      }).join('');
    }
    html += '</tbody></table></div>';
    html += '<div><div style="font-weight:600;margin-bottom:8px;font-size:0.88rem">Najwolniejsze</div>' +
      '<table class="data-table" style="font-size:0.82rem"><thead><tr><th>Typ</th><th>Latency</th><th>Błąd</th></tr></thead><tbody>';
    if (!d.slowest.length) {
      html += _empty(3, 'Brak danych.');
    } else {
      html += d.slowest.map(r =>
        '<tr><td>' + _esc(r.call_type) + '</td>' +
        '<td style="color:' + (r.latency_ms > 3000 ? 'var(--red)' : 'inherit') + '">' + _ms(r.latency_ms) + '</td>' +
        '<td style="color:var(--red);font-size:0.75rem">' + _esc(r.error || '') + '</td></tr>'
      ).join('');
    }
    html += '</tbody></table></div></div>';
    container.innerHTML = html;
  } catch (e) { container.innerHTML = '<p style="color:var(--red)">Błąd: ' + _esc(e.message) + '</p>'; }
}

async function _loadErrors() {
  const tbody = document.getElementById('ana-errors-body');
  try {
    const d = await apiFetch('/api/admin/analytics/errors?limit=20');
    if (!d.errors.length) { tbody.innerHTML = _empty(5, 'Brak błędów.'); return; }
    tbody.innerHTML = d.errors.map(e => {
      const ts = e.created_at ? new Date(e.created_at).toLocaleTimeString('pl-PL') : '—';
      return '<tr>' +
        '<td style="white-space:nowrap;font-size:0.8rem;color:var(--t3)">' + _esc(ts) + '</td>' +
        '<td><span style="font-size:0.75rem;background:var(--red-light);color:var(--red);padding:2px 6px;border-radius:4px">' + _esc(e.source) + '</span></td>' +
        '<td style="font-size:0.82rem">' + _esc(e.event_type) + '</td>' +
        '<td style="font-size:0.8rem">' + _esc(e.campaign_id ?? '—') + '</td>' +
        '<td style="font-size:0.8rem;color:var(--t2)">' + _esc(e.detail || '') + '</td></tr>';
    }).join('');
  } catch (e) { tbody.innerHTML = _empty(5, 'Błąd: ' + e.message); }
}

function _activateTab(key) {
  document.querySelectorAll('#ana-tabs .stab').forEach(b =>
    b.classList.toggle('active', b.dataset.anatab === key)
  );
  document.querySelectorAll('.stab-panel').forEach(p => {
    p.style.display = p.id === 'anatab-' + key ? '' : 'none';
  });
  if (!_tabLoaded.has(key)) {
    _tabLoaded.add(key);
    switch (key) {
      case 'players': _loadPlayers(); break;
      case 'events':  _loadEvents();  break;
      case 'llm':     _loadLlm();     break;
      case 'errors':  _loadErrors();  break;
    }
  }
}

export async function init(panel) {
  panel.innerHTML = _html();
  _loadKpi();
  _tabLoaded.add('players');
  _loadPlayers();

  document.getElementById('ana-tabs').addEventListener('click', e => {
    const btn = e.target.closest('[data-anatab]');
    if (btn) _activateTab(btn.dataset.anatab);
  });

  document.getElementById('ev-apply-btn')?.addEventListener('click', () => {
    _tabLoaded.delete('events');
    _activateTab('events');
  });

  document.getElementById('anatab-llm')?.addEventListener('click', e => {
    const btn = e.target.closest('[data-llmperiod]');
    if (!btn) return;
    document.querySelectorAll('[data-llmperiod]').forEach(b => b.classList.toggle('on', b === btn));
    _llmPeriod = btn.dataset.llmperiod;
    _tabLoaded.delete('llm');
    _loadLlm();
  });

  document.getElementById('ana-refresh')?.addEventListener('click', () => {
    _tabLoaded.clear();
    _loadKpi();
    const active = document.querySelector('#ana-tabs .stab.active')?.dataset.anatab || 'players';
    _activateTab(active);
  });
}
