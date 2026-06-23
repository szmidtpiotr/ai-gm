/**
 * W15 #920 — Sekcja "Wizytówka" w modular admin: CMS-lite do edycji treści showcase.
 * Tabs: Historia · Świat · FAQ · Roadmapa · Changelog
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

const _esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// ── State ─────────────────────────────────────────────────────────────────────
let _data = {};
let _dirty = {};
let _currentTab = 'historia';
let _editingStageIdx = null;
let _editingKrainaIdx = null;
let _editingFaqIdx = null;

const _TABS = [
  { key: 'historia',  label: '📜 Historia' },
  { key: 'swiat',     label: '🌍 Świat' },
  { key: 'faq',       label: '❓ FAQ' },
  { key: 'roadmap',   label: '🗺 Roadmapa' },
  { key: 'changelog', label: '📋 Changelog' },
];

const _HTML = `
<div id="section-showcase">
  <div class="section-header">
    <div>
      <div class="section-heading">Wizytówka</div>
      <div class="section-sub">Edycja treści strony <a href="/showcase/" target="_blank" style="color:var(--accent)">/showcase/</a> — zmiany widoczne natychmiast</div>
    </div>
    <div style="display:flex;gap:8px;align-items:center">
      <a class="btn btn-sm btn-secondary" href="/showcase/" target="_blank">🔗 Podgląd</a>
      <button id="sc-save-btn" class="btn btn-primary btn-sm" onclick="scSave()" disabled>Zapisano</button>
    </div>
  </div>

  <div class="stab-bar" id="sc-stab-bar">
    ${_TABS.map(t => `<button class="stab${t.key === 'historia' ? ' active' : ''}" data-sctab="${t.key}">${t.label}</button>`).join('')}
  </div>

  <div id="sc-tab-content" style="margin-top:12px"></div>
</div>`;

// ── API helpers ───────────────────────────────────────────────────────────────

async function _load(key) {
  if (_data[key]) return _data[key];
  try {
    _data[key] = await apiFetch(`/api/admin/showcase/${key}`);
  } catch (e) {
    showToast(`Błąd ładowania ${key}: ${e.message}`, 'error');
    _data[key] = {};
  }
  return _data[key];
}

async function scSave() {
  const key = _currentTab;
  const btn = document.getElementById('sc-save-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Zapisuję…'; }
  try {
    await apiFetch(`/api/admin/showcase/${key}`, {
      method: 'PUT',
      body: JSON.stringify(_data[key]),
    });
    _dirty[key] = false;
    _updateSaveBtn();
    showToast('Zapisano! Strona /showcase/ zaktualizowana.', 'success');
  } catch (e) {
    showToast(`Błąd zapisu: ${e.message}`, 'error');
  } finally {
    if (btn) { btn.textContent = 'Zapisz zmiany'; }
    _updateSaveBtn();
  }
}

function _markDirty(key) {
  _dirty[key] = true;
  _updateSaveBtn();
}

function _updateSaveBtn() {
  const btn = document.getElementById('sc-save-btn');
  if (!btn) return;
  const dirty = !!_dirty[_currentTab];
  btn.disabled = !dirty;
  btn.textContent = dirty ? '💾 Zapisz zmiany' : 'Zapisano';
}

// ── Tab routing ───────────────────────────────────────────────────────────────

async function _switchTab(key) {
  _currentTab = key;
  document.querySelectorAll('.stab[data-sctab]').forEach(b =>
    b.classList.toggle('active', b.dataset.sctab === key));
  _updateSaveBtn();
  const panel = document.getElementById('sc-tab-content');
  if (!panel) return;
  panel.innerHTML = '<div style="padding:40px;text-align:center;color:var(--t3)">Ładowanie…</div>';
  await _load(key);
  switch (key) {
    case 'historia':  _renderHistoria(panel); break;
    case 'swiat':     _renderSwiat(panel); break;
    case 'faq':       _renderFaq(panel); break;
    case 'roadmap':   _renderRoadmap(panel); break;
    case 'changelog': _renderChangelog(panel); break;
  }
}

// ── HISTORIA tab ──────────────────────────────────────────────────────────────

function _renderHistoria(panel) {
  const d = _data.historia;
  panel.innerHTML = `
  <div class="card" style="margin-bottom:12px">
    <div class="card-header"><span class="card-title">Wstęp</span></div>
    <div style="padding:14px 16px">
      <textarea id="sc-historia-intro" class="field-input" rows="3" style="width:100%;font-size:0.82rem;resize:vertical">${_esc(d.intro || '')}</textarea>
      <button class="btn btn-sm btn-secondary" style="margin-top:8px" onclick="scHistoriaIntroSave()">Zatwierdź wstęp</button>
    </div>
  </div>
  <div class="card">
    <div class="card-header">
      <span class="card-title">Etapy historii (${(d.stages || []).length})</span>
      <button class="btn btn-sm btn-primary" onclick="scHistoriaAddStage()">+ Dodaj etap</button>
    </div>
    <div id="sc-historia-stages" style="padding:8px 16px 12px">
      ${_renderStagesList(d.stages || [])}
    </div>
  </div>`;
}

function _renderStagesList(stages) {
  if (!stages.length) return '<div style="color:var(--t3);padding:12px 0">Brak etapów. Kliknij + Dodaj etap.</div>';
  return stages.map((s, i) => `
    <div style="padding:10px 0;border-bottom:1px solid var(--border);display:flex;gap:10px;align-items:start">
      <div style="flex:1;min-width:0">
        <div style="font-weight:600;color:var(--accent);font-size:0.85rem">${_esc(s.when || '')}</div>
        <div style="font-weight:700;color:var(--t1);margin-top:2px">${_esc(s.title || '')}</div>
        <div style="color:var(--t3);font-size:0.75rem;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_esc((s.body || '').slice(0, 120))}…</div>
      </div>
      <div style="display:flex;gap:4px;flex-shrink:0">
        <button class="btn btn-sm btn-secondary" style="padding:3px 8px" onclick="scHistoriaEditStage(${i})">✏ Edytuj</button>
        <button class="btn btn-sm" style="padding:3px 8px;background:rgba(120,50,50,0.4);color:#f08080" onclick="scHistoriaDeleteStage(${i})">🗑</button>
        ${i > 0 ? `<button class="btn btn-sm btn-secondary" style="padding:3px 6px" onclick="scHistoriaMoveStage(${i},-1)">↑</button>` : ''}
        ${i < stages.length - 1 ? `<button class="btn btn-sm btn-secondary" style="padding:3px 6px" onclick="scHistoriaMoveStage(${i},1)">↓</button>` : ''}
      </div>
    </div>`).join('');
}

function _openStageEditor(idx) {
  _editingStageIdx = idx;
  const stages = _data.historia.stages || [];
  const isNew = idx >= stages.length;
  const s = isNew ? { when: '', title: '', body: '' } : stages[idx];
  let modal = document.getElementById('sc-stage-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'sc-stage-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;display:flex;align-items:center;justify-content:center;padding:16px';
    document.body.appendChild(modal);
  }
  modal.innerHTML = `
    <div style="background:var(--surface-2);border:1px solid var(--border);border-radius:12px;width:100%;max-width:640px;max-height:90vh;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:14px">
      <div style="font-weight:700;font-size:1.1rem;color:var(--t1)">${isNew ? 'Nowy etap' : 'Edycja etapu'}</div>
      <div>
        <label style="font-size:0.78rem;font-weight:600;color:var(--t2);display:block;margin-bottom:4px">Kiedy</label>
        <input id="sc-stage-when" class="field-input" type="text" value="${_esc(s.when || '')}" style="width:100%" placeholder="np. kwiecień 2026 — iskra" />
      </div>
      <div>
        <label style="font-size:0.78rem;font-weight:600;color:var(--t2);display:block;margin-bottom:4px">Tytuł</label>
        <input id="sc-stage-title" class="field-input" type="text" value="${_esc(s.title || '')}" style="width:100%" />
      </div>
      <div>
        <label style="font-size:0.78rem;font-weight:600;color:var(--t2);display:block;margin-bottom:4px">Treść</label>
        <textarea id="sc-stage-body" class="field-input" rows="10" style="width:100%;font-size:0.82rem;resize:vertical;line-height:1.6">${_esc(s.body || '')}</textarea>
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-secondary btn-sm" onclick="scStageCancel()">Anuluj</button>
        <button class="btn btn-primary btn-sm" onclick="scStageSave(${idx},${isNew})">Zapisz etap</button>
      </div>
    </div>`;
}

function scHistoriaIntroSave() {
  const val = document.getElementById('sc-historia-intro')?.value ?? '';
  _data.historia.intro = val;
  _markDirty('historia');
  showToast('Wstęp zaktualizowany — kliknij 💾 Zapisz zmiany.', 'info');
}
function scHistoriaEditStage(idx) { _openStageEditor(idx); }
function scHistoriaAddStage() { _openStageEditor((_data.historia.stages || []).length); }

function scHistoriaDeleteStage(idx) {
  if (!confirm('Usunąć ten etap historii?')) return;
  _data.historia.stages = (_data.historia.stages || []).filter((_, i) => i !== idx);
  _markDirty('historia');
  const panel = document.getElementById('sc-tab-content');
  if (panel) _renderHistoria(panel);
}

function scHistoriaMoveStage(idx, dir) {
  const stages = _data.historia.stages || [];
  const ni = idx + dir;
  if (ni < 0 || ni >= stages.length) return;
  [stages[idx], stages[ni]] = [stages[ni], stages[idx]];
  _markDirty('historia');
  const panel = document.getElementById('sc-tab-content');
  if (panel) _renderHistoria(panel);
}

function scStageSave(idx, isNew) {
  const when = document.getElementById('sc-stage-when')?.value?.trim() || '';
  const title = document.getElementById('sc-stage-title')?.value?.trim() || '';
  const body = document.getElementById('sc-stage-body')?.value?.trim() || '';
  if (!title) { showToast('Tytuł jest wymagany.', 'error'); return; }
  if (!_data.historia.stages) _data.historia.stages = [];
  const entry = { when, title, body };
  if (isNew) { _data.historia.stages.push(entry); } else { _data.historia.stages[idx] = entry; }
  _markDirty('historia');
  scStageCancel();
  const panel = document.getElementById('sc-tab-content');
  if (panel) _renderHistoria(panel);
  showToast('Etap zapisany — kliknij 💾 Zapisz zmiany.', 'success');
}

function scStageCancel() {
  _editingStageIdx = null;
  document.getElementById('sc-stage-modal')?.remove();
}

// ── ŚWIAT tab ─────────────────────────────────────────────────────────────────

function _renderSwiat(panel) {
  const d = _data.swiat;
  const krainy = d.krainy || [];
  panel.innerHTML = `
  <div class="card" style="margin-bottom:12px">
    <div class="card-header"><span class="card-title">Wstęp świata</span></div>
    <div style="padding:14px 16px">
      <textarea id="sc-swiat-intro" class="field-input" rows="3" style="width:100%;font-size:0.82rem;resize:vertical">${_esc(d.intro || '')}</textarea>
      <button class="btn btn-sm btn-secondary" style="margin-top:8px" onclick="scSwiatIntroSave()">Zatwierdź wstęp</button>
    </div>
  </div>
  <div class="card">
    <div class="card-header"><span class="card-title">Krainy (${krainy.length})</span></div>
    <div style="padding:8px 16px 12px">${_renderKrainyList(krainy)}</div>
  </div>`;
  if (_editingKrainaIdx !== null) _openKrainaEditor(_editingKrainaIdx);
}

function _renderKrainyList(krainy) {
  if (!krainy.length) return '<div style="color:var(--t3);padding:12px 0">Brak krain.</div>';
  return krainy.map((k, i) => `
    <div style="padding:10px 0;border-bottom:1px solid var(--border);display:flex;gap:10px;align-items:start">
      <div style="width:48px;height:48px;background:var(--surface);border-radius:6px;overflow:hidden;flex-shrink:0">
        <img src="/showcase/${_esc(k.img || '')}" style="width:100%;height:100%;object-fit:cover" onerror="this.style.opacity=0.2" />
      </div>
      <div style="flex:1;min-width:0">
        <div style="font-weight:700;color:var(--t1)">${_esc(k.name || '')}
          <span style="color:var(--t3);font-size:0.75rem;margin-left:6px">${_esc(k.tag || '')}</span>
          ${k.available ? '<span style="color:#4caf78;font-size:0.72rem;margin-left:6px">✓ dostępna</span>' : '<span style="color:var(--t3);font-size:0.72rem;margin-left:6px">🔒 zablokowana</span>'}
        </div>
        <div style="color:var(--t3);font-size:0.75rem;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_esc((k.desc || '').slice(0, 120))}…</div>
      </div>
      <button class="btn btn-sm btn-secondary" style="flex-shrink:0;padding:3px 8px" onclick="scKrainaEdit(${i})">✏ Edytuj</button>
    </div>`).join('');
}

function _openKrainaEditor(idx) {
  _editingKrainaIdx = idx;
  const k = (_data.swiat.krainy || [])[idx] || {};
  let modal = document.getElementById('sc-kraina-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'sc-kraina-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;display:flex;align-items:center;justify-content:center;padding:16px';
    document.body.appendChild(modal);
  }
  modal.innerHTML = `
    <div style="background:var(--surface-2);border:1px solid var(--border);border-radius:12px;width:100%;max-width:580px;max-height:90vh;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:14px">
      <div style="font-weight:700;font-size:1.1rem;color:var(--t1)">Edycja krainy: ${_esc(k.name || '')}</div>
      <div>
        <label style="font-size:0.78rem;font-weight:600;color:var(--t2);display:block;margin-bottom:4px">Nazwa</label>
        <input id="sc-kraina-name" class="field-input" value="${_esc(k.name || '')}" style="width:100%" />
      </div>
      <div>
        <label style="font-size:0.78rem;font-weight:600;color:var(--t2);display:block;margin-bottom:4px">Tag (podtytuł)</label>
        <input id="sc-kraina-tag" class="field-input" value="${_esc(k.tag || '')}" style="width:100%" />
      </div>
      <div>
        <label style="font-size:0.78rem;font-weight:600;color:var(--t2);display:block;margin-bottom:4px">Opis</label>
        <textarea id="sc-kraina-desc" class="field-input" rows="5" style="width:100%;font-size:0.82rem;resize:vertical">${_esc(k.desc || '')}</textarea>
      </div>
      <div style="display:flex;gap:12px;align-items:center">
        <label style="font-size:0.78rem;font-weight:600;color:var(--t2)">Dostępna dla graczy:</label>
        <input type="checkbox" id="sc-kraina-avail" ${k.available ? 'checked' : ''} style="width:18px;height:18px;cursor:pointer" />
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-secondary btn-sm" onclick="scKrainaCancel()">Anuluj</button>
        <button class="btn btn-primary btn-sm" onclick="scKrainaSave(${idx})">Zapisz krainę</button>
      </div>
    </div>`;
}

function scSwiatIntroSave() {
  _data.swiat.intro = document.getElementById('sc-swiat-intro')?.value ?? '';
  _markDirty('swiat');
  showToast('Wstęp świata zaktualizowany.', 'info');
}
function scKrainaEdit(idx) { _openKrainaEditor(idx); }

function scKrainaSave(idx) {
  const krainy = _data.swiat.krainy || [];
  if (!krainy[idx]) return;
  krainy[idx] = {
    ...krainy[idx],
    name: document.getElementById('sc-kraina-name')?.value?.trim() || krainy[idx].name,
    tag: document.getElementById('sc-kraina-tag')?.value?.trim() || krainy[idx].tag,
    desc: document.getElementById('sc-kraina-desc')?.value?.trim() || krainy[idx].desc,
    available: !!(document.getElementById('sc-kraina-avail')?.checked),
  };
  _markDirty('swiat');
  scKrainaCancel();
  const panel = document.getElementById('sc-tab-content');
  if (panel) _renderSwiat(panel);
  showToast('Kraina zaktualizowana — kliknij 💾 Zapisz zmiany.', 'success');
}

function scKrainaCancel() {
  _editingKrainaIdx = null;
  document.getElementById('sc-kraina-modal')?.remove();
}

// ── FAQ tab ───────────────────────────────────────────────────────────────────

function _renderFaq(panel) {
  const items = (_data.faq?.faq) || [];
  panel.innerHTML = `
  <div class="card">
    <div class="card-header">
      <span class="card-title">FAQ (${items.length})</span>
      <button class="btn btn-sm btn-primary" onclick="scFaqAdd()">+ Dodaj pytanie</button>
    </div>
    <div id="sc-faq-list" style="padding:8px 16px 12px">${_renderFaqList(items)}</div>
  </div>`;
  if (_editingFaqIdx !== null) _openFaqEditor(_editingFaqIdx);
}

function _renderFaqList(items) {
  if (!items.length) return '<div style="color:var(--t3);padding:12px 0">Brak pytań FAQ.</div>';
  return items.map((item, i) => `
    <div style="padding:10px 0;border-bottom:1px solid var(--border)">
      <div style="font-weight:600;color:var(--t1);margin-bottom:4px">${_esc(item.q || '')}</div>
      <div style="color:var(--t3);font-size:0.8rem">${_esc(item.a || '')}</div>
      <div style="display:flex;gap:6px;margin-top:8px">
        <button class="btn btn-sm btn-secondary" style="padding:2px 8px" onclick="scFaqEdit(${i})">✏ Edytuj</button>
        <button class="btn btn-sm" style="padding:2px 8px;background:rgba(120,50,50,0.4);color:#f08080" onclick="scFaqDelete(${i})">🗑</button>
        ${i > 0 ? `<button class="btn btn-sm btn-secondary" style="padding:2px 6px" onclick="scFaqMove(${i},-1)">↑</button>` : ''}
        ${i < items.length - 1 ? `<button class="btn btn-sm btn-secondary" style="padding:2px 6px" onclick="scFaqMove(${i},1)">↓</button>` : ''}
      </div>
    </div>`).join('');
}

function _openFaqEditor(idx) {
  _editingFaqIdx = idx;
  const items = _data.faq?.faq || [];
  const isNew = idx >= items.length;
  const item = isNew ? { q: '', a: '' } : items[idx];
  let modal = document.getElementById('sc-faq-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'sc-faq-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;display:flex;align-items:center;justify-content:center;padding:16px';
    document.body.appendChild(modal);
  }
  modal.innerHTML = `
    <div style="background:var(--surface-2);border:1px solid var(--border);border-radius:12px;width:100%;max-width:560px;padding:24px;display:flex;flex-direction:column;gap:14px">
      <div style="font-weight:700;font-size:1.1rem">${isNew ? 'Nowe pytanie FAQ' : 'Edycja pytania'}</div>
      <div>
        <label style="font-size:0.78rem;font-weight:600;color:var(--t2);display:block;margin-bottom:4px">Pytanie</label>
        <input id="sc-faq-q" class="field-input" type="text" value="${_esc(item.q)}" style="width:100%" />
      </div>
      <div>
        <label style="font-size:0.78rem;font-weight:600;color:var(--t2);display:block;margin-bottom:4px">Odpowiedź</label>
        <textarea id="sc-faq-a" class="field-input" rows="4" style="width:100%;font-size:0.82rem;resize:vertical">${_esc(item.a)}</textarea>
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-secondary btn-sm" onclick="scFaqCancel()">Anuluj</button>
        <button class="btn btn-primary btn-sm" onclick="scFaqSave(${idx},${isNew})">Zapisz</button>
      </div>
    </div>`;
}

function scFaqAdd() { _openFaqEditor((_data.faq?.faq || []).length); }
function scFaqEdit(idx) { _openFaqEditor(idx); }

function scFaqDelete(idx) {
  if (!confirm('Usunąć to pytanie?')) return;
  _data.faq.faq = (_data.faq.faq || []).filter((_, i) => i !== idx);
  _markDirty('faq');
  const panel = document.getElementById('sc-tab-content');
  if (panel) _renderFaq(panel);
}

function scFaqMove(idx, dir) {
  const items = _data.faq.faq || [];
  const ni = idx + dir;
  if (ni < 0 || ni >= items.length) return;
  [items[idx], items[ni]] = [items[ni], items[idx]];
  _markDirty('faq');
  const panel = document.getElementById('sc-tab-content');
  if (panel) _renderFaq(panel);
}

function scFaqSave(idx, isNew) {
  const q = document.getElementById('sc-faq-q')?.value?.trim() || '';
  const a = document.getElementById('sc-faq-a')?.value?.trim() || '';
  if (!q) { showToast('Pytanie jest wymagane.', 'error'); return; }
  if (!_data.faq.faq) _data.faq.faq = [];
  if (isNew) { _data.faq.faq.push({ q, a }); } else { _data.faq.faq[idx] = { q, a }; }
  _markDirty('faq');
  scFaqCancel();
  const panel = document.getElementById('sc-tab-content');
  if (panel) _renderFaq(panel);
  showToast('Pytanie zapisane — kliknij 💾 Zapisz zmiany.', 'success');
}

function scFaqCancel() {
  _editingFaqIdx = null;
  document.getElementById('sc-faq-modal')?.remove();
}

// ── ROADMAP tab ───────────────────────────────────────────────────────────────

function _renderRoadmap(panel) {
  const kolumny = _data.roadmap?.kolumny || [];
  panel.innerHTML = `
  <div class="card">
    <div class="card-header">
      <span class="card-title">Kolumny roadmapy</span>
      <button class="btn btn-sm btn-secondary" onclick="scRmSaveAll()">Zatwierdź zmiany</button>
    </div>
    <div style="padding:14px 16px">
      ${kolumny.map((kol, ki) => `
        <div style="margin-bottom:20px;border:1px solid var(--border);border-radius:8px;padding:14px">
          <div style="font-weight:700;color:var(--accent);margin-bottom:10px">${_esc(kol.status || '')}</div>
          <div style="display:flex;flex-direction:column;gap:6px">
            ${(kol.items || []).map((item, ii) => `
              <div style="display:flex;gap:6px;align-items:center">
                <input class="field-input sc-rm-item" data-col="${ki}" data-idx="${ii}" value="${_esc(item)}" style="flex:1;font-size:0.82rem;padding:4px 8px" />
                <button class="btn btn-sm" style="padding:2px 7px;background:rgba(120,50,50,0.4);color:#f08080;flex-shrink:0" onclick="scRmDeleteItem(${ki},${ii})">✕</button>
              </div>`).join('')}
          </div>
          <button class="btn btn-sm btn-secondary" style="margin-top:8px" onclick="scRmAddItem(${ki})">+ Dodaj punkt</button>
        </div>`).join('')}
    </div>
  </div>`;
}

function scRmAddItem(ki) {
  scRmSaveAll();
  const kolumny = _data.roadmap.kolumny || [];
  if (!kolumny[ki].items) kolumny[ki].items = [];
  kolumny[ki].items.push('Nowy punkt');
  _markDirty('roadmap');
  const panel = document.getElementById('sc-tab-content');
  if (panel) _renderRoadmap(panel);
}

function scRmDeleteItem(ki, ii) {
  scRmSaveAll();
  const kolumny = _data.roadmap.kolumny || [];
  kolumny[ki].items = (kolumny[ki].items || []).filter((_, i) => i !== ii);
  _markDirty('roadmap');
  const panel = document.getElementById('sc-tab-content');
  if (panel) _renderRoadmap(panel);
}

function scRmSaveAll() {
  const kolumny = _data.roadmap?.kolumny || [];
  document.querySelectorAll('.sc-rm-item').forEach(input => {
    const ki = parseInt(input.dataset.col, 10);
    const ii = parseInt(input.dataset.idx, 10);
    if (kolumny[ki]?.items) kolumny[ki].items[ii] = input.value;
  });
  _markDirty('roadmap');
}

// ── CHANGELOG tab ─────────────────────────────────────────────────────────────

function _renderChangelog(panel) {
  const entries = _data.changelog?.entries || [];
  panel.innerHTML = `
  <div class="card">
    <div class="card-header">
      <span class="card-title">Changelog (${entries.length} wersji)</span>
      <span style="color:var(--t3);font-size:0.75rem">Tylko do podglądu — generowany z CHANGELOG.md</span>
    </div>
    <div style="padding:8px 16px 12px;max-height:600px;overflow-y:auto">
      ${entries.map(e => `
        <div style="padding:10px 0;border-bottom:1px solid var(--border)">
          <div style="display:flex;justify-content:space-between;align-items:baseline">
            <span style="font-weight:700;color:var(--accent)">${_esc(e.version || '')}</span>
            <span style="color:var(--t3);font-size:0.72rem">${_esc(e.date || '')}</span>
          </div>
          <div style="font-weight:600;margin:4px 0;font-size:0.88rem">${_esc(e.title || '')}</div>
          <ul style="margin:4px 0 0 16px;padding:0;color:var(--t3);font-size:0.78rem">
            ${(e.highlights || []).map(h => `<li style="margin-bottom:2px">${_esc(h)}</li>`).join('')}
          </ul>
        </div>`).join('')}
    </div>
  </div>
  <div style="padding:8px 0;color:var(--t3);font-size:0.78rem">
    Regeneruj: <code style="background:var(--surface);padding:2px 6px;border-radius:4px">ssh claude@192.168.1.61 'cd /home/piotrszmidt/ai-gm &amp;&amp; python3 scripts/generate_showcase_changelog.py'</code>
  </div>`;
}

// ── Init ───────────────────────────────────────────────────────────────────────

export async function init(panel) {
  panel.innerHTML = _HTML;

  document.querySelectorAll('.stab[data-sctab]').forEach(btn => {
    btn.addEventListener('click', () => _switchTab(btn.dataset.sctab));
  });

  await _switchTab('historia');
}

Object.assign(window, {
  scSave,
  scHistoriaIntroSave, scHistoriaEditStage, scHistoriaAddStage,
  scHistoriaDeleteStage, scHistoriaMoveStage, scStageSave, scStageCancel,
  scSwiatIntroSave, scKrainaEdit, scKrainaSave, scKrainaCancel,
  scFaqAdd, scFaqEdit, scFaqDelete, scFaqMove, scFaqSave, scFaqCancel,
  scRmAddItem, scRmDeleteItem, scRmSaveAll,
});
