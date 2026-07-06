/**
 * #1211 — Sandbox scenariuszy (modular admin/).
 * Deterministyczny setup sesji pod testowany element + boczny log mechaniki.
 * Przygotowanie robi agent (Claude: czyta issue → scenario_prepare przez MCP)
 * albo admin ręcznie przez formularz setupu poniżej. Exported: init(panel).
 */
import { apiFetch }  from '../shared/api.js';
import { showToast } from '../shared/toast.js';

function _esc(s) { return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

const SETUP_TEMPLATE = {
  hero_id: 0,
  issue_number: 0,
  title: 'Opis testowanego elementu',
  location_name: 'Zaułek w Błotsteinie',
  scene_enemies: [],
  scene_npcs: [],
  start_combat: false,
  session_flags: {},
  ingame_hours: 9,
  hero_overrides: {},
  gm_plan: {},
  opening_narration: 'Stoisz w…',
  agent_notes: '',
};

let _pollTimer = null;
let _pollSince = 0;
let _pollCid = 0;

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-head"><h2>🎬 Sandbox scenariuszy <span style="font-size:12px;color:var(--t3)">#1211</span></h2></div>
    <p style="color:var(--t3);max-width:820px">
      Ustawia jednorazową, izolowaną sesję (klon bohatera <code>[SCN]</code> + kampania
      <code>[SBX-SCN]</code>) dokładnie „w miejscu" testowanego elementu — grasz normalnie w UI
      gracza, a tu widzisz log mechaniki tura po turze. Najprościej: poproś agenta
      (<code>przygotuj scenariusz pod #NNN</code>) — agent czyta issue i sam wypełnia setup.
    </p>

    <div style="display:grid;grid-template-columns:minmax(320px,420px) 1fr;gap:16px;align-items:start">
      <div>
        <div class="card" style="padding:14px;border:1px solid var(--accent,#6b8afd)">
          <h3 style="margin-top:0">🤖 Kreator — opisz agentowi</h3>
          <div style="display:flex;gap:8px">
            <input id="scn-issue" type="number" placeholder="# issue" style="width:110px">
            <span style="color:var(--t3);font-size:12px;align-self:center">i/lub opis:</span>
          </div>
          <textarea id="scn-desc" rows="3" placeholder="Np. „ustaw rannego bohatera nocą w zaułku z dwoma bandytami — testuję gate ucieczki""
            style="width:100%;margin-top:6px"></textarea>
          <button id="scn-draft" class="btn btn-primary" style="margin-top:6px">✨ Wygeneruj setup (LLM)</button>
          <div id="scn-draft-reply" style="font-size:12px;color:var(--t3);margin-top:6px"></div>
        </div>
        <div class="card" style="padding:14px;margin-top:14px">
          <h3 style="margin-top:0">Przygotuj ręcznie</h3>
          <label style="font-size:12px;color:var(--t3)">Bohater (źródło klona — nietykany)</label>
          <select id="scn-hero" style="width:100%;margin:4px 0 10px"></select>
          <label style="font-size:12px;color:var(--t3)">Setup (JSON)</label>
          <textarea id="scn-setup" rows="14" spellcheck="false"
            style="width:100%;font-family:monospace;font-size:12px"></textarea>
          <button id="scn-prepare" class="btn btn-primary" style="margin-top:8px">🎬 Przygotuj scenariusz</button>
        </div>
        <div class="card" style="padding:14px;margin-top:14px">
          <h3 style="margin-top:0">Scenariusze <button id="scn-refresh" class="btn" style="float:right">↻</button></h3>
          <div id="scn-list">Ładowanie…</div>
        </div>
      </div>
      <div class="card" style="padding:14px">
        <h3 style="margin-top:0">📡 Log mechaniki
          <label style="float:right;font-size:12px;color:var(--t3)">
            <input type="checkbox" id="scn-poll"> auto-odświeżaj (5 s)
          </label>
        </h3>
        <div id="scn-state-head" style="color:var(--t3);font-size:13px">Wybierz scenariusz z listy.</div>
        <div id="scn-log" style="margin-top:10px"></div>
      </div>
    </div>`;

  const $ = (id) => panel.querySelector('#' + id);
  $('scn-setup').value = JSON.stringify(SETUP_TEMPLATE, null, 2);

  // heroes dropdown — reuse combat-sandbox lookup
  try {
    const h = await apiFetch('/api/admin/sandbox/heroes');
    $('scn-hero').innerHTML = (h.heroes || []).map(x =>
      `<option value="${x.id}">${_esc(x.name)} (L${x.level ?? '?'} ${_esc(x.archetype ?? '')}, u${x.user_id})</option>`
    ).join('') || '<option value="">brak bohaterów</option>';
  } catch (e) { $('scn-hero').innerHTML = '<option value="">błąd wczytywania</option>'; }

  $('scn-draft').addEventListener('click', async () => {
    const issueNo = parseInt($('scn-issue').value, 10) || null;
    const desc = $('scn-desc').value.trim();
    if (!issueNo && !desc) { showToast('Podaj numer issue albo opis', 'error'); return; }
    const btn = $('scn-draft');
    btn.disabled = true; btn.textContent = '⏳ LLM pracuje…';
    try {
      const res = await apiFetch('/api/admin/scenario/draft', {
        method: 'POST', body: JSON.stringify({ issue_number: issueNo, description: desc }),
      });
      $('scn-setup').value = JSON.stringify(res.setup, null, 2);
      if (res.setup?.hero_id) $('scn-hero').value = String(res.setup.hero_id);
      $('scn-draft-reply').innerHTML =
        `${_esc(res.reply)}${res.issue ? `<br>📄 issue #${res.issue.number}: ${_esc(res.issue.title)}` : ''}` +
        `${res.setup?.agent_notes ? `<br>📝 ${_esc(res.setup.agent_notes)}` : ''}` +
        '<br><b>Sprawdź setup po prawej i kliknij 🎬 Przygotuj.</b>';
    } catch (e) { showToast('Kreator: ' + e.message, 'error'); }
    finally { btn.disabled = false; btn.textContent = '✨ Wygeneruj setup (LLM)'; }
  });

  $('scn-prepare').addEventListener('click', async () => {
    let setup;
    try { setup = JSON.parse($('scn-setup').value); }
    catch (e) { showToast('Setup nie jest poprawnym JSON: ' + e.message, 'error'); return; }
    const heroSel = parseInt($('scn-hero').value, 10);
    if (!setup.hero_id && heroSel) setup.hero_id = heroSel;
    try {
      const res = await apiFetch('/api/admin/scenario/prepare', {
        method: 'POST', body: JSON.stringify(setup),
      });
      showToast(`Scenariusz gotowy — kampania #${res.campaign_id}, klon ${res.hero?.name}`, 'success');
      await loadList();
      watch(res.campaign_id);
    } catch (e) { showToast('Prepare: ' + e.message, 'error'); }
  });

  $('scn-refresh').addEventListener('click', loadList);
  $('scn-poll').addEventListener('change', (ev) => {
    clearInterval(_pollTimer); _pollTimer = null;
    if (ev.target.checked && _pollCid) _pollTimer = setInterval(() => renderState(_pollCid, true), 5000);
  });

  async function loadList() {
    try {
      const res = await apiFetch('/api/admin/scenario/list');
      const rows = res.scenarios || [];
      $('scn-list').innerHTML = rows.length ? rows.map(s => `
        <div class="card" style="padding:10px;margin-bottom:8px">
          <div><b>${_esc(s.title)}</b> <span style="color:var(--t3)">(${s.status})</span></div>
          <div style="font-size:12px;color:var(--t3)">
            ${s.issue_number ? `issue <b>#${s.issue_number}</b> · ` : ''}
            ${_esc(s.character_name || '—')} · tur: ${s.turn_count}
          </div>
          ${s.agent_notes ? `<div style="font-size:12px;color:var(--amber,#caa)">📝 ${_esc(s.agent_notes)}</div>` : ''}
          <div style="margin-top:6px">
            <button class="btn" data-watch="${s.campaign_id}">📡 Log</button>
            <a class="btn" href="/?campaign=${s.campaign_id}" target="_blank"
               title="Deep-link: otwiera tę kampanię w UI gracza (konto właściciela klona; po zalogowaniu trafiasz prosto do czatu)">▶ Graj</a>
          </div>
        </div>`).join('') : '<div style="color:var(--t3)">Brak aktywnych scenariuszy.</div>';
      $('scn-list').querySelectorAll('[data-watch]').forEach(b =>
        b.addEventListener('click', () => watch(parseInt(b.dataset.watch, 10))));
    } catch (e) { $('scn-list').innerHTML = `<div style="color:var(--red)">${_esc(e.message)}</div>`; }
  }

  function watch(cid) {
    _pollCid = cid; _pollSince = 0;
    localStorage.setItem('aigm_scn_watch', String(cid));
    $('scn-log').innerHTML = '';
    renderState(cid, false);
    if ($('scn-poll').checked) {
      clearInterval(_pollTimer);
      _pollTimer = setInterval(() => renderState(cid, true), 5000);
    }
  }

  async function renderState(cid, incremental) {
    try {
      const st = await apiFetch(`/api/admin/scenario/${cid}/state?since_turn=${incremental ? _pollSince : 0}`);
      const h = st.hero || {};
      $('scn-state-head').innerHTML = `
        <b>${_esc(st.campaign?.title)}</b> —
        ${_esc(h.name || '')} ❤️ ${h.hp}/${h.max_hp}${h.mana ? ` · ✨ ${h.mana}` : ''} ·
        🕐 ${st.session?.ingame_hours}:00 ·
        wrogowie sceny: ${JSON.stringify(st.session?.scene_enemies || [])}
        ${st.active_combat ? ' · <b style="color:var(--red)">⚔ WALKA AKTYWNA</b>'
          : (st.last_combat ? ` · ⚔ walka zakończona (${_esc(st.last_combat.status)})` : '')}`;
      // merge: każda tura z rozmowy + jej ślad mechaniki (mechanika bez tury też widoczna)
      const mech = {};
      (st.mechanics || []).forEach(t => { mech[t.turn_number] = t; });
      const turnNums = [...new Set([
        ...(st.turns || []).map(t => t.turn_number),
        ...Object.keys(mech).map(Number),
      ])].sort((a, b) => a - b);
      const blocks = turnNums.map(n => {
        const turn = (st.turns || []).find(t => t.turn_number === n);
        const t = mech[n] || {};
        const d = t.decision;
        return `
        <div class="card" style="padding:8px;margin-bottom:6px;font-size:12px">
          <div><b>Tura ${n}</b>${d ? ` — intent: <b>${_esc(d.action_type)}</b> → ${_esc(d.route)}${d.gate_blocked ? ` · ⛔ gate: ${_esc(d.gate_reason || '')}` : ''} · handler: ${_esc(d.handler || '')}` : ''}</div>
          ${turn ? `<div style="color:var(--t3)">🗨 ${_esc((turn.user_text || '').slice(0, 80))} → ${_esc((turn.assistant_text || '').slice(0, 110))}…</div>` : ''}
          ${((t.dice_rolls) || []).map(r =>
            `<div>🎲 ${_esc(r.roll_type)} [${_esc(r.actor)}] ${_esc(r.notation || '')} = <b>${r.total}</b>${r.dc ? ` vs DC ${r.dc}` : ''} → ${_esc(r.outcome || '')}</div>`).join('')}
          ${((t.state_changes) || []).map(s =>
            `<div>Δ ${_esc(s.resource)}: ${_esc(s.before_val)} → ${_esc(s.after_val)} (${_esc(s.delta)}) — ${_esc(s.cause || '')}</div>`).join('')}
          ${!d && !(t.dice_rolls || []).length && !(t.state_changes || []).length ? '<div style="color:var(--t3)">— bez śladu mechaniki (czysta narracja)</div>' : ''}
        </div>`;
      }).join('');
      if (incremental) $('scn-log').insertAdjacentHTML('afterbegin', blocks);
      else $('scn-log').innerHTML = blocks || '<div style="color:var(--t3)">Brak tur (zagraj pierwszą turę w UI gracza).</div>';
      const nums = [
        ...(st.mechanics || []).map(t => t.turn_number),
        ...(st.turns || []).map(t => t.turn_number),
      ];
      if (nums.length) _pollSince = Math.max(_pollSince, ...nums);
    } catch (e) {
      if (!incremental) $('scn-log').innerHTML = `<div style="color:var(--red)">${_esc(e.message)}</div>`;
    }
  }

  await loadList();

  // F5-persist: wróć do oglądanego scenariusza, jeśli nadal istnieje
  const saved = parseInt(localStorage.getItem('aigm_scn_watch') || '', 10);
  if (saved && panel.querySelector(`[data-watch="${saved}"]`)) watch(saved);
}
