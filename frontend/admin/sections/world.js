/**
 * FADM-P4 (#406) — sekcja Świat: NPC, wrogowie, tabele łupów, oczekujące.
 * Port 1:1 z admin_panel_v3/index.html + openLootEntriesModal (przeniesione z content).
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';
import { initSortableTable } from '../shared/table.js';

// ── State ──────────────────────────────────────────────────────────────────────
const _loaded = new Set();

// ── Helpers ────────────────────────────────────────────────────────────────────
function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
const _loading = cols => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr>`;
const _errRow  = (cols, msg) => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--red);font-size:0.8rem">Błąd: ${_esc(msg)}</td></tr>`;

function _showToast(msg, type) { showToast(msg, type); }

function filterTableGeneric(input, tableId, nameClass) {
  const q = input.value.toLowerCase();
  document.querySelectorAll(`#${tableId} tbody tr`).forEach(row => {
    const name = row.querySelector(`.${nameClass}`)?.textContent.toLowerCase() || '';
    row.style.display = name.includes(q) ? '' : 'none';
  });
}

function _toggleDetails(tableId, btn) {
  const t = document.getElementById(tableId);
  if (!t) return;
  const on = t.classList.toggle('show-details');
  if (btn) btn.classList.toggle('active', on);
  try { localStorage.setItem(`v3_det_${tableId}`, on ? '1' : '0'); } catch {}
}

// ── Generic row edit/delete ────────────────────────────────────────────────────
const _ROW_REGISTRY = {
  'npcs-table': { endpoint:'/api/admin/npcs', keyField:'id', fields:[
      {name:'label',             label:'Imię',             type:'text'},
      {name:'npc_type',          label:'Typ',              type:'text'},
      {name:'is_ally',           label:'Sojusznik',        type:'checkbox'},
      {name:'is_shop',           label:'Kupiec',           type:'checkbox'},
      {name:'is_quest_giver',    label:'Dawca zadań',      type:'checkbox'},
      {name:'is_active',         label:'Aktywny',          type:'checkbox'},
      {name:'description',       label:'Opis',             type:'textarea'},
      {name:'personality_prompt',label:'Prompt osobowości',type:'textarea'},
    ], reload: () => { _loaded.delete('npcs'); _loadNPCs(); } },
};

function _wireRowActions(tableId) {
  const table = document.getElementById(tableId);
  if (!table || table._wired) return;
  table._wired = true;
  const cfg = _ROW_REGISTRY[tableId];
  if (!cfg) return;
  table.addEventListener('click', e => {
    const editBtn = e.target.closest('.btn-icon[title="Edytuj"]');
    const delBtn  = e.target.closest('.btn-icon[title="Usuń"]');
    if (!editBtn && !delBtn) return;
    const row = (editBtn || delBtn).closest('tr');
    if (!row || !row.dataset.rjson) return;
    let rec;
    try { rec = JSON.parse(decodeURIComponent(row.dataset.rjson)); } catch { return; }
    if (editBtn) { _openGenericEditModal(cfg, rec); return; }
    if (delBtn)  { _genericDelete(cfg, rec); }
  });
}

function _openGenericEditModal(cfg, record) {
  const key = record[cfg.keyField];
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  const fieldsHtml = cfg.fields.map(f => {
    const v = record[f.name];
    if (f.type === 'checkbox') {
      return `<div class="form-row"><label style="display:flex;gap:8px;align-items:center;cursor:pointer"><input type="checkbox" name="${f.name}" ${v?'checked':''}> ${_esc(f.label)}</label></div>`;
    }
    if (f.type === 'textarea') {
      return `<div class="form-row"><label class="form-label">${_esc(f.label)}</label><textarea class="form-input" name="${f.name}" rows="2">${_esc(v||'')}</textarea></div>`;
    }
    return `<div class="form-row"><label class="form-label">${_esc(f.label)}</label><input class="form-input" name="${f.name}" type="${f.type}" value="${_esc(v??'')}"></div>`;
  }).join('');
  overlay.innerHTML = `<div class="modal-box" style="max-width:480px">
    <div class="modal-head"><span class="modal-title">Edytuj rekord</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body" style="padding:12px 16px">
      <div style="font-size:0.72rem;color:var(--t3);margin-bottom:8px">Klucz: <code>${_esc(key)}</code></div>
      ${fieldsHtml}
    </div>
    <div class="modal-foot" style="padding:12px 16px;display:flex;justify-content:flex-end;gap:8px">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" id="gen-save-btn">Zapisz</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector('#gen-save-btn').onclick = async () => {
    const payload = {};
    for (const f of cfg.fields) {
      const el = overlay.querySelector(`[name="${f.name}"]`);
      if (!el) continue;
      if (f.type === 'checkbox') payload[f.name] = el.checked;
      else if (f.type === 'number') { const n = parseFloat(el.value); payload[f.name] = isNaN(n) ? null : n; }
      else payload[f.name] = el.value.trim() || null;
    }
    try {
      await apiFetch(`${cfg.endpoint}/${encodeURIComponent(key)}`, { method:'PATCH', body: JSON.stringify(payload) });
      showToast('Zapisano.', 'success');
      overlay.remove();
      cfg.reload();
    } catch(e) { showToast(e.message || 'Błąd zapisu.', 'error'); }
  };
}

async function _genericDelete(cfg, record) {
  const key = record[cfg.keyField];
  const label = record.label || record.key || key;
  if (!confirm(`Usunąć "${label}"?`)) return;
  try {
    await apiFetch(`${cfg.endpoint}/${encodeURIComponent(key)}`, { method:'DELETE' });
    showToast('Usunięto.', 'success');
    cfg.reload();
  } catch(e) { showToast(e.message || 'Błąd usuwania.', 'error'); }
}

// ── NPC ────────────────────────────────────────────────────────────────────────
async function _loadNPCs() {
  const tbody = document.querySelector('#npcs-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(6);
  try {
    const d = await apiFetch('/api/admin/npcs');
    const items = d.data || d.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--t3)">Brak NPC</td></tr>`; return; }
    tbody.innerHTML = items.slice(0,30).map(n => {
      const att = n.is_ally ? '<span class="badge badge-green">Przyjazny</span>' : (n.npc_type==='hostile'?'<span class="badge badge-red">Wrogi</span>':'<span class="badge badge-amber">Neutralny</span>');
      const loc = Array.isArray(n.location_keys) ? n.location_keys[0] : (n.location_keys||'—');
      const enc = encodeURIComponent(JSON.stringify(n));
      return `<tr data-key="${_esc(n.id??n.key)}" data-rjson="${enc}">
        <td class="col-check"><input type="checkbox"></td>
        <td class="td-sticky td-name">${_esc(n.label||n.key)}</td>
        <td>${att}</td>
        <td class="td-muted">${_esc(loc)}</td>
        <td class="td-muted">${_esc(n.npc_type||'—')}</td>
        <td class="td-actions">${n.is_shop ? `<button class="btn btn-sm" style="font-size:0.72rem;padding:2px 6px;margin-right:4px" title="Ekwipunek sklepu" onclick="window._worldShopInv(${n.id},this)">🛒</button>` : ''}<button class="btn-icon" style="font-size:0.8rem" title="Obraz" onclick="window._worldNpcImage('${_esc(n.id??n.key)}','${enc}')">🖼</button> <button class="btn-icon" title="Edytuj">✎</button> <button class="btn-icon danger" title="Usuń">✕</button></td>
      </tr>`;
    }).join('');
    _wireRowActions('npcs-table');
  } catch(e) { tbody.innerHTML = _errRow(6, e.message); }
}

function openShopInventoryModal(npcId, btn) {
  const row = btn.closest('tr');
  const npcData = JSON.parse(decodeURIComponent(row.dataset.rjson || '{}'));
  const npcLabel = npcData.label || String(npcId);
  let _items = [];
  try { _items = JSON.parse(npcData.shop_inventory_json || '[]'); } catch(e) {}

  function _renderInvItems() {
    if (!_items.length) return '<div style="color:var(--t3);font-size:0.8rem;text-align:center;padding:12px">Brak przedmiotów — dodaj poniżej.</div>';
    return _items.map((it, i) =>
      `<div style="display:flex;align-items:center;gap:6px;padding:5px 8px;background:var(--surface2);border-radius:4px">
        <span class="badge badge-${it.type==='weapon'?'red':it.type==='consumable'?'green':'amber'}" style="font-size:0.7rem">${_esc(it.type)}</span>
        <code style="font-size:0.8rem;flex:1">${_esc(it.key)}</code>
        <button class="btn-icon danger" style="font-size:0.75rem" onclick="window._shopInvRemove(${i})">✕</button>
      </div>`
    ).join('');
  }

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.id = 'shop-inv-modal-' + npcId;
  overlay.innerHTML = `<div class="modal-box" style="max-width:460px">
    <div class="modal-head"><span class="modal-title">🛒 Sklep: ${_esc(npcLabel)}</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body" style="display:flex;flex-direction:column;gap:8px">
      <div id="shop-inv-list-${npcId}" style="display:flex;flex-direction:column;gap:4px;min-height:40px">${_renderInvItems()}</div>
      <hr style="border:none;border-top:1px solid var(--border);margin:2px 0">
      <div style="display:flex;gap:6px;align-items:center">
        <select id="shop-inv-type-${npcId}" class="form-input" style="width:130px">
          <option value="weapon">weapon</option>
          <option value="consumable">consumable</option>
          <option value="item">item</option>
          <option value="armor">armor</option>
        </select>
        <input id="shop-inv-key-${npcId}" class="form-input" style="flex:1" placeholder="klucz (np. longsword, health_potion)">
        <button class="btn btn-secondary btn-sm" onclick="window._shopInvAdd(${npcId})">+ Dodaj</button>
      </div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" id="shop-inv-save-${npcId}" onclick="window._shopInvSave(${npcId})">💾 Zapisz</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);

  window._shopInvRemove = function(i) {
    _items.splice(i, 1);
    const el = document.getElementById('shop-inv-list-' + npcId);
    if (el) el.innerHTML = _renderInvItems();
  };
  window._shopInvAdd = function(id) {
    const type = document.getElementById('shop-inv-type-' + id)?.value || 'item';
    const key = (document.getElementById('shop-inv-key-' + id)?.value || '').trim();
    if (!key) { _showToast('Podaj klucz przedmiotu.', 'error'); return; }
    if (_items.some(it => it.key === key && it.type === type)) { _showToast('Już na liście.', 'error'); return; }
    _items.push({ type, key });
    const el = document.getElementById('shop-inv-list-' + id);
    if (el) el.innerHTML = _renderInvItems();
    const inp = document.getElementById('shop-inv-key-' + id);
    if (inp) inp.value = '';
  };
  window._shopInvSave = async function(id) {
    const btn = document.getElementById('shop-inv-save-' + id);
    if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
    try {
      await apiFetch(`/api/admin/npcs/${id}`, { method: 'PATCH', body: JSON.stringify({ shop_inventory_json: JSON.stringify(_items) }) });
      _showToast('Ekwipunek sklepu zapisany.', 'success');
      document.getElementById('shop-inv-modal-' + id)?.remove();
      _loaded.delete('npcs'); _loadNPCs();
    } catch(e) {
      _showToast(e.message || 'Błąd zapisu.', 'error');
      if (btn) { btn.disabled = false; btn.textContent = '💾 Zapisz'; }
    }
  };
}

// ── Enemies ────────────────────────────────────────────────────────────────────
async function _loadEnemies() {
  const tbody = document.querySelector('#world-enemies-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(9);
  try {
    const d = await apiFetch('/api/admin/enemies');
    const items = d.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:24px;color:var(--t3)">Brak wrogów</td></tr>`; return; }
    const tierBadge = t => ({1:'<span class="badge badge-green">Słaby</span>',2:'<span class="badge badge-blue">Standard</span>',3:'<span class="badge badge-amber">Elita</span>',4:'<span class="badge badge-red">Boss</span>'}[t]||`<span class="badge badge-slate">T${t??'—'}</span>`);
    tbody.innerHTML = items.map(e => {
      const enc = encodeURIComponent(JSON.stringify(e));
      return `<tr data-key="${_esc(e.key)}" data-rjson="${enc}">
        <td class="col-check"><input type="checkbox"></td>
        <td class="td-sticky td-name">${_esc(e.label||e.key)}</td>
        <td class="td-mono">${e.tier??'—'}</td>
        <td class="td-mono">${e.hp_base??'—'}</td>
        <td class="td-mono">${_esc(e.damage_die||'—')}</td>
        <td>${tierBadge(e.tier)}</td>
        <td class="td-muted">${_esc(e.loot_table_key||'—')}</td>
        <td class="td-actions">
          <button class="btn-icon" style="font-size:0.8rem" title="Obraz" onclick="window._worldEnemyImage('${_esc(e.key)}','${enc}')">🖼</button>
          <button class="btn-icon" title="Edytuj" onclick="window._worldEnemyForm('${enc}')">✎</button>
          <button class="btn-icon danger" title="Usuń" onclick="window._worldDeleteEnemy('${_esc(e.key)}',this)">✕</button>
        </td>
      </tr>`;
    }).join('');
    const pg = document.querySelector('#wtab-enemies .pagination span');
    if (pg) pg.textContent = `${items.length} wrogów`;
  } catch(e) { tbody.innerHTML = _errRow(9, e.message); }
}

async function deleteEnemy(key, btn) {
  if (!confirm(`Usunąć wroga "${key}"?`)) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/enemies/${key}`, { method: 'DELETE' });
    _loaded.delete('enemies');
    await _loadEnemies();
    _showToast('Usunięto wroga.', 'success');
  } catch(e) {
    _showToast(e.message || 'Błąd usuwania.', 'error');
    btn.disabled = false;
  }
}

function openEnemyFormModal(prefillOrNull) {
  const p = typeof prefillOrNull === 'string' ? JSON.parse(decodeURIComponent(prefillOrNull)) : (prefillOrNull || {});
  const isEdit = !!p.key;
  const TIERS = ['weak','standard','elite','boss'];
  const DMG_TYPES = ['physical','fire','cold','poison','magic','lightning'];
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.onclick = ev => { if (ev.target === overlay) overlay.remove(); };
  overlay.innerHTML = `<div class="modal" style="max-width:560px">
    <div class="modal-header">
      <div class="modal-title">${isEdit ? 'Edytuj wroga: '+_esc(p.label||p.key) : 'Nowy wróg'}</div>
      <button class="btn-icon" onclick="this.closest('.modal-overlay').remove()">✕</button>
    </div>
    <div class="modal-body" style="overflow-y:auto;max-height:calc(100vh - 140px)">
      <div class="form-grid">
        ${isEdit ? '' : `<div class="form-field form-full"><label class="form-label required">Klucz</label><input id="ef-key" class="form-input mono" placeholder="np. goblin_archer" /></div>`}
        <div class="form-field form-full"><label class="form-label required">Nazwa</label><input id="ef-label" class="form-input" value="${_esc(p.label||'')}" /></div>
        <div class="form-field"><label class="form-label">Poziom</label>
          <select id="ef-tier" class="form-select">${TIERS.map(t=>`<option value="${t}"${p.tier===t?' selected':''}>${t}</option>`).join('')}</select>
        </div>
        <div class="form-field"><label class="form-label">Typ dmg</label>
          <select id="ef-dmgtype" class="form-select">${DMG_TYPES.map(t=>`<option value="${t}"${p.damage_type===t?' selected':''}>${t}</option>`).join('')}</select>
        </div>
        <div class="form-field"><label class="form-label">HP bazowe</label><input id="ef-hp" class="form-input mono" type="number" value="${p.hp_base??''}" /></div>
        <div class="form-field"><label class="form-label">AC bazowe</label><input id="ef-ac" class="form-input mono" type="number" value="${p.ac_base??''}" /></div>
        <div class="form-field"><label class="form-label">Bonus ataku</label><input id="ef-atk" class="form-input mono" type="number" value="${p.attack_bonus??''}" /></div>
        <div class="form-field"><label class="form-label">Kość obrażeń</label><input id="ef-die" class="form-input mono" placeholder="np. 1d6" value="${_esc(p.damage_die||'')}" /></div>
        <div class="form-field"><label class="form-label">Bonus dmg</label><input id="ef-dmgb" class="form-input mono" type="number" value="${p.damage_bonus??''}" /></div>
        <div class="form-field"><label class="form-label">Ataki/turę</label><input id="ef-apts" class="form-input mono" type="number" min="1" value="${p.attacks_per_turn??1}" /></div>
        <div class="form-field"><label class="form-label">Nagroda XP</label><input id="ef-xp" class="form-input mono" type="number" value="${p.xp_award??''}" /></div>
        <div class="form-field"><label class="form-label">Drop %</label><input id="ef-drop" class="form-input mono" type="number" min="0" max="100" value="${p.drop_chance!=null?Math.round(p.drop_chance*100):''}" /></div>
        <div class="form-field form-full"><label class="form-label">Opis</label><textarea id="ef-desc" class="form-textarea" rows="2">${_esc(p.description||'')}</textarea></div>
        <div class="form-field form-full"><label class="form-label">Notatka (specjalne zdolności)</label><textarea id="ef-note" class="form-textarea" rows="2">${_esc(p.note||'')}</textarea></div>
        <div class="form-field form-full">
          <label class="form-label">Obraz</label>
          <div style="display:flex;gap:12px;align-items:center">
            <div style="width:64px;height:80px;border-radius:6px;border:1px dashed var(--border);display:flex;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0;background:var(--canvas)">
              ${p.image_url ? `<img src="${_esc(p.image_url)}" style="width:100%;height:100%;object-fit:cover;border-radius:5px">` : `<span style="font-size:1.4rem;color:var(--t3)">🖼</span>`}
            </div>
            <div style="display:flex;flex-direction:column;gap:6px">
              <span style="font-size:0.75rem;color:var(--t3)">${p.image_url ? 'Obraz przypisany' : 'Brak obrazu'}</span>
              ${isEdit ? `<button type="button" class="btn btn-secondary btn-sm" onclick="this.closest('.modal-overlay').remove();window._worldEnemyImage('${_esc(p.key)}','${encodeURIComponent(JSON.stringify(p))}')">🖼 Generuj / zmień obraz</button>` : ''}
            </div>
          </div>
        </div>
        <div class="form-field"><label class="form-label" style="flex-direction:row;align-items:center;gap:8px;cursor:pointer"><input type="checkbox" id="ef-active" ${p.is_active!==false?'checked':''} /> Aktywny</label></div>
      </div>
    </div>
    <div style="display:flex;gap:8px;justify-content:flex-end;padding:14px 20px;border-top:1px solid var(--border);flex-shrink:0">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" onclick="window._worldSaveEnemy('${_esc(p.key||'')}',this)">Zapisz</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
}

async function saveEnemyForm(existingKey, btn) {
  const g = id => document.getElementById(id);
  const label = g('ef-label')?.value?.trim();
  if (!label) { _showToast('Wypełnij nazwę.', 'error'); return; }
  const key = existingKey || g('ef-key')?.value?.trim();
  if (!key) { _showToast('Wypełnij klucz.', 'error'); return; }
  const body = {
    label, key,
    tier: g('ef-tier')?.value,
    damage_type: g('ef-dmgtype')?.value,
    hp_base: parseInt(g('ef-hp')?.value) || null,
    ac_base: parseInt(g('ef-ac')?.value) || null,
    attack_bonus: parseInt(g('ef-atk')?.value) || 0,
    damage_die: g('ef-die')?.value?.trim() || null,
    damage_bonus: parseInt(g('ef-dmgb')?.value) || 0,
    attacks_per_turn: parseInt(g('ef-apts')?.value) || 1,
    xp_award: parseInt(g('ef-xp')?.value) || 0,
    drop_chance: g('ef-drop')?.value !== '' ? parseInt(g('ef-drop').value)/100 : null,
    description: g('ef-desc')?.value?.trim() || null,
    note: g('ef-note')?.value?.trim() || null,
    is_active: g('ef-active')?.checked ?? true,
  };
  btn.disabled = true; btn.textContent = '⏳';
  try {
    if (existingKey) {
      await apiFetch(`/api/admin/enemies/${existingKey}`, { method: 'PATCH', body: JSON.stringify(body) });
    } else {
      await apiFetch('/api/admin/enemies', { method: 'POST', body: JSON.stringify(body) });
    }
    btn.closest('.modal-overlay').remove();
    _loaded.delete('enemies');
    await _loadEnemies();
    _showToast(existingKey ? 'Zapisano wroga.' : 'Dodano wroga.', 'success');
  } catch(e) {
    _showToast(e.message || 'Błąd zapisu.', 'error');
    btn.disabled = false; btn.textContent = 'Zapisz';
  }
}

// ── Loot tables ────────────────────────────────────────────────────────────────
async function _loadBestiaryLoot() {
  const container = document.getElementById('world-loot-container');
  if (!container) return;
  container.innerHTML = '<div style="padding:28px;text-align:center;color:var(--t3);font-size:0.8rem">Ładowanie…</div>';
  try {
    const d = await apiFetch('/api/admin/loot-tables');
    const items = d.items || [];
    if (!items.length) { container.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Brak tabel łupów.</div>'; return; }
    container.innerHTML = `<div class="table-wrap"><table class="data-table" id="world-loot-table">
      <thead><tr>
        <th><div class="th-inner">Klucz</div></th>
        <th class="td-sticky"><div class="th-inner sorted">Nazwa <span class="sort-icon asc">▲</span></div></th>
        <th><div class="th-inner">Złoto min</div></th>
        <th><div class="th-inner">Złoto max</div></th>
        <th><div class="th-inner">Wpisy</div></th>
        <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
      </tr></thead>
      <tbody>${items.map(t => `<tr>
        <td class="td-mono" style="font-size:0.72rem" data-sort-val="${_esc(t.key)}">${_esc(t.key)}</td>
        <td class="td-sticky td-name" data-sort-val="${_esc(t.label||t.key)}">${_esc(t.label||t.key)}</td>
        <td class="td-mono" data-sort-val="${t.gold_min??''}">${t.gold_min??'—'}</td>
        <td class="td-mono" data-sort-val="${t.gold_max??''}">${t.gold_max??'—'}</td>
        <td class="td-mono" data-sort-val="${t.entries_count??t.entries?.length??''}">${t.entries_count??t.entries?.length??'—'}</td>
        <td class="td-actions">
          <button class="btn btn-sm btn-secondary" style="font-size:0.72rem" onclick="window._worldOpenLootEntries('${_esc(t.key)}','${_esc(t.label||t.key)}')">Wpisy</button>
          <button class="btn-icon" title="Usuń" onclick="window._worldDeleteLootTable('${_esc(t.key)}',this)">✕</button>
        </td>
      </tr>`).join('')}</tbody>
    </table></div>`;
    initSortableTable('world-loot-table');
  } catch(e) { container.innerHTML = `<div style="padding:24px;text-align:center;color:var(--red)">${_esc(e.message)}</div>`; }
}

function _openAddLootTableModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="width:420px">
    <div class="modal-head"><span class="modal-title">Nowa tabela łupów</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body" style="padding:16px;display:flex;flex-direction:column;gap:12px">
      <div><label class="form-label">Klucz *</label><input class="form-input form-mono" id="nlt-key" placeholder="np. loot_bandyta"></div>
      <div><label class="form-label">Nazwa *</label><input class="form-input" id="nlt-label" placeholder="Łupy bandyty"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <div><label class="form-label">Złoto min</label><input class="form-input" id="nlt-gmin" type="number" value="1"></div>
        <div><label class="form-label">Złoto max</label><input class="form-input" id="nlt-gmax" type="number" value="5"></div>
      </div>
      <button class="btn btn-primary" onclick="window._worldSubmitAddLootTable(this)">Utwórz</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
}

async function _submitAddLootTable(btn) {
  const key = document.getElementById('nlt-key')?.value?.trim();
  const label = document.getElementById('nlt-label')?.value?.trim();
  const gold_min = parseInt(document.getElementById('nlt-gmin')?.value) || 1;
  const gold_max = parseInt(document.getElementById('nlt-gmax')?.value) || 5;
  if (!key || !label) { _showToast('Klucz i nazwa wymagane.', 'error'); return; }
  btn.disabled = true;
  try {
    await apiFetch('/api/admin/loot-tables', { method:'POST', body: JSON.stringify({ key, label, gold_min, gold_max }) });
    btn.closest('.modal-overlay').remove();
    _showToast('Tabela utworzona.', 'success');
    _loaded.delete('loot'); _loadBestiaryLoot();
  } catch(e) { _showToast(e.message||'Błąd.','error'); btn.disabled = false; }
}

async function _deleteBestiaryLootTable(key, btn) {
  if (!confirm(`Usunąć tabelę łupów "${key}"?`)) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/loot-tables/${key}`, { method:'DELETE' });
    _showToast('Usunięto.','success');
    _loaded.delete('loot'); _loadBestiaryLoot();
  } catch(e) { _showToast(e.message||'Błąd.','error'); btn.disabled = false; }
}

// ── Loot entries modal (ported from content.js) ────────────────────────────────
async function openLootEntriesModal(tableKey, tableLabel) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="width:640px;max-height:80vh">
    <div class="modal-head">
      <span class="modal-title">Wpisy: ${_esc(tableLabel)}</span>
      <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
    </div>
    <div class="modal-body" style="padding:0">
      <div style="padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:flex-end">
        <button class="btn btn-sm btn-primary" id="add-entry-btn">+ Wpis</button>
      </div>
      <div class="table-wrap" style="max-height:50vh;overflow-y:auto">
        <table class="data-table">
          <thead><tr>
            <th>Przedmiot</th><th>Typ</th><th style="width:70px">Szansa %</th>
            <th style="width:60px">Min. szt</th><th style="width:60px">Maks. szt</th><th class="td-actions">Akcje</th>
          </tr></thead>
          <tbody id="loot-entries-tbody"><tr><td colspan="6" style="text-align:center;padding:20px;color:var(--t3)">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>`;
  document.body.appendChild(overlay);

  const loadEntries = async () => {
    const tb = overlay.querySelector('#loot-entries-tbody');
    tb.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--t3)">Ładowanie…</td></tr>`;
    try {
      const d = await apiFetch(`/api/admin/loot-tables/${tableKey}/entries`);
      const entries = Array.isArray(d) ? d : (d.items || []);
      if (!entries.length) { tb.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--t3)">Brak wpisów</td></tr>`; return; }
      const typeBadge = e => {
        if (e.weapon_key) return `<span class="badge badge-amber">broń</span>`;
        if (e.item_key) return `<span class="badge badge-blue">przedmiot</span>`;
        return `<span class="badge badge-green">konsumable</span>`;
      };
      tb.innerHTML = entries.map((e, i) => `<tr>
        <td class="td-name">${_esc(e.source_label || e.item_key || e.consumable_key || e.weapon_key || '—')}</td>
        <td>${typeBadge(e)}</td>
        <td class="td-mono">${e.weight??'—'}</td>
        <td class="td-mono">${e.qty_min??1}</td>
        <td class="td-mono">${e.qty_max??1}</td>
        <td class="td-actions"><button class="btn-icon danger" data-entry-id="${e.id}">✕</button></td>
      </tr>`).join('');
      tb.querySelectorAll('[data-entry-id]').forEach((btn, i) => {
        btn.onclick = async () => {
          if (!confirm('Usunąć wpis?')) return;
          btn.disabled = true;
          try {
            await apiFetch(`/api/admin/loot-tables/${tableKey}/entries/by-id/${entries[i].id}`, { method:'DELETE' });
            showToast('Usunięto wpis.', 'success');
            loadEntries();
          } catch(err) { showToast('Błąd: '+err.message, 'error'); btn.disabled = false; }
        };
      });
    } catch(err) { tb.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--red);font-size:0.78rem">${_esc(err.message)}</td></tr>`; }
  };

  overlay.querySelector('#add-entry-btn').onclick = () => _openAddLootEntryModal(tableKey, loadEntries);
  loadEntries();
}

function _openAddLootEntryModal(tableKey, onSaved) {
  const overlay2 = document.createElement('div');
  overlay2.className = 'modal-overlay open';
  overlay2.style.zIndex = '300';
  overlay2.innerHTML = `<div class="modal-box" style="width:400px">
    <div class="modal-head"><span class="modal-title">Nowy wpis łupu</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body">
      <div class="form-row"><label class="form-label">Typ źródła</label>
        <select class="form-input" name="source_type">
          <option value="item">Przedmiot</option><option value="weapon">Broń</option><option value="consumable">Konsumable</option>
        </select>
      </div>
      <div class="form-row"><label class="form-label">Klucz źródła *</label><input class="form-input" name="source_key" placeholder="np. sword_basic"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
        <div class="form-row"><label class="form-label">Waga (1-100)</label><input class="form-input" name="weight" type="number" value="50" min="1" max="100"></div>
        <div class="form-row"><label class="form-label">Min szt.</label><input class="form-input" name="qty_min" type="number" value="1" min="1"></div>
        <div class="form-row"><label class="form-label">Max szt.</label><input class="form-input" name="qty_max" type="number" value="1" min="1"></div>
      </div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" id="entry-save-btn">Dodaj</button>
    </div>
  </div>`;
  document.body.appendChild(overlay2);
  overlay2.querySelector('#entry-save-btn').onclick = async () => {
    const source_type = overlay2.querySelector('[name="source_type"]').value;
    const source_key  = overlay2.querySelector('[name="source_key"]').value.trim();
    if (!source_key) { showToast('Klucz źródła jest wymagany.', 'error'); return; }
    const data = { source_type, source_key,
      weight:  parseInt(overlay2.querySelector('[name="weight"]').value,10)||50,
      qty_min: parseInt(overlay2.querySelector('[name="qty_min"]').value,10)||1,
      qty_max: parseInt(overlay2.querySelector('[name="qty_max"]').value,10)||1 };
    overlay2.remove();
    try {
      await apiFetch(`/api/admin/loot-tables/${tableKey}/entries`, { method:'POST', body:JSON.stringify(data) });
      showToast('Dodano wpis.', 'success');
      onSaved();
    } catch(e) { showToast('Błąd: '+e.message, 'error'); }
  };
}

// ── Pending review ─────────────────────────────────────────────────────────────
async function _loadBestiaryPending() {
  const container = document.getElementById('world-pending-container');
  if (!container) return;
  container.innerHTML = '<div style="padding:28px;text-align:center;color:var(--t3);font-size:0.8rem">Ładowanie…</div>';
  try {
    const [npcRes, enemyRes, weapRes, itemRes] = await Promise.allSettled([
      apiFetch('/api/admin/world/pending/npcs'),
      apiFetch('/api/admin/world/pending/enemies'),
      apiFetch('/api/admin/world/pending/weapons'),
      apiFetch('/api/admin/world/pending/items'),
    ]);
    const npcs    = npcRes.status==='fulfilled'   ? (npcRes.value?.items||npcRes.value||[])     : [];
    const enemies = enemyRes.status==='fulfilled' ? (enemyRes.value?.items||enemyRes.value||[]) : [];
    const weapons = weapRes.status==='fulfilled'  ? (weapRes.value?.items||weapRes.value||[])   : [];
    const items   = itemRes.status==='fulfilled'  ? (itemRes.value?.items||itemRes.value||[])   : [];
    const total = npcs.length + enemies.length + weapons.length + items.length;
    const badge = document.getElementById('world-pending-badge');
    if (badge) { badge.textContent = total || ''; badge.style.display = total ? '' : 'none'; }
    if (!total) {
      container.innerHTML = '<div class="empty-state"><div class="empty-icon">✓</div><div class="empty-title">Brak oczekujących</div><div class="empty-sub">Wszystkie NPC, wrogowie, bronie i przedmioty zatwierdzone.</div></div>';
      return;
    }
    const _formatDate = (iso) => {
      if (!iso) return '—';
      try {
        const d = new Date(iso);
        return d.toLocaleString('pl-PL', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
      } catch { return '—'; }
    };
    const _pn = (label, key) => `<div class="td-name">${_esc(label||key)}</div><div class="td-muted" style="font-size:0.7rem;margin-top:1px">${_esc(key)}</div>`;
    const mkNpcRow = p => `<tr>
      <td class="col-check"><input type="checkbox"></td>
      <td class="td-sticky" data-sort-val="${_esc(p.label||p.name||p.key)}">${_pn(p.label||p.name, p.key)}</td>
      <td data-sort-val="NPC"><span class="badge badge-green">NPC</span></td>
      <td class="td-muted" data-sort-val="${_esc(p.npc_type||p.role||'')}">${_esc(p.npc_type||p.role||'—')}</td>
      <td class="td-muted" data-sort-val="${_esc((p.description||p.backstory||'').slice(0,70))}" style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${_esc(p.description||p.backstory||'')}">${_esc((p.description||p.backstory||'').slice(0,70)||'—')}</td>
      <td class="td-muted" data-sort-val="${_esc(p.created_at||'')}" style="font-size:0.78rem;white-space:nowrap">${_formatDate(p.created_at)}</td>
      <td class="td-actions">
        <button class="btn-icon" title="Edytuj i Zatwierdź" onclick="window._worldPendingEditNpc(${JSON.stringify(p).replace(/"/g,'&quot;')})">✎</button>
        <button class="btn-icon success" title="Zatwierdź" onclick="window._worldReviewEntity('npc','${_esc(p.key)}','approve',this)">✓</button>
        <button class="btn-icon danger" title="Odrzuć" onclick="window._worldReviewEntity('npc','${_esc(p.key)}','discard',this)">✕</button>
      </td>
    </tr>`;
    const mkEnemyRow = p => `<tr>
      <td class="col-check"><input type="checkbox"></td>
      <td class="td-sticky" data-sort-val="${_esc(p.label||p.key)}">${_pn(p.label, p.key)}</td>
      <td data-sort-val="Wróg"><span class="badge badge-red">Wróg</span></td>
      <td class="td-muted" data-sort-val="${_esc(p.tier||'')}">${_esc(p.tier||'—')}</td>
      <td class="td-muted" data-sort-val="${_esc((p.description||p.note||'').slice(0,70))}" style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${_esc(p.description||p.note||'')}">${_esc((p.description||p.note||'').slice(0,70)||'—')}</td>
      <td class="td-muted" data-sort-val="${_esc(p.created_at||'')}" style="font-size:0.78rem;white-space:nowrap">${_formatDate(p.created_at)}</td>
      <td class="td-actions">
        <button class="btn-icon" title="Edytuj i Zatwierdź" onclick="window._worldPendingEditEnemy(${JSON.stringify(p).replace(/"/g,'&quot;')})">✎</button>
        <button class="btn-icon success" title="Zatwierdź" onclick="window._worldReviewEntity('enemy','${_esc(p.key)}','approve',this)">✓</button>
        <button class="btn-icon danger" title="Odrzuć" onclick="window._worldReviewEntity('enemy','${_esc(p.key)}','discard',this)">✕</button>
      </td>
    </tr>`;
    const mkWeaponRow = p => `<tr>
      <td class="col-check"><input type="checkbox"></td>
      <td class="td-sticky" data-sort-val="${_esc(p.label||p.key)}">${_pn(p.label, p.key)}</td>
      <td data-sort-val="Broń"><span class="badge badge-amber">Broń</span></td>
      <td class="td-muted" data-sort-val="${_esc(p.weapon_type||p.damage_die||'')}">${_esc(p.weapon_type||p.damage_die||'—')}</td>
      <td class="td-muted" data-sort-val="${_esc((p.description||p.note||'').slice(0,70))}" style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${_esc(p.description||p.note||'')}">${_esc((p.description||p.note||'').slice(0,70)||'—')}</td>
      <td class="td-muted" data-sort-val="${_esc(p.created_at||'')}" style="font-size:0.78rem;white-space:nowrap">${_formatDate(p.created_at)}</td>
      <td class="td-actions">
        <button class="btn-icon success" title="Zatwierdź" onclick="window._worldReviewEntity('weapon','${_esc(p.key)}','approve',this)">✓</button>
        <button class="btn-icon danger" title="Odrzuć" onclick="window._worldReviewEntity('weapon','${_esc(p.key)}','discard',this)">✕</button>
      </td>
    </tr>`;
    const mkItemRow = p => `<tr>
      <td class="col-check"><input type="checkbox"></td>
      <td class="td-sticky" data-sort-val="${_esc(p.label||p.key)}">${_pn(p.label, p.key)}</td>
      <td data-sort-val="Przedmiot"><span class="badge badge-blue">Przedmiot</span></td>
      <td class="td-muted" data-sort-val="${_esc(p.item_type||'')}">${_esc(p.item_type||'—')}</td>
      <td class="td-muted" data-sort-val="${_esc((p.description||p.note||'').slice(0,70))}" style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${_esc(p.description||p.note||'')}">${_esc((p.description||p.note||'').slice(0,70)||'—')}</td>
      <td class="td-muted" data-sort-val="${_esc(p.created_at||'')}" style="font-size:0.78rem;white-space:nowrap">${_formatDate(p.created_at)}</td>
      <td class="td-actions">
        <button class="btn-icon" title="Edytuj i Zatwierdź" onclick="window._worldPendingEditItem(${JSON.stringify(p).replace(/"/g,'&quot;')})">✎</button>
        <button class="btn-icon success" title="Zatwierdź" onclick="window._worldReviewEntity('item','${_esc(p.key)}','approve',this)">✓</button>
        <button class="btn-icon danger" title="Odrzuć" onclick="window._worldReviewEntity('item','${_esc(p.key)}','discard',this)">✕</button>
      </td>
    </tr>`;
    container.innerHTML = `<div class="table-wrap"><table class="data-table" id="bestiary-pending-table">
      <thead><tr>
        <th class="col-check"></th>
        <th class="td-sticky"><div class="th-inner sorted">Nazwa <span class="sort-icon asc">▲</span></div></th>
        <th><div class="th-inner">Typ</div></th>
        <th><div class="th-inner">Rola/Tier</div></th>
        <th><div class="th-inner">Opis</div></th>
        <th><div class="th-inner">Data utworzenia</div></th>
        <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
      </tr></thead>
      <tbody>${[...npcs.map(mkNpcRow), ...enemies.map(mkEnemyRow), ...weapons.map(mkWeaponRow), ...items.map(mkItemRow)].join('')}</tbody>
    </table></div>`;
    initSortableTable('bestiary-pending-table');
  } catch(e) {
    container.innerHTML = `<div style="padding:24px;text-align:center;color:var(--red);font-size:0.8rem">${_esc(e.message)}</div>`;
  }
}

async function reviewEntityBestiary(entityType, key, action, btn) {
  if (!confirm(`${action === 'approve' ? 'Zatwierdź' : 'Odrzuć'} "${key}"?`)) return;
  btn.disabled = true; btn.textContent = '⏳';
  try {
    await apiFetch(`/api/admin/world/review/${entityType}/${key}`, { method: 'POST', body: JSON.stringify({ action }) });
    _showToast(action === 'approve' ? 'Zatwierdzono.' : 'Odrzucono.', 'success');
    _loaded.delete('pending');
    await _loadBestiaryPending();
    if (window.__adminShell && window.__adminShell._loadPendingCount) {
      await window.__adminShell._loadPendingCount();
    }
  } catch(e) {
    _showToast(e.message || 'Błąd.', 'error');
    btn.disabled = false; btn.textContent = action === 'approve' ? '✓ Zatwierdź' : '✕ Odrzuć';
  }
}

function openPendingNpcEditModal(item) {
  const p = typeof item === 'string' ? JSON.parse(item) : item;
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="max-width:540px">
    <div class="modal-head"><span class="modal-title">Edytuj i Zatwierdź NPC: ${_esc(p.label||p.key)}</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body" style="display:grid;gap:10px">
      <div class="form-row"><label class="form-label">Nazwa *</label><input id="pnpc-label" class="field-input" value="${_esc(p.label||'')}"></div>
      <div class="form-row"><label class="form-label">Typ NPC</label><input id="pnpc-type" class="field-input" value="${_esc(p.npc_type||'')}"></div>
      <div style="display:flex;flex-wrap:wrap;gap:14px;padding:4px 0">
        <label style="display:flex;gap:6px;align-items:center;cursor:pointer"><input type="checkbox" id="pnpc-ally" ${p.is_ally?'checked':''}> Sojusznik</label>
        <label style="display:flex;gap:6px;align-items:center;cursor:pointer"><input type="checkbox" id="pnpc-shop" ${p.is_shop?'checked':''}> Kupiec</label>
        <label style="display:flex;gap:6px;align-items:center;cursor:pointer"><input type="checkbox" id="pnpc-quest" ${p.is_quest_giver?'checked':''}> Dawca zadań</label>
        <label style="display:flex;gap:6px;align-items:center;cursor:pointer"><input type="checkbox" id="pnpc-active" ${p.is_active!==false?'checked':''}> Aktywny</label>
      </div>
      <div class="form-row"><label class="form-label">Opis</label><textarea id="pnpc-desc" class="field-input" rows="3">${_esc(p.description||p.backstory||'')}</textarea></div>
      <div class="form-row"><label class="form-label">Osobowość (prompt GM)</label><textarea id="pnpc-prompt" class="field-input" rows="3">${_esc(p.personality_prompt||'')}</textarea></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" onclick="window._worldSavePendingNpc('${_esc(p.key)}',this)">✓ Zapisz i Zatwierdź</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
}

async function savePendingNpc(key, btn) {
  const g = id => document.getElementById(id);
  const label = g('pnpc-label')?.value?.trim();
  if (!label) { _showToast('Wypełnij nazwę.', 'error'); return; }
  btn.disabled = true; btn.textContent = '⏳';
  const body = {
    label,
    npc_type: g('pnpc-type')?.value?.trim() || null,
    is_ally: g('pnpc-ally')?.checked ?? false,
    is_shop: g('pnpc-shop')?.checked ?? false,
    is_quest_giver: g('pnpc-quest')?.checked ?? false,
    is_active: g('pnpc-active')?.checked ?? true,
    description: g('pnpc-desc')?.value?.trim() || null,
    personality_prompt: g('pnpc-prompt')?.value?.trim() || null,
  };
  try {
    await apiFetch(`/api/admin/npcs/${key}`, { method: 'PATCH', body: JSON.stringify(body) });
    await apiFetch(`/api/admin/world/review/npc/${key}`, { method: 'POST', body: JSON.stringify({ action: 'approve' }) });
    btn.closest('.modal-overlay').remove();
    _loaded.delete('pending'); _loaded.delete('npcs');
    await _loadBestiaryPending();
    if (window.__adminShell && window.__adminShell._loadPendingCount) {
      await window.__adminShell._loadPendingCount();
    }
    _showToast('Zatwierdzono NPC.', 'success');
  } catch(e) {
    _showToast(e.message || 'Błąd.', 'error');
    btn.disabled = false; btn.textContent = '✓ Zapisz i Zatwierdź';
  }
}

function openPendingEnemyEditModal(item) {
  const p = typeof item === 'string' ? JSON.parse(item) : item;
  const TIERS = ['weak','standard','elite','boss'];
  const DMG_TYPES = ['physical','fire','cold','poison','magic','lightning'];
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="max-width:560px">
    <div class="modal-head"><span class="modal-title">Edytuj i Zatwierdź: ${_esc(p.label||p.key)}</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body" style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div class="form-row" style="grid-column:1/-1"><label class="form-label">Nazwa *</label><input id="pe-label" class="field-input" value="${_esc(p.label||'')}"></div>
      <div class="form-row"><label class="form-label">Poziom</label>
        <select id="pe-tier" class="field-input">${TIERS.map(t=>`<option value="${t}"${p.tier===t?' selected':''}>${t}</option>`).join('')}</select>
      </div>
      <div class="form-row"><label class="form-label">Typ dmg</label>
        <select id="pe-dmgtype" class="field-input">${DMG_TYPES.map(t=>`<option value="${t}"${p.damage_type===t?' selected':''}>${t}</option>`).join('')}</select>
      </div>
      <div class="form-row"><label class="form-label">HP bazowe</label><input id="pe-hp" class="field-input" type="number" value="${p.hp_base??''}"></div>
      <div class="form-row"><label class="form-label">AC bazowe</label><input id="pe-ac" class="field-input" type="number" value="${p.ac_base??''}"></div>
      <div class="form-row"><label class="form-label">Bonus ataku</label><input id="pe-atk" class="field-input" type="number" value="${p.attack_bonus??''}"></div>
      <div class="form-row"><label class="form-label">Kość obrażeń</label><input id="pe-die" class="field-input" placeholder="np. 1d6" value="${_esc(p.damage_die||'')}"></div>
      <div class="form-row"><label class="form-label">Nagroda XP</label><input id="pe-xp" class="field-input" type="number" value="${p.xp_award??''}"></div>
      <div class="form-row"><label class="form-label">Drop %</label><input id="pe-drop" class="field-input" type="number" min="0" max="100" value="${p.drop_chance!=null?Math.round(p.drop_chance*100):''}"></div>
      <div class="form-row" style="grid-column:1/-1"><label class="form-label">Opis</label><textarea id="pe-desc" class="field-input" rows="2">${_esc(p.description||'')}</textarea></div>
      <div class="form-row" style="grid-column:1/-1"><label class="form-label">Notatka (specjalne zdolności)</label><textarea id="pe-note" class="field-input" rows="2">${_esc(p.note||'')}</textarea></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" onclick="window._worldSavePendingEnemy('${_esc(p.key)}',this)">✓ Zapisz i Zatwierdź</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
}

async function savePendingEnemy(key, btn) {
  const g = id => document.getElementById(id);
  const label = g('pe-label')?.value?.trim();
  if (!label) { _showToast('Wypełnij nazwę.', 'error'); return; }
  btn.disabled = true; btn.textContent = '⏳';
  const body = {
    label, key,
    tier: g('pe-tier')?.value,
    damage_type: g('pe-dmgtype')?.value,
    hp_base: parseInt(g('pe-hp')?.value) || null,
    ac_base: parseInt(g('pe-ac')?.value) || null,
    attack_bonus: parseInt(g('pe-atk')?.value) || 0,
    damage_die: g('pe-die')?.value?.trim() || null,
    xp_award: parseInt(g('pe-xp')?.value) || 0,
    drop_chance: g('pe-drop')?.value !== '' ? parseInt(g('pe-drop').value)/100 : null,
    description: g('pe-desc')?.value?.trim() || null,
    note: g('pe-note')?.value?.trim() || null,
  };
  try {
    await apiFetch(`/api/admin/enemies/${key}`, { method: 'PATCH', body: JSON.stringify(body) });
    await apiFetch(`/api/admin/world/review/enemy/${key}`, { method: 'POST', body: JSON.stringify({ action: 'approve' }) });
    btn.closest('.modal-overlay').remove();
    _loaded.delete('pending'); _loaded.delete('enemies');
    await _loadBestiaryPending();
    if (window.__adminShell && window.__adminShell._loadPendingCount) {
      await window.__adminShell._loadPendingCount();
    }
    _showToast('Zatwierdzono wroga.', 'success');
  } catch(e) {
    _showToast(e.message || 'Błąd.', 'error');
    btn.disabled = false; btn.textContent = '✓ Zapisz i Zatwierdź';
  }
}

function openPendingItemEditModal(item) {
  const p = typeof item === 'string' ? JSON.parse(item) : item;
  const TYPES = ['misc','quest','armor','consumable','narrative'];
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="max-width:520px">
    <div class="modal-head"><span class="modal-title">Edytuj i Zatwierdź: ${_esc(p.label||p.key)}</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body" style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div class="form-row" style="grid-column:1/-1"><label class="form-label">Nazwa *</label><input id="pi-label" class="field-input" value="${_esc(p.label||'')}"></div>
      <div class="form-row"><label class="form-label">Typ</label>
        <select id="pi-type" class="field-input">${TYPES.map(t=>`<option value="${t}"${(p.item_type||'misc')===t?' selected':''}>${t}</option>`).join('')}</select>
      </div>
      <div class="form-row"><label class="form-label">Wartość (GP)</label><input id="pi-value" class="field-input" type="number" min="0" value="${p.value_gp??0}"></div>
      <div class="form-row"><label class="form-label">Waga (kg)</label><input id="pi-weight" class="field-input" type="number" min="0" step="0.1" value="${p.weight_kg??0}"></div>
      <div class="form-row" style="grid-column:1/-1"><label class="form-label">Opis</label><textarea id="pi-desc" class="field-input" rows="2">${_esc(p.description||'')}</textarea></div>
      <div class="form-row" style="grid-column:1/-1"><label class="form-label">Notatka (specjalne zdolności)</label><textarea id="pi-note" class="field-input" rows="2">${_esc(p.note||'')}</textarea></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" onclick="window._worldSavePendingItem('${_esc(p.key)}',this)">✓ Zapisz i Zatwierdź</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
}

async function savePendingItem(key, btn) {
  const g = id => document.getElementById(id);
  const label = g('pi-label')?.value?.trim();
  if (!label) { _showToast('Wypełnij nazwę.', 'error'); return; }
  btn.disabled = true; btn.textContent = '⏳';
  const body = {
    label,
    item_type: g('pi-type')?.value || 'misc',
    value_gp: parseInt(g('pi-value')?.value) || 0,
    weight_kg: g('pi-weight')?.value !== '' ? parseFloat(g('pi-weight').value) : 0,
    description: g('pi-desc')?.value?.trim() || null,
    note: g('pi-note')?.value?.trim() || null,
  };
  try {
    await apiFetch(`/api/admin/items/${key}`, { method: 'PATCH', body: JSON.stringify(body) });
    await apiFetch(`/api/admin/world/review/item/${key}`, { method: 'POST', body: JSON.stringify({ action: 'approve' }) });
    btn.closest('.modal-overlay').remove();
    _loaded.delete('pending');
    await _loadBestiaryPending();
    if (window.__adminShell && window.__adminShell._loadPendingCount) {
      await window.__adminShell._loadPendingCount();
    }
    _showToast('Zatwierdzono przedmiot.', 'success');
  } catch(e) {
    _showToast(e.message || 'Błąd.', 'error');
    btn.disabled = false; btn.textContent = '✓ Zapisz i Zatwierdź';
  }
}

// ── Enemy image modal ──────────────────────────────────────────────────────────
function _buildEnemyImagePrompt(e) {
  const tierMap = { weak:'weak creature, fragile enemy', standard:'standard fantasy enemy, combat ready', elite:'elite dangerous creature, powerful warrior', boss:'massive boss monster, terrifying creature, legendary' };
  const typeMap = {
    humanoid:'humanoid fantasy character, warrior stance', beast:'wild beast, animal creature',
    undead:'undead creature, dark fantasy', demon:'demonic entity, corrupted being',
    dragon:'draconic creature, scales and claws', golem:'stone construct, magical golem',
    spirit:'ethereal spirit, ghostly form', wolf:'wolf, large wolf creature, grey fur, fangs',
    wilk:'wolf, large wolf creature, grey fur, fangs', rat:'rat creature, giant rat',
    szczur:'rat creature, giant rat', goblin:'goblin creature, small green humanoid',
    orc:'orc warrior, muscular green humanoid', ork:'orc warrior, muscular green humanoid',
    skeleton:'skeleton warrior, animated bones', zombie:'zombie, rotting undead',
    vampire:'vampire creature, dark undead', wampir:'vampire creature, dark undead',
    spider:'giant spider, arachnid creature', pająk:'giant spider, arachnid creature',
    troll:'troll creature, large rocky humanoid', giant:'giant creature, enormous humanoid',
    ogre:'ogre creature, massive brute',
  };
  const tier = tierMap[e.tier] || 'fantasy creature';
  const d = ((e.description || '') + ' ' + (e.label || '') + ' ' + (e.key || '')).toLowerCase();
  const typeHint = (() => {
    for (const [k,v] of Object.entries(typeMap)) if (d.includes(k)) return v;
    return 'fantasy enemy creature';
  })();
  const nameTag = e.label ? e.label + ', ' : '';
  if (e._tileContext) {
    return [nameTag + typeHint, tier,
      'top down view, overhead perspective, seen from directly above',
      'isolated creature sprite, single subject, centered',
      'Gloomhaven board game token art style, flat 2D illustration',
      'pure solid black background, void background, no scenery, no floor, no shadows',
      'square format, no text, no UI'].join(', ');
  }
  return [nameTag + typeHint, tier,
    'character portrait, dramatic side lighting',
    'detailed fantasy illustration, dark moody atmosphere',
    'no text, no UI'].join(', ');
}

async function openEnemyImageModal(key, encData) {
  const e = typeof encData === 'string' ? JSON.parse(decodeURIComponent(encData)) : encData;
  const initialPrompt = _buildEnemyImagePrompt(e);
  const m = document.createElement('div');
  m.id = 'enemy-img-modal';
  m.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center';
  m.innerHTML = `<div style="background:var(--surface);border-radius:12px;width:min(560px,96vw);max-height:92vh;display:flex;flex-direction:column;overflow:hidden">
    <div style="padding:14px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;flex-shrink:0">
      <strong>🖼 Obraz: ${_esc(e.label||key)}</strong>
      <span id="ei-trans-badge" style="font-size:0.68rem;background:var(--border);border-radius:4px;padding:2px 6px;color:var(--t3)">✦ auto</span>
      <button onclick="document.getElementById('enemy-img-modal').remove()" style="margin-left:auto;background:none;border:none;color:var(--t2);font-size:1.2rem;cursor:pointer;line-height:1">✕</button>
    </div>
    <div class="modal-body" style="overflow-y:auto;flex:1;padding:16px;display:flex;flex-direction:column;gap:14px">
      <div>
        <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:4px">Prompt (EN)</label>
        <textarea id="ei-prompt" style="resize:none;width:100%;box-sizing:border-box;overflow:hidden;field-sizing:content;min-height:72px;max-height:240px;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px;color:var(--t1);font-size:0.82rem">${_esc(initialPrompt)}</textarea>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <label style="font-size:0.75rem;color:var(--t3)">Rozmiar</label>
        <select id="ei-size" style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:4px 8px;color:var(--t1);font-size:0.8rem">
          <option value="576x1024" selected>576×1024 portret ★</option>
          <option value="768x1024">768×1024 portret 3:4</option>
          <option value="512x512">512×512</option>
          <option value="768x768">768×768</option>
        </select>
        <label style="font-size:0.75rem;color:var(--t3)">Kroki</label>
        <input type="number" id="ei-steps" value="4" min="1" max="20" style="width:52px;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:4px 6px;color:var(--t1);font-size:0.8rem">
      </div>
      <div id="ei-preview" style="min-height:60px;border-radius:8px;border:1px dashed var(--border);display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:0.8rem">
        ${e.image_url ? `<img src="${_esc(e.image_url)}" style="max-width:100%;max-height:300px;border-radius:6px;object-fit:contain">` : 'Brak obrazu'}
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button id="ei-gen-btn" class="btn btn-primary" style="flex:1">⚡ Generuj</button>
        <button id="ei-ref-btn" class="btn btn-secondary" style="flex:1" disabled>🔄 Popraw</button>
        <button id="ei-nobg-btn" class="btn btn-secondary" style="flex:none" ${e.image_url?'':'disabled'} title="Usuń tło">✂ Usuń tło</button>
        <button class="btn btn-secondary" style="flex:none" onclick="window.eiOpenGallery('${_esc(key)}')">🖼 Galeria</button>
      </div>
      <div id="ei-nobg-row" style="display:${e.image_url?'flex':'none'};align-items:center;gap:8px;flex-wrap:nowrap">
        <label style="font-size:0.72rem;color:var(--t3);white-space:nowrap">Próg tła</label>
        <input type="range" id="ei-nobg-thresh" min="5" max="100" value="30" step="1" style="flex:1;accent-color:var(--accent)">
        <span id="ei-nobg-val" style="font-size:0.72rem;color:var(--t2);width:28px;text-align:right">30</span>
      </div>
    </div>
    <div class="modal-foot" style="padding:12px 16px;border-top:1px solid var(--border);display:flex;gap:8px;justify-content:flex-end;flex-shrink:0">
      <button id="ei-accept-btn" class="btn btn-success" disabled>✓ Akceptuj i zapisz</button>
      <button id="ei-remove-btn" class="btn btn-danger" ${e.image_url?'':'disabled'} style="font-size:0.8rem">✕ Usuń obraz</button>
      <button onclick="document.getElementById('enemy-img-modal').remove()" class="btn btn-secondary">Anuluj</button>
    </div>
  </div>`;
  document.body.appendChild(m);
  m.addEventListener('click', ev => { if (ev.target === m) m.remove(); });

  let _lastFilename = e.image_url ? e.image_url.split('/').pop() : null;
  let _lastUrl = e.image_url || null;
  const ta = document.getElementById('ei-prompt');
  const _autoResize = t => { t.style.height='auto'; t.style.height=Math.min(t.scrollHeight,240)+'px'; };
  ta.addEventListener('input', () => _autoResize(ta)); _autoResize(ta);

  document.getElementById('ei-gen-btn').onclick = async () => {
    const btn = document.getElementById('ei-gen-btn');
    btn.disabled = true; btn.textContent = '⏳ Generuję…';
    try {
      const [w,h] = (document.getElementById('ei-size').value||'576x1024').split('x').map(Number);
      const steps = parseInt(document.getElementById('ei-steps').value)||4;
      const r = await apiFetch('/api/admin/images/generate',{method:'POST',body:JSON.stringify({prompt:ta.value.trim()||initialPrompt,width:w,height:h,steps})});
      _lastFilename = r.filename; _lastUrl = r.url;
      document.getElementById('ei-preview').innerHTML = `<img src="${_esc(r.url)}" style="max-width:100%;max-height:300px;border-radius:6px;object-fit:contain">`;
      document.getElementById('ei-ref-btn').disabled = false;
      document.getElementById('ei-accept-btn').disabled = false;
      _showNobgRow();
    } catch(ex) { _showToast(ex.message||'Błąd generowania','error'); }
    finally { btn.disabled=false; btn.textContent='⚡ Generuj'; }
  };

  document.getElementById('ei-ref-btn').onclick = async () => {
    if (!_lastFilename) return;
    const btn = document.getElementById('ei-ref-btn');
    btn.disabled=true; btn.textContent='⏳ Poprawa…';
    try {
      const steps = parseInt(document.getElementById('ei-steps').value)||8;
      const r = await apiFetch('/api/admin/images/refine',{method:'POST',body:JSON.stringify({source_filename:_lastFilename,prompt:ta.value.trim(),denoise:0.6,steps})});
      _lastFilename=r.filename; _lastUrl=r.url;
      document.getElementById('ei-preview').innerHTML=`<img src="${_esc(r.url)}" style="max-width:100%;max-height:300px;border-radius:6px;object-fit:contain">`;
      _showNobgRow();
    } catch(ex){ _showToast(ex.message||'Błąd','error'); }
    finally{ btn.disabled=false; btn.textContent='🔄 Popraw'; }
  };

  document.getElementById('ei-accept-btn').onclick = async () => {
    if (!_lastUrl) return;
    try {
      await apiFetch(`/api/admin/enemies/${encodeURIComponent(key)}`,{method:'PATCH',body:JSON.stringify({image_url:_lastUrl})});
      _showToast('Obraz zapisany.','success');
      m.remove();
      const eRow = document.querySelector(`#world-enemies-table tr[data-key="${CSS.escape(key)}"]`);
      if (eRow) { const cur=JSON.parse(decodeURIComponent(eRow.dataset.rjson||'{}')); cur.image_url=_lastUrl; eRow.dataset.rjson=encodeURIComponent(JSON.stringify(cur)); }
      _loadEnemies();
    } catch(ex){ _showToast(ex.message||'Błąd zapisu','error'); }
  };

  document.getElementById('ei-remove-btn').onclick = async () => {
    try {
      await apiFetch(`/api/admin/enemies/${encodeURIComponent(key)}`,{method:'PATCH',body:JSON.stringify({image_url:null})});
      _showToast('Obraz usunięty.','success');
      document.getElementById('ei-preview').innerHTML='Brak obrazu';
      document.getElementById('ei-remove-btn').disabled=true;
      const eRow=document.querySelector(`#world-enemies-table tr[data-key="${CSS.escape(key)}"]`);
      if(eRow){const cur=JSON.parse(decodeURIComponent(eRow.dataset.rjson||'{}'));cur.image_url=null;eRow.dataset.rjson=encodeURIComponent(JSON.stringify(cur));}
    } catch(ex){ _showToast(ex.message||'Błąd','error'); }
  };

  const _nobgThresh = document.getElementById('ei-nobg-thresh');
  const _nobgVal = document.getElementById('ei-nobg-val');
  _nobgThresh.addEventListener('input', () => { _nobgVal.textContent = _nobgThresh.value; });

  const _showNobgRow = () => {
    document.getElementById('ei-nobg-row').style.display = 'flex';
    document.getElementById('ei-nobg-btn').disabled = false;
  };

  document.getElementById('ei-nobg-btn').onclick = async () => {
    if (!_lastFilename) return;
    const btn = document.getElementById('ei-nobg-btn');
    btn.disabled=true; btn.textContent='⏳ Usuwam…';
    const thresh = parseInt(_nobgThresh.value)||30;
    try {
      const r = await apiFetch(`/api/admin/images/remove-bg/${encodeURIComponent(_lastFilename)}?threshold=${thresh}`,{method:'POST'});
      _lastFilename=r.filename; _lastUrl=r.url;
      document.getElementById('ei-preview').innerHTML=`<div style="background:repeating-conic-gradient(#666 0% 25%,#444 0% 50%) 0 0/16px 16px;border-radius:6px;display:inline-block;max-width:100%"><img src="${_esc(r.url)}" style="max-width:100%;max-height:300px;border-radius:6px;object-fit:contain;display:block"></div>`;
      document.getElementById('ei-accept-btn').disabled=false;
      _showToast('Tło usunięte — sprawdź podgląd.','success');
    } catch(ex){ _showToast(ex.message||'Błąd usuwania tła','error'); }
    finally{ btn.disabled=false; btn.textContent='✂ Usuń tło'; }
  };

  setTimeout(async () => {
    if (e._tileContext || !e.description) return;
    try {
      const r = await apiFetch('/api/admin/images/describe-prompt',{method:'POST',body:JSON.stringify({text:e.description,context:`enemy tier:${e.tier||'standard'}, type:creature`})});
      if (r.keywords) {
        const extra = 'character portrait, dramatic side lighting, dark fantasy illustration, no text, no UI';
        ta.value = r.keywords + ', ' + extra; _autoResize(ta);
        const badge = document.getElementById('ei-trans-badge');
        if (badge) { badge.textContent='✦ auto+AI'; badge.style.background='#7c3aed33'; badge.style.color='#a78bfa'; }
      }
    } catch{}
  }, 100);
}

async function eiOpenGallery(key) {
  let modal = document.createElement('div');
  modal.id = 'ei-gallery-modal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:10000;display:flex;align-items:center;justify-content:center';
  modal.innerHTML = `<div style="background:var(--surface);border-radius:12px;width:min(720px,95vw);max-height:85vh;display:flex;flex-direction:column;overflow:hidden">
    <div style="padding:14px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0">
      <strong>Galeria obrazów</strong>
      <button onclick="document.getElementById('ei-gallery-modal').remove()" style="background:none;border:none;color:var(--t2);font-size:1.2rem;cursor:pointer;line-height:1">✕</button>
    </div>
    <div id="ei-gallery-grid" style="padding:12px;overflow-y:auto;flex:1;display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px">
      <div style="grid-column:1/-1;text-align:center;padding:20px;color:var(--t3)">Ładowanie...</div>
    </div>
  </div>`;
  document.body.appendChild(modal);
  modal.addEventListener('click', ev => { if(ev.target===modal) modal.remove(); });
  const grid = document.getElementById('ei-gallery-grid');
  try {
    const data = await apiFetch('/api/admin/images/list');
    const imgs = data.images || [];
    if (!imgs.length) { grid.innerHTML='<div style="grid-column:1/-1;text-align:center;padding:20px;color:var(--t3)">Brak obrazów.</div>'; return; }
    grid.innerHTML = imgs.map(img => {
      const encUrl = encodeURIComponent(img.url);
      return `<div onclick="window.eiPickGallery('${_esc(key)}','${encUrl}')" style="border:2px solid var(--border);border-radius:6px;overflow:hidden;cursor:pointer;transition:border-color .15s" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'">
        <img src="${_esc(img.url)}" style="width:100%;height:90px;object-fit:cover;display:block" loading="lazy">
        <div style="padding:3px 5px;font-size:0.62rem;color:var(--t3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_esc(img.filename)}</div>
      </div>`;
    }).join('');
  } catch(ex){ grid.innerHTML=`<div style="grid-column:1/-1;text-align:center;color:var(--danger)">${_esc(ex.message)}</div>`; }
}

async function eiPickGallery(key, encUrl) {
  document.getElementById('ei-gallery-modal')?.remove();
  const url = decodeURIComponent(encUrl);
  const prev = document.getElementById('ei-preview');
  if (prev) prev.innerHTML = `<img src="${_esc(url)}" style="max-width:100%;max-height:300px;border-radius:6px;object-fit:contain">`;
  const acceptBtn2 = document.getElementById('ei-accept-btn');
  if (acceptBtn2) {
    acceptBtn2.disabled = false;
    acceptBtn2.onclick = async () => {
      try {
        await apiFetch(`/api/admin/enemies/${encodeURIComponent(key)}`,{method:'PATCH',body:JSON.stringify({image_url:url})});
        _showToast('Obraz zapisany.','success');
        document.getElementById('enemy-img-modal')?.remove();
        _loadEnemies();
      } catch(ex){ _showToast(ex.message||'Błąd','error'); }
    };
  }
}

// ── NPC image modal ────────────────────────────────────────────────────────────
function _buildNpcImagePrompt(n) {
  const typeMap = { merchant:'friendly merchant, shop keeper, rich clothing', quest_giver:'wise quest giver, village elder, distinguished', neutral:'neutral NPC character, townsperson', ally:'heroic ally character, adventurer companion' };
  const type = typeMap[n.npc_type] || 'fantasy NPC character';
  const isAlly = n.is_ally ? 'heroic, trustworthy, adventurer' : '';
  return [type, isAlly, 'character portrait', 'warm fantasy lighting', 'detailed illustration', 'friendly expression', 'no text', 'no UI'].filter(Boolean).join(', ');
}

async function openNpcImageModal(id, encData) {
  const n = typeof encData === 'string' ? JSON.parse(decodeURIComponent(encData)) : encData;
  const initialPrompt = _buildNpcImagePrompt(n);
  const m = document.createElement('div');
  m.id = 'npc-img-modal';
  m.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center';
  m.innerHTML = `<div style="background:var(--surface);border-radius:12px;width:min(560px,96vw);max-height:92vh;display:flex;flex-direction:column;overflow:hidden">
    <div style="padding:14px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;flex-shrink:0">
      <strong>🖼 Obraz NPC: ${_esc(n.label||id)}</strong>
      <span id="ni-trans-badge" style="font-size:0.68rem;background:var(--border);border-radius:4px;padding:2px 6px;color:var(--t3)">✦ auto</span>
      <button onclick="document.getElementById('npc-img-modal').remove()" style="margin-left:auto;background:none;border:none;color:var(--t2);font-size:1.2rem;cursor:pointer;line-height:1">✕</button>
    </div>
    <div class="modal-body" style="overflow-y:auto;flex:1;padding:16px;display:flex;flex-direction:column;gap:14px">
      <div>
        <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:4px">Prompt (EN)</label>
        <textarea id="ni-prompt" style="resize:none;width:100%;box-sizing:border-box;overflow:hidden;field-sizing:content;min-height:72px;max-height:240px;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px;color:var(--t1);font-size:0.82rem">${_esc(initialPrompt)}</textarea>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <label style="font-size:0.75rem;color:var(--t3)">Rozmiar</label>
        <select id="ni-size" style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:4px 8px;color:var(--t1);font-size:0.8rem">
          <option value="576x1024" selected>576×1024 portret ★</option>
          <option value="768x1024">768×1024 portret 3:4</option>
          <option value="512x512">512×512</option>
        </select>
        <label style="font-size:0.75rem;color:var(--t3)">Kroki</label>
        <input type="number" id="ni-steps" value="4" min="1" max="20" style="width:52px;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:4px 6px;color:var(--t1);font-size:0.8rem">
      </div>
      <div id="ni-preview" style="min-height:60px;border-radius:8px;border:1px dashed var(--border);display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:0.8rem">
        ${n.image_url ? `<img src="${_esc(n.image_url)}" style="max-width:100%;max-height:300px;border-radius:6px;object-fit:contain">` : 'Brak obrazu'}
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button id="ni-gen-btn" class="btn btn-primary" style="flex:1">⚡ Generuj</button>
        <button id="ni-ref-btn" class="btn btn-secondary" style="flex:1" disabled>🔄 Popraw</button>
        <button class="btn btn-secondary" style="flex:none" onclick="window.niOpenGallery('${_esc(String(id))}')">🖼 Galeria</button>
      </div>
    </div>
    <div class="modal-foot" style="padding:12px 16px;border-top:1px solid var(--border);display:flex;gap:8px;justify-content:flex-end;flex-shrink:0">
      <button id="ni-accept-btn" class="btn btn-success" disabled>✓ Akceptuj i zapisz</button>
      <button id="ni-remove-btn" class="btn btn-danger" ${n.image_url?'':'disabled'} style="font-size:0.8rem">✕ Usuń obraz</button>
      <button onclick="document.getElementById('npc-img-modal').remove()" class="btn btn-secondary">Anuluj</button>
    </div>
  </div>`;
  document.body.appendChild(m);
  m.addEventListener('click', ev => { if (ev.target===m) m.remove(); });

  let _lastFilename=null, _lastUrl=null;
  const ta=document.getElementById('ni-prompt');
  const _autoResize=t=>{t.style.height='auto';t.style.height=Math.min(t.scrollHeight,240)+'px';};
  ta.addEventListener('input',()=>_autoResize(ta)); _autoResize(ta);

  document.getElementById('ni-gen-btn').onclick = async () => {
    const btn=document.getElementById('ni-gen-btn');
    btn.disabled=true; btn.textContent='⏳ Generuję…';
    try {
      const [w,h]=(document.getElementById('ni-size').value||'576x1024').split('x').map(Number);
      const steps=parseInt(document.getElementById('ni-steps').value)||4;
      const r=await apiFetch('/api/admin/images/generate',{method:'POST',body:JSON.stringify({prompt:ta.value.trim()||initialPrompt,width:w,height:h,steps})});
      _lastFilename=r.filename; _lastUrl=r.url;
      document.getElementById('ni-preview').innerHTML=`<img src="${_esc(r.url)}" style="max-width:100%;max-height:300px;border-radius:6px;object-fit:contain">`;
      document.getElementById('ni-ref-btn').disabled=false;
      document.getElementById('ni-accept-btn').disabled=false;
    } catch(ex){_showToast(ex.message||'Błąd generowania','error');}
    finally{btn.disabled=false;btn.textContent='⚡ Generuj';}
  };

  document.getElementById('ni-ref-btn').onclick = async () => {
    if(!_lastFilename) return;
    const btn=document.getElementById('ni-ref-btn');
    btn.disabled=true; btn.textContent='⏳ Poprawa…';
    try {
      const steps=parseInt(document.getElementById('ni-steps').value)||8;
      const r=await apiFetch('/api/admin/images/refine',{method:'POST',body:JSON.stringify({source_filename:_lastFilename,prompt:ta.value.trim(),denoise:0.6,steps})});
      _lastFilename=r.filename; _lastUrl=r.url;
      document.getElementById('ni-preview').innerHTML=`<img src="${_esc(r.url)}" style="max-width:100%;max-height:300px;border-radius:6px;object-fit:contain">`;
    } catch(ex){_showToast(ex.message||'Błąd','error');}
    finally{btn.disabled=false;btn.textContent='🔄 Popraw';}
  };

  document.getElementById('ni-accept-btn').onclick = async () => {
    if(!_lastUrl) return;
    try {
      await apiFetch(`/api/admin/npcs/${encodeURIComponent(String(id))}`,{method:'PATCH',body:JSON.stringify({image_url:_lastUrl})});
      _showToast('Obraz NPC zapisany.','success');
      m.remove();
      const nRow=document.querySelector(`#npcs-table tr[data-key="${CSS.escape(String(id))}"]`);
      if(nRow){const cur=JSON.parse(decodeURIComponent(nRow.dataset.rjson||'{}'));cur.image_url=_lastUrl;nRow.dataset.rjson=encodeURIComponent(JSON.stringify(cur));}
      _loadNPCs();
    } catch(ex){_showToast(ex.message||'Błąd zapisu','error');}
  };

  document.getElementById('ni-remove-btn').onclick = async () => {
    try {
      await apiFetch(`/api/admin/npcs/${encodeURIComponent(String(id))}`,{method:'PATCH',body:JSON.stringify({image_url:null})});
      _showToast('Obraz usunięty.','success');
      document.getElementById('ni-preview').innerHTML='Brak obrazu';
      document.getElementById('ni-remove-btn').disabled=true;
    } catch(ex){_showToast(ex.message||'Błąd','error');}
  };
}

async function niOpenGallery(id) {
  let modal=document.createElement('div');
  modal.id='ni-gallery-modal';
  modal.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:10000;display:flex;align-items:center;justify-content:center';
  modal.innerHTML=`<div style="background:var(--surface);border-radius:12px;width:min(720px,95vw);max-height:85vh;display:flex;flex-direction:column;overflow:hidden">
    <div style="padding:14px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0">
      <strong>Galeria obrazów</strong>
      <button onclick="document.getElementById('ni-gallery-modal').remove()" style="background:none;border:none;color:var(--t2);font-size:1.2rem;cursor:pointer;line-height:1">✕</button>
    </div>
    <div id="ni-gallery-grid" style="padding:12px;overflow-y:auto;flex:1;display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px">
      <div style="grid-column:1/-1;text-align:center;padding:20px;color:var(--t3)">Ładowanie...</div>
    </div>
  </div>`;
  document.body.appendChild(modal);
  modal.addEventListener('click',ev=>{if(ev.target===modal)modal.remove();});
  const grid=document.getElementById('ni-gallery-grid');
  try {
    const data=await apiFetch('/api/admin/images/list');
    const imgs=data.images||[];
    if(!imgs.length){grid.innerHTML='<div style="grid-column:1/-1;text-align:center;padding:20px;color:var(--t3)">Brak obrazów.</div>';return;}
    grid.innerHTML=imgs.map(img=>{
      const encUrl=encodeURIComponent(img.url);
      return `<div onclick="window.niPickGallery('${_esc(id)}','${encUrl}')" style="border:2px solid var(--border);border-radius:6px;overflow:hidden;cursor:pointer;transition:border-color .15s" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'">
        <img src="${_esc(img.url)}" style="width:100%;height:90px;object-fit:cover;display:block" loading="lazy">
        <div style="padding:3px 5px;font-size:0.62rem;color:var(--t3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_esc(img.filename)}</div>
      </div>`;
    }).join('');
  } catch(ex){grid.innerHTML=`<div style="grid-column:1/-1;text-align:center;color:var(--danger)">${_esc(ex.message)}</div>`;}
}

async function niPickGallery(id, encUrl) {
  document.getElementById('ni-gallery-modal')?.remove();
  const url=decodeURIComponent(encUrl);
  const prev=document.getElementById('ni-preview');
  if(prev) prev.innerHTML=`<img src="${_esc(url)}" style="max-width:100%;max-height:300px;border-radius:6px;object-fit:contain">`;
  const acceptBtn=document.getElementById('ni-accept-btn');
  if(acceptBtn){
    acceptBtn.disabled=false;
    acceptBtn.onclick=async()=>{
      try {
        await apiFetch(`/api/admin/npcs/${encodeURIComponent(id)}`,{method:'PATCH',body:JSON.stringify({image_url:url})});
        _showToast('Obraz NPC zapisany.','success');
        document.getElementById('npc-img-modal')?.remove();
        _loadNPCs();
      } catch(ex){_showToast(ex.message||'Błąd','error');}
    };
  }
}

// ── Add action ─────────────────────────────────────────────────────────────────
function _worldAddAction() {
  const activeTab = document.querySelector('#section-world .stab.active')?.dataset?.wtab;
  if (activeTab === 'enemies') openEnemyFormModal(null);
  else _showToast('Przełącz na zakładkę Wrogowie, aby dodać wroga.','info');
}

// ── Section HTML ───────────────────────────────────────────────────────────────
function _sectionHtml() {
  return `
    <div class="section-header">
      <div>
        <div class="section-heading">Świat</div>
        <div class="section-sub">NPC, wrogowie i oczekujące do zatwierdzenia</div>
      </div>
      <button class="btn btn-primary btn-sm" id="world-add-btn" onclick="window._worldAddAction()">+ Dodaj</button>
    </div>

    <div class="card">
      <div class="section-tabs" id="world-tabs">
        <button class="stab active" data-wtab="npcs">NPC</button>
        <button class="stab" data-wtab="enemies">Wrogowie</button>
        <button class="stab" data-wtab="loot">Tabele Łupów</button>
        <button class="stab" data-wtab="pending">Oczekujące <span class="nav-badge" id="world-pending-badge" style="display:none">0</span></button>
      </div>

      <!-- NPC -->
      <div class="stab-panel active" id="wtab-npcs">
        <div class="toolbar">
          <div class="search-box">
            <span class="search-box-icon">🔍</span>
            <input type="text" placeholder="Szukaj NPC…" oninput="window._worldFilterTable(this,'npcs-table','td-name')">
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table" id="npcs-table">
            <thead><tr>
              <th class="col-check"><input type="checkbox"></th>
              <th class="td-sticky"><div class="th-inner sorted">Imię <span class="sort-icon asc">▲</span></div></th>
              <th><div class="th-inner">Nastawienie</div></th>
              <th><div class="th-inner">Lokacja</div></th>
              <th><div class="th-inner">Rola</div></th>
              <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
            </tr></thead>
            <tbody><tr><td colspan="6" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
          </table>
        </div>
      </div>

      <!-- Wrogowie -->
      <div class="stab-panel" id="wtab-enemies">
        <div class="toolbar">
          <div class="search-box">
            <span class="search-box-icon">🔍</span>
            <input type="text" placeholder="Szukaj wrogów…" oninput="window._worldFilterTable(this,'world-enemies-table','td-name')">
          </div>
          <button class="btn btn-primary btn-sm" onclick="window._worldEnemyForm(null)">+ Dodaj wroga</button>
          <div class="toolbar-right">
            <button class="btn-toggle-details" data-details-for="world-enemies-table" onclick="window._worldToggleDetails('world-enemies-table',this)">Szczegóły</button>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table" id="world-enemies-table">
            <thead><tr>
              <th class="col-check"><input type="checkbox"></th>
              <th class="td-sticky"><div class="th-inner">Nazwa</div></th>
              <th><div class="th-inner">Poziom</div></th>
              <th><div class="th-inner">HP</div></th>
              <th><div class="th-inner">Kość</div></th>
              <th><div class="th-inner">Tier</div></th>
              <th><div class="th-inner">Tabela łupów</div></th>
              <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
            </tr></thead>
            <tbody><tr><td colspan="8" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
          </table>
        </div>
      </div>

      <!-- Tabele Łupów -->
      <div class="stab-panel" id="wtab-loot">
        <div class="toolbar">
          <div class="search-box">
            <span class="search-box-icon">🔍</span>
            <input type="text" placeholder="Szukaj tabel łupów…" oninput="window._worldFilterTable(this,'world-loot-table','td-name')">
          </div>
          <button class="btn btn-primary btn-sm" onclick="window._worldAddLootTable()">+ Dodaj tabelę</button>
        </div>
        <div id="world-loot-container"><div style="padding:28px;text-align:center;color:var(--t3);font-size:0.8rem">Ładowanie…</div></div>
      </div>

      <!-- Oczekujące -->
      <div class="stab-panel" id="wtab-pending">
        <div style="padding:28px;text-align:center;color:var(--t3);font-size:0.8rem" id="world-pending-container">Ładowanie…</div>
      </div>
    </div>`;
}

// ── Tab switching ──────────────────────────────────────────────────────────────
const _TAB_LOADERS = {
  npcs:    () => { if (!_loaded.has('npcs'))    { _loaded.add('npcs');    _loadNPCs().catch(()=>_loaded.delete('npcs')); } },
  enemies: () => { if (!_loaded.has('enemies')) { _loaded.add('enemies'); _loadEnemies().catch(()=>_loaded.delete('enemies')); } },
  loot:    () => { if (!_loaded.has('loot'))    { _loaded.add('loot');    _loadBestiaryLoot().catch(()=>_loaded.delete('loot')); } },
  pending: () => { if (!_loaded.has('pending')) { _loaded.add('pending'); _loadBestiaryPending().catch(()=>_loaded.delete('pending')); } },
};

// ── Init ───────────────────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = _sectionHtml();

  // Expose globals for inline onclick strings
  window._worldFilterTable    = (inp, tid, cls) => filterTableGeneric(inp, tid, cls);
  window._worldToggleDetails  = (tid, btn) => _toggleDetails(tid, btn);
  window._worldAddAction      = () => _worldAddAction();
  window._worldAddLootTable   = () => _openAddLootTableModal();
  window._worldSubmitAddLootTable = (btn) => _submitAddLootTable(btn);
  window._worldOpenLootEntries  = (key, label) => openLootEntriesModal(key, label);
  window._worldDeleteLootTable  = (key, btn) => _deleteBestiaryLootTable(key, btn);
  window._worldEnemyImage     = (key, enc) => openEnemyImageModal(key, enc);
  window._worldEnemyForm      = (p) => openEnemyFormModal(p);
  window._worldSaveEnemy      = (key, btn) => saveEnemyForm(key, btn);
  window._worldDeleteEnemy    = (key, btn) => deleteEnemy(key, btn);
  window._worldShopInv        = (id, btn) => openShopInventoryModal(id, btn);
  window._worldNpcImage       = (id, enc) => openNpcImageModal(id, enc);
  window._worldReviewEntity   = (type, key, action, btn) => reviewEntityBestiary(type, key, action, btn);
  window._worldPendingEditNpc   = (p) => openPendingNpcEditModal(p);
  window._worldSavePendingNpc   = (key, btn) => savePendingNpc(key, btn);
  window._worldPendingEditEnemy = (p) => openPendingEnemyEditModal(p);
  window._worldSavePendingEnemy = (key, btn) => savePendingEnemy(key, btn);
  window._worldPendingEditItem  = (p) => openPendingItemEditModal(p);
  window._worldSavePendingItem  = (key, btn) => savePendingItem(key, btn);
  window.eiOpenGallery  = (key) => eiOpenGallery(key);
  window.eiPickGallery  = (key, enc) => eiPickGallery(key, enc);
  window.niOpenGallery  = (id) => niOpenGallery(id);
  window.niPickGallery  = (id, enc) => niPickGallery(id, enc);

  // Wire tab switching
  panel.querySelector('#world-tabs')?.addEventListener('click', e => {
    const btn = e.target.closest('.stab[data-wtab]');
    if (!btn) return;
    const tab = btn.dataset.wtab;
    panel.querySelectorAll('#world-tabs .stab').forEach(b => b.classList.toggle('active', b === btn));
    panel.querySelectorAll('.stab-panel').forEach(p => p.classList.toggle('active', p.id === `wtab-${tab}`));
    _TAB_LOADERS[tab]?.();
  });

  // smart-entry-saved: refresh enemies when AI creates one
  document.addEventListener('smart-entry-saved', e => {
    if (e.detail?.table === 'game_config_enemies') {
      _loaded.delete('enemies'); _loadEnemies();
    }
  });

  // Load initial tab
  _TAB_LOADERS.npcs();
}
