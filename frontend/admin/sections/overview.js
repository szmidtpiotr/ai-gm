// FADM-P1 (#403) — sekcja overview, port 1:1 z admin_panel_v3/index.html.
// Statystyki przeglądowe + 2 feedy (tury/audyt) + 6 zakładek analityki (days filter).
// Wszystkie endpointy bez zmian (backend nietknięty). Wywołania przez shared/api.js.
import { apiFetch, APIError } from '../shared/api.js';
import { esc } from '../shared/table.js';
import { showToast } from '../shared/toast.js';

// ── Helpers (port z monolitu) ──────────────────────────────────────────────
function _timeAgo(iso) {
  if (!iso) return '';
  const diff = Math.round((Date.now() - new Date(iso)) / 1000);
  if (diff < 60) return 'przed chwilą';
  if (diff < 3600) return `${Math.round(diff / 60)} min temu`;
  if (diff < 86400) return `${Math.round(diff / 3600)} godz. temu`;
  return `${Math.round(diff / 86400)} dni temu`;
}

function _smallTable(rows, cols) {
  if (!rows.length) return '<div style="color:var(--t3);font-size:0.82rem">Brak danych.</div>';
  return `<table class="data-table" style="font-size:0.82rem"><thead><tr>${cols.map(c => `<th>${esc(c.label)}</th>`).join('')}</tr></thead><tbody>
    ${rows.map(r => `<tr>${cols.map(c => `<td class="${c.cls || ''}">${esc(r[c.k] ?? '—')}</td>`).join('')}</tr>`).join('')}
  </tbody></table>`;
}

// ── Markup sekcji (port z 2171-2272; bez mock-liczb, bez zmyślonych delt) ──
function _sectionHtml() {
  return `
  <section class="section active" id="section-overview">
    <div class="section-header">
      <div>
        <div class="section-heading">Przegląd</div>
        <div class="section-sub">Statystyki i aktywność gry</div>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <div class="filter-group" id="ana-days-filter" style="display:none">
          <button class="chip on">7 dni</button>
          <button class="chip">30 dni</button>
          <button class="chip">Wszystko</button>
        </div>
        <button class="btn btn-secondary btn-sm" id="ov-refresh-btn">⟳ Odśwież</button>
      </div>
    </div>

    <div class="section-tabs" id="overview-tabs">
      <button class="stab active" data-ovtab="overview">Przegląd</button>
      <button class="stab" data-anatab="overview">Statystyki</button>
      <button class="stab" data-anatab="dice">Kości</button>
      <button class="stab" data-anatab="combat">Walka</button>
      <button class="stab" data-anatab="economy">Gospodarka</button>
      <button class="stab" data-anatab="events">Zdarzenia</button>
      <button class="stab" data-anatab="llm">LLM</button>
    </div>

    <div class="stab-panel active" id="ovtab-overview">
      <div class="stat-grid">
        <div class="stat-card"><div class="stat-label">Kampanie aktywne</div><div class="stat-row"><div class="stat-value">—</div></div><div class="stat-sub">aktywne kampanie</div></div>
        <div class="stat-card"><div class="stat-label">Gracze</div><div class="stat-row"><div class="stat-value">—</div></div><div class="stat-sub">zarejestrowani</div></div>
        <div class="stat-card"><div class="stat-label">Tury dziś</div><div class="stat-row"><div class="stat-value">—</div></div><div class="stat-sub">tury wykonane dzisiaj</div></div>
        <div class="stat-card"><div class="stat-label">Rozmiar bazy</div><div class="stat-row"><div class="stat-value">—</div></div><div class="stat-sub">plik ai_gm.db</div></div>
      </div>

      <div class="feeds-grid">
        <div class="card">
          <div class="card-header"><span class="card-title">Ostatnie tury</span><span class="card-count" id="ov-turns-count">—</span></div>
          <div id="ov-turns-feed"><div style="color:var(--t3);padding:14px;text-align:center;font-size:0.82rem">Ładowanie…</div></div>
        </div>
        <div class="card">
          <div class="card-header"><span class="card-title">Zmiany w treści</span><span class="card-count" id="ov-audit-count">—</span></div>
          <div id="ov-audit-feed"><div style="color:var(--t3);padding:14px;text-align:center;font-size:0.82rem">Ładowanie…</div></div>
        </div>
      </div>
    </div>

    <div class="stab-panel" id="anatab-overview" style="margin-top:14px">
      <div class="stat-grid" style="margin-bottom:16px">
        <div class="stat-card"><div class="stat-label">Tury łącznie</div><div class="stat-row"><div class="stat-value" id="ana-total-turns">—</div></div><div class="stat-sub" id="ana-turns-sub">Ładowanie…</div></div>
        <div class="stat-card"><div class="stat-label">Śr. tury/sesja</div><div class="stat-row"><div class="stat-value" id="ana-avg-turns">—</div></div><div class="stat-sub" id="ana-avg-sub">—</div></div>
        <div class="stat-card"><div class="stat-label">Walki stoczone</div><div class="stat-row"><div class="stat-value" id="ana-combat-total">—</div></div><div class="stat-sub" id="ana-combat-sub">—</div></div>
        <div class="stat-card"><div class="stat-label">Nat 20 / Nat 1</div><div class="stat-row"><div class="stat-value" id="ana-nat20">—</div></div><div class="stat-sub" id="ana-nat-sub">—</div></div>
      </div>
      <div class="two-col" style="margin-bottom:16px">
        <div class="card"><div class="card-header"><span class="card-title">Tury dziennie</span><span class="card-count">7 dni</span></div><div class="bar-chart" id="ana-turns-chart"><div style="padding:12px;color:var(--t3);text-align:center">Ładowanie…</div></div></div>
        <div class="card"><div class="card-header"><span class="card-title">Klasy postaci</span><span class="card-count">aktywne kampanie</span></div><div class="bar-chart" id="ana-archetype-chart"><div style="padding:12px;color:var(--t3);text-align:center">Ładowanie…</div></div></div>
      </div>
      <div class="card"><div class="card-header"><span class="card-title">Aktywni gracze</span><span class="card-count">7 dni</span></div><div class="table-wrap"><table class="data-table" id="active-players-table"><thead><tr><th><div class="th-inner">Gracz</div></th><th><div class="th-inner">Kampania</div></th><th><div class="th-inner">Tury (7 dni)</div></th><th><div class="th-inner">Śr. czas sesji</div></th></tr></thead><tbody><tr><td colspan="4" style="text-align:center;padding:20px;color:var(--t3)">Ładowanie…</td></tr></tbody></table></div></div>
    </div>
    <div class="stab-panel" id="anatab-dice" style="margin-top:14px"><div class="card"><div class="card-header"><span class="card-title">Rozkład rzutów d20</span></div><div id="ana-dice-chart" style="padding:14px"><div style="text-align:center;color:var(--t3);padding:20px">Ładowanie…</div></div></div></div>
    <div class="stab-panel" id="anatab-combat" style="margin-top:14px"><div class="two-col" style="gap:14px"><div class="card"><div class="card-header"><span class="card-title">Najczęściej zabijani</span></div><div id="ana-killed" style="padding:14px"><div style="color:var(--t3)">Ładowanie…</div></div></div><div class="card"><div class="card-header"><span class="card-title">Najgroźniejsi wrogowie</span></div><div id="ana-deadliest" style="padding:14px"><div style="color:var(--t3)">Ładowanie…</div></div></div></div></div>
    <div class="stab-panel" id="anatab-economy" style="margin-top:14px"><div class="two-col" style="gap:14px"><div class="card"><div class="card-header"><span class="card-title">Najczęstsze przedmioty</span></div><div id="ana-econ-items" style="padding:14px"><div style="color:var(--t3)">Ładowanie…</div></div></div><div class="card"><div class="card-header"><span class="card-title">Źródło łupów</span></div><div id="ana-econ-sources" style="padding:14px"><div style="color:var(--t3)">Ładowanie…</div></div></div></div></div>
    <div class="stab-panel" id="anatab-events" style="margin-top:14px"><div class="card"><div class="card-header"><span class="card-title">Ostatnie zdarzenia</span></div><div id="ana-events" style="padding:0"><div style="text-align:center;color:var(--t3);padding:20px">Ładowanie…</div></div></div></div>
    <div class="stab-panel" id="anatab-llm" style="margin-top:14px"><div class="card" style="margin-bottom:14px"><div class="card-header"><span class="card-title">Wywołania wg typu</span></div><div id="ana-llm-types" style="padding:14px"><div style="color:var(--t3)">Ładowanie…</div></div></div><div class="card"><div class="card-header"><span class="card-title">Najwolniejsze wywołania</span></div><div id="ana-llm-slowest" style="padding:14px"><div style="color:var(--t3)">Ładowanie…</div></div></div></div>
    <div class="stab-panel" id="anatab-mcp" style="margin-top:14px"><div class="card"><div class="card-header"><span class="card-title">MCP — status</span></div><div style="padding:14px;color:var(--t3);font-size:0.85rem">MCP informacje dostępne w v2: <a href="/admin2/#analytics" target="_blank" style="color:var(--accent)">otwórz w v2 ↗</a></div></div></div>
  </section>`;
}

// ── init(panel) ────────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = _sectionHtml();

  // Stan analityki (lokalny dla tego montażu sekcji).
  let analyticsDays = 7;
  const anaTabLoaded = new Set();

  // ── Loader: główny przegląd ──────────────────────────────────────────────
  async function loadOverview() {
    const activeAnaTab = document.querySelector('#overview-tabs .stab[data-anatab].active');
    if (activeAnaTab) { loadAnalytics(); if (!anaTabLoaded.has(activeAnaTab.dataset.anatab)) loadAnalyticsTab(activeAnaTab.dataset.anatab); }
    try {
      const d = await apiFetch('/api/admin/overview');
      const cards = document.querySelectorAll('#section-overview #ovtab-overview .stat-card');
      if (cards[0]) cards[0].querySelector('.stat-value').textContent = d.campaigns_active ?? '—';
      if (cards[1]) cards[1].querySelector('.stat-value').textContent = d.users_total ?? '—';
      if (cards[2]) cards[2].querySelector('.stat-value').textContent = d.turns_today ?? '—';
      if (cards[3]) cards[3].querySelector('.stat-value').textContent = d.db_size_mb != null ? d.db_size_mb.toFixed(1) + ' MB' : '—';

      // Recent turns feed
      const turnsFeed = document.getElementById('ov-turns-feed');
      const turnsCount = document.getElementById('ov-turns-count');
      const turns = d.recent_turns || [];
      if (turnsCount) turnsCount.textContent = turns.length ? `${turns.length} ostatnich` : 'brak';
      if (turnsFeed) {
        if (!turns.length) {
          turnsFeed.innerHTML = '<div style="color:var(--t3);padding:14px;text-align:center;font-size:0.82rem">Brak tur.</div>';
        } else {
          turnsFeed.innerHTML = turns.map(t => {
            const ut = (t.user_text || '').slice(0, 60).trim();
            const at = (t.assistant_text || '').slice(0, 60).trim();
            const time = t.created_at ? new Date(t.created_at).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' }) : '';
            return `<div class="feed-row"><div class="feed-icon blue">⚔</div><div class="feed-text"><strong>${esc(t.campaign_title || ('Kampania ' + t.id))}</strong> ${esc(ut)}${ut.length === 60 ? '…' : ''}${at ? ` <span style="color:var(--t3)">— ${esc(at)}${at.length === 60 ? '…' : ''}</span>` : ''}</div><div class="feed-time">${esc(time)}</div></div>`;
          }).join('');
        }
      }

      // Recent content changes (audit log)
      const auditFeed = document.getElementById('ov-audit-feed');
      const auditCount = document.getElementById('ov-audit-count');
      const audit = d.recent_audit || [];
      if (auditCount) auditCount.textContent = audit.length ? `${audit.length} ostatnich` : 'brak';
      if (auditFeed) {
        if (!audit.length) {
          auditFeed.innerHTML = '<div style="color:var(--t3);padding:14px;text-align:center;font-size:0.82rem">Brak zmian.</div>';
        } else {
          const opIcon = { INSERT: ['green', '+'], UPDATE: ['blue', '✎'], DELETE: ['red', '✕'], APPROVE: ['green', '✓'] };
          auditFeed.innerHTML = audit.map(a => {
            const [cls, icon] = opIcon[a.operation] || ['slate', '·'];
            const time = a.performed_at ? new Date(a.performed_at).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' }) : '';
            return `<div class="feed-row"><div class="feed-icon ${cls}">${icon}</div><div class="feed-text">${esc(a.operation || '')} <strong>${esc(a.row_key || '')}</strong> <span style="color:var(--t3)">w ${esc(a.table_name || '')}</span></div><div class="feed-time">${esc(time)}</div></div>`;
          }).join('');
        }
      }
    } catch (e) {
      // FADM-P2: błąd widoczny dla admina (zamiast cichego console.warn).
      if (!(e instanceof APIError && e.status === 401)) showToast('Nie udało się załadować przeglądu: ' + e.message, 'error');
      const tf = document.getElementById('ov-turns-feed');
      if (tf) tf.innerHTML = `<div style="color:var(--red);padding:14px;text-align:center;font-size:0.82rem">Błąd: ${esc(e.message)}</div>`;
    }
  }

  // ── Loader: analityka (zakładka Statystyki) ──────────────────────────────
  async function loadAnalytics() {
    anaTabLoaded.clear();
    try {
      const [ov, dice, combat] = await Promise.all([
        apiFetch(`/api/admin/analytics/overview?days=${analyticsDays}`),
        apiFetch(`/api/admin/analytics/dice?days=${analyticsDays}`),
        apiFetch(`/api/admin/analytics/combat?days=${analyticsDays}`),
      ]);
      const totals = ov.totals || {};
      const cards = document.querySelectorAll('#anatab-overview .stat-card');

      if (cards[0]) {
        cards[0].querySelector('.stat-value').textContent = totals.turns ?? '—';
        cards[0].querySelector('.stat-sub').textContent = `${analyticsDays} dni`;
      }
      if (cards[1]) {
        const camps = totals.active_campaigns ?? 0;
        const avg = totals.turns && camps ? (totals.turns / camps).toFixed(1) : '—';
        cards[1].querySelector('.stat-value').textContent = avg;
        cards[1].querySelector('.stat-sub').textContent = `z ${camps || '?'} aktywnych kampanii`;
      }
      if (cards[2]) {
        cards[2].querySelector('.stat-value').textContent = totals.combats ?? '—';
        const oc = combat.outcomes || {};
        const won = oc.victory ?? 0; const total = combat.total_combats ?? 0;
        cards[2].querySelector('.stat-sub').textContent = total ? `${won} wygranych, ${total - won} innych` : '— wyników';
      }
      if (cards[3]) {
        const nat20 = dice.crit_count ?? '—';
        const nat1 = dice.fumble_count ?? '—';
        cards[3].querySelector('.stat-value').textContent = nat20;
        cards[3].querySelector('.stat-sub').textContent = `vs ${nat1} nat 1 · śr. ${dice.avg_roll?.toFixed(1) ?? '—'}`;
      }

      // Turns per day bar chart
      const turnsChart = document.getElementById('ana-turns-chart');
      if (turnsChart && ov.turns_per_day?.length) {
        const days = ov.turns_per_day.slice(-7);
        const max = Math.max(...days.map(d => d.count), 1);
        const dayNames = ['Nd', 'Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob'];
        turnsChart.innerHTML = days.map(d => {
          const date = new Date(d.day + 'T12:00:00Z');
          const label = dayNames[date.getDay()];
          const pct = Math.round(d.count / max * 100);
          return `<div class="bar-row"><span class="bar-label">${label}</span><div class="bar-track"><div class="bar-fill blue" style="width:${pct}%"></div></div><span class="bar-val">${d.count}</span></div>`;
        }).join('');
      }

      // Archetype distribution + active players — z żywych kampanii
      try {
        const camps = await apiFetch('/api/admin/campaigns/live');
        const archChart = document.getElementById('ana-archetype-chart');
        if (archChart) {
          const items = (camps.items || []).filter(c => c.status === 'active' && c.char_archetype);
          if (!items.length) {
            archChart.innerHTML = '<div style="padding:12px;color:var(--t3);font-size:0.82rem;text-align:center">Brak aktywnych kampanii.</div>';
          } else {
            const counts = {};
            items.forEach(c => { counts[c.char_archetype] = (counts[c.char_archetype] || 0) + 1; });
            const total = items.length;
            const archMap = { warrior: ['Wojownik', 'blue'], scholar: ['Uczony', 'green'], rogue: ['Złodziej', 'amber'], ranger: ['Ranger', 'slate'], priest: ['Kapłan', 'slate'] };
            const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
            archChart.innerHTML = sorted.map(([k, n]) => {
              const [label, cls] = archMap[k] || [k, 'slate'];
              const pct = Math.round(n / total * 100);
              return `<div class="bar-row"><span class="bar-label-wide">${esc(label)}</span><div class="bar-track"><div class="bar-fill ${cls}" style="width:${pct}%"></div></div><span class="bar-val">${pct}%</span></div>`;
            }).join('');
          }
        }
        const apTbody = document.querySelector('#active-players-table tbody');
        if (apTbody) {
          const top = (camps.items || []).filter(c => c.owner_username && (c.turn_count || 0) > 0)
            .sort((a, b) => (b.turn_count || 0) - (a.turn_count || 0)).slice(0, 8);
          if (!top.length) {
            apTbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:20px;color:var(--t3)">Brak danych.</td></tr>';
          } else {
            apTbody.innerHTML = top.map(c => `<tr>
              <td class="td-name">${esc(c.owner_username)}</td>
              <td class="td-muted">${esc(c.title || ('Kampania ' + c.id))}</td>
              <td class="td-mono">${c.turn_count ?? 0}</td>
              <td class="td-muted">—</td>
            </tr>`).join('');
          }
        }
      } catch (e) { console.warn('analytics arch', e.message); }

    } catch (e) {
      if (!(e instanceof APIError && e.status === 401)) showToast('Błąd analityki: ' + e.message, 'error');
    }
  }

  // ── Sub-taby analityki ───────────────────────────────────────────────────
  async function loadAnalyticsTab(tab) {
    if (anaTabLoaded.has(tab)) return;
    anaTabLoaded.add(tab);
    try {
      if (tab === 'dice') await loadAnaDice();
      else if (tab === 'combat') await loadAnaCombat();
      else if (tab === 'economy') await loadAnaEconomy();
      else if (tab === 'events') await loadAnaEvents();
      else if (tab === 'llm') await loadAnaLlm();
    } catch (e) { anaTabLoaded.delete(tab); showToast(`Błąd zakładki ${tab}: ${e.message}`, 'error'); }
  }

  async function loadAnaDice() {
    const host = document.getElementById('ana-dice-chart');
    if (!host) return;
    const d = await apiFetch(`/api/admin/analytics/dice?days=${analyticsDays}`);
    const dist = Array.isArray(d.distribution) ? d.distribution : [];
    if (!dist.length || !d.total_rolls) { host.innerHTML = '<div style="color:var(--t3);padding:14px">Brak danych.</div>'; return; }
    const max = Math.max(...dist.map(e => e.total), 1);
    host.innerHTML = `<div class="bar-chart">${dist.map(e => {
      const pct = Math.round(e.total / max * 100);
      const cls = e.value === 20 ? 'green' : e.value === 1 ? 'red' : 'blue';
      return `<div class="bar-row"><span class="bar-label">${e.value}</span><div class="bar-track"><div class="bar-fill ${cls}" style="width:${pct}%"></div></div><span class="bar-val">${e.total}</span></div>`;
    }).join('')}</div>
    <div style="margin-top:10px;color:var(--t3);font-size:0.78rem">Nat 20: <strong style="color:var(--t1)">${d.crit_count ?? 0}</strong> · Nat 1: <strong style="color:var(--t1)">${d.fumble_count ?? 0}</strong> · Średnia: <strong style="color:var(--t1)">${d.avg_roll?.toFixed(2) ?? '—'}</strong></div>`;
  }

  async function loadAnaCombat() {
    const d = await apiFetch(`/api/admin/analytics/combat?days=${analyticsDays}`);
    document.getElementById('ana-killed').innerHTML = _smallTable(d.top_enemies_killed || [], [{ k: 'name', label: 'Wróg' }, { k: 'kills', label: 'Zabić', cls: 'td-mono' }]);
    document.getElementById('ana-deadliest').innerHTML = _smallTable(d.player_killers || [], [{ k: 'name', label: 'Wróg' }, { k: 'count', label: 'Zabójstwa gracza', cls: 'td-mono' }]);
  }

  async function loadAnaEconomy() {
    const d = await apiFetch(`/api/admin/analytics/economy?days=${analyticsDays}`);
    document.getElementById('ana-econ-items').innerHTML = _smallTable(d.top_items || [], [{ k: 'name', label: 'Przedmiot' }, { k: 'type', label: 'Typ' }, { k: 'total', label: 'Ilość', cls: 'td-mono' }]);
    document.getElementById('ana-econ-sources').innerHTML = _smallTable(d.by_source || [], [{ k: 'source', label: 'Źródło' }, { k: 'count', label: 'Sztuk', cls: 'td-mono' }]);
  }

  async function loadAnaEvents() {
    const host = document.getElementById('ana-events');
    const d = await apiFetch(`/api/admin/analytics/events?days=${analyticsDays}`);
    const events = d.events || d.items || [];
    if (!events.length) { host.innerHTML = '<div style="color:var(--t3);padding:20px;text-align:center">Brak zdarzeń.</div>'; return; }
    host.innerHTML = events.slice(0, 50).map(e => {
      const sevColor = { info: 'var(--t3)', warn: '#f59e0b', error: '#ef4444' }[e.severity] || 'var(--t3)';
      return `<div style="padding:10px 14px;border-bottom:1px solid var(--border);display:grid;grid-template-columns:auto 1fr auto auto;gap:10px;align-items:center;font-size:0.82rem">
        <span style="color:${sevColor};width:6px;height:6px;border-radius:50%;background:${sevColor};display:inline-block"></span>
        <div><div style="font-weight:600">${esc(e.event_type || e.type || 'event')}</div><div style="color:var(--t3);font-size:0.72rem;margin-top:2px">${esc((e.event_data || '').slice(0, 80))}</div></div>
        <span style="color:var(--t3);font-size:0.72rem">kamp #${e.campaign_id ?? '—'}</span>
        <span style="color:var(--t3);font-size:0.72rem">${esc(_timeAgo(e.created_at || e.ts) || '—')}</span>
      </div>`;
    }).join('');
  }

  async function loadAnaLlm() {
    try {
      const d = await apiFetch(`/api/admin/analytics/llm?days=${analyticsDays}`);
      const byType = (d.by_type || []).map(r => ({ ...r, avg_ms: r.avg_ms != null ? Math.round(r.avg_ms) : null }));
      document.getElementById('ana-llm-types').innerHTML = _smallTable(byType, [
        { k: 'call_type', label: 'Typ' },
        { k: 'n', label: 'Wywołania', cls: 'td-mono' },
        { k: 'avg_ms', label: 'Śr. ms', cls: 'td-mono' },
        { k: 'cache_hits', label: 'Cache', cls: 'td-mono' },
      ]);
      const slowest = d.slowest || [];
      document.getElementById('ana-llm-slowest').innerHTML = _smallTable(slowest, [
        { k: 'call_type', label: 'Typ' },
        { k: 'model', label: 'Model' },
        { k: 'latency_ms', label: 'Czas (ms)', cls: 'td-mono' },
        { k: 'created_at', label: 'Kiedy', cls: 'td-muted' },
        { k: 'error', label: 'Błąd' },
      ]);
    } catch (e) {
      document.getElementById('ana-llm-types').innerHTML = `<div style="color:var(--red)">${esc(e.message)}</div>`;
    }
  }

  // ── Wiring: przełączanie zakładek (port 5705-5725) ───────────────────────
  document.getElementById('overview-tabs')?.addEventListener('click', e => {
    const btn = e.target.closest('.stab[data-ovtab], .stab[data-anatab]');
    if (!btn) return;
    document.querySelectorAll('#overview-tabs .stab').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('#section-overview > .stab-panel').forEach(p => p.classList.remove('active'));
    const daysFilter = document.getElementById('ana-days-filter');
    if (btn.dataset.ovtab) {
      const panelEl = document.getElementById(`ovtab-${btn.dataset.ovtab}`);
      if (panelEl) panelEl.classList.add('active');
      if (daysFilter) daysFilter.style.display = 'none';
    } else if (btn.dataset.anatab) {
      const tab = btn.dataset.anatab;
      const panelEl = document.getElementById(`anatab-${tab}`);
      if (panelEl) panelEl.classList.add('active');
      if (daysFilter) daysFilter.style.display = '';
      loadAnalytics();
      if (!anaTabLoaded.has(tab)) loadAnalyticsTab(tab);
    }
  });

  // Days filter chips (port 14447-14455)
  document.getElementById('ana-days-filter')?.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.getElementById('ana-days-filter')?.querySelectorAll('.chip').forEach(c => c.classList.remove('on'));
      chip.classList.add('on');
      analyticsDays = chip.textContent.trim() === '30 dni' ? 30 : chip.textContent.trim() === 'Wszystko' ? 365 : 7;
      loadAnalytics();
      const active = document.querySelector('#overview-tabs .stab[data-anatab].active');
      if (active) { anaTabLoaded.delete(active.dataset.anatab); loadAnalyticsTab(active.dataset.anatab); }
    });
  });

  document.getElementById('ov-refresh-btn')?.addEventListener('click', () => loadOverview());

  await loadOverview();
}
