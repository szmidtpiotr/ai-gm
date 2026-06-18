/**
 * FADM-P3 (#405) — sekcja Zawartość: broń, zbroje, przedmioty, konsumable, czary, tabele łupów + Kreator AI.
 * Port 1:1 z admin_panel_v3/index.html. Dodane: D5 item VIEW modal, loot jako tab.
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

// ── State ──────────────────────────────────────────────────────────────────────
const _loaded = new Set();

// Smart Entry state
let _seOverlay = null, _seSessionId = null, _seCurrentTable = null;
let _seSchemaFields = [], _seDraft = {}, _seExistingKey = null;
const _seSchemaCache = {};

// Image modal state
let _igModels = [];

// Generic edit modal state
let _genModalEjData = null;

// ── Helpers ────────────────────────────────────────────────────────────────────
function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
const _loading = cols => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr>`;
const _errRow  = (cols, msg) => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--red);font-size:0.8rem">Błąd: ${_esc(msg)}</td></tr>`;

function _starsNum(rec) {
  let n;
  if (rec && typeof rec === 'object') {
    n = rec.rarity != null ? rec.rarity : (rec.value_gp || 0);
    if (rec.rarity == null) n = n > 1000 ? 5 : n > 400 ? 4 : n > 150 ? 3 : n > 50 ? 2 : 1;
  } else { n = 1; }
  return Math.max(1, Math.min(5, Math.round(n)));
}

function _stars(rec) {
  const n = _starsNum(rec);
  return `<span class="stars">${[1,2,3,4,5].map(i=>`<span class="star ${i<=n?'on':'off'}">★</span>`).join('')}</span>`;
}

function _toggleDetails(tableId, btn) {
  const t = document.getElementById(tableId);
  if (!t) return;
  const on = t.classList.toggle('show-details');
  if (btn) btn.classList.toggle('active', on);
  try { localStorage.setItem(`v3_det_${tableId}`, on ? '1' : '0'); } catch {}
}

function _restoreDetailsToggle(tableId) {
  try {
    if (localStorage.getItem(`v3_det_${tableId}`) === '1') {
      const t = document.getElementById(tableId);
      if (t) t.classList.add('show-details');
      const btn = document.querySelector(`[data-details-for="${tableId}"]`);
      if (btn) btn.classList.add('active');
    }
  } catch {}
}

function _filterTable(tableId, val) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const q = (val || '').toLowerCase();
  table.querySelectorAll('tbody tr').forEach(row => {
    const name = row.querySelector('.td-name')?.textContent?.toLowerCase() || '';
    const mono = row.querySelector('.td-mono')?.textContent?.toLowerCase() || '';
    row.style.display = (!q || name.includes(q) || mono.includes(q)) ? '' : 'none';
  });
}

// ── Generic row edit/delete ────────────────────────────────────────────────────
const _ROW_REGISTRY = {
  'weapons-table': { endpoint:'/api/admin/weapons', keyField:'key', fields:[
      {name:'label',      label:'Nazwa',        type:'text'},
      {name:'weapon_type',label:'Typ',          type:'text'},
      {name:'damage_die', label:'Kość obrażeń', type:'text'},
      {name:'weight_kg',  label:'Waga (kg)',    type:'number', step:'0.1'},
      {name:'value_gp',   label:'Cena (gp)',    type:'number'},
      {name:'rarity',     label:'Rzadkość (1-5)', type:'number', min:1, max:5},
      {name:'is_active',  label:'Aktywny',      type:'checkbox'},
      {name:'description',label:'Opis',         type:'textarea'},
      {name:'effect_json',label:'Efekty broni (on-equip)', type:'effect_json_builder'},
    ], reload: () => { _loaded.delete('weapons'); _loadWeapons(); } },
  'armor-table': { endpoint:'/api/admin/items', keyField:'key', fields:[
      {name:'label',          label:'Nazwa',     type:'text'},
      {name:'ac_bonus',       label:'Bonus AC',  type:'number'},
      {name:'armor_coverage', label:'Pokrycie',  type:'text'},
      {name:'weight_kg',      label:'Waga (kg)', type:'number', step:'0.1'},
      {name:'value_gp',       label:'Cena (gp)', type:'number'},
      {name:'rarity',         label:'Rzadkość (1-5)', type:'number', min:1, max:5},
      {name:'is_active',      label:'Aktywny',   type:'checkbox'},
      {name:'description',    label:'Opis',      type:'textarea'},
      {name:'effect_json',    label:'Efekty zbroi (on-equip)', type:'effect_json_builder'},
    ], reload: () => { _loaded.delete('armor'); _loadArmor(); } },
  'items-table': { endpoint:'/api/admin/items', keyField:'key', fields:[
      {name:'label',      label:'Nazwa',     type:'text'},
      {name:'item_type',  label:'Typ',       type:'text'},
      {name:'weight_kg',  label:'Waga (kg)', type:'number', step:'0.1'},
      {name:'value_gp',   label:'Cena (gp)', type:'number'},
      {name:'rarity',     label:'Rzadkość (1-5)', type:'number', min:1, max:5},
      {name:'is_active',  label:'Aktywny',   type:'checkbox'},
      {name:'description',label:'Opis',      type:'textarea'},
      {name:'effect_json',label:'Efekty przedmiotu (on-equip)', type:'effect_json_builder'},
    ], reload: () => { _loaded.delete('items'); _loadItems(); } },
  'consumables-table': { endpoint:'/api/admin/consumables', keyField:'key', fields:[
      {name:'label',       label:'Nazwa',         type:'text'},
      {name:'charges',     label:'Ładunki',       type:'number'},
      {name:'base_price',  label:'Cena',          type:'number'},
      {name:'weight_kg',   label:'Waga (kg)',     type:'number', step:'0.1'},
      {name:'rarity',      label:'Rzadkość (1-5)', type:'number', min:1, max:5},
      {name:'is_active',   label:'Aktywny',       type:'checkbox'},
      {name:'description', label:'Opis',          type:'textarea'},
      {name:'effect_json', label:'Efekty on-use', type:'effect_json_builder', effectTypes:'consumable'},
    ], reload: () => { _loaded.delete('consumables'); _loadConsumables(); } },
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

async function _openGenericEditModal(cfg, record) {
  const key = record[cfg.keyField];
  const hasEfxBuilder = cfg.fields.some(f => f.type === 'effect_json_builder');
  if (hasEfxBuilder) await _loadConditionsCache();

  const efxState = {}; // field.name → current effects[]

  const fieldsHtml = cfg.fields.map(f => {
    const v = record[f.name];
    if (f.type === 'effect_json_builder') {
      const existingEffects = (() => {
        try {
          const parsed = typeof v === 'string' ? JSON.parse(v) : (v || null);
          return Array.isArray(parsed) ? parsed : (parsed?.effects || []);
        } catch { return []; }
      })();
      efxState[f.name] = [...existingEffects];
      return `<div class="form-row" style="grid-column:1/-1;margin-top:6px">
        <label class="form-label" style="margin-bottom:4px">${_esc(f.label)}</label>
        <div data-efx-field="${_esc(f.name)}" data-efx-types="${_esc(f.effectTypes||'')}">${_effectBuilderHtml(existingEffects, f.effectTypes)}</div>
      </div>`;
    }
    if (f.type === 'checkbox') {
      return `<div class="form-row"><label style="display:flex;gap:8px;align-items:center;cursor:pointer"><input type="checkbox" name="${f.name}" ${v?'checked':''}> ${_esc(f.label)}</label></div>`;
    }
    if (f.type === 'textarea') {
      return `<div class="form-row"><label class="form-label">${_esc(f.label)}</label><textarea class="form-input" name="${f.name}" rows="2">${_esc(v||'')}</textarea></div>`;
    }
    const step = f.step ? ` step="${f.step}"` : '';
    const min  = f.min !== undefined ? ` min="${f.min}"` : '';
    const max  = f.max !== undefined ? ` max="${f.max}"` : '';
    return `<div class="form-row"><label class="form-label">${_esc(f.label)}</label><input class="form-input" name="${f.name}" type="${f.type}" value="${_esc(v??'')}"${step}${min}${max}></div>`;
  }).join('');

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="max-width:${hasEfxBuilder ? '560px' : '480px'}">
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
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });

  // Wire effect builders
  for (const f of cfg.fields.filter(f => f.type === 'effect_json_builder')) {
    const wrapper = overlay.querySelector(`[data-efx-field="${f.name}"]`);
    const builder = wrapper?.querySelector('.effect-builder');
    if (builder) _wireEffectBuilder(builder, efx => { efxState[f.name] = efx; });
  }

  overlay.querySelector('#gen-save-btn').onclick = async () => {
    const payload = {};
    for (const f of cfg.fields) {
      if (f.type === 'effect_json_builder') {
        const effects = efxState[f.name] || [];
        payload[f.name] = effects.length > 0 ? _effectsToJson(effects, f.effectTypes) : null;
        continue;
      }
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

// ── D5: Item view modal ────────────────────────────────────────────────────────
function _openItemViewModal(rec) {
  const fxJson = rec.effect_json ? (typeof rec.effect_json === 'string' ? rec.effect_json : JSON.stringify(rec.effect_json, null, 2)) : null;
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="max-width:460px">
    <div class="modal-head">
      <span class="modal-title">👁 ${_esc(rec.label || rec.key)}</span>
      <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
    </div>
    <div class="modal-body" style="padding:14px 16px;display:flex;flex-direction:column;gap:10px">
      <div style="font-size:0.72rem;color:var(--t3)">Klucz: <code>${_esc(rec.key)}</code></div>
      ${rec.item_type || rec.weapon_type ? `<div><span class="badge badge-slate">${_esc(rec.item_type || rec.weapon_type)}</span></div>` : ''}
      ${rec.damage_die ? `<div style="font-size:0.85rem">Obrażenia: <strong>${_esc(rec.damage_die)}</strong></div>` : ''}
      ${rec.ac_bonus != null ? `<div style="font-size:0.85rem">AC: <strong>+${rec.ac_bonus}</strong></div>` : ''}
      ${rec.effect_type ? `<div style="font-size:0.85rem">Efekt: <strong>${_esc(rec.effect_type)}</strong>${rec.effect_dice?` ${_esc(rec.effect_dice)}`:''}${rec.effect_bonus?` +${rec.effect_bonus}`:''}</div>` : ''}
      ${rec.weight_kg != null ? `<div style="font-size:0.82rem;color:var(--t2)">Waga: ${rec.weight_kg} kg</div>` : ''}
      ${rec.value_gp != null ? `<div style="font-size:0.82rem;color:var(--t2)">Cena: ${rec.value_gp} sz</div>` : ''}
      ${rec.rarity != null ? `<div>${_stars(rec)}</div>` : ''}
      ${rec.description ? `<div style="font-size:0.82rem;color:var(--t2);line-height:1.5;padding:8px;background:var(--bg3);border-radius:4px">${_esc(rec.description)}</div>` : ''}
      ${fxJson ? `<div><div style="font-size:0.72rem;color:var(--t3);margin-bottom:4px">Efekt JSON</div><pre style="background:#111;border:1px solid #222;border-radius:4px;padding:8px;font-size:0.7rem;color:#888;overflow:auto;max-height:120px;margin:0">${_esc(fxJson)}</pre></div>` : ''}
      ${rec.image_url ? `<div><img src="${_esc(rec.image_url)}" style="max-width:100%;max-height:180px;border-radius:6px;border:1px solid var(--border);object-fit:contain"></div>` : ''}
    </div>
    <div class="modal-foot" style="padding:10px 16px;display:flex;justify-content:flex-end">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Zamknij</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
}

// ── Table loaders ──────────────────────────────────────────────────────────────

async function _loadWeapons() {
  const tbody = document.querySelector('#weapons-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(15);
  try {
    const d = await apiFetch('/api/admin/weapons');
    const items = d.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="15" style="text-align:center;padding:24px;color:var(--t3)">Brak broni</td></tr>`; return; }
    const typeBadge = t => {
      const lt = (t||'').toLowerCase();
      if (lt==='ranged') return `<span class="badge badge-slate">Dystansowa</span>`;
      if (lt==='magic')  return `<span class="badge badge-slate" style="color:#7c3aed">Magiczna</span>`;
      if (lt==='pierce') return `<span class="badge badge-blue">Przebicie</span>`;
      if (lt==='blunt')  return `<span class="badge badge-green">Obuchowa</span>`;
      return `<span class="badge badge-amber">${_esc(t||'Melee')}</span>`;
    };
    const yesNo = v => v ? '<span class="badge badge-green">Tak</span>' : '<span class="badge badge-slate">—</span>';
    tbody.innerHTML = items.map(w => {
      const dmg = w.linked_stat ? `${w.damage_die}+${w.linked_stat}` : (w.damage_die||'—');
      const rng = w.range_m ? `${w.range_m} m` : 'Kontakt';
      const enc = encodeURIComponent(JSON.stringify(w));
      return `<tr data-key="${_esc(w.key)}" data-rjson="${enc}">
        <td class="detail-col td-mono" style="font-size:0.72rem">${_esc(w.key)}</td>
        <td class="td-sticky td-name" style="cursor:pointer" onclick='window._contentViewRec(${JSON.stringify(enc)})'>${_esc(w.label||w.key)}</td>
        <td>${typeBadge(w.weapon_type)}</td>
        <td class="td-mono">${_esc(dmg)}</td>
        <td class="td-muted">${_esc(rng)}</td>
        <td class="detail-col td-muted">${_esc(w.weapon_slot||'—')}</td>
        <td class="detail-col">${yesNo(w.two_handed)}</td>
        <td class="detail-col">${yesNo(w.finesse)}</td>
        <td class="td-mono">${w.weight_kg!=null?w.weight_kg+' kg':'—'}</td>
        <td class="td-mono">${w.value_gp!=null?w.value_gp+' sz':'—'}</td>
        <td data-sort-val="${_starsNum(w)}">${_stars(w)}</td>
        <td class="detail-col">${w.is_active===false?'<span class="badge badge-slate">○</span>':'<span class="badge badge-green">●</span>'}</td>
        <td class="detail-col"><span>${w.is_locked?'🔒':''}</span></td>
        <td class="detail-col"><span style="font-size:0.72rem;color:var(--t3)">${w.template_id?'📖 #'+w.template_id:'—'}</span></td>
        <td class="td-actions">
          <button class="btn-icon" style="font-size:0.8rem" title="Obraz" onclick="window._contentImgModal('${_esc(w.key)}','${enc}','weapon')">🖼</button>
          <button class="btn-icon" title="Edytuj">✎</button>
          <button class="btn-icon danger" title="Usuń">✕</button>
        </td>
      </tr>`;
    }).join('');
    _wireRowActions('weapons-table');
    _restoreDetailsToggle('weapons-table');
  } catch(e) { tbody.innerHTML = _errRow(15, e.message); }
}

async function _loadArmor() {
  const tbody = document.querySelector('#armor-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(13);
  try {
    const d = await apiFetch('/api/admin/items');
    const items = (d.items||[]).filter(it => it.item_type==='armor' || (it.ac_bonus|0) > 0);
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="13" style="text-align:center;padding:24px;color:var(--t3)">Brak zbroi</td></tr>`; return; }
    tbody.innerHTML = items.map(it => {
      const enc = encodeURIComponent(JSON.stringify(it));
      return `<tr data-key="${_esc(it.key)}" data-rjson="${enc}">
        <td class="detail-col td-mono" style="font-size:0.72rem">${_esc(it.key)}</td>
        <td class="td-sticky td-name" style="cursor:pointer" onclick='window._contentViewRec(${JSON.stringify(enc)})'>${_esc(it.label||it.key)}</td>
        <td><span class="badge badge-slate">${_esc(it.item_type||'—')}</span></td>
        <td class="td-mono">${it.ac_bonus!=null?'+'+it.ac_bonus+' AC':'—'}</td>
        <td class="td-muted">—</td>
        <td class="detail-col td-muted">${_esc(it.armor_coverage||'—')}</td>
        <td class="td-mono">${it.weight_kg!=null?it.weight_kg+' kg':'—'}</td>
        <td class="td-mono">${it.value_gp!=null?it.value_gp+' sz':'—'}</td>
        <td data-sort-val="${_starsNum(it)}">${_stars(it)}</td>
        <td class="detail-col">${it.is_active===false?'<span class="badge badge-slate">○</span>':'<span class="badge badge-green">●</span>'}</td>
        <td class="detail-col"><span>${it.is_locked?'🔒':''}</span></td>
        <td class="td-actions">
          <button class="btn-icon" style="font-size:0.8rem" title="Obraz" onclick="window._contentImgModal('${_esc(it.key)}','${enc}','armor')">🖼</button>
          <button class="btn-icon" title="Edytuj">✎</button>
          <button class="btn-icon danger" title="Usuń">✕</button>
        </td>
      </tr>`;
    }).join('');
    _wireRowActions('armor-table');
    _restoreDetailsToggle('armor-table');
  } catch(e) { tbody.innerHTML = _errRow(13, e.message); }
}

async function _loadItems() {
  const tbody = document.querySelector('#items-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(13);
  try {
    const d = await apiFetch('/api/admin/items');
    const items = (d.items||[]).filter(it => it.item_type!=='armor' && it.item_type!=='consumable');
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="13" style="text-align:center;padding:24px;color:var(--t3)">Brak przedmiotów</td></tr>`; return; }
    const typeMap = {tool:{l:'Narzędzie',c:'badge-slate'}, magic:{l:'Magiczne',c:'badge-blue'}, special:{l:'Specjalne',c:'badge-amber'}, quest:{l:'Questowe',c:'badge-red'}};
    tbody.innerHTML = items.map(it => {
      const t = typeMap[it.item_type] || {l:it.item_type||'—',c:'badge-slate'};
      const enc = encodeURIComponent(JSON.stringify(it));
      const fxJson = it.effect_json ? (typeof it.effect_json === 'string' ? it.effect_json : JSON.stringify(it.effect_json)) : '';
      return `<tr data-key="${_esc(it.key)}" data-rjson="${enc}">
        <td class="detail-col td-mono" style="font-size:0.72rem">${_esc(it.key)}</td>
        <td class="td-sticky td-name" style="cursor:pointer" onclick='window._contentViewRec(${JSON.stringify(enc)})'>${_esc(it.label||it.key)}</td>
        <td><span class="badge ${t.c}">${_esc(t.l)}</span></td>
        <td class="td-muted">${_esc((it.description||'').slice(0,55))||'—'}</td>
        <td class="detail-col td-mono" style="font-size:0.68rem;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${_esc(fxJson)}">${_esc(fxJson||'—')}</td>
        <td class="td-mono">${it.weight_kg!=null?it.weight_kg+' kg':'—'}</td>
        <td class="td-mono">${it.value_gp!=null?it.value_gp+' sz':'—'}</td>
        <td data-sort-val="${_starsNum(it)}">${_stars(it)}</td>
        <td class="detail-col td-muted" style="font-size:0.72rem">${_esc(it.created_by||'—')}</td>
        <td class="detail-col">${it.is_active===false?'<span class="badge badge-slate">○</span>':'<span class="badge badge-green">●</span>'}</td>
        <td class="detail-col"><span>${it.is_locked?'🔒':''}</span></td>
        <td class="td-actions">
          <button class="btn-icon" style="font-size:0.8rem" title="Obraz" onclick="window._contentImgModal('${_esc(it.key)}','${enc}','item')">🖼</button>
          <button class="btn-icon" title="Edytuj">✎</button>
          <button class="btn-icon danger" title="Usuń">✕</button>
        </td>
      </tr>`;
    }).join('');
    _wireRowActions('items-table');
    _restoreDetailsToggle('items-table');
  } catch(e) { tbody.innerHTML = _errRow(13, e.message); }
}

async function _loadConsumables() {
  const tbody = document.querySelector('#consumables-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(13);
  try {
    const d = await apiFetch('/api/admin/consumables');
    const items = d.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="13" style="text-align:center;padding:24px;color:var(--t3)">Brak konsumabli</td></tr>`; return; }
    const effBadge = t => { const m={'heal_hp':'badge-green','restore_mana':'badge-blue','remove_condition':'badge-purple','add_condition':'badge-amber'}; const l={'heal_hp':'Leczenie','restore_mana':'Mana','remove_condition':'Oczyszczenie','add_condition':'Kondycja'}; return t?`<span class="badge ${m[t]||'badge-slate'}">${l[t]||t}</span>`:'<span class="td-muted">—</span>'; };
    tbody.innerHTML = items.map(c => {
      const eff = c.effect_dice ? `${c.effect_dice}${c.effect_bonus?'+'+c.effect_bonus:''} ${c.effect_type||''}`.trim() : (c.effect_type||'—');
      const enc = encodeURIComponent(JSON.stringify(c));
      return `<tr data-key="${_esc(c.key)}" data-rjson="${enc}">
        <td class="detail-col td-mono" style="font-size:0.72rem">${_esc(c.key)}</td>
        <td class="td-sticky td-name" style="cursor:pointer" onclick='window._contentViewRec(${JSON.stringify(enc)})'>${_esc(c.label||c.key)}</td>
        <td>${effBadge(c.effect_type)}</td>
        <td class="td-muted">${_esc(eff)}</td>
        <td class="td-muted">${c.charges?c.charges+'× użycie':'Natychmiastowy'}</td>
        <td class="detail-col td-mono">${c.charges??'—'}</td>
        <td class="td-mono">—</td>
        <td class="td-mono">${c.base_price!=null?c.base_price+' sz':'—'}</td>
        <td data-sort-val="${_starsNum(c)}">${_stars(c)}</td>
        <td class="detail-col">${c.is_active===false?'<span class="badge badge-slate">○</span>':'<span class="badge badge-green">●</span>'}</td>
        <td class="detail-col"><span>${c.is_locked?'🔒':''}</span></td>
        <td class="td-actions">
          <button class="btn-icon" style="font-size:0.8rem" title="Obraz" onclick="window._contentImgModal('${_esc(c.key)}','${enc}','consumable')">🖼</button>
          <button class="btn-icon" title="Edytuj">✎</button>
          <button class="btn-icon danger" title="Usuń">✕</button>
        </td>
      </tr>`;
    }).join('');
    _wireRowActions('consumables-table');
    _restoreDetailsToggle('consumables-table');
  } catch(e) { tbody.innerHTML = _errRow(13, e.message); }
}

// ── Effects Builder (F3 #463) ──────────────────────────────────────────────
const _EFFECT_TYPES = [
  {
    value: 'damage_bonus', label: 'Bonus obrażeń', fields: ['value'],
    tooltip: 'Stały bonus do obrażeń (liczba całkowita). Doliczany po rzucie kością, NIE podwaja się przy trafieniu krytycznym.\nNp. 2 = zawsze +2 obrażeń.',
  },
  {
    value: 'heal_on_hit', label: 'Leczenie przy trafieniu', fields: ['value'],
    tooltip: 'HP przywrócone atakującemu przy każdym trafieniu (liczba całkowita). Nie może przekroczyć max HP.\nNp. 3 = leczysz 3 HP za każde trafienie.',
  },
  {
    value: 'ac_bonus', label: 'Bonus AC', fields: ['value'],
    tooltip: 'Dodawany do obrony gracza (AC) jednorazowo na start walki (liczba całkowita). Obowiązuje przez całą walkę.\nNp. 2 = +2 AC.',
  },
  {
    value: 'static_stat_modifier', label: 'Modyfikator statystyki', fields: ['stat', 'value'],
    tooltip: 'Modyfikator statystyki aplikowany na start walki (liczba całkowita, może być ujemna).\nNp. +2 = bonus do statystyki, -1 = klątwa/osłabienie.',
  },
  {
    value: 'apply_condition', label: 'Aplikuj kondycję', fields: ['condition_key', 'duration_rounds'],
    tooltip: 'Aplikuje wybraną kondycję na wroga przy trafieniu. Nie nakłada duplikatów tej samej kondycji.',
  },
  { value: 'narrative_only', label: 'Tylko narracja', fields: [],
    tooltip: 'Brak efektu mechanicznego — LLM może odczytać opis w note i narrować specjalne właściwości.' },
];

// On-use effects dla konsumabli (#771) — oddzielne od gearowych on-equip
const _CONSUMABLE_EFFECT_TYPES = [
  { value: 'heal_hp', label: 'Leczenie HP', fields: ['value'],
    tooltip: 'Leczy HP gracza. Wartość: kostka (np. 2d4) lub liczba całkowita.' },
  { value: 'restore_mana', label: 'Przywróć manę', fields: ['value'],
    tooltip: 'Przywraca manę gracza (tylko Scholar). Wartość: kostka lub liczba.' },
  { value: 'remove_condition', label: 'Zdejmij kondycję', fields: ['condition_key'],
    tooltip: 'Usuwa wybraną kondycję z gracza (np. antidote → poisoned).' },
  { value: 'apply_condition', label: 'Aplikuj kondycję', fields: ['condition_key', 'target', 'duration_rounds'],
    tooltip: 'Aplikuje kondycję na gracza (self) lub wroga (enemy) przez N rund.' },
  { value: 'damage_enemy', label: 'Obrażenia wrogowi ⭐', fields: ['value', 'target'],
    tooltip: 'Zadaje obrażenia wrogowi w walce. Poza walką → tylko narracja. Wartość: kostka (np. 2d6).' },
  { value: 'narrative_only', label: 'Tylko narracja', fields: [],
    tooltip: 'Brak efektu mechanicznego — LLM narruje użycie.' },
];

const _STATS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];

// Cache kondycji dla dropdownu apply_condition — ładowany raz przy otwarciu modalu
let _conditionsCache = null;

async function _loadConditionsCache() {
  if (_conditionsCache !== null) return;
  try {
    const d = await apiFetch('/api/admin/conditions');
    _conditionsCache = (d.items || []).map(c => ({ key: c.key, label: c.label || c.key }));
  } catch {
    _conditionsCache = [];
  }
}

function _resolveEffectTypes(effectTypesHint) {
  return effectTypesHint === 'consumable' ? _CONSUMABLE_EFFECT_TYPES : _EFFECT_TYPES;
}

function _effectBuilderHtml(effects, effectTypesHint) {
  const rows = (effects || []).map((e, i) => _effectRowHtml(e, i, effectTypesHint)).join('');
  return `<div class="effect-builder" id="effect-builder" data-etypes="${_esc(effectTypesHint||'')}">
    <div id="effect-rows">${rows}</div>
    <button type="button" class="btn btn-sm btn-secondary" id="add-effect-btn" style="margin-top:6px">+ Efekt</button>
  </div>`;
}

function _effectRowHtml(e, i, effectTypesHint) {
  const types = _resolveEffectTypes(effectTypesHint);
  const defaultType = types[0]?.value || 'damage_bonus';
  const typeSel = `<select class="form-input effect-type-sel" style="min-width:170px" data-idx="${i}">
    ${types.map(t => `<option value="${t.value}"${e.type===t.value?' selected':''}>${_esc(t.label)}</option>`).join('')}
  </select>`;
  const tdef = types.find(t => t.value === (e.type || defaultType)) || types[0];
  const extraFields = _buildExtraFields(tdef, e);
  return `<div class="effect-row" data-idx="${i}" style="display:flex;gap:6px;align-items:flex-end;margin-bottom:6px;flex-wrap:wrap">
    ${typeSel}
    <div class="effect-extra" style="display:flex;gap:6px;align-items:flex-end;flex-wrap:wrap">${extraFields}</div>
    <button type="button" class="btn-icon danger effect-del" data-idx="${i}" title="Usuń efekt">✕</button>
  </div>`;
}

function _buildExtraFields(tdef, e) {
  return (tdef.fields || []).map(f => {
    if (f === 'value') {
      const tip = tdef.tooltip ? ` title="${_esc(tdef.tooltip)}"` : '';
      return `<input class="form-input effect-value" type="number" placeholder="Wartość" value="${e.value??''}" style="width:90px"${tip}>`;
    }
    if (f === 'stat') {
      return `<select class="form-input effect-stat" style="width:80px" title="${_esc(tdef.tooltip||'')}">
        ${_STATS.map(s => `<option${e.stat===s?' selected':''}>${s}</option>`).join('')}
      </select>`;
    }
    if (f === 'condition_key') {
      const conds = _conditionsCache || [];
      if (conds.length) {
        const opts = conds.map(c => `<option value="${_esc(c.key)}"${e.condition_key===c.key?' selected':''}>${_esc(c.label)}</option>`).join('');
        return `<select class="form-input effect-cond-key" style="width:160px" title="${_esc(tdef.tooltip||'')}"><option value="">— kondycja —</option>${opts}</select>`;
      }
      return `<input class="form-input effect-cond-key" type="text" placeholder="klucz kondycji" value="${_esc(e.condition_key||'')}" style="width:130px" title="${_esc(tdef.tooltip||'')}">`;
    }
    if (f === 'duration_rounds') return `<input class="form-input effect-duration" type="number" placeholder="Rundy" value="${e.duration_rounds??3}" style="width:70px" title="Liczba rund trwania kondycji (0 = do końca walki)">`;
    if (f === 'target') {
      const cur = e.target || 'self';
      return `<select class="form-input effect-target" style="width:100px" title="Cel efektu">
        <option value="self"${cur==='self'?' selected':''}>self (gracz)</option>
        <option value="enemy"${cur==='enemy'?' selected':''}>enemy (wróg)</option>
        <option value="area"${cur==='area'?' selected':''}>area (obszar)</option>
      </select>`;
    }
    return '';
  }).join('');
}

function _wireEffectBuilder(container, onChange) {
  const rowsEl = container.querySelector('#effect-rows');
  const addBtn = container.querySelector('#add-effect-btn');
  const builderEl = container.querySelector('.effect-builder') || container.querySelector('#effect-builder');
  const effectTypesHint = builderEl?.dataset?.etypes || '';
  const types = _resolveEffectTypes(effectTypesHint);

  const _wireRows = () => {
    rowsEl.querySelectorAll('.effect-type-sel').forEach(sel => {
      sel.addEventListener('change', () => {
        const i = parseInt(sel.dataset.idx);
        const effects = _readEffects(container, effectTypesHint);
        effects[i] = { type: sel.value };
        rowsEl.innerHTML = effects.map((e, j) => _effectRowHtml(e, j, effectTypesHint)).join('');
        _wireRows();
        onChange(effects);
      });
    });
    rowsEl.querySelectorAll('.effect-del').forEach(btn => {
      btn.addEventListener('click', () => {
        const i = parseInt(btn.dataset.idx);
        const effects = _readEffects(container, effectTypesHint);
        effects.splice(i, 1);
        rowsEl.innerHTML = effects.map((e, j) => _effectRowHtml(e, j, effectTypesHint)).join('');
        _wireRows();
        onChange(effects);
      });
    });
    rowsEl.querySelectorAll('.effect-value,.effect-stat,.effect-duration,.effect-target').forEach(inp => {
      inp.addEventListener('input', () => onChange(_readEffects(container, effectTypesHint)));
      inp.addEventListener('change', () => onChange(_readEffects(container, effectTypesHint)));
    });
    rowsEl.querySelectorAll('.effect-cond-key').forEach(el => {
      el.addEventListener('change', () => onChange(_readEffects(container, effectTypesHint)));
      el.addEventListener('input', () => onChange(_readEffects(container, effectTypesHint)));
    });
  };

  addBtn.addEventListener('click', () => {
    const effects = _readEffects(container, effectTypesHint);
    effects.push({ type: types[0]?.value || 'damage_bonus' });
    rowsEl.innerHTML = effects.map((e, i) => _effectRowHtml(e, i, effectTypesHint)).join('');
    _wireRows();
    onChange(effects);
  });

  _wireRows();
}

function _readEffects(container, effectTypesHint) {
  const types = _resolveEffectTypes(effectTypesHint);
  const defaultType = types[0]?.value || 'damage_bonus';
  const rows = container.querySelectorAll('#effect-rows .effect-row');
  return Array.from(rows).map(row => {
    const type = row.querySelector('.effect-type-sel')?.value || defaultType;
    const tdef = types.find(t => t.value === type) || types[0];
    const e = { type };
    if (tdef.fields.includes('value')) {
      const raw = row.querySelector('.effect-value')?.value ?? '';
      const v = parseFloat(raw);
      // preserve dice strings (e.g. "2d6") as-is
      e.value = isNaN(v) ? (raw.trim() || 0) : v;
    }
    if (tdef.fields.includes('stat')) {
      e.stat = row.querySelector('.effect-stat')?.value || 'STR';
    }
    if (tdef.fields.includes('condition_key')) {
      e.condition_key = (row.querySelector('.effect-cond-key')?.value || '').trim();
    }
    if (tdef.fields.includes('duration_rounds')) {
      const d = parseInt(row.querySelector('.effect-duration')?.value ?? '3');
      e.duration_rounds = isNaN(d) ? 3 : d;
    }
    if (tdef.fields.includes('target')) {
      e.target = row.querySelector('.effect-target')?.value || 'self';
    }
    return e;
  });
}

function _effectsToJson(effects, effectTypesHint) {
  if (!effects || !effects.length) return null;
  const category = effectTypesHint === 'consumable' ? 'consumable_immediate' : 'gear_bonus';
  return JSON.stringify({ schema_version: 1, effect_category: category, effects });
}

function _parseEffectJson(raw) {
  if (!raw) return [];
  try {
    const p = typeof raw === 'string' ? JSON.parse(raw) : raw;
    return Array.isArray(p.effects) ? p.effects : [];
  } catch { return []; }
}

// ── Affixes (F3 #463) ─────────────────────────────────────────────────────
async function _loadAffixes() {
  const tbody = document.querySelector('#affixes-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(6);
  try {
    const data = await apiFetch('/api/admin/affixes');
    const items = data.items || [];
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--t3)">Brak afiksów</td></tr>`;
      return;
    }
    const tierBadge = t => `<span class="badge badge-${['','blue','green','amber','red','red'][t]||'slate'}">T${t}</span>`;
    tbody.innerHTML = items.map(a => {
      const effects = _parseEffectJson(a.effect_json);
      const effectSummary = effects.map(e => {
        const tdef = _EFFECT_TYPES.find(t => t.value === e.type);
        const label = tdef?.label || e.type;
        const val = e.value != null ? ` +${e.value}` : (e.stat ? ` ${e.stat}+${e.value||'?'}` : (e.condition_key ? ` ${e.condition_key}` : ''));
        return `<span class="badge badge-slate" style="font-size:0.65rem">${_esc(label)}${_esc(val)}</span>`;
      }).join(' ') || '<span class="td-muted">—</span>';
      const enc = encodeURIComponent(JSON.stringify(a));
      return `<tr data-key="${_esc(a.key)}" data-rjson="${enc}">
        <td class="td-sticky td-mono td-name" style="cursor:pointer" onclick="window._contentAffixEdit('${enc}')">${_esc(a.key)}</td>
        <td>${_esc(a.name)}</td>
        <td>${tierBadge(a.tier||1)}</td>
        <td><span class="badge badge-slate">${_esc(a.allowed_item_types||'weapon')}</span></td>
        <td style="padding:4px 8px">${effectSummary}</td>
        <td class="td-actions">
          <button class="btn-icon" title="Edytuj" onclick="window._contentAffixEdit('${enc}')">✎</button>
          <button class="btn-icon danger" title="Usuń" onclick="window._contentAffixDelete('${_esc(a.key)}',this)">✕</button>
        </td>
      </tr>`;
    }).join('');
    const badge = document.querySelector('#content-tabs .stab[data-tab="affixes"] span');
    if (badge) badge.textContent = `(${items.length})`;
  } catch(e) { tbody.innerHTML = _errRow(6, e.message); }
}

async function _openAffixModal(existing) {
  await _loadConditionsCache();
  const isEdit = !!existing;
  const effects = _parseEffectJson(existing?.effect_json);
  let currentEffects = effects;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="max-width:560px">
    <div class="modal-head">
      <span class="modal-title">${isEdit ? 'Edytuj afiks' : 'Nowy afiks'}</span>
      <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
    </div>
    <div class="modal-body" style="padding:12px 16px">
      ${isEdit ? `<div style="font-size:0.72rem;color:var(--t3);margin-bottom:8px">Klucz: <code>${_esc(existing.key)}</code></div>` : `
      <div class="form-row">
        <label class="form-label">Klucz *</label>
        <input class="form-input" name="key" type="text" placeholder="np. sharp_plus" value="${_esc(existing?.key||'')}">
      </div>`}
      <div class="form-row">
        <label class="form-label">Nazwa *</label>
        <input class="form-input" name="name" type="text" placeholder="np. Ostry +" value="${_esc(existing?.name||'')}">
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <div class="form-row">
          <label class="form-label">Tier (1-5)</label>
          <input class="form-input" name="tier" type="number" min="1" max="5" value="${existing?.tier||1}">
        </div>
        <div class="form-row">
          <label class="form-label">Typ przedmiotu</label>
          <select class="form-input" name="allowed_item_types">
            ${['weapon','armor','consumable','misc'].map(t => `<option${(existing?.allowed_item_types||'weapon')===t?' selected':''}>${t}</option>`).join('')}
          </select>
        </div>
      </div>
      <div class="form-row">
        <label class="form-label" style="margin-bottom:6px">Efekty</label>
        ${_effectBuilderHtml(effects)}
      </div>
      <div class="form-row" style="margin-top:4px">
        <label style="display:flex;gap:8px;align-items:center;cursor:pointer">
          <input type="checkbox" name="is_active" ${(existing?.is_active!==false)?'checked':''}> Aktywny
        </label>
      </div>
    </div>
    <div class="modal-foot" style="padding:12px 16px;display:flex;justify-content:flex-end;gap:8px">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" id="affix-save-btn">Zapisz</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);

  _wireEffectBuilder(overlay.querySelector('#effect-builder'), efx => { currentEffects = efx; });

  overlay.querySelector('#affix-save-btn').onclick = async () => {
    const key = isEdit ? existing.key : (overlay.querySelector('[name="key"]')?.value?.trim() || '');
    const name = overlay.querySelector('[name="name"]').value.trim();
    const tier = parseInt(overlay.querySelector('[name="tier"]').value) || 1;
    const allowed_item_types = overlay.querySelector('[name="allowed_item_types"]').value;
    const is_active = overlay.querySelector('[name="is_active"]').checked;
    const effect_json = _effectsToJson(currentEffects);

    if (!name) { showToast('Nazwa jest wymagana.', 'warn'); return; }
    if (!isEdit && !key) { showToast('Klucz jest wymagany.', 'warn'); return; }

    try {
      if (isEdit) {
        await apiFetch(`/api/admin/affixes/${encodeURIComponent(key)}`, {
          method: 'PATCH',
          body: JSON.stringify({ name, tier, allowed_item_types, effect_json, is_active }),
        });
      } else {
        await apiFetch('/api/admin/affixes', {
          method: 'POST',
          body: JSON.stringify({ key, name, tier, allowed_item_types, effect_json, is_active }),
        });
      }
      showToast(isEdit ? 'Afiks zaktualizowany.' : 'Afiks dodany.', 'success');
      overlay.remove();
      _loaded.delete('affixes');
      _loadAffixes();
    } catch(e) { showToast(e.message || 'Błąd zapisu.', 'error'); }
  };
}

async function _deleteAffix(key, btn) {
  if (!confirm(`Usunąć afiks "${key}"?`)) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/affixes/${encodeURIComponent(key)}`, { method: 'DELETE' });
    showToast('Usunięto afiks.', 'success');
    _loaded.delete('affixes');
    _loadAffixes();
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; }
}

async function _loadLootTables() {
  const tbody = document.querySelector('#loot-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(6);
  try {
    const data = await apiFetch('/api/admin/loot-tables');
    const items = Array.isArray(data) ? data : (data.items || []);
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--t3)">Brak tabel łupów</td></tr>`; return; }
    tbody.innerHTML = items.map(lt => `<tr>
      <td class="td-sticky td-mono td-name">${_esc(lt.key)}</td>
      <td>${_esc(lt.label||'—')}</td>
      <td class="td-mono">${lt.gold_min??'—'}</td>
      <td class="td-mono">${lt.gold_max??'—'}</td>
      <td style="text-align:center">${lt.is_active ? '<span class="badge badge-green">●</span>' : '<span class="badge badge-slate">○</span>'}</td>
      <td class="td-actions">
        <button class="btn btn-sm btn-secondary" onclick="window._contentOpenLootEntries('${_esc(lt.key)}','${_esc(lt.label||lt.key)}')">Wpisy</button>
        <button class="btn-icon danger" title="Usuń" onclick="window._contentDeleteLootTable('${_esc(lt.key)}',this)">✕</button>
      </td>
    </tr>`).join('');
    const badge = document.querySelector('#content-tabs .stab[data-tab="loot"] span');
    if (badge) badge.textContent = `(${items.length})`;
  } catch(e) { tbody.innerHTML = _errRow(6, e.message); }
}

async function _loadSpells() {
  const tbody = document.querySelector('#spells-table tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(14);
  try {
    const d = await apiFetch('/api/admin/spells');
    const items = d.items || d || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="14" style="text-align:center;padding:24px;color:var(--t3)">Brak czarów</td></tr>`; return; }
    const schoolBadge = s => ({magic_bolt:'badge-blue',mend_wounds:'badge-green',arcane_shield:'badge-slate',sleep:'badge-amber',burning_arc:'badge-red',drain_life:'badge-red',chain_lightning:'badge-blue',stone_skin:'badge-slate',fireball:'badge-red'}[s]||'badge-blue');
    tbody.innerHTML = items.map(sp => `<tr>
      <td class="detail-col td-mono" style="font-size:0.72rem">${_esc(sp.key)}</td>
      <td class="td-sticky td-name">${_esc(sp.label||sp.key)}</td>
      <td><span class="badge ${schoolBadge(sp.key)}">${_esc(sp.spell_type||'magiczny')}</span></td>
      <td class="td-mono" style="text-align:center">${sp.tier??'—'}</td>
      <td class="td-mono" style="text-align:center">${sp.mana_cost??'—'}</td>
      <td class="td-mono">${sp.damage_die||'—'}</td>
      <td class="td-mono">${sp.heal_die||'—'}</td>
      <td class="detail-col td-muted">${_esc(sp.effect_stat||'—')}</td>
      <td class="detail-col td-mono">${sp.range_m!=null?sp.range_m+' m':'—'}</td>
      <td class="detail-col td-mono">${sp.aoe_radius_m!=null?sp.aoe_radius_m+' m':'—'}</td>
      <td class="td-muted" style="font-size:0.75rem">${_esc(sp.target_zone||'single')}</td>
      <td class="detail-col td-muted" style="font-size:0.72rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${_esc(sp.description||'')}">${_esc((sp.description||'').slice(0,40)||'—')}</td>
      <td style="text-align:center">${sp.is_active ? '<span class="badge badge-green">●</span>' : '<span class="badge badge-slate">○</span>'}</td>
      <td class="td-actions">
        <button class="btn-icon" title="Edytuj" onclick="window._contentEditSpell('${_esc(sp.key)}')">✎</button>
        <button class="btn-icon danger" title="Usuń" onclick="window._contentDeleteSpell('${_esc(sp.key)}',this)">✕</button>
      </td>
    </tr>`).join('');
    const btn = document.querySelector('#content-tabs .stab[data-tab="spells"] span');
    if (btn) btn.textContent = `(${items.length})`;
    _restoreDetailsToggle('spells-table');
  } catch(e) { tbody.innerHTML = _errRow(14, e.message); }
}

function _loadTab(tab) {
  if (_loaded.has(tab)) return;
  const fns = { weapons:_loadWeapons, armor:_loadArmor, items:_loadItems, consumables:_loadConsumables, loot:_loadLootTables, spells:_loadSpells, affixes:_loadAffixes };
  const fn = fns[tab];
  if (!fn) return;
  _loaded.add(tab);
  fn().catch(() => _loaded.delete(tab));
}

// ── Loot modals ────────────────────────────────────────────────────────────────
async function _openLootEntriesModal(tableKey, tableLabel) {
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

async function _deleteLootTable(key, btn) {
  if (!confirm(`Usunąć tabelę łupów "${key}"?`)) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/loot-tables/${key}`, { method:'DELETE' });
    _loaded.delete('loot'); _loadLootTables();
    showToast('Usunięto.', 'success');
  } catch(e) { showToast('Błąd: '+e.message, 'error'); btn.disabled = false; }
}

// ── Spell modals ───────────────────────────────────────────────────────────────
function _openSpellForm(prefill, onSubmit) {
  const p = prefill || {};
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  const stype = p.spell_type || 'attack';
  const tzone = p.target_zone || 'any';
  const sopt = (v,lbl) => `<option value="${v}" ${stype===v?'selected':''}>${lbl}</option>`;
  const zopt = (v,lbl) => `<option value="${v}" ${tzone===v?'selected':''}>${lbl}</option>`;
  const STATS = ['STR','DEX','CON','INT','WIS','CHA'];
  overlay.innerHTML = `<div class="modal-box" style="width:520px">
    <div class="modal-head"><span class="modal-title">${p.key ? 'Edytuj czar' : 'Nowy czar'}</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body">
      <div class="form-row"><label class="form-label">Klucz *</label><input class="form-input" name="key" value="${_esc(p.key||'')}" placeholder="np. magic_bolt" ${p.key?'readonly':''}></div>
      <div class="form-row"><label class="form-label">Nazwa *</label><input class="form-input" name="label" value="${_esc(p.label||'')}"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div class="form-row"><label class="form-label">Typ czaru *</label><select class="form-input" name="spell_type">${sopt('attack','Atak (1 cel)')}${sopt('attack_aoe','Atak AoE')}${sopt('heal','Leczenie')}${sopt('defense','Obrona / tarcza')}${sopt('effect','Efekt / kondycja')}</select></div>
        <div class="form-row"><label class="form-label">Tier (1-5)</label><input class="form-input" name="tier" type="number" value="${p.tier??1}" min="1" max="5"></div>
        <div class="form-row"><label class="form-label">Koszt many (1-10)</label><input class="form-input" name="mana_cost" type="number" value="${p.mana_cost??1}" min="0" max="10"></div>
        <div class="form-row"><label class="form-label">Strefa celu</label><select class="form-input" name="target_zone">${zopt('any','Dowolna')}${zopt('self','Tylko siebie')}${zopt('engaged','Zwarcie')}${zopt('ranged','Dystans')}</select></div>
        <div class="form-row"><label class="form-label">Kość obrażeń</label><input class="form-input" name="damage_die" value="${_esc(p.damage_die||'')}" placeholder="np. 2d6"></div>
        <div class="form-row"><label class="form-label">Kość leczenia</label><input class="form-input" name="heal_die" value="${_esc(p.heal_die||'')}" placeholder="np. 2d6"></div>
        <div class="form-row"><label class="form-label">Stat obrony celu</label><select class="form-input" name="effect_stat"><option value="" ${!p.effect_stat?'selected':''}>—</option>${STATS.map(s=>`<option value="${s}" ${p.effect_stat===s?'selected':''}>${s}</option>`).join('')}</select></div>
        <div class="form-row"><label class="form-label">Klucz kondycji (FAZA S)</label><input class="form-input" name="effect_type" value="${_esc(p.effect_type||'')}" placeholder="np. slowed, stunned"></div>
        <div class="form-row"><label class="form-label">Czas trwania (rundy)</label><input class="form-input" name="effect_duration" type="number" value="${p.effect_duration??1}" min="1" max="10"></div>
        <div class="form-row" style="align-self:end;padding-bottom:4px;display:flex;gap:16px">
          <label style="display:flex;gap:8px;align-items:center;cursor:pointer"><input type="checkbox" name="aoe" ${p.aoe?'checked':''}> AoE</label>
          <label style="display:flex;gap:8px;align-items:center;cursor:pointer"><input type="checkbox" name="is_active" ${(p.is_active??true)?'checked':''}> Aktywny</label>
        </div>
      </div>
      <div class="form-row" style="margin-top:4px"><label class="form-label">Opis</label><textarea class="form-input" name="description" rows="2">${_esc(p.description||'')}</textarea></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div class="form-row"><label class="form-label">Ranga 2 (JSON)</label><textarea class="form-input" name="rank2_json" rows="2" placeholder='{"mana_cost":2,"damage_die":"2d8"}'>${_esc(p.rank2_json||'')}</textarea></div>
        <div class="form-row"><label class="form-label">Ranga 3 (JSON)</label><textarea class="form-input" name="rank3_json" rows="2" placeholder='{"mana_cost":1,"damage_die":"3d6"}'>${_esc(p.rank3_json||'')}</textarea></div>
      </div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" id="spell-save-btn">Zapisz</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector('#spell-save-btn').onclick = async () => {
    const val = n => overlay.querySelector(`[name="${n}"]`).value.trim();
    const key = val('key');
    const label = val('label');
    if (!key || !label) { showToast('Klucz i nazwa są wymagane.', 'error'); return; }
    const data = { key, label,
      spell_type: val('spell_type'),
      tier: parseInt(val('tier'),10)||1,
      mana_cost: parseInt(val('mana_cost'),10)||0,
      target_zone: val('target_zone'),
      damage_die: val('damage_die')||null,
      heal_die:   val('heal_die')||null,
      effect_stat: val('effect_stat')||null,
      effect_type: val('effect_type')||null,
      effect_duration: parseInt(val('effect_duration'),10)||1,
      aoe: overlay.querySelector('[name="aoe"]').checked ? 1 : 0,
      is_active: overlay.querySelector('[name="is_active"]').checked,
      rank2_json: val('rank2_json')||null,
      rank3_json: val('rank3_json')||null,
      description: val('description')||null,
    };
    overlay.remove();
    await onSubmit(data);
  };
}

async function _addSpell() {
  _openSpellForm(null, async data => {
    try {
      await apiFetch('/api/admin/spells', { method:'POST', body:JSON.stringify(data) });
      _loaded.delete('spells'); _loadSpells();
      showToast('Dodano czar.', 'success');
    } catch(e) { showToast('Błąd: '+e.message, 'error'); }
  });
}

async function _editSpell(key) {
  const all = await apiFetch('/api/admin/spells').then(d => d.items||d||[]);
  const row = all.find(s => s.key === key);
  if (!row) return;
  _openSpellForm(row, async data => {
    try {
      await apiFetch(`/api/admin/spells/${key}`, { method:'PATCH', body:JSON.stringify(data) });
      _loaded.delete('spells'); _loadSpells();
      showToast('Zapisano.', 'success');
    } catch(e) { showToast('Błąd: '+e.message, 'error'); }
  });
}

async function _deleteSpell(key, btn) {
  if (!confirm(`Usunąć czar "${key}"?`)) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/spells/${key}`, { method:'DELETE' });
    _loaded.delete('spells'); _loadSpells();
    showToast('Usunięto.', 'success');
  } catch(e) { showToast('Błąd: '+e.message, 'error'); btn.disabled = false; }
}

// ── Image modal ────────────────────────────────────────────────────────────────
async function _openItemImageModal(key, encData, tableType) {
  const item = typeof encData === 'string' ? JSON.parse(decodeURIComponent(encData)) : encData;
  const endpointMap = { weapon:'/api/admin/weapons', item:'/api/admin/items', consumable:'/api/admin/consumables', armor:'/api/admin/items' };
  const reloadMap = {
    weapon: () => { _loaded.delete('weapons'); _loadWeapons(); },
    item:   () => { _loaded.delete('items');   _loadItems(); },
    consumable: () => { _loaded.delete('consumables'); _loadConsumables(); },
    armor:  () => { _loaded.delete('armor');   _loadArmor(); },
  };
  const endpoint = endpointMap[tableType] || '/api/admin/items';
  const reload   = reloadMap[tableType] || (() => {});
  const m = document.createElement('div');
  m.id = 'item-img-modal';
  m.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center';
  m.innerHTML = `<div style="background:var(--surface,#1a1a27);border-radius:12px;width:min(520px,96vw);max-height:90vh;display:flex;flex-direction:column;overflow:hidden">
    <div style="padding:14px 16px;border-bottom:1px solid var(--border,#333);display:flex;align-items:center;gap:10px;flex-shrink:0">
      <strong>🖼 Obraz: ${_esc(item.label||key)}</strong>
      <button onclick="document.getElementById('item-img-modal').remove()" style="margin-left:auto;background:none;border:none;color:var(--t2);font-size:1.2rem;cursor:pointer">✕</button>
    </div>
    <div style="overflow-y:auto;flex:1;padding:16px;display:flex;flex-direction:column;gap:14px">
      <div>
        <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:4px">Prompt (EN)</label>
        <textarea id="ii-prompt" style="resize:none;width:100%;box-sizing:border-box;min-height:72px;max-height:200px;background:var(--bg,#111);border:1px solid var(--border,#333);border-radius:6px;padding:8px;color:var(--t1,#eee);font-size:0.82rem">${_esc(item.image_prompt||'')}</textarea>
      </div>
      <div id="ii-preview" style="min-height:60px;border-radius:8px;border:1px dashed var(--border,#333);display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:0.8rem">
        ${item.image_url ? `<img src="${_esc(item.image_url)}" style="max-width:100%;max-height:280px;border-radius:6px;object-fit:contain">` : 'Brak obrazu'}
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button id="ii-gen-btn" class="btn btn-primary" style="flex:1">⚡ Generuj</button>
        <button id="ii-ref-btn" class="btn btn-secondary" style="flex:1" disabled>🔄 Popraw</button>
      </div>
    </div>
    <div style="padding:12px 16px;border-top:1px solid var(--border,#333);display:flex;gap:8px;justify-content:flex-end;flex-shrink:0">
      <button id="ii-accept-btn" class="btn btn-success" disabled>✓ Akceptuj i zapisz</button>
      <button onclick="document.getElementById('item-img-modal').remove()" class="btn btn-secondary">Anuluj</button>
    </div>
  </div>`;
  document.body.appendChild(m);
  m.addEventListener('click', ev => { if (ev.target === m) m.remove(); });

  let _lastFilename = null, _lastUrl = null;

  m.querySelector('#ii-gen-btn').onclick = async () => {
    const btn = m.querySelector('#ii-gen-btn');
    btn.disabled = true; btn.textContent = '⏳ Generuję…';
    try {
      const prompt = m.querySelector('#ii-prompt').value.trim() || 'fantasy item, detailed illustration';
      const r = await apiFetch('/api/admin/images/generate', {method:'POST', body:JSON.stringify({prompt,width:512,height:512,steps:4})});
      _lastFilename = r.filename; _lastUrl = r.url;
      m.querySelector('#ii-preview').innerHTML = `<img src="${_esc(r.url)}" style="max-width:100%;max-height:280px;border-radius:6px;object-fit:contain">`;
      m.querySelector('#ii-ref-btn').disabled = false;
      m.querySelector('#ii-accept-btn').disabled = false;
    } catch(ex) { showToast(ex.message||'Błąd generowania', 'error'); }
    finally { btn.disabled = false; btn.textContent = '⚡ Generuj'; }
  };

  m.querySelector('#ii-accept-btn').onclick = async () => {
    if (!_lastFilename) return;
    const btn = m.querySelector('#ii-accept-btn');
    btn.disabled = true; btn.textContent = 'Zapisuję…';
    try {
      await apiFetch(`${endpoint}/${encodeURIComponent(key)}`, {method:'PATCH', body:JSON.stringify({image_url:_lastUrl, image_prompt:m.querySelector('#ii-prompt').value.trim()||null})});
      showToast('Obraz zapisany.', 'success');
      reload(); m.remove();
    } catch(ex) { showToast(ex.message||'Błąd zapisu', 'error'); btn.disabled=false; btn.textContent='✓ Akceptuj i zapisz'; }
  };
}

// ── Smart Entry ────────────────────────────────────────────────────────────────
const SE_TABLE_LABELS = {
  game_config_weapons:    'Broń',
  game_config_items:      'Przedmioty',
  game_config_consumables:'Konsumable',
  game_config_enemies:    'Wrogowie',
  game_config_armor:      'Zbroja',
  game_config_loot_tables:'Tabele Łupów',
  game_config_spells:     'Czary',
};
const SE_SUPPORTED = Object.keys(SE_TABLE_LABELS);

function _seGenId() { return 'se-' + Math.random().toString(36).slice(2,10); }
function _seSlugify(str) {
  const m = {'ą':'a','ć':'c','ę':'e','ł':'l','ń':'n','ó':'o','ś':'s','ź':'z','ż':'z','Ą':'a','Ć':'c','Ę':'e','Ł':'l','Ń':'n','Ó':'o','Ś':'s','Ź':'z','Ż':'z'};
  return str.split('').map(c=>m[c]||c).join('').toLowerCase().replace(/\s+/g,'_').replace(/[^a-z0-9_]/g,'').slice(0,50);
}

function _seEnsureOverlay() {
  if (_seOverlay) return _seOverlay;
  const el = document.createElement('div');
  el.id = 'smart-entry-overlay';
  el.className = 'smart-entry-overlay';
  el.innerHTML = `
    <div class="smart-entry-panel">
      <div class="smart-entry-header">
        <span class="smart-entry-title">🤖 Kreator AI</span>
        <select id="se-table-select" class="form-input" style="font-size:0.82rem;padding:4px 8px;margin-left:8px;flex:0 0 auto;width:auto">
          ${SE_SUPPORTED.map(t=>`<option value="${t}">${SE_TABLE_LABELS[t]}</option>`).join('')}
        </select>
        <span style="flex:1"></span>
        <button class="smart-entry-close" id="se-close-btn" type="button">✕ Zamknij</button>
      </div>
      <div class="smart-entry-body">
        <div class="smart-entry-chat-col">
          <div class="smart-entry-messages" id="se-messages"></div>
          <div class="se-mode-badge" id="se-mode-badge">✨ Tryb tworzenia</div>
          <div class="smart-entry-input-row" style="align-items:flex-end">
            <textarea id="se-input" class="form-input" placeholder="Opisz rekord który chcesz stworzyć…" rows="3" maxlength="1000" style="resize:vertical;min-height:60px;flex:1"></textarea>
            <button class="btn btn-primary" id="se-send-btn" type="button">Wyślij</button>
          </div>
        </div>
        <div class="smart-entry-form-col">
          <div class="se-form-toolbar">
            <select id="se-existing-select" class="form-input" style="flex:1;font-size:0.82rem">
              <option value="">+ Nowy rekord</option>
            </select>
            <button class="btn btn-secondary btn-sm" id="se-load-btn" type="button" style="font-size:0.78rem;white-space:nowrap;display:none">Załaduj</button>
          </div>
          <div id="se-form-fields" class="se-form-fields-panel"></div>
          <div class="se-form-footer">
            <button class="btn btn-primary" id="se-save-btn" type="button" disabled style="width:100%">✅ Zapisz rekord</button>
          </div>
        </div>
      </div>
    </div>`;
  document.body.appendChild(el);
  _seOverlay = el;
  el.querySelector('#se-close-btn').addEventListener('click', _closeSmartEntry);
  el.addEventListener('click', e => { if (e.target === el) _closeSmartEntry(); });
  el.querySelector('#se-send-btn').addEventListener('click', _seSend);
  el.querySelector('#se-input').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); _seSend(); } });
  el.querySelector('#se-table-select').addEventListener('change', e => _seSwitchTable(e.target.value));
  const handleSelectChange = async () => {
    const key = el.querySelector('#se-existing-select').value;
    if (!key) {
      _seDraft = {}; _seExistingKey = null;
      _seRenderFormValues(); _seUpdateSaveBtn(); _seUpdateModeBadge();
      el.querySelector('#se-messages').innerHTML = '';
      _seAppendMsg('Tryb nowego rekordu — opisz co chcesz stworzyć.', 'agent');
    } else {
      await _seLoadExisting(key);
    }
  };
  el.querySelector('#se-load-btn').addEventListener('click', handleSelectChange);
  el.querySelector('#se-existing-select').addEventListener('change', handleSelectChange);
  el.querySelector('#se-save-btn').addEventListener('click', _seSave);
  return el;
}

async function _seFetchSchema(table) {
  if (_seSchemaCache[table]) return _seSchemaCache[table];
  const d = await apiFetch(`/api/admin/smart-entry/schema?table=${table}`);
  _seSchemaCache[table] = d;
  return d;
}
async function _seFetchList(table) {
  try { const d = await apiFetch(`/api/admin/smart-entry/list?table=${table}`); return d.items || []; }
  catch { return []; }
}

async function _seSwitchTable(table) {
  _seCurrentTable = table;
  _seDraft = {}; _seExistingKey = null; _seSessionId = _seGenId();
  if (_seOverlay) {
    _seOverlay.querySelector('#se-messages').innerHTML = '';
    _seOverlay.querySelector('#se-form-fields').innerHTML = `<div style="padding:16px;color:var(--t3)">Ładowanie schematu…</div>`;
    _seAppendMsg(`Tabela: ${SE_TABLE_LABELS[table]||table}. Opisz rekord lub wybierz istniejący z listy po prawej.`, 'agent');
  }
  try {
    const schema = await _seFetchSchema(table);
    _seSchemaFields = schema.fields || [];
    _seRenderFormFields();
    _seUpdateSaveBtn(); _seUpdateModeBadge();
  } catch(e) { showToast('Błąd schematu: '+e.message, 'error'); }
  const items = await _seFetchList(table);
  if (_seOverlay) {
    const sel = _seOverlay.querySelector('#se-existing-select');
    sel.innerHTML = `<option value="">+ Nowy rekord</option>`;
    items.forEach(it => {
      const o = document.createElement('option');
      o.value = it.key;
      o.textContent = it.label ? `${it.label} (${it.key})` : it.key;
      sel.appendChild(o);
    });
  }
}

function _seRenderFormFields() {
  const container = _seOverlay.querySelector('#se-form-fields');
  container.innerHTML = '';
  _seSchemaFields.forEach(field => {
    const row = document.createElement('div');
    row.className = 'se-field-row' + (field.required ? ' required' : '');
    row.dataset.fieldKey = field.key;
    const lbl = document.createElement('div');
    lbl.className = 'se-field-label';
    lbl.textContent = field.label + (field.required ? ' *' : '');
    row.appendChild(lbl);
    const input = _seBuildInput(field);
    _seBindInputEvents(input, field);
    row.appendChild(input);
    container.appendChild(row);
  });
}

function _seBuildInput(field) {
  let el;
  if (field.type === 'single_choice' && field.options) {
    el = document.createElement('select');
    el.className = 'se-field-input';
    const empty = document.createElement('option');
    empty.value = ''; empty.textContent = '— wybierz —';
    el.appendChild(empty);
    field.options.forEach(opt => {
      const o = document.createElement('option');
      const val = typeof opt === 'object' ? (opt.label || opt.value) : opt;
      o.value = val; o.textContent = val;
      el.appendChild(o);
    });
  } else if (field.type === 'boolean') {
    const wrap = document.createElement('label');
    wrap.className = 'se-bool-wrap';
    el = document.createElement('input');
    el.type = 'checkbox'; el.className = 'se-field-checkbox';
    wrap.appendChild(el);
    wrap.dataset.fieldKey = field.key;
    return wrap;
  } else if (field.type === 'number') {
    el = document.createElement('input');
    el.type = 'number'; el.className = 'se-field-input';
    if (field.min !== undefined) el.min = field.min;
    if (field.max !== undefined) el.max = field.max;
  } else if (field.type === 'textarea') {
    el = document.createElement('textarea');
    el.className = 'se-field-textarea'; el.rows = 3;
    if (field.placeholder) el.placeholder = field.placeholder.slice(0,120);
  } else {
    el = document.createElement('input');
    el.type = 'text'; el.className = 'se-field-input';
    if (field.placeholder) el.placeholder = field.placeholder.slice(0,80);
  }
  el.dataset.fieldKey = field.key;
  return el;
}

function _seBindInputEvents(el, field) {
  const update = () => {
    _seDraft[field.key] = _seReadValue(field, el);
    _seUpdateFieldRow(field.key); _seUpdateSaveBtn();
    const r = _seOverlay?.querySelector(`.se-field-row[data-field-key="${field.key}"]`);
    if (r) r.classList.remove('se-field-changed--marked');
    if (field.key === 'label') {
      const keyField = _seSchemaFields.find(f => f.key === 'key');
      if (keyField && !_seDraft['key']) {
        const slug = _seSlugify(String(_seDraft['label']||''));
        const keyRow = _seOverlay.querySelector(`[data-field-key="key"]`);
        const keyInput = keyRow ? keyRow.querySelector('input,select') : null;
        if (keyInput) { keyInput.value = slug; _seDraft['key'] = slug; _seUpdateFieldRow('key'); }
      }
    }
  };
  if (el.tagName === 'LABEL') { el.querySelector('input')?.addEventListener('change', update); }
  else if (el.classList.contains('se-multi-choice')) { el.querySelectorAll('input').forEach(cb => cb.addEventListener('change', update)); }
  else { el.addEventListener('input', update); el.addEventListener('change', update); }
}

function _seReadValue(field, el) {
  if (field.type === 'boolean') { const cb = el.tagName==='LABEL'?el.querySelector('input'):el; return cb?.checked?1:0; }
  return el.value || '';
}

function _seRenderFormValues() {
  if (!_seOverlay) return;
  _seSchemaFields.forEach(field => {
    const row = _seOverlay.querySelector(`.se-field-row[data-field-key="${field.key}"]`);
    if (!row) return;
    const val = _seDraft[field.key] ?? '';
    const el = row.querySelector('input,select,textarea');
    if (!el) return;
    if (field.type === 'boolean') { const cb = row.querySelector('input[type=checkbox]'); if (cb) cb.checked = !!val; }
    else el.value = val;
    _seUpdateFieldRow(field.key);
  });
}

function _seUpdateFieldRow(key) {
  if (!_seOverlay) return;
  const row = _seOverlay.querySelector(`.se-field-row[data-field-key="${key}"]`);
  if (!row) return;
  const v = _seDraft[key];
  row.classList.toggle('filled', !!(v !== undefined && v !== '' && v !== null));
}

function _seUpdateSaveBtn() {
  const btn = _seOverlay?.querySelector('#se-save-btn');
  if (!btn) return;
  const allFilled = _seSchemaFields.filter(f=>f.required).every(f => { const v=_seDraft[f.key]; return v!==undefined&&v!==''&&v!==null; });
  btn.disabled = !allFilled;
  btn.textContent = _seExistingKey ? '✅ Zaktualizuj rekord' : '✅ Zapisz rekord';
}

async function _seLoadExisting(key) {
  try {
    const rec = await apiFetch(`/api/admin/smart-entry/record?table=${_seCurrentTable}&key=${encodeURIComponent(key)}`);
    _seDraft = { ...rec }; _seExistingKey = key; _seSessionId = _seGenId();
    _seRenderFormValues(); _seUpdateSaveBtn(); _seUpdateModeBadge();
    if (_seOverlay) {
      _seOverlay.querySelector('#se-messages').innerHTML = '';
      _seAppendMsg(`Załadowano: "${rec.label||key}". Opisz co chcesz zmienić.`, 'agent');
    }
  } catch(e) { showToast('Błąd ładowania: '+e.message, 'error'); }
}

function _seUpdateModeBadge() {
  const badge = _seOverlay?.querySelector('#se-mode-badge');
  const input = _seOverlay?.querySelector('#se-input');
  if (!badge) return;
  const hasContent = Object.values(_seDraft).some(v => v!==undefined&&v!==''&&v!==null);
  if (hasContent) {
    badge.textContent = '🔄 Tryb uzupełniania'; badge.classList.add('refine');
    if (input) input.placeholder = 'Opisz co chcesz zmienić…';
  } else {
    badge.textContent = '✨ Tryb tworzenia'; badge.classList.remove('refine');
    if (input) input.placeholder = 'Opisz rekord który chcesz stworzyć…';
  }
}

function _seFlashChanged(fields) {
  if (!_seOverlay) return;
  _seOverlay.querySelectorAll('.se-field-changed--marked').forEach(r => r.classList.remove('se-field-changed--marked'));
  (fields||[]).forEach(key => {
    const row = _seOverlay.querySelector(`.se-field-row[data-field-key="${key}"]`);
    if (!row) return;
    row.classList.add('se-field-changed','se-field-changed--marked');
    setTimeout(() => row.classList.remove('se-field-changed'), 2000);
  });
}

async function _seSend() {
  const input = _seOverlay.querySelector('#se-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  _seAppendMsg(text, 'user');
  const sendBtn = _seOverlay.querySelector('#se-send-btn');
  sendBtn.disabled = true;
  const typing = _seAppendMsg('…', 'agent');
  try {
    const r = await apiFetch('/api/admin/smart-entry/message', {
      method:'POST',
      body: JSON.stringify({ session_id:_seSessionId, table:_seCurrentTable, message:text, current_draft:_seDraft, target_key:_seExistingKey||null }),
    });
    typing.remove();
    if (r.reply) _seAppendMsg(r.reply, 'agent');
    if (r.draft && typeof r.draft==='object') {
      _seDraft = { ..._seDraft, ...Object.fromEntries(Object.entries(r.draft).filter(([,v])=>v!==null&&v!==undefined)) };
      _seRenderFormValues();
      _seFlashChanged(Array.isArray(r.changed_fields) ? r.changed_fields : []);
      _seUpdateSaveBtn(); _seUpdateModeBadge();
    }
  } catch(e) { typing.remove(); _seAppendMsg(`Błąd: ${e.message||JSON.stringify(e)}`, 'agent error'); }
  finally { sendBtn.disabled = false; }
}

async function _seSave() {
  const btn = _seOverlay.querySelector('#se-save-btn');
  btn.disabled = true; const orig = btn.textContent; btn.textContent = 'Zapisuję…';
  try {
    const r = await apiFetch('/api/admin/smart-entry/save', {
      method:'POST',
      body: JSON.stringify({ session_id:_seSessionId, draft:_seDraft, table:_seCurrentTable, target_key:_seExistingKey||null }),
    });
    const verb = r.mode==='update'?'Zaktualizowano':'Zapisano';
    showToast(`${verb}: ${r.key}`, 'success');
    _seAppendMsg(`✓ Rekord "${r.key}" ${r.mode==='update'?'zaktualizowany':'zapisany'}.`, 'agent success');
    window.dispatchEvent(new CustomEvent('smart-entry-saved', { detail:{ table:r.table||_seCurrentTable, key:r.key, mode:r.mode } }));
    _seDraft = {}; _seExistingKey = null; _seSessionId = _seGenId();
    if (_seOverlay) {
      _seOverlay.querySelector('#se-existing-select').value = '';
      _seRenderFormValues(); _seUpdateSaveBtn(); _seUpdateModeBadge();
    }
  } catch(e) {
    showToast(e.message||'Błąd zapisu.', 'error');
    btn.textContent = orig; _seUpdateSaveBtn();
  }
}

function _seAppendMsg(text, type) {
  if (!_seOverlay) return { remove: () => {} };
  const messages = _seOverlay.querySelector('#se-messages');
  const div = document.createElement('div');
  div.className = `chat-msg ${type}`;
  div.innerHTML = `<div class="chat-bubble">${_esc(text).replace(/\n/g,'<br>')}</div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

async function _openSmartEntry(table) {
  const overlay = _seEnsureOverlay();
  overlay.classList.add('visible');
  _seSessionId = _seGenId();
  const sel = overlay.querySelector('#se-table-select');
  const target = table || sel.value || SE_SUPPORTED[0];
  if (sel.value !== target) sel.value = target;
  await _seSwitchTable(target);
}

function _closeSmartEntry() { if (_seOverlay) _seOverlay.classList.remove('visible'); }

function _openSmartEntryForCurrentTab() {
  const activeTab = document.querySelector('#content-tabs .stab.active')?.dataset?.tab || 'weapons';
  const map = { weapons:'game_config_weapons', items:'game_config_items', consumables:'game_config_consumables', armor:'game_config_armor', loot:'game_config_loot_tables', spells:'game_config_spells' };
  const table = map[activeTab];
  if (!table) { showToast('Kreator AI nie obsługuje tej zakładki.', 'warn'); return; }
  _openSmartEntry(table);
}

// ── Section HTML ───────────────────────────────────────────────────────────────
function _sectionHtml() {
  return `<section class="section active" id="section-content">
  <div class="section-header">
    <div>
      <div class="section-heading">Zawartość</div>
    </div>
    <button class="btn btn-primary btn-sm" id="content-kreator-btn">🤖 Kreator AI</button>
  </div>
  <div class="card">
    <div class="section-tabs" id="content-tabs">
      <button class="stab active" data-tab="weapons">Broń <span style="font-size:0.7rem;color:var(--t3)"></span></button>
      <button class="stab" data-tab="armor">Zbroja <span style="font-size:0.7rem;color:var(--t3)"></span></button>
      <button class="stab" data-tab="items">Przedmioty <span style="font-size:0.7rem;color:var(--t3)"></span></button>
      <button class="stab" data-tab="consumables">Konsumable <span style="font-size:0.7rem;color:var(--t3)"></span></button>
      <button class="stab" data-tab="loot">Tabele łupów <span style="font-size:0.7rem;color:var(--t3)"></span></button>
      <button class="stab" data-tab="spells">Czary <span style="font-size:0.7rem;color:var(--t3)"></span></button>
      <button class="stab" data-tab="affixes">Afiksy <span style="font-size:0.7rem;color:var(--t3)"></span></button>
    </div>

    <!-- Broń -->
    <div class="stab-panel active" id="stab-weapons">
      <div class="toolbar">
        <div class="search-box"><span class="search-box-icon">🔍</span><input type="text" placeholder="Szukaj broni…" data-filter-for="weapons-table"></div>
        <div class="toolbar-right">
          <button class="btn-toggle-details" data-details-for="weapons-table">Szczegóły</button>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table" id="weapons-table">
          <thead><tr>
            <th class="detail-col"><div class="th-inner">Klucz</div></th>
            <th class="td-sticky"><div class="th-inner sorted">Nazwa</div></th>
            <th><div class="th-inner">Typ</div></th>
            <th><div class="th-inner">Obrażenia</div></th>
            <th><div class="th-inner">Zasięg</div></th>
            <th class="detail-col"><div class="th-inner">Slot</div></th>
            <th class="detail-col"><div class="th-inner">Oburącz</div></th>
            <th class="detail-col"><div class="th-inner">Finezja</div></th>
            <th><div class="th-inner">Waga</div></th>
            <th><div class="th-inner">Cena</div></th>
            <th><div class="th-inner">Rzadkość</div></th>
            <th class="detail-col"><div class="th-inner">Aktywny</div></th>
            <th class="detail-col"><div class="th-inner">🔒</div></th>
            <th class="detail-col"><div class="th-inner">Szablon</div></th>
            <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
          </tr></thead>
          <tbody><tr><td colspan="15" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- Zbroja -->
    <div class="stab-panel" id="stab-armor">
      <div class="toolbar">
        <div class="search-box"><span class="search-box-icon">🔍</span><input type="text" placeholder="Szukaj zbroi…" data-filter-for="armor-table"></div>
        <div class="toolbar-right"><button class="btn-toggle-details" data-details-for="armor-table">Szczegóły</button></div>
      </div>
      <div class="table-wrap">
        <table class="data-table" id="armor-table">
          <thead><tr>
            <th class="detail-col">Klucz</th><th class="td-sticky">Nazwa</th><th>Typ</th>
            <th>AC</th><th>Pokrycie</th><th class="detail-col">Okrycie</th>
            <th>Waga</th><th>Cena</th><th>Rzadkość</th>
            <th class="detail-col">Aktywny</th><th class="detail-col">🔒</th><th>Akcje</th>
          </tr></thead>
          <tbody><tr><td colspan="13" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- Przedmioty -->
    <div class="stab-panel" id="stab-items">
      <div class="toolbar">
        <div class="search-box"><span class="search-box-icon">🔍</span><input type="text" placeholder="Szukaj przedmiotów…" data-filter-for="items-table"></div>
        <div class="toolbar-right"><button class="btn-toggle-details" data-details-for="items-table">Szczegóły</button></div>
      </div>
      <div class="table-wrap">
        <table class="data-table" id="items-table">
          <thead><tr>
            <th class="detail-col">Klucz</th><th class="td-sticky">Nazwa</th><th>Typ</th>
            <th>Opis</th><th class="detail-col">Efekt JSON</th>
            <th>Waga</th><th>Cena</th><th>Rzadkość</th>
            <th class="detail-col">Źródło</th><th class="detail-col">Aktywny</th><th class="detail-col">🔒</th><th>Akcje</th>
          </tr></thead>
          <tbody><tr><td colspan="13" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- Konsumable -->
    <div class="stab-panel" id="stab-consumables">
      <div class="toolbar">
        <div class="search-box"><span class="search-box-icon">🔍</span><input type="text" placeholder="Szukaj konsumabli…" data-filter-for="consumables-table"></div>
        <div class="toolbar-right"><button class="btn-toggle-details" data-details-for="consumables-table">Szczegóły</button></div>
      </div>
      <div class="table-wrap">
        <table class="data-table" id="consumables-table">
          <thead><tr>
            <th class="detail-col">Klucz</th><th class="td-sticky">Nazwa</th><th>Efekt</th>
            <th>Formuła</th><th>Użycia</th><th class="detail-col">Ładunki</th>
            <th>Waga</th><th>Cena</th><th>Rzadkość</th>
            <th class="detail-col">Aktywny</th><th class="detail-col">🔒</th><th>Akcje</th>
          </tr></thead>
          <tbody><tr><td colspan="13" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- Tabele łupów -->
    <div class="stab-panel" id="stab-loot">
      <div class="toolbar">
        <div class="search-box"><span class="search-box-icon">🔍</span><input type="text" placeholder="Szukaj tabel łupów…" data-filter-for="loot-table"></div>
      </div>
      <div class="table-wrap">
        <table class="data-table" id="loot-table">
          <thead><tr>
            <th class="td-sticky">Klucz</th><th>Nazwa</th>
            <th style="width:80px">Złoto min</th><th style="width:80px">Złoto max</th>
            <th style="width:80px">Aktywna</th><th class="td-actions">Akcje</th>
          </tr></thead>
          <tbody><tr><td colspan="6" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- Czary -->
    <div class="stab-panel" id="stab-spells">
      <div class="toolbar">
        <div class="search-box"><span class="search-box-icon">🔍</span><input type="text" placeholder="Szukaj czarów…" data-filter-for="spells-table"></div>
        <button class="btn btn-primary btn-sm" id="add-spell-btn">+ Czar</button>
        <div class="toolbar-right"><button class="btn-toggle-details" data-details-for="spells-table">Szczegóły</button></div>
      </div>
      <div class="table-wrap">
        <table class="data-table" id="spells-table">
          <thead><tr>
            <th class="detail-col">Klucz</th><th class="td-sticky">Nazwa</th><th>Szkoła</th>
            <th style="width:60px">Tier</th><th style="width:80px">Koszt many</th>
            <th>Obrażenia</th><th>Leczenie</th>
            <th class="detail-col">Stat efektu</th><th class="detail-col">Zasięg</th><th class="detail-col">AoE</th>
            <th style="width:80px">Strefa</th><th class="detail-col">Opis</th>
            <th style="width:80px">Aktywny</th><th class="td-actions">Akcje</th>
          </tr></thead>
          <tbody><tr><td colspan="14" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- Afiksy (F3 #463) -->
    <div class="stab-panel" id="stab-affixes">
      <div class="toolbar">
        <div class="search-box"><span class="search-box-icon">🔍</span><input type="text" placeholder="Szukaj afiksów…" data-filter-for="affixes-table"></div>
        <button class="btn btn-primary btn-sm" id="add-affix-btn">+ Afiks</button>
      </div>
      <div class="table-wrap">
        <table class="data-table" id="affixes-table">
          <thead><tr>
            <th class="td-sticky">Klucz</th><th>Nazwa</th><th style="width:60px">Tier</th>
            <th>Typ</th><th>Efekty</th><th class="td-actions">Akcje</th>
          </tr></thead>
          <tbody><tr><td colspan="6" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>
</section>`;
}

// ── Smart-entry-saved handler ──────────────────────────────────────────────────
function _onSmartEntrySaved(e) {
  const t = e.detail?.table;
  if (t === 'game_config_weapons')      { _loaded.delete('weapons'); _loadWeapons(); }
  else if (t === 'game_config_items')   { _loaded.delete('items'); _loadItems(); _loaded.delete('armor'); _loadArmor(); }
  else if (t === 'game_config_consumables') { _loaded.delete('consumables'); _loadConsumables(); }
  else if (t === 'game_config_armor')   { _loaded.delete('armor'); _loadArmor(); }
  else if (t === 'game_config_loot_tables') { _loaded.delete('loot'); _loadLootTables(); }
}

// ── Entry point ────────────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = _sectionHtml();
  const root = panel.querySelector('#section-content');

  // Expose functions needed by inline onclick handlers in generated HTML
  window._contentImgModal  = (key, enc, type) => _openItemImageModal(key, enc, type);
  window._contentViewRec   = enc => _openItemViewModal(JSON.parse(decodeURIComponent(enc)));
  window._contentEditSpell = key => _editSpell(key);
  window._contentDeleteSpell = (key, btn) => _deleteSpell(key, btn);
  window._contentOpenLootEntries = (key, label) => _openLootEntriesModal(key, label);
  window._contentDeleteLootTable = (key, btn) => _deleteLootTable(key, btn);
  window._contentAffixEdit = enc => _openAffixModal(JSON.parse(decodeURIComponent(enc)));
  window._contentAffixDelete = (key, btn) => _deleteAffix(key, btn);

  // Tab switching
  root.querySelector('#content-tabs').addEventListener('click', e => {
    const btn = e.target.closest('.stab[data-tab]');
    if (!btn) return;
    const tab = btn.dataset.tab;
    root.querySelectorAll('#content-tabs .stab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    root.querySelectorAll('.stab-panel').forEach(p => p.classList.remove('active'));
    root.querySelector(`#stab-${tab}`)?.classList.add('active');
    _loadTab(tab);
  });

  // Details toggles
  root.querySelectorAll('[data-details-for]').forEach(btn => {
    btn.addEventListener('click', () => _toggleDetails(btn.dataset.detailsFor, btn));
  });

  // Search inputs
  root.querySelectorAll('[data-filter-for]').forEach(inp => {
    inp.addEventListener('input', () => _filterTable(inp.dataset.filterFor, inp.value));
  });

  // Spell add button
  root.querySelector('#add-spell-btn')?.addEventListener('click', _addSpell);

  // Affix add button (F3 #463)
  root.querySelector('#add-affix-btn')?.addEventListener('click', () => _openAffixModal(null));

  // Kreator AI button
  root.querySelector('#content-kreator-btn')?.addEventListener('click', _openSmartEntryForCurrentTab);

  // Smart-entry auto-refresh
  window.addEventListener('smart-entry-saved', _onSmartEntrySaved);

  // Load default tab
  _loadTab('weapons');
}
