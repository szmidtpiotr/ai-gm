/**
 * FADM-P12 (#414) — sekcja Zaproszenia: kody invite.
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

// ── Helpers ────────────────────────────────────────────────────────────────────
function _esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── State ─────────────────────────────────────────────────────────────────────
const _INV_BASE_URL = 'https://aigm-dev.studio-colorbox.com';

const _INV_TEMPLATES = [
  `Witaj, Wędrowcze!

Otwieram przed Tobą bramy mrocznego świata AI-GM — gry fabularnej, gdzie sztuczna inteligencja wciela się w rolę Mistrza Gry.

Czeka na Ciebie:
⚔ Epickie kampanie w klimacie dark fantasy
🔮 Tajemnicze lochy i potwory do pokonania
📖 Historia, którą sam piszesz każdym rzutem kości

Dołącz do drużyny tutaj:
[LINK]

Do zobaczenia przy stole!`,

  `Hej!

Odkryłem coś wyjątkowego — AI-GM, gra RPG prowadzona przez sztuczną inteligencję. Mistrz Gry nigdy nie śpi, nie zapomina i zawsze ma dla Ciebie misję.

Zarejestruj się moim linkiem i zacznij przygodę:
[LINK]

Twój bohater czeka. Nie każ mu czekać zbyt długo. ⚔`,

  `Zaproszenie do gry: AI-GM

Wyobraź sobie grę RPG, gdzie nie musisz czekać na Mistrza Gry — AI prowadzi sesję 24/7, pamięta każdą Twoją decyzję i adaptuje świat do Twoich wyborów.

Wojownik, Uczony czy Łowca — kim zostaniesz?

Zarejestruj się tutaj:
[LINK]

Link ważny przez 72 godziny.`,

  `Czeka na Ciebie wezwanie!

Świat AI-GM potrzebuje nowych bohaterów. Mroczne krainy, starożytne zagadki, wrogowie czyhający w każdym zaułku — i sztuczna inteligencja jako Twój osobisty Mistrz Gry.

Odpowiedz na wezwanie:
[LINK]

Niech kości się toczą! 🎲`,
];

let _invCurrentLink = '';
let _invLastCode = '';
let _invLastEmail = '';

// ── Functions ─────────────────────────────────────────────────────────────────

async function _loadInvites() {
  _invRollMessage(); // auto-populate template on first load
  await Promise.all([_refreshInviteTree(), _refreshInviteList()]);
}

async function _refreshInviteTree() {
  // Load D3 dynamically once
  if (!window.d3) {
    await new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js';
      s.onload = resolve; s.onerror = reject;
      document.head.appendChild(s);
    });
  }
  let treeData;
  try {
    const resp = await apiFetch('/api/admin/invite-tree');
    treeData = resp.tree;
  } catch(e) {
    const loadEl = document.getElementById('inv-tree-loading');
    if (loadEl) loadEl.textContent = 'Błąd: ' + (e.message || 'nieznany');
    return;
  }
  const loadEl = document.getElementById('inv-tree-loading');
  if (loadEl) loadEl.style.display = 'none';
  if (!treeData || (Array.isArray(treeData) && !treeData.length)) {
    const wrap = document.getElementById('invite-tree-svg-wrap');
    if (wrap) wrap.innerHTML = '<div style="text-align:center;padding:60px;color:var(--t3)">Brak danych drzewa zaproszeń.</div>';
    return;
  }
  const rootData = Array.isArray(treeData)
    ? { id:0, name:'AI-GM', username:'root', status:'active', turns:0, children:treeData }
    : treeData;
  _drawInviteTree(rootData);
}

function _drawInviteTree(rootData) {
  const d3 = window.d3;
  const wrap = document.getElementById('invite-tree-svg-wrap');
  if (!wrap) return;
  const svgEl = document.getElementById('invite-tree-svg');
  if (svgEl) svgEl.innerHTML = '';
  const activityColor = { active:'#4caf78', low:'#c9944a', cold:'#6b665e' };
  const margin = { top:24, right:140, bottom:24, left:100 };
  const dx = 44, dy = 180;
  const root = d3.hierarchy(rootData);
  root.descendants().forEach(d => { if (d.depth > 1) { d._children = d.children; d.children = null; } });
  const tree = d3.tree().nodeSize([dx, dy]);
  const svg = d3.select('#invite-tree-svg');
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);
  const linkGen = d3.linkHorizontal().x(d => d.y).y(d => d.x);
  const gLinks = g.append('g').attr('fill','none').attr('stroke','#3a3d50').attr('stroke-width',1.5);
  const gNodes = g.append('g').attr('cursor','pointer');
  function update(source) {
    tree(root);
    let x0 = Infinity, x1 = -Infinity;
    root.each(d => { if (d.x > x1) x1 = d.x; if (d.x < x0) x0 = d.x; });
    const height = x1 - x0 + margin.top + margin.bottom + dx*2;
    const width  = root.height * dy + margin.left + margin.right + 60;
    svg.attr('width', Math.max(width,400)).attr('height', Math.max(height,200));
    g.attr('transform', `translate(${margin.left},${margin.top + (-x0 + dx)})`);
    const links = gLinks.selectAll('path').data(root.links(), d => d.target.data.id);
    links.enter().append('path').attr('opacity',0)
      .attr('d', () => { const o={x:source.x0??source.x,y:source.y0??source.y}; return linkGen({source:o,target:o}); })
      .merge(links).transition().duration(250).attr('opacity',1).attr('d',linkGen);
    links.exit().transition().duration(250).attr('opacity',0)
      .attr('d', () => { const o={x:source.x,y:source.y}; return linkGen({source:o,target:o}); }).remove();
    const nodes = gNodes.selectAll('g.inv-node').data(root.descendants(), d => d.data.id);
    const nodeEnter = nodes.enter().append('g').attr('class','inv-node')
      .attr('transform', () => `translate(${source.y0??source.y},${source.x0??source.x})`).attr('opacity',0)
      .on('click', (event, d) => {
        if (d._children || d.children) {
          if (d.children) { d._children = d.children; d.children = null; } else { d.children = d._children; d._children = null; }
          update(d);
        }
      });
    nodeEnter.append('circle').attr('r',10).attr('fill','transparent')
      .attr('stroke', d => activityColor[d.data.status]||'#6b665e')
      .attr('stroke-width', d => d._children ? 2 : 0).attr('stroke-dasharray','3,2');
    nodeEnter.append('circle').attr('class','inv-node-circle').attr('r',6)
      .attr('fill', d => activityColor[d.data.status]||'#6b665e').attr('stroke','#0f1117').attr('stroke-width',1.5);
    nodeEnter.append('text').attr('class','inv-node-label').attr('dy','0.32em')
      .attr('x', d => (d.children||d._children) ? -14 : 14)
      .attr('text-anchor', d => (d.children||d._children) ? 'end' : 'start')
      .attr('fill','#c9a54a').attr('font-size','12px').text(d => d.data.name||d.data.username);
    nodeEnter.append('text').attr('class','inv-node-turns').attr('dy','0.32em').attr('y',-13)
      .attr('text-anchor','middle').attr('fill', d => activityColor[d.data.status]||'#6b665e')
      .attr('font-size','10px').text(d => d.data.turns > 0 ? `${d.data.turns}t` : '');
    const nodeMerge = nodeEnter.merge(nodes);
    nodeMerge.transition().duration(250).attr('transform', d => `translate(${d.y},${d.x})`).attr('opacity',1);
    nodeMerge.select('circle.inv-node-circle').attr('fill', d => activityColor[d.data.status]||'#6b665e');
    nodeMerge.select('circle:first-child').attr('stroke-width', d => d._children ? 2 : 0);
    nodeMerge.select('text.inv-node-label')
      .attr('x', d => (d.children||d._children) ? -14 : 14)
      .attr('text-anchor', d => (d.children||d._children) ? 'end' : 'start');
    nodes.exit().transition().duration(250).attr('transform', () => `translate(${source.y},${source.x})`).attr('opacity',0).remove();
    root.each(d => { d.x0 = d.x; d.y0 = d.y; });
  }
  root.x0 = 0; root.y0 = 0; update(root);
}

async function _refreshInviteList() {
  const listEl = document.getElementById('invites-list');
  if (!listEl) return;
  try {
    const d = await apiFetch('/api/admin/invites');
    const invites = d.invites || [];
    if (!invites.length) { listEl.innerHTML = '<div style="color:var(--t3)">Brak aktywnych zaproszeń.</div>'; return; }
    listEl.innerHTML = invites.map(inv => {
      const maxU = inv.max_uses ?? 1;
      const usedC = inv.uses_count ?? 0;
      const exhausted = maxU > 0 && usedC >= maxU;
      let badge;
      if (maxU === 1) {
        badge = inv.used_at ? '<span class="badge badge-green">Użyte</span>' : '';
      } else {
        const limitLabel = maxU === 0 ? '∞' : String(maxU);
        const color = exhausted ? '#4caf78' : '#a090e0';
        badge = `<span style="font-size:0.7rem;background:rgba(160,144,224,0.15);color:${color};border:1px solid ${color}44;border-radius:4px;padding:1px 7px">${usedC}/${limitLabel}</span>`;
      }
      const canRevoke = !inv.used_at && !exhausted;
      const revokeBtn = canRevoke ? `<button class="btn btn-sm btn-danger" style="padding:2px 8px;font-size:0.72rem" onclick="revokeInvite(${inv.id},this)">Odwołaj</button>` : '';
      return `<div style="padding:6px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;gap:8px">
        <div style="min-width:0;flex:1">
          <div class="td-mono" style="font-size:0.75rem">${_esc(inv.email||'(otwarte)')}</div>
          <div style="color:var(--t3);font-size:0.72rem">Od: ${_esc(inv.creator_name||'—')} · wygasa ${_esc(inv.expires_at?.slice(0,10)||'?')}</div>
        </div>
        <div style="display:flex;align-items:center;gap:6px">${badge}${revokeBtn}</div>
      </div>`;
    }).join('');
  } catch(e) { if (listEl) listEl.innerHTML = `<div style="color:var(--red,#e55)">${_esc(e.message)}</div>`; }
}

function _invRollMessage() {
  const t = _INV_TEMPLATES[Math.floor(Math.random() * _INV_TEMPLATES.length)];
  const el = document.getElementById('inv-msg');
  if (el) el.value = t.replace('[LINK]', _invCurrentLink || '[link zostanie wstawiony po wygenerowaniu]');
}

function _invCopyFullMsg() {
  const text = document.getElementById('inv-full-msg')?.textContent || _invCurrentLink;
  navigator.clipboard.writeText(text).then(() => showToast('Wiadomość skopiowana.', 'success'));
}

function _invCopyLink() {
  navigator.clipboard.writeText(_invCurrentLink).then(() => showToast('Link skopiowany.', 'success'));
}

async function _invSendEmail(btn) {
  if (!_invLastCode) { showToast('Najpierw wygeneruj zaproszenie.', 'error'); return; }
  if (!_invLastEmail) { showToast('Brak adresu e-mail.', 'error'); return; }
  btn.disabled = true; btn.textContent = '⏳ Wysyłam…';
  const inviterName = document.getElementById('inv-sender')?.value?.trim() || 'AI-GM';
  try {
    await apiFetch(`/api/admin/invites/${_invLastCode}/send-email`, {
      method: 'POST',
      body: JSON.stringify({ inviter_name: inviterName }),
    });
    showToast(`E-mail wysłany do ${_invLastEmail}`, 'success');
    btn.textContent = '✓ Wysłano';
  } catch(e) {
    showToast(e.message || 'Błąd wysyłki e-mail.', 'error');
    btn.disabled = false; btn.textContent = '📧 Wyślij e-mail';
  }
}

async function createInvite(btn) {
  const email = document.getElementById('inv-email')?.value?.trim() || null;
  const message = document.getElementById('inv-msg')?.value?.trim() || null;
  const max_uses = parseInt(document.getElementById('inv-max-uses')?.value ?? '1', 10);
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const d = await apiFetch('/api/admin/invites', { method: 'POST', body: JSON.stringify({ email, message, max_uses }) });
    // Build full link — backend may return relative path if APP_BASE_URL not set
    const rawLink = d.invite_link || '';
    _invCurrentLink = rawLink.startsWith('http') ? rawLink : `${_INV_BASE_URL}${rawLink}`;
    _invLastCode = d.code || '';
    _invLastEmail = email || '';

    const linkEl = document.getElementById('inv-link');
    const resultEl = document.getElementById('inv-result');
    const fullMsgEl = document.getElementById('inv-full-msg');
    const msgEl = document.getElementById('inv-msg');
    const sendBtn = document.getElementById('inv-send-email-btn');

    if (linkEl) linkEl.textContent = _invCurrentLink;

    // Build full message: replace [LINK] placeholder or append link
    const msgRaw = msgEl?.value?.trim() || '';
    const fullMsg = msgRaw
      ? (msgRaw.includes('[LINK]') ? msgRaw.replace('[LINK]', _invCurrentLink) : msgRaw + '\n\n' + _invCurrentLink)
      : _invCurrentLink;
    if (fullMsgEl) fullMsgEl.textContent = fullMsg;

    // Update textarea to show final message with real link
    if (msgEl && msgRaw.includes('[LINK]')) msgEl.value = msgRaw.replace('[LINK]', _invCurrentLink);

    // Show send button only when email is provided; reset state
    if (sendBtn) {
      sendBtn.style.display = email ? '' : 'none';
      sendBtn.disabled = false;
      sendBtn.textContent = '📧 Wyślij e-mail';
    }

    // Show batch badge if multi-use
    const batchBadgeEl = document.getElementById('inv-batch-badge');
    if (batchBadgeEl) {
      if (max_uses === 0) { batchBadgeEl.textContent = '∞ bez limitu'; batchBadgeEl.style.display = ''; }
      else if (max_uses > 1) { batchBadgeEl.textContent = `batch · ${max_uses} użyć`; batchBadgeEl.style.display = ''; }
      else batchBadgeEl.style.display = 'none';
    }

    if (resultEl) resultEl.style.display = '';
    showToast('Zaproszenie wygenerowane.', 'success');
    await _refreshInviteList();
  } catch(e) { showToast(e.message || 'Błąd generowania.', 'error'); }
  finally { btn.disabled = false; btn.textContent = '⚔ Generuj zaproszenie'; }
}

async function revokeInvite(id, btn) {
  if (!confirm('Odwołać zaproszenie?')) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/invites/${id}`, { method: 'DELETE' });
    showToast('Odwołano.', 'success');
    await _refreshInviteList();
  } catch(e) { showToast(e.message||'Błąd.','error'); btn.disabled = false; }
}

// ── Init ───────────────────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = `<div id="section-invites">
      <div class="section-header">
        <div>
          <div class="section-heading">Zaproszenia</div>
          <div class="section-sub">Zapraszaj graczy i przeglądaj genealogię drużyny</div>
        </div>
      </div>

      <div class="two-col" style="margin-bottom:12px;align-items:start">

        <!-- LEFT: invite generator -->
        <div class="card" style="display:flex;flex-direction:column;gap:0">
          <div class="card-header" style="display:flex;align-items:center;justify-content:space-between">
            <span class="card-title">⚔ Nowe zaproszenie</span>
            <button class="btn btn-sm btn-secondary" onclick="_invRollMessage()" title="Losuj inną wiadomość" style="padding:3px 10px;font-size:0.76rem">🎲 Losuj wiadomość</button>
          </div>
          <div style="padding:14px 16px;display:flex;flex-direction:column;gap:10px">
            <div class="form-row" style="margin:0">
              <label style="font-size:0.78rem;font-weight:600;color:var(--t2);margin-bottom:4px">Nadawca (nazwa w e-mailu)</label>
              <input id="inv-sender" class="field-input" type="text" placeholder="Piotr Szmidt" value="Piotr Szmidt" style="font-size:0.82rem" />
            </div>
            <div class="form-row" style="margin:0">
              <label style="font-size:0.78rem;font-weight:600;color:var(--t2);margin-bottom:4px">E-mail gracza (opcjonalnie)</label>
              <input id="inv-email" class="field-input form-mono" type="email" placeholder="gracz@example.com" style="font-size:0.82rem" />
            </div>
            <div class="form-row" style="margin:0">
              <label style="font-size:0.78rem;font-weight:600;color:var(--t2);margin-bottom:4px">Limit użyć</label>
              <select id="inv-max-uses" class="field-input" style="font-size:0.82rem">
                <option value="1">1 — jednorazowe (dla konkretnej osoby)</option>
                <option value="5">5 użyć</option>
                <option value="10">10 użyć</option>
                <option value="25" selected>25 użyć (batch startowy)</option>
                <option value="50">50 użyć</option>
                <option value="100">100 użyć</option>
                <option value="0">∞ — bez limitu</option>
              </select>
            </div>
            <div class="form-row" style="margin:0">
              <label style="font-size:0.78rem;font-weight:600;color:var(--t2);margin-bottom:4px">Treść wiadomości</label>
              <textarea id="inv-msg" class="field-input" rows="6" style="font-size:0.8rem;line-height:1.5;resize:vertical" placeholder="Kliknij 🎲 Losuj wiadomość lub wpisz własną…"></textarea>
            </div>
            <button class="btn btn-primary" onclick="createInvite(this)" style="width:100%;font-weight:600">⚔ Generuj zaproszenie</button>
          </div>

          <!-- Result panel -->
          <div id="inv-result" style="display:none;border-top:1px solid var(--border)">
            <div style="padding:14px 16px;display:flex;flex-direction:column;gap:10px">
              <div style="display:flex;align-items:center;gap:8px">
                <div style="font-size:0.75rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em">Gotowe do wysłania</div>
                <span id="inv-batch-badge" style="display:none;font-size:0.7rem;background:rgba(124,111,224,0.2);color:#a090e0;border:1px solid rgba(124,111,224,0.35);border-radius:4px;padding:1px 7px;font-weight:600"></span>
              </div>

              <!-- Full message preview -->
              <div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;font-size:0.8rem;line-height:1.6;white-space:pre-wrap;font-family:inherit;color:var(--t1);max-height:220px;overflow-y:auto" id="inv-full-msg"></div>

              <div style="display:flex;gap:8px">
                <button class="btn btn-primary btn-sm" style="flex:1" onclick="_invCopyFullMsg()">📋 Kopiuj wiadomość</button>
                <button class="btn btn-sm btn-secondary" style="flex:1" onclick="_invCopyLink()">🔗 Kopiuj sam link</button>
              </div>
              <button id="inv-send-email-btn" class="btn btn-sm" style="display:none;width:100%;background:linear-gradient(135deg,#2a6b3a,#1e5230);color:#a8f0b8;border:1px solid #2a6b3a;font-weight:600" onclick="_invSendEmail(this)">📧 Wyślij e-mail</button>

              <div style="font-size:0.72rem;color:var(--t3);padding:6px 8px;background:var(--surface);border-radius:6px;word-break:break-all;font-family:monospace" id="inv-link"></div>
            </div>
          </div>
        </div>

        <!-- RIGHT: active invites list -->
        <div class="card">
          <div class="card-header"><span class="card-title">📬 Aktywne zaproszenia</span></div>
          <div id="invites-list" style="font-size:0.82rem;padding:8px 16px 12px"></div>
        </div>
      </div>

      <!-- Player tree -->
      <div class="card">
        <div class="card-header"><span class="card-title">🌳 Drzewo graczy</span></div>
        <div id="invite-tree-svg-wrap" style="overflow-x:auto;min-height:300px;background:rgba(0,0,0,0.15);border-radius:8px;padding:16px;position:relative;margin:8px">
          <div id="inv-tree-loading" style="text-align:center;padding:60px;color:var(--t3)">Ładowanie drzewa…</div>
          <svg id="invite-tree-svg" style="display:block"></svg>
        </div>
        <div style="padding:8px 12px 12px;display:flex;gap:16px;flex-wrap:wrap;font-size:0.78rem;color:var(--t3)">
          <span><span style="color:#4caf78">●</span> Aktywny (&lt;30 dni, ≥10 tur)</span>
          <span><span style="color:#c9944a">●</span> Mało aktywny (1–9 tur)</span>
          <span><span style="color:#6b665e">●</span> Nieaktywny</span>
        </div>
      </div>
  </div>`;
  _loadInvites();
}

Object.assign(window, { createInvite, revokeInvite, _invRollMessage, _invCopyFullMsg, _invCopyLink, _invSendEmail });
