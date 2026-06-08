/**
 * FADM-P12 (#414) — sekcja Wiedza: baza dokumentów / RAG.
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

// ── Helpers ────────────────────────────────────────────────────────────────────
function _esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
const _loading = cols => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr>`;
const _errRow  = (cols, msg) => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--red);font-size:0.8rem">Błąd: ${_esc(msg)}</td></tr>`;

function filterTableGeneric(input, tableId, nameClass) {
  const q = input.value.toLowerCase();
  document.querySelectorAll(`#${tableId} tbody tr`).forEach(tr => {
    const cell = tr.querySelector(`.${nameClass}`);
    tr.style.display = (!q || (cell && cell.textContent.toLowerCase().includes(q))) ? '' : 'none';
  });
}

// ── Functions ─────────────────────────────────────────────────────────────────

async function _loadKnowledge() {
  const tbody = document.getElementById('knowledge-tbody');
  if (!tbody) return;
  tbody.innerHTML = _loading(6);
  try {
    const d = await apiFetch('/api/admin/knowledge-book');
    const items = d.items || [];
    if (!items.length) { tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--t3)">Brak wskazówek</td></tr>`; return; }
    const catBadge = { general:'badge-slate', magic:'badge-blue', combat:'badge-red', mechanics:'badge-amber', exploration:'badge-green', economy:'badge-slate' };
    tbody.innerHTML = items.map(k => `<tr>
      <td class="td-mono" style="font-size:0.72rem">${_esc(k.tip_key)}</td>
      <td class="td-sticky td-name editable" onclick="mechPatchEdit(this,'/api/admin/knowledge-book/${_esc(k.tip_key)}','title')">${_esc(k.title||k.tip_key)}</td>
      <td><span class="badge ${catBadge[k.category]||'badge-slate'}">${_esc(k.category||'—')}</span></td>
      <td class="td-mono editable" onclick="mechPatchEdit(this,'/api/admin/knowledge-book/${_esc(k.tip_key)}','sort_order')">${k.sort_order??0}</td>
      <td><span class="badge ${k.is_active?'badge-green':'badge-slate'}">${k.is_active?'●':'○'}</span></td>
      <td class="td-actions">
        <button class="btn-icon" title="Edytuj" onclick="openKnowledgeModal(${JSON.stringify(k).replace(/"/g,'&quot;')})">✎</button>
        <button class="btn-icon danger" title="Usuń" onclick="deleteKnowledge('${_esc(k.tip_key)}',this)">✕</button>
      </td>
    </tr>`).join('');
  } catch(e) { tbody.innerHTML = _errRow(6, e.message); }
}

function openKnowledgeModal(prefillOrNull) {
  const p = typeof prefillOrNull === 'string' ? JSON.parse(prefillOrNull) : (prefillOrNull || {});
  const isEdit = !!p.tip_key;
  const CATS = ['general','magic','combat','mechanics','exploration','economy'];
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="max-width:520px">
    <div class="modal-head"><span>${isEdit ? 'Edytuj wskazówkę' : 'Nowa wskazówka'}</span><button onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body" style="display:flex;flex-direction:column;gap:10px">
      ${isEdit ? '' : `<div class="form-row"><label>Klucz *</label><input id="kn-key" class="field-input form-mono" placeholder="np. combat_basics" /></div>`}
      <div class="form-row"><label>Tytuł *</label><input id="kn-title" class="field-input" value="${_esc(p.title||'')}" /></div>
      <div class="form-row"><label>Kategoria</label>
        <select id="kn-cat" class="field-input">${CATS.map(c=>`<option value="${c}"${p.category===c?' selected':''}>${c}</option>`).join('')}</select>
      </div>
      <div class="form-row"><label>Treść</label><textarea id="kn-body" class="field-input" rows="5">${_esc(p.body||'')}</textarea></div>
      <div class="form-row"><label>Kolejność</label><input id="kn-order" class="field-input" type="number" value="${p.sort_order??0}" style="width:100px" /></div>
      <div class="form-row"><label><input type="checkbox" id="kn-active" ${p.is_active!==false?'checked':''} /> Aktywna</label></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" onclick="saveKnowledge('${_esc(p.tip_key||'')}',this)">Zapisz</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
}

async function saveKnowledge(existingKey, btn) {
  const g = id => document.getElementById(id);
  const title = g('kn-title')?.value?.trim();
  if (!title) { showToast('Wypełnij tytuł.', 'error'); return; }
  const key = existingKey || g('kn-key')?.value?.trim();
  if (!key) { showToast('Wypełnij klucz.', 'error'); return; }
  const body = { tip_key: key, title, body: g('kn-body')?.value?.trim()||'', category: g('kn-cat')?.value||'general', sort_order: parseInt(g('kn-order')?.value)||0, is_active: g('kn-active')?.checked??true };
  btn.disabled = true; btn.textContent = '⏳';
  try {
    if (existingKey) await apiFetch(`/api/admin/knowledge-book/${key}`, { method: 'PATCH', body: JSON.stringify(body) });
    else await apiFetch('/api/admin/knowledge-book', { method: 'POST', body: JSON.stringify(body) });
    btn.closest('.modal-overlay').remove();
    await _loadKnowledge();
    window._loadToolsKnowledge?.();
    showToast(existingKey ? 'Zapisano.' : 'Dodano wskazówkę.', 'success');
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; btn.textContent = 'Zapisz'; }
}

async function deleteKnowledge(key, btn) {
  if (!confirm(`Usunąć wskazówkę "${key}"?`)) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/knowledge-book/${key}`, { method: 'DELETE' });
    await _loadKnowledge();
    showToast('Usunięto.', 'success');
  } catch(e) { showToast(e.message||'Błąd.','error'); btn.disabled = false; }
}

// ── Init ───────────────────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = `<div id="section-knowledge">
      <div class="section-header">
        <div>
          <div class="section-heading">Wiedza</div>
          <div class="section-sub">Wskazówki i porady wyświetlane graczom</div>
        </div>
        <button class="btn btn-primary btn-sm" onclick="openKnowledgeModal(null)">+ Dodaj wskazówkę</button>
      </div>
      <div class="card">
        <div class="toolbar">
          <div class="search-box">
            <span class="search-box-icon">🔍</span>
            <input type="text" placeholder="Szukaj wskazówek…" oninput="filterTableGeneric(this,'knowledge-table','td-name')">
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table" id="knowledge-table">
            <thead><tr>
              <th><div class="th-inner">Klucz</div></th>
              <th class="td-sticky"><div class="th-inner">Tytuł</div></th>
              <th><div class="th-inner">Kategoria</div></th>
              <th><div class="th-inner">Kolejność</div></th>
              <th><div class="th-inner">Aktywna</div></th>
              <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
            </tr></thead>
            <tbody id="knowledge-tbody"></tbody>
          </table>
        </div>
      </div>
  </div>`;
  _loadKnowledge();
}

Object.assign(window, { openKnowledgeModal, saveKnowledge, deleteKnowledge, filterTableGeneric });
