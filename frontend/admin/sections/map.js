/**
 * FADM-P5 (#407) — sekcja Mapa: budowniczy świata (hex SVG), generowanie proceduralne,
 * lokacje (drzewo parent/child), teren, oczekujące lokacje + podmapy.
 * Port 1:1 z admin_panel_v3/index.html (martwy _loadPendingReview pominięty).
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

// ── State ──────────────────────────────────────────────────────────────────────
// Monolit używał _worldLoaded jako cache zakładek mapy — zachowane 1:1 (lokalne dla modułu).
const _worldLoaded = new Set();
// #590 — cache full records of pending/floating locations so the detail/edit
// modal can render every field without an extra round-trip.
const _locDetailReg = {};

// ── Helpers ────────────────────────────────────────────────────────────────────
function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
const _loading = cols => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">\u0141adowanie\u2026</td></tr>`;
const _errRow  = (cols, msg) => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--red);font-size:0.8rem">B\u0142\u0105d: ${_esc(msg)}</td></tr>`;
function _showToast(msg, type) { showToast(msg, type); }

function filterTableGeneric(input, tableId, nameClass) {
  const q = input.value.toLowerCase();
  document.querySelectorAll(`#${tableId} tbody tr`).forEach(row => {
    const name = row.querySelector(`.${nameClass}`)?.textContent.toLowerCase() || '';
    row.style.display = name.includes(q) ? '' : 'none';
  });
}

// ── Generic row edit/delete (locations-table) ───────────────────────────────────
const _ROW_REGISTRY = {
  'locations-table':   { endpoint:'/api/admin/locations',
      // Delete/patch live on the /api/locations router, NOT /api/admin/locations
      // (which has no bare {key} route → the old value 404'd, "Błąd usuwania").
      deleteEndpoint:'/api/locations', patchEndpoint:'/api/locations/admin/locations',
      deleteForce:true,   // purge trash even when a parent still has sub-locations
      keyField:'key', fields:[
      {name:'label',         label:'Nazwa',  type:'text'},
      {name:'location_type', label:'Typ',    type:'text'},
      {name:'biome',         label:'Biom',   type:'text'},
      {name:'tier',          label:'Tier',   type:'number'},
      {name:'description',   label:'Opis',   type:'textarea'},
      {name:'image_url',     label:'Obraz',  type:'image-preview'},
    ], reload: () => { _worldLoaded.delete('locations'); _loadLocations(); } },
};

// ── mechPatchEdit (inline label edit) ──────────────────────────────────────────
  async function mechPatchEdit(cell, patchUrl, field) {
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
    input.addEventListener('keydown', e => { if(e.key==='Enter'){e.preventDefault();save();} if(e.key==='Escape'){cell.textContent=orig;} });
  }

// ── Generic edit/delete modal ──────────────────────────────────────────────────
  let _genModalEjData = null;
  function _openGenericEjBuilder() {
    openEffectBuilder(_genModalEjData, 'standard', 'Effect JSON', function(data) {
      _genModalEjData = data;
      const p = document.getElementById('gen-ej-preview');
      if (p) p.textContent = data ? JSON.stringify(data, null, 2) : '— brak efektu —';
    });
  }

  function _openGenericEditModal(cfg, record) {
    const key = record[cfg.keyField];
    // Init effect-builder state from record
    _genModalEjData = null;
    const ejField = cfg.fields.find(f => f.type === 'effect-builder');
    if (ejField) {
      const raw = record[ejField.name];
      try { _genModalEjData = raw ? JSON.parse(raw) : null; } catch(e) {}
    }
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
      if (f.type === 'image-preview') {
        if (!v) return `<div class="form-row"><label class="form-label">${_esc(f.label)}</label><div style="font-size:0.75rem;color:var(--t3);padding:6px 0">Brak obrazu</div></div>`;
        return `<div class="form-row"><label class="form-label">${_esc(f.label)}</label><div style="margin-top:4px"><img src="${_esc(v)}" style="max-width:100%;max-height:200px;border-radius:var(--r);border:1px solid var(--border);object-fit:contain;display:block"><div style="font-size:0.68rem;color:var(--t3);margin-top:4px;word-break:break-all">${_esc(v)}</div></div></div>`;
      }
      if (f.type === 'effect-builder') {
        let ejData = null;
        try { ejData = v ? JSON.parse(v) : null; } catch(e) {}
        const preview = ejData ? JSON.stringify(ejData, null, 2) : '— brak efektu —';
        return `<div class="form-row"><label class="form-label" style="display:flex;justify-content:space-between;align-items:center"><span>${_esc(f.label)}</span><button type="button" class="btn btn-secondary" style="font-size:0.78rem;padding:3px 10px" onclick="_openGenericEjBuilder()">Edytuj efekty</button></label><div id="gen-ej-preview" style="background:#111;border:1px solid #2a2a2a;border-radius:4px;padding:8px;font-size:0.72rem;color:#555;font-family:monospace;word-break:break-all;cursor:pointer;white-space:pre-wrap;max-height:80px;overflow:auto" onclick="_openGenericEjBuilder()">${_esc(preview)}</div></div>`;
      }
      const step = f.step ? ` step="${f.step}"` : '';
      return `<div class="form-row"><label class="form-label">${_esc(f.label)}</label><input class="form-input" name="${f.name}" type="${f.type}" value="${_esc(v??'')}"${step}></div>`;
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
        if (f.type === 'image-preview') continue;
        if (f.type === 'effect-builder') { payload[f.name] = _genModalEjData ? JSON.stringify(_genModalEjData) : null; continue; }
        const el = overlay.querySelector(`[name="${f.name}"]`);
        if (!el) continue;
        if (f.type === 'checkbox') payload[f.name] = el.checked;
        else if (f.type === 'number') {
          const n = parseFloat(el.value);
          payload[f.name] = isNaN(n) ? null : n;
        } else payload[f.name] = el.value.trim() || null;
      }
      try {
        await apiFetch(`${cfg.patchEndpoint || cfg.endpoint}/${encodeURIComponent(key)}`, { method:'PATCH', body: JSON.stringify(payload) });
        _showToast('Zapisano.', 'success');
        overlay.remove();
        cfg.reload();
      } catch(e) { _showToast(e.message || 'Błąd zapisu.', 'error'); }
    };
  }

  async function _genericDelete(cfg, record) {
    const key = record[cfg.keyField];
    const label = record.label || record.key || key;
    if (!confirm(`Usunąć "${label}"?`)) return;
    try {
      const base = cfg.deleteEndpoint || cfg.endpoint;
      const qs = cfg.deleteForce ? '?force=true' : '';
      await apiFetch(`${base}/${encodeURIComponent(key)}${qs}`, { method:'DELETE' });
      _showToast('Usunięto.', 'success');
      cfg.reload();
    } catch(e) { _showToast(e.message || 'Błąd usuwania.', 'error'); }
  }

// ── Duplikaty lokacji (#1409) ───────────────────────────────────────────────
  const _DUP_API = '/api/admin/location-duplicates';
  let _locDupData = null;

  async function _loadLocDupBadge() {
    try {
      const { count } = await apiFetch(`${_DUP_API}/count`);
      const b = document.getElementById('loc-dup-badge');
      if (b) { b.textContent = count; b.style.display = count > 0 ? '' : 'none'; }
    } catch { /* badge is best-effort */ }
  }

  const _GARBAGE_LABELS = {
    test:     ['🧪 Testowe / smoke', 'Klucz z prefiksem test_, znacznikiem [TEST] lub sufiksem czasu.'],
    orphaned: ['🔗 Osierocone', 'Rodzic (parent) nie istnieje lub jest nieaktywny.'],
    floating: ['🎈 Bez hexa i kampanii', 'Aktywna lokacja bez hexa, rodzica i kampanii — wisi w próżni.'],
    inactive: ['💤 Nieaktywne', 'Już miękko usunięte (is_active=0), wciąż zalegają w bazie.'],
  };

  function _dupRecordRow(rec, gi) {
    const locked = rec.hex_locked;
    const removable = !locked;
    return `<label class="loc-dup-rec" style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:5px;background:var(--bg2,#141414)">
      <input type="radio" name="dup-keep-${gi}" value="${_esc(rec.key)}" ${!locked ? '' : 'checked'} title="Zachowaj tę lokację">
      <input type="checkbox" class="loc-dup-rm" data-key="${_esc(rec.key)}" ${removable ? 'checked' : 'disabled'} title="${removable ? 'Usuń przy scalaniu' : 'Zablokowana — hex jej używa'}">
      <span style="flex:1;font-size:0.82rem;color:var(--text)">${_esc(rec.label || '—')}
        <code style="font-size:0.68rem;color:var(--t3)">${_esc(rec.key)}</code>
        ${locked ? '<span title="Hex świata używa tej lokacji — nie zostanie usunięta" style="color:#e0b040">🔒 hex</span>' : ''}
        ${!rec.is_active ? '<span style="color:var(--t3);font-size:0.7rem">(nieaktywna)</span>' : ''}
      </span>
    </label>`;
  }

  function _renderLocDup() {
    const root = document.getElementById('loc-dup-root');
    if (!root || !_locDupData) return;
    const { groups, garbage, excess, garbage_total } = _locDupData;

    const groupsHtml = groups.length ? groups.map((g, gi) => `
      <div class="card loc-dup-group" data-gi="${gi}" style="padding:10px;margin-bottom:8px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span style="font-size:0.82rem;font-weight:600">${g.match === 'exact' ? '🟰 Dokładne' : '≈ Podobne'}: „${_esc(g.label)}" <span style="color:var(--t3);font-weight:400">(${g.records.length})</span></span>
          <div style="display:flex;gap:6px">
            <button class="btn btn-sm btn-primary" data-dup-action="merge" data-gi="${gi}">Scal</button>
            <button class="btn btn-sm btn-secondary" data-dup-action="ignore" data-gi="${gi}" title="To nie duplikat — schowaj grupę">🚫 Nie duplikat</button>
          </div>
        </div>
        <div style="font-size:0.68rem;color:var(--t3);margin-bottom:4px">⦿ = zachowaj · ☑ = usuń (dzieci i sesje przepięte na zachowaną)</div>
        <div style="display:flex;flex-direction:column;gap:3px">${g.records.map(r => _dupRecordRow(r, gi)).join('')}</div>
      </div>`).join('') : '<div style="color:var(--t3);font-size:0.82rem;padding:8px">Brak duplikatów ✓</div>';

    const garbageHtml = Object.entries(garbage).map(([kind, rows]) => {
      const [title, hint] = _GARBAGE_LABELS[kind];
      if (!rows.length) return '';
      const list = rows.map(r => `
        <div style="display:flex;align-items:center;gap:8px;padding:4px 8px;border-radius:4px;background:var(--bg2,#141414)">
          <span style="flex:1;font-size:0.8rem">${_esc(r.label || '—')} <code style="font-size:0.66rem;color:var(--t3)">${_esc(r.key)}</code>
            ${r.hex_locked ? '<span title="Hex świata używa tej lokacji" style="color:#e0b040">🔒</span>' : ''}</span>
          <button class="btn btn-sm ${r.hex_locked ? 'btn-secondary' : ''}" style="${r.hex_locked ? 'opacity:0.5' : 'background:#7f1d1d;color:#fca5a5'}" data-dup-action="del" data-key="${_esc(r.key)}" ${r.hex_locked ? 'disabled title="Hex jej używa — odepnij w Budowniczym najpierw"' : ''}>Usuń</button>
        </div>`).join('');
      return `<div class="card" style="padding:10px;margin-bottom:8px">
        <div style="font-size:0.82rem;font-weight:600;margin-bottom:2px">${title} <span style="color:var(--t3);font-weight:400">(${rows.length})</span></div>
        <div style="font-size:0.68rem;color:var(--t3);margin-bottom:6px">${hint}</div>
        <div style="display:flex;flex-direction:column;gap:3px">${list}</div>
      </div>`;
    }).join('') || '<div style="color:var(--t3);font-size:0.82rem;padding:8px">Brak śmieci ✓</div>';

    root.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <div style="font-size:0.82rem;color:var(--t2)"><strong>${excess}</strong> nadmiarowych duplikatów · <strong>${garbage_total}</strong> śmieci</div>
        <button class="btn btn-sm btn-secondary" data-dup-action="refresh">↻ Odśwież</button>
      </div>
      <div style="font-size:0.78rem;font-weight:700;color:var(--t3);letter-spacing:0.05em;margin:4px 0 8px">DUPLIKATY (ta sama nazwa)</div>
      ${groupsHtml}
      <div style="font-size:0.78rem;font-weight:700;color:var(--t3);letter-spacing:0.05em;margin:16px 0 8px">ŚMIECI</div>
      ${garbageHtml}`;
  }

  async function _loadLocDuplicates() {
    const root = document.getElementById('loc-dup-root');
    if (root) root.innerHTML = '<div style="padding:28px;text-align:center;color:var(--t3);font-size:0.8rem">Skanuję lokacje…</div>';
    try {
      _locDupData = await apiFetch(_DUP_API);
      _renderLocDup();
      _loadLocDupBadge();
    } catch (e) {
      if (root) root.innerHTML = `<div style="padding:24px;text-align:center;color:var(--red);font-size:0.8rem">Błąd: ${_esc(e.message)}</div>`;
    }
  }

  async function _locDupMerge(gi) {
    const group = _locDupData?.groups?.[gi];
    if (!group) return;
    const card = document.querySelector(`.loc-dup-group[data-gi="${gi}"]`);
    const keepEl = card?.querySelector(`input[name="dup-keep-${gi}"]:checked`);
    if (!keepEl) { _showToast('Wybierz lokację do zachowania (⦿).', 'warn'); return; }
    const keep = keepEl.value;
    const removeKeys = [...card.querySelectorAll('.loc-dup-rm:checked')]
      .map(c => c.dataset.key).filter(k => k !== keep);
    if (!removeKeys.length) { _showToast('Zaznacz przynajmniej jedną lokację do usunięcia (☑).', 'warn'); return; }
    if (!confirm(`Scalić ${removeKeys.length} lokacji w „${keep}"? Dzieci i sesje zostaną przepięte, duplikaty usunięte.`)) return;
    try {
      const res = await apiFetch(`${_DUP_API}/merge`, { method:'POST', body: JSON.stringify({ keep_key: keep, remove_keys: removeKeys }) });
      const skipped = res.skipped_hex_locked?.length;
      _showToast(`Scalono ${res.deleted.length}.` + (skipped ? ` ${skipped} pominięto (hex).` : ''), 'success');
      _loadLocDuplicates();
    } catch (e) { _showToast(e.message || 'Błąd scalania.', 'error'); }
  }

  async function _locDupIgnore(gi) {
    const group = _locDupData?.groups?.[gi];
    if (!group) return;
    const keys = group.records.map(r => r.key);
    try {
      await apiFetch(`${_DUP_API}/ignore`, { method:'POST', body: JSON.stringify({ keys }) });
      _showToast('Oznaczono jako „nie duplikat".', 'success');
      _loadLocDuplicates();
    } catch (e) { _showToast(e.message || 'Błąd.', 'error'); }
  }

  async function _locDupDelete(key) {
    if (!confirm(`Usunąć lokację „${key}"?`)) return;
    try {
      await apiFetch(`/api/locations/${encodeURIComponent(key)}?force=true`, { method:'DELETE' });
      _showToast('Usunięto.', 'success');
      _loadLocDuplicates();
    } catch (e) { _showToast(e.message || 'Błąd usuwania.', 'error'); }
  }

  function _wireLocDup(panel) {
    const root = panel.querySelector('#wtab-duplicates');
    if (!root || root._wired) return;
    root._wired = true;
    root.addEventListener('click', e => {
      const btn = e.target.closest('[data-dup-action]');
      if (!btn) return;
      const act = btn.dataset.dupAction;
      if (act === 'refresh') return _loadLocDuplicates();
      if (act === 'merge')   return _locDupMerge(+btn.dataset.gi);
      if (act === 'ignore')  return _locDupIgnore(+btn.dataset.gi);
      if (act === 'del')     return _locDupDelete(btn.dataset.key);
    });
  }

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
      if (delBtn) {
        if (cfg.noDelete) { _showToast('Usuwanie niedostępne dla tego typu.', 'warn'); return; }
        _genericDelete(cfg, rec);
      }
    });
  }

// ── Locations filter ───────────────────────────────────────────────────────────
  function filterLocationsType(chip, type) {
    document.querySelectorAll('#locations-type-filter .chip').forEach(c => c.classList.remove('on'));
    chip.classList.add('on');
    document.querySelectorAll('#locations-table tbody tr').forEach(row => {
      if (!type) { row.style.display = ''; return; }
      const badge = row.querySelector('.badge')?.textContent?.toLowerCase() || '';
      row.style.display = badge.includes(type) ? '' : 'none';
    });
  }

  function filterLocationsRegion(select) {
    const region = select.value;
    document.querySelectorAll('#locations-table tbody tr').forEach(row => {
      if (!region) { row.style.display = ''; return; }
      const cell = row.querySelector('.td-region')?.dataset?.region || '';
      row.style.display = cell === region ? '' : 'none';
    });
  }

// ── Tab dispatcher + hexmap generate ───────────────────────────────────────────
  function _loadMapTab(tab) {
    if (_worldLoaded.has(tab)) return Promise.resolve();
    const fn = { locations:_loadLocations, review:_loadPendingLocations, terrain:_loadTerrain, builder:_loadBuilder, generate:_hexmapLoadStats, floating:_loadFloating, duplicates:_loadLocDuplicates }[tab];
    if (!fn) return Promise.resolve();
    _worldLoaded.add(tab);
    return fn().catch(err => { _worldLoaded.delete(tab); console.warn('Map tab failed:', tab, err.message); });
  }

  // ── Ustawienia mapy (#1482: generator świata i masowe czyszczenie usunięte) ──
  async function _hexmapLoadStats() {
    try {
      const d = await apiFetch('/api/admin/world/map');
      const hexes = d.hexes || [];
      const el = document.getElementById('hexmap-total');
      if (el) el.textContent = hexes.length;
      const counts = {};
      hexes.forEach(h => { counts[h.hex_type] = (counts[h.hex_type]||0)+1; });
      const card = document.getElementById('hexmap-types-card');
      if (card) {
        const top5 = Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,5);
        card.innerHTML = top5.map(([t,n])=>`<span style="font-size:0.78rem;color:var(--t2)">${_esc(t)}: <strong>${n}</strong></span>`).join(' · ') || '<span style="color:var(--t3);font-size:0.78rem">Brak heksów</span>';
      }
    } catch(_e) {}
    // PM7 (#1226): load global knowledge-bubble radius into the FOW card.
    _loadKnowledgeBubble();
  }

  // ── PM7 (#1226): globalny promień bąbla wiedzy (FOW) ──────────────────────────
  async function _loadKnowledgeBubble() {
    const inp = document.getElementById('kbr-radius');
    if (!inp) return;
    try {
      const d = await apiFetch('/api/admin/settings/knowledge-bubble-radius');
      if (d && d.radius != null) inp.value = d.radius;
    } catch(_e) {}
  }

  async function saveKnowledgeBubble() {
    const inp = document.getElementById('kbr-radius');
    if (!inp) return;
    const radius = parseInt(inp.value, 10);
    if (isNaN(radius) || radius < 0) { _showToast('Podaj poprawny promień (≥0).', 'error'); return; }
    const btn = document.getElementById('kbr-save-btn');
    if (btn) btn.disabled = true;
    try {
      const d = await apiFetch('/api/admin/settings/knowledge-bubble-radius', {
        method: 'PUT', body: JSON.stringify({ radius }),
      });
      inp.value = d.radius;
      _showToast(`Zasięg wiedzy = ${d.radius} heksów.`, 'success');
    } catch(e) { _showToast('Błąd: ' + e.message, 'error'); }
    finally { if (btn) btn.disabled = false; }
  }

// ── Locations tree + NPC assign ────────────────────────────────────────────────
  // Phase 5.2 — Lokacje with parent/child accordion tree
  let _locTreeExpanded = new Set();
  let _locByParent = {};

  function _renderLocTree() {
    const tbody = document.querySelector('#locations-table tbody');
    if (!tbody) return;
    const locBadge = t => { const m={dungeon:'badge-red',city:'badge-blue',town:'badge-blue',forest:'badge-green',wilderness:'badge-green',ruin:'badge-amber'}; return `<span class="badge ${m[t]||'badge-slate'}">${_esc(t||'—')}</span>`; };
    const rowHtml = (l, depth) => {
      const enc = encodeURIComponent(JSON.stringify(l));
      const children = _locByParent[l.key] || [];
      const hasKids = children.length > 0;
      const expanded = _locTreeExpanded.has(l.key);
      const caret = hasKids ? `<button class="loc-tree-toggle" data-loc-key="${_esc(l.key)}" style="background:none;border:none;cursor:pointer;font-size:0.85rem;color:var(--t2);padding:0 4px;width:18px">${expanded?'▼':'▶'}</button>` : '<span style="display:inline-block;width:18px"></span>';
      const indent = depth * 18;
      const childCount = hasKids ? ` <span style="color:var(--t3);font-size:0.72rem">(${children.length})</span>` : '';
      const regionLabel = l.region ? _esc(l.region) : '<span class="td-muted">(brak)</span>';
      return `<tr data-key="${_esc(l.key)}" data-rjson="${enc}">
        <td class="col-check"><input type="checkbox" class="loc-check" data-key="${_esc(l.key)}"></td>
        <td class="td-sticky td-name"><span style="display:inline-block;width:${indent}px"></span>${caret}<span style="font-weight:${depth===0?'600':'normal'}">${_esc(l.label||l.key)}</span>${childCount}</td>
        <td>${locBadge(l.location_type)}</td>
        <td class="td-region" data-region="${_esc(l.region||'')}" style="font-size:0.78rem;color:var(--t2)">${regionLabel}</td>
        <td class="td-muted">${_esc(l.biome||l.location_subtype||'—')}</td>
        <td class="td-mono">${l.tier||'—'}</td>
        <td>${l.safe_for_rest ? '<span class="badge badge-green">🛏 Safe</span>' : '<span class="td-muted">—</span>'}</td>
        <td class="td-actions"><button class="btn btn-sm btn-secondary" style="font-size:0.7rem;padding:2px 6px;margin-right:4px" title="Przypisz NPC/Wrogów" onclick="openLocNpcModal('${_esc(l.key)}')">👤</button><button class="btn btn-sm btn-secondary" style="font-size:0.7rem;padding:2px 6px;margin-right:4px" title="Generuj obraz" onclick="openLocImageModal('${_esc(l.key)}','${enc}')">${l.image_url ? '🖼' : '🎨'}</button><button class="btn-icon" title="Edytuj">✎</button> <button class="btn-icon danger" title="Usuń">✕</button></td>
      </tr>`;
    };
    const renderBranch = (parentKey, depth) => {
      const branch = _locByParent[parentKey] || [];
      let html = '';
      for (const l of branch) {
        html += rowHtml(l, depth);
        if (_locTreeExpanded.has(l.key)) html += renderBranch(l.key, depth+1);
      }
      return html;
    };
    tbody.innerHTML = renderBranch('', 0) || `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--t3)">Brak lokacji</td></tr>`;
    if (!tbody._locWired) {
      tbody._locWired = true;
      tbody.addEventListener('click', e => {
        const btn = e.target.closest('.loc-tree-toggle');
        if (!btn) return;
        e.stopPropagation();
        const k = btn.dataset.locKey;
        if (_locTreeExpanded.has(k)) _locTreeExpanded.delete(k); else _locTreeExpanded.add(k);
        _renderLocTree();
      });
    }
  }

  async function _loadLocations() {
    const tbody = document.querySelector('#locations-table tbody');
    if (!tbody) return;
    tbody.innerHTML = _loading(8);
    try {
      const d = await apiFetch('/api/locations/admin/locations?active_only=1');
      const items = Array.isArray(d) ? d : (d.items||[]);
      _locByParent = {};
      items.forEach(l => {
        const p = l.parent_key || '';
        (_locByParent[p] = _locByParent[p] || []).push(l);
      });
      _renderLocTree();
      _wireRowActions('locations-table');
      _wireLocSelection();
    } catch(e) { tbody.innerHTML = _errRow(8, e.message); }
  }

  // ── Masowe usuwanie zaznaczonych lokacji ───────────────────────────────────
  function _checkedLocKeys() {
    return [...document.querySelectorAll('#locations-table .loc-check:checked')].map(c => c.dataset.key);
  }
  function _updateLocSel() {
    const n = _checkedLocKeys().length;
    const btn = document.getElementById('loc-bulk-del');
    const cnt = document.getElementById('loc-sel-count');
    if (cnt) cnt.textContent = n;
    if (btn) btn.style.display = n > 0 ? '' : 'none';
    const all = document.getElementById('loc-check-all');
    if (all) {
      const boxes = document.querySelectorAll('#locations-table .loc-check');
      all.checked = boxes.length > 0 && n === boxes.length;
      all.indeterminate = n > 0 && n < boxes.length;
    }
  }
  function _wireLocSelection() {
    const table = document.getElementById('locations-table');
    if (table && !table._selWired) {
      table._selWired = true;
      // Delegacja — przeżywa re-render tbody (rozwijanie drzewa).
      table.addEventListener('change', e => {
        if (e.target.classList.contains('loc-check')) _updateLocSel();
      });
    }
    const all = document.getElementById('loc-check-all');
    if (all && !all._wired) {
      all._wired = true;
      all.addEventListener('change', () => {
        document.querySelectorAll('#locations-table .loc-check').forEach(c => { c.checked = all.checked; });
        _updateLocSel();
      });
    }
    const btn = document.getElementById('loc-bulk-del');
    if (btn && !btn._wired) { btn._wired = true; btn.addEventListener('click', _locBulkDelete); }
    _updateLocSel();
  }
  async function _locBulkDelete() {
    const keys = _checkedLocKeys();
    if (!keys.length) return;
    if (!confirm(`Usunąć ${keys.length} zaznaczonych lokacji? Podlokacje zostaną usunięte razem z rodzicem.`)) return;
    const btn = document.getElementById('loc-bulk-del');
    if (btn) { btn.disabled = true; btn.style.opacity = '0.6'; }
    let ok = 0; const failed = [];
    // Sekwencyjnie — brak endpointu bulk; force=true czyści rodziców z podlokacjami.
    for (const key of keys) {
      try {
        await apiFetch(`/api/locations/${encodeURIComponent(key)}?force=true`, { method: 'DELETE' });
        ok++;
      } catch (e) { failed.push(key); }
    }
    if (btn) { btn.disabled = false; btn.style.opacity = ''; }
    _showToast(`Usunięto ${ok}/${keys.length}.` + (failed.length ? ` Nieudane: ${failed.length}.` : ''), failed.length ? 'warn' : 'success');
    _worldLoaded.delete('locations');
    _loadLocations();
  }

  // U28 — Floating lokacje
  async function _loadFloating() {
    const tbody = document.querySelector('#floating-locations-table tbody');
    if (!tbody) return;
    tbody.innerHTML = _loading(7);
    try {
      const items = await apiFetch('/api/admin/locations/floating');
      if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:28px;color:var(--t3)">Brak floating lokacji — wszystkie zakotwiczone ✓</td></tr>';
        return;
      }
      items.forEach(loc => { _locDetailReg[loc.key] = loc; });  // #590
      tbody.innerHTML = items.map(loc => `
        <tr data-key="${_esc(loc.key)}">
          <td><code style="font-size:0.75rem">${_esc(loc.key)}</code></td>
          <td>${_esc(loc.label || '—')}</td>
          <td>${_esc(loc.location_subtype || loc.location_type || '—')}</td>
          <td style="font-size:0.78rem;color:var(--t2)">${loc.region ? _esc(loc.region) : '<span class="td-muted">(brak)</span>'}</td>
          <td>${(loc.terrain_tags||[]).map(t => `<span class="chip on" style="font-size:0.7rem;padding:2px 6px">${_esc(t)}</span>`).join(' ')}</td>
          <td>${_esc(loc.biome || '—')}</td>
          <td style="white-space:nowrap">
            <button class="btn btn-sm" onclick="openLocDetailModal('${_esc(loc.key)}','floating')">👁 Podgląd</button>
            <button class="btn btn-sm btn-secondary" onclick="openPlaceModal('${_esc(loc.key)}')">⚓ Osadź</button>
          </td>
        </tr>`).join('');
    } catch(e) { tbody.innerHTML = _errRow(7, e.message); }
  }

  window.openPlaceModal = function(locKey) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `<div class="modal-box" style="max-width:400px">
      <div class="modal-head"><span>⚓ Osadź lokację na hexie</span><button id="pm-x">✕</button></div>
      <div style="padding:16px;display:flex;flex-direction:column;gap:12px">
        <div style="font-size:0.82rem;color:var(--t2)">Lokacja: <code>${_esc(locKey)}</code></div>
        <label style="font-size:0.8rem;font-weight:600">Współrzędna Q (kolumna)</label>
        <input id="pm-q" type="number" class="field-input" placeholder="np. 2" value="0">
        <label style="font-size:0.8rem;font-weight:600">Współrzędna R (wiersz)</label>
        <input id="pm-r" type="number" class="field-input" placeholder="np. 3" value="0">
      </div>
      <div class="modal-foot">
        <button class="btn btn-secondary" id="pm-cancel">Anuluj</button>
        <button class="btn btn-primary" id="pm-save">⚓ Osadź</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#pm-x').onclick = () => overlay.remove();
    overlay.querySelector('#pm-cancel').onclick = () => overlay.remove();
    overlay.querySelector('#pm-save').onclick = async () => {
      const q = parseInt(overlay.querySelector('#pm-q').value, 10);
      const r = parseInt(overlay.querySelector('#pm-r').value, 10);
      try {
        await apiFetch(`/api/admin/locations/${encodeURIComponent(locKey)}/place`, {
          method: 'POST', body: JSON.stringify({q, r}),
        });
        _showToast(`Lokacja ${locKey} osadzona na (${q},${r})`, 'success');
        overlay.remove();
        _worldLoaded.delete('floating');
        _loadFloating();
      } catch(e) { _showToast(e.message || 'Błąd osadzania', 'error'); }
    };
  };

  // #590 — podgląd/edycja pełnych pól wpisu (pending lub floating) przed decyzją
  window.openLocDetailModal = function(locKey, source) {
    const loc = _locDetailReg[locKey] || { key: locKey };
    const tagsStr = Array.isArray(loc.terrain_tags) ? loc.terrain_tags.join(', ') : (loc.terrain_tags || '');
    const fld = (label, id, val, type) => `
      <label style="font-size:0.78rem;font-weight:600;color:var(--t2)">${label}</label>
      <input id="${id}" type="${type||'text'}" class="field-input" value="${_esc(val==null?'':String(val))}">`;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `<div class="modal-box" style="max-width:520px">
      <div class="modal-head"><span>👁 Lokacja: ${_esc(loc.label || locKey)}</span><button id="ld-x">✕</button></div>
      <div style="padding:16px;display:flex;flex-direction:column;gap:10px;max-height:60vh;overflow:auto">
        <div style="font-size:0.78rem;color:var(--t3)">Klucz: <code>${_esc(locKey)}</code>
          ${loc.ai_generated ? '<span class="chip on" style="margin-left:8px;font-size:0.7rem">AI</span>' : ''}
          <span class="chip" style="margin-left:6px;font-size:0.7rem">${source}</span></div>
        ${fld('Nazwa', 'ld-label', loc.label)}
        <label style="font-size:0.78rem;font-weight:600;color:var(--t2)">Opis</label>
        <textarea id="ld-description" class="field-input" rows="4">${_esc(loc.description||'')}</textarea>
        ${fld('Typ', 'ld-location_type', loc.location_type)}
        ${fld('Podtyp', 'ld-location_subtype', loc.location_subtype)}
        ${fld('Biom', 'ld-biome', loc.biome)}
        ${fld('Tier', 'ld-tier', loc.tier, 'number')}
        ${fld('Rodzic (parent_key)', 'ld-parent_key', loc.parent_key)}
        ${fld('Tagi terenu (po przecinku)', 'ld-terrain_tags', tagsStr)}
      </div>
      <div class="modal-foot">
        <button class="btn btn-secondary" id="ld-cancel">Zamknij</button>
        <button class="btn btn-primary" id="ld-save">💾 Zapisz zmiany</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    overlay.querySelector('#ld-x').onclick = close;
    overlay.querySelector('#ld-cancel').onclick = close;
    overlay.querySelector('#ld-save').onclick = async () => {
      const v = id => overlay.querySelector(id).value.trim();
      const tierRaw = v('#ld-tier');
      const tags = v('#ld-terrain_tags');
      const fields = {
        label: v('#ld-label'),
        description: v('#ld-description'),
        location_type: v('#ld-location_type'),
        location_subtype: v('#ld-location_subtype'),
        biome: v('#ld-biome'),
        parent_key: v('#ld-parent_key'),
        tier: tierRaw === '' ? null : parseInt(tierRaw, 10),
        terrain_tags: JSON.stringify(tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : []),
      };
      try {
        await apiFetch(`/api/admin/locations/${encodeURIComponent(locKey)}/edit`, {
          method: 'PATCH', body: JSON.stringify({ fields }),
        });
        _showToast('Zmiany zapisane', 'success');
        close();
        // odśwież listę źródłową
        if (source === 'floating') { _worldLoaded.delete('floating'); _loadFloating(); }
        else { _worldLoaded.delete('review'); _loadPendingLocations(); }
      } catch(e) { _showToast(e.message || 'Błąd zapisu', 'error'); }
    };
  };

  async function openLocNpcModal(locKey) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `<div class="modal-box" style="max-width:640px">
      <div class="modal-head"><span>👤 NPC / Wrogowie — <code>${_esc(locKey)}</code></span><button id="lnm-x">✕</button></div>
      <div style="padding:16px;display:flex;flex-direction:column;gap:14px">
        <div>
          <div style="font-size:0.75rem;font-weight:600;color:var(--t2);margin-bottom:6px">NPC w lokacji</div>
          <div id="lnm-npc-chips" style="display:flex;flex-wrap:wrap;gap:6px;min-height:28px"></div>
          <div style="display:flex;gap:6px;margin-top:8px">
            <select id="lnm-npc-sel" style="flex:1;background:var(--bg3);color:var(--t1);border:1px solid var(--border);border-radius:4px;padding:4px;font-size:0.78rem">
              <option value="">— wybierz NPC —</option>
            </select>
            <button class="btn btn-sm btn-secondary" id="lnm-npc-add">+ Dodaj</button>
          </div>
        </div>
        <div>
          <div style="font-size:0.75rem;font-weight:600;color:var(--t2);margin-bottom:6px">Wrogowie w lokacji</div>
          <div id="lnm-enemy-chips" style="display:flex;flex-wrap:wrap;gap:6px;min-height:28px"></div>
          <div style="display:flex;gap:6px;margin-top:8px">
            <select id="lnm-enemy-sel" style="flex:1;background:var(--bg3);color:var(--t1);border:1px solid var(--border);border-radius:4px;padding:4px;font-size:0.78rem">
              <option value="">— wybierz wroga —</option>
            </select>
            <button class="btn btn-sm btn-secondary" id="lnm-enemy-add">+ Dodaj</button>
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-secondary" id="lnm-cancel">Anuluj</button>
        <button class="btn btn-primary" id="lnm-save">✓ Zapisz</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);

    let npcKeys = [], enemyKeys = [];

    const renderChips = (containerId, keys, type) => {
      const el = overlay.querySelector(containerId);
      if (!keys.length) { el.innerHTML = '<span style="color:var(--t3);font-size:0.75rem">Brak</span>'; return; }
      el.innerHTML = keys.map(k =>
        `<span style="display:flex;align-items:center;gap:4px;background:var(--bg3);padding:3px 8px;border-radius:12px;font-size:0.75rem">${_esc(k)}<button data-remove="${_esc(k)}" data-type="${type}" style="background:none;border:none;cursor:pointer;color:var(--t3);font-size:0.8rem;padding:0 0 0 2px">×</button></span>`
      ).join('');
    };
    const refreshChips = () => {
      renderChips('#lnm-npc-chips', npcKeys, 'npc');
      renderChips('#lnm-enemy-chips', enemyKeys, 'enemy');
    };

    overlay.addEventListener('click', e => {
      const btn = e.target.closest('[data-remove]');
      if (!btn) return;
      if (btn.dataset.type === 'npc') npcKeys = npcKeys.filter(x => x !== btn.dataset.remove);
      else enemyKeys = enemyKeys.filter(x => x !== btn.dataset.remove);
      refreshChips();
    });

    try {
      const [loc, npcsData, enemiesData] = await Promise.all([
        apiFetch(`/api/locations/${locKey}`),
        apiFetch('/api/admin/npcs'),
        apiFetch('/api/admin/enemies'),
      ]);
      npcKeys = Array.isArray(loc.npc_keys) ? [...loc.npc_keys] : [];
      enemyKeys = Array.isArray(loc.enemy_keys) ? [...loc.enemy_keys] : [];
      refreshChips();
      const npcSel = overlay.querySelector('#lnm-npc-sel');
      const enemySel = overlay.querySelector('#lnm-enemy-sel');
      (npcsData.data||npcsData.items||[]).forEach(n => {
        const opt = document.createElement('option');
        opt.value = String(n.key||n.id||'');
        opt.textContent = n.label||n.key||String(n.id);
        npcSel.appendChild(opt);
      });
      (enemiesData.items||[]).forEach(e => {
        const opt = document.createElement('option');
        opt.value = e.key;
        opt.textContent = `${e.label||e.key} (T${e.tier||1})`;
        enemySel.appendChild(opt);
      });
    } catch(err) { _showToast(err.message||'Błąd ładowania.','error'); }

    overlay.querySelector('#lnm-npc-add').onclick = () => {
      const v = overlay.querySelector('#lnm-npc-sel').value;
      if (v && !npcKeys.includes(v)) { npcKeys.push(v); refreshChips(); }
    };
    overlay.querySelector('#lnm-enemy-add').onclick = () => {
      const v = overlay.querySelector('#lnm-enemy-sel').value;
      if (v && !enemyKeys.includes(v)) { enemyKeys.push(v); refreshChips(); }
    };

    const closeModal = () => overlay.remove();
    overlay.querySelector('#lnm-x').onclick = closeModal;
    overlay.querySelector('#lnm-cancel').onclick = closeModal;
    overlay.querySelector('#lnm-save').onclick = async () => {
      try {
        await apiFetch(`/api/locations/admin/locations/${encodeURIComponent(locKey)}`, {
          method: 'PATCH', body: JSON.stringify({ npc_keys: npcKeys, enemy_keys: enemyKeys }),
        });
        _showToast('Zapisano NPC/Wrogów.', 'success');
        _worldLoaded.delete('locations');
        closeModal();
      } catch(err) { _showToast(err.message||'Błąd zapisu.','error'); }
    };
  }

// ── Pending locations + submap editor ──────────────────────────────────────────
  async function _loadPendingLocations() {
    const container = document.getElementById('wtab-review');
    if (!container) return;
    container.innerHTML = '<div style="padding:28px;text-align:center;color:var(--t3);font-size:0.8rem">Ładowanie…</div>';
    try {
      const [locRes, subRes] = await Promise.allSettled([
        apiFetch('/api/admin/world/pending/locations'),
        apiFetch('/api/admin/world/hexes/submappable'),
      ]);
      const locs = locRes.status==='fulfilled' ? (locRes.value?.items||locRes.value||[]) : [];
      const submappable = subRes.status==='fulfilled' ? (subRes.value?.hexes||[]) : [];
      const totalPending = locs.length;
      if (!totalPending && !submappable.length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">✓</div><div class="empty-title">Brak oczekujących</div><div class="empty-sub">Wszystkie wpisy zatwierdzone.</div></div>';
        return;
      }
      locs.forEach(p => { _locDetailReg[p.key] = p; });  // #590
      const mkLocRow = p => {
        const hasCoords = p.world_hex_q != null && p.world_hex_r != null;
        const coordCell = hasCoords
          ? `<td class="td-mono" style="font-size:0.72rem;white-space:nowrap">(${p.world_hex_q},${p.world_hex_r})</td>`
          : `<td class="td-muted" style="font-size:0.72rem">—</td>`;
        return `<tr>
        <td class="td-mono" style="font-size:0.72rem">${_esc(p.key)}</td>
        <td class="td-sticky td-name">${_esc(p.label||p.key)}</td>
        <td class="td-muted">${_esc(p.location_type||'—')}</td>
        <td style="font-size:0.78rem;color:var(--t2)">${p.region ? _esc(p.region) : '<span class="td-muted">(brak)</span>'}</td>
        <td class="td-muted">${_esc(p.biome||'—')}</td>
        ${coordCell}
        <td class="td-muted" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_esc((p.description||'').slice(0,70))}</td>
        <td class="td-actions" style="white-space:nowrap">
          <button class="btn btn-sm" style="font-size:0.72rem" onclick="openLocDetailModal('${_esc(p.key)}','pending')">👁 Podgląd</button>
          <button class="btn btn-sm btn-primary" style="font-size:0.72rem" onclick="reviewEntity('location','${_esc(p.key)}','approve',this)">✓ Zatwierdź</button>
          <button class="btn btn-sm" style="font-size:0.72rem;background:var(--amber,#f59e0b);color:#fff;border:none;border-radius:4px;padding:3px 8px;cursor:pointer" onclick="approveKanon('location','${_esc(p.key)}',this)">★ Kanon</button>
          <button class="btn btn-sm btn-danger" style="font-size:0.72rem" onclick="reviewEntity('location','${_esc(p.key)}','discard',this)">✕</button>
        </td>
      </tr>`;
      };
      const locSection = totalPending ? `<div class="table-wrap"><table class="data-table" id="pending-loc-table">
        <thead><tr>
          <th><div class="th-inner">Klucz</div></th>
          <th class="td-sticky"><div class="th-inner">Nazwa</div></th>
          <th><div class="th-inner">Typ</div></th>
          <th><div class="th-inner">Kraina</div></th>
          <th><div class="th-inner">Biom</div></th>
          <th><div class="th-inner">Koord.</div></th>
          <th><div class="th-inner">Opis</div></th>
          <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
        </tr></thead>
        <tbody>${locs.map(mkLocRow).join('')}</tbody>
      </table></div>` : '';
      const subSection = submappable.length ? `
        <div style="padding:10px 16px 6px;font-weight:600;font-size:0.82rem;color:var(--t2);border-top:1px solid var(--border);margin-top:${totalPending?'12px':'0'}">
          🏘️ Heksy z podmapą (${submappable.length})
          <span style="font-size:0.7rem;font-weight:400;color:var(--t3);margin-left:8px">Typy terenu które mogą posiadać lokalną podmapę</span>
        </div>
        <div class="table-wrap"><table class="data-table">
          <thead><tr>
            <th><div class="th-inner">Typ</div></th>
            <th><div class="th-inner">Koord.</div></th>
            <th class="td-sticky"><div class="th-inner">Etykieta</div></th>
            <th><div class="th-inner">Submap</div></th>
            <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
          </tr></thead>
          <tbody>${submappable.map(h => `<tr>
            <td style="white-space:nowrap"><span style="font-size:1rem">${_esc(h.map_icon||'⬡')}</span> <span class="td-muted" style="font-size:0.75rem">${_esc(h.type_label||h.hex_type)}</span></td>
            <td class="td-mono" style="font-size:0.72rem">(${h.q},${h.r})</td>
            <td class="td-sticky td-name">${_esc(h.label||'—')}</td>
            <td><span class="badge ${h.submap_exists?'badge-green':'badge-slate'}">${h.submap_exists?'✓ Istnieje':'Brak'}</span></td>
            <td class="td-actions" style="white-space:nowrap">
              ${h.submap_exists?`<button class="btn btn-sm btn-primary" style="font-size:0.72rem" onclick="openSubmapModal(${h.q},${h.r})">✎ Edytuj</button> `:''}
              <select id="sub-sz-${h.q}-${h.r}" style="background:var(--bg3);color:var(--t1);border:1px solid var(--border);border-radius:4px;padding:2px 3px;font-size:0.68rem;height:26px">
                <option value="1">S (7)</option><option value="2">M (19)</option><option value="3" selected>L (37)</option><option value="4">XL (61)</option>
              </select>
              <button class="btn btn-sm btn-secondary" style="font-size:0.72rem"
                onclick="pendingGenSubmap(${h.q},${h.r},this)">
                ${h.submap_exists?'↺ Regen':'🏘 Generuj'}
              </button>
            </td>
          </tr>`).join('')}</tbody>
        </table></div>` : '';
      container.innerHTML = locSection + subSection;
    } catch(e) {
      container.innerHTML = `<div style="padding:24px;text-align:center;color:var(--red);font-size:0.8rem">${_esc(e.message)}</div>`;
    }
  }

  // R2 #1242: POST generate-local; on 409 (hex has a settlement local map) show
  // a confirm dialog and retry with force=true. Throws {__cancelled:true} if the
  // admin declines, so callers can stay silent instead of toasting an error.
  async function _genLocalWithForce(payload) {
    try {
      return await apiFetch('/api/admin/world/generate-local', { method:'POST', body: JSON.stringify(payload) });
    } catch(e) {
      if (e && e.status === 409) {
        if (!confirm(`${e.message}\n\nNadpisać mimo to?`)) {
          throw { __cancelled: true };
        }
        return await apiFetch('/api/admin/world/generate-local', { method:'POST', body: JSON.stringify({ ...payload, force: true }) });
      }
      throw e;
    }
  }

  async function pendingGenSubmap(q, r, btn) {
    const szSel = document.getElementById(`sub-sz-${q}-${r}`);
    const radius = szSel ? parseInt(szSel.value) : 3;
    btn.disabled = true; btn.textContent = '⏳';
    try {
      await _genLocalWithForce({parent_q: q, parent_r: r, seed: 0, radius});
      await openSubmapModal(q, r);
      _worldLoaded.delete('review');
      await _loadPendingLocations();
    } catch(e) {
      if (e && e.__cancelled) { /* admin declined overwrite */ }
      else _showToast(e.message || 'Błąd generowania podmopy.', 'error');
      btn.disabled = false; btn.textContent = '🏘 Generuj';
    }
  }

  async function openSubmapModal(q, r) {
    const [data, typesData] = await Promise.all([
      apiFetch(`/api/admin/world/local-map/${q}/${r}`),
      apiFetch('/api/admin/world/hex-types'),
    ]);
    if (!data.ok) { _showToast(data.error || 'Brak podmopy.', 'error'); return; }
    const hexes = data.hexes || [];
    const parent = data.parent || {};
    const allTypes = {};
    for (const t of (typesData.hex_types || [])) allTypes[t.hex_type] = t;

    const hexMap = {};
    for (const h of hexes) hexMap[`${h.q},${h.r}`] = h;

    let selectedType = hexes[0]?.hex_type || Object.keys(allTypes)[0] || 'plains';
    let isPainting = false;
    let editorMode = 'paint'; // 'paint' | 'location'

    const SZ = 30;
    const h2p = (lq, lr) => ({ x: SZ * 1.5 * lq, y: SZ * (Math.sqrt(3)/2*lq + Math.sqrt(3)*lr) });
    const hexPts = (s) => Array.from({length:6}, (_,i) => {
      const a = Math.PI/3*i;
      return `${(s*Math.cos(a)).toFixed(1)},${(s*Math.sin(a)).toFixed(1)}`;
    }).join(' ');

    const pxList = hexes.map(h => h2p(h.q, h.r));
    const minX = Math.min(...pxList.map(p=>p.x)) - SZ*1.5;
    const minY = Math.min(...pxList.map(p=>p.y)) - SZ*1.5;
    const maxX = Math.max(...pxList.map(p=>p.x)) + SZ*1.5;
    const maxY = Math.max(...pxList.map(p=>p.y)) + SZ*1.5;
    const vw = (maxX-minX).toFixed(1), vh = (maxY-minY).toFixed(1);

    const submapTypeKeys = [...new Set(hexes.map(h=>h.hex_type))];
    const otherTypeKeys = Object.keys(allTypes).filter(k=>!submapTypeKeys.includes(k));

    const buildSvg = () => hexes.map(h => {
      const {x,y} = h2p(h.q, h.r);
      const tx=(x-minX).toFixed(1), ty=(y-minY).toFixed(1);
      const t = allTypes[h.hex_type] || {};
      const fill = t.map_color || '#1a2020';
      const label = (h.label||'').slice(0,10);
      const icon = t.map_icon || '';
      return `<g data-lq="${h.q}" data-lr="${h.r}" transform="translate(${tx},${ty})" style="cursor:crosshair">
        <polygon points="${hexPts(SZ-1.5)}" fill="${fill}" stroke="#555" stroke-width="0.8"/>
        <text class="smod-icon" x="0" y="-3" text-anchor="middle" font-size="12" style="pointer-events:none">${icon}</text>
        <text x="0" y="11" text-anchor="middle" font-size="6" fill="#ccc" style="pointer-events:none">${_esc(label)}</text>
      </g>`;
    }).join('');

    const paletteGroup = (label, keys) => !keys.length ? '' : `
      <div style="font-size:0.58rem;color:var(--t3);margin:6px 4px 2px;text-transform:uppercase;letter-spacing:0.06em">${label}</div>
      ${keys.map(k => {
        const t = allTypes[k] || {label:k, map_icon:'⬡'};
        return `<div class="smod-type" data-type="${_esc(k)}" style="padding:4px 6px;cursor:pointer;border-radius:4px;display:flex;align-items:center;gap:5px;font-size:0.72rem">
          <span style="font-size:0.9rem">${_esc(t.map_icon||'⬡')}</span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_esc(t.label||k)}</span>
        </div>`;
      }).join('')}`;

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `<div class="modal-box" style="max-width:940px;height:88vh;display:flex;flex-direction:column">
      <div class="modal-head">
        <span>🏘️ Edytor podmopy: ${_esc(parent.label||`(${q},${r})`)} — ${hexes.length} heks.</span>
        <div style="display:flex;gap:6px;align-items:center">
          <button id="smod-mode-paint" class="btn btn-sm btn-primary" style="font-size:0.72rem">🖌 Maluj</button>
          <button id="smod-mode-loc" class="btn btn-sm btn-secondary" style="font-size:0.72rem">🔗 Lokacja</button>
          <button id="smod-x">✕</button>
        </div>
      </div>
      <div style="display:flex;flex:1;overflow:hidden">
        <div id="smod-palette" style="width:155px;flex-shrink:0;overflow-y:auto;padding:6px;border-right:1px solid var(--border);background:var(--bg2)">
          <div style="font-size:0.68rem;font-weight:600;color:var(--t2);margin-bottom:4px;padding:0 4px">Wybrany typ:</div>
          <div id="smod-cur" style="padding:4px 6px;background:var(--bg3);border-radius:4px;font-size:0.75rem;margin-bottom:6px;border:1px solid var(--accent)">—</div>
          ${paletteGroup('W podmapie', submapTypeKeys)}
          ${paletteGroup('Inne', otherTypeKeys)}
        </div>
        <div style="flex:1;overflow:hidden;background:#080608;position:relative">
          <svg id="smod-svg" viewBox="0 0 ${vw} ${vh}" style="width:100%;height:100%;display:block;user-select:none">${buildSvg()}</svg>
          <div id="smod-tip" style="position:absolute;display:none;background:#222;color:#ccc;font-size:0.68rem;padding:2px 7px;border-radius:3px;pointer-events:none;z-index:10"></div>
        </div>
        <div id="smod-loc-panel" style="width:215px;flex-shrink:0;overflow-y:auto;padding:10px;border-left:1px solid var(--border);background:var(--bg2);display:none">
          <div style="font-size:0.68rem;font-weight:600;color:var(--t2);margin-bottom:8px">Lokacja heksa</div>
          <div id="smod-loc-info" style="font-size:0.75rem;color:var(--t3);padding:8px;background:var(--bg3);border-radius:4px;margin-bottom:8px">Kliknij heks aby zobaczyć lokację.</div>
          <div id="smod-loc-form" style="display:none">
            <div style="font-size:0.68rem;color:var(--t3);margin-bottom:4px">Przypisz lokację:</div>
            <select id="smod-loc-sel" style="width:100%;background:var(--bg3);color:var(--t1);border:1px solid var(--border);border-radius:4px;padding:4px;font-size:0.75rem;margin-bottom:8px"></select>
            <button id="smod-loc-assign" class="btn btn-sm btn-primary" style="width:100%;font-size:0.75rem">✓ Przypisz</button>
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <select id="smod-sz" style="background:var(--bg3);color:var(--t1);border:1px solid var(--border);border-radius:4px;padding:4px 6px;font-size:0.75rem">
          <option value="1">S – 7 heks.</option><option value="2">M – 19 heks.</option><option value="3" selected>L – 37 heks.</option><option value="4">XL – 61 heks.</option>
        </select>
        <button class="btn btn-secondary" id="smod-regen">↺ Regeneruj</button>
        <button class="btn btn-primary" id="smod-ok">✓ Przyjmij</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);

    // Highlight selected type chip
    const refreshPalette = () => {
      overlay.querySelectorAll('.smod-type').forEach(c => {
        const active = c.dataset.type === selectedType;
        c.style.background = active ? 'var(--bg3)' : 'transparent';
        c.style.outline = active ? '1px solid var(--accent,#6366f1)' : 'none';
      });
      const t = allTypes[selectedType] || {};
      const cur = overlay.querySelector('#smod-cur');
      if (cur) cur.textContent = `${t.map_icon||'⬡'} ${t.label||selectedType}`;
    };
    refreshPalette();

    const refreshMode = () => {
      const isPaint = editorMode === 'paint';
      overlay.querySelector('#smod-mode-paint').className = `btn btn-sm ${isPaint ? 'btn-primary' : 'btn-secondary'}`;
      overlay.querySelector('#smod-mode-loc').className = `btn btn-sm ${!isPaint ? 'btn-primary' : 'btn-secondary'}`;
      overlay.querySelector('#smod-palette').style.display = isPaint ? '' : 'none';
      overlay.querySelector('#smod-loc-panel').style.display = isPaint ? 'none' : '';
      const svgEl = overlay.querySelector('#smod-svg');
      svgEl.querySelectorAll('[data-lq]').forEach(g => g.style.cursor = isPaint ? 'crosshair' : 'pointer');
    };
    refreshMode();

    overlay.querySelector('#smod-mode-paint').onclick = () => { editorMode = 'paint'; refreshMode(); };
    overlay.querySelector('#smod-mode-loc').onclick = () => { editorMode = 'location'; refreshMode(); };

    overlay.querySelector('#smod-palette').addEventListener('click', e => {
      const chip = e.target.closest('.smod-type');
      if (!chip) return;
      selectedType = chip.dataset.type;
      refreshPalette();
    });

    const paintHex = (lq, lr) => {
      const key = `${lq},${lr}`;
      if (!hexMap[key] || hexMap[key].hex_type === selectedType) return;
      hexMap[key].hex_type = selectedType;
      const t = allTypes[selectedType] || {};
      const g = overlay.querySelector(`[data-lq="${lq}"][data-lr="${lr}"]`);
      if (g) {
        g.querySelector('polygon').setAttribute('fill', t.map_color || '#333');
        const iconEl = g.querySelector('.smod-icon');
        if (iconEl) iconEl.textContent = t.map_icon || '';
      }
      apiFetch(`/api/admin/world/local-hexes/${q}/${r}/${lq}/${lr}`, {
        method: 'PATCH', body: JSON.stringify({ hex_type: selectedType }),
      }).catch(e => console.warn('patch local hex:', e.message));
    };

    const loadLocPanel = async (lq, lr) => {
      const info = overlay.querySelector('#smod-loc-info');
      const form = overlay.querySelector('#smod-loc-form');
      const sel = overlay.querySelector('#smod-loc-sel');
      info.textContent = '⏳ Ładowanie…';
      form.style.display = 'none';
      try {
        const d = await apiFetch(`/api/admin/world/hex-location/${q}/${r}/${lq}/${lr}`);
        const specific = d.specific;
        const generic = d.generic;
        const current = specific || generic;
        const isGeneric = !specific && !!generic;
        info.innerHTML = current
          ? `<div style="font-weight:600;margin-bottom:3px">${_esc(current.label||current.key||'')}</div>
             <div style="font-size:0.68rem;color:var(--t3)">${isGeneric ? '⬡ Generyczna (fallback)' : '⭐ Specyficzna'}</div>
             ${current.description ? `<div style="font-size:0.68rem;color:var(--t3);margin-top:4px;line-height:1.4">${_esc(current.description.slice(0,120))}${current.description.length>120?'…':''}</div>` : ''}`
          : `<div style="color:var(--t3);font-size:0.72rem">Brak lokacji dla tego heksa.</div>`;
        if (d.candidates?.length) {
          sel.innerHTML = d.candidates.map(c =>
            `<option value="${_esc(c.key)}" ${current && c.key === current.key && !isGeneric ? 'selected' : ''}>${_esc(c.label||c.key||'')}${c.is_generic?' (generyczna)':''}</option>`
          ).join('');
          form.style.display = '';
          overlay.querySelector('#smod-loc-assign').onclick = async () => {
            const locKey = sel.value;
            try {
              await apiFetch(`/api/admin/world/assign-hex-location/${q}/${r}/${lq}/${lr}`, {
                method: 'PATCH', body: JSON.stringify({ location_key: locKey }),
              });
              _showToast('Przypisano lokację.', 'success');
              await loadLocPanel(lq, lr);
            } catch(err) { _showToast(err.message||'Błąd.','error'); }
          };
        }
      } catch(err) { info.textContent = `Błąd: ${err.message}`; }
    };

    const svg = overlay.querySelector('#smod-svg');
    const tip = overlay.querySelector('#smod-tip');
    const stopPaint = () => { isPainting = false; };

    svg.addEventListener('mousedown', e => {
      const g = e.target.closest('[data-lq]'); if (!g) return;
      if (editorMode === 'paint') {
        isPainting = true;
        paintHex(parseInt(g.dataset.lq), parseInt(g.dataset.lr));
      } else {
        loadLocPanel(parseInt(g.dataset.lq), parseInt(g.dataset.lr));
      }
    });
    svg.addEventListener('mousemove', e => {
      const g = e.target.closest('[data-lq]');
      if (g) {
        const lq=g.dataset.lq, lr=g.dataset.lr;
        const h = hexMap[`${lq},${lr}`];
        if (h) {
          const t = allTypes[h.hex_type]||{};
          tip.style.display='block';
          tip.style.left=(e.offsetX+12)+'px'; tip.style.top=(e.offsetY+8)+'px';
          tip.textContent=`(${lq},${lr}) ${t.label||h.hex_type}${h.label?' — '+h.label:''}`;
        }
        if (editorMode === 'paint' && isPainting) paintHex(parseInt(lq), parseInt(lr));
      } else { tip.style.display='none'; }
    });
    document.addEventListener('mouseup', stopPaint);
    svg.addEventListener('mouseleave', () => { tip.style.display='none'; });

    const closeModal = () => { document.removeEventListener('mouseup', stopPaint); overlay.remove(); };
    overlay.querySelector('#smod-x').onclick = closeModal;
    overlay.querySelector('#smod-ok').onclick = closeModal;

    overlay.querySelector('#smod-regen').onclick = async (e) => {
      const btn = e.currentTarget;
      const radius = parseInt(overlay.querySelector('#smod-sz')?.value || '3');
      btn.disabled = true; btn.textContent = '⏳';
      try {
        await _genLocalWithForce({parent_q:q, parent_r:r, seed:Math.floor(Math.random()*99999), radius});
        closeModal();
        await openSubmapModal(q, r);
      } catch(err) {
        if (err && err.__cancelled) { btn.disabled=false; btn.textContent='↺ Regeneruj'; }
        else { _showToast(err.message||'Błąd.','error'); btn.disabled=false; btn.textContent='↺ Regeneruj'; }
      }
    };
  }

  async function approveKanon(entityType, key, btn) {
    btn.disabled = true; btn.textContent = '⏳';
    try {
      if (entityType === 'location') {
        // #1169 — /api/locations/{key} has no PATCH (405); the partial-update
        // endpoint that accepts `canonical` is /api/locations/admin/locations/{key}.
        await apiFetch(`/api/locations/admin/locations/${key}`, { method:'PATCH', body: JSON.stringify({ canonical: 1 }) }).catch(()=>{});
      }
      await apiFetch(`/api/admin/world/review/${entityType}/${key}`, { method:'POST', body: JSON.stringify({ action:'approve' }) });
      _showToast(`Zatwierdzono jako Kanon.`, 'success');
      _worldLoaded.delete('review'); _loadPendingLocations();
    } catch(e) { _showToast(e.message||'Błąd.','error'); btn.disabled = false; btn.textContent = '★ Kanon'; }
  }

// ── Review entity ──────────────────────────────────────────────────────────────
  async function reviewEntity(entityType, key, action, btn) {
    // #995: location approve for settlements → subloc checklist modal
    if (entityType === 'location' && action === 'approve') {
      await _approveLocationWithSublocs(key, btn, async () => {
        _worldLoaded.delete('review');
        await _loadPendingLocations();
      });
      return;
    }
    const label = action === 'approve' ? 'Zatwierdź' : 'Odrzuć';
    if (!confirm(`${label} "${key}"?`)) return;
    btn.disabled = true; btn.textContent = '⏳';
    try {
      await apiFetch(`/api/admin/world/review/${entityType}/${key}`, { method: 'POST', body: JSON.stringify({ action }) });
      _showToast(action === 'approve' ? 'Zatwierdzono.' : 'Odrzucono.', 'success');
      _worldLoaded.delete('review');
      await _loadPendingLocations();
    } catch(e) {
      _showToast(e.message || 'Błąd.', 'error');
      btn.disabled = false; btn.textContent = action === 'approve' ? '✓ Zatwierdź' : '✕ Odrzuć';
    }
  }

// ── Terrain ────────────────────────────────────────────────────────────────────
  async function _loadTerrain() {
    const tbody = document.getElementById('terrain-tbody');
    if (!tbody) return;
    tbody.innerHTML = _loading(10);
    try {
      const rows = await apiFetch('/api/admin/world/hex-terrain-config');
      const items = Array.isArray(rows) ? rows : (rows.items || []);
      const totalW = items.reduce((s,r) => s+(r.spawn_weight||0), 0);
      if (!items.length) { tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:24px;color:var(--t3)">Brak typów terenu</td></tr>`; return; }
      tbody.innerHTML = items.map(r => {
        const pct = totalW > 0 && r.spawn_weight > 0 ? ((r.spawn_weight/totalW)*100).toFixed(1) : '0';
        return `<tr>
          <td style="text-align:center;font-size:1.2rem">${r.map_icon||'?'}</td>
          <td class="td-mono" style="font-size:0.75rem">${_esc(r.hex_type)}</td>
          <td class="td-name editable" onclick="mechPatchEdit(this,'/api/admin/world/hex-terrain-config/${_esc(r.hex_type)}','label')">${_esc(r.label||'')}</td>
          <td>
            <input type="number" class="field-input" style="width:72px;padding:3px 6px;font-size:0.8rem"
              value="${r.spawn_weight}" min="0" max="999"
              onchange="terrainPatch('${_esc(r.hex_type)}','spawn_weight',this.value,this)"
              onkeydown="if(event.key==='Enter')this.blur()" />
            <span style="font-size:0.7rem;color:var(--t3);margin-left:4px">${pct}%</span>
          </td>
          <td>
            <select class="field-input" style="width:104px;padding:3px 6px;font-size:0.75rem"
              onchange="terrainPatch('${_esc(r.hex_type)}','placement_mode',this.value,this)">
              <option value="biome" ${(r.placement_mode||'biome')==='biome'?'selected':''}>biome</option>
              <option value="scatter" ${r.placement_mode==='scatter'?'selected':''}>scatter</option>
              <option value="path" ${r.placement_mode==='path'?'selected':''}>path</option>
            </select>
          </td>
          <td>
            <input type="number" class="field-input" style="width:64px;padding:3px 6px;font-size:0.8rem"
              value="${r.travel_hours}" min="0.5" max="48" step="0.5"
              onchange="terrainPatch('${_esc(r.hex_type)}','travel_hours',this.value,this)"
              onkeydown="if(event.key==='Enter')this.blur()" />
          </td>
          <td>
            <input type="number" class="field-input" style="width:60px;padding:3px 6px;font-size:0.8rem"
              value="${Math.round((r.encounter_base_chance||0)*100)}" min="0" max="100"
              onchange="terrainPatch('${_esc(r.hex_type)}','encounter_pct',this.value,this)"
              onkeydown="if(event.key==='Enter')this.blur()" />
          </td>
          <td><span class="badge ${r.is_active?'badge-green':'badge-slate'}">${r.is_active?'●':'○'}</span></td>
          <td style="text-align:center">
            <input type="checkbox" title="Może mieć podmapę lokalną" ${r.has_submap?'checked':''}
              onchange="terrainPatch('${_esc(r.hex_type)}','has_submap',this.checked?'1':'0',this)" />
          </td>
          <td class="td-actions"><button class="btn-icon" title="Edytuj" onclick="openTerrainFormModal(${JSON.stringify(r).replace(/"/g,'&quot;')})">✎</button></td>
        </tr>`;
      }).join('');
    } catch(e) { tbody.innerHTML = _errRow(10, e.message); }
  }

  async function terrainPatch(key, field, rawValue, input) {
    let value;
    if (field === 'placement_mode') value = rawValue;
    else if (field === 'encounter_pct') value = parseFloat(rawValue)/100;
    else if (field === 'has_submap') value = parseInt(rawValue);
    else value = parseFloat(rawValue);
    if (typeof value === 'number' && isNaN(value)) return;
    const apiField = field === 'encounter_pct' ? 'encounter_base_chance' : field;
    try {
      await apiFetch(`/api/admin/world/hex-terrain-config/${key}`, { method: 'PATCH', body: JSON.stringify({ [apiField]: value }) });
      _showToast('Zapisano.', 'success');
      _worldLoaded.delete('terrain');
      await _loadTerrain();
    } catch(e) {
      _showToast(e.message || 'Błąd zapisu.', 'error');
    }
  }

  function openTerrainFormModal(prefillOrNull) {
    const p = typeof prefillOrNull === 'string' ? JSON.parse(prefillOrNull) : (prefillOrNull || {});
    const isEdit = !!p.hex_type;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `<div class="modal-box" style="max-width:440px">
      <div class="modal-head"><span>${isEdit ? 'Edytuj teren: '+_esc(p.label||p.hex_type) : 'Nowy typ terenu'}</span><button onclick="this.closest('.modal-overlay').remove()">✕</button></div>
      <div class="modal-body" style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        ${isEdit ? '' : `<div class="form-row" style="grid-column:1/-1"><label>Klucz *</label><input id="tf-key" class="field-input form-mono" placeholder="np. forest" /></div>`}
        <div class="form-row" style="grid-column:1/-1"><label>Etykieta *</label><input id="tf-label" class="field-input" value="${_esc(p.label||'')}" /></div>
        <div class="form-row"><label>Ikona (emoji)</label><input id="tf-icon" class="field-input" value="${_esc(p.map_icon||'')}" style="font-size:1.2rem" /></div>
        <div class="form-row"><label>Kolor mapy</label><input id="tf-color" class="field-input" type="color" value="${_esc(p.map_color||'#4ade80')}" /></div>
        <div class="form-row"><label>Waga spawnu</label><input id="tf-weight" class="field-input" type="number" min="0" max="999" value="${p.spawn_weight??10}" /></div>
        <div class="form-row"><label>Czas podróży (h)</label><input id="tf-hours" class="field-input" type="number" min="1" max="48" step="0.5" value="${p.travel_hours??4}" /></div>
        <div class="form-row"><label>Szansa na enc. (%)</label><input id="tf-enc" class="field-input" type="number" min="0" max="100" value="${Math.round((p.encounter_base_chance||0)*100)}" /></div>
        <div class="form-row"><label>Tryb rozmieszczenia</label>
          <select id="tf-placement" class="field-input">
            <option value="biome" ${(p.placement_mode||'biome')==='biome'?'selected':''}>Biom (skupiska)</option>
            <option value="scatter" ${p.placement_mode==='scatter'?'selected':''}>Rozproszony (pojedyncze)</option>
            <option value="path" ${p.placement_mode==='path'?'selected':''}>Ścieżka (linie: rzeka/droga)</option>
          </select></div>
        <div class="form-row"><label><input type="checkbox" id="tf-active" ${p.is_active!==false?'checked':''} /> Aktywny</label></div>
        <div class="form-row" style="grid-column:1/-1"><label>Opis</label><textarea id="tf-desc" class="field-input" rows="2">${_esc(p.description||'')}</textarea></div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
        <button class="btn btn-primary" onclick="saveTerrainForm('${_esc(p.hex_type||'')}',this)">Zapisz</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);
  }

  async function saveTerrainForm(existingKey, btn) {
    const g = id => document.getElementById(id);
    const label = g('tf-label')?.value?.trim();
    if (!label) { _showToast('Wypełnij etykietę.', 'error'); return; }
    const key = existingKey || g('tf-key')?.value?.trim();
    if (!key) { _showToast('Wypełnij klucz.', 'error'); return; }
    const body = {
      hex_type: key, label,
      map_icon: g('tf-icon')?.value?.trim() || null,
      map_color: g('tf-color')?.value || null,
      spawn_weight: parseInt(g('tf-weight')?.value) || 0,
      travel_hours: parseFloat(g('tf-hours')?.value) || 4,
      encounter_base_chance: (parseInt(g('tf-enc')?.value)||0)/100,
      placement_mode: g('tf-placement')?.value || 'biome',
      is_active: g('tf-active')?.checked ?? true,
    };
    btn.disabled = true; btn.textContent = '⏳';
    try {
      if (existingKey) {
        await apiFetch(`/api/admin/world/hex-terrain-config/${key}`, { method: 'PATCH', body: JSON.stringify(body) });
      } else {
        await apiFetch('/api/admin/world/hex-terrain-config', { method: 'POST', body: JSON.stringify(body) });
      }
      btn.closest('.modal-overlay').remove();
      _worldLoaded.delete('terrain');
      await _loadTerrain();
      _showToast('Teren zapisany.', 'success');
    } catch(e) {
      _showToast(e.message || 'Błąd zapisu.', 'error');
      btn.disabled = false; btn.textContent = 'Zapisz';
    }
  }

// ── World builder (hex SVG) ────────────────────────────────────────────────────
  // ── World Builder ─────────────────────────────────────────────────────────────

  let _wbHexTypes = {};
  let _wbHexes = {};
  let _wbTeleports = [];
  let _wbLocations = {}; // keyed by "q,r"
  let _wbSelected = null;
  let _wbPaintType = 'forest';
  let _wbPaintMode = false;
  let _wbShowLocOverlay = false; // toggle: highlight hexes with locations
  let _wbDrawingTp = null;
  let _wbPainting = false;        // mid drag-stroke
  let _wbStroke = null;           // Map<"q,r", priorHexCloneOrNull> for current stroke
  let _wbUndoStack = [];          // [{kind:'paint'|'full', items:[{q,r,before}]}]
  let _wbRenderRAF = null;
  let _wbZoom = 1.0;
  let _wbPan = { x: 400, y: 280 };
  let _wbDragStart = null;
  const _WB_SIZE = 40;
  // RM6 — region state
  let _wbRegions = [];
  let _wbActiveRegion = null;

  function _wbHexToPixel(q, r) {
    return { x: _WB_SIZE * 1.5 * q, y: _WB_SIZE * (Math.sqrt(3) / 2 * q + Math.sqrt(3) * r) };
  }

  function _wbRegionBadgeHtml(status) {
    const s = { live: ['#22c55e', 'live'], coming: ['#f59e0b', 'coming'], locked: ['#6b7280', 'locked'] };
    const [c, t] = s[status] || ['#6b7280', status || '?'];
    return `<span style="padding:1px 5px;border-radius:3px;background:${c}22;color:${c};border:1px solid ${c}55;font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em">${t}</span>`;
  }

  function _wbRenderRegionBar() {
    const bar = document.getElementById('wb-region-bar');
    if (!bar) return;
    if (!_wbRegions.length) { bar.innerHTML = ''; return; }
    const opts = _wbRegions.map(r =>
      `<option value="${_esc(r.key)}"${r.key === _wbActiveRegion ? ' selected' : ''}>${_esc(r.label)} (${r.status})</option>`
    ).join('');
    const active = _wbActiveRegion ? _wbRegions.find(r => r.key === _wbActiveRegion) : null;
    const dotColor = active ? active.color : '#7ab648';
    const badge = active ? _wbRegionBadgeHtml(active.status) : _wbRegionBadgeHtml('live');
    const warn = (active && active.status !== 'live')
      ? `<span style="font-size:0.65rem;color:#f59e0b;margin-left:6px">⚠ niedostępna dla graczy</span>`
      : '';
    // #1039 — przełącznik dostępności: admin widzi każdą krainę, gracz tylko 'live'.
    const toggle = active
      ? `<button onclick="wbToggleRegionStatus('${_esc(active.key)}')"
           style="margin-left:auto;background:${active.status === 'live' ? '#3a2a2a' : '#1e3a24'};
           border:1px solid ${active.status === 'live' ? '#6b3030' : '#2f6b3d'};
           color:${active.status === 'live' ? '#ff9f9f' : '#8de89f'};font-size:0.66rem;
           padding:3px 9px;border-radius:4px;cursor:pointer;font-weight:600">
           ${active.status === 'live' ? '🚫 Ukryj graczom' : '✅ Udostępnij graczom'}</button>`
      : '';
    bar.innerHTML = `<div style="display:flex;align-items:center;gap:8px;padding:5px 10px;background:#0d0d18;border-bottom:2px solid ${dotColor}33">
      <span style="font-size:0.68rem;color:var(--t3)">Kraina:</span>
      <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${dotColor};flex-shrink:0"></span>
      <select id="wb-region-select" onchange="wbFilterRegion(this.value)" style="background:#111;border:1px solid #2a2a3a;color:#c8c0a8;font-size:0.72rem;padding:2px 6px;border-radius:4px;cursor:pointer">
        <option value="">Wszystkie (live)</option>${opts}
      </select>
      ${badge}${warn}${toggle}
    </div>`;
  }

  /** #1039 — flip live↔coming; zmiana natychmiast gatuje travel graczy. */
  async function wbToggleRegionStatus(key) {
    const reg = _wbRegions.find(r => r.key === key);
    if (!reg) return;
    const next = reg.status === 'live' ? 'coming' : 'live';
    const q = next === 'live'
      ? `Udostępnić krainę „${reg.label}" graczom? Od tej chwili będą mogli do niej podróżować.`
      : `Ukryć krainę „${reg.label}" przed graczami? Próba wejścia zostanie zablokowana.`;
    if (!confirm(q)) return;
    try {
      const res = await apiFetch(`/api/admin/regions/${encodeURIComponent(key)}/status`, {
        method: 'PATCH', body: JSON.stringify({ status: next }),
      });
      reg.status = res.status || next;
      reg.status_override = res.status || next;
      _wbRenderRegionBar();
      showToast(
        next === 'live'
          ? `✅ ${reg.label} — udostępniona graczom`
          : `🚫 ${reg.label} — ukryta przed graczami`,
        'success',
      );
    } catch (e) {
      showToast(`Nie udało się zmienić statusu: ${e.message || e}`, 'error');
    }
  }

  async function wbFilterRegion(key) {
    _wbActiveRegion = key || null;
    _wbRenderRegionBar();
    await _wbLoadHexes();
    _wbCenter();
    _wbRender();
  }

  function _wbHexCorners(cx, cy, size) {
    return Array.from({ length: 6 }, (_, i) => {
      const a = Math.PI / 180 * 60 * i;
      return `${cx + size * Math.cos(a)},${cy + size * Math.sin(a)}`;
    }).join(' ');
  }

  function _wbKey(q, r) { return `${q},${r}`; }

  function _wbNeighbors(q, r) {
    return [[1,0],[-1,0],[0,1],[0,-1],[1,-1],[-1,1]].map(([dq,dr]) => ({ q:q+dq, r:r+dr }));
  }

  function _wbWs(wx, wy) { return { x: wx * _wbZoom + _wbPan.x, y: wy * _wbZoom + _wbPan.y }; }

  function _wbRender() {
    const svg = document.getElementById('wb-svg');
    if (!svg) return;
    let html = '';

    for (const hex of Object.values(_wbHexes)) {
      const { x, y } = _wbHexToPixel(hex.q, hex.r);
      const { x:sx, y:sy } = _wbWs(x, y);
      const rz = _WB_SIZE * _wbZoom;
      const cfg = _wbHexTypes[hex.hex_type] || { map_color:'#4a6a4a', map_icon:'' };
      const sel = _wbSelected && _wbSelected.q === hex.q && _wbSelected.r === hex.r;
      const hl = !sel && _wbPaintType && hex.hex_type === _wbPaintType;
      const hasLoc = _wbShowLocOverlay && !!_wbLocations[_wbKey(hex.q, hex.r)];
      const strokeColor = sel ? '#f0c040' : hasLoc ? '#4ade80' : hl ? '#38bdf8' : '#222';
      const strokeWidth = sel ? 2 : hasLoc ? 2.5 : hl ? 2 : 0.7;
      html += `<polygon class="whx" data-q="${hex.q}" data-r="${hex.r}"
        points="${_wbHexCorners(sx, sy, rz - 1)}"
        fill="${cfg.map_color}" stroke="${strokeColor}"
        stroke-width="${strokeWidth}"
        style="cursor:${_wbPaintMode ? 'crosshair' : 'pointer'}"/>`;
      if (hasLoc) html += `<polygon points="${_wbHexCorners(sx, sy, rz - 1)}" fill="#4ade80" fill-opacity="0.18" stroke="none" style="pointer-events:none"/>`;
      if (_wbZoom >= 0.45 && cfg.map_icon)
        html += `<text x="${sx}" y="${sy - rz * 0.05}" text-anchor="middle"
          font-size="${Math.max(9, 13 * _wbZoom)}" style="pointer-events:none">${cfg.map_icon}</text>`;
      if (_wbZoom >= 0.5 && hex.label)
        html += `<text x="${sx}" y="${sy + rz * 0.38}" text-anchor="middle"
          font-size="${Math.max(7, 9 * _wbZoom)}" fill="#c8c0a8" style="pointer-events:none">${_esc(hex.label.slice(0, 14))}</text>`;
    }

    if (_wbZoom >= 0.3) {
      const placed = new Set(Object.keys(_wbHexes));
      const ghosts = new Set();
      for (const h of Object.values(_wbHexes))
        for (const n of _wbNeighbors(h.q, h.r))
          if (!placed.has(_wbKey(n.q, n.r))) ghosts.add(_wbKey(n.q, n.r));
      for (const k of ghosts) {
        const [q, r] = k.split(',').map(Number);
        const { x, y } = _wbHexToPixel(q, r);
        const { x:sx, y:sy } = _wbWs(x, y);
        html += `<polygon class="whg" data-q="${q}" data-r="${r}"
          points="${_wbHexCorners(sx, sy, _WB_SIZE * _wbZoom - 1)}"
          fill="transparent" stroke="#2a2a3a" stroke-width="0.5" stroke-dasharray="3,3"
          style="cursor:crosshair"/>`;
      }
    }

    for (const t of _wbTeleports) {
      const p1 = _wbHexToPixel(t.from_q, t.from_r), p2 = _wbHexToPixel(t.to_q, t.to_r);
      const s1 = _wbWs(p1.x, p1.y), s2 = _wbWs(p2.x, p2.y);
      const mx = (s1.x + s2.x) / 2, my = (s1.y + s2.y) / 2 - 28 * _wbZoom;
      const colors = { boat:'#3a8aaa', magic:'#8a3aaa', tunnel:'#8a6a3a', portal:'#3aaa6a' };
      const col = colors[t.travel_type] || '#888';
      html += `<path d="M${s1.x},${s1.y} Q${mx},${my} ${s2.x},${s2.y}"
        fill="none" stroke="${col}" stroke-width="${1.4 * _wbZoom}" stroke-dasharray="5,3"
        style="pointer-events:none"/>`;
      if (_wbZoom >= 0.55 && t.label)
        html += `<text x="${mx}" y="${my - 4}" text-anchor="middle"
          font-size="${Math.max(7, 8 * _wbZoom)}" fill="${col}" style="pointer-events:none">${_esc(t.label)}</text>`;
    }

    // Location markers overlay
    if (_wbZoom >= 0.35) {
      for (const loc of Object.values(_wbLocations)) {
        const { x, y } = _wbHexToPixel(loc.q, loc.r);
        const { x:sx, y:sy } = _wbWs(x, y);
        const rz = _WB_SIZE * _wbZoom;
        const pending = loc.pending;
        const markerColor = pending ? '#888' : '#f0c040';
        const markerOpacity = pending ? '0.55' : '1';
        const icon = pending ? '◈' : '★';
        html += `<text class="wloc-marker" data-locq="${loc.q}" data-locr="${loc.r}"
          x="${sx}" y="${sy - rz * 0.25}" text-anchor="middle"
          font-size="${Math.max(8, 14 * _wbZoom)}" fill="${markerColor}" opacity="${markerOpacity}"
          style="cursor:pointer;pointer-events:all">${icon}</text>`;
        if (_wbZoom >= 0.6) {
          html += `<text x="${sx}" y="${sy - rz * 0.52}" text-anchor="middle"
            font-size="${Math.max(6, 8 * _wbZoom)}" fill="${markerColor}" opacity="${markerOpacity}"
            style="pointer-events:none">${_esc((loc.label || '').slice(0, 12))}</text>`;
        }
      }
    }

    svg.innerHTML = html;
    svg.querySelectorAll('.whx,.whg').forEach(el => el.addEventListener('click', _wbOnHexClick));
    svg.querySelectorAll('.wloc-marker').forEach(el => el.addEventListener('click', _wbOnLocMarkerClick));
    const zl = document.getElementById('wb-zoom-label');
    if (zl) zl.textContent = `Zoom: ${Math.round(_wbZoom * 100)}%`;
  }

  async function _wbOnHexClick(e) {
    const q = parseInt(e.target.dataset.q), r = parseInt(e.target.dataset.r);
    if (_wbDrawingTp) {
      if (_wbDrawingTp.q === q && _wbDrawingTp.r === r) {
        _wbDrawingTp = null; _showToast('Anulowano.', 'info'); return;
      }
      await _wbCreateTeleport(_wbDrawingTp.q, _wbDrawingTp.r, q, r);
      _wbDrawingTp = null; return;
    }
    if (_wbPaintMode) {
      return;  // painting handled by drag (mousedown/move/up); avoids double-paint on click
    } else if (_wbHexes[_wbKey(q, r)]) {
      _wbSelected = {q, r}; _wbRender();
      const loc = _wbLocations[_wbKey(q, r)];
      if (loc) _wbShowLocationDetail(loc);
      else _wbRenderDetail(_wbHexes[_wbKey(q, r)]);
    } else await _wbPaint(q, r);
  }

  function _wbOnLocMarkerClick(e) {
    e.stopPropagation();
    const q = parseInt(e.target.dataset.locq), r = parseInt(e.target.dataset.locr);
    const loc = _wbLocations[_wbKey(q, r)];
    if (!loc) return;
    _wbSelected = {q, r}; _wbRender();
    _wbShowLocationDetail(loc);
  }

  function _wbShowLocationDetail(loc) {
    const p = document.getElementById('wb-detail');
    if (!p) return;
    const isPending = loc.pending;
    const statusBadge = isPending
      ? `<span class="badge badge-amber">⏳ Oczekuje</span>`
      : `<span class="badge badge-green">✓ Zatwierdzona</span>`;
    const sourceInfo = loc.source_campaign_id
      ? `<div style="font-size:0.72rem;color:var(--t3);margin-top:4px">Kampania #${loc.source_campaign_id}</div>` : '';
    p.innerHTML = `
      <div class="wb-dh" style="gap:6px">
        <span>⊕ Lokacja</span>
        ${statusBadge}
      </div>
      <div style="font-weight:600;font-size:0.9rem;margin:8px 0 2px">${_esc(loc.label || loc.key)}</div>
      <div style="font-size:0.72rem;color:var(--t3);font-family:monospace;margin-bottom:6px">${_esc(loc.key)}</div>
      ${loc.description ? `<div style="font-size:0.78rem;color:var(--t2);margin-bottom:8px;line-height:1.4">${_esc(loc.description.slice(0, 200))}${loc.description.length > 200 ? '…' : ''}</div>` : ''}
      ${sourceInfo}
      <div style="font-size:0.72rem;color:var(--t3);margin-bottom:10px">created_by: ${_esc(loc.created_by)} · hex (${loc.q},${loc.r})</div>
      ${isPending ? `<div style="display:flex;gap:6px">
        <button class="btn btn-sm btn-primary" onclick="_wbApproveLocation('${_esc(loc.key)}', this)">✓ Zatwierdź</button>
        <button class="btn btn-sm btn-danger" onclick="_wbDiscardLocation('${_esc(loc.key)}', this)">✕ Odrzuć</button>
      </div>` : `<div style="display:flex;flex-direction:column;gap:6px">
        <div style="font-size:0.78rem;color:var(--t3)">Lokacja globalna — widoczna w każdej kampanii.</div>
        <button class="btn btn-sm btn-secondary" onclick="_wbEnrichSublocs('${_esc(loc.key)}', this)">🪄 Nadaj nazwy LLM (sub-lokacje)</button>
      </div>`}
    `;
  }

  // #995 — Settlement subloc checklist modal before approving a location
  async function _approveLocationWithSublocs(key, btn, onSuccess) {
    btn.disabled = true; btn.textContent = '⏳';
    try {
      const defaults = await apiFetch(`/api/admin/world/locations/${key}/subloc-defaults`).catch(() => null);
      if (defaults && defaults.is_settlement && defaults.checklist && defaults.checklist.length) {
        btn.disabled = false; btn.textContent = '✓ Zatwierdź';
        await _showSublockChecklistModal(key, defaults, onSuccess);
      } else {
        if (!confirm(`Zatwierdzić lokację "${key}"?`)) { btn.disabled = false; btn.textContent = '✓ Zatwierdź'; return; }
        await apiFetch(`/api/admin/world/review/location/${key}`, { method: 'POST', body: JSON.stringify({ action: 'approve' }) });
        _showToast('Zatwierdzono.', 'success');
        onSuccess();
      }
    } catch(e) { _showToast(e.message || 'Błąd', 'error'); btn.disabled = false; btn.textContent = '✓ Zatwierdź'; }
  }

  function _showSublockChecklistModal(key, defaults, onSuccess) {
    return new Promise(resolve => {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay open';
      const items = defaults.checklist.map((c, i) => `
        <label style="display:flex;align-items:center;gap:8px;padding:5px 0;cursor:pointer">
          <input type="checkbox" data-subtype="${_esc(c.subtype)}" ${c.selected ? 'checked' : ''}>
          <span>${_esc(c.label)}</span>
          <span class="badge ${c.safe_for_rest ? 'badge-green' : 'badge-red'}" style="font-size:0.65rem;padding:1px 5px">${c.safe_for_rest ? '✓ nocleg' : '✕ ryzyko'}</span>
        </label>`).join('');
      overlay.innerHTML = `<div class="modal-box" style="max-width:420px">
        <div class="modal-head">
          <span class="modal-title">🏘 Zatwierdź + generuj pod-lokacje</span>
          <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="modal-body" style="padding:12px 16px">
          <div style="font-size:0.78rem;color:var(--t2);margin-bottom:10px">Osada: <strong>${_esc(key)}</strong> (${_esc(defaults.settlement_subtype)})</div>
          <div style="margin-bottom:4px;font-size:0.8rem;font-weight:600;color:var(--t1)">Wybierz pod-lokacje do wygenerowania:</div>
          <div id="subloc-checklist" style="display:flex;flex-direction:column;padding:4px 0">${items}</div>
          <div style="margin-top:12px;display:flex;gap:8px">
            <label style="display:flex;align-items:center;gap:6px;font-size:0.78rem;color:var(--t3);cursor:pointer">
              <input type="checkbox" id="subloc-none-checkbox">
              <span>Zatwierdź bez generowania</span>
            </label>
          </div>
        </div>
        <div class="modal-foot" style="padding:12px 16px;display:flex;justify-content:flex-end;gap:8px">
          <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
          <button class="btn btn-primary" id="subloc-confirm-btn">✓ Zatwierdź + generuj</button>
        </div>
      </div>`;
      document.body.appendChild(overlay);

      overlay.querySelector('#subloc-none-checkbox').addEventListener('change', e => {
        const confirmBtn = overlay.querySelector('#subloc-confirm-btn');
        const checkboxes = overlay.querySelectorAll('#subloc-checklist input[type="checkbox"]');
        checkboxes.forEach(cb => { cb.disabled = e.target.checked; });
        confirmBtn.textContent = e.target.checked ? '✓ Zatwierdź (bez pod-lokacji)' : '✓ Zatwierdź + generuj';
      });

      overlay.querySelector('#subloc-confirm-btn').addEventListener('click', async () => {
        const noneChecked = overlay.querySelector('#subloc-none-checkbox').checked;
        const selected = noneChecked ? [] :
          [...overlay.querySelectorAll('#subloc-checklist input[type="checkbox"]:checked')]
            .map(cb => cb.dataset.subtype);
        const confirmBtn = overlay.querySelector('#subloc-confirm-btn');
        confirmBtn.disabled = true; confirmBtn.textContent = '⏳';
        try {
          const body = { action: 'approve', generate_sublocs: selected.length ? selected : null };
          const res = await apiFetch(`/api/admin/world/review/location/${key}`, { method: 'POST', body: JSON.stringify(body) });
          const cnt = res.generated_sublocs ? res.generated_sublocs.length : 0;
          if (cnt > 0) {
            // #996 — show enrich button before closing modal
            const foot = overlay.querySelector('.modal-foot');
            foot.innerHTML = `
              <div style="width:100%;text-align:left;font-size:0.78rem;color:var(--t2)">
                ✓ Wygenerowano ${cnt} pod-lokacji.
              </div>
              <button class="btn btn-secondary" id="subloc-skip-enrich-btn">Zamknij</button>
              <button class="btn btn-primary" id="subloc-enrich-btn">🪄 Nadaj nazwy LLM</button>
            `;
            foot.querySelector('#subloc-skip-enrich-btn').addEventListener('click', () => {
              overlay.remove(); onSuccess(); resolve();
            });
            foot.querySelector('#subloc-enrich-btn').addEventListener('click', async () => {
              const eb = foot.querySelector('#subloc-enrich-btn');
              eb.disabled = true; eb.textContent = '⏳ Pytam LLM…';
              try {
                const er = await apiFetch(`/api/admin/world/locations/${key}/enrich-sublocs`, { method: 'POST', body: JSON.stringify({}) });
                _showToast(`🪄 Wzbogacono ${er.enriched} nazw sub-lokacji.`, 'success');
              } catch(e) {
                _showToast('Wzbogacanie nie powiodło się — sub-lokacje mają generyczne nazwy.', 'warn');
              }
              overlay.remove(); onSuccess(); resolve();
            });
          } else {
            _showToast('Zatwierdzono.', 'success');
            overlay.remove(); onSuccess(); resolve();
          }
        } catch(e) {
          _showToast(e.message || 'Błąd', 'error');
          confirmBtn.disabled = false; confirmBtn.textContent = '✓ Zatwierdź + generuj';
        }
      });
    });
  }

  async function _wbApproveLocation(key, btn) {
    await _approveLocationWithSublocs(key, btn, async () => {
      const lm = await apiFetch('/api/admin/world/locations-map').catch(() => ({ locations: [], pending_count: 0 }));
      _wbLocations = {};
      for (const loc of (lm.locations || [])) _wbLocations[_wbKey(loc.q, loc.r)] = loc;
      const badge = document.getElementById('map-pending-badge');
      if (badge) { const cnt = lm.pending_count || 0; badge.textContent = cnt ? `${cnt} oczekujące` : ''; badge.style.display = cnt ? '' : 'none'; }
      _wbRender();
      const updated = _wbLocations[_wbKey(lm.locations?.find(l=>l.key===key)?.q, lm.locations?.find(l=>l.key===key)?.r)];
      if (updated) _wbShowLocationDetail(updated);
    });
  }

  async function _wbDiscardLocation(key, btn) {
    if (!confirm(`Odrzucić i usunąć lokację "${key}"?`)) return;
    btn.disabled = true; btn.textContent = '⏳';
    try {
      await apiFetch(`/api/admin/world/review/location/${key}`, { method: 'POST', body: JSON.stringify({ action: 'discard' }) });
      _showToast('Odrzucona.', 'success');
      const k = Object.keys(_wbLocations).find(k2 => _wbLocations[k2].key === key);
      if (k) delete _wbLocations[k];
      const cnt = Object.values(_wbLocations).filter(l => l.pending).length;
      const badge = document.getElementById('map-pending-badge');
      if (badge) { badge.textContent = cnt ? `${cnt} oczekujące` : ''; badge.style.display = cnt ? '' : 'none'; }
      _wbRender(); _wbClearDetail();
    } catch(e) { _showToast(e.message || 'Błąd', 'error'); btn.disabled = false; btn.textContent = '✕ Odrzuć'; }
  }

  async function _wbEnrichSublocs(key, btn) {
    btn.disabled = true; btn.textContent = '⏳ Pytam LLM…';
    try {
      const res = await apiFetch(`/api/admin/world/locations/${key}/enrich-sublocs`, { method: 'POST', body: JSON.stringify({}) });
      if (res.enriched > 0) {
        _showToast(`🪄 Wzbogacono ${res.enriched} nazw sub-lokacji.`, 'success');
      } else {
        _showToast('Brak sub-lokacji do wzbogacenia (wszystkie już wzbogacone lub brak).', 'info');
      }
    } catch(e) {
      _showToast(e.message || 'Błąd wzbogacania.', 'error');
    }
    btn.disabled = false; btn.textContent = '🪄 Nadaj nazwy LLM (sub-lokacje)';
  }

  function _wbRenderThrottled() {
    if (_wbRenderRAF) return;
    _wbRenderRAF = requestAnimationFrame(() => { _wbRenderRAF = null; _wbRender(); });
  }

  function _wbHexUnderPoint(clientX, clientY) {
    const el = document.elementFromPoint(clientX, clientY);
    const poly = el && el.closest && el.closest('.whx,.whg');
    if (!poly) return null;
    return { q: parseInt(poly.dataset.q), r: parseInt(poly.dataset.r) };
  }

  // Paint one cell into the in-progress stroke (optimistic, local only).
  function _wbPaintCell(q, r) {
    if (!_wbPaintType || !_wbStroke) return;
    const key = _wbKey(q, r);
    if (_wbStroke.has(key)) return;                 // already painted this stroke
    const prev = _wbHexes[key] || null;
    if (prev && prev.hex_type === _wbPaintType) { _wbStroke.set(key, prev); return; }
    _wbStroke.set(key, prev ? JSON.parse(JSON.stringify(prev)) : null);
    const cfg = _wbHexTypes[_wbPaintType] || {};
    const enc = cfg.encounter_base_chance != null ? cfg.encounter_base_chance
              : (prev ? prev.encounter_chance : 0.15);
    _wbHexes[key] = { ...(prev || { q, r, label: null, atmosphere: null, encounter_pool: [] }),
                      q, r, hex_type: _wbPaintType, encounter_chance: enc };
    _wbRenderThrottled();
  }

  // Persist the finished stroke in one bulk call; record an undo entry.
  async function _wbCommitStroke() {
    const stroke = _wbStroke; _wbStroke = null;
    if (!stroke || stroke.size === 0) return;
    const keys = [...stroke.keys()];
    // drop no-op cells (painted same type they already were)
    const changed = keys.filter(k => {
      const before = stroke.get(k);
      return !(before && before.hex_type === _wbHexes[k]?.hex_type);
    });
    if (!changed.length) return;
    const items = changed.map(k => { const [q, r] = k.split(',').map(Number); return { q, r, before: stroke.get(k) }; });
    const payload = changed.map(k => { const h = _wbHexes[k]; return { q: h.q, r: h.r, hex_type: h.hex_type, encounter_chance: h.encounter_chance }; });
    try {
      const res = await apiFetch('/api/admin/world/hexes/bulk-paint', { method: 'POST', body: JSON.stringify({ hexes: payload }) });
      for (const h of (res.hexes || [])) _wbHexes[_wbKey(h.q, h.r)] = h;
      _wbPushUndo('paint', items);
      _wbRender();
      _showToast(`Pomalowano ${payload.length} ${payload.length === 1 ? 'hex' : 'heksów'}.`, 'success');
    } catch(e) {
      for (const it of items) { const k = _wbKey(it.q, it.r); if (it.before) _wbHexes[k] = it.before; else delete _wbHexes[k]; }
      _wbRender();
      _showToast(e.message || 'Błąd malowania', 'error');
    }
  }

  // Single-hex paint (click on empty ghost in select mode, or programmatic).
  async function _wbPaint(q, r) {
    if (!_wbPaintType) { _showToast('Wybierz typ terenu z palety.', 'info'); return; }
    _wbStroke = new Map();
    _wbPaintCell(q, r);
    await _wbCommitStroke();
    const h = _wbHexes[_wbKey(q, r)];
    if (h) { _wbSelected = { q, r }; _wbRenderDetail(h); }
  }

  function _wbPushUndo(kind, items) {
    if (!items || !items.length) return;
    _wbUndoStack.push({ kind, items });
    if (_wbUndoStack.length > 50) _wbUndoStack.shift();
    _wbUpdateUndoBtn();
  }

  function _wbUpdateUndoBtn() {
    const b = document.getElementById('wb-undo');
    if (!b) return;
    b.disabled = _wbUndoStack.length === 0;
    b.textContent = _wbUndoStack.length ? `↶ Cofnij (${_wbUndoStack.length})` : '↶ Cofnij';
  }

  // Recreate or update a hex so it fully matches `h` (used to undo delete/save).
  async function _wbRestoreFull(h) {
    const key = _wbKey(h.q, h.r);
    const body = { hex_type: h.hex_type, label: h.label ?? null, atmosphere: h.atmosphere ?? null,
                   encounter_chance: h.encounter_chance ?? 0.15, encounter_pool: h.encounter_pool || [] };
    if (_wbHexes[key]) {
      const res = await apiFetch(`/api/admin/world/hexes/${h.q}/${h.r}`, { method: 'PATCH', body: JSON.stringify(body) });
      _wbHexes[key] = res.hex;
    } else {
      const res = await apiFetch('/api/admin/world/hexes', { method: 'POST', body: JSON.stringify({ q: h.q, r: h.r, ...body }) });
      _wbHexes[key] = res.hex;
    }
  }

  async function _wbUndo() {
    const entry = _wbUndoStack.pop();
    _wbUpdateUndoBtn();
    if (!entry) { _showToast('Brak czego cofnąć.', 'info'); return; }
    const restore = entry.items.filter(i => i.before);
    const remove = entry.items.filter(i => !i.before);
    try {
      if (restore.length && entry.kind === 'paint') {
        const payload = restore.map(i => ({ q: i.before.q, r: i.before.r, hex_type: i.before.hex_type, encounter_chance: i.before.encounter_chance ?? 0.15 }));
        const res = await apiFetch('/api/admin/world/hexes/bulk-paint', { method: 'POST', body: JSON.stringify({ hexes: payload }) });
        for (const h of (res.hexes || [])) _wbHexes[_wbKey(h.q, h.r)] = h;
      } else {
        for (const i of restore) await _wbRestoreFull(i.before);
      }
      for (const i of remove) {
        await apiFetch(`/api/admin/world/hexes/${i.q}/${i.r}`, { method: 'DELETE' }).catch(() => {});
        delete _wbHexes[_wbKey(i.q, i.r)];
      }
      _wbSelected = null; _wbRender(); _wbClearDetail(); _wbUpdateUndoBtn();
      _showToast('Cofnięto ostatnią edycję.', 'success');
    } catch(e) {
      _wbUndoStack.push(entry); _wbUpdateUndoBtn();
      _showToast(e.message || 'Błąd cofania', 'error');
    }
  }

  async function _wbDeleteHex(q, r) {
    if (!confirm(`Usunąć hex (${q},${r})?`)) return;
    const before = _wbHexes[_wbKey(q, r)] ? JSON.parse(JSON.stringify(_wbHexes[_wbKey(q, r)])) : null;
    try {
      await apiFetch(`/api/admin/world/hexes/${q}/${r}`, { method: 'DELETE' });
      delete _wbHexes[_wbKey(q, r)]; _wbSelected = null; _wbRender(); _wbClearDetail();
      if (before) _wbPushUndo('full', [{ q, r, before }]);
      _showToast('Hex usunięty.', 'success');
    } catch(e) { _showToast(e.message || 'Błąd', 'error'); }
  }

  async function _wbSaveHex(q, r, updates) {
    const before = _wbHexes[_wbKey(q, r)] ? JSON.parse(JSON.stringify(_wbHexes[_wbKey(q, r)])) : null;
    try {
      const res = await apiFetch(`/api/admin/world/hexes/${q}/${r}`, { method: 'PATCH', body: JSON.stringify(updates) });
      _wbHexes[_wbKey(q, r)] = res.hex; _wbRender(); _wbRenderDetail(res.hex);
      if (before) _wbPushUndo('full', [{ q, r, before }]);
      _showToast('Zapisano.', 'success');
    } catch(e) { _showToast(e.message || 'Błąd', 'error'); }
  }

  async function _wbCreateTeleport(fq, fr, tq, tr) {
    const type = prompt('Typ: boat | magic | tunnel | portal', 'boat') || 'boat';
    const hours = parseFloat(prompt('Czas podróży (h):', '8') || '8');
    const label = (prompt('Etykieta (opcjonalna):', '') || '').trim() || null;
    try {
      const res = await apiFetch('/api/admin/world/teleport-connections', {
        method: 'POST', body: JSON.stringify({ from_q: fq, from_r: fr, to_q: tq, to_r: tr, travel_type: type, travel_hours: hours, label })
      });
      _wbTeleports.push(res.connection); _wbRender();
      _showToast(`Połączenie ${type} dodane.`, 'success');
    } catch(e) { _showToast(e.message || 'Błąd', 'error'); }
  }

  function _wbRenderDetail(hex) {
    const p = document.getElementById('wb-detail');
    if (!p) return;
    const cfg = _wbHexTypes[hex.hex_type] || {};
    const pool = (Array.isArray(hex.encounter_pool) ? hex.encounter_pool : []).join(',');
    const myTps = _wbTeleports.filter(t =>
      (t.from_q === hex.q && t.from_r === hex.r) || (t.to_q === hex.q && t.to_r === hex.r));

    p.innerHTML = `
      <div class="wb-dh">
        <span>${cfg.map_icon || '⬡'} (${hex.q},${hex.r})</span>
        <button class="btn-icon danger" id="wbd-del">✕</button>
      </div>
      <div id="wbd-safe" style="font-size:0.68rem;margin:2px 0 6px 0;color:var(--t3)">🛏 Sprawdzam…</div>
      <label class="wb-lbl">Typ terenu</label>
      <select id="wbd-type">${Object.entries(_wbHexTypes).map(([k,v]) =>
        `<option value="${k}"${k === hex.hex_type ? ' selected' : ''}>${v.map_icon || ''} ${v.label}</option>`).join('')}</select>
      <label class="wb-lbl">Etykieta</label>
      <input id="wbd-label" type="text" value="${_esc(hex.label || '')}" placeholder="np. Thornwood"/>
      <label class="wb-lbl">Atmosfera</label>
      <textarea id="wbd-atm" rows="2">${_esc(hex.atmosphere || '')}</textarea>
      <label class="wb-lbl">Szansa spotkania</label>
      <input id="wbd-enc" type="number" value="${hex.encounter_chance}" min="0" max="1" step="0.05"/>
      <label class="wb-lbl">Wrogowie (klucze, przecinkami)</label>
      <input id="wbd-pool" type="text" value="${_esc(pool)}"/>
      <div style="display:flex;gap:6px;margin-top:10px">
        <button class="primary-btn" id="wbd-save" style="flex:1;font-size:0.72rem;padding:5px 8px">Zapisz</button>
        <button class="secondary-btn" id="wbd-tp" style="font-size:0.72rem;padding:5px 8px" title="Połącz z innym hexem">⤷</button>
      </div>
      <button class="secondary-btn" id="wbd-treasure" style="width:100%;margin-top:6px;font-size:0.72rem;padding:5px 8px" title="Zakop skarb dla bohatera (mapa trafia do jego Map skarbów)">🗺 Zakop skarb</button>
      ${cfg.has_submap ? `<div style="display:flex;gap:4px;margin-top:6px"><select id="wbd-local-sz" style="background:var(--bg3);color:var(--t1);border:1px solid var(--border);border-radius:4px;padding:3px 4px;font-size:0.68rem;flex-shrink:0"><option value="1">S (7)</option><option value="2">M (19)</option><option value="3" selected>L (37)</option><option value="4">XL (61)</option></select><button id="wbd-gen-local" style="flex:1;font-size:0.7rem;padding:5px 6px;background:var(--bg3);border:1px solid var(--border);border-radius:5px;color:var(--t2);cursor:pointer">🏘️ Generuj podmapę</button></div>` : ''}
      <div style="margin-top:10px;font-size:0.68rem;color:var(--t3)">Połączenia specjalne:</div>
      ${myTps.length ? myTps.map(t => {
        const other = (t.from_q === hex.q && t.from_r === hex.r) ? `→(${t.to_q},${t.to_r})` : `←(${t.from_q},${t.from_r})`;
        return `<div style="display:flex;align-items:center;gap:4px;font-size:0.68rem;margin:2px 0">
          <span style="flex:1">${t.travel_type} ${other} ${t.travel_hours}h</span>
          <button class="btn-icon danger wbd-del-tp" data-id="${t.id}" style="font-size:0.6rem">✕</button>
        </div>`;
      }).join('') : `<span style="font-size:0.68rem;color:var(--t3)">Brak</span>`}`;

    _wbSafeRestBadge(p.querySelector('#wbd-safe'), hex.q, hex.r);
    p.querySelector('#wbd-del').onclick = () => _wbDeleteHex(hex.q, hex.r);
    p.querySelector('#wbd-save').onclick = () => _wbSaveHex(hex.q, hex.r, {
      hex_type: p.querySelector('#wbd-type').value,
      label: p.querySelector('#wbd-label').value.trim() || null,
      atmosphere: p.querySelector('#wbd-atm').value.trim() || null,
      encounter_chance: parseFloat(p.querySelector('#wbd-enc').value) || 0.15,
      encounter_pool: p.querySelector('#wbd-pool').value.split(',').map(s => s.trim()).filter(Boolean),
    });
    const _genLocalBtn = p.querySelector('#wbd-gen-local');
    if (_genLocalBtn) _genLocalBtn.onclick = async () => {
      const radius = parseInt(p.querySelector('#wbd-local-sz')?.value || '3');
      _genLocalBtn.disabled = true; _genLocalBtn.textContent = '⏳';
      try {
        const res = await apiFetch('/api/admin/world/generate-local', { method:'POST', body: JSON.stringify({parent_q: hex.q, parent_r: hex.r, seed: 0, radius}) });
        _showToast(`Wygenerowano ${res.hexes_created} lokalnych heksów.`, 'success');
        await openSubmapModal(hex.q, hex.r);
      } catch(e) { _showToast(e.message || 'Błąd', 'error'); }
      finally { _genLocalBtn.disabled = false; _genLocalBtn.textContent = '🏘️ Generuj podmapę'; }
    };
    p.querySelector('#wbd-tp').onclick = () => {
      _wbDrawingTp = { q: hex.q, r: hex.r };
      _showToast('Kliknij docelowy hex. Kliknij ten sam → anuluj.', 'info');
    };
    // #1196 — zakop skarb na tym hexie dla wskazanego bohatera (event content).
    const _treBtn = p.querySelector('#wbd-treasure');
    if (_treBtn) _treBtn.onclick = async () => {
      const cid = window.prompt('ID bohatera (character_id), który dostanie mapę:');
      if (!cid) return;
      const parts = parseInt(window.prompt('Liczba części mapy (1 = cała naraz):', '1') || '1') || 1;
      const label = window.prompt('Nazwa skarbu (opcjonalnie):', 'Mapa skarbu') || 'Mapa skarbu';
      const guardian = window.prompt('Klucz strażnika (opcjonalnie, puste = brak):', '') || null;
      try {
        const res = await apiFetch('/api/admin/world/treasures', {
          method: 'POST',
          body: JSON.stringify({
            hex_q: hex.q, hex_r: hex.r, character_id: parseInt(cid),
            total_parts: parts, label, guardian_enemy_key: guardian,
          }),
        });
        _showToast(`Skarb zakopany (#${res.treasure_id}) — mapa trafiła do bohatera ${cid}.`, 'success');
      } catch (e) { _showToast(e.message || 'Błąd zakopywania', 'error'); }
    };
    p.querySelectorAll('.wbd-del-tp').forEach(b => b.onclick = async () => {
      const id = parseInt(b.dataset.id);
      try {
        await apiFetch(`/api/admin/world/teleport-connections/${id}`, { method: 'DELETE' });
        _wbTeleports = _wbTeleports.filter(t => t.id !== id);
        _wbRender(); _wbRenderDetail(_wbHexes[_wbKey(hex.q, hex.r)]);
        _showToast('Połączenie usunięte.', 'success');
      } catch(e) { _showToast(e.message, 'error'); }
    });
  }

  async function _wbSafeRestBadge(el, q, r) {
    if (!el) return;
    try {
      const res = await apiFetch(`/api/admin/hex-safe/${q}/${r}`);
      const reason = res.reason || 'no_hex_record';
      const locLabel = res.location_label || res.location_key || '—';
      const cfg = {
        safe_via_location:        { g: '✅', t: `Bezpieczne — ${locLabel}`,      c: '#7ac76e' },
        unsafe_location_flag_off: { g: '⚠',  t: `Niebezpieczne — ${locLabel}`,  c: '#d97a4a' },
        wilderness_no_location:   { g: '🌲', t: 'Dzicz — brak lokacji',           c: '#9a9a9a' },
        unknown_location_key:     { g: '❓', t: `Nieznana lokacja (${res.location_key || '?'})`, c: '#c95c2e' },
        no_hex_record:            { g: '•',  t: 'Brak rekordu hexa',              c: '#666'    },
      }[reason] || { g: '?', t: reason, c: '#888' };
      el.innerHTML = `<span style="color:${cfg.c};font-weight:600">${cfg.g} ${_esc(cfg.t)}</span>`;
    } catch(e) {
      el.innerHTML = `<span style="color:#c95c2e">⚠ ${_esc(e.message || '?')}</span>`;
    }
  }

  function _wbClearDetail() {
    const p = document.getElementById('wb-detail');
    if (p) p.innerHTML = '<div style="color:var(--t3);font-size:0.78rem">Kliknij hex aby edytować lub puste miejsce aby pomalować.</div>';
  }

  function _wbRenderPalette() {
    const pal = document.getElementById('wb-palette');
    if (!pal) return;
    pal.innerHTML = Object.entries(_wbHexTypes).map(([k,v]) =>
      `<button class="wb-pb${_wbPaintType === k ? ' active' : ''}" data-type="${k}"
        style="background:${v.map_color};color:#e8e4dc" title="${_esc(v.label)}">${v.map_icon || '⬡'}</button>`
    ).join('');
    pal.querySelectorAll('.wb-pb').forEach(b => b.onclick = () => {
      _wbPaintType = b.dataset.type === _wbPaintType ? null : b.dataset.type; _wbDrawingTp = null; _wbRenderPalette(); _wbRender();
    });
    const mSelect = document.getElementById('wb-mode-select');
    const mPaint = document.getElementById('wb-mode-paint');
    if (mSelect && mPaint) {
      mSelect.className = `btn btn-sm ${!_wbPaintMode ? 'btn-primary' : 'btn-secondary'}`;
      mPaint.className = `btn btn-sm ${_wbPaintMode ? 'btn-primary' : 'btn-secondary'}`;
      mSelect.onclick = () => { _wbPaintMode = false; _wbRenderPalette(); _wbRender(); };
      mPaint.onclick = () => { _wbPaintMode = true; _wbRenderPalette(); _wbRender(); };
    }
    const locOverlayBtn = document.getElementById('wb-loc-overlay');
    if (locOverlayBtn) locOverlayBtn.onclick = () => {
      _wbShowLocOverlay = !_wbShowLocOverlay;
      locOverlayBtn.className = `btn btn-sm ${_wbShowLocOverlay ? 'btn-primary' : 'btn-secondary'}`;
      _wbRender();
    };
    const undoBtn = document.getElementById('wb-undo');
    if (undoBtn) { undoBtn.onclick = _wbUndo; _wbUpdateUndoBtn(); }
    const saveBtn = document.getElementById('wb-save-canon');
    if (saveBtn) saveBtn.onclick = async () => {
      // #1482: przy wybranej krainie zapisujemy TYLKO ją — nie mieszamy krain w jednym pliku.
      const rq = _wbActiveRegion ? `?region=${encodeURIComponent(_wbActiveRegion)}` : '';
      const scope = _wbActiveRegion ? `krainę „${_wbActiveRegion}"` : 'WSZYSTKIE krainy';
      if (!confirm(`Zapisać ${scope} jako KANON?\n\nStanie się bazą odtwarzaną po każdym resecie/wipe DB. Nadpisze poprzedni zapis.`)) return;
      const orig = saveBtn.textContent; saveBtn.disabled = true; saveBtn.textContent = '💾 Zapisuję…';
      try {
        const res = await apiFetch(`/api/admin/world/map/snapshot${rq}`, { method: 'POST' });
        _showToast(`Mapa zapisana jako kanon (${res.count} heksów). Przeżyje reset DB.`, 'success');
      } catch (e) {
        _showToast('Błąd zapisu mapy: ' + (e && e.message ? e.message : e), 'error');
      } finally { saveBtn.disabled = false; saveBtn.textContent = orig; }
    };
    const restoreBtn = document.getElementById('wb-restore-canon');
    if (restoreBtn) restoreBtn.onclick = async () => {
      // #1482: bez wybranej krainy backend odmówi (403) — pełny restore kasował wszystkie krainy.
      if (!_wbActiveRegion) {
        _showToast('Wybierz krainę na liście po lewej — odtwarzamy mapę per kraina (#1482).', 'warn');
        return;
      }
      if (!confirm(`Wczytać krainę „${_wbActiveRegion}" z KANONU?\n\nNadpisze heksy TEJ krainy wersją z pliku data/regions/. Tej operacji nie można cofnąć.`)) return;
      const orig = restoreBtn.textContent; restoreBtn.disabled = true; restoreBtn.textContent = '📂 Wczytuję…';
      try {
        const res = await apiFetch(`/api/admin/world/map/restore?region=${encodeURIComponent(_wbActiveRegion)}`, { method: 'POST' });
        _showToast(`Mapa odtworzona z kanonu (${res.count} heksów).`, 'success');
        await _wbLoadHexes();
        _wbRender();
      } catch (e) {
        _showToast('Błąd wczytywania mapy: ' + (e && e.message ? e.message : e), 'error');
      } finally { restoreBtn.disabled = false; restoreBtn.textContent = orig; }
    };
  }

  async function _wbLoadHexes() {
    const url = _wbActiveRegion
      ? `/api/admin/world/map?region=${encodeURIComponent(_wbActiveRegion)}`
      : '/api/admin/world/map';
    const m = await apiFetch(url);
    _wbHexes = {};
    for (const h of (m.hexes || [])) _wbHexes[_wbKey(h.q, h.r)] = h;
    _wbTeleports = m.teleport_connections || [];
    if (m.regions && m.regions.length) _wbRegions = m.regions;
    _wbUndoStack = [];
    _wbUpdateUndoBtn();
    const svg = document.getElementById('wb-svg');
    if (svg) {
      const active = _wbActiveRegion ? _wbRegions.find(r => r.key === _wbActiveRegion) : null;
      svg.style.background = active ? `color-mix(in srgb, ${active.color} 8%, #080608)` : '#080608';
    }
  }

  function _wbCenter() {
    const svg = document.getElementById('wb-svg');
    if (!svg) return;
    const svgRect = svg.getBoundingClientRect();
    const W = Math.max(200, svgRect.width || 900);
    const H = Math.max(200, svgRect.height || 600);
    const list = Object.values(_wbHexes);
    if (!list.length) { _wbPan = { x: W / 2, y: H / 2 }; _wbZoom = 1; return; }
    const px = list.map(h => _wbHexToPixel(h.q, h.r).x);
    const py = list.map(h => _wbHexToPixel(h.q, h.r).y);
    const minX = Math.min(...px), maxX = Math.max(...px);
    const minY = Math.min(...py), maxY = Math.max(...py);
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
    const spanX = (maxX - minX) + _WB_SIZE * 3;
    const spanY = (maxY - minY) + _WB_SIZE * 3;
    _wbZoom = list.length === 1 ? 1 : Math.max(0.08, Math.min(1.5, Math.min(W / spanX, H / spanY)));
    _wbPan = { x: W / 2 - cx * _wbZoom, y: H / 2 - cy * _wbZoom };
  }

  function wbCenter() { _wbCenter(); _wbRender(); }

  async function _loadBuilder() {
    const svg = document.getElementById('wb-svg');
    if (!svg) return;

    _wbHexes = {}; _wbTeleports = []; _wbLocations = {}; _wbSelected = null;
    _wbZoom = 1; _wbPan = { x: 400, y: 280 }; _wbDrawingTp = null;
    _wbUndoStack = []; _wbPainting = false; _wbStroke = null;

    try {
      const [m, t, lm] = await Promise.all([
        apiFetch('/api/admin/world/map'),
        apiFetch('/api/admin/world/hex-types'),
        apiFetch('/api/admin/world/locations-map').catch(() => ({ locations: [], pending_count: 0 })),
      ]);
      for (const h of (m.hexes || [])) _wbHexes[_wbKey(h.q, h.r)] = h;
      _wbTeleports = m.teleport_connections || [];
      if (m.regions && m.regions.length) _wbRegions = m.regions;
      _wbHexTypes = {};
      for (const ht of (t.hex_types || [])) _wbHexTypes[ht.hex_type] = ht;
      _wbLocations = {};
      for (const loc of (lm.locations || [])) _wbLocations[_wbKey(loc.q, loc.r)] = loc;
      const badge = document.getElementById('map-pending-badge');
      if (badge) {
        const cnt = lm.pending_count || 0;
        badge.textContent = cnt ? `${cnt} oczekujące` : '';
        badge.style.display = cnt ? '' : 'none';
      }
    } catch(e) {
      const detail = document.getElementById('wb-detail');
      if (detail) detail.innerHTML = `<div style="color:var(--err);padding:12px">Błąd ładowania mapy: ${_esc(e.message)}</div>`;
      return;
    }

    _wbRenderPalette();
    _wbRenderRegionBar();

    // Wheel zoom
    svg.addEventListener('wheel', (e) => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const f = e.deltaY < 0 ? 1.15 : 0.87;
      const nz = Math.max(0.12, Math.min(5, _wbZoom * f));
      _wbPan.x = mx - (mx - _wbPan.x) * (nz / _wbZoom);
      _wbPan.y = my - (my - _wbPan.y) * (nz / _wbZoom);
      _wbZoom = nz; _wbRender();
    }, { passive: false });

    // Pan drag (alt/middle) + paint drag (left button in paint mode). Wired once per svg.
    if (!svg._wbDragWired) {
      let _wbDs = null;
      svg.addEventListener('mousedown', (e) => {
        if (e.button === 1 || (e.button === 0 && e.altKey)) {
          _wbDs = { x: e.clientX - _wbPan.x, y: e.clientY - _wbPan.y }; e.preventDefault();
          return;
        }
        if (e.button === 0 && _wbPaintMode && _wbPaintType) {
          const cell = _wbHexUnderPoint(e.clientX, e.clientY);
          if (!cell) return;
          e.preventDefault();
          _wbPainting = true; _wbStroke = new Map();
          _wbPaintCell(cell.q, cell.r);
        }
      });
      window.addEventListener('mousemove', (e) => {
        if (_wbDs) { _wbPan = { x: e.clientX - _wbDs.x, y: e.clientY - _wbDs.y }; _wbRender(); return; }
        if (_wbPainting) { const c = _wbHexUnderPoint(e.clientX, e.clientY); if (c) _wbPaintCell(c.q, c.r); }
      });
      window.addEventListener('mouseup', () => {
        _wbDs = null;
        if (_wbPainting) { _wbPainting = false; _wbCommitStroke(); }
      });
      // Ctrl/Cmd+Z → undo last edit (only while builder tab is visible, not while typing)
      window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z')) {
          const root = document.getElementById('wb-root');
          if (!root || !root.offsetParent) return;          // builder tab not visible
          const tag = (document.activeElement?.tagName || '').toLowerCase();
          if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
          e.preventDefault(); _wbUndo();
        }
      });
      // Touch: pinch-zoom + 1-finger pan + tap-to-edit (M5)
      let _wbTs = null;
      svg.addEventListener('touchstart', (e) => {
        e.preventDefault();
        if (e.touches.length === 1) {
          _wbTs = { type: 'pan', x: e.touches[0].clientX, y: e.touches[0].clientY,
            px: _wbPan.x, py: _wbPan.y, moved: false };
        } else if (e.touches.length === 2) {
          const dx = e.touches[1].clientX - e.touches[0].clientX;
          const dy = e.touches[1].clientY - e.touches[0].clientY;
          const rect = svg.getBoundingClientRect();
          _wbTs = { type: 'pinch', dist: Math.hypot(dx, dy), zoom: _wbZoom,
            px: _wbPan.x, py: _wbPan.y,
            midX: (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left,
            midY: (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top };
        }
      }, { passive: false });
      svg.addEventListener('touchmove', (e) => {
        e.preventDefault();
        if (!_wbTs) return;
        if (_wbTs.type === 'pan' && e.touches.length === 1) {
          const dx = e.touches[0].clientX - _wbTs.x;
          const dy = e.touches[0].clientY - _wbTs.y;
          if (Math.abs(dx) > 3 || Math.abs(dy) > 3) _wbTs.moved = true;
          _wbPan = { x: _wbTs.px + dx, y: _wbTs.py + dy };
          _wbRender();
        } else if (_wbTs.type === 'pinch' && e.touches.length === 2) {
          const dx = e.touches[1].clientX - e.touches[0].clientX;
          const dy = e.touches[1].clientY - e.touches[0].clientY;
          const dist = Math.hypot(dx, dy);
          const nz = Math.max(0.12, Math.min(5, _wbTs.zoom * (dist / _wbTs.dist)));
          _wbPan.x = _wbTs.midX - (_wbTs.midX - _wbTs.px) * (nz / _wbTs.zoom);
          _wbPan.y = _wbTs.midY - (_wbTs.midY - _wbTs.py) * (nz / _wbTs.zoom);
          _wbZoom = nz;
          _wbRender();
        }
      }, { passive: false });
      svg.addEventListener('touchend', (e) => {
        if (_wbTs?.type === 'pan' && !_wbTs.moved) {
          const t = e.changedTouches[0];
          const el = document.elementFromPoint(t.clientX, t.clientY);
          if (el) {
            if (el.classList.contains('whx') || el.classList.contains('whg'))
              _wbOnHexClick({ target: el });
            else if (el.classList.contains('wloc-marker'))
              _wbOnLocMarkerClick({ target: el });
          }
        }
        _wbTs = null;
      });
      svg._wbDragWired = true;
    }
    _wbUpdateUndoBtn();

    // ResizeObserver for re-render on container resize
    if (typeof ResizeObserver !== 'undefined' && !svg._wbRO) {
      const ro = new ResizeObserver(() => _wbRender());
      ro.observe(svg); svg._wbRO = true;
    }

    // Auto-center with layout settle retry
    let attempts = 0;
    const tryCenter = () => {
      const r = svg.getBoundingClientRect();
      if ((r.width < 50 || r.height < 50) && attempts < 10) { attempts++; setTimeout(tryCenter, 50); return; }
      _wbCenter(); _wbRender();
    };
    requestAnimationFrame(tryCenter);
  }

// ── Location image generation ──────────────────────────────────────────────────
  function _buildLocImagePrompt(loc) {
    const typeMap = {
      dungeon:'dark dungeon interior, torchlit stone corridors',
      town:'medieval fantasy town square, cobblestone streets',
      city:'medieval fantasy city, stone buildings, busy streets',
      wilderness:'open wilderness landscape, untamed nature',
      building:'fantasy building interior, wooden beams',
      cave:'deep cave chamber, stalactites, bioluminescent glow',
      camp:'campsite in ancient forest, firelight',
      ruins:'ancient crumbling ruins, moss-covered stone',
      forest:'dense enchanted forest, rays of light through canopy',
      road:'winding dirt road through forest',
      tavern:'cozy medieval tavern interior, fireplace',
      temple:'ancient stone temple, mystical atmosphere',
      tower:'stone wizard tower interior',
      harbor:'fantasy harbor, sailing ships, misty sea',
      market:'bustling medieval market, colorful stalls',
    };
    const biomeMap = {
      ruin:'ruined stone architecture',forest:'ancient woodland',
      mountain:'rocky mountain terrain',urban:'stone city architecture',
      underground:'underground cavern',coast:'coastal sea cliffs',
      swamp:'misty swamp bog',plains:'open grassy plains',
      desert:'arid desert landscape',tundra:'frozen tundra',
    };
    const moodMap = {
      safe:'warm welcoming light',dangerous:'ominous dark atmosphere',
      mysterious:'eerie mystical fog',sacred:'divine golden light',
    };
    const type = typeMap[loc.location_type] || typeMap[loc.location_subtype] || 'fantasy RPG location';
    const biome = biomeMap[loc.biome] || '';
    const mood = loc.safe_for_rest ? moodMap.safe : (moodMap[loc.mood] || '');
    const tier = loc.tier ? `tier ${loc.tier} difficulty area` : '';
    const parts = [biome, type, mood, tier, 'fantasy RPG location art, atmospheric illustrated style, moody cinematic lighting, detailed, no text, no letters, no UI'].filter(Boolean);
    return parts.join(', ');
  }

  async function openLocImageModal(key, loc) {
    if (typeof loc === 'string') { try { loc = JSON.parse(decodeURIComponent(loc)); } catch(_) { loc = {key}; } }

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.id = 'loc-img-overlay';

    let _liRefB64 = '', _liRefFilename = '', _liPendingUrl = '', _liPendingFilename = '';

    const render = () => {
      const hasRef = !!(_liRefB64 || _liRefFilename);
      overlay.innerHTML = `<div class="modal-box" style="max-width:660px;max-height:92vh;display:flex;flex-direction:column">
        <div class="modal-head">
          <span class="modal-title">🎨 Obraz — ${_esc(loc.label || loc.key)}</span>
          <button class="modal-close" id="li-close">✕</button>
        </div>
        <div class="modal-body" style="padding:14px 16px;display:flex;flex-direction:column;gap:12px;overflow-y:auto;flex:1">

          <!-- Living Prompt -->
          <div>
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
              <label class="form-label" style="margin:0">Prompt</label>
              <span class="li-trans-badge" style="display:inline-flex;align-items:center;gap:4px;font-size:0.65rem;padding:1px 6px;background:var(--blue-light);color:var(--blue-text);border-radius:var(--r-sm);border:1px solid var(--blue-border)" title="AI doda tłumaczenie opisu lokacji">✦ auto</span>
              <button id="li-rebuild-prompt" class="btn btn-sm btn-secondary" style="font-size:0.65rem;padding:1px 5px;margin-left:auto">↺ Odbuduj</button>
            </div>
            <textarea id="li-prompt" class="form-input" rows="3" style="resize:none;font-size:0.8rem;border-left:2px solid #0d9488;width:100%;box-sizing:border-box;overflow:hidden;field-sizing:content;min-height:72px;max-height:240px">${_esc(_buildLocImagePrompt(loc))}</textarea>
          </div>

          <!-- Style reference -->
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span style="font-size:0.7rem;font-weight:600;color:var(--t3);text-transform:uppercase;letter-spacing:.05em">Styl ref:</span>
            ${_liRefFilename || _liRefB64 ? `
              <img src="${_liRefFilename ? '/images/tiles/'+_esc(_liRefFilename) : 'data:image/png;base64,'+_liRefB64.slice(0,20)+'...'}" style="height:32px;width:32px;object-fit:cover;border-radius:var(--r-sm);border:1px solid var(--border)">
              <span style="font-size:0.7rem;color:var(--t2)">${_esc(_liRefFilename || 'upload')}</span>
              <button id="li-ref-clear" class="btn btn-sm btn-danger" style="font-size:0.65rem;padding:1px 5px">✕</button>
              <div style="display:flex;align-items:center;gap:6px;flex:1;min-width:140px">
                <label style="font-size:0.68rem;color:var(--t3);white-space:nowrap">Wpływ: <span id="li-denoise-val">60%</span></label>
                <input type="range" id="li-denoise" min="10" max="90" value="60" style="flex:1;accent-color:#0d9488">
              </div>
            ` : `
              <label class="btn btn-sm btn-secondary" style="cursor:pointer;font-size:0.7rem;padding:2px 8px">📎 Upload<input type="file" id="li-ref-upload" accept="image/*" style="display:none"></label>
              <button id="li-ref-gallery" class="btn btn-sm btn-secondary" style="font-size:0.7rem;padding:2px 8px">🖼 Z galerii</button>
            `}
          </div>

          <!-- Controls row -->
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <select id="li-size" class="form-input" style="width:auto;font-size:0.78rem;padding:5px 8px">
              <option value="576x1024" selected>576×1024 portret ★</option>
              <option value="768x1024">768×1024 portret 3:4</option>
              <option value="512x512">512×512</option>
              <option value="768x768">768×768</option>
              <option value="1024x576">1024×576 pejzaż</option>
            </select>
            <label style="font-size:0.7rem;color:var(--t3);white-space:nowrap">Kroki: <span id="li-steps-val">6</span></label>
            <input type="range" id="li-steps" min="4" max="16" value="6" style="flex:1;min-width:80px;accent-color:var(--blue)">
            <button id="li-pick-gallery" class="btn btn-secondary" style="white-space:nowrap;font-size:0.78rem" title="Wybierz istniejący obraz z galerii">🖼 Galeria</button>
            <button id="li-gen-btn" class="btn btn-primary" style="white-space:nowrap">${hasRef ? '🔄 Refinuj' : '🎨 Generuj'}</button>
          </div>

          <!-- Preview -->
          <div id="li-preview" style="width:100%;min-height:280px;background:#1e1e2e;border-radius:var(--r);display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative">
            ${_liPendingUrl
              ? `<img src="${_esc(_liPendingUrl)}" style="max-width:100%;max-height:480px;object-fit:contain">
                 <div style="position:absolute;bottom:0;right:0;background:rgba(0,0,0,0.6);color:#aaa;font-size:0.62rem;padding:2px 6px;border-radius:var(--r-sm) 0 var(--r-sm) 0">${_esc(_liPendingFilename)}</div>
                 <div style="position:absolute;top:6px;left:6px;background:rgba(0,0,0,0.55);color:#ccc;font-size:0.65rem;padding:2px 8px;border-radius:var(--r-sm)">Edytuj prompt ↑ i kliknij Generuj ponownie</div>`
              : loc.image_url
                ? `<img src="${_esc(loc.image_url)}" style="max-width:100%;max-height:480px;object-fit:contain">
                   <div style="position:absolute;top:6px;left:6px;background:rgba(5,150,105,0.85);color:#fff;font-size:0.62rem;padding:2px 6px;border-radius:var(--r-sm)">✓ Aktualny obraz</div>`
                : `<div style="text-align:center;color:#555"><div style="font-size:2rem;opacity:.3">🖼</div><div style="font-size:0.75rem;margin-top:4px">Brak obrazu — wygeneruj poniżej</div></div>`
            }
          </div>
        </div>
        <div class="modal-foot" style="display:flex;justify-content:space-between;align-items:center;padding:10px 16px;gap:8px;flex-wrap:wrap;flex-shrink:0;border-top:1px solid var(--border)">
          <div style="display:flex;gap:6px">
            ${loc.image_url ? `<button id="li-remove-btn" class="btn btn-secondary" style="color:var(--red);font-size:0.78rem">✕ Usuń obraz</button>` : ''}
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            ${_liPendingUrl ? `<span style="font-size:0.65rem;color:var(--t3)">edytuj prompt i kliknij Generuj ponownie</span>` : ''}
            <button id="li-cancel" class="btn btn-secondary">Anuluj</button>
            ${_liPendingUrl ? `<button id="li-accept-btn" class="btn btn-primary">✓ Zatwierdź obraz</button>` : ''}
          </div>
        </div>
      </div>`;

      // Wire close / cancel
      overlay.querySelector('#li-close').onclick = () => overlay.remove();
      overlay.querySelector('#li-cancel').onclick = () => overlay.remove();
      overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };

      // Auto-resize textarea helper
      const _autoResize = ta => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 240) + 'px'; };
      const promptEl = overlay.querySelector('#li-prompt');
      if (promptEl) { promptEl.oninput = () => _autoResize(promptEl); requestAnimationFrame(() => _autoResize(promptEl)); }

      // Rebuild prompt
      const rebuildBtn = overlay.querySelector('#li-rebuild-prompt');
      if (rebuildBtn) rebuildBtn.onclick = () => {
        if (promptEl) { promptEl.value = _buildLocImagePrompt(loc); _autoResize(promptEl); }
      };

      // Steps slider
      const stepsEl = overlay.querySelector('#li-steps');
      const stepsVal = overlay.querySelector('#li-steps-val');
      if (stepsEl) stepsEl.oninput = () => { if (stepsVal) stepsVal.textContent = stepsEl.value; };

      // Denoise slider
      const denoiseEl = overlay.querySelector('#li-denoise');
      const denoiseVal = overlay.querySelector('#li-denoise-val');
      if (denoiseEl) denoiseEl.oninput = () => { if (denoiseVal) denoiseVal.textContent = denoiseEl.value + '%'; };

      // Ref clear
      const refClear = overlay.querySelector('#li-ref-clear');
      if (refClear) refClear.onclick = () => { _liRefB64 = ''; _liRefFilename = ''; render(); };

      // Ref upload
      const uploadEl = overlay.querySelector('#li-ref-upload');
      if (uploadEl) uploadEl.onchange = e => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = ev => {
          _liRefB64 = ev.target.result.split(',')[1];
          _liRefFilename = '';
          render();
        };
        reader.readAsDataURL(file);
      };

      // Ref gallery
      const galleryBtn = overlay.querySelector('#li-ref-gallery');
      if (galleryBtn) galleryBtn.onclick = async () => {
        try {
          const d = await apiFetch('/api/admin/images/list');
          const imgs = d.images || [];
          if (!imgs.length) { _showToast('Brak obrazów w galerii', 'warn'); return; }
          // Mini gallery picker
          const pick = document.createElement('div');
          pick.className = 'modal-overlay open';
          pick.style.zIndex = '10002';
          pick.innerHTML = `<div class="modal-box" style="max-width:520px">
            <div class="modal-head"><span>Wybierz referencję styl</span><button id="pick-x">✕</button></div>
            <div style="padding:12px;display:grid;grid-template-columns:repeat(4,1fr);gap:8px;max-height:340px;overflow-y:auto">
              ${imgs.map(img => `<div style="aspect-ratio:1;cursor:pointer;border-radius:var(--r-sm);overflow:hidden;border:2px solid transparent" data-fn="${_esc(img.filename)}" class="li-pick-thumb">
                <img src="${_esc(img.url)}" style="width:100%;height:100%;object-fit:cover" loading="lazy">
              </div>`).join('')}
            </div>
          </div>`;
          document.body.appendChild(pick);
          pick.querySelector('#pick-x').onclick = () => pick.remove();
          pick.onclick = e => { if (e.target === pick) pick.remove(); };
          pick.querySelectorAll('.li-pick-thumb').forEach(el => {
            el.onmouseenter = () => el.style.borderColor = 'var(--blue)';
            el.onmouseleave = () => el.style.borderColor = 'transparent';
            el.onclick = () => {
              _liRefFilename = el.dataset.fn;
              _liRefB64 = '';
              pick.remove();
              render();
            };
          });
        } catch(e) { _showToast('Błąd galerii: ' + e.message, 'error'); }
      };

      // Pick existing image from gallery → assign directly (no generation)
      const pickGalleryBtn = overlay.querySelector('#li-pick-gallery');
      if (pickGalleryBtn) pickGalleryBtn.onclick = async () => {
        try {
          const d = await apiFetch('/api/admin/images/list');
          const imgs = d.images || [];
          if (!imgs.length) { _showToast('Brak obrazów w galerii', 'warn'); return; }
          const pick = document.createElement('div');
          pick.className = 'modal-overlay open';
          pick.style.zIndex = '10002';
          pick.innerHTML = `<div class="modal-box" style="max-width:580px;max-height:90vh;display:flex;flex-direction:column">
            <div class="modal-head" style="flex-shrink:0"><span>Wybierz obraz dla lokacji</span><button id="lpick-x">✕</button></div>
            <div style="padding:12px;display:grid;grid-template-columns:repeat(4,1fr);gap:8px;overflow-y:auto;flex:1">
              ${imgs.map(img => `<div style="cursor:pointer;border-radius:var(--r-sm);overflow:hidden;border:2px solid transparent;position:relative" data-fn="${_esc(img.filename)}" data-url="${_esc(img.url)}" class="lpick-thumb">
                <img src="${_esc(img.url)}" style="width:100%;aspect-ratio:1;object-fit:cover;display:block" loading="lazy">
                <div style="position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,0.6);font-size:0.58rem;color:#aaa;padding:2px 4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_esc(img.filename)}</div>
              </div>`).join('')}
            </div>
          </div>`;
          document.body.appendChild(pick);
          pick.querySelector('#lpick-x').onclick = () => pick.remove();
          pick.onclick = e => { if (e.target === pick) pick.remove(); };
          pick.querySelectorAll('.lpick-thumb').forEach(el => {
            el.onmouseenter = () => el.style.borderColor = 'var(--green,#10b981)';
            el.onmouseleave = () => el.style.borderColor = 'transparent';
            el.onclick = () => {
              _liPendingUrl = el.dataset.url;
              _liPendingFilename = el.dataset.fn;
              pick.remove();
              render();
            };
          });
        } catch(e) { _showToast('Błąd galerii: ' + e.message, 'error'); }
      };

      // Generate / Refine
      const genBtn = overlay.querySelector('#li-gen-btn');
      if (genBtn) genBtn.onclick = async () => {
        const prompt = overlay.querySelector('#li-prompt').value.trim();
        if (!prompt) { _showToast('Prompt wymagany', 'warn'); return; }
        const sizeVal = overlay.querySelector('#li-size').value;
        const [w, h] = sizeVal.split('x').map(Number);
        const steps = parseInt(overlay.querySelector('#li-steps').value);
        const denoise = denoiseEl ? parseInt(denoiseEl.value) / 100 : 0.6;

        genBtn.disabled = true;
        genBtn.textContent = '⏳…';
        const preview = overlay.querySelector('#li-preview');
        preview.innerHTML = '<div style="text-align:center;color:#555"><div class="img-spinner"></div><div style="font-size:0.75rem;margin-top:8px;color:#888">Generowanie…</div></div>';

        try {
          let data;
          if (_liRefFilename) {
            data = await apiFetch('/api/admin/images/refine', { method:'POST', body: JSON.stringify({ source_filename: _liRefFilename, prompt, denoise, steps }) });
          } else if (_liRefB64) {
            data = await apiFetch('/api/admin/images/refine-upload', { method:'POST', body: JSON.stringify({ upload_b64: _liRefB64, prompt, denoise, steps }) });
          } else {
            data = await apiFetch('/api/admin/images/generate', { method:'POST', body: JSON.stringify({ prompt, width: w, height: h, steps }) });
          }
          _liPendingUrl = data.url;
          _liPendingFilename = data.filename;
          render();
        } catch(e) {
          _showToast('Błąd: ' + e.message, 'error');
          preview.innerHTML = `<div style="color:var(--red);font-size:0.78rem;text-align:center;padding:20px">Błąd: ${_esc(e.message)}</div>`;
        } finally {
          genBtn.disabled = false;
          genBtn.textContent = (_liRefB64 || _liRefFilename) ? '🔄 Refinuj' : '🎨 Generuj';
        }
      };

      // Accept
      const acceptBtn = overlay.querySelector('#li-accept-btn');
      if (acceptBtn) acceptBtn.onclick = async () => {
        console.log('[loc-img] accept clicked, key=', key, 'pendingUrl=', _liPendingUrl);
        try {
          const patchUrl = `/api/locations/admin/locations/${encodeURIComponent(key)}`;
          console.log('[loc-img] sending PATCH to', patchUrl);
          await apiFetch(patchUrl, {
            method: 'PATCH',
            body: JSON.stringify({ image_url: _liPendingUrl })
          });
          loc.image_url = _liPendingUrl;
          // Immediately update data-rjson on the row so edit modal shows fresh data
          const locRow = document.querySelector(`#locations-table tr[data-key="${CSS.escape(key)}"]`);
          if (locRow) locRow.dataset.rjson = encodeURIComponent(JSON.stringify(loc));
          _liPendingUrl = '';
          _liPendingFilename = '';
          _showToast('Obraz przypisany do lokacji ✓', 'success');
          render();
          _worldLoaded.delete('locations');
          _loadLocations();
        } catch(e) {
          console.error('[loc-img] accept error:', e);
          _showToast('Błąd zapisu: ' + e.message, 'error');
        }
      };

      // Remove existing image
      const removeBtn = overlay.querySelector('#li-remove-btn');
      if (removeBtn) removeBtn.onclick = async () => {
        if (!confirm('Usunąć obraz z lokacji?')) return;
        try {
          await apiFetch(`/api/locations/admin/locations/${encodeURIComponent(key)}`, {
            method: 'PATCH',
            body: JSON.stringify({ image_url: null })
          });
          loc.image_url = null;
          const locRowRm = document.querySelector(`#locations-table tr[data-key="${CSS.escape(key)}"]`);
          if (locRowRm) locRowRm.dataset.rjson = encodeURIComponent(JSON.stringify(loc));
          _showToast('Obraz usunięty.', 'info');
          render();
          _worldLoaded.delete('locations');
          _loadLocations();
        } catch(e) { _showToast('Błąd: ' + e.message, 'error'); }
      };
    };

    document.body.appendChild(overlay);
    render();

    // Async: translate Polish description → English keywords, inject into prompt
    if (loc.description && loc.description.trim()) {
      const context = [loc.location_type, loc.biome, loc.location_subtype].filter(Boolean).join(', ');
      apiFetch('/api/admin/images/describe-prompt', {
        method: 'POST',
        body: JSON.stringify({ text: loc.description, context })
      }).then(d => {
        if (!d.keywords) return;
        const ta = overlay.querySelector('#li-prompt');
        if (!ta || !overlay.isConnected) return;
        // Append translated description keywords before the style suffix
        const current = ta.value;
        const styleIdx = current.lastIndexOf('fantasy RPG location art');
        const base = styleIdx > 0 ? current.slice(0, styleIdx).replace(/,\s*$/, '') : current;
        const style = styleIdx > 0 ? current.slice(styleIdx) : 'fantasy RPG location art, atmospheric illustrated style, moody cinematic lighting, detailed, no text, no letters, no UI';
        ta.value = [base, d.keywords, style].filter(Boolean).join(', ');
        // Trigger auto-resize
        ta.dispatchEvent(new Event('input'));
        // Show subtle indicator
        const badge = overlay.querySelector('.li-trans-badge');
        if (badge) { badge.textContent = '✦ auto+AI'; badge.style.background = 'var(--green-light)'; badge.style.color = 'var(--green-text)'; badge.style.borderColor = 'var(--green-border)'; }
      }).catch(() => {}); // silent fail — base prompt still usable
    }
  }


// ── Section HTML ────────────────────────────────────────────────────────────────
function _sectionHtml() {
  return `
      <div class="section-header">
        <div>
          <div class="section-heading">Mapa</div>
          <div class="section-sub">Lokacje, teren i budowniczy świata</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <span class="badge badge-red" id="map-pending-badge" style="display:none">0 oczekujące</span>
          <button class="btn btn-primary btn-sm" onclick="document.querySelector('[data-mtap=locations]')?.click()">+ Dodaj lokację</button>
        </div>
      </div>

      <div class="card">
        <div class="section-tabs" id="map-tabs">
          <button class="stab active" data-mtap="builder">Mapa</button>
          <button class="stab" data-mtap="generate">⚙ Ustawienia mapy</button>
          <button class="stab" data-mtap="locations">Lokacje</button>
          <button class="stab" data-mtap="floating">⚓ Floating</button>
          <button class="stab" data-mtap="terrain">Teren</button>
          <button class="stab" data-mtap="review">Do zatwierdzenia</button>
          <button class="stab" data-mtap="duplicates">🧹 Duplikaty <span class="badge badge-red" id="loc-dup-badge" style="display:none">0</span></button>
        </div>

        <!-- Lokacje -->
        <div class="stab-panel" id="wtab-locations">
          <div class="toolbar">
            <div class="search-box">
              <span class="search-box-icon">🔍</span>
              <input type="text" placeholder="Szukaj lokacji…" oninput="filterTableGeneric(this,'locations-table','td-name')">
            </div>
            <div class="filter-group" id="locations-type-filter">
              <button class="chip on" onclick="filterLocationsType(this,'')">Wszystkie</button>
              <button class="chip" onclick="filterLocationsType(this,'loch')">Loch</button>
              <button class="chip" onclick="filterLocationsType(this,'miasto')">Miasto</button>
              <button class="chip" onclick="filterLocationsType(this,'dzikość')">Dzikość</button>
            </div>
            <select id="locations-region-filter" onchange="filterLocationsRegion(this)" style="background:#111;border:1px solid #2a2a3a;color:#c8c0a8;font-size:0.72rem;padding:3px 8px;border-radius:4px;cursor:pointer;height:28px">
              <option value="">Wszystkie krainy</option>
              <option value="kresy">Kresy</option>
              <option value="czarnobor">Czarnobór</option>
              <option value="siwe_granie">Siwe Granie</option>
              <option value="martwe_pustkowia">Martwe Pustkowia</option>
              <option value="koronne_niziny">Koronne Niziny</option>
              <option value="wybrzeze_lez">Wybrzeże Łez</option>
            </select>
            <button id="loc-bulk-del" class="btn btn-sm" style="display:none;margin-left:auto;background:#7f1d1d;color:#fca5a5;border:1px solid #dc2626" title="Usuń wszystkie zaznaczone lokacje">🗑 Usuń zaznaczone (<span id="loc-sel-count">0</span>)</button>
          </div>
          <div class="table-wrap" style="max-height:calc(100vh - 280px);overflow-y:auto">
            <table class="data-table" id="locations-table">
              <thead>
                <tr>
                  <th class="col-check"><input type="checkbox" id="loc-check-all" title="Zaznacz wszystkie"></th>
                  <th class="td-sticky"><div class="th-inner sorted">Nazwa <span class="sort-icon asc">▲</span></div></th>
                  <th><div class="th-inner">Typ</div></th>
                  <th><div class="th-inner">Kraina</div></th>
                  <th><div class="th-inner">Biom</div></th>
                  <th><div class="th-inner">Tier</div></th>
                  <th><div class="th-inner">Safe</div></th>
                  <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
                </tr>
              </thead>
              <tbody id="locations-tbody"></tbody>
            </table>
          </div>
          <button class="add-row-btn">＋ Dodaj lokację</button>
        </div>

        <!-- U28: Floating Lokacje -->
        <div class="stab-panel" id="wtab-floating">
          <div class="toolbar">
            <span style="color:var(--t3);font-size:0.82rem">Lokacje niezakotwiczone na hexach (floating). Osadź ręcznie podając współrzędne hexa (q, r).</span>
          </div>
          <div class="table-wrap" style="max-height:calc(100vh - 280px);overflow-y:auto">
            <table class="data-table" id="floating-locations-table">
              <thead>
                <tr>
                  <th>Klucz</th>
                  <th>Nazwa</th>
                  <th>Typ</th>
                  <th>Kraina</th>
                  <th>Tagi terenu</th>
                  <th>Biom</th>
                  <th>Akcja</th>
                </tr>
              </thead>
              <tbody><tr><td colspan="7" style="text-align:center;padding:28px;color:var(--t3)">Ładowanie…</td></tr></tbody>
            </table>
          </div>
        </div>

        <!-- Teren -->
        <div class="stab-panel" id="wtab-terrain">
          <div class="toolbar">
            <span style="color:var(--t3);font-size:0.82rem">Waga spawnu określa częstotliwość generowania. Wartość 0 = wyłączony.</span>
            <button class="btn btn-primary btn-sm" onclick="openTerrainFormModal(null)">+ Nowy typ</button>
          </div>
          <div class="table-wrap">
            <table class="data-table" id="terrain-table">
              <thead>
                <tr>
                  <th><div class="th-inner">Ikona</div></th>
                  <th><div class="th-inner">Klucz</div></th>
                  <th><div class="th-inner">Etykieta</div></th>
                  <th><div class="th-inner">Waga spawnu</div></th>
                  <th><div class="th-inner" title="biome=skupiska, scatter=rozproszone, path=linie">Tryb</div></th>
                  <th><div class="th-inner">Czas podróży (h)</div></th>
                  <th><div class="th-inner">Enc. %</div></th>
                  <th><div class="th-inner">Aktywny</div></th>
                  <th><div class="th-inner" title="Czy ten teren może mieć lokalną podmapę (miasto, lochy, ruiny itp.)">Submap</div></th>
                  <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
                </tr>
              </thead>
              <tbody id="terrain-tbody"></tbody>
            </table>
          </div>
        </div>

        <!-- Do zatwierdzenia -->
        <div class="stab-panel" id="wtab-review">
          <div style="padding:28px;text-align:center;color:var(--t3);font-size:0.8rem">Ładowanie…</div>
        </div>

        <!-- Duplikaty lokacji (#1409) -->
        <div class="stab-panel" id="wtab-duplicates">
          <div style="padding:16px" id="loc-dup-root">
            <div style="padding:28px;text-align:center;color:var(--t3);font-size:0.8rem">Ładowanie…</div>
          </div>
        </div>

        <!-- Ustawienia mapy (#1482) -->
        <div class="stab-panel" id="wtab-generate">
          <div style="padding:16px;display:flex;flex-direction:column;gap:16px">
            <!-- Nav shortcut -->
            <div style="display:flex;justify-content:flex-end">
              <button class="btn btn-sm btn-secondary" onclick="document.querySelector('[data-mtap=builder]')?.click()">🗺 Otwórz budowniczego →</button>
            </div>
            <!-- Stats row -->
            <div id="hexmap-stats" style="display:flex;gap:12px;flex-wrap:wrap">
              <div class="card" style="padding:10px 14px;flex:1;min-width:120px">
                <div style="font-size:1.4rem;font-weight:700;color:var(--text)" id="hexmap-total">—</div>
                <div style="font-size:0.72rem;color:var(--t3)">Heksów w świecie</div>
              </div>
              <div class="card" style="padding:10px 14px;flex:1;min-width:120px" id="hexmap-types-card">
                <div style="font-size:0.78rem;color:var(--t3)">Ładowanie…</div>
              </div>
            </div>
            <!-- #1482: generator świata usunięty -->
            <div class="card" style="padding:14px 16px;border-color:#c9a54a">
              <div style="font-weight:600;margin-bottom:6px;color:#c9a54a">Mapa świata jest budowana ręcznie</div>
              <div style="font-size:0.78rem;color:var(--t3);line-height:1.5">
                Proceduralny generator świata i masowe czyszczenie mapy zostały usunięte —
                jedno kliknięcie potrafiło nadpisać godziny ręcznej pracy. Teren malujesz w
                zakładce <b>Mapa</b>, a kopię wzorcową robisz przyciskiem
                <b>💾 Zapisz mapę (kanon)</b>. Odtworzenie krainy: <b>📂 Wczytaj mapę (z kanonu)</b>
                przy wybranej krainie. Podmapy osad (<b>🏘 Generuj</b>) działają bez zmian.
              </div>
            </div>
            <!-- PM7 (#1226): globalny promień bąbla wiedzy (FOW) -->
            <div class="card" style="padding:16px">
              <div style="font-weight:600;margin-bottom:6px">Zasięg wiedzy gracza (mgła wojny)</div>
              <div style="font-size:0.72rem;color:var(--t3);margin-bottom:12px">Promień (w heksach) bąbla „znane z opowieści” wokół pozycji gracza. Większy = gracz zna więcej terenu z wyprzedzenia. Domyślnie 4.</div>
              <div style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">
                <div>
                  <label style="font-size:0.78rem;color:var(--t3);display:block;margin-bottom:4px">Promień (heksów)</label>
                  <input type="number" id="kbr-radius" class="form-input" value="4" min="0" max="20" style="width:90px">
                </div>
                <button class="btn btn-primary" id="kbr-save-btn" onclick="saveKnowledgeBubble()">💾 Zapisz zasięg</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Budowniczy świata -->
        <div class="stab-panel active" id="wtab-builder">
          <div class="wb-layout" id="wb-root">
            <div class="wb-sidebar" id="wb-sidebar">
              <div style="display:flex;gap:3px;padding:6px 6px 2px">
                <button id="wb-mode-select" class="btn btn-sm btn-primary" style="flex:1;font-size:0.68rem;padding:4px 3px" title="Zaznacz heks">⬡ Wybierz</button>
                <button id="wb-mode-paint" class="btn btn-sm btn-secondary" style="flex:1;font-size:0.68rem;padding:4px 3px" title="Maluj heksy (przeciągnij)">🖌 Maluj</button>
              </div>
              <div style="padding:2px 6px 2px">
                <button id="wb-undo" class="btn btn-sm btn-secondary" style="width:100%;font-size:0.68rem;padding:4px 3px" title="Cofnij ostatnią edycję (Ctrl+Z)" disabled>↶ Cofnij</button>
              </div>
              <div style="padding:0 6px 2px">
                <button id="wb-loc-overlay" class="btn btn-sm btn-secondary" style="width:100%;font-size:0.68rem;padding:4px 3px" title="Podświetl heksy z przypiętymi lokacjami (zielone = ma lokację)">📍 Lokacje na mapie</button>
              </div>
              <div style="padding:0 6px 2px">
                <button id="wb-save-canon" class="btn btn-sm" style="width:100%;font-size:0.68rem;padding:5px 3px;background:#c9a54a;color:#1a1206;border:1px solid #c9a54a;font-weight:700" title="Zapisz bieżącą mapę jako kanon — trwałe, przeżywa reset/wipe DB">💾 Zapisz mapę (kanon)</button>
              </div>
              <div style="padding:0 6px 4px">
                <button id="wb-restore-canon" class="btn btn-sm" style="width:100%;font-size:0.68rem;padding:5px 3px;background:#2a4a2a;color:#a8d4a8;border:1px solid #4a7a4a;font-weight:700" title="Wczytaj mapę z ostatnio zapisanego kanonu — nadpisze bieżącą mapę">📂 Wczytaj mapę (z kanonu)</button>
              </div>
              <div style="font-size:0.65rem;font-weight:700;color:var(--t3);letter-spacing:0.1em;padding:4px 10px 2px">TEREN</div>
              <div class="wb-palette" id="wb-palette"></div>
              <div class="wb-hint" id="wb-hint">Maluj: wybierz typ + przeciągnij<br>Kliknij hex → edytuj<br>Ctrl+Z → cofnij<br>Alt+drag → przesuń · Scroll → zoom</div>
              <div id="wb-zoom-label" style="font-size:0.68rem;color:var(--t3);padding:2px 8px">Zoom: 100%</div>
              <button onclick="wbCenter()" style="margin:6px 8px;font-size:0.7rem;padding:5px 8px;background:var(--bg3);border:1px solid var(--border);border-radius:5px;color:var(--t2);cursor:pointer;width:calc(100% - 16px)">⊡ Dopasuj</button>
            </div>
            <div style="display:flex;flex-direction:column;flex:1;min-width:0;overflow:hidden">
              <div id="wb-region-bar"></div>
              <div class="wb-canvas-wrap" style="flex:1">
                <svg id="wb-svg" style="background:#080608"></svg>
              </div>
            </div>
            <div class="wb-detail" id="wb-detail">
              <div style="color:var(--t3);font-size:0.78rem">Kliknij hex aby edytować.</div>
            </div>
          </div>
        </div>

      </div>
`;
}

// ── Mount ───────────────────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = _sectionHtml();

  // DOM wiped na każdym mount → wyczyść cache zakładek aby aktywna zakładka odrysowała się od nowa.
  _worldLoaded.clear();

  // Expose globals for inline onclick/onchange strings (port 1:1 zachowuje nazwy bare).
  Object.assign(window, {
    filterTableGeneric, filterLocationsType, filterLocationsRegion, openTerrainFormModal,
    saveKnowledgeBubble,
    wbCenter, openLocNpcModal, openLocImageModal, reviewEntity,
    approveKanon, openSubmapModal, pendingGenSubmap, saveTerrainForm, terrainPatch,
    mechPatchEdit, _wbApproveLocation, _wbDiscardLocation, _openGenericEjBuilder,
    openLocDetailModal, wbFilterRegion, wbToggleRegionStatus,
  });

  // Wire tab switching (data-mtap)
  panel.querySelector('#map-tabs')?.addEventListener('click', e => {
    const btn = e.target.closest('.stab[data-mtap]');
    if (!btn) return;
    const tab = btn.dataset.mtap;
    panel.querySelectorAll('#map-tabs .stab').forEach(b => b.classList.toggle('active', b === btn));
    panel.querySelectorAll('.stab-panel').forEach(p => p.classList.toggle('active', p.id === `wtab-${tab}`));
    _loadMapTab(tab).then(() => { if (tab === 'builder') setTimeout(wbCenter, 80); });
  });

  _wireLocDup(panel);       // #1409 — detektor duplikatów lokacji (delegacja klików)
  _loadLocDupBadge();       // badge na zakładce od razu po wejściu w sekcję

  // Domyślna zakładka: budowniczy (wtab-builder aktywny w HTML)
  _loadMapTab('builder').then(() => setTimeout(wbCenter, 80));
}
