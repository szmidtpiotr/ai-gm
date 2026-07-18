/**
 * FADM-P2 (#404) — sekcja Mechanika: staty, umiejętności, DC, kondycje, archetypy.
 * Port 1:1 z admin_panel_v3/index.html. Backend BEZ zmian.
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function _loading(cols) {
  return `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr>`;
}
function _errRow(cols, msg) {
  return `<tr><td colspan="${cols}" style="text-align:center;padding:24px;color:var(--red);font-size:0.8rem">Błąd: ${_esc(msg)}</td></tr>`;
}

const _mechLoaded = new Set();

// ── Encounter config ──────────────────────────────────────────────────────────

// BL-A7 (#1423) — presety trudności (label → mnożnik), zsynchronizowane z backendem.
const _ENC_DIFFICULTY_PRESETS = { latwy: 0.75, normalny: 1.0, trudny: 1.35, hardcore: 1.75 };

function _syncEncPresetButtons(root, mult) {
  const m = Number(mult);
  root.querySelectorAll('.enc-preset-btn').forEach(b => {
    const active = Math.abs(Number(b.dataset.mult) - m) < 0.001;
    b.classList.toggle('btn-primary', active);
    b.classList.toggle('btn-ghost', !active);
  });
}

async function _loadEncounterConfig(root) {
  try {
    const c = await apiFetch('/api/admin/world/encounter-config');
    const set = (id, v) => { const el = root.querySelector(id); if (el && v != null) el.value = v; };
    set('#enc-cfg-interval', c.n_turns_interval ?? 20);
    set('#enc-cfg-dwell', c.dwell_settle_turns ?? 3);
    set('#enc-cfg-difficulty', c.difficulty_mult ?? 1.0);
    set('#enc-cfg-budget-base', c.threat_budget_base ?? 30);
    set('#enc-cfg-budget-power', c.threat_budget_per_power ?? 25);
    set('#enc-cfg-pool-min', c.pool_min_size ?? 6);
    set('#enc-cfg-repeat', c.repeat_penalty ?? 0.25);
    _syncEncPresetButtons(root, c.difficulty_mult ?? 1.0);
  } catch (_) { /* ignore */ }
}

async function _saveEncounterConfig(root) {
  const st = root.querySelector('#enc-cfg-status');
  const numOr = (id, d) => { const v = parseFloat(root.querySelector(id)?.value); return Number.isFinite(v) ? v : d; };
  const body = {
    n_turns_interval: parseInt(root.querySelector('#enc-cfg-interval')?.value) || 20,
    dwell_settle_turns: parseInt(root.querySelector('#enc-cfg-dwell')?.value) || 3,
    difficulty_mult: numOr('#enc-cfg-difficulty', 1.0),
    threat_budget_base: numOr('#enc-cfg-budget-base', 30),
    threat_budget_per_power: numOr('#enc-cfg-budget-power', 25),
    pool_min_size: parseInt(root.querySelector('#enc-cfg-pool-min')?.value) || 6,
    repeat_penalty: numOr('#enc-cfg-repeat', 0.25),
  };
  try {
    const r = await apiFetch('/api/admin/world/encounter-config', { method: 'POST', body: JSON.stringify(body) });
    _syncEncPresetButtons(root, r.difficulty_mult ?? 1.0);
    if (st) { st.textContent = `✓ zapisano (trudność ×${r.difficulty_mult})`; st.style.color = 'var(--green)'; }
  } catch (e) {
    if (st) { st.textContent = '✕ ' + (e.message || 'błąd'); st.style.color = 'var(--red)'; }
  }
}

function _applyEncPreset(root, mult) {
  const el = root.querySelector('#enc-cfg-difficulty');
  if (el) el.value = mult;
  _syncEncPresetButtons(root, mult);
  _saveEncounterConfig(root);
}

async function _runEncounterPreview(root) {
  const box = root.querySelector('#enc-preview-out');
  if (!box) return;
  const level = parseInt(root.querySelector('#enc-preview-level')?.value) || 1;
  const hexType = (root.querySelector('#enc-preview-terrain')?.value || '').trim() || null;
  box.innerHTML = '<div style="color:var(--t3);font-size:.78rem;padding:6px">Losuję…</div>';
  try {
    const r = await apiFetch('/api/admin/world/encounter-preview', {
      method: 'POST', body: JSON.stringify({ level, hex_type: hexType, samples: 3 }),
    });
    if (r.empty_pool) {
      box.innerHTML = `<div style="color:var(--red);font-size:.78rem;padding:6px">Pusta pula wrogów dla poz. ${level}${hexType ? ' / ' + _esc(hexType) : ''}.</div>`;
      return;
    }
    const head = `<div style="font-size:.72rem;color:var(--t3);margin-bottom:4px">Budżet f(poz. ${level}) = ${r.threat_budget} · trudność ×${r.difficulty_mult}</div>`;
    box.innerHTML = head + (r.samples || []).map(s => {
      const enemies = (s.enemies || []).map(e =>
        `${e.count > 1 ? e.count + '× ' : ''}${_esc(e.name || e.enemy_key)}${e.rank ? ' <span style="color:var(--amber)">[' + _esc(e.rank) + ']</span>' : ''}`
      ).join(', ');
      return `<div style="padding:5px 7px;border:1px solid var(--border);border-radius:6px;margin-bottom:4px;font-size:.8rem">
        <span class="badge" style="font-size:.66rem">${_esc(s.pattern || '?')}</span>
        ${enemies} <span style="color:var(--t3);font-size:.7rem">(zagr. ${s.threat_spent}/${s.threat_budget})</span></div>`;
    }).join('');
  } catch (e) {
    box.innerHTML = `<div style="color:var(--red);font-size:.78rem;padding:6px">Błąd: ${_esc(e.message || 'błąd')}</div>`;
  }
}

// ── Stats ─────────────────────────────────────────────────────────────────────

function _startEdit(td) {
  if (td.querySelector('input')) return;
  const original = td.textContent.trim();
  const input = document.createElement('input');
  input.className = 'cell-input';
  input.value = original;
  td.textContent = '';
  td.appendChild(input);
  input.focus();
  input.select();
  function save() {
    const val = input.value.trim() || original;
    td.textContent = val;
    td.classList.add('editable');
    td.addEventListener('click', () => _startEdit(td));
  }
  input.addEventListener('blur', save);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); save(); }
    if (e.key === 'Escape') { td.textContent = original; td.classList.add('editable'); td.addEventListener('click', () => _startEdit(td)); }
  });
}

async function _loadStats(root) {
  const tbody = root.querySelector('#stats-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(4);
  try {
    const d = await apiFetch('/api/admin/stats');
    const items = d.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--t3)">Brak statystyk</td></tr>`; return; }
    tbody.innerHTML = items.map(s => `<tr>
      <td class="td-mono" data-label="Klucz">${_esc(s.key)}</td>
      <td class="td-name editable" data-label="Nazwa" data-key="${_esc(s.key)}" data-field="label" data-patch="/api/admin/stats/${_esc(s.key)}">${_esc(s.label||s.key)}</td>
      <td class="td-muted editable" data-label="Opis" data-key="${_esc(s.key)}" data-field="description" data-patch="/api/admin/stats/${_esc(s.key)}">${_esc((s.description||'').slice(0,80)||'—')}</td>
      <td data-label="Zablokowany">${s.locked_at ? `<span class="badge badge-amber" title="${_esc(s.locked_at)}">🔒</span>` : '<span class="td-muted">—</span>'}</td>
    </tr>`).join('');
    root.querySelectorAll('#stats-table .editable').forEach(td => td.addEventListener('click', () => _startEdit(td)));
  } catch(e) { tbody.innerHTML = _errRow(4, e.message); }
}

// ── Skills ────────────────────────────────────────────────────────────────────

async function _loadSkills(root) {
  const tbody = root.querySelector('#skills-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(7);
  try {
    const [sd, sk] = await Promise.all([apiFetch('/api/admin/stats'), apiFetch('/api/admin/skills')]);
    root._statsCache = sd.items || [];
    const items = sk.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--t3)">Brak umiejętności</td></tr>`; return; }
    tbody.innerHTML = items.map(s => `<tr>
      <td class="td-mono" data-label="Klucz">${_esc(s.key)}</td>
      <td class="td-name" data-label="Nazwa">${_esc(s.label||s.key)}</td>
      <td data-label="Statystyka"><span class="badge badge-blue">${_esc(s.linked_stat||'—')}</span></td>
      <td class="td-mono" data-label="Maks. rang">${s.rank_ceiling??'—'}${Object.keys(_parseRankCost(s.rank_cost_json)).length ? ` <span class="badge badge-amber" title="Własny koszt XP za rangę">💰</span>` : ''}</td>
      <td class="td-muted" data-label="Słowa klucz." style="font-size:0.72rem;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${_esc(s.trigger_keywords||'')}">${_esc(s.trigger_keywords||'—')}</td>
      <td class="td-muted" data-label="Opis">${_esc((s.description||'').slice(0,60)||'—')}</td>
      <td data-label="Zablokowany">${s.locked_at ? `<span class="badge badge-amber">🔒</span>` : '<span class="td-muted">—</span>'}</td>
      <td class="td-actions">
        <button class="btn-icon" title="Edytuj" data-edit-skill="${_esc(s.key)}">✎</button>
        <button class="btn-icon danger" title="Usuń" data-delete-skill="${_esc(s.key)}" data-locked="${s.locked_at ? '1' : ''}">✕</button>
      </td>
    </tr>`).join('');
    root.querySelectorAll('[data-edit-skill]').forEach(btn =>
      btn.addEventListener('click', () => _openEditSkillModal(root, btn.dataset.editSkill)));
    root.querySelectorAll('[data-delete-skill]').forEach(btn =>
      btn.addEventListener('click', () => _deleteSkill(root, btn.dataset.deleteSkill, btn, !!btn.dataset.locked)));
  } catch(e) { tbody.innerHTML = _errRow(8, e.message); }
}

// ── DC ────────────────────────────────────────────────────────────────────────

async function _mechPatchEdit(cell, patchUrl, field) {
  const orig = cell.textContent.trim();
  const input = document.createElement('input');
  input.className = 'inline-input';
  input.value = orig === '—' ? '' : orig;
  cell.textContent = '';
  cell.appendChild(input);
  input.focus();
  const save = async () => {
    const val = input.value.trim();
    if (val === orig || (val === '' && orig === '—')) { cell.textContent = orig; return; }
    try {
      await apiFetch(patchUrl, { method: 'PATCH', body: JSON.stringify({ [field]: val || null }) });
      cell.textContent = val || '—';
      showToast('Zapisano.', 'success');
    } catch(e) { cell.textContent = orig; showToast('Błąd: ' + e.message, 'error'); }
  };
  input.addEventListener('blur', save);
  input.addEventListener('keydown', e => {
    if(e.key==='Enter'){e.preventDefault();save();}
    if(e.key==='Escape'){cell.textContent=orig;}
  });
}

async function _loadDC(root) {
  const tbody = root.querySelector('#dc-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(5);
  try {
    const d = await apiFetch('/api/admin/dc');
    const items = d.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--t3)">Brak poziomów DC</td></tr>`; return; }
    tbody.innerHTML = items.map(dc => `<tr>
      <td class="td-mono" data-label="Klucz">${_esc(dc.key)}</td>
      <td class="td-name" data-label="Nazwa">${_esc(dc.label||dc.key)}</td>
      <td class="td-mono editable" data-label="Wartość" data-patch="/api/admin/dc/${_esc(dc.key)}" data-field="value">${dc.value??'—'}</td>
      <td class="td-muted" data-label="Opis">${_esc((dc.description||'').slice(0,80)||'—')}</td>
      <td data-label="Zablokowany">${dc.locked_at ? `<span class="badge badge-amber">🔒</span>` : '<span class="td-muted">—</span>'}</td>
    </tr>`).join('');
    root.querySelectorAll('#dc-table .editable[data-patch]').forEach(td =>
      td.addEventListener('click', () => _mechPatchEdit(td, td.dataset.patch, td.dataset.field)));
  } catch(e) { tbody.innerHTML = _errRow(5, e.message); }
}

// ── Conditions ────────────────────────────────────────────────────────────────

async function _loadConditions(root) {
  const tbody = root.querySelector('#conditions-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(7);
  try {
    const d = await apiFetch('/api/admin/conditions');
    const items = d.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--t3)">Brak kondycji</td></tr>`; return; }
    tbody.innerHTML = items.map(c => `<tr>
      <td class="td-mono" data-label="Klucz">${_esc(c.key)}</td>
      <td class="td-name" data-label="Nazwa">${_esc(c.label||c.key)}</td>
      <td class="td-mono" data-label="Efekt JSON" style="font-size:0.72rem;max-width:160px;overflow:hidden;text-overflow:ellipsis">${c.effect_json ? _esc(typeof c.effect_json==='string'?c.effect_json:JSON.stringify(c.effect_json)) : '—'}</td>
      <td data-label="Kumulowalny" style="text-align:center">${c.stackable ? '✓' : '—'}</td>
      <td data-label="Aktywny" style="text-align:center">${c.is_active ? '<span class="badge badge-green">●</span>' : '<span class="badge badge-slate">○</span>'}</td>
      <td data-label="Zablokowany">${c.locked_at ? `<span class="badge badge-amber">🔒</span>` : '<span class="td-muted">—</span>'}</td>
      <td class="td-actions">
        <button class="btn-icon" title="Edytuj" data-edit-cond="${_esc(c.key)}">✎</button>
        ${!c.locked_at ? `<button class="btn-icon danger" title="Usuń" data-delete-cond="${_esc(c.key)}">✕</button>` : ''}
      </td>
    </tr>`).join('');
    root.querySelectorAll('[data-edit-cond]').forEach(btn =>
      btn.addEventListener('click', () => _openEditConditionModal(root, btn.dataset.editCond)));
    root.querySelectorAll('[data-delete-cond]').forEach(btn =>
      btn.addEventListener('click', () => _deleteCondition(root, btn.dataset.deleteCond, btn)));
  } catch(e) { tbody.innerHTML = _errRow(7, e.message); }
}

// ── Archetypes ────────────────────────────────────────────────────────────────

async function _loadArchetypes(root) {
  const tbody = root.querySelector('#archetypes-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(6);
  try {
    const d = await apiFetch('/api/admin/archetypes');
    const items = d.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--t3)">Brak archetypów</td></tr>`; return; }
    tbody.innerHTML = items.map(a => `<tr>
      <td class="td-mono" data-label="Klucz">${_esc(a.key)}</td>
      <td class="td-name" data-label="Nazwa">${_esc(a.label||a.key)}</td>
      <td class="td-mono editable" data-label="HP bazowe" data-patch="/api/admin/archetypes/${_esc(a.key)}" data-field="hp_base">${a.hp_base??'—'}</td>
      <td class="td-mono editable" data-label="Złoto start." data-patch="/api/admin/archetypes/${_esc(a.key)}" data-field="starter_gold_gp">${a.starter_gold_gp??'—'}</td>
      <td class="td-muted" data-label="Opis">${_esc((a.description||'').slice(0,60)||'—')}</td>
      <td data-label="Zablokowany">${a.locked_at ? `<span class="badge badge-amber">🔒</span>` : '<span class="td-muted">—</span>'}</td>
    </tr>`).join('');
    root.querySelectorAll('#archetypes-table .editable[data-patch]').forEach(td =>
      td.addEventListener('click', () => _mechPatchEdit(td, td.dataset.patch, td.dataset.field)));
  } catch(e) { tbody.innerHTML = _errRow(6, e.message); }
}

// ── XP Awards ─────────────────────────────────────────────────────────────────

async function _loadXpAwards(root) {
  const tbody = root.querySelector('#xp-awards-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(6);
  try {
    const d = await apiFetch('/api/admin/xp-awards');
    const items = d.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--t3)">Brak wpisów XP</td></tr>`; return; }
    tbody.innerHTML = items.map(a => `<tr data-award-id="${a.id}">
      <td class="td-mono" data-label="Klucz">${_esc(a.source_key||a.id)}</td>
      <td class="td-muted" data-label="Kategoria">${_esc(a.category||'—')}</td>
      <td class="td-name" data-label="Nazwa">${_esc(a.label||'—')}</td>
      <td class="td-mono editable" data-label="XP" data-patch="/api/admin/xp-awards/${a.id}" data-field="xp_amount" style="text-align:right">${a.xp_amount??'—'}</td>
      <td class="td-muted" data-label="Opis">${_esc((a.description||'').slice(0,80)||'—')}</td>
      <td class="xp-active-toggle" data-label="Aktywny" data-award-id="${a.id}" data-active="${a.is_active?1:0}" style="cursor:pointer;text-align:center">${a.is_active ? '<span class="badge badge-green">Tak</span>' : '<span class="badge badge-gray">Nie</span>'}</td>
    </tr>`).join('');
    root.querySelectorAll('#xp-awards-table .editable[data-patch]').forEach(td =>
      td.addEventListener('click', () => _mechPatchEdit(td, td.dataset.patch, td.dataset.field)));
    root.querySelectorAll('#xp-awards-table .xp-active-toggle').forEach(td => {
      td.addEventListener('click', async () => {
        const newVal = td.dataset.active === '1' ? 0 : 1;
        try {
          await apiFetch(`/api/admin/xp-awards/${td.dataset.awardId}`, { method:'PATCH', body: JSON.stringify({is_active: newVal}) });
          td.dataset.active = String(newVal);
          td.innerHTML = newVal ? '<span class="badge badge-green">Tak</span>' : '<span class="badge badge-gray">Nie</span>';
        } catch(e) { showToast('Błąd: ' + e.message, 'error'); }
      });
    });
  } catch(e) { tbody.innerHTML = _errRow(6, e.message); }
}

// ── Tab loader ────────────────────────────────────────────────────────────────

function _loadTab(root, tab) {
  if (_mechLoaded.has(tab)) return Promise.resolve();
  const fn = { stats:_loadStats, skills:_loadSkills, dc:_loadDC, conditions:_loadConditions, archetypes:_loadArchetypes, xp:_loadXpAwards }[tab];
  if (!fn) return Promise.resolve();
  _mechLoaded.add(tab);
  return fn(root).catch(err => { _mechLoaded.delete(tab); console.warn('Mech tab failed:', tab, err.message); });
}

// ── Skill modal ───────────────────────────────────────────────────────────────

function _openAddSkillModal(root) {
  const stats = root._statsCache || [];
  _openSkillForm(root, null, stats, async data => {
    try {
      await apiFetch('/api/admin/skills', { method:'POST', body:JSON.stringify(data) });
      _mechLoaded.delete('skills');
      _loadSkills(root);
      showToast('Dodano umiejętność.', 'success');
    } catch(e) { showToast('Błąd: '+e.message, 'error'); }
  });
}

async function _openEditSkillModal(root, key) {
  const stats = root._statsCache || (await apiFetch('/api/admin/stats').then(d => d.items||[]));
  const all = await apiFetch('/api/admin/skills').then(d => d.items||[]);
  const row = all.find(s => s.key === key);
  if (!row) return;
  _openSkillForm(root, row, stats, async data => {
    try {
      await apiFetch(`/api/admin/skills/${key}`, { method:'PATCH', body:JSON.stringify(data) });
      _mechLoaded.delete('skills');
      _loadSkills(root);
      showToast('Zapisano.', 'success');
    } catch(e) { showToast('Błąd: '+e.message, 'error'); }
  });
}

// #1382 — parse rank_cost_json (string from DB or already-parsed object) → {rank:cost}.
function _parseRankCost(raw) {
  if (!raw) return {};
  let obj = raw;
  if (typeof raw === 'string') {
    const s = raw.trim();
    if (!s) return {};
    try { obj = JSON.parse(s); } catch { return {}; }
  }
  if (typeof obj !== 'object' || Array.isArray(obj)) return {};
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    const rank = parseInt(k, 10), cost = parseInt(v, 10);
    if (rank >= 1 && cost > 0) out[rank] = cost;
  }
  return out;
}

// #1382 — one small numeric input per rank 1..ceiling; empty = inherit global cost.
function _rankCostInputs(p) {
  const ceiling = Math.max(1, parseInt(p.rank_ceiling, 10) || 5);
  const existing = _parseRankCost(p.rank_cost_json);
  let html = '';
  for (let r = 1; r <= ceiling; r++) {
    const val = existing[r] != null ? existing[r] : '';
    html += `<div style="display:flex;flex-direction:column;align-items:center">
      <span style="font-size:0.7rem;color:var(--muted,#888)">rang ${r}</span>
      <input class="form-input skill-rank-cost" data-rank="${r}" type="number" min="1"
             value="${val}" placeholder="dom." style="width:64px;text-align:center">
    </div>`;
  }
  return html;
}

function _openSkillForm(root, prefill, stats, onSubmit) {
  const p = prefill || {};
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="max-width:440px">
    <div class="modal-head"><span class="modal-title">${p.key ? 'Edytuj umiejętność' : 'Nowa umiejętność'}</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body">
      <div class="form-row"><label class="form-label">Klucz *</label><input class="form-input" name="key" value="${_esc(p.key||'')}" placeholder="np. acrobatics" ${p.key?'readonly':''}></div>
      <div class="form-row"><label class="form-label">Nazwa *</label><input class="form-input" name="label" value="${_esc(p.label||'')}" placeholder="Akrobatyka"></div>
      <div class="form-row"><label class="form-label">Statystyka *</label><select class="form-input" name="linked_stat">${stats.map(s=>`<option value="${_esc(s.key)}" ${p.linked_stat===s.key?'selected':''}>${_esc(s.label||s.key)}</option>`).join('')}</select></div>
      <div class="form-row"><label class="form-label">Maks. rang</label><input class="form-input" name="rank_ceiling" type="number" value="${p.rank_ceiling??5}" min="1"></div>
      <div class="form-row"><label class="form-label">Opis</label><textarea class="form-input" name="description" rows="2">${_esc(p.description||'')}</textarea></div>
      <div class="form-row"><label class="form-label">Trigger keywords</label><input class="form-input" name="trigger_keywords" value="${_esc(p.trigger_keywords||'')}" placeholder="miecz,broń — oddzielone przecinkami"></div>
      <div class="form-row">
        <label class="form-label">Koszt XP za rangę <span style="font-weight:400;color:var(--muted,#888)">(puste = wartość domyślna)</span></label>
        <div id="skill-rank-costs" style="display:flex;flex-wrap:wrap;gap:8px">${_rankCostInputs(p)}</div>
      </div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" id="skill-save-btn">Zapisz</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector('#skill-save-btn').addEventListener('click', async () => {
    const key = overlay.querySelector('[name="key"]').value.trim();
    const label = overlay.querySelector('[name="label"]').value.trim();
    const linked_stat = overlay.querySelector('[name="linked_stat"]').value;
    const rank_ceiling = parseInt(overlay.querySelector('[name="rank_ceiling"]').value, 10);
    const description = overlay.querySelector('[name="description"]').value.trim();
    const trigger_keywords = overlay.querySelector('[name="trigger_keywords"]').value.trim();
    // #1382 — collect per-rank overrides; empty inputs inherit the global cost.
    const rank_cost = {};
    overlay.querySelectorAll('.skill-rank-cost').forEach(inp => {
      const r = inp.dataset.rank; const v = parseInt(inp.value, 10);
      if (Number.isFinite(v) && v > 0) rank_cost[r] = v;
    });
    const rank_cost_json = Object.keys(rank_cost).length ? rank_cost : null;
    if (!key) { showToast('Klucz jest wymagany.', 'error'); return; }
    if (!label) { showToast('Nazwa jest wymagana.', 'error'); return; }
    overlay.remove();
    await onSubmit({ key, label, linked_stat, rank_ceiling, description: description||null, trigger_keywords: trigger_keywords||null, rank_cost_json });
  });
}

async function _deleteSkill(root, key, btn, isLocked) {
  const msg = isLocked ? `Umiejętność "${key}" jest zablokowana. Na pewno usunąć?` : `Usunąć umiejętność "${key}"?`;
  if (!confirm(msg)) return;
  btn.disabled = true;
  try {
    const opts = { method: 'DELETE' };
    if (isLocked) { opts.headers = {'Content-Type':'application/json'}; opts.body = JSON.stringify({force:true}); }
    await apiFetch(`/api/admin/skills/${key}`, opts);
    _mechLoaded.delete('skills');
    _loadSkills(root);
    showToast('Usunięto.', 'success');
  } catch(e) { showToast('Błąd: '+e.message, 'error'); btn.disabled = false; }
}

// ── Condition modal ───────────────────────────────────────────────────────────

function _openAddConditionModal(root) { _openConditionForm(root, null); }

async function _openEditConditionModal(root, key) {
  const all = await apiFetch('/api/admin/conditions').then(d => d.items||[]);
  _openConditionForm(root, all.find(c => c.key === key) || null);
}

function _openConditionForm(root, prefill) {
  const p = prefill || {};
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="max-width:440px">
    <div class="modal-head"><span class="modal-title">${p.key ? 'Edytuj kondycję' : 'Nowa kondycja'}</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body">
      <div class="form-row"><label class="form-label">Klucz *</label><input class="form-input" name="key" value="${_esc(p.key||'')}" placeholder="np. poisoned" ${p.key?'readonly':''}></div>
      <div class="form-row"><label class="form-label">Nazwa *</label><input class="form-input" name="label" value="${_esc(p.label||'')}" placeholder="Zatruty"></div>
      <div class="form-row"><label class="form-label">Efekt JSON</label><textarea class="form-input form-mono" name="effect_json" rows="3" placeholder='{"penalty": -2}'>${_esc(typeof p.effect_json==='object'?JSON.stringify(p.effect_json,null,2):(p.effect_json||''))}</textarea></div>
      <div class="form-row"><label class="form-label">Opis</label><textarea class="form-input" name="description" rows="2">${_esc(p.description||'')}</textarea></div>
      <div class="form-row"><label class="form-label">Auto-usuń</label><input class="form-input" name="auto_remove" value="${_esc(p.auto_remove||'')}" placeholder="np. on_turn_end"></div>
      <div class="form-row" style="flex-direction:row;gap:20px;align-items:center">
        <label style="display:flex;gap:6px;align-items:center;cursor:pointer"><input type="checkbox" name="stackable" ${p.stackable?'checked':''}> Kumulowalny</label>
        <label style="display:flex;gap:6px;align-items:center;cursor:pointer"><input type="checkbox" name="is_active" ${(p.is_active??true)?'checked':''}> Aktywny</label>
      </div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" id="cond-save-btn">Zapisz</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector('#cond-save-btn').addEventListener('click', async () => {
    const key = overlay.querySelector('[name="key"]').value.trim();
    const label = overlay.querySelector('[name="label"]').value.trim();
    const effect_json_raw = overlay.querySelector('[name="effect_json"]').value.trim();
    const description = overlay.querySelector('[name="description"]').value.trim();
    const auto_remove = overlay.querySelector('[name="auto_remove"]').value.trim();
    const stackable = overlay.querySelector('[name="stackable"]').checked;
    const is_active = overlay.querySelector('[name="is_active"]').checked;
    if (!key) { showToast('Klucz jest wymagany.', 'error'); return; }
    if (!label) { showToast('Nazwa jest wymagana.', 'error'); return; }
    if (effect_json_raw) {
      try { JSON.parse(effect_json_raw); } catch { showToast('Efekt JSON jest nieprawidłowy.', 'error'); return; }
    }
    overlay.remove();
    const data = { key, label, description: description||null, effect_json: effect_json_raw||null, stackable, is_active, auto_remove: auto_remove||null };
    try {
      if (p.key) {
        await apiFetch(`/api/admin/conditions/${p.key}`, { method:'PATCH', body:JSON.stringify(data) });
      } else {
        await apiFetch('/api/admin/conditions', { method:'POST', body:JSON.stringify(data) });
      }
      _mechLoaded.delete('conditions');
      _loadConditions(root);
      showToast('Zapisano.', 'success');
    } catch(e) { showToast('Błąd: '+e.message, 'error'); }
  });
}

async function _deleteCondition(root, key, btn) {
  if (!confirm(`Usunąć kondycję "${key}"?`)) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/conditions/${key}`, { method: 'DELETE' });
    _mechLoaded.delete('conditions');
    _loadConditions(root);
    showToast('Usunięto.', 'success');
  } catch(e) { showToast('Błąd: '+e.message, 'error'); btn.disabled = false; }
}

// ── Filter ────────────────────────────────────────────────────────────────────

function _filterTable(input, tableId, nameClass, root) {
  const q = input.value.toLowerCase();
  root.querySelectorAll(`#${tableId} tbody tr`).forEach(row => {
    const name = row.querySelector(`.${nameClass}`)?.textContent.toLowerCase() || '';
    row.style.display = name.includes(q) ? '' : 'none';
  });
}

// ── HTML ──────────────────────────────────────────────────────────────────────

function _sectionHtml() {
  return `<section class="section active" id="section-mechanics">
    <div class="section-header">
      <div>
        <div class="section-heading">Mechaniki</div>
        <div class="section-sub">Statystyki, umiejętności, DC, kondycje, archetypy</div>
      </div>
    </div>
    <div class="card" style="margin-bottom:12px">
      <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:12px 14px">
        <div style="font-weight:600">⚔ Encountery — częstotliwość</div>
        <div style="display:flex;align-items:center;gap:6px">
          <label style="font-size:.78rem;color:var(--t3)">Interwał (spokojne tury w dziczy)</label>
          <input id="enc-cfg-interval" type="number" min="3" max="200" class="field-input" style="width:80px">
        </div>
        <div style="display:flex;align-items:center;gap:6px">
          <label style="font-size:.78rem;color:var(--t3)">Osiedlenie (tury → spadek szansy)</label>
          <input id="enc-cfg-dwell" type="number" min="1" max="50" class="field-input" style="width:70px">
        </div>
      </div>
    </div>
    <div class="card" style="margin-bottom:12px">
      <div style="padding:12px 14px">
        <div style="font-weight:600;margin-bottom:8px">🎚 Trudność spotkań <span style="font-weight:400;color:var(--t3);font-size:.74rem">— skaluje siłę i liczebność wrogów w podróży (bez deployu)</span></div>
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px">
          <span style="font-size:.78rem;color:var(--t3)">Preset:</span>
          <button class="btn btn-sm btn-ghost enc-preset-btn" data-mult="0.75">Łatwy</button>
          <button class="btn btn-sm btn-ghost enc-preset-btn" data-mult="1.0">Normalny</button>
          <button class="btn btn-sm btn-ghost enc-preset-btn" data-mult="1.35">Trudny</button>
          <button class="btn btn-sm btn-ghost enc-preset-btn" data-mult="1.75">Hardcore</button>
          <span style="font-size:.78rem;color:var(--t3);margin-left:8px">Mnożnik:</span>
          <input id="enc-cfg-difficulty" type="number" min="0.25" max="3" step="0.05" class="field-input" style="width:80px">
          <button class="btn btn-primary btn-sm" id="enc-cfg-save">Zapisz</button>
          <span id="enc-cfg-status" style="font-size:.75rem;color:var(--t3)"></span>
        </div>
        <details style="margin-bottom:8px">
          <summary style="cursor:pointer;font-size:.78rem;color:var(--t3)">Zaawansowane (budżet zagrożenia, pula)</summary>
          <div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:8px">
            <div style="display:flex;align-items:center;gap:6px"><label style="font-size:.74rem;color:var(--t3)">Budżet bazowy</label><input id="enc-cfg-budget-base" type="number" min="5" max="200" step="1" class="field-input" style="width:70px"></div>
            <div style="display:flex;align-items:center;gap:6px"><label style="font-size:.74rem;color:var(--t3)">Przyrost / pkt Power</label><input id="enc-cfg-budget-power" type="number" min="0" max="100" step="1" class="field-input" style="width:70px"></div>
            <div style="display:flex;align-items:center;gap:6px"><label style="font-size:.74rem;color:var(--t3)">Min. rozmiar puli</label><input id="enc-cfg-pool-min" type="number" min="1" max="30" step="1" class="field-input" style="width:60px"></div>
            <div style="display:flex;align-items:center;gap:6px"><label style="font-size:.74rem;color:var(--t3)">Kara powtórek</label><input id="enc-cfg-repeat" type="number" min="0" max="1" step="0.05" class="field-input" style="width:60px"></div>
          </div>
        </details>
        <div style="border-top:1px solid var(--border);padding-top:8px">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px">
            <span style="font-size:.78rem;color:var(--t3)">Podgląd składu:</span>
            <label style="font-size:.74rem;color:var(--t3)">Poziom</label>
            <input id="enc-preview-level" type="number" min="1" max="20" value="10" class="field-input" style="width:60px">
            <label style="font-size:.74rem;color:var(--t3)">Teren</label>
            <input id="enc-preview-terrain" type="text" placeholder="road / forest / …" class="field-input" style="width:130px">
            <button class="btn btn-sm btn-ghost" id="enc-preview-btn">Losuj skład</button>
          </div>
          <div id="enc-preview-out"></div>
        </div>
      </div>
    </div>
    <div class="card" style="overflow:visible">
      <div class="stab-bar" id="mech-stab-bar">
        <button class="stab active" data-mtab="stats">Statystyki</button>
        <button class="stab" data-mtab="skills">Umiejętności</button>
        <button class="stab" data-mtab="dc">Poziomy DC</button>
        <button class="stab" data-mtab="conditions">Kondycje</button>
        <button class="stab" data-mtab="archetypes">Archetypy</button>
        <button class="stab" data-mtab="xp">Nagrody XP</button>
      </div>
      <div id="mtab-stats" class="stab-panel active">
        <div class="toolbar"><span class="td-muted" style="font-size:0.78rem">Statystyki są zdefiniowane systemowo — możesz edytować nazwę i opis.</span></div>
        <div class="table-wrap data-table--cards">
          <table class="data-table" id="stats-table">
            <thead><tr>
              <th>Klucz</th><th>Nazwa</th><th>Opis</th><th style="width:80px">Zablokowany</th>
            </tr></thead>
            <tbody><tr><td colspan="4" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
          </table>
        </div>
      </div>
      <div id="mtab-skills" class="stab-panel" style="display:none">
        <div class="toolbar">
          <div class="search-box"><span class="search-box-icon">🔍</span><input type="text" id="skills-search" placeholder="Szukaj umiejętności…"></div>
          <button class="btn btn-primary btn-sm" id="add-skill-btn">+ Umiejętność</button>
        </div>
        <div class="table-wrap data-table--cards">
          <table class="data-table" id="skills-table">
            <thead><tr>
              <th>Klucz</th><th>Nazwa</th><th>Statystyka</th><th>Maks. rang</th><th>Słowa kluczowe</th><th>Opis</th><th>Zablokowany</th><th class="td-actions">Akcje</th>
            </tr></thead>
            <tbody><tr><td colspan="8" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
          </table>
        </div>
      </div>
      <div id="mtab-dc" class="stab-panel" style="display:none">
        <div class="toolbar"><span class="td-muted" style="font-size:0.78rem">Poziomy DC są stałe — możesz edytować wartość i opis.</span></div>
        <div class="table-wrap data-table--cards">
          <table class="data-table" id="dc-table">
            <thead><tr>
              <th>Klucz</th><th>Nazwa</th><th style="width:80px">Wartość</th><th>Opis</th><th style="width:80px">Zablokowany</th>
            </tr></thead>
            <tbody><tr><td colspan="5" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
          </table>
        </div>
      </div>
      <div id="mtab-conditions" class="stab-panel" style="display:none">
        <div class="toolbar">
          <div class="search-box"><span class="search-box-icon">🔍</span><input type="text" id="conditions-search" placeholder="Szukaj kondycji…"></div>
          <button class="btn btn-primary btn-sm" id="add-cond-btn">+ Kondycja</button>
        </div>
        <div class="table-wrap data-table--cards">
          <table class="data-table" id="conditions-table">
            <thead><tr>
              <th>Klucz</th><th>Nazwa</th><th>Efekt JSON</th><th style="width:90px">Kumulowalny</th><th style="width:90px">Aktywny</th><th>Zablokowany</th><th class="td-actions">Akcje</th>
            </tr></thead>
            <tbody><tr><td colspan="7" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
          </table>
        </div>
      </div>
      <div id="mtab-archetypes" class="stab-panel" style="display:none">
        <div class="toolbar"><span class="td-muted" style="font-size:0.78rem">Archetypy definiują klasy postaci — HP bazowe i złoto startowe.</span></div>
        <div class="table-wrap data-table--cards">
          <table class="data-table" id="archetypes-table">
            <thead><tr>
              <th>Klucz</th><th>Nazwa</th><th style="width:90px">HP bazowe</th><th style="width:100px">Złoto startowe</th><th>Opis</th><th style="width:80px">Zablokowany</th>
            </tr></thead>
            <tbody><tr><td colspan="6" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
          </table>
        </div>
      </div>
      <div id="mtab-xp" class="stab-panel" style="display:none">
        <div class="toolbar"><span class="td-muted" style="font-size:0.78rem">Katalog zdarzeń przyznających XP (game_config_xp_awards). Tylko do odczytu.</span></div>
        <div class="table-wrap data-table--cards">
          <table class="data-table" id="xp-awards-table">
            <thead><tr>
              <th>Klucz</th><th style="width:110px">Kategoria</th><th>Nazwa</th><th style="width:80px;text-align:right">XP</th><th>Opis</th><th style="width:70px">Aktywny</th>
            </tr></thead>
            <tbody><tr><td colspan="6" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>
  </section>`;
}

// ── Entry point ───────────────────────────────────────────────────────────────

export async function init(panel) {
  _mechLoaded.clear();
  panel.innerHTML = _sectionHtml();
  const root = panel.querySelector('#section-mechanics');

  // Encounter config + BL-A7 (#1423) trudność/podgląd
  _loadEncounterConfig(root);
  root.querySelector('#enc-cfg-save').addEventListener('click', () => _saveEncounterConfig(root));
  root.querySelectorAll('.enc-preset-btn').forEach(b =>
    b.addEventListener('click', () => _applyEncPreset(root, parseFloat(b.dataset.mult))));
  root.querySelector('#enc-preview-btn')?.addEventListener('click', () => _runEncounterPreview(root));

  // Stab bar
  root.querySelector('#mech-stab-bar').querySelectorAll('.stab[data-mtab]').forEach(btn => {
    btn.addEventListener('click', () => {
      root.querySelectorAll('#mech-stab-bar .stab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.mtab;
      root.querySelectorAll('.stab-panel').forEach(p => p.style.display = 'none');
      const tabPanel = root.querySelector(`#mtab-${tab}`);
      if (tabPanel) { tabPanel.style.display = ''; tabPanel.classList.add('active'); }
      _loadTab(root, tab);
    });
  });

  // Search filters
  root.querySelector('#skills-search')?.addEventListener('input', e => _filterTable(e.target, 'skills-table', 'td-name', root));
  root.querySelector('#conditions-search')?.addEventListener('input', e => _filterTable(e.target, 'conditions-table', 'td-name', root));

  // Add buttons
  root.querySelector('#add-skill-btn')?.addEventListener('click', () => _openAddSkillModal(root));
  root.querySelector('#add-cond-btn')?.addEventListener('click', () => _openAddConditionModal(root));

  // Initial load: stats tab
  await _loadTab(root, 'stats');
}
