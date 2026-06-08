/**
 * FADM-P12 (#414) — sekcja Zgłoszenia błędów.
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

// ── Helpers ────────────────────────────────────────────────────────────────────
function _esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── State ─────────────────────────────────────────────────────────────────────
let _brItems = [];
let _brCurrentId = null;
let _brCurrentCtxJson = null;
let _brViewMode = 'text'; // 'text' | 'json'

// ── Functions ─────────────────────────────────────────────────────────────────

function _brStatusBadge(status, hasGH) {
  if (!hasGH) return '';
  if (status === 'closed') return '<span class="badge badge-green" style="margin-left:6px">✓ closed</span>';
  return '<span class="badge badge-amber" style="margin-left:6px">● open</span>';
}

async function _loadBugReports() {
  const tbody = document.getElementById('br-tbody');
  if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:32px;color:var(--t3)">Ładowanie…</td></tr>`;
  try {
    const d = await apiFetch('/api/admin/bug-reports');
    _brItems = d.items || [];
    const withGH = _brItems.filter(r => r.github_issue_url).length;
    const local = _brItems.length - withGH;

    const total = document.getElementById('br-total');
    const gh = document.getElementById('br-github');
    const loc = document.getElementById('br-local');
    const sub = document.getElementById('br-sub');
    const badge = document.getElementById('br-nav-badge');

    if (total) total.textContent = _brItems.length;
    if (gh) gh.textContent = withGH;
    if (loc) loc.textContent = local;
    if (sub) sub.textContent = `${_brItems.length} zgłoszeń · ${withGH} na GitHub`;
    if (badge) { badge.textContent = _brItems.length; badge.style.display = _brItems.length ? '' : 'none'; }

    if (!tbody) return;
    if (!_brItems.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--t3)">Brak zgłoszeń.</td></tr>`;
      return;
    }
    tbody.innerHTML = _brItems.map((r, i) => {
      const obs = _esc((r.observation || '').slice(0, 80)) + (r.observation?.length > 80 ? '…' : '');
      const date = r.created_at ? r.created_at.slice(0, 16).replace('T', ' ') : '—';
      const ghLink = r.github_issue_url
        ? `<a href="${_esc(r.github_issue_url)}" target="_blank" class="badge badge-green" style="text-decoration:none">#${r.github_issue_number}</a>`
        : `<span class="badge badge-slate">lokalne</span>`;
      const statusCell = r.github_issue_url
        ? (r.github_status === 'closed'
            ? `<span class="badge badge-green">✓ closed</span>`
            : `<span class="badge badge-amber">● open</span>`)
        : '—';
      const typeCell = r.report_type === 'feature'
        ? `<span class="badge badge-green" style="font-size:0.7rem">💡</span>`
        : `<span class="badge badge-red" style="font-size:0.7rem">🐛</span>`;
      return `<tr style="cursor:pointer" onclick="openBrDrawer(${i})">
        <td class="td-mono" style="font-size:0.78rem;white-space:nowrap">${date}</td>
        <td>${typeCell} <span class="badge badge-blue">${_esc(r.username || '?')}</span></td>
        <td style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${obs}</td>
        <td>${ghLink}</td>
        <td>${statusCell}</td>
        <td><button class="btn-icon" onclick="event.stopPropagation();openBrDrawer(${i})">▶</button></td>
      </tr>`;
    }).join('');
  } catch(e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:32px;color:#e55">${_esc(e.message)}</td></tr>`;
  }
}

function _brRenderText(r, ctx) {
  const char = ctx.character || {};
  const camp = ctx.campaign || {};
  const turns = ctx.last_turns || [];
  const inventory = ctx.inventory || [];
  const combatRolls = ctx.combat_rolls || [];
  const activeCombat = ctx.active_combat || {};

  const charLine = char.name
    ? `${_esc(char.name)} — HP: ${char.hp_current}/${char.hp_max}${char.mana_current != null ? `, mana: ${char.mana_current}/${char.mana_max}` : ''}, level ${char.level}, ${_esc(char.archetype || '?')}, gold: ${char.gold || 0}`
    : '(brak danych postaci)';
  const statsHtml = char.stats
    ? Object.entries(char.stats).map(([k,v]) => `<span class="badge badge-slate" style="margin:2px">${k}: ${v}</span>`).join(' ')
    : '—';
  const condHtml = (char.conditions||[]).length
    ? (char.conditions||[]).map(c => `<span class="badge badge-red" style="margin:2px">${_esc(String(c))}</span>`).join(' ')
    : '<span style="color:var(--t3);font-size:0.82rem">brak</span>';

  const turnsHtml = turns.length
    ? turns.map(t => {
        const raw = t.assistant_text || '';
        let pretty = raw;
        try { pretty = JSON.stringify(JSON.parse(raw), null, 2); } catch {}
        const hasRaw = raw.length > 0;
        return `
        <div class="br-turn-card" style="margin-bottom:10px;padding:8px;background:rgba(0,0,0,0.2);border-radius:6px;font-size:0.79rem">
          <div style="display:flex;justify-content:space-between;align-items:center;color:var(--t3);margin-bottom:4px">
            <span>Tura ${t.turn_number} [${t.route || '?'}] · ${(t.created_at||'').slice(0,16)}</span>
            ${hasRaw ? `<button onclick="_toggleTurnJson(this)" style="font-size:0.68rem;padding:1px 7px;background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.15);border-radius:4px;color:var(--t3);cursor:pointer;white-space:nowrap">{ } JSON</button>` : ''}
          </div>
          <div class="br-turn-text">
            <div><b>Gracz:</b> ${_esc((t.user_text||'').slice(0,1000))}</div>
            ${hasRaw ? `<div style="margin-top:4px;color:var(--t2)"><b>GM:</b> ${_esc(raw.slice(0,2000))}</div>` : ''}
          </div>
          ${hasRaw ? `<pre class="br-turn-json" style="display:none;background:rgba(0,0,0,0.4);border-radius:6px;padding:10px;font-size:0.71rem;line-height:1.5;overflow-x:auto;white-space:pre-wrap;word-break:break-all;max-height:320px;margin-top:6px">${_esc(pretty)}</pre>` : ''}
        </div>`;
      }).join('')
    : '<div style="color:var(--t3);font-size:0.82rem">Brak tur.</div>';

  const invHtml = inventory.length
    ? inventory.map(i => {
        const key = i.item_key || i.weapon_key || i.consumable_key || '?';
        const label = i.label || key;
        return `<span class="badge badge-slate" style="margin:2px">${_esc(label)} ×${i.quantity}${i.equipped ? ' ⚔' : ''}</span>`;
      }).join(' ')
    : '<span style="color:var(--t3);font-size:0.82rem">pusty</span>';

  let combatHtml = '';
  if (activeCombat.round != null) {
    const combatants = (activeCombat.combatants || []).map(c =>
      typeof c === 'object'
        ? `<span class="badge ${c.type === 'player' ? 'badge-blue' : 'badge-red'}" style="margin:2px">${_esc(c.name||'?')} HP:${c.hp_current??'?'}/${c.hp_max??'?'} z:${c.zone||'?'}</span>`
        : ''
    ).join(' ');
    combatHtml = `<div style="margin-bottom:6px;font-size:0.8rem">Runda ${activeCombat.round}, status: ${_esc(activeCombat.status||'?')}, tura: ${_esc(String(activeCombat.current_turn||'?'))}</div>${combatants}`;
  }
  const rollsHtml = combatRolls.length
    ? combatRolls.map(roll => {
        const hit = roll.hit ? '✅' : '❌';
        const parts = [`T${roll.turn_number}`, hit, `<b>${_esc(roll.actor||'?')}</b>`, `[${_esc(roll.event_type||'?')}]`];
        if (roll.target_name) parts.push(`→ ${_esc(roll.target_name)}`);
        if (roll.roll_value != null) parts.push(`d20=${roll.roll_value}`);
        if (roll.damage != null) parts.push(`dmg=${roll.damage}`);
        if (roll.hp_after != null) parts.push(`hp_after=${roll.hp_after}`);
        return `<div style="font-size:0.78rem;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.05)">${parts.join(' ')}${roll.narrative ? `<br><span style="color:var(--t3)">${_esc(String(roll.narrative).slice(0,150))}</span>` : ''}</div>`;
      }).join('')
    : '<div style="color:var(--t3);font-size:0.82rem">Brak rzutów walki.</div>';

  return `
    <div style="margin-bottom:16px">
      <div style="font-size:0.75rem;color:var(--t3);margin-bottom:4px">OBSERWACJA</div>
      <div style="background:rgba(0,0,0,0.25);border-radius:8px;padding:12px;font-size:0.9rem;line-height:1.5">${_esc(r.observation || '—')}</div>
    </div>
    <div style="margin-bottom:16px">
      <div style="font-size:0.75rem;color:var(--t3);margin-bottom:4px">REPRODUKCJA</div>
      <div style="background:rgba(0,0,0,0.25);border-radius:8px;padding:12px;font-size:0.85rem;line-height:1.5;white-space:pre-wrap">${_esc(r.reproduction || '—')}</div>
    </div>
    <div style="margin-bottom:12px">
      <div style="font-size:0.75rem;color:var(--t3);margin-bottom:6px">STAN POSTACI</div>
      <div style="background:rgba(0,0,0,0.25);border-radius:8px;padding:12px;font-size:0.82rem">
        <div style="margin-bottom:6px">${charLine}</div>
        <div style="margin-bottom:6px">${statsHtml}</div>
        <div>Kondycje: ${condHtml}</div>
        ${camp.title ? `<div style="margin-top:6px;color:var(--t3)">Kampania: <b>${_esc(camp.title)}</b> (ID: ${camp.id}, ${camp.status})</div>` : ''}
      </div>
    </div>
    <div style="margin-bottom:12px">
      <div style="font-size:0.75rem;color:var(--t3);margin-bottom:6px">EKWIPUNEK</div>
      <div style="background:rgba(0,0,0,0.25);border-radius:8px;padding:10px;font-size:0.82rem">${invHtml}</div>
    </div>
    ${(activeCombat.round != null || combatRolls.length) ? `
    <div style="margin-bottom:12px">
      <div style="font-size:0.75rem;color:var(--t3);margin-bottom:6px">WALKA${activeCombat.round != null ? ' (aktywna)' : ''}</div>
      <div style="background:rgba(0,0,0,0.25);border-radius:8px;padding:10px;font-size:0.82rem">
        ${combatHtml}
        <div style="margin-top:8px;font-size:0.72rem;color:var(--t3);margin-bottom:4px">RZUTY (${combatRolls.length})</div>
        ${rollsHtml}
      </div>
    </div>` : ''}
    <div style="margin-bottom:12px">
      <div style="font-size:0.75rem;color:var(--t3);margin-bottom:6px">OSTATNIE TURY (${turns.length})</div>
      ${turnsHtml}
    </div>
    <div style="font-size:0.78rem;color:var(--t3);border-top:1px solid var(--border);padding-top:12px;display:flex;gap:12px;flex-wrap:wrap">
      <span>Gracz: <b>${_esc(r.username || '?')}</b></span>
      <span>ID kampanii: ${r.campaign_id || '—'}</span>
      <span>Data: ${(r.created_at||'').slice(0,16)}</span>
      ${r.github_issue_url ? `<a href="${_esc(r.github_issue_url)}" target="_blank" class="badge badge-green" style="text-decoration:none">GitHub #${r.github_issue_number}</a>` : '<span class="badge badge-slate">brak GitHub</span>'}
    </div>`;
}

function _brRenderJson(r) {
  let pretty = r.context_json || '{}';
  try { pretty = JSON.stringify(JSON.parse(pretty), null, 2); } catch {}
  return `<pre style="background:rgba(0,0,0,0.35);border-radius:8px;padding:14px;font-size:0.75rem;line-height:1.5;overflow:auto;white-space:pre-wrap;word-break:break-all;max-height:60vh">${_esc(pretty)}</pre>`;
}

function openBrDrawer(idx) {
  const r = _brItems[idx];
  if (!r) return;
  _brCurrentId = r.id;
  _brCurrentCtxJson = r.context_json;
  _brViewMode = 'text';

  document.getElementById('br-detail-id').textContent = r.id;
  document.getElementById('br-delete-btn').disabled = false;
  const typeBadge = document.getElementById('br-type-badge');
  if (typeBadge) typeBadge.innerHTML = r.report_type === 'feature'
    ? '<span class="badge badge-green">💡 Sugestia</span>'
    : '<span class="badge badge-red">🐛 Błąd</span>';

  const toggleBtn = document.getElementById('br-toggle-btn');
  if (toggleBtn) toggleBtn.textContent = '{ } JSON';

  const syncBtn = document.getElementById('br-sync-btn');
  if (syncBtn) { syncBtn.disabled = !r.github_issue_url; syncBtn.textContent = '🔄 Sync GitHub'; }

  const statusBadge = document.getElementById('br-gh-status-badge');
  if (statusBadge) statusBadge.innerHTML = _brStatusBadge(r.github_status, !!r.github_issue_url);

  let ctx = {};
  try { ctx = JSON.parse(r.context_json || '{}'); } catch {}
  document.getElementById('br-detail-body').innerHTML = _brRenderText(r, ctx);

  const backdrop = document.getElementById('br-drawer-backdrop');
  backdrop.style.display = 'flex';
}

function _toggleTurnJson(btn) {
  const card = btn.closest('.br-turn-card');
  const pre = card.querySelector('.br-turn-json');
  const textDiv = card.querySelector('.br-turn-text');
  const showJson = pre.style.display === 'none';
  pre.style.display = showJson ? 'block' : 'none';
  textDiv.style.display = showJson ? 'none' : '';
  btn.textContent = showJson ? '≡ Text' : '{ } JSON';
}

function toggleBrView() {
  const r = _brItems.find(x => x.id === _brCurrentId);
  if (!r) return;
  const btn = document.getElementById('br-toggle-btn');
  if (_brViewMode === 'text') {
    _brViewMode = 'json';
    btn.textContent = '≡ Text';
    document.getElementById('br-detail-body').innerHTML = _brRenderJson(r);
  } else {
    _brViewMode = 'text';
    btn.textContent = '{ } JSON';
    let ctx = {};
    try { ctx = JSON.parse(r.context_json || '{}'); } catch {}
    document.getElementById('br-detail-body').innerHTML = _brRenderText(r, ctx);
  }
}

async function syncBrGitHub() {
  if (!_brCurrentId) return;
  const btn = document.getElementById('br-sync-btn');
  btn.disabled = true;
  btn.textContent = '⏳…';
  try {
    const d = await apiFetch(`/api/admin/bug-reports/${_brCurrentId}/sync-github`, { method: 'POST' });
    const status = d.github_status;
    // update local cache
    const r = _brItems.find(x => x.id === _brCurrentId);
    if (r) r.github_status = status;
    const badge = document.getElementById('br-gh-status-badge');
    if (badge) badge.innerHTML = _brStatusBadge(status, true);
    showToast(`GitHub status: ${status}`, 'success');
  } catch(e) { showToast(e.message || 'Sync error.', 'error'); }
  finally { btn.disabled = false; btn.textContent = '🔄 Sync GitHub'; }
}

async function syncAllBrGitHub() {
  const btn = document.getElementById('br-sync-all-btn');
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = '⏳ Sync…';
  try {
    const d = await apiFetch('/api/admin/bug-reports/sync-all-github', { method: 'POST' });
    // update local cache statuses
    if (d.statuses) {
      for (const [id, status] of Object.entries(d.statuses)) {
        const r = _brItems.find(x => String(x.id) === String(id));
        if (r) r.github_status = status;
      }
    }
    showToast(`Sync: ${d.synced} zaktualizowano${d.errors ? `, ${d.errors} błędów` : ''}`, d.errors ? 'error' : 'success');
    _loadBugReports();
  } catch(e) { showToast(e.message || 'Błąd sync.', 'error'); }
  finally { btn.disabled = false; btn.textContent = '🔄 Sync GitHub'; }
}

function closeBrDrawer() {
  document.getElementById('br-drawer-backdrop').style.display = 'none';
  _brCurrentId = null;
}

async function deleteBrReport() {
  if (!_brCurrentId) return;
  if (!confirm(`Usunąć zgłoszenie #${_brCurrentId}?`)) return;
  const btn = document.getElementById('br-delete-btn');
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/bug-reports/${_brCurrentId}`, { method: 'DELETE' });
    closeBrDrawer();
    _loadBugReports();
    showToast('Usunięto.', 'success');
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; }
}

// ── Init ───────────────────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = `<div id="section-bugreports">
      <div class="section-header">
        <div>
          <div class="section-heading">Zgłoszenia błędów</div>
          <div class="section-sub" id="br-sub">Raporty od testerów</div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-secondary btn-sm" id="br-sync-all-btn" onclick="syncAllBrGitHub()">🔄 Sync GitHub</button>
          <button class="btn btn-secondary btn-sm" onclick="_loadBugReports()">⟳ Odśwież</button>
        </div>
      </div>

      <div class="stat-grid" style="margin-bottom:16px">
        <div class="stat-card">
          <div class="stat-label">Łącznie zgłoszeń</div>
          <div class="stat-row"><div class="stat-value" id="br-total">—</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Przesłano do GitHub</div>
          <div class="stat-row"><div class="stat-value" id="br-github">—</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Tylko lokalne</div>
          <div class="stat-row"><div class="stat-value" id="br-local">—</div></div>
        </div>
      </div>

      <div class="card" style="overflow:hidden">
        <div class="table-wrap" style="overflow-x:auto">
          <table class="data-table" id="br-table">
            <thead><tr>
              <th>Data</th>
              <th>Gracz</th>
              <th>Obserwacja</th>
              <th>GitHub</th>
              <th>Status</th>
              <th>Akcje</th>
            </tr></thead>
            <tbody id="br-tbody"><tr><td colspan="6" style="text-align:center;padding:32px;color:var(--t3)">Ładowanie…</td></tr></tbody>
          </table>
        </div>
      </div>

      <!-- Detail modal -->
      <div id="br-drawer-backdrop" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:800;align-items:center;justify-content:center;padding:16px" onclick="if(event.target===this)closeBrDrawer()">
        <div id="br-drawer" style="background:var(--bg2,#161310);border:1px solid var(--border);border-radius:12px;width:100%;max-width:680px;max-height:90vh;min-width:320px;min-height:200px;overflow:auto;resize:both;padding:24px;box-shadow:0 16px 64px rgba(0,0,0,0.7)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:8px">
            <div style="font-weight:700;font-size:15px">Zgłoszenie #<span id="br-detail-id"></span> <span id="br-type-badge"></span> <span id="br-gh-status-badge"></span></div>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn btn-secondary btn-sm" id="br-toggle-btn" onclick="toggleBrView()">{ } JSON</button>
              <button class="btn btn-secondary btn-sm" id="br-sync-btn" onclick="syncBrGitHub()">🔄 Sync GitHub</button>
              <button class="btn btn-danger btn-sm" id="br-delete-btn" onclick="deleteBrReport()">🗑 Usuń</button>
              <button class="btn-icon" onclick="closeBrDrawer()">✕</button>
            </div>
          </div>
          <div id="br-detail-body"></div>
        </div>
      </div>
  </div>`;
  _loadBugReports();
}

Object.assign(window, { syncAllBrGitHub, closeBrDrawer, toggleBrView, syncBrGitHub, deleteBrReport, openBrDrawer, _toggleTurnJson, _loadBugReports });
