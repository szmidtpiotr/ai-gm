/**
 * FADM-P9 (#411) — sekcja Gracze: konta, uprawnienia, drawer gracza.
 * Port 1:1 z admin_panel_v3/index.html.
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';
import { initSortableTable } from '../shared/table.js';

// ── Helpers ────────────────────────────────────────────────────────────────────
function _esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
const _loading = cols => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr>`;
const _errRow  = (cols, msg) => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--red);font-size:0.8rem">Błąd: ${_esc(msg)}</td></tr>`;

function _timeAgo(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const diff = Date.now() - d.getTime();
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days  = Math.floor(diff / 86400000);
  if (mins < 2)   return 'Teraz';
  if (mins < 60)  return `${mins} min temu`;
  if (hours < 24) return `${hours}h temu`;
  if (days === 1) return 'wczoraj';
  return d.toLocaleDateString('pl-PL');
}

// ── Module-level state ─────────────────────────────────────────────────────────
let _pdrawerCurrentUser = null;

// ── Mode labels ────────────────────────────────────────────────────────────────
const _MODE_LABELS = {
  ai_campaign_enabled:    { label: 'Kampania AI',                    desc: 'Generowanie kampanii przez AI na żywo.' },
  prebuilt_enabled:       { label: 'Gotowa kampania',                 desc: 'Wybór z predefiniowanych szablonów przygód.' },
  dungeon_enabled:        { label: 'Loch (stary)',                    desc: 'Farmowalne lochy — stary system proceduralny.' },
  dungeon_tiles_enabled:  { label: 'Loch (Kafelki)',                  desc: 'Nowy system kafelkowy z wizualnymi komnatami.' },
  multiplayer_enabled:    { label: 'Multiplayer (Wyprawa grupowa)',    desc: 'Lobby wieloosobowe — tworzenie i dołączanie do sesji grupowych.' },
};

// ── Filter / selection helpers ─────────────────────────────────────────────────
export function filterTableGeneric(input, tableId, nameClass) {
  const q = input.value.toLowerCase();
  document.querySelectorAll(`#${tableId} tbody tr`).forEach(row => {
    const name = row.querySelector(`.${nameClass}`)?.textContent.toLowerCase() || '';
    row.style.display = name.includes(q) ? '' : 'none';
  });
}

export function filterPlayers(chip, role) {
  document.querySelectorAll('#section-players .filter-group .chip').forEach(c => c.classList.remove('on'));
  chip.classList.add('on');
  document.querySelectorAll('#players-table tbody tr').forEach(row => {
    if (!role) { row.style.display = ''; return; }
    const badge = row.querySelector('.badge')?.textContent?.toLowerCase() || '';
    row.style.display = badge.includes(role) ? '' : 'none';
  });
}

export function toggleAll(prefix, master) {
  document.querySelectorAll(`.${prefix}-row-check`).forEach(cb => {
    cb.checked = master.checked;
    cb.closest('tr').classList.toggle('selected', master.checked);
  });
  rowCheck(prefix);
}

export function rowCheck(prefix) {
  const checked = document.querySelectorAll(`.${prefix}-row-check:checked`).length;
  const bar   = document.getElementById(`${prefix}-sel-bar`);
  const count = document.getElementById(`${prefix}-sel-count`);
  if (bar)   { bar.classList.toggle('visible', checked > 0); }
  if (count) count.textContent = `${checked} zaznaczonych`;
  document.querySelectorAll(`.${prefix}-row-check`).forEach(cb => {
    cb.closest('tr').classList.toggle('selected', cb.checked);
  });
}

// ── New account modal ──────────────────────────────────────────────────────────
export function openNewAccountModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="width:420px">
    <div class="modal-head"><span class="modal-title">Nowe konto</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body">
      <div class="form-row"><label class="form-label">Nazwa użytkownika *</label><input id="na-username" class="form-input form-mono" placeholder="min 3 znaki"></div>
      <div class="form-row" style="margin-top:8px"><label class="form-label">Hasło *</label><input id="na-pass" class="form-input" type="password" placeholder="min 8 znaków"></div>
      <div class="form-row" style="margin-top:8px"><label class="form-label">Wyświetlana nazwa</label><input id="na-display" class="form-input" placeholder="opcjonalnie"></div>
      <div class="form-row" style="margin-top:8px;align-items:center"><label><input type="checkbox" id="na-admin" style="margin-right:6px"> Administrator</label></div>
      <div style="display:flex;gap:8px;margin-top:16px">
        <button class="btn btn-primary" onclick="_doCreateAccount(this)">Utwórz konto</button>
        <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      </div>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector('#na-username').focus();
}

async function _doCreateAccount(btn) {
  const username     = document.getElementById('na-username')?.value?.trim();
  const password     = document.getElementById('na-pass')?.value;
  const display_name = document.getElementById('na-display')?.value?.trim() || null;
  const is_admin     = document.getElementById('na-admin')?.checked || false;
  if (!username || !password) { showToast('Wymagane: login i hasło.', 'error'); return; }
  btn.disabled = true; btn.textContent = '⏳';
  try {
    await apiFetch('/api/admin/accounts/create', { method:'POST', body: JSON.stringify({ username, password, display_name, is_admin }) });
    showToast('Konto utworzone.', 'success');
    btn.closest('.modal-overlay').remove();
    _loadPlayers();
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; btn.textContent = 'Utwórz konto'; }
}

// ── Players table ──────────────────────────────────────────────────────────────
async function _loadPlayers() {
  const tbody = document.querySelector('#players-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(8);
  try {
    const d = await apiFetch('/api/admin/accounts');
    const items = d.items || [];
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--t3)">Brak użytkowników</td></tr>`;
      return;
    }
    tbody.innerHTML = items.map(u => `<tr data-player-id="${u.id}">
      <td class="col-check"><input type="checkbox" class="player-row-check" onchange="rowCheck('player')"></td>
      <td class="td-sticky" data-sort-val="${_esc(u.username||'')}">
        <div style="display:flex;align-items:center;gap:8px">
          <div class="user-avatar" style="width:24px;height:24px;font-size:10px">${_esc((u.username||'?')[0].toUpperCase())}</div>
          <div><div class="td-name">${_esc(u.username)}</div><div class="td-muted">${_esc(u.display_name||'')}</div></div>
        </div>
      </td>
      <td>${u.is_admin ? '<span class="badge badge-red">Admin</span>' : '<span class="badge badge-blue">Gracz</span>'}${u.is_tester ? '<span class="badge badge-amber" style="margin-left:4px">Tester</span>' : ''}</td>
      <td class="td-muted" data-sort-val="${u.campaigns_count ?? 0}">${u.campaigns_count ?? 0} kampanii</td>
      <td class="td-mono" data-sort-val="0">—</td>
      <td class="td-muted" data-sort-val="${u.created_at || ''}">${_timeAgo(u.created_at) || '—'}</td>
      <td><span class="badge badge-slate" id="llm-badge-${u.id}">…</span></td>
      <td class="td-actions">
        <button class="btn-icon" title="Otwórz panel gracza" onclick="openPlayerDrawer(${u.id},'${_esc(u.username)}')">▶</button>
        ${!u.is_admin ? `<button class="btn-icon danger" title="Usuń" onclick="_deletePlayerRow(${u.id},'${_esc(u.username)}',this)">✕</button>` : ''}
      </td>
    </tr>`).join('');
    const pg = document.querySelector('#section-players .pagination span');
    if (pg) pg.textContent = `${items.length} użytkowników`;
    initSortableTable('players-table');
    // Lazy-load LLM mode badges
    items.forEach(u => _loadPlayerLlmBadge(u.id));
  } catch(e) { tbody.innerHTML = _errRow(8, e.message); }
}

async function _loadPlayerLlmBadge(userId) {
  try {
    const d = await apiFetch(`/api/admin/users/${userId}/llm-settings`);
    const s = d.settings || {};
    const badge = document.getElementById(`llm-badge-${userId}`);
    if (!badge) return;
    if (s.mode === 'custom') {
      badge.className = 'badge badge-amber';
      badge.textContent = `Custom · ${_esc(s.model || s.provider || '?')}`;
    } else {
      badge.className = 'badge badge-slate';
      badge.textContent = 'Domyślny';
    }
  } catch { /* non-critical */ }
}

// ── Bulk delete players ────────────────────────────────────────────────────────
export async function _bulkDeletePlayers(btn) {
  const checked = [...document.querySelectorAll('.player-row-check:checked')];
  if (!checked.length) { showToast('Nic nie zaznaczone.', 'warn'); return; }
  if (!confirm(`Usunąć ${checked.length} konto(-a)? Operacji nie da się cofnąć.`)) return;
  btn.disabled = true;
  let ok = 0, fail = 0;
  for (const cb of checked) {
    const row = cb.closest('tr');
    const userId = row?.dataset?.playerId;
    if (!userId) { fail++; continue; }
    try { await apiFetch(`/api/admin/accounts/${userId}`, { method:'DELETE' }); ok++; } catch { fail++; }
  }
  showToast(`Usunięto ${ok}${fail ? ' (błąd: ' + fail + ')' : ''}.`, fail ? 'warn' : 'success');
  btn.disabled = false;
  _loadPlayers();
}

export async function _deletePlayerRow(userId, username, btn) {
  if (!confirm(`Trwale usunąć konto „${username}" wraz z bohaterami i własnymi kampaniami? Tej operacji nie da się cofnąć.`)) return;
  btn.disabled = true;
  try {
    const r = await apiFetch(`/api/admin/accounts/${userId}`, { method:'DELETE' });
    showToast(`Konto „${username}" usunięte (bohaterów: ${r.characters_deleted ?? 0}, kampanii: ${r.campaigns_deleted ?? 0}).`, 'success');
    _loadPlayers();
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; }
}

// ── Player drawer ──────────────────────────────────────────────────────────────
export function _closePlayerDrawer() {
  document.querySelector('.pdrawer')?.classList.remove('open');
  document.querySelector('.pdrawer-backdrop')?.classList.remove('open');
  _pdrawerCurrentUser = null;
}

export async function openPlayerDrawer(userId, username) {
  _pdrawerCurrentUser = { id: userId, username };
  let backdrop = document.querySelector('.pdrawer-backdrop');
  let drawer   = document.querySelector('.pdrawer');
  if (!drawer) {
    backdrop = document.createElement('div');
    backdrop.className = 'pdrawer-backdrop';
    backdrop.onclick = _closePlayerDrawer;
    document.body.appendChild(backdrop);
    drawer = document.createElement('div');
    drawer.className = 'pdrawer';
    drawer.innerHTML = `
      <div class="pdrawer-head">
        <div><div class="pdrawer-title" id="pdrawer-title">…</div><div class="pdrawer-sub" id="pdrawer-sub"></div></div>
        <button class="btn-icon" onclick="_closePlayerDrawer()">✕</button>
      </div>
      <div class="pdrawer-tabs">
        <button class="pdrawer-tab active" data-pdtab="info">Info</button>
        <button class="pdrawer-tab" data-pdtab="camps">Kampanie</button>
        <button class="pdrawer-tab" data-pdtab="llm">LLM</button>
        <button class="pdrawer-tab" data-pdtab="modes">Tryby gry</button>
      </div>
      <div class="pdrawer-body">
        <div class="pdrawer-pane active" id="pdrawer-info"><div style="padding:20px;text-align:center;color:var(--t3)">Ładowanie…</div></div>
        <div class="pdrawer-pane" id="pdrawer-camps"></div>
        <div class="pdrawer-pane" id="pdrawer-llm"></div>
        <div class="pdrawer-pane" id="pdrawer-modes"></div>
      </div>
      <div class="pdrawer-foot">
        <button class="btn btn-secondary" onclick="_closePlayerDrawer()">Zamknij</button>
      </div>`;
    document.body.appendChild(drawer);
    drawer.querySelectorAll('.pdrawer-tab').forEach(t => t.addEventListener('click', () => _switchPdrawerTab(t.dataset.pdtab)));
  }
  document.getElementById('pdrawer-title').textContent = username;
  document.getElementById('pdrawer-sub').textContent   = `User ID: ${userId}`;
  document.getElementById('pdrawer-info').innerHTML    = '<div style="padding:20px;text-align:center;color:var(--t3)">Ładowanie…</div>';
  const campsPane  = document.getElementById('pdrawer-camps');
  const llmPane    = document.getElementById('pdrawer-llm');
  const modesPane  = document.getElementById('pdrawer-modes');
  campsPane.innerHTML = ''; campsPane.dataset.loaded = '';
  llmPane.innerHTML   = ''; llmPane.dataset.loaded   = '';
  if (modesPane) { modesPane.innerHTML = ''; modesPane.dataset.loaded = ''; }
  _switchPdrawerTab('info');
  backdrop.classList.add('open');
  drawer.classList.add('open');
  _loadPdrawerInfo(userId);
}

export function _switchPdrawerTab(tab) {
  document.querySelectorAll('.pdrawer-tab').forEach(b => b.classList.toggle('active', b.dataset.pdtab === tab));
  document.querySelectorAll('.pdrawer-pane').forEach(p => p.classList.toggle('active', p.id === `pdrawer-${tab}`));
  if (!_pdrawerCurrentUser) return;
  if (tab === 'camps'  && !document.getElementById('pdrawer-camps').dataset.loaded)  _loadPdrawerCamps(_pdrawerCurrentUser.id);
  if (tab === 'llm'    && !document.getElementById('pdrawer-llm').dataset.loaded)    _loadPdrawerLlm(_pdrawerCurrentUser.id);
  if (tab === 'modes'  && !document.getElementById('pdrawer-modes').dataset.loaded)  _loadPdrawerModes(_pdrawerCurrentUser.id);
}

// ── Drawer: Info tab ───────────────────────────────────────────────────────────
async function _loadPdrawerInfo(userId) {
  const pane = document.getElementById('pdrawer-info');
  try {
    const all = await apiFetch('/api/admin/accounts');
    const u   = (all.items || []).find(x => x.id === userId);
    if (!u) { pane.innerHTML = '<div style="padding:20px;color:var(--t3)">Nie znaleziono.</div>'; return; }
    const isActive = u.is_active !== 0 && u.is_active !== false;
    pane.innerHTML = `
      <div class="form-row"><label class="form-label">Login</label><input class="form-input" value="${_esc(u.username)}" readonly></div>
      <div class="form-row"><label class="form-label">Nazwa wyświetlana</label><input class="form-input" id="pd-display" value="${_esc(u.display_name||'')}"></div>
      <div class="form-row"><label style="display:flex;gap:8px;align-items:center;cursor:pointer"><input type="checkbox" id="pd-admin" ${u.is_admin ? 'checked' : ''}${u.id === 1 ? ' disabled' : ''}> Administrator</label></div>
      <div class="form-row"><label style="display:flex;gap:8px;align-items:center;cursor:pointer"><input type="checkbox" id="pd-active" ${isActive ? 'checked' : ''}${u.id === 1 ? ' disabled' : ''}> Konto aktywne</label></div>
      <div class="form-row"><label style="display:flex;gap:8px;align-items:center;cursor:pointer"><input type="checkbox" id="pd-tester" ${u.is_tester ? 'checked' : ''}> Tester (może zgłaszać błędy)</label></div>
      <div style="display:flex;gap:8px;margin-top:14px">
        <button class="btn btn-primary btn-sm" onclick="_savePdrawerInfo(${userId},this)">Zapisz</button>
      </div>
      <hr style="margin:18px 0;border:none;border-top:1px solid var(--border)">
      <div style="font-weight:600;margin-bottom:8px">Reset hasła</div>
      <div class="form-row"><label class="form-label">Nowe hasło</label><input class="form-input" id="pd-newpw" type="password" placeholder="Min. 8 znaków"></div>
      <div><button class="btn btn-secondary btn-sm" onclick="_resetPdrawerPassword(${userId},this)">Ustaw hasło</button></div>
      ${u.id !== 1 ? `<hr style="margin:18px 0;border:none;border-top:1px solid var(--border)">
      <div style="font-weight:600;margin-bottom:8px;color:var(--red)">Strefa niebezpieczna</div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-secondary btn-sm" onclick="_toggleBlockAccount(${userId},${isActive ? 1 : 0},this)">${isActive ? 'Zablokuj konto' : 'Odblokuj konto'}</button>
        <button class="btn btn-danger btn-sm" onclick="_deletePdrawerAccount(${userId},this)">Usuń konto</button>
      </div>` : ''}`;
  } catch(e) { pane.innerHTML = `<div style="padding:20px;color:#e55">${_esc(e.message)}</div>`; }
}

export async function _savePdrawerInfo(userId, btn) {
  btn.disabled = true; const orig = btn.textContent; btn.textContent = '⏳';
  try {
    const payload = {
      display_name: document.getElementById('pd-display').value.trim() || null,
      is_admin:     document.getElementById('pd-admin').checked  ? 1 : 0,
      is_active:    document.getElementById('pd-active').checked ? 1 : 0,
      is_tester:    document.getElementById('pd-tester').checked ? 1 : 0,
    };
    await apiFetch(`/api/admin/accounts/${userId}`, { method:'PATCH', body: JSON.stringify(payload) });
    showToast('Zapisano.', 'success');
    _loadPlayers();
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); }
  finally { btn.disabled = false; btn.textContent = orig; }
}

export async function _resetPdrawerPassword(userId, btn) {
  const pw = document.getElementById('pd-newpw').value;
  if (!pw || pw.length < 8) { showToast('Hasło musi mieć min. 8 znaków.', 'error'); return; }
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/accounts/${userId}/set-password`, { method:'POST', body: JSON.stringify({ new_password: pw }) });
    showToast('Hasło zaktualizowane.', 'success');
    document.getElementById('pd-newpw').value = '';
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); }
  finally { btn.disabled = false; }
}

export async function _toggleBlockAccount(userId, isActive, btn) {
  const next = isActive ? 0 : 1;
  if (!confirm(next ? 'Odblokować konto?' : 'Zablokować konto?')) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/accounts/${userId}`, { method:'PATCH', body: JSON.stringify({ is_active: next }) });
    showToast(next ? 'Konto odblokowane.' : 'Konto zablokowane.', 'success');
    _loadPdrawerInfo(userId);
    _loadPlayers();
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; }
}

export async function _deletePdrawerAccount(userId, btn) {
  if (!confirm('Trwale usunąć to konto wraz z bohaterami i własnymi kampaniami? Tej operacji nie da się cofnąć.')) return;
  btn.disabled = true;
  try {
    const r = await apiFetch(`/api/admin/accounts/${userId}`, { method:'DELETE' });
    showToast(`Konto usunięte (bohaterów: ${r.characters_deleted ?? 0}, kampanii: ${r.campaigns_deleted ?? 0}).`, 'success');
    _closePlayerDrawer();
    _loadPlayers();
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; }
}

// ── Drawer: Kampanie tab ───────────────────────────────────────────────────────
async function _loadPdrawerCamps(userId) {
  const pane = document.getElementById('pdrawer-camps');
  pane.innerHTML = '<div style="padding:20px;text-align:center;color:var(--t3)">Ładowanie…</div>';
  try {
    const [resUses, activity, resCfg] = await Promise.all([
      apiFetch(`/api/admin/users/${userId}/resurrection-uses`).catch(() => ({ uses_remaining: null })),
      apiFetch(`/api/admin/users/${userId}/activity`).catch(() => ({ items: [] })),
      apiFetch('/api/admin/resurrection-config').catch(() => null),
    ]);
    const camps           = activity.items || activity.campaigns || [];
    const usesRemaining   = resUses.uses_remaining;  // null = bez limitu (∞)
    const globalResEnabled = resCfg ? !!(resCfg.enabled) : true;
    const STATUS  = { active: 'Aktywna', ended: 'Zakończona', aborted: 'Przerwana' };
    const SBADGE  = { active: 'badge-green', ended: 'badge-slate', aborted: 'badge-red' };
    pane.innerHTML = `
      ${!globalResEnabled ? `<div style="padding:8px 12px;background:var(--amber-dim,#3a2d00);border:1px solid var(--amber,#f59e0b);border-radius:6px;margin-bottom:10px;font-size:0.78rem;color:var(--amber,#f59e0b)">&#9888; Wskrzeszenia są globalnie <strong>wyłączone</strong> (System → Wskrzeszenie). Ustawienie limitów nie zadziała, dopóki nie włączysz tej opcji.</div>` : ''}
      <div class="card" style="padding:12px;margin-bottom:12px">
        <div style="font-size:0.85rem;font-weight:600;margin-bottom:8px">✦ Wskrzeszenia tego gracza</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
          <input class="form-input" id="pd-uses" type="number" min="0" max="99" value="${usesRemaining ?? ''}" placeholder="∞ bez limitu" style="width:120px">
          <button class="btn btn-primary btn-sm" onclick="_saveResUses(${userId},false,this)">Zapisz</button>
          <button class="btn btn-secondary btn-sm" onclick="_saveResUses(${userId},true,this)">Bez limitu (∞)</button>
        </div>
        <div style="font-size:0.72rem;color:var(--t3);margin-top:6px">Pozostałe życia: <strong>${usesRemaining ?? '∞ (bez limitu)'}</strong></div>
      </div>
      ${camps.length === 0 ? '<div style="padding:20px;text-align:center;color:var(--t3)">Brak kampanii.</div>' :
        camps.map(c => {
          const hp    = c.char_current_hp, maxHp = c.char_max_hp;
          const pct   = (hp != null && maxHp) ? Math.round((hp / maxHp) * 100) : null;
          const tone  = pct === null ? '' : (pct < 30 ? 'red' : pct < 60 ? 'amber' : 'green');
          const lastT = c.last_turn_at ? new Date(c.last_turn_at).toLocaleDateString('pl-PL') : '—';
          const isDead = c.char_status === 'dead' || (c.char_current_hp != null && c.char_current_hp <= 0);
          return `
          <div class="card" style="padding:10px;margin-bottom:8px">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
              <div style="font-weight:600">${_esc(c.title || 'Kampania ' + (c.id || ''))}</div>
              <span class="badge ${SBADGE[c.status] || 'badge-slate'}">${STATUS[c.status] || _esc(c.status || '')}</span>
            </div>
            ${c.char_name ? `<div style="font-size:0.75rem;color:var(--t2);margin-top:4px">${_esc(c.char_name)}${c.char_archetype ? ' · ' + _esc(c.char_archetype) : ''}</div>` : ''}
            ${pct !== null ? `<div class="hp-bar" style="margin-top:6px"><div class="hp-fill ${tone}" style="width:${pct}%"></div></div><div style="font-size:0.7rem;color:var(--t3);margin-top:2px">${hp}/${maxHp} HP</div>` : ''}
            <div style="font-size:0.72rem;color:var(--t3);margin-top:4px">Tury: ${c.turn_count ?? '—'} · Ostatnia: ${lastT}</div>
            ${(isDead && c.char_id) ? `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border)">
              <span class="badge badge-red">&#x1F480; Bohater martwy</span>
              <button class="btn btn-primary btn-sm" style="margin-top:6px;width:100%" onclick="_resurrectChar(${c.char_id},'${_esc(c.char_name || 'Bohater')}',${userId},this)">✦ Wskrześ bohatera (force)</button>
            </div>` : ''}
          </div>`;
        }).join('')}`;
    pane.dataset.loaded = '1';
  } catch(e) { pane.innerHTML = `<div style="padding:20px;color:var(--red)">${_esc(e.message)}</div>`; }
}

export async function _saveResUses(userId, clear, btn) {
  let payload;
  if (clear) { payload = { clear: true }; }
  else {
    const raw = (document.getElementById('pd-uses').value || '').trim();
    if (raw === '') { payload = { clear: true }; }
    else {
      const n = parseInt(raw, 10);
      if (isNaN(n) || n < 0) { showToast('Podaj liczbę ≥ 0.', 'error'); return; }
      payload = { uses_remaining: n };
    }
  }
  btn.disabled = true;
  try {
    const res = await apiFetch(`/api/admin/users/${userId}/resurrection-uses`, { method:'PATCH', body: JSON.stringify(payload) });
    showToast(`Wskrzeszenia: ${res.uses_remaining ?? 'bez limitu'}.`, 'success');
    document.getElementById('pdrawer-camps').dataset.loaded = '';
    _loadPdrawerCamps(userId);
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; }
}

export async function _resurrectChar(charId, name, userId, btn) {
  if (!confirm(`Wskrzesić bohatera „${name}" bezpłatnie (admin force)?`)) return;
  btn.disabled = true; btn.textContent = 'Wskrzeszam…';
  try {
    const res = await apiFetch(`/api/admin/characters/${charId}/resurrect`, { method:'POST', body: JSON.stringify({ force: true }) });
    showToast(`✦ ${name} wskrzeszony — HP ${res.revived_hp ?? '?'}/${res.max_hp ?? '?'}`, 'success');
    document.getElementById('pdrawer-camps').dataset.loaded = '';
    _loadPdrawerCamps(userId);
  } catch(e) { showToast(e.message || 'Błąd wskrzeszenia.', 'error'); btn.disabled = false; btn.textContent = '✦ Wskrześ bohatera (force)'; }
}

// ── Drawer: Tryby gry tab ──────────────────────────────────────────────────────
export async function _loadPdrawerModes(userId) {
  const pane = document.getElementById('pdrawer-modes');
  pane.innerHTML = '<div style="padding:20px;text-align:center;color:var(--t3)">Ładowanie…</div>';
  try {
    const d = await apiFetch(`/api/admin/users/${userId}/game-modes`);
    const { global_flags = {}, overrides = {}, effective = {} } = d;
    pane.innerHTML = `
      <div style="padding:12px">
        <p style="font-size:0.78rem;color:var(--t3);margin:0 0 12px">
          Puste = brak nadpisania (używa globalnego ustawienia). Zaznacz lub odznacz, aby wymusić wartość dla tego gracza.
        </p>
        <div style="display:flex;flex-direction:column;gap:14px" id="pdrawer-modes-checks">
          ${Object.entries(_MODE_LABELS).map(([key, {label, desc}]) => {
            const isOverridden = key in overrides;
            const val = effective[key] !== false;
            return `
            <div style="display:flex;align-items:flex-start;gap:10px">
              <input type="checkbox" data-modekey="${key}" ${val ? 'checked' : ''} ${isOverridden ? 'data-overridden="1"' : ''}
                style="width:17px;height:17px;margin-top:2px;accent-color:var(--accent);flex-shrink:0">
              <span>
                <strong style="font-size:0.88rem">${label}</strong>
                ${isOverridden
                  ? '<span style="font-size:0.7rem;color:var(--accent);margin-left:6px">nadpisano</span>'
                  : '<span style="font-size:0.7rem;color:var(--t3);margin-left:6px">globalne: ' + (global_flags[key] !== false ? '✓' : '✗') + '</span>'}
                <span style="display:block;font-size:0.75rem;color:var(--t3)">${desc}</span>
              </span>
            </div>`;
          }).join('')}
        </div>
        <div style="display:flex;gap:8px;margin-top:16px">
          <button class="btn btn-primary btn-sm" onclick="_savePdrawerModes(${userId},this)">Zapisz nadpisania</button>
          <button class="btn btn-secondary btn-sm" onclick="_clearPdrawerModes(${userId},this)">Wyczyść (wróć do globalnych)</button>
        </div>
      </div>`;
    pane.dataset.loaded = '1';
  } catch(e) { pane.innerHTML = `<div style="padding:20px;color:var(--red)">${_esc(e.message)}</div>`; }
}

export async function _savePdrawerModes(userId, btn) {
  btn.disabled = true;
  const checks  = document.querySelectorAll('#pdrawer-modes-checks input[type=checkbox]');
  const payload = {};
  checks.forEach(cb => { payload[cb.dataset.modekey] = cb.checked; });
  try {
    await apiFetch(`/api/admin/users/${userId}/game-modes`, { method:'PATCH', body: JSON.stringify(payload) });
    showToast('Tryby gracza zapisane.', 'success');
    document.getElementById('pdrawer-modes').dataset.loaded = '';
    _loadPdrawerModes(userId);
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; }
}

export async function _clearPdrawerModes(userId, btn) {
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/users/${userId}/game-modes`, { method:'DELETE' });
    showToast('Nadpisania wyczyszczone.', 'success');
    document.getElementById('pdrawer-modes').dataset.loaded = '';
    _loadPdrawerModes(userId);
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; }
}

// ── Drawer: LLM tab ────────────────────────────────────────────────────────────
export async function _loadPdrawerLlm(userId) {
  const pane = document.getElementById('pdrawer-llm');
  pane.innerHTML = '<div style="padding:20px;text-align:center;color:var(--t3)">Ładowanie…</div>';
  try {
    const d  = await apiFetch(`/api/admin/users/${userId}/llm-settings`);
    const s  = d.settings || {};
    const isCustom = s.mode === 'custom';
    pane.innerHTML = `
      <div class="form-row" style="margin-bottom:12px">
        <label style="display:flex;gap:8px;align-items:center;cursor:pointer">
          <input type="checkbox" id="pdllm-custom" ${isCustom ? 'checked' : ''} onchange="document.getElementById('pdllm-fields').style.display=this.checked?'':'none'">
          Własna konfiguracja LLM
        </label>
      </div>
      <div id="pdllm-fields" style="display:${isCustom ? 'block' : 'none'}">
        <div class="form-row"><label class="form-label">Dostawca</label>
          <select id="pdllm-provider" class="form-input">
            <option value="openai" ${s.provider === 'openai' ? 'selected' : ''}>OpenAI</option>
            <option value="ollama" ${s.provider === 'ollama' ? 'selected' : ''}>Ollama</option>
            <option value="other"  ${s.provider && !['openai','ollama'].includes(s.provider) ? 'selected' : ''}>Inny</option>
          </select>
        </div>
        <div class="form-row"><label class="form-label">Base URL</label><input class="form-input" id="pdllm-url"   value="${_esc(s.base_url||'')}" placeholder="https://api.openai.com"></div>
        <div class="form-row"><label class="form-label">Model</label>    <input class="form-input" id="pdllm-model" value="${_esc(s.model||'')}"    placeholder="gpt-4.1"></div>
        <div class="form-row"><label class="form-label">API Key ${s.api_key_set ? '<em style="color:var(--t3)">(ustawiony)</em>' : ''}</label>
          <input class="form-input" id="pdllm-key" type="password" placeholder="Zostaw puste, by nie zmieniać">
        </div>
      </div>
      <button class="btn btn-primary btn-sm" onclick="_savePdrawerLlm(${userId},this)">Zapisz LLM</button>`;
    pane.dataset.loaded = '1';
  } catch(e) { pane.innerHTML = `<div style="padding:20px;color:#e55">${_esc(e.message)}</div>`; }
}

export async function _savePdrawerLlm(userId, btn) {
  const isCustom = document.getElementById('pdllm-custom')?.checked;
  const payload  = { mode: isCustom ? 'custom' : 'default' };
  if (isCustom) {
    payload.provider = document.getElementById('pdllm-provider')?.value || 'openai';
    payload.base_url = document.getElementById('pdllm-url')?.value?.trim()   || '';
    payload.model    = document.getElementById('pdllm-model')?.value?.trim() || '';
    const key = document.getElementById('pdllm-key')?.value;
    if (key) payload.api_key = key;
  }
  btn.disabled = true; const orig = btn.textContent; btn.textContent = '⏳';
  try {
    await apiFetch(`/api/admin/users/${userId}/llm-settings`, { method:'PUT', body: JSON.stringify(payload) });
    _loadPlayerLlmBadge(userId);
    showToast('Ustawienia LLM zapisane.', 'success');
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); }
  finally { btn.disabled = false; btn.textContent = orig; }
}

// ── Module entry point ─────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = `<div id="section-players">
    <div class="section-header">
      <div>
        <div class="section-heading">Gracze</div>
        <div class="section-sub">Zarządzanie kontami i uprawnieniami</div>
      </div>
      <button class="btn btn-primary btn-sm" onclick="openNewAccountModal()">+ Nowe konto</button>
    </div>

    <div class="card">
      <div class="toolbar">
        <div class="search-box">
          <span class="search-box-icon">&#x1F50D;</span>
          <input type="text" placeholder="Szukaj gracza…" oninput="filterTableGeneric(this,'players-table','td-name')">
        </div>
        <div class="filter-group">
          <button class="chip on"  onclick="filterPlayers(this,'')">Wszyscy</button>
          <button class="chip"     onclick="filterPlayers(this,'admin')">Adminowie</button>
          <button class="chip"     onclick="filterPlayers(this,'gracz')">Gracze</button>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table" id="players-table">
          <thead>
            <tr>
              <th class="col-check"><input type="checkbox" onchange="toggleAll('player', this)"></th>
              <th class="td-sticky"><div class="th-inner sorted">Użytkownik <span class="sort-icon asc">&#x25B2;</span></div></th>
              <th><div class="th-inner">Rola</div></th>
              <th><div class="th-inner">Kampanie</div></th>
              <th><div class="th-inner">Tury <span class="sort-icon">&#x25B2;</span></div></th>
              <th><div class="th-inner">Ostatnia aktywność <span class="sort-icon">&#x25B2;</span></div></th>
              <th><div class="th-inner">Model LLM</div></th>
              <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
      <div class="selection-bar" id="player-sel-bar" style="border-top:1px solid var(--blue-border);border-bottom:none">
        <span class="sel-count" id="player-sel-count">0 zaznaczonych</span>
        <button class="btn btn-sm btn-secondary">Zmień rolę</button>
        <button class="btn btn-sm btn-danger" onclick="_bulkDeletePlayers(this)">Usuń konta</button>
      </div>
      <div class="pagination">
        <span>0 użytkowników</span>
      </div>
    </div>
  </div>`;

  _loadPlayers();
}

// ── Global onclick surface ─────────────────────────────────────────────────────
Object.assign(window, {
  openNewAccountModal,
  _doCreateAccount,
  filterPlayers,
  filterTableGeneric,
  toggleAll,
  rowCheck,
  _bulkDeletePlayers,
  openPlayerDrawer,
  _closePlayerDrawer,
  _switchPdrawerTab,
  _savePdrawerInfo,
  _resetPdrawerPassword,
  _toggleBlockAccount,
  _deletePdrawerAccount,
  _deletePlayerRow,
  _saveResUses,
  _resurrectChar,
  _loadPdrawerModes,
  _savePdrawerModes,
  _clearPdrawerModes,
  _savePdrawerLlm,
});
