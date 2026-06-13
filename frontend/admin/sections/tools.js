/**
 * FADM-P10 (#412) — sekcja Narzędzia: runner, sandbox bojowy, REST, wiedza, MCP, obrazy, Playwright.
 * Port 1:1 z admin_panel_v3/index.html.
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

// ── Helpers ────────────────────────────────────────────────────────────────────
function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
const _loading = cols => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr>`;
const _errRow  = (cols, msg) => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--red);font-size:0.8rem">Błąd: ${_esc(msg)}</td></tr>`;

// ── Module-level state ─────────────────────────────────────────────────────────

// Test Runner
let _toolsScenarios = [];
const _toolsTabLoaded = new Set();

// MCP
let _mcpDemoToken = null;
let _mcpDemoCamps = [];

const _MCP_URL = "https://aigm-dev.studio-colorbox.com/mcp";
const _MCP_TOOLS = [
  { name:"initialize_player_session", star:true,  write:true,  desc:"Loguje się jako gracz testowy i ładuje aktywną kampanię + postać. Wywołaj jako pierwsze." },
  { name:"submit_player_turn",        star:true,  write:true,  desc:"Wysyła akcję gracza do MG i zwraca narrację. Główna pętla rozgrywki." },
  { name:"change_player_zone",        star:false, write:true,  desc:"Przełącza strefę walki: zwarcie ↔ dystans." },
  { name:"flee_from_combat",          star:false, write:true,  desc:"Próba ucieczki z walki (traci XP i łupy)." },
  { name:"get_campaign_summary",      star:true,  write:false, desc:"Pełny snapshot kampanii: postać, plan MG, tury, ekwipunek, NPCs." },
  { name:"get_full_campaign_context", star:false, write:false, desc:"Dump w markdown — idealny do wklejenia w Perplexity / ChatGPT." },
  { name:"get_system_health",         star:false, write:false, desc:"Aktywne kampanie, rozmiar DB, ostatni LLM call, błędy ostatniej godziny." },
  { name:"get_llm_performance",       star:false, write:false, desc:"Statystyki wywołań LLM wg okresu (24h / 7d / 30d) i typu." },
  { name:"get_player_stats",          star:false, write:false, desc:"Aktywność graczy: tury, śmierci, XP, aktywna kampania." },
  { name:"get_world_analytics",       star:false, write:false, desc:"Lokacje, wrogowie, pending review, hexes, bank pomysłów." },
  { name:"query_game_events",         star:false, write:false, desc:"Filtrowany log zdarzeń (combat_victory, player_death, long_rest…)." },
  { name:"query_action_log",          star:false, write:false, desc:"Paginowany log tur kampanii wg trasy / zakresu tur." },
  { name:"get_error_log",             star:false, write:false, desc:"Błędy i ostrzeżenia z game_events + llm_call_log." },
];

// Rest Sandbox
let _rstState = { campId: null, charId: null, heroId: null };
let _rstLog = [];

// Combat Sandbox
const _csState = {
  heroes: [], enemies: [], selectedHero: null, selectedEnemies: new Set(),
  campaignId: null, characterId: null, combatState: null, characterFull: null,
  log: [], busy: false,
};
const ZONE_LABEL = { engaged: 'Zwarcie', ranged: 'Dystans' };

// Image Generator
let _imgLastUrl = '';
let _imgLastFilename = '';
let _imgActivePreset = '';
let _imgRefB64 = '';
let _imgRefFilename = '';
let _imgGalleryPickMode = false;

// ── Stab bar wiring ────────────────────────────────────────────────────────────
function _wireStabBar() {
  document.getElementById('tools-stab-bar')?.querySelectorAll('.stab[data-toolstab]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#tools-stab-bar .stab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.toolstab;
      document.querySelectorAll('#section-tools .stab-panel').forEach(p => { p.style.display = 'none'; p.classList.remove('active'); });
      const panel = document.getElementById(`toolstab-${tab}`);
      if (panel) { panel.style.display = ''; panel.classList.add('active'); }
      if (!_toolsTabLoaded.has(tab)) {
        _toolsTabLoaded.add(tab);
        if (tab === 'combat')    _loadCombatSandbox().catch(e => { _toolsTabLoaded.delete(tab); console.warn('tools combat tab', e.message); });
        if (tab === 'rest')      _loadRestSandbox().catch(e =>   { _toolsTabLoaded.delete(tab); console.warn('tools rest tab', e.message); });
        if (tab === 'knowledge') _loadToolsKnowledge().catch(e =>{ _toolsTabLoaded.delete(tab); console.warn('tools knowledge tab', e.message); });
        if (tab === 'mcp')       _loadToolsMcp().catch(e =>      { _toolsTabLoaded.delete(tab); console.warn('tools mcp tab', e.message); });
        if (tab === 'images')    _loadImgGallery().catch(e =>    { _toolsTabLoaded.delete(tab); console.warn('tools images tab', e.message); });
        if (tab === 'playwright') _loadToolsPlaywright().catch(e => { _toolsTabLoaded.delete(tab); console.warn('tools playwright tab', e.message); });
        if (tab === 'dblint')    _loadToolsDbLint().catch(e =>     { _toolsTabLoaded.delete(tab); console.warn('tools dblint tab', e.message); });
      }
    });
  });
}

function _wireImgPresets() {
  document.querySelectorAll('#section-tools .img-preset').forEach(btn => {
    btn.addEventListener('click', () => {
      const ta = document.getElementById('img-prompt');
      const preset = btn.dataset.preset;
      const prefix = btn.dataset.prefix + ' ';
      if (_imgActivePreset === preset) {
        document.querySelectorAll('#section-tools .img-preset').forEach(b => {
          ta.value = ta.value.replace(b.dataset.prefix + ' ', '').trim();
          b.classList.remove('on');
        });
        _imgActivePreset = '';
      } else {
        document.querySelectorAll('#section-tools .img-preset').forEach(b => {
          ta.value = ta.value.replace(b.dataset.prefix + ' ', '').trim();
          b.classList.remove('on');
        });
        ta.value = prefix + ta.value.trimStart();
        btn.classList.add('on');
        _imgActivePreset = preset;
      }
      ta.focus();
    });
  });

  const stepsSlider = document.getElementById('img-steps');
  const stepsVal = document.getElementById('img-steps-val');
  if (stepsSlider) stepsSlider.addEventListener('input', () => { if (stepsVal) stepsVal.textContent = stepsSlider.value; });

  const denoiseSlider = document.getElementById('img-ref-denoise');
  const denoiseVal = document.getElementById('img-ref-denoise-val');
  if (denoiseSlider) denoiseSlider.addEventListener('input', () => { if (denoiseVal) denoiseVal.textContent = denoiseSlider.value + '%'; });
}

// ── Test Runner ────────────────────────────────────────────────────────────────
async function _loadTools() {
  try {
    const d = await apiFetch('/api/test_runner/scenarios');
    _toolsScenarios = d.scenarios || d.items || [];
    const sel = document.getElementById('tools-scenario');
    if (sel) {
      sel.innerHTML = `<option value="">— Wybierz scenariusz —</option>` +
        _toolsScenarios.map(s => `<option value="${_esc(s.filename||s.name||s)}">${_esc(s.title||s.name||s.filename||s)}</option>`).join('');
    }
  } catch(e) {
    const sel = document.getElementById('tools-scenario');
    if (sel) sel.innerHTML = `<option value="">⚠ ${_esc(e.message)}</option>`;
  }
  const runBtn = document.getElementById('tools-run-tests');
  if (runBtn && !runBtn._wired) {
    runBtn._wired = true;
    runBtn.addEventListener('click', async () => {
      const sel = document.getElementById('tools-scenario');
      const out = document.getElementById('tools-run-out');
      const file = sel?.value;
      if (!file) { showToast('Wybierz scenariusz.', 'error'); return; }
      runBtn.disabled = true; runBtn.textContent = '⏳';
      out.textContent = 'Uruchamianie…';
      try {
        const r = await apiFetch('/api/test_runner/start', { method:'POST', body: JSON.stringify({ scenario: file }) });
        const runId = r.run_id || r.id || '?';
        out.innerHTML = `Uruchomiono: <code>${_esc(runId)}</code> · <a href="#" onclick="event.preventDefault();_pollTestStatus('${_esc(runId)}',this)" style="color:var(--accent)">Sprawdź status</a>`;
        showToast('Test uruchomiony.', 'success');
      } catch(e) { out.innerHTML = `<span style="color:#e55">${_esc(e.message)}</span>`; showToast(e.message, 'error'); }
      finally { runBtn.disabled = false; runBtn.textContent = '▶ Uruchom'; }
    });
  }
  const refreshBtn = document.getElementById('tools-refresh-runs');
  if (refreshBtn && !refreshBtn._wired) {
    refreshBtn._wired = true;
    refreshBtn.addEventListener('click', _refreshToolsRuns);
  }
  _refreshToolsRuns();
}

function _refreshToolsRuns() {
  const tbody = document.querySelector('#tools-runs-table tbody');
  const cnt = document.getElementById('tools-runs-count');
  if (!tbody) return;
  if (!_toolsScenarios.length) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;padding:18px;color:var(--t3)">Brak scenariuszy.</td></tr>';
    if (cnt) cnt.textContent = '0';
    return;
  }
  if (cnt) cnt.textContent = `${_toolsScenarios.length} scenariuszy`;
  tbody.innerHTML = _toolsScenarios.map(s => {
    const name = s.title || s.name || s.filename || s;
    const fname = s.filename || s.name || s;
    return `<tr>
      <td>${_esc(name)}</td>
      <td class="td-mono" style="font-size:0.75rem">${_esc(fname)}</td>
      <td class="td-actions"><button class="btn btn-sm btn-secondary" onclick="_runScenarioFromList('${_esc(fname)}',this)">▶ Uruchom</button></td>
    </tr>`;
  }).join('');
}

async function _runScenarioFromList(file, btn) {
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const r = await apiFetch('/api/test_runner/start', { method:'POST', body: JSON.stringify({ scenario: file }) });
    const runId = r.run_id || r.id || '?';
    btn.textContent = `▶ ${runId}`;
    showToast(`Uruchomiono ${runId}`, 'success');
    setTimeout(() => { btn.disabled = false; btn.textContent = '▶ Uruchom'; }, 3000);
  } catch(e) { showToast(e.message, 'error'); btn.disabled = false; btn.textContent = '▶ Uruchom'; }
}

async function _pollTestStatus(runId, link) {
  try {
    const s = await apiFetch(`/api/test_runner/status/${runId}`);
    const status = s.status || s.state || 'unknown';
    link.parentElement.insertAdjacentHTML('beforeend', `<div style="font-size:0.72rem;color:var(--t3);margin-top:4px">Status: <code>${_esc(status)}</code> · faza: <code>${_esc(s.phase||'-')}</code></div>`);
  } catch(e) { showToast(e.message, 'error'); }
}

// ── Playwright Regression panel ────────────────────────────────────────────────
async function _loadToolsPlaywright() {
  const listEl = document.getElementById('pw-spec-list');
  const runAllBtn = document.getElementById('pw-run-all');
  if (!listEl) return;
  listEl.innerHTML = '<div style="color:var(--t3);font-size:0.78rem">Ładowanie…</div>';
  try {
    const d = await apiFetch('/api/test_runner/playwright-specs');
    const specs = d.specs || [];
    if (!specs.length) {
      listEl.innerHTML = '<div style="color:var(--t3);font-size:0.78rem">Brak spec files w <code>playwright/ux/</code></div>';
    } else {
      const groups = {};
      specs.forEach(s => { (groups[s.group || 'ux'] = groups[s.group || 'ux'] || []).push(s); });
      const GROUP_LABEL = { regression: '🐞 Regresja', acceptance: '✅ Acceptance (C1–C19)', admin3: '🛠 Admin3 smoke', ux: 'Inne' };
      const specCard = (s) => {
        const issueBadge = s.issue
          ? `<a href="https://github.com/szmidtpiotr/ai-gm/issues/${s.issue}" target="_blank" rel="noopener"
              style="display:inline-block;background:var(--accent,#6c8);color:#000;font-size:0.65rem;font-weight:700;padding:1px 5px;border-radius:3px;text-decoration:none;margin-right:4px">#${s.issue}</a>`
          : '';
        const countBadge = s.testCount
          ? `<span style="font-size:0.65rem;color:var(--t3);margin-left:4px">${s.testCount} test${s.testCount !== 1 ? 'y' : ''}</span>`
          : '';
        const desc = s.description
          ? `<div style="font-size:0.72rem;color:var(--t2);margin-top:5px;line-height:1.5">${_esc(s.description)}</div>`
          : '';
        const name = s.filename.split('/').pop().replace('.spec.js','');
        return `
          <div style="padding:10px 12px;border:1px solid var(--bdr,#333);border-radius:6px;display:flex;flex-direction:column;gap:0">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">
              <div style="flex:1;min-width:0">
                <div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;margin-bottom:2px">
                  ${issueBadge}
                  <span style="font-weight:600;font-size:0.82rem;color:var(--t1)">${_esc(name)}</span>
                  ${countBadge}
                </div>
                ${desc}
              </div>
              <button class="btn btn-sm btn-secondary" style="flex-shrink:0" onclick="_runPlaywrightSpec('${_esc(s.filename)}',this)">▶</button>
            </div>
          </div>`;
      };
      listEl.innerHTML = Object.keys(groups).sort().map(g => `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:6px">
          <span style="font-size:0.72rem;font-weight:700;color:var(--t2);text-transform:uppercase;letter-spacing:.04em">${GROUP_LABEL[g] || g}</span>
          <button class="btn btn-sm btn-secondary" style="font-size:0.68rem;padding:2px 8px" onclick="_runPlaywrightSpec('${_esc(g)}',this)">▶ grupa</button>
        </div>
        ${groups[g].map(specCard).join('')}
      `).join('');
    }
  } catch(e) {
    listEl.innerHTML = `<div style="color:var(--red,#e55);font-size:0.78rem">${_esc(e.message)}</div>`;
  }
  if (runAllBtn && !runAllBtn._wired) {
    runAllBtn._wired = true;
    runAllBtn.addEventListener('click', () => _runPlaywrightSpec(null, runAllBtn));
  }
}

async function _runPlaywrightSpec(filename, btn) {
  const logEl = document.getElementById('pw-log');
  const statusEl = document.getElementById('pw-status');
  if (!logEl) return;
  if (btn) { btn.disabled = true; }
  logEl.innerHTML = `<span style="color:var(--t3)">Uruchamianie: ${_esc(filename || 'wszystkie')} …</span>`;
  if (statusEl) { statusEl.textContent = '⏳ Running…'; statusEl.style.color = 'var(--t3)'; }

  const append = (line, isErr = false) => {
    const el = document.createElement('div');
    el.style.cssText = `white-space:pre-wrap;color:${isErr ? '#f88' : 'var(--t2)'}`;
    el.textContent = line;
    logEl.appendChild(el);
    logEl.scrollTop = logEl.scrollHeight;
  };

  const tok = localStorage.getItem('aigm_admin_token') || '';
  try {
    const resp = await fetch('/api/test_runner/playwright-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${tok}` },
      body: JSON.stringify({ spec: filename }),
    });
    if (!resp.ok) { throw new Error(`HTTP ${resp.status}`); }

    logEl.innerHTML = '';
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    let done = false;
    let success = false;

    while (!done) {
      const { value, done: d } = await reader.read();
      done = d;
      if (value) buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const obj = JSON.parse(line.slice(6));
          if (obj.type === 'log') append(obj.line, obj.isErr);
          else if (obj.type === 'done') { success = obj.success; done = true; }
        } catch (_) { /* parse error */ }
      }
    }

    if (statusEl) {
      statusEl.textContent = success ? '✓ Passed' : '✗ Failed';
      statusEl.style.color = success ? '#4c8' : '#e55';
    }
    showToast(success ? 'Testy przeszły ✓' : 'Testy nie przeszły ✗', success ? 'success' : 'error');
  } catch(e) {
    append(`Błąd: ${e.message}`, true);
    if (statusEl) { statusEl.textContent = '✗ Error'; statusEl.style.color = '#e55'; }
    showToast(e.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = btn.id === 'pw-run-all' ? '▶ Uruchom wszystkie' : '▶';
    }
  }
}

// ── Knowledge ─────────────────────────────────────────────────────────────────
async function _loadToolsKnowledge() {
  const host = document.getElementById('toolstab-knowledge-content');
  if (!host) return;
  host.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>';
  try {
    const d = await apiFetch('/api/admin/knowledge-book');
    const items = d.items || [];
    const addBtn = `<div style="display:flex;justify-content:flex-end;margin-bottom:8px"><button class="btn btn-sm btn-primary" onclick="openKnowledgeModal(null)">+ Dodaj wskazówkę</button></div>`;
    if (!items.length) {
      host.innerHTML = addBtn + '<div style="text-align:center;padding:24px;color:var(--t3)">Brak wskazówek.</div>';
      return;
    }
    host.innerHTML = addBtn + `<div class="card"><div class="card-header"><span class="card-title">Księga Wiedzy</span><span class="card-count">${items.length}</span></div>
      <div class="table-wrap"><table class="data-table" id="tools-knowledge-table"><thead><tr>
        <th><div class="th-inner">Klucz</div></th>
        <th class="td-sticky"><div class="th-inner">Tytuł</div></th>
        <th><div class="th-inner">Kategoria</div></th>
        <th><div class="th-inner">Kolejność</div></th>
        <th><div class="th-inner">Aktywna</div></th>
        <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
      </tr></thead><tbody>${items.map(k => `<tr>
        <td class="td-mono" style="font-size:0.72rem">${_esc(k.tip_key)}</td>
        <td class="td-sticky td-name">${_esc(k.title)}</td>
        <td class="td-muted">${_esc(k.category||'—')}</td>
        <td class="td-mono">${k.sort_order??0}</td>
        <td>${k.is_active?'<span class="badge badge-green">✓</span>':'<span class="badge badge-slate">—</span>'}</td>
        <td class="td-actions">
          <button class="btn-icon" onclick="openKnowledgeModal(${JSON.stringify(k).replace(/"/g,'&quot;')})">✎</button>
          <button class="btn-icon btn-icon--danger" onclick="_deleteKnowledgeTip('${_esc(k.tip_key)}')">🗑</button>
        </td>
      </tr>`).join('')}</tbody></table></div></div>`;
    host._reload = _loadToolsKnowledge;
  } catch(e) { host.innerHTML = `<div style="padding:24px;text-align:center;color:var(--red)">${_esc(e.message)}</div>`; }
}

async function _deleteKnowledgeTip(key) {
  if (!confirm(`Usunąć wskazówkę "${key}"?`)) return;
  try {
    await apiFetch(`/api/admin/knowledge-book/${key}`, { method: 'DELETE' });
    showToast('Usunięto.', 'success');
    _loadToolsKnowledge();
  } catch(e) { showToast(e.message, 'error'); }
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
    await _loadToolsKnowledge();
    showToast(existingKey ? 'Zapisano.' : 'Dodano wskazówkę.', 'success');
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; btn.textContent = 'Zapisz'; }
}

async function deleteKnowledge(key, btn) {
  if (!confirm(`Usunąć wskazówkę "${key}"?`)) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/knowledge-book/${key}`, { method: 'DELETE' });
    await _loadToolsKnowledge();
    showToast('Usunięto.', 'success');
  } catch(e) { showToast(e.message||'Błąd.','error'); btn.disabled = false; }
}

// ── MCP helpers ────────────────────────────────────────────────────────────────
async function _mcpApiFetch(path, options = {}) {
  const token = localStorage.getItem('aigm_admin_token') || '';
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const resp = await fetch(`/api${path}`, { ...options, headers });
  let body = null;
  try { body = await resp.json(); } catch { /* non-json */ }
  if (!resp.ok) {
    const msg = body?.detail || `HTTP ${resp.status}`;
    throw new Error(String(msg).slice(0, 200));
  }
  return body;
}

async function _loadToolsMcp() {
  const host = document.getElementById('toolstab-mcp');
  if (!host) return;
  const writeCount = _MCP_TOOLS.filter(t => t.write).length;
  const readCount  = _MCP_TOOLS.filter(t => !t.write).length;
  host.innerHTML = `<div class="mcp-tab" style="margin-top:12px">
    <div class="mcp-server-card">
      <div class="mcp-server-header">
        <div>
          <div class="mcp-server-name">🤖 AI-GM MCP Server</div>
          <div class="mcp-server-sub">Model Context Protocol — AI-queryable + playable game</div>
        </div>
        <span class="mcp-status-badge mcp-checking" id="mcp-tab-badge">⏳ Checking…</span>
      </div>
      <div class="mcp-url-row">
        <code class="mcp-url-code">${_MCP_URL}</code>
        <button class="mcp-copy-btn" id="mcp-copy-btn">📋 Kopiuj</button>
      </div>
      <div class="mcp-meta-row">
        <span>Transport: <strong>Streamable HTTP</strong></span>
        <span>·</span>
        <span>Narzędzia: <strong>${_MCP_TOOLS.length}</strong> (${writeCount} write, ${readCount} read)</span>
        <span>·</span>
        <span>Dostęp: <strong>Read + Write</strong></span>
      </div>
    </div>
    <div class="mcp-two-col">
      <div class="mcp-connect-card">
        <div class="mcp-section-title">🔍 Perplexity</div>
        <div class="mcp-connect-steps">
          <div class="mcp-step"><span class="mcp-step-label">URL:</span><code>${_MCP_URL}</code></div>
          <div class="mcp-step"><span class="mcp-step-label">Type:</span><code>Streamable HTTP</code></div>
        </div>
        <div class="mcp-examples-title">Prompt startowy dla Perplexity:</div>
        <ul class="mcp-examples">
          <li>„Wywołaj initialize_player_session, potem get_full_campaign_context i zagraj kilka tur."</li>
          <li>„Jesteś wojownikiem w polskim RPG. Zacznij od initialize_player_session."</li>
        </ul>
      </div>
      <div class="mcp-connect-card">
        <div class="mcp-section-title">⌨️ Claude Code / Desktop</div>
        <div class="mcp-connect-steps" style="margin-bottom:14px">
          <div class="mcp-step-label" style="margin-bottom:6px">Claude Code CLI:</div>
          <pre class="mcp-code-block">claude mcp add ai-gm \\
  --transport http \\
  ${_MCP_URL}</pre>
        </div>
        <div class="mcp-connect-steps">
          <div class="mcp-step-label" style="margin-bottom:6px">claude_desktop_config.json:</div>
          <pre class="mcp-code-block">{ "mcpServers": {
  "ai-gm": {
    "url": "${_MCP_URL}"
  }
}}</pre>
        </div>
      </div>
    </div>
    <div class="mcp-tools-card">
      <div class="mcp-section-title">🔧 ${_MCP_TOOLS.length} dostępnych narzędzi</div>
      <div class="mcp-tools-list">${_MCP_TOOLS.map(t => `
        <div class="mcp-tool-row">
          <code class="mcp-tool-name${t.star?' mcp-tool-star':''}">${t.star?'★ ':''}${t.name}</code>
          <span class="mcp-tool-badge${t.write?' mcp-tool-write':' mcp-tool-read'}">${t.write?'write':'read'}</span>
          <span class="mcp-tool-desc">${t.desc}</span>
        </div>`).join('')}
      </div>
    </div>
    <div class="mcp-config-section">
      <h4>Konfiguracja sesji MCP</h4>
      <div class="mcp-config-row">
        <label>Gracz:</label>
        <select id="mcp-cfg-user" class="field-input mcp-live-sel" disabled style="font-size:0.82rem"><option value="">Ładowanie…</option></select>
        <label>Bohater:</label>
        <select id="mcp-cfg-hero" class="field-input mcp-live-sel" disabled style="font-size:0.82rem"><option value="">— wybierz gracza —</option></select>
        <label>Kampania:</label>
        <span id="mcp-cfg-camp-display" class="mcp-cfg-camp-display">—</span>
        <button id="mcp-cfg-save" class="btn btn-primary btn-sm" disabled>Zapisz</button>
      </div>
      <div id="mcp-cfg-status" class="mcp-cfg-status">Ładowanie aktywnej sesji…</div>
    </div>
    <div class="mcp-live-section">
      <div class="mcp-live-header">
        <span class="mcp-live-title">🎮 Podgląd na żywo</span>
        <select id="mcp-camp-sel" class="field-input mcp-live-sel" disabled style="font-size:0.82rem"><option value="">Ładowanie kampanii…</option></select>
        <button id="mcp-iframe-reload" class="mcp-reload-btn">↺ Załaduj</button>
      </div>
      <div id="mcp-diag-bar" class="mcp-diag-bar" hidden></div>
      <div class="mcp-iframe-wrap">
        <iframe id="mcp-player-iframe" src="about:blank"></iframe>
      </div>
    </div>
  </div>`;

  document.getElementById('mcp-copy-btn')?.addEventListener('click', () => {
    navigator.clipboard.writeText(_MCP_URL).then(() => {
      const btn = document.getElementById('mcp-copy-btn');
      btn.textContent = '✓ Skopiowano';
      setTimeout(() => { btn.textContent = '📋 Kopiuj'; }, 2000);
    }).catch(() => {});
  });

  document.getElementById('mcp-iframe-reload')?.addEventListener('click', _mcpLoadSelectedCampaign);
  document.getElementById('mcp-camp-sel')?.addEventListener('change', _mcpLoadSelectedCampaign);

  _mcpInitDemoCampaigns();
  _mcpInitConfig();

  const badge = document.getElementById('mcp-tab-badge');
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 5000);
    const resp = await fetch('/mcp', {
      method:'POST', signal:ctrl.signal,
      headers:{'Content-Type':'application/json','Accept':'application/json, text/event-stream'},
      body:JSON.stringify({jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2025-03-26',capabilities:{},clientInfo:{name:'admin-panel',version:'1'}}}),
    });
    clearTimeout(t);
    badge.className = resp.ok ? 'mcp-status-badge mcp-online' : 'mcp-status-badge mcp-offline';
    badge.textContent = resp.ok ? '● Online' : '● Offline';
  } catch {
    badge.className = 'mcp-status-badge mcp-offline';
    badge.textContent = '● Offline';
  }
}

async function _mcpInitConfig() {
  const userSel  = document.getElementById('mcp-cfg-user');
  const heroSel  = document.getElementById('mcp-cfg-hero');
  const campDisp = document.getElementById('mcp-cfg-camp-display');
  const saveBtn  = document.getElementById('mcp-cfg-save');
  const statusEl = document.getElementById('mcp-cfg-status');
  let _heroMap = {}, _pinnedHeroId = null;

  try {
    const cfg = await _mcpApiFetch('/admin/mcp/config');
    _pinnedHeroId = cfg.hero_id ?? null;
    if (statusEl) statusEl.textContent = cfg.hero_name
      ? `Aktywna: bohater „${cfg.hero_name}" → kampania „${cfg.campaign_title ?? '—'}"`
      : 'Brak przypietej sesji — MCP używa auto-wykrywania.';
  } catch(e) { if (statusEl) statusEl.textContent = `Błąd ładowania: ${e.message}`; }

  const updateCampDisplay = () => {
    const hero = _heroMap[heroSel?.value];
    if (campDisp) campDisp.textContent = hero?.campaign_id ? `#${hero.campaign_id} ${hero.campaign_title||''}`.trim() : '—';
    if (saveBtn) saveBtn.disabled = false;
  };

  const populateHeroes = async (userId) => {
    if (!heroSel) return;
    heroSel.innerHTML = `<option value="">— brak (auto) —</option>`;
    heroSel.disabled = true; if (campDisp) campDisp.textContent = '—'; if (saveBtn) saveBtn.disabled = true;
    if (!_mcpDemoToken) return;
    try {
      const url = userId ? `/api/characters?user_id=${userId}` : `/api/characters`;
      const resp = await fetch(url, { headers:{'Authorization':`Bearer ${_mcpDemoToken}`} });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      const heroes = data.heroes || (Array.isArray(data) ? data : []);
      _heroMap = {};
      heroes.forEach(h => {
        _heroMap[String(h.id)] = h;
        const opt = document.createElement('option');
        opt.value = String(h.id);
        opt.textContent = `${h.name}  (${h.campaign_title || `kampania #${h.campaign_id}` || 'brak kampanii'})`;
        heroSel.appendChild(opt);
      });
      heroSel.disabled = false; if (saveBtn) saveBtn.disabled = false;
      if (_pinnedHeroId && _heroMap[String(_pinnedHeroId)]) {
        heroSel.value = String(_pinnedHeroId); updateCampDisplay();
        const uid = _heroMap[String(_pinnedHeroId)]?.user_id;
        if (uid && userSel) userSel.value = String(uid);
      }
    } catch(e) { heroSel.innerHTML = `<option value="">⚠ ${e.message}</option>`; heroSel.disabled = false; if (saveBtn) saveBtn.disabled = false; }
  };

  const populateUsers = async () => {
    let waited = 0;
    const waitAndLoad = () => { if (_mcpDemoToken || waited >= 3000) _doPopulate(); else { waited += 150; setTimeout(waitAndLoad, 150); } };
    const _doPopulate = async () => {
      try {
        const resp = await fetch('/api/characters', { headers:{'Authorization':`Bearer ${_mcpDemoToken}`} });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const heroes = data.heroes || (Array.isArray(data) ? data : []);
        const seen = new Map();
        heroes.forEach(h => { if (h.user_id && !seen.has(h.user_id)) seen.set(h.user_id, h.user_id); });
        if (userSel) {
          userSel.innerHTML = `<option value="">— wszyscy gracze —</option>`;
          seen.forEach(uid => { const opt=document.createElement('option'); opt.value=String(uid); opt.textContent=`Gracz #${uid}`; userSel.appendChild(opt); });
          userSel.disabled = false;
        }
        populateHeroes(null);
      } catch(e) { if (userSel) { userSel.innerHTML = `<option value="">⚠ ${e.message}</option>`; userSel.disabled = false; } populateHeroes(null); }
    };
    waitAndLoad();
  };

  userSel?.addEventListener('change', () => { _pinnedHeroId = null; populateHeroes(userSel.value ? parseInt(userSel.value) : null); });
  heroSel?.addEventListener('change', updateCampDisplay);
  saveBtn?.addEventListener('click', async () => {
    saveBtn.disabled = true; saveBtn.textContent = 'Zapisywanie…';
    const hero = _heroMap[heroSel?.value] ?? null;
    const heroId = hero ? parseInt(heroSel.value) : null;
    const campId = hero?.campaign_id ?? null;
    try {
      await _mcpApiFetch('/admin/mcp/config', { method:'PUT', body:JSON.stringify({campaign_id:campId,hero_id:heroId}) });
      if (statusEl) statusEl.textContent = hero ? `Aktywna: bohater „${hero.name}" → kampania „${hero.campaign_title||campId}"` : 'Brak przypietej sesji.';
      showToast('Konfiguracja MCP zapisana', 'success');
      if (campId) { const sel=document.getElementById('mcp-camp-sel'); if (sel) { sel.value=String(campId); _mcpLoadSelectedCampaign(); } }
    } catch(e) { showToast(`Błąd zapisu: ${e.message}`, 'error'); }
    finally { saveBtn.disabled = false; saveBtn.textContent = 'Zapisz'; }
  });
  populateUsers();
}

async function _mcpInitDemoCampaigns() {
  const sel = document.getElementById('mcp-camp-sel');
  try {
    const loginResp = await fetch('/api/auth/login', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({username:'demo', password:'demo'}),
    });
    if (!loginResp.ok) throw new Error(`Login failed ${loginResp.status}`);
    const auth = await loginResp.json();
    _mcpDemoToken = auth.access_token;
    localStorage.setItem('token', auth.access_token);
    localStorage.setItem('aigm_access_token', auth.access_token);
    if (auth.refresh_token) localStorage.setItem('aigm_refresh_token', auth.refresh_token);
    localStorage.setItem('user', JSON.stringify({id:auth.user_id,username:auth.username,display_name:auth.display_name,is_admin:auth.is_admin}));
    const campsResp = await fetch('/api/campaigns', { headers:{'Authorization':`Bearer ${_mcpDemoToken}`} });
    if (!campsResp.ok) throw new Error('Brak dostępu do kampanii');
    const campsData = await campsResp.json();
    const all = (campsData.campaigns || (Array.isArray(campsData) ? campsData : [])).sort((a,b) => (b.id??0)-(a.id??0));
    _mcpDemoCamps = all;
    if (sel) {
      sel.innerHTML = '';
      const active = all.filter(c => c.status === 'active'), ended = all.filter(c => c.status !== 'active');
      if (active.length) { const g=document.createElement('optgroup'); g.label='Aktywne'; active.forEach(c => { const o=document.createElement('option'); o.value=c.id; o.textContent=`#${c.id} ${c.title||'Kampania'}`; g.appendChild(o); }); sel.appendChild(g); }
      if (ended.length)  { const g=document.createElement('optgroup'); g.label='Zakończone'; ended.forEach(c => { const o=document.createElement('option'); o.value=c.id; o.textContent=`#${c.id} ${c.title||'Kampania'}`; g.appendChild(o); }); sel.appendChild(g); }
      if (!all.length) sel.innerHTML = `<option value="">Brak kampanii</option>`;
      sel.disabled = false;
      if (active.length) sel.value = String(active[0].id); else if (all.length) sel.value = String(all[0].id);
      _mcpLoadSelectedCampaign();
    }
  } catch(e) { if (sel) { sel.disabled = false; sel.innerHTML = `<option value="">⚠ ${e.message}</option>`; } }
}

function _mcpLoadSelectedCampaign() {
  const sel = document.getElementById('mcp-camp-sel');
  const iframe = document.getElementById('mcp-player-iframe');
  const diagBar = document.getElementById('mcp-diag-bar');
  if (!iframe) return;
  const campId = sel?.value;
  if (!campId) return;
  const camp = _mcpDemoCamps.find(c => String(c.id) === String(campId));
  if (camp?.character_id) localStorage.setItem('aigm_hero_id', String(camp.character_id));
  localStorage.setItem('aigm_campaign_id', String(campId));
  if (diagBar) { diagBar.textContent = '⏳ Ładowanie…'; diagBar.hidden = false; }
  iframe.addEventListener('load', function _onLoad() {
    iframe.removeEventListener('load', _onLoad);
    setTimeout(() => {
      try {
        const doc = iframe.contentDocument;
        if (!doc) { if (diagBar) { diagBar.textContent = '⚠ brak dostępu do iframe (cross-origin?)'; diagBar.hidden = false; } return; }
        const active = doc.querySelector('.screen--active');
        const screenId = active?.id || 'none';
        const heroName = doc.getElementById('character-name-display')?.textContent?.trim() || '—';
        const msgCount = doc.getElementById('chat-messages')?.childElementCount ?? 0;
        if (diagBar) { diagBar.textContent = `Ekran: ${screenId} | Bohater: ${heroName} | Wiad: ${msgCount}`; diagBar.hidden = false; }
      } catch(e) { if (diagBar) { diagBar.textContent = `⚠ Błąd iframe: ${e.message}`; diagBar.hidden = false; } }
    }, 2500);
  });
  iframe.src = '/?_t=' + Date.now();
}

// ── Rest Sandbox ───────────────────────────────────────────────────────────────
async function _loadRestSandbox() {
  const heroesEl = document.getElementById('rst-heroes');
  if (!heroesEl) return;
  heroesEl.innerHTML = '<div style="color:var(--t3);font-size:0.8rem">Ładowanie…</div>';
  try {
    const d = await apiFetch('/api/admin/rest-sandbox/heroes');
    const heroes = d.heroes || [];
    heroesEl.innerHTML = heroes.map(h => `<button class="btn btn-sm btn-secondary rst-hero-btn" data-id="${h.id}" onclick="rstSelectHero(${h.id},'${_esc(h.name)}',this)">${_esc(h.name)} <span style="color:var(--t3);font-size:0.7rem">${_esc(h.archetype||'')}</span></button>`).join('');
    document.getElementById('rst-setup-btn').disabled = true;
  } catch(e) { heroesEl.innerHTML = `<div style="color:var(--red,#e55)">${_esc(e.message)}</div>`; }
}

function rstSelectHero(id, name, btn) {
  document.querySelectorAll('.rst-hero-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _rstState.heroId = id;
  document.getElementById('rst-setup-btn').disabled = false;
}

function _rstLog_(msg) {
  const ts = new Date().toLocaleTimeString('pl');
  _rstLog.unshift(`[${ts}] ${msg}`);
  const logEl = document.getElementById('rst-log');
  if (logEl) logEl.innerHTML = _rstLog.slice(0, 100).map(l => `<div>${_esc(l)}</div>`).join('');
}

async function rstSetup(btn) {
  if (!_rstState.heroId) return;
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const d = await apiFetch('/api/admin/rest-sandbox/setup', { method: 'POST', body: JSON.stringify({ hero_id: _rstState.heroId }) });
    _rstState.campId = d.campaign_id;
    _rstState.charId = d.character_id;
    _rstLog_(`Sandbox przygotowany: ${d.hero?.name || '?'}`);
    document.getElementById('rst-end-btn').style.display = '';
    btn.style.display = 'none';
    await _rstRefreshSheet();
    _rstRenderControls();
  } catch(e) { showToast(e.message||'Błąd.','error'); btn.disabled = false; btn.textContent = 'Przygotuj sandbox'; }
}

async function rstEnd(btn) {
  if (!confirm('Zakończyć sesję rest sandbox?')) return;
  btn.disabled = true;
  try {
    await apiFetch('/api/admin/rest-sandbox/end', { method: 'POST', body: JSON.stringify({ campaign_id: _rstState.campId }) });
    _rstState = { campId: null, charId: null, heroId: null };
    _rstLog_('Sesja zakończona.');
    document.getElementById('rst-end-btn').style.display = 'none';
    const setupBtn = document.getElementById('rst-setup-btn');
    setupBtn.style.display = ''; setupBtn.disabled = true; setupBtn.textContent = 'Przygotuj sandbox';
    document.getElementById('rst-sheet').style.display = 'none';
    document.getElementById('rst-controls').innerHTML = '<div style="color:var(--t3);font-size:0.8rem">Najpierw przygotuj sandbox.</div>';
    document.querySelectorAll('.rst-hero-btn').forEach(b => b.classList.remove('active'));
  } catch(e) { showToast(e.message||'Błąd.','error'); btn.disabled = false; }
}

async function _rstRefreshSheet() {
  if (!_rstState.charId) return;
  try {
    const c = await apiFetch(`/api/admin/rest-sandbox/character/${_rstState.charId}`);
    document.getElementById('rst-name').textContent = `${c.name} (${c.archetype} L${c.level})`;
    document.getElementById('rst-hp-txt').textContent = `${c.hp}/${c.max_hp}`;
    document.getElementById('rst-hp-bar').style.width = `${Math.round((c.hp/c.max_hp)*100)}%`;
    document.getElementById('rst-short-rest-remaining').textContent = c.short_rests_remaining ?? '—';
    document.getElementById('rst-sheet').style.display = '';
  } catch(e) { console.warn('rst sheet', e.message); }
}

function _rstRenderControls() {
  const el = document.getElementById('rst-controls');
  if (!el) return;
  el.innerHTML = `
    <button class="btn btn-sm btn-secondary" onclick="rstBuildCamp(this)">⛺ Rozbij obóz</button>
    <div style="display:flex;align-items:center;gap:8px">
      <label style="font-size:0.82rem"><input type="checkbox" id="rst-safe" onchange="rstSetSafe(this.checked)" /> Teren bezpieczny</label>
    </div>
    <button class="btn btn-sm btn-primary" id="rst-short-btn" onclick="rstShortRest(this)">Krótki odpoczynek</button>
    <button class="btn btn-sm btn-primary" onclick="rstLongRest(this)">Długi odpoczynek</button>
    <button class="btn btn-sm btn-secondary" onclick="rstRollEncounter(this)">Rzut losowego spotkania</button>
    <button class="btn btn-sm btn-danger" onclick="rstResetHero(this)">Reset HP bohatera</button>`;
}

async function rstBuildCamp(btn) {
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const d = await apiFetch('/api/admin/rest-sandbox/build-camp', { method: 'POST', body: JSON.stringify({ campaign_id: _rstState.campId, character_id: _rstState.charId }) });
    _rstLog_(d.already_camped ? 'Obóz już rozbity.' : `Obóz rozbity. Lokacja: ${d.location||'?'}`);
  } catch(e) { _rstLog_('Błąd obozu: ' + e.message); }
  finally { btn.disabled = false; btn.textContent = '⛺ Rozbij obóz'; }
}

async function rstSetSafe(safe) {
  try {
    await apiFetch('/api/admin/rest-sandbox/set-hex-safe', { method: 'POST', body: JSON.stringify({ campaign_id: _rstState.campId, safe }) });
    _rstLog_(`Teren ustawiony na: ${safe ? 'bezpieczny' : 'niebezpieczny'}`);
  } catch(e) { _rstLog_('Błąd: ' + e.message); }
}

async function rstShortRest(btn) {
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const d = await apiFetch('/api/admin/rest-sandbox/short-rest', { method: 'POST', body: JSON.stringify({ campaign_id: _rstState.campId, character_id: _rstState.charId }) });
    _rstLog_(`Krótki odpoczynek: rzut ${d.roll}+${d.con_mod} → HP ${d.hp_before}→${d.hp_after}. Pozostało: ${d.short_rests_remaining}/2`);
    await _rstRefreshSheet();
  } catch(e) { _rstLog_('Błąd: ' + e.message); }
  finally { btn.disabled = false; btn.textContent = 'Krótki odpoczynek'; }
}

async function rstLongRest(btn) {
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const d = await apiFetch('/api/admin/rest-sandbox/long-rest', { method: 'POST', body: JSON.stringify({ campaign_id: _rstState.campId, character_id: _rstState.charId }) });
    _rstLog_(`Długi odpoczynek: HP→${d.hp_after}${d.xp_unlocked?', XP odblokowane':''}`);
    await _rstRefreshSheet();
  } catch(e) { _rstLog_('Błąd: ' + e.message); }
  finally { btn.disabled = false; btn.textContent = 'Długi odpoczynek'; }
}

async function rstRollEncounter(btn) {
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const d = await apiFetch('/api/admin/rest-sandbox/roll-encounter', { method: 'POST', body: JSON.stringify({ campaign_id: _rstState.campId, character_id: _rstState.charId }) });
    _rstLog_(`Spotkanie: rzut ${d.roll}, szansa ${Math.round((d.chance||0)*100)}% → ${d.triggered?'WYZWOLONE!':'Brak spotkania'}. ${d.detail||''}`);
  } catch(e) { _rstLog_('Błąd: ' + e.message); }
  finally { btn.disabled = false; btn.textContent = 'Rzut losowego spotkania'; }
}

async function rstResetHero(btn) {
  if (!confirm('Zresetować HP bohatera?')) return;
  btn.disabled = true;
  try {
    const d = await apiFetch('/api/admin/rest-sandbox/reset-hero', { method: 'POST', body: JSON.stringify({ campaign_id: _rstState.campId, character_id: _rstState.charId }) });
    _rstLog_(`Reset: HP ${d.hp}/${d.max_hp}`);
    await _rstRefreshSheet();
  } catch(e) { _rstLog_('Błąd: ' + e.message); }
  finally { btn.disabled = false; btn.textContent = 'Reset HP bohatera'; }
}

function rstCopyReport() {
  const name = document.getElementById('rst-name')?.textContent || '?';
  const log = _rstLog.join('\n');
  const report = `# Rest Sandbox Report\n\nBohater: ${name}\n\n## Log\n${log}`;
  navigator.clipboard.writeText(report).then(() => showToast('Skopiowano.', 'success'));
}

// ── Combat Sandbox ─────────────────────────────────────────────────────────────
function _csLog(msg) {
  const ts = new Date().toLocaleTimeString('pl-PL', { hour12: false });
  _csState.log.push(`[${ts}] ${msg}`);
  const el = document.getElementById('cs-log');
  if (el) { el.textContent = _csState.log.join('\n'); el.scrollTop = el.scrollHeight; }
}

async function _loadCombatSandbox() {
  _csState.log = [];
  try {
    const [h, e] = await Promise.all([
      apiFetch('/api/admin/sandbox/heroes'),
      apiFetch('/api/admin/sandbox/enemies'),
    ]);
    _csState.heroes = h.heroes || [];
    _csState.enemies = e.enemies || [];
  } catch(err) { showToast('Błąd ładowania: '+err.message, 'error'); return; }
  _csRenderHeroPicker(); _csRenderEnemyPicker();
  _csBindControls();
}

function _csRenderHeroPicker() {
  const host = document.getElementById('cs-hero-picker');
  if (!host) return;
  if (!_csState.heroes.length) { host.innerHTML = '<div style="color:var(--t3);font-size:0.78rem">Brak bohaterów.</div>'; return; }
  host.innerHTML = _csState.heroes.map(h => {
    const hid = h.id ?? h.character_id;
    const sel = (_csState.selectedHero?.id ?? _csState.selectedHero?.character_id) === hid;
    return `<button class="btn ${sel?'btn-primary':'btn-secondary'} btn-sm" data-hero-id="${hid}" style="justify-content:flex-start;text-align:left;font-size:0.78rem">${_esc(h.name||'?')} <span style="opacity:0.7;margin-left:auto">${_esc(h.archetype||'')}</span></button>`;
  }).join('');
  host.querySelectorAll('button[data-hero-id]').forEach(b => b.addEventListener('click', () => {
    const id = parseInt(b.dataset.heroId,10);
    _csState.selectedHero = _csState.heroes.find(h => (h.id ?? h.character_id) === id);
    _csRenderHeroPicker();
  }));
}

function _csRenderEnemyPicker() {
  const host = document.getElementById('cs-enemy-picker');
  const search = document.getElementById('cs-enemy-search');
  if (!host) return;
  const q = (search?.value || '').toLowerCase();
  const filtered = _csState.enemies.filter(e => !q || (e.label||e.key||'').toLowerCase().includes(q));
  if (!filtered.length) { host.innerHTML = '<div style="color:var(--t3);font-size:0.74rem;padding:6px">Brak wyników.</div>'; return; }
  host.innerHTML = filtered.slice(0,80).map(e => {
    const checked = _csState.selectedEnemies.has(e.key);
    return `<label style="display:flex;align-items:center;gap:6px;font-size:0.78rem;cursor:pointer;padding:3px 4px;border-radius:3px"><input type="checkbox" data-enemy-key="${_esc(e.key)}" ${checked?'checked':''}>${_esc(e.label||e.key)} <span style="opacity:0.6;font-size:0.7rem;margin-left:auto">HP ${e.hp_base??'—'} · AC ${e.ac_base??'—'}</span></label>`;
  }).join('');
  host.querySelectorAll('input[data-enemy-key]').forEach(cb => cb.addEventListener('change', () => {
    const k = cb.dataset.enemyKey;
    if (cb.checked) _csState.selectedEnemies.add(k); else _csState.selectedEnemies.delete(k);
    _csRenderEnemySummary();
  }));
  _csRenderEnemySummary();
}

function _csRenderEnemySummary() {
  const el = document.getElementById('cs-enemy-summary');
  if (!el) return;
  el.textContent = _csState.selectedEnemies.size ? `Wybrano: ${_csState.selectedEnemies.size}` : '';
}

function _csBindControls() {
  const search = document.getElementById('cs-enemy-search');
  if (search && !search._wired) { search._wired = true; search.addEventListener('input', () => _csRenderEnemyPicker()); }
  const setup = document.getElementById('cs-setup-btn');
  if (setup && !setup._wired) { setup._wired = true; setup.addEventListener('click', _csSetup); }
  const start = document.getElementById('cs-start-btn');
  if (start && !start._wired) { start._wired = true; start.addEventListener('click', _csStartCombat); }
  const atk = document.getElementById('cs-attack-btn');
  if (atk && !atk._wired) { atk._wired = true; atk.addEventListener('click', () => _csAction('attack')); }
  const mv = document.getElementById('cs-move-btn');
  if (mv && !mv._wired) { mv._wired = true; mv.addEventListener('click', () => _csAction('move')); }
  const enturn = document.getElementById('cs-enemy-turn-btn');
  if (enturn && !enturn._wired) { enturn._wired = true; enturn.addEventListener('click', _csEnemyTurn); }
  const reset = document.getElementById('cs-reset-btn');
  if (reset && !reset._wired) { reset._wired = true; reset.addEventListener('click', _csResetHero); }
  const end = document.getElementById('cs-end-btn');
  if (end && !end._wired) { end._wired = true; end.addEventListener('click', _csEndCombat); }
  const copy = document.getElementById('cs-copy-btn');
  if (copy && !copy._wired) { copy._wired = true; copy.addEventListener('click', _csCopyReport); }
}

async function _csSetup() {
  if (!_csState.selectedHero) { showToast('Wybierz bohatera.', 'error'); return; }
  if (!_csState.selectedEnemies.size) { showToast('Wybierz co najmniej jednego wroga.', 'error'); return; }
  _csLog(`Setup: hero=${_csState.selectedHero.name} enemies=${[..._csState.selectedEnemies].join(',')}`);
  try {
    const heroId = _csState.selectedHero.id ?? _csState.selectedHero.character_id;
    const d = await apiFetch('/api/admin/sandbox/setup', { method:'POST', body: JSON.stringify({ hero_id: heroId })});
    _csState.campaignId = d.campaign_id;
    _csState.characterId = d.character_id;
    _csLog(`✓ Sandbox gotowy. Kamp #${d.campaign_id} · Klon #${d.character_id}`);
    showToast('Sandbox gotowy.', 'success');
    document.getElementById('cs-start-btn').disabled = false;
    await _csRefreshSheet();
  } catch(e) { _csLog('✗ '+e.message); showToast(e.message, 'error'); }
}

async function _csRefreshSheet() {
  if (!_csState.characterId) return;
  try {
    const d = await apiFetch(`/api/admin/sandbox/character/${_csState.characterId}`);
    _csState.characterFull = d;
    const el = document.getElementById('cs-sheet');
    if (!el) return;
    const sh = d;
    const stats = sh.stats || {};
    const hpPct = sh.max_hp ? Math.round((sh.hp/sh.max_hp)*100) : 0;
    const hpCls = hpPct<30?'low':hpPct<60?'mid':'green';
    el.innerHTML = `
      <div style="font-size:0.82rem;font-weight:600;margin-bottom:6px">${_esc(sh.name||'?')}</div>
      <div style="font-size:0.72rem;color:var(--t3);margin-bottom:6px">${_esc(sh.archetype||'')} · Poziom ${sh.level??1}</div>
      <div style="margin-bottom:4px"><div class="hp-bar"><div class="hp-fill ${hpCls}" style="width:${hpPct}%"></div></div><div style="font-size:0.7rem;color:var(--t3);margin-top:2px">HP ${sh.hp??'—'}/${sh.max_hp??'—'}${sh.max_mana?` · Mana ${sh.mana??'—'}/${sh.max_mana}`:''}</div></div>
      <div style="font-size:0.7rem;color:var(--t3);display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center;margin-top:8px">
        ${['STR','DEX','CON','INT','WIS','CHA','LCK'].map(k => `<div><div>${k}</div><div style="color:var(--t1);font-weight:600">${stats[k]??'—'}</div></div>`).join('')}
      </div>`;
  } catch(e) { console.warn('cs-sheet', e.message); }
}

async function _csStartCombat() {
  try {
    const d = await apiFetch('/api/admin/sandbox/start-combat', { method:'POST', body: JSON.stringify({
      campaign_id: _csState.campaignId,
      character_id: _csState.characterId,
      enemy_keys: [..._csState.selectedEnemies],
    })});
    _csState.combatState = d.combat_state || d;
    _csLog(`▶ Walka start. Combat #${_csState.combatState?.combat_id || '?'}`);
    _csRenderCombat();
    document.getElementById('cs-actions').style.display = 'flex';
    document.getElementById('cs-meta-actions').style.display = 'flex';
    document.getElementById('cs-start-btn').disabled = true;
  } catch(e) { _csLog('✗ '+e.message); showToast(e.message, 'error'); }
}

function _csRenderCombat() {
  const el = document.getElementById('cs-combat-state');
  if (!el) return;
  const s = _csState.combatState;
  if (!s) { el.innerHTML = '<div style="color:var(--t3);text-align:center;padding:30px">Brak walki.</div>'; return; }
  const combs = s.combatants || s.combatant_states || [];
  const activeId = s.current_turn || s.active_combatant_id;
  el.innerHTML = `
    <div style="font-size:0.72rem;color:var(--t3);margin-bottom:8px">Runda ${s.round||1} · ${(combs.find(c=>c.id===activeId)?.name)||'?'} w akcji</div>
    <div style="display:flex;flex-direction:column;gap:6px">
      ${combs.map(c => {
        const hp = c.hp_current ?? c.hp ?? 0;
        const maxHp = c.hp_max ?? c.max_hp ?? 1;
        const pct = maxHp ? Math.round((hp/maxHp)*100) : 0;
        const cls = pct<30?'low':pct<60?'mid':'green';
        const active = c.id === activeId;
        const zoneIcon = c.zone === 'ranged' ? '🏹' : '⚔';
        return `<div style="padding:6px;border:1px solid ${active?'var(--blue)':'var(--border)'};border-radius:4px;background:${active?'var(--blue-light)':'transparent'}">
          <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.78rem;margin-bottom:3px">
            <span><strong>${_esc(c.name||c.label||'?')}</strong> ${zoneIcon} <span style="color:var(--t3);font-size:0.7rem">${ZONE_LABEL[c.zone]||c.zone||''} · INI ${c.initiative_roll ?? c.initiative ?? '—'}</span></span>
            <span style="font-size:0.72rem">HP ${hp}/${maxHp}</span>
          </div>
          <div class="hp-bar"><div class="hp-fill ${cls}" style="width:${pct}%"></div></div>
        </div>`;
      }).join('')}
    </div>`;
}

async function _csAction(kind) {
  if (!_csState.combatState) return;
  if (_csState.busy) return;
  _csState.busy = true;
  try {
    const body = { campaign_id: _csState.campaignId, character_id: _csState.characterId, action: kind };
    const d = await apiFetch('/api/admin/sandbox/advance-turn', { method:'POST', body: JSON.stringify(body) });
    _csState.combatState = d.combat_state || d;
    _csLog(`▶ ${kind}: tura ${d.current_turn ?? '?'}`);
    _csRenderCombat();
    await _csRefreshSheet();
  } catch(e) { _csLog('✗ '+e.message); showToast(e.message, 'error'); }
  finally { _csState.busy = false; }
}

async function _csEnemyTurn() {
  if (!_csState.combatState) return;
  try {
    const d = await apiFetch('/api/admin/sandbox/advance-turn', { method:'POST', body: JSON.stringify({ campaign_id: _csState.campaignId }) });
    _csState.combatState = d.combat_state || d;
    _csLog(`▶ Tura wroga: tura ${d.current_turn ?? '?'}`);
    _csRenderCombat();
    await _csRefreshSheet();
  } catch(e) { _csLog('✗ '+e.message); }
}

async function _csResetHero() {
  if (!confirm('Reset HP/Mana klona?')) return;
  try {
    await apiFetch('/api/admin/sandbox/reset-hero', { method:'POST', body: JSON.stringify({ campaign_id: _csState.campaignId, character_id: _csState.characterId }) });
    _csLog('↻ Hero zresetowany');
    await _csRefreshSheet();
  } catch(e) { _csLog('✗ '+e.message); }
}

async function _csEndCombat() {
  if (!confirm('Zakończyć walkę?')) return;
  try {
    await apiFetch('/api/admin/sandbox/end-combat', { method:'POST', body: JSON.stringify({ campaign_id: _csState.campaignId }) });
    _csLog('⏹ Walka zakończona');
    _csState.combatState = null;
    _csRenderCombat();
    document.getElementById('cs-actions').style.display = 'none';
    document.getElementById('cs-meta-actions').style.display = 'none';
    document.getElementById('cs-start-btn').disabled = false;
  } catch(e) { _csLog('✗ '+e.message); }
}

function _csCopyReport() {
  const hero = _csState.characterFull?.name || '?';
  const report = `# Combat Sandbox Report\n\nBohater: ${hero}\nKampania: ${_csState.campaignId}\n\n## Log\n${_csState.log.join('\n')}`;
  navigator.clipboard.writeText(report).then(() => showToast('Skopiowano raport.', 'success'));
}

// ── Image Generator ────────────────────────────────────────────────────────────
function _imgRefShowState() {
  const hasRef = !!(_imgRefB64 || _imgRefFilename);
  const clearBtn = document.getElementById('img-ref-clear');
  const preview  = document.getElementById('img-ref-preview');
  const denoiseRow = document.getElementById('img-ref-denoise-row');
  const genBtn   = document.getElementById('img-gen-btn');
  if (clearBtn)  clearBtn.style.display   = hasRef ? '' : 'none';
  if (preview)   preview.style.display    = hasRef ? '' : 'none';
  if (denoiseRow) denoiseRow.style.display = hasRef ? 'flex' : 'none';
  if (genBtn)    genBtn.innerHTML = hasRef ? '🔄 Refined Generuj' : '🎨 Generuj';
}

function imgRefUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const fullB64 = e.target.result;
    _imgRefB64 = fullB64.split(',')[1];
    _imgRefFilename = '';
    const thumb = document.getElementById('img-ref-thumb');
    const label = document.getElementById('img-ref-label');
    if (thumb) { thumb.src = fullB64; }
    if (label) label.textContent = file.name;
    _imgRefShowState();
  };
  reader.readAsDataURL(file);
  input.value = '';
}

function imgRefFromGallery() {
  _imgGalleryPickMode = true;
  showToast('Kliknij obraz w galerii jako referencję', 'info');
  const grid = document.getElementById('img-gallery-grid');
  if (!grid) return;
  grid.style.outline = '2px dashed var(--blue)';
  grid.style.borderRadius = 'var(--r)';
  _loadImgGallery();
}

function imgRefClear() {
  _imgRefB64 = '';
  _imgRefFilename = '';
  _imgGalleryPickMode = false;
  const thumb = document.getElementById('img-ref-thumb');
  const label = document.getElementById('img-ref-label');
  const upload = document.getElementById('img-ref-upload');
  const grid = document.getElementById('img-gallery-grid');
  if (thumb) thumb.src = '';
  if (label) label.textContent = '—';
  if (upload) upload.value = '';
  if (grid) { grid.style.outline = ''; grid.style.borderRadius = ''; }
  _imgRefShowState();
  _loadImgGallery();
}

function _imgPickAsRef(filename, url) {
  _imgRefFilename = filename;
  _imgRefB64 = '';
  _imgGalleryPickMode = false;
  const thumb = document.getElementById('img-ref-thumb');
  const label = document.getElementById('img-ref-label');
  const grid = document.getElementById('img-gallery-grid');
  if (thumb) { thumb.src = url; }
  if (label) label.textContent = filename;
  if (grid) { grid.style.outline = ''; grid.style.borderRadius = ''; }
  _imgRefShowState();
  _loadImgGallery();
  showToast('Ustawiono referencję: ' + filename, 'success');
}

// ── DB Lint ────────────────────────────────────────────────────────────────────

async function _loadToolsDbLint() {
  const runBtn = document.getElementById('dblint-run');
  if (!runBtn) return;
  runBtn.addEventListener('click', async () => {
    const spinner = document.getElementById('dblint-spinner');
    const output = document.getElementById('dblint-output');
    const statusEl = document.getElementById('dblint-status');
    runBtn.disabled = true;
    if (spinner) spinner.style.display = '';
    if (output) { output.style.display = 'none'; output.textContent = ''; }
    try {
      const result = await apiFetch('/api/admin/db-lint');
      const errors = result.errors || [];
      const warnings = result.warnings || [];
      const exitCode = result.exit_code ?? 0;
      const statusMap = { 0: '✅ CLEAN', 1: '⚠️ WARNINGS', 2: '❌ ERRORS' };
      if (statusEl) statusEl.textContent = statusMap[exitCode] ?? `exit ${exitCode}`;
      const lines = [];
      if (errors.length) { lines.push(`ERRORS (${errors.length}):`); errors.forEach(e => lines.push(`  ${e}`)); }
      if (warnings.length) { lines.push(`WARNINGS (${warnings.length}):`); warnings.forEach(w => lines.push(`  ${w}`)); }
      if (!errors.length && !warnings.length) lines.push('  ✅ Baza wygląda zdrowo — brak problemów.');
      if (output) { output.textContent = lines.join('\n'); output.style.display = ''; }
    } catch (e) {
      if (statusEl) statusEl.textContent = '⚠️ Błąd';
      if (output) { output.textContent = `Błąd: ${e.message}`; output.style.display = ''; }
    } finally {
      runBtn.disabled = false;
      if (spinner) spinner.style.display = 'none';
    }
  });
}

async function _loadImgGallery() {
  const grid = document.getElementById('img-gallery-grid');
  const count = document.getElementById('img-gallery-count');
  if (!grid) return;
  grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--t3)"><div class="img-spinner"></div>Ładowanie…</div>';
  try {
    const data = await apiFetch('/api/admin/images/list');
    const imgs = data.images || [];
    if (count) count.textContent = imgs.length;
    if (!imgs.length) {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px 20px;color:var(--t3)"><div style="font-size:32px;margin-bottom:8px;opacity:0.25">🖼</div><div style="font-size:0.8rem">Brak wygenerowanych obrazów</div></div>';
      return;
    }
    const pickMode = _imgGalleryPickMode;
    grid.innerHTML = imgs.map(img => `
      <div class="img-thumb-card" onclick="${pickMode
        ? `_imgPickAsRef('${img.filename}','${img.url}')`
        : `imgOpenLightbox('${img.url}','${img.filename}')`
      }">
        <img src="${img.url}" alt="${img.filename}" loading="lazy">
        <div class="img-thumb-overlay">
          <span class="img-thumb-filename">${img.filename}</span>
          ${pickMode
            ? `<button class="img-thumb-del" style="background:var(--blue)" onclick="event.stopPropagation();_imgPickAsRef('${img.filename}','${img.url}')">📌 Ref</button>`
            : `<button class="img-thumb-del" onclick="event.stopPropagation();imgDelete('${img.filename}')">🗑</button>`
          }
        </div>
      </div>
    `).join('');
  } catch(e) {
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:20px;color:var(--red);font-size:0.8rem">Błąd: ${e.message}</div>`;
  }
}

async function imgGenerate() {
  const prompt = document.getElementById('img-prompt').value.trim();
  if (!prompt) { showToast('Wpisz opis obrazu.', 'warn'); return; }

  const sizeVal = document.getElementById('img-size').value;
  const [w, h] = sizeVal.split('x').map(Number);
  const steps = parseInt(document.getElementById('img-steps').value);
  const denoiseEl = document.getElementById('img-ref-denoise');
  const denoise = denoiseEl ? parseInt(denoiseEl.value) / 100 : 0.6;
  const hasRef = !!(_imgRefB64 || _imgRefFilename);

  const btn = document.getElementById('img-gen-btn');
  const status = document.getElementById('img-gen-status');
  const previewArea = document.getElementById('img-preview-area');
  const promptEl = document.getElementById('img-prompt');
  const copyBtn = document.getElementById('img-copy-url-btn');
  const refineBtn = document.getElementById('img-refine-btn');

  btn.disabled = true;
  btn.innerHTML = '⏳ Generowanie…';
  promptEl.classList.add('generating');
  if (status) status.textContent = '0s…';
  if (copyBtn) copyBtn.style.display = 'none';
  if (refineBtn) refineBtn.style.display = 'none';

  const start = Date.now();
  const timer = setInterval(() => {
    if (status) status.textContent = `${Math.round((Date.now()-start)/1000)}s…`;
  }, 1000);

  previewArea.innerHTML = '<div style="text-align:center;padding:20px;color:var(--t3)"><div class="img-spinner"></div><div style="font-size:0.78rem">' + (hasRef ? 'Refinowanie obrazu…' : 'Generowanie obrazu…') + '</div></div>';

  try {
    let data;
    if (_imgRefFilename) {
      data = await apiFetch('/api/admin/images/refine', {
        method: 'POST',
        body: JSON.stringify({ source_filename: _imgRefFilename, prompt, denoise, steps })
      });
    } else if (_imgRefB64) {
      data = await apiFetch('/api/admin/images/refine-upload', {
        method: 'POST',
        body: JSON.stringify({ upload_b64: _imgRefB64, prompt, denoise, steps })
      });
    } else {
      data = await apiFetch('/api/admin/images/generate', {
        method: 'POST',
        body: JSON.stringify({ prompt, width: w, height: h, steps })
      });
    }

    _imgLastUrl = data.url;
    _imgLastFilename = data.filename;

    previewArea.innerHTML = `
      <img src="${data.url}" alt="Generated"
        style="max-width:100%;max-height:320px;border-radius:var(--r);display:block;margin:0 auto;box-shadow:var(--shadow-md);cursor:pointer"
        onclick="imgOpenLightbox('${data.url}','${data.filename}')">
    `;
    if (copyBtn) copyBtn.style.display = '';
    if (refineBtn) refineBtn.style.display = '';
    if (status) status.textContent = `${Math.round((Date.now()-start)/1000)}s`;
    showToast(hasRef ? 'Obraz zrefinowany!' : 'Obraz wygenerowany!', 'success');
    _loadImgGallery();
  } catch(e) {
    previewArea.innerHTML = `<div style="color:var(--red);font-size:0.8rem;text-align:center;padding:20px">Błąd: ${e.message}</div>`;
    if (status) status.textContent = 'błąd';
    showToast('Błąd: ' + e.message, 'error');
  } finally {
    clearInterval(timer);
    btn.disabled = false;
    btn.innerHTML = (_imgRefB64 || _imgRefFilename) ? '🔄 Refined Generuj' : '🎨 Generuj';
    promptEl.classList.remove('generating');
  }
}

function imgUseLastAsRef() {
  if (!_imgLastFilename) return;
  _imgRefFilename = _imgLastFilename;
  _imgRefB64 = '';
  const thumb = document.getElementById('img-ref-thumb');
  const label = document.getElementById('img-ref-label');
  if (thumb) thumb.src = _imgLastUrl;
  if (label) label.textContent = _imgLastFilename;
  _imgRefShowState();
  showToast('Ostatni obraz ustawiony jako referencja', 'success');
}

function imgCopyPreviewUrl() {
  const origin = window.location.origin;
  const url = _imgLastUrl.startsWith('http') ? _imgLastUrl : origin + '/' + _imgLastUrl.replace(/^\//, '');
  navigator.clipboard.writeText(url).then(() => {
    const btn = document.getElementById('img-copy-url-btn');
    const orig = btn.innerHTML;
    btn.innerHTML = '✓ Skopiowano';
    setTimeout(() => btn.innerHTML = orig, 2000);
  });
}

async function imgDelete(filename) {
  if (!confirm(`Usunąć ${filename}?`)) return;
  try {
    await apiFetch(`/api/admin/images/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    showToast('Obraz usunięty.', 'info');
    _loadImgGallery();
  } catch(e) {
    showToast('Błąd usuwania: ' + e.message, 'error');
  }
}

function imgOpenLightbox(url, filename) {
  const img = document.getElementById('img-lightbox-img');
  const fn = document.getElementById('img-lightbox-filename');
  if (img) img.src = url;
  if (fn) fn.textContent = filename;
  document.getElementById('img-lightbox').classList.add('open');
}

function imgCloseLightbox() {
  document.getElementById('img-lightbox').classList.remove('open');
}

function imgLightboxCopy() {
  const url = document.getElementById('img-lightbox-img').src;
  navigator.clipboard.writeText(url).then(() => {
    const btn = document.getElementById('img-lb-copy-btn');
    const orig = btn.innerHTML;
    btn.innerHTML = '✓ Skopiowano';
    setTimeout(() => btn.innerHTML = orig, 2000);
  });
}

function imgLightboxUseAsRef() {
  const filename = document.getElementById('img-lightbox-filename').textContent;
  const url = document.getElementById('img-lightbox-img').src;
  if (!filename || filename === '—') return;
  _imgRefFilename = filename;
  _imgRefB64 = '';
  const thumb = document.getElementById('img-ref-thumb');
  const label = document.getElementById('img-ref-label');
  if (thumb) thumb.src = url;
  if (label) label.textContent = filename;
  _imgRefShowState();
  imgCloseLightbox();
  showToast('Ustawiono referencję: ' + filename, 'success');
}

// ── Module entry point ─────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = `<div id="section-tools">
    <div class="section-header">
      <div>
        <div class="section-heading">Narzędzia</div>
        <div class="section-sub">Diagnostyka, testy i zasoby wiedzy</div>
      </div>
    </div>

    <div class="stab-bar" id="tools-stab-bar">
      <button class="stab active" data-toolstab="runner">▶ Test Runner</button>
      <button class="stab" data-toolstab="combat">⚔ Combat Sandbox</button>
      <button class="stab" data-toolstab="rest">⛺ Rest Sandbox</button>
      <button class="stab" data-toolstab="knowledge">📖 Wiedza</button>
      <button class="stab" data-toolstab="mcp">⬡ MCP</button>
      <button class="stab" data-toolstab="images">🖼 Obrazy</button>
      <button class="stab" data-toolstab="playwright">🎭 Playwright</button>
      <button class="stab" data-toolstab="dblint">🔍 DB Lint</button>
    </div>

    <!-- Test Runner panel -->
    <div class="stab-panel active" id="toolstab-runner">
      <div class="two-col" style="margin-top:12px">
        <div class="action-group" style="padding:0;display:grid;grid-template-columns:1fr;gap:12px">
          <div class="card" style="overflow:hidden">
            <div style="padding:20px;display:flex;align-items:flex-start;gap:14px">
              <div style="font-size:28px;line-height:1">▶</div>
              <div style="flex:1">
                <div style="font-weight:700;font-size:0.9rem;color:var(--t1);margin-bottom:4px">Test Runner</div>
                <div style="font-size:0.78rem;color:var(--t2);margin-bottom:14px;line-height:1.5">Uruchom zestaw testów Playwright na stacku DEV.</div>
                <div style="display:flex;gap:6px;flex-wrap:wrap">
                  <select class="form-input" id="tools-scenario" style="max-width:200px;font-size:0.78rem"><option value="">— Załaduj scenariusze —</option></select>
                  <button class="btn btn-secondary btn-sm" id="tools-run-tests">▶ Uruchom</button>
                </div>
                <div id="tools-run-out" style="margin-top:8px;font-size:0.75rem;color:var(--t3)"></div>
              </div>
            </div>
          </div>
          <div class="card" style="overflow:hidden">
            <div style="padding:20px;display:flex;align-items:flex-start;gap:14px">
              <div style="font-size:28px;line-height:1">≡</div>
              <div style="flex:1">
                <div style="font-weight:700;font-size:0.9rem;color:var(--t1);margin-bottom:4px">Status testów</div>
                <div style="font-size:0.78rem;color:var(--t2);margin-bottom:14px;line-height:1.5">Sprawdź stan ostatniego uruchomienia.</div>
                <button class="btn btn-secondary btn-sm" id="tools-refresh-runs">⟳ Odśwież listę</button>
              </div>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Ostatnie testy / scenariusze</span>
            <span class="card-count" id="tools-runs-count">—</span>
          </div>
          <div class="table-wrap">
            <table class="data-table" style="min-width:320px" id="tools-runs-table">
              <thead>
                <tr>
                  <th><div class="th-inner">Scenariusz</div></th>
                  <th><div class="th-inner">Plik</div></th>
                  <th><div class="th-inner">Akcje</div></th>
                </tr>
              </thead>
              <tbody><tr><td colspan="3" style="text-align:center;padding:18px;color:var(--t3)">Kliknij ⟳ aby odświeżyć listę.</td></tr></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Playwright Regression panel -->
    <div class="stab-panel" id="toolstab-playwright" style="display:none">
      <div style="margin-top:12px;display:grid;grid-template-columns:320px 1fr;gap:16px;align-items:start">
        <!-- Left: spec list -->
        <div style="display:flex;flex-direction:column;gap:10px">
          <div class="card">
            <div class="card-header">
              <span class="card-title">Testy Playwright</span>
              <button class="btn btn-sm btn-primary" id="pw-run-all">▶ Uruchom wszystkie</button>
            </div>
            <div style="padding:12px;display:flex;flex-direction:column;gap:8px;max-height:500px;overflow-y:auto" id="pw-spec-list">
              <div style="color:var(--t3);font-size:0.78rem">Kliknij zakładkę aby załadować…</div>
            </div>
          </div>
          <div class="card" style="padding:14px">
            <div style="font-size:0.75rem;color:var(--t2);line-height:1.6">
              <strong>Jak działa:</strong><br>
              Playwright odpala spec files z <code>playwright/ux/</code> (regression, acceptance, admin3) wewnątrz kontenera test-agent.<br><br>
              <strong>▶ grupa</strong> uruchamia całą suitę, <strong>▶</strong> pojedynczy plik.<br>
              <strong>Uwaga:</strong> Acceptance (C1–C19) rozgrywa tury z prawdziwym LLM — trwa kilka–kilkanaście minut.
            </div>
          </div>
        </div>
        <!-- Right: live output -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">Wyniki / log</span>
            <span id="pw-status" style="font-size:0.78rem;font-weight:600"></span>
          </div>
          <div id="pw-log" style="padding:12px;min-height:200px;max-height:500px;overflow-y:auto;font-family:monospace;font-size:0.72rem;color:var(--t2);background:var(--bg2,#111);border-radius:4px;line-height:1.5">
            <span style="color:var(--t3)">Tu pojawi się output testów…</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Combat Sandbox panel -->
    <div class="stab-panel" id="toolstab-combat" style="display:none">
      <div style="display:grid;grid-template-columns:300px 1fr 300px;gap:16px;margin-top:12px">
        <!-- Left: Setup -->
        <div style="display:flex;flex-direction:column;gap:12px">
          <div class="card">
            <div class="card-header"><span class="card-title">Bohater</span></div>
            <div style="padding:12px;display:flex;flex-direction:column;gap:6px" id="cs-hero-picker"><div style="color:var(--t3);font-size:0.78rem">Ładowanie…</div></div>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Wrogowie</span></div>
            <div style="padding:12px">
              <input class="form-input" id="cs-enemy-search" placeholder="Szukaj…" style="font-size:0.78rem;margin-bottom:8px">
              <div style="max-height:200px;overflow-y:auto;display:flex;flex-direction:column;gap:2px" id="cs-enemy-picker"></div>
              <div style="font-size:0.72rem;color:var(--accent);margin-top:6px" id="cs-enemy-summary"></div>
            </div>
            <div style="padding:0 12px 12px;display:flex;gap:8px">
              <button class="btn btn-secondary btn-sm" id="cs-setup-btn">Przygotuj sandbox</button>
              <button class="btn btn-primary btn-sm" id="cs-start-btn" disabled>▶ Start walki</button>
            </div>
          </div>
          <div class="card" id="cs-sheet" style="padding:12px;font-size:0.8rem"></div>
        </div>
        <!-- Center: Combat state -->
        <div style="display:flex;flex-direction:column;gap:12px">
          <div class="card" style="flex:1">
            <div class="card-header"><span class="card-title">Stan walki</span></div>
            <div style="padding:12px" id="cs-combat-state"><div style="color:var(--t3);text-align:center;padding:30px">Brak walki.</div></div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap" id="cs-actions" style="display:none">
            <button class="btn btn-primary btn-sm" id="cs-attack-btn">⚔ Atak</button>
            <button class="btn btn-secondary btn-sm" id="cs-move-btn">👣 Ruch</button>
            <button class="btn btn-secondary btn-sm" id="cs-spell-btn" disabled>✨ Czar</button>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap" id="cs-meta-actions" style="display:none">
            <button class="btn btn-sm btn-secondary" id="cs-enemy-turn-btn">➤ Tura wroga</button>
            <button class="btn btn-sm btn-secondary" id="cs-reset-btn">↻ Reset HP</button>
            <button class="btn btn-sm btn-danger" id="cs-end-btn">⏹ Koniec walki</button>
          </div>
        </div>
        <!-- Right: Log -->
        <div style="display:flex;flex-direction:column;gap:12px">
          <div class="card" style="flex:1">
            <div class="card-header">
              <span class="card-title">Log</span>
              <button class="btn btn-sm btn-secondary" id="cs-copy-btn">📋 Kopiuj raport</button>
            </div>
            <pre id="cs-log" style="padding:12px;font-size:0.72rem;color:var(--t2);white-space:pre-wrap;word-break:break-word;max-height:500px;overflow-y:auto;margin:0"></pre>
          </div>
        </div>
      </div>
    </div>

    <!-- Rest Sandbox panel -->
    <div class="stab-panel" id="toolstab-rest" style="display:none">
      <div style="display:grid;grid-template-columns:260px 1fr;gap:16px;margin-top:12px">
        <div class="card">
          <div class="card-header"><span class="card-title">Bohater</span></div>
          <div style="padding:12px;display:flex;flex-direction:column;gap:6px" id="rst-heroes"><div style="color:var(--t3);font-size:0.78rem">Ładowanie…</div></div>
          <div style="padding:0 12px 12px;display:flex;gap:8px">
            <button class="btn btn-secondary btn-sm" id="rst-setup-btn" disabled onclick="rstSetup(this)">Przygotuj sandbox</button>
            <button class="btn btn-danger btn-sm" id="rst-end-btn" style="display:none" onclick="rstEnd(this)">⏹ Zakończ</button>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:12px">
          <div class="card" id="rst-sheet" style="display:none">
            <div class="card-header"><span class="card-title" id="rst-name">—</span></div>
            <div style="padding:12px">
              <div style="font-size:0.78rem;margin-bottom:6px">HP: <strong id="rst-hp-txt">—</strong></div>
              <div class="hp-bar"><div class="hp-fill green" id="rst-hp-bar" style="width:100%"></div></div>
              <div style="font-size:0.72rem;color:var(--t3);margin-top:4px">Krótkie odp. pozostały: <strong id="rst-short-rest-remaining">—</strong>/2</div>
            </div>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Akcje</span></div>
            <div style="padding:12px;display:flex;flex-direction:column;gap:8px" id="rst-controls"><div style="color:var(--t3);font-size:0.8rem">Najpierw przygotuj sandbox.</div></div>
          </div>
          <div class="card">
            <div class="card-header">
              <span class="card-title">Log</span>
              <button class="btn btn-sm btn-secondary" onclick="rstCopyReport()">📋 Kopiuj</button>
            </div>
            <div id="rst-log" style="padding:12px;font-size:0.72rem;color:var(--t2);max-height:300px;overflow-y:auto;display:flex;flex-direction:column;gap:2px"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- DB Lint panel -->
    <div class="stab-panel" id="toolstab-dblint" style="display:none">
      <div style="margin-top:12px;max-width:760px">
        <div class="card">
          <div class="card-header">
            <span class="card-title">🔍 DB Lint — Audyt integralności bazy</span>
            <span class="card-count" id="dblint-status">—</span>
          </div>
          <div style="padding:16px;display:flex;flex-direction:column;gap:12px">
            <div style="font-size:0.8rem;color:var(--t2);line-height:1.5">
              Sprawdza wiszące FK, brakujące pola, wartości poza zakresem, enum violations i effect_json.
              Exit code: <code>0</code>=czysto, <code>1</code>=warnings, <code>2</code>=errors.
            </div>
            <div style="display:flex;gap:8px;align-items:center">
              <button class="btn btn-secondary btn-sm" id="dblint-run">▶ Uruchom audyt</button>
              <span id="dblint-spinner" style="display:none;color:var(--t3);font-size:0.8rem">Ładowanie…</span>
            </div>
            <pre id="dblint-output" style="background:var(--bg2);padding:14px;border-radius:6px;font-size:0.75rem;color:var(--t2);white-space:pre-wrap;word-break:break-word;min-height:60px;display:none"></pre>
          </div>
        </div>
      </div>
    </div>

    <!-- Wiedza panel -->
    <div class="stab-panel" id="toolstab-knowledge" style="display:none">
      <div style="margin-top:12px" id="toolstab-knowledge-content">
        <div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>
      </div>
    </div>

    <!-- MCP panel -->
    <div class="stab-panel" id="toolstab-mcp" style="display:none">
      <div style="padding:24px;text-align:center;color:var(--t3);font-size:0.85rem">Ładowanie MCP…</div>
    </div>

    <!-- Images tab -->
    <div class="stab-panel" id="toolstab-images" style="display:none">
      <div style="display:grid;grid-template-columns:380px 1fr;gap:14px;margin-top:14px">

        <!-- LEFT: Generator + Preview -->
        <div style="display:flex;flex-direction:column;gap:12px">

          <div class="card">
            <div class="card-header">
              <span class="card-title">🎨 Generator</span>
              <span class="card-count" id="img-gen-status">gotowy</span>
            </div>

            <!-- Preset chips -->
            <div style="padding:12px 14px 0;display:flex;gap:6px;flex-wrap:wrap">
              <button class="img-preset" data-preset="tile" data-prefix="top-down dungeon room tile, dark stone walls, torch lighting, fantasy RPG board game art, illustrated drawing style, Betrayal at House on the Hill aesthetic, square format, no text, no letters,">🏰 Dungeon Tile</button>
              <button class="img-preset" data-preset="enemy" data-prefix="fantasy RPG enemy portrait, dark fantasy illustrated style, game card art, black background, detailed drawing, no text, no letters,">👹 Enemy Portrait</button>
              <button class="img-preset" data-preset="item" data-prefix="fantasy RPG item artwork, isolated on black background, magical glow, detailed illustration, game icon style, no text, no letters,">⚔ Item Art</button>
              <button class="img-preset" data-preset="map" data-prefix="fantasy map icon, top-down view, small tile symbol, RPG cartography style, parchment aesthetic, no text,">🗺 Map Icon</button>
            </div>

            <!-- Reference image section -->
            <div id="img-ref-section" style="padding:8px 14px 0;border-top:1px solid var(--border);margin-top:6px">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                <span style="font-size:0.68rem;font-weight:600;color:var(--t3);text-transform:uppercase;letter-spacing:0.05em">Referencja</span>
                <label class="btn btn-sm btn-secondary" style="cursor:pointer;padding:3px 8px;font-size:0.72rem">
                  📎 Upload
                  <input type="file" id="img-ref-upload" accept="image/*" style="display:none" onchange="imgRefUpload(this)">
                </label>
                <button class="btn btn-sm btn-secondary" style="font-size:0.72rem;padding:3px 8px" onclick="imgRefFromGallery()">🖼 Z galerii</button>
                <button id="img-ref-clear" class="btn btn-sm btn-danger" style="font-size:0.72rem;padding:3px 8px;display:none" onclick="imgRefClear()">✕ Usuń</button>
              </div>
              <div id="img-ref-preview" style="display:none;margin-bottom:6px">
                <img id="img-ref-thumb" src="" alt="ref" style="height:60px;border-radius:var(--r-sm);border:1px solid var(--border-strong);object-fit:cover">
                <span style="font-size:0.7rem;color:var(--t3);margin-left:8px" id="img-ref-label">—</span>
              </div>
              <div id="img-ref-denoise-row" style="display:none;align-items:center;gap:8px">
                <label style="font-size:0.68rem;color:var(--t3);white-space:nowrap">Wpływ: <span id="img-ref-denoise-val">60%</span></label>
                <input type="range" id="img-ref-denoise" min="10" max="95" value="60" style="flex:1;accent-color:var(--blue);margin:0">
              </div>
            </div>

            <!-- Prompt -->
            <div style="padding:10px 14px;display:flex;flex-direction:column;gap:10px">
              <textarea id="img-prompt" class="form-input" rows="5"
                placeholder="Opisz scenę, pokój, postać lub przedmiot…"
                style="resize:none;font-size:0.82rem;line-height:1.55;transition:border-color 0.2s,box-shadow 0.2s"></textarea>

              <!-- Settings -->
              <div style="display:flex;gap:10px;align-items:flex-end">
                <div style="display:flex;flex-direction:column;gap:3px">
                  <label style="font-size:0.68rem;font-weight:600;color:var(--t3);text-transform:uppercase;letter-spacing:0.05em">Rozmiar</label>
                  <select id="img-size" class="form-input" style="font-size:0.78rem;padding:5px 8px;width:auto">
                    <option value="512x512">512 × 512</option>
                    <option value="768x768">768 × 768</option>
                    <option value="1024x1024">1024 × 1024</option>
                    <option value="1280x1280">1280 × 1280</option>
                    <option value="512x768">512 × 768 (portret)</option>
                    <option value="768x1024">768 × 1024 (portret)</option>
                    <option value="1024x576">1024 × 576 (pejzaż)</option>
                  </select>
                </div>
                <div style="display:flex;flex-direction:column;gap:3px;flex:1">
                  <label style="font-size:0.68rem;font-weight:600;color:var(--t3);text-transform:uppercase;letter-spacing:0.05em">Kroki: <span id="img-steps-val">4</span></label>
                  <input type="range" id="img-steps" min="4" max="20" value="4" style="width:100%;accent-color:var(--blue);margin:0">
                </div>
              </div>

              <button class="btn btn-primary" id="img-gen-btn" onclick="imgGenerate()"
                style="width:100%;padding:9px 14px;font-size:0.85rem;justify-content:center">
                🎨 Generuj
              </button>
            </div>
          </div>

          <!-- Preview -->
          <div class="card">
            <div class="card-header">
              <span class="card-title">Podgląd</span>
              <div style="display:flex;gap:6px">
                <button class="btn btn-sm btn-secondary" id="img-refine-btn" style="display:none" onclick="imgUseLastAsRef()">🔄 Użyj jako ref</button>
                <button class="btn btn-sm btn-secondary" id="img-copy-url-btn" style="display:none" onclick="imgCopyPreviewUrl()">📋 Kopiuj URL</button>
              </div>
            </div>
            <div id="img-preview-area" style="padding:14px;min-height:160px;display:flex;align-items:center;justify-content:center">
              <div style="text-align:center;color:var(--t3)">
                <div style="font-size:36px;margin-bottom:8px;opacity:0.25">🖼</div>
                <div style="font-size:0.78rem">Wygenerowany obraz pojawi się tutaj</div>
              </div>
            </div>
          </div>
        </div>

        <!-- RIGHT: Gallery -->
        <div class="card" style="display:flex;flex-direction:column;min-height:500px">
          <div class="card-header">
            <span class="card-title">Galeria</span>
            <div style="display:flex;align-items:center;gap:8px">
              <span class="card-count" id="img-gallery-count">—</span>
              <button class="btn btn-sm btn-secondary" onclick="_loadImgGallery()">⟳ Odśwież</button>
            </div>
          </div>
          <div style="flex:1;overflow-y:auto;padding:14px">
            <div id="img-gallery-grid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
              <div style="grid-column:1/-1;text-align:center;padding:40px 20px;color:var(--t3)">
                <div style="font-size:32px;margin-bottom:8px;opacity:0.25">🖼</div>
                <div style="font-size:0.8rem">Brak wygenerowanych obrazów</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>`;

  _wireStabBar();
  _wireImgPresets();
  await _loadTools();
}

// ── Expose onclick-referenced functions to window ──────────────────────────────
Object.assign(window, {
  // Test Runner
  _runScenarioFromList,
  _pollTestStatus,
  // Playwright
  _runPlaywrightSpec,
  // Knowledge
  openKnowledgeModal,
  saveKnowledge,
  deleteKnowledge,
  _deleteKnowledgeTip,
  _loadToolsKnowledge,
  // MCP
  _mcpLoadSelectedCampaign,
  _loadImgGallery,
  // Rest Sandbox
  rstSelectHero,
  rstSetup,
  rstEnd,
  rstBuildCamp,
  rstSetSafe,
  rstShortRest,
  rstLongRest,
  rstRollEncounter,
  rstResetHero,
  rstCopyReport,
  // Image Generator
  imgRefUpload,
  imgRefFromGallery,
  imgRefClear,
  imgGenerate,
  imgUseLastAsRef,
  imgCopyPreviewUrl,
  imgDelete,
  imgOpenLightbox,
  imgCloseLightbox,
  imgLightboxCopy,
  imgLightboxUseAsRef,
  _imgPickAsRef,
});
