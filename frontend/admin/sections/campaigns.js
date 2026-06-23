import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';
import { rowCheck, toggleAll } from '../shared/selection.js';  // #588

// ── Module helpers ─────────────────────────────────────────────────────────
const _esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const _loading = cols => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Ładowanie…</td></tr>`;
const _errRow  = (cols, msg) => `<tr><td colspan="${cols}" style="text-align:center;padding:28px;color:var(--red);font-size:0.8rem">${_esc(msg)}</td></tr>`;
function _showToast(msg, type) { showToast(msg, type); }
function _timeAgo(iso) {
  if (!iso) return '';
  const diff = Math.round((Date.now() - new Date(iso)) / 1000);
  if (diff < 60) return 'przed chwil\u0105';
  if (diff < 3600) return `${Math.round(diff/60)} min temu`;
  if (diff < 86400) return `${Math.round(diff/3600)} godz. temu`;
  return `${Math.round(diff/86400)} dni temu`;
}
function _hp(cur, max) {
  if (!max) return '<span class="td-muted">\u2014</span>';
  const pct = Math.round(cur / max * 100);
  const cls = pct > 60 ? 'high' : pct > 30 ? 'mid' : 'low';
  const col = pct <= 30 ? ' style="color:var(--red)"' : '';
  return `<div class="hp-wrap"><div class="hp-bar"><div class="hp-fill ${cls}" style="width:${pct}%"></div></div><span class="hp-label"${col}>${cur}/${max}</span></div>`;
}
function filterTableGeneric(input, tableId, nameClass) {
  const q = input.value.toLowerCase();
  document.querySelectorAll(`#${tableId} tbody tr`).forEach(row => {
    const txt = row.querySelector('.'+ nameClass)?.textContent?.toLowerCase() || '';
    row.style.display = txt.includes(q) ? '' : 'none';
  });
}


// ══════════════════════════════════════════════════════════════
//  filterCampaigns
// ══════════════════════════════════════════════════════════════
  function filterCampaigns(chip, status) {
    document.querySelectorAll('#section-campaigns .filter-group .chip').forEach(c => c.classList.remove('on'));
    chip.classList.add('on');
    const statusMap = { 'aktywne': 'aktywna', 'w walce': 'walce', 'zakończone': 'zakończona', 'usunięte': 'usunięta' };
    const match = statusMap[status] || status;
    // Filter table rows
    document.querySelectorAll('#campaigns-table tbody tr').forEach(row => {
      if (!status) { row.style.display = ''; return; }
      const badge = row.querySelector('.badge')?.textContent?.toLowerCase() || '';
      row.style.display = badge.includes(match) ? '' : 'none';
    });
    // Filter cards view
    document.querySelectorAll('#campaigns-cards-grid > .card').forEach(card => {
      if (!status) { card.style.display = ''; return; }
      const badge = card.querySelector('.badge')?.textContent?.toLowerCase() || '';
      card.style.display = badge.includes(match) ? '' : 'none';
    });
  }

// ══════════════════════════════════════════════════════════════
//  _campsData / _loadCampaigns / _renderCampCards / _setCampView
// ══════════════════════════════════════════════════════════════
  let _campsData = [];
  async function _loadCampaigns() {
    const tbody = document.querySelector('#campaigns-table tbody');
    if (!tbody) return;
    tbody.innerHTML = _loading(9);
    try {
      const d = await apiFetch('/api/admin/campaigns/live');
      const items = d.items || [];
      _campsData = items;
      if (!items.length) { tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:24px;color:var(--t3)">Brak kampanii</td></tr>`; _renderCampCards(); return; }
      const archMap = { warrior:'Wojownik', scholar:'Uczony', rogue:'Złodziej', ranger:'Ranger' };
      const statusBadge = s => ({'active':'<span class="badge badge-green">● Aktywna</span>','in_combat':'<span class="badge badge-red">⚔ W walce</span>','ended':'<span class="badge badge-slate">✓ Zakończona</span>','idle':'<span class="badge badge-slate">○ Oczekuje</span>','deleted_by_player':'<span class="badge badge-slate" style="opacity:0.6">🗑 Usunięta</span>'}[s] || `<span class="badge badge-slate">${_esc(s)}</span>`);
      tbody.innerHTML = items.map(c => `<tr>
        <td class="col-check"><input type="checkbox" class="camp-row-check" onchange="rowCheck('camp')"></td>
        <td class="td-sticky" data-label="Kampania" data-sort-val="${_esc(c.title)}"><div class="campaign-row-name">${_esc(c.title)}${c.plan_degraded ? ' <span title="GM Plan nie mógł być wygenerowany przez LLM; użyto planu zapasowego. Zregeneruj z Warsztatu." style="font-size:0.72rem;color:#f59e0b;cursor:help">⚠ Plan uproszczony</span>' : ''}</div><div class="campaign-row-sub"><span class="td-muted" style="margin-right:6px">#${c.id}</span>${_timeAgo(c.last_turn_at)||'brak tur'}</div></td>
        <td class="td-mono" data-label="Bohater" data-sort-val="${_esc(c.char_name||'')}">${_esc(c.char_name||'—')}${c.owner_username?`<div class="td-muted" style="font-size:0.74rem">@${_esc(c.owner_username)}</div>`:''}</td>
        <td data-label="Klasa" data-sort-val="${_esc(archMap[c.char_archetype]||c.char_archetype||'')}">${c.char_archetype?`<span class="type-badge">${_esc(archMap[c.char_archetype]||c.char_archetype)}</span>`:'<span class="td-muted">—</span>'}</td>
        <td class="td-mono" data-label="Poz." data-sort-val="${c.char_level??''}">${c.char_level??'—'}</td>
        <td data-label="HP" data-sort-val="${c.char_current_hp??''}">${_hp(c.char_current_hp, c.char_max_hp)}</td>
        <td class="td-mono" data-label="Tura" data-sort-val="${c.turn_count??''}">${c.turn_count??'—'}</td>
        <td data-label="Status" data-sort-val="${c.status??''}">${statusBadge(c.status)}</td>
        <td class="td-actions"><button class="btn-icon" title="Szczegóły" onclick="openCampaignModal(${c.id})">⊞</button> <button class="btn-icon danger" title="Usuń kampanię" onclick="deleteCampaign(${c.id},'${_esc(c.title)}',this)">✕</button></td>
      </tr>`).join('');
      const pg = document.querySelector('#section-campaigns .pagination span');
      if (pg) pg.textContent = `${items.length} kampanii`;
      _renderCampCards();
      // Apply persisted view choice
      const saved = (() => { try { return localStorage.getItem('v3_camp_view'); } catch { return null; } })();
      if (saved === 'cards') _setCampView('cards');
    } catch(e) { tbody.innerHTML = _errRow(9, e.message); }
  }

  function _renderCampCards() {
    const grid = document.getElementById('campaigns-cards-grid');
    if (!grid) return;
    if (!_campsData.length) { grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--t3)">Brak kampanii.</div>'; return; }
    const archMap = { warrior:'Wojownik', scholar:'Uczony', rogue:'Złodziej', ranger:'Ranger' };
    grid.innerHTML = _campsData.map(c => {
      const pct = c.char_max_hp ? Math.round((c.char_current_hp/c.char_max_hp)*100) : 0;
      const hpCls = pct < 30 ? 'low' : pct < 65 ? 'mid' : 'green';
      const statusBadge = ({'active':'<span class="badge badge-green">● Aktywna</span>','in_combat':'<span class="badge badge-red">⚔ W walce</span>','ended':'<span class="badge badge-slate">✓ Zakończona</span>','idle':'<span class="badge badge-slate">○ Oczekuje</span>','deleted_by_player':'<span class="badge badge-slate" style="opacity:0.6">🗑 Usunięta</span>'}[c.status] || '<span class="badge badge-slate">—</span>');
      return `<div class="card" style="padding:14px;cursor:pointer" onclick="openCampaignModal(${c.id})">
        <div style="display:flex;justify-content:space-between;align-items:start;gap:8px;margin-bottom:8px">
          <div style="font-weight:600;color:var(--t1);font-size:0.94rem">${_esc(c.title)}${c.plan_degraded ? ' <span title="GM Plan nie mógł być wygenerowany przez LLM; użyto planu zapasowego. Zregeneruj z Warsztatu." style="font-size:0.7rem;color:#f59e0b;cursor:help;display:block;margin-top:2px">⚠ Plan uproszczony</span>' : ''}</div>
          ${statusBadge}
        </div>
        <div style="display:flex;gap:8px;font-size:0.78rem;color:var(--t2);margin-bottom:10px">
          <span>${_esc(c.char_name||'?')}</span>
          ${c.owner_username?`<span class="td-muted">@${_esc(c.owner_username)}</span>`:''}
          ${c.char_archetype ? `<span class="type-badge">${_esc(archMap[c.char_archetype]||c.char_archetype)}</span>` : ''}
          <span class="td-muted">Poz. ${c.char_level??'—'}</span>
        </div>
        ${c.char_max_hp ? `<div style="margin-bottom:8px"><div class="hp-bar"><div class="hp-fill ${hpCls}" style="width:${pct}%"></div></div><div style="font-size:0.72rem;color:var(--t3);margin-top:3px">HP ${c.char_current_hp??'—'}/${c.char_max_hp}</div></div>` : ''}
        <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:var(--t3)">
          <span>Tury: <strong style="color:var(--t1)">${c.turn_count??'—'}</strong></span>
          <span style="display:flex;gap:6px;align-items:center"><span style="opacity:0.5">#${c.id}</span><span>${_timeAgo(c.last_turn_at)||'brak tur'}</span></span>
        </div>
      </div>`;
    }).join('');
  }

  function _setCampView(view) {
    const tableView = document.getElementById('campaigns-table-view');
    const cardsView = document.getElementById('campaigns-cards-view');
    if (!tableView || !cardsView) return;
    tableView.style.display = view === 'cards' ? 'none' : '';
    cardsView.style.display = view === 'cards' ? 'block' : 'none';
    document.querySelectorAll('#camp-view-toggle .btn-view').forEach(b => {
      const on = b.dataset.view === view;
      b.style.background = on ? 'var(--blue)' : 'var(--bg2)';
      b.style.color = on ? '#fff' : 'var(--t2)';
      b.classList.toggle('active', on);
    });
    try { localStorage.setItem('v3_camp_view', view); } catch {}
    if (view === 'cards') _renderCampCards();
  }

// ══════════════════════════════════════════════════════════════
//  deleteCampaign / _bulkDeleteCampaigns
// ══════════════════════════════════════════════════════════════
  async function deleteCampaign(id, title, btn) {
    if (!confirm(`Usunąć kampanię „${title}"? Tej operacji nie da się cofnąć.`)) return;
    btn.disabled = true;
    try {
      await apiFetch(`/api/campaigns/${id}`, { method:'DELETE' });
      _showToast(`Kampania „${title}" usunięta.`, 'success');
      _loadCampaigns();
    } catch(e) { _showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; }
  }

  async function _bulkDeleteCampaigns(btn) {
    const checked = [...document.querySelectorAll('.camp-row-check:checked')];
    if (!checked.length) { _showToast('Nic nie zaznaczone.','warn'); return; }
    if (!confirm(`Usunąć ${checked.length} kampanię(-e)? Operacji nie da się cofnąć.`)) return;
    btn.disabled = true;
    let ok = 0, fail = 0;
    for (const cb of checked) {
      const row = cb.closest('tr');
      const delBtn = row?.querySelector('.btn-icon.danger');
      const titleEl = row?.querySelector('.campaign-row-name');
      const id = delBtn?.getAttribute('onclick')?.match(/deleteCampaign\((\d+)/)?.[1];
      if (!id) { fail++; continue; }
      try { await apiFetch(`/api/campaigns/${id}`, { method:'DELETE' }); ok++; } catch { fail++; }
    }
    _showToast(`Usunięto ${ok}${fail?' (błąd: '+fail+')':''}.`, fail ? 'warn' : 'success');
    btn.disabled = false;
    _loadCampaigns();
  }

// ══════════════════════════════════════════════════════════════
//  Campaign admin commands (_CAMP_CMDS + helpers + _campModalResurrect)
// ══════════════════════════════════════════════════════════════
  const _CAMP_CMDS = [
    { cmd: '/debug set-hp',          hint: 'N',          desc: 'Ustaw HP postaci' },
    { cmd: '/debug dump-state',       hint: '',           desc: 'Pokaż pełny stan' },
    { cmd: '/debug xp add',          hint: 'N',          desc: 'Dodaj XP' },
    { cmd: '/debug xp set',          hint: 'N',          desc: 'Ustaw XP' },
    { cmd: '/debug roll',            hint: '[skill]',     desc: 'Rzut kością' },
    { cmd: '/debug reset-cooldowns', hint: '',           desc: 'Resetuj cooldowny' },
    { cmd: '/debug set-state',       hint: 'NARRATIVE|COMBAT', desc: 'Zmień stan sesji' },
    { cmd: '/heal',                  hint: '[N|max]',    desc: 'Dodaj HP (domyślnie max)' },
    { cmd: '/sethp',                 hint: 'N',          desc: 'Ustaw HP na N' },
    { cmd: '/gold',                  hint: 'N',          desc: 'Dodaj N złota' },
    { cmd: '/setgold',               hint: 'N',          desc: 'Ustaw złoto na N' },
    { cmd: '/level',                 hint: 'N',          desc: 'Ustaw poziom' },
    { cmd: '/stat',                  hint: 'STR|DEX|CON|INT|WIS|CHA N', desc: 'Dodaj do statystyki' },
    { cmd: '/additem',               hint: 'klucz',      desc: 'Dodaj przedmiot' },
    { cmd: '/removeitem',            hint: 'klucz',      desc: 'Usuń przedmiot' },
    { cmd: '/clearinv',              hint: '',           desc: 'Wyczyść ekwipunek' },
    { cmd: '/questadd',              hint: 'klucz',      desc: 'Dodaj quest' },
    { cmd: '/questfinish',           hint: 'klucz',      desc: 'Zakończ quest' },
    { cmd: '/combatend',             hint: '',           desc: 'Zakończ walkę' },
    { cmd: '/show',                  hint: '',           desc: 'Pokaż stan postaci' },
  ];

  let _campCmdSuggestIdx = -1;

  function _campCmdSuggest(campId, input) {
    const dropdown = document.getElementById(`camp-cmd-suggest-${campId}`);
    if (!dropdown) return;
    const val = (input.value || '').toLowerCase();
    if (!val || !val.startsWith('/')) { dropdown.style.display = 'none'; return; }
    const matches = _CAMP_CMDS.filter(c => c.cmd.toLowerCase().startsWith(val) || c.cmd.toLowerCase().includes(val.slice(1)));
    if (!matches.length) { dropdown.style.display = 'none'; return; }
    _campCmdSuggestIdx = -1;
    dropdown.innerHTML = matches.map((c, i) => `
      <div class="camp-cmd-item" data-idx="${i}" data-fill="${_esc(c.hint ? c.cmd + ' ' : c.cmd)}"
        style="padding:7px 12px;cursor:pointer;display:flex;gap:10px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,0.05)"
        onmouseenter="this.style.background='rgba(124,111,224,0.15)'" onmouseleave="this.style.background=''"
        onmousedown="event.preventDefault();_campCmdPick(${campId},'${_esc(c.hint ? c.cmd + ' ' : c.cmd)}')">
        <span style="font-family:monospace;font-size:0.8rem;color:var(--t1);white-space:nowrap">${_esc(c.cmd)}${c.hint ? ' <span style=\'color:var(--t3)\'>' + _esc(c.hint) + '</span>' : ''}</span>
        <span style="font-size:0.72rem;color:var(--t3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_esc(c.desc)}</span>
      </div>`).join('');
    dropdown.style.display = 'block';
  }

  function _campCmdPick(campId, fill) {
    const input = document.getElementById(`camp-cmd-input-${campId}`);
    const dropdown = document.getElementById(`camp-cmd-suggest-${campId}`);
    if (input) { input.value = fill; input.focus(); }
    if (dropdown) dropdown.style.display = 'none';
    _campCmdSuggestIdx = -1;
  }

  function _campCmdKey(event, charId, campId) {
    const dropdown = document.getElementById(`camp-cmd-suggest-${campId}`);
    const items = dropdown ? Array.from(dropdown.querySelectorAll('.camp-cmd-item')) : [];
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      _campCmdSuggestIdx = Math.min(_campCmdSuggestIdx + 1, items.length - 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      _campCmdSuggestIdx = Math.max(_campCmdSuggestIdx - 1, -1);
    } else if (event.key === 'Tab' && items.length) {
      event.preventDefault();
      const idx = _campCmdSuggestIdx >= 0 ? _campCmdSuggestIdx : 0;
      _campCmdPick(campId, items[idx]?.dataset.fill || '');
      return;
    } else if (event.key === 'Enter') {
      if (_campCmdSuggestIdx >= 0 && items[_campCmdSuggestIdx]) {
        event.preventDefault();
        _campCmdPick(campId, items[_campCmdSuggestIdx].dataset.fill || '');
      } else {
        if (dropdown) dropdown.style.display = 'none';
        _campCmd(charId, campId, event.target);
      }
      return;
    } else if (event.key === 'Escape') {
      if (dropdown) dropdown.style.display = 'none';
      _campCmdSuggestIdx = -1;
      return;
    }
    items.forEach((el, i) => {
      el.style.background = i === _campCmdSuggestIdx ? 'rgba(124,111,224,0.25)' : '';
    });
  }

  async function _campCmd(charId, campId, btnOrEvent) {
    const inputEl = document.getElementById(`camp-cmd-input-${campId}`);
    const resultEl = document.getElementById(`camp-cmd-result-${campId}`);
    if (!inputEl) return;
    const raw = inputEl.value.trim();
    if (!raw.startsWith('/')) { if (resultEl) resultEl.innerHTML = '<span style="color:var(--red)">Komenda musi zaczynać się od /</span>'; return; }

    if (resultEl) resultEl.innerHTML = '<span style="color:var(--t3)">⏳ Wykonuję…</span>';
    const btn = btnOrEvent instanceof HTMLElement ? btnOrEvent : null;
    if (btn) btn.disabled = true;
    try {
      const res = await apiFetch(`/api/admin/campaigns/${campId}/run-command`, {
        method: 'POST',
        body: JSON.stringify({ text: raw }),
      });
      const inner = res.result ?? res;
      const summary = typeof inner === 'object'
        ? Object.entries(inner).filter(([k]) => k !== 'ok').map(([k,v]) => `${k}: <b>${Array.isArray(v)?v.join(', '):v}</b>`).join(' · ')
        : String(inner);
      if (resultEl) resultEl.innerHTML = `<span style="color:#4caf78">✓ ${summary || 'OK'}</span>`;
      inputEl.value = '';
    } catch(e) {
      if (resultEl) resultEl.innerHTML = `<span style="color:var(--red)">✗ ${_esc(e.message)}</span>`;
    }
    if (btn) btn.disabled = false;
  }

  async function _campModalResurrect(charId, name, btn) {
    if (!confirm(`Wskrzesić bohatera „${name}" bezpłatnie (admin force)?`)) return;
    btn.disabled = true; btn.textContent = 'Wskrzeszam…';
    try {
      const res = await apiFetch(`/api/admin/characters/${charId}/resurrect`, { method:'POST', body: JSON.stringify({ force: true }) });
      _showToast(`✦ ${name} wskrzeszony — HP ${res.revived_hp ?? '?'}/${res.max_hp ?? '?'}`, 'success');
      btn.textContent = '✓ Wskrzeszony';
      btn.style.background = 'var(--green)';
    } catch(e) { _showToast(e.message || 'Błąd wskrzeszenia.', 'error'); btn.disabled = false; btn.textContent = '✦ Wskrześ bohatera'; }
  }

  // HI5 (#628): otwórz Inspektora Bohatera (modal HI2) dla bohatera tej kampanii.
  // REUSE — dynamiczny import sekcji „Bohaterowie"; ten sam URL/wersja co loader sekcji
  // (?v=37) → ta sama instancja modułu w cache, bez podwójnego fetchu. Modal sam dba o
  // banery #1013 + live-lock i guardowane zapisy (audyt + 409).
  async function _campOpenInspector(charId) {
    try {
      const mod = await import('./heroes.js?v=40');
      mod.openInspector(Number(charId));
    } catch (e) {
      _showToast(`Nie udało się otworzyć inspektora: ${e.message}`, 'error');
    }
  }

// ══════════════════════════════════════════════════════════════
//  Hex-map rendering + edit modal
// ══════════════════════════════════════════════════════════════
  function _renderAdminHexMap(hexes, hexTypes, currentHex) {
    if (!hexes || !hexes.length) {
      return `<div id="admin-hex-map-svg-wrap" style="padding:24px;text-align:center;color:var(--t3)">Brak danych mapy.</div>`;
    }
    const HEX_SIZE = 18;
    const hexToPixel = (q, r) => ({ x: HEX_SIZE * 1.5 * q, y: HEX_SIZE * Math.sqrt(3) * (r + q / 2) });
    const corners = size => Array.from({length:6}, (_,i) => {
      const angle = Math.PI / 180 * (60 * i);
      return `${(size * Math.cos(angle)).toFixed(2)},${(size * Math.sin(angle)).toFixed(2)}`;
    }).join(' ');
    const pts = corners(HEX_SIZE - 1);
    const typeColors = {
      forest: '#1a3320', mountain: '#3a2a1a', plains: '#1e2b10',
      water: '#0a1e30', desert: '#2e2010', dungeon: '#2a1030',
      town: '#1a1e2e', road: '#1e1a14', default: '#181818'
    };
    const pixels = hexes.map(h => hexToPixel(h.q, h.r));
    const minX = Math.min(...pixels.map(p => p.x)) - HEX_SIZE * 1.2;
    const minY = Math.min(...pixels.map(p => p.y)) - HEX_SIZE * 1.2;
    const maxX = Math.max(...pixels.map(p => p.x)) + HEX_SIZE * 1.2;
    const maxY = Math.max(...pixels.map(p => p.y)) + HEX_SIZE * 1.2;
    const vw = (maxX - minX).toFixed(1);
    const vh = (maxY - minY).toFixed(1);
    const hexGroups = hexes.map(h => {
      const px = hexToPixel(h.q, h.r);
      const tx = (px.x - minX).toFixed(1);
      const ty = (px.y - minY).toFixed(1);
      const htColor = hexTypes[h.hex_type] && hexTypes[h.hex_type].map_color;
      const fill = htColor || typeColors[h.hex_type] || typeColors.default;
      const isCurrent = currentHex && h.q === currentHex.q && h.r === currentHex.r;
      let stroke = '#333', strokeW = '0.5';
      if (isCurrent) { stroke = '#ff2222'; strokeW = '2.5'; }
      else if (h.discovered) { stroke = '#4a8a4a'; strokeW = '1'; }
      const opacity = (h.discovered || isCurrent) ? '1' : '0.45';
      const indicators = [];
      if (isCurrent) {
        // Red pointer triangle pointing down
        indicators.push(`<polygon points="0,-7 5,2 -5,2" fill="#ff2222" opacity="0.95"/>`);
        indicators.push(`<circle cx="0" cy="0" r="2.5" fill="#fff" opacity="0.9"/>`);
      } else if (h.encounter_cleared) indicators.push(`<text x="0" y="3" text-anchor="middle" font-size="7" fill="#4a8" opacity="0.9">✓</text>`);
      if (h.campaign_label) indicators.push(`<circle cx="${(HEX_SIZE*0.5).toFixed(1)}" cy="${-(HEX_SIZE*0.55).toFixed(1)}" r="2.5" fill="#8af" opacity="0.85"/>`);
      return `<g data-q="${h.q}" data-r="${h.r}" transform="translate(${tx},${ty})" style="cursor:pointer" opacity="${opacity}">
        <polygon points="${pts}" fill="${fill}" stroke="${stroke}" stroke-width="${strokeW}"/>
        ${indicators.join('')}
      </g>`;
    });
    return `<div id="admin-hex-map-svg-wrap" style="overflow:auto;height:calc(100vh - 260px);min-height:300px;background:#0d0d0d;border:1px solid var(--border);border-radius:var(--r)">
      <svg viewBox="0 0 ${vw} ${vh}" width="${vw}" height="${vh}" xmlns="http://www.w3.org/2000/svg" style="display:block;min-width:${vw}px">
        ${hexGroups.join('\n        ')}
      </svg>
    </div>`;
  }

  const _HEX_TYPES = ['plains','forest','hills','lake','mountains','swamp','town','castle','road','river','ruins','cave','dungeon'];

  function _showHexEditModal({ campId, q, r, hex }) {
    document.getElementById('hex-edit-modal')?.remove();
    const m = document.createElement('div');
    m.id = 'hex-edit-modal';
    m.style.cssText = 'position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.7)';
    const typeOptions = _HEX_TYPES.map(t => `<option value="${t}"${t===(hex.hex_type||'')?'selected':''}>${t}</option>`).join('');
    m.innerHTML = `
      <div style="background:var(--surface,#1a1a1a);border:1px solid var(--border,#333);border-radius:10px;padding:24px;width:360px;max-width:95vw;position:relative">
        <button onclick="document.getElementById('hex-edit-modal').remove()" style="position:absolute;top:10px;right:12px;background:none;border:none;cursor:pointer;color:var(--t3,#888);font-size:1.1rem">✕</button>
        <div style="font-weight:700;font-size:1rem;margin-bottom:16px;color:var(--text,#e0d8c8)">Hex (${q}, ${r})</div>
        <div style="display:flex;flex-direction:column;gap:10px">
          <div>
            <label style="font-size:0.78rem;color:var(--t3,#888);display:block;margin-bottom:4px">Typ terenu (globalna zmiana)</label>
            <select id="hxe-type" class="form-input" style="width:100%">${typeOptions}</select>
          </div>
          <label style="display:flex;align-items:center;gap:8px;font-size:0.85rem;color:var(--t2,#b0a080)">
            <input type="checkbox" id="hxe-disc" ${hex.discovered?'checked':''}> Odkryty
          </label>
          <label style="display:flex;align-items:center;gap:8px;font-size:0.85rem;color:var(--t2,#b0a080)">
            <input type="checkbox" id="hxe-clear" ${hex.encounter_cleared?'checked':''}> Encounter oczyszczony
          </label>
          <div>
            <label style="font-size:0.78rem;color:var(--t3,#888);display:block;margin-bottom:4px">Etykieta kampanii</label>
            <input id="hxe-label" type="text" class="form-input" value="${_esc(hex.campaign_label||'')}" placeholder="np. Ruiny Starego Zamku" style="width:100%">
          </div>
          <div>
            <label style="font-size:0.78rem;color:var(--t3,#888);display:block;margin-bottom:4px">Notatki GM</label>
            <textarea id="hxe-notes" class="form-input" rows="2" style="width:100%;resize:vertical">${_esc(hex.campaign_notes||'')}</textarea>
          </div>
          <button id="hxe-save" class="btn btn-primary" style="margin-top:4px">Zapisz</button>
        </div>
      </div>
    `;
    document.body.appendChild(m);
    m.addEventListener('click', e => { if (e.target === m) m.remove(); });
    m.querySelector('#hxe-save').addEventListener('click', async () => {
      const newType = m.querySelector('#hxe-type').value;
      const payload = {
        discovered: m.querySelector('#hxe-disc').checked,
        encounter_cleared: m.querySelector('#hxe-clear').checked,
        campaign_label: m.querySelector('#hxe-label').value.trim() || null,
        campaign_notes: m.querySelector('#hxe-notes').value.trim() || null,
      };
      try {
        const promises = [
          apiFetch(`/api/admin/campaigns/${campId}/hex-map/${q}/${r}`, {method:'PATCH', body: JSON.stringify(payload)}),
        ];
        if (newType !== (hex.hex_type||'')) {
          promises.push(apiFetch(`/api/admin/world/hexes/${q}/${r}`, {method:'PATCH', body: JSON.stringify({hex_type: newType})}));
        }
        await Promise.all(promises);
        _showToast('Zapisano hex', 'success');
        m.remove();
      } catch(e) { _showToast(e.message, 'error'); }
    });
  }

// ══════════════════════════════════════════════════════════════
//  openCampaignModal
// ══════════════════════════════════════════════════════════════
  async function openCampaignModal(campId) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `<div class="modal-box" id="camp-modal-box" style="width:min(1100px,96vw);max-height:94vh;display:flex;flex-direction:column;transition:all 0.2s">
      <div class="modal-head">
        <span class="modal-title" id="camp-modal-title">Kampania #${campId}</span>
        <div style="display:flex;gap:6px;align-items:center">
          <button title="Pełny ekran" style="background:none;border:1px solid var(--border);border-radius:5px;padding:3px 7px;cursor:pointer;color:var(--t2);font-size:0.85rem" onclick="(function(btn){const box=document.getElementById('camp-modal-box');const isMax=box.dataset.max==='1';if(isMax){box.style.cssText='width:min(1100px,96vw);max-height:94vh;display:flex;flex-direction:column;transition:all 0.2s';box.dataset.max='0';btn.textContent='⛶';}else{box.style.cssText='position:fixed;inset:10px;width:auto;max-height:none;display:flex;flex-direction:column;transition:all 0.2s;border-radius:8px';box.dataset.max='1';btn.textContent='⊡';}})(this)">⛶</button>
          <button class="modal-close" onclick="if(window._inspectorTimer){clearInterval(window._inspectorTimer);window._inspectorTimer=null;}this.closest('.modal-overlay').remove()">✕</button>
        </div>
      </div>
      <div class="camp-modal-tabs" style="display:flex;gap:0;border-bottom:1px solid var(--border);padding:0 16px;flex-shrink:0;flex-wrap:wrap">
        ${['overview','plan','turns','dice','state','decisions','events','quests','map','npcs','workshop','world','inspector'].map((t,i) => `<button class="stab${i===0?' active':''}" data-ctab="${t}" style="border-radius:0;border-bottom:none;margin-bottom:-1px">${{overview:'Przegląd',plan:'Plan GM',turns:'Tury',dice:'🎲 Rzuty',state:'📊 Stan',decisions:'🧭 Decyzje',events:'🗓 Zdarzenia',quests:'🎯 Questy+XP',map:'Mapa',npcs:'👥 Znani NPC',workshop:'Warsztat',world:'🌍 Stan Świata',inspector:'🔍 Inspector'}[t]}</button>`).join('')}
      </div>
      <div class="modal-body" style="flex:1;overflow-y:auto;padding:0" id="camp-modal-body">
        <div id="ctab-overview" style="padding:16px"><div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div></div>
        <div id="ctab-plan"     style="padding:16px;display:none"></div>
        <div id="ctab-turns"    style="padding:0;display:none"></div>
        <div id="ctab-dice"     style="padding:0;display:none"></div>
        <div id="ctab-state"    style="padding:0;display:none"></div>
        <div id="ctab-decisions" style="padding:0;display:none"></div>
        <div id="ctab-events"   style="padding:0;display:none"></div>
        <div id="ctab-quests"   style="padding:0;display:none"></div>
        <div id="ctab-map"      style="padding:16px;display:none"></div>
        <div id="ctab-npcs"     style="padding:16px;display:none"></div>
        <div id="ctab-workshop" style="padding:16px;display:none;height:420px;display:none;flex-direction:column;gap:8px"></div>
        <div id="ctab-world"       style="padding:16px;display:none"></div>
        <div id="ctab-inspector"   style="padding:16px;display:none;font-family:monospace;font-size:0.8rem"></div>
      </div>
    </div>`;
    document.body.appendChild(overlay);

    overlay.querySelectorAll('[data-ctab]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (window._inspectorTimer) { clearInterval(window._inspectorTimer); window._inspectorTimer = null; }
        overlay.querySelectorAll('[data-ctab]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.ctab;
        overlay.querySelectorAll('[id^="ctab-"]').forEach(p => p.style.display = 'none');
        const panel = overlay.querySelector(`#ctab-${tab}`);
        if (panel) panel.style.display = tab === 'workshop' ? 'flex' : 'block';
        if (!panel.dataset.loaded) { panel.dataset.loaded = '1'; _loadCampTab(campId, tab, panel, overlay); }
      });
    });

    _loadCampTab(campId, 'overview', overlay.querySelector('#ctab-overview'), overlay);
  }

// ══════════════════════════════════════════════════════════════
//  _loadCampTab (overview / plan / turns / map / npcs / workshop / world / inspector)
// ══════════════════════════════════════════════════════════════
  async function _loadCampTab(campId, tab, panel, overlay) {
    if (tab === 'overview') {
      try {
        const d = await apiFetch(`/api/admin/campaigns/live`);
        const c = (d.items||[]).find(x => x.id === campId);
        if (!c) { panel.innerHTML = '<p style="color:var(--t3)">Nie znaleziono kampanii.</p>'; return; }
        overlay.querySelector('#camp-modal-title').textContent = `${c.title || 'Kampania'} #${campId}`;
        const archMap = { warrior:'Wojownik', scholar:'Uczony', rogue:'Złodziej', ranger:'Ranger' };
        const condArr = Array.isArray(c.char_conditions) ? c.char_conditions : (c.char_conditions ? [c.char_conditions] : []);
        panel.innerHTML = `
          <div class="camp-overview-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">
            <div class="info-grid">
              <div class="info-row"><span class="info-key">Postać</span><span class="info-val">${_esc(c.char_name||'—')}</span></div>
              <div class="info-row"><span class="info-key">Archetyp</span><span class="info-val">${_esc(archMap[c.char_archetype]||c.char_archetype||'—')}</span></div>
              <div class="info-row"><span class="info-key">Poziom</span><span class="info-val mono">${c.char_level??'—'}</span></div>
              <div class="info-row"><span class="info-key">Lokacja</span><span class="info-val">${_esc(c.char_location||'—')}</span></div>
              <div class="info-row"><span class="info-key">Tury</span><span class="info-val mono">${c.turn_count??'—'}</span></div>
              <div class="info-row"><span class="info-key">Gracz</span><span class="info-val">${_esc(c.owner_username||'—')}</span></div>
              <div class="info-row" id="tag-err-row-${campId}"><span class="info-key">Błędy tagów</span><span class="info-val td-muted">…</span></div>
            </div>
            <div>
              <div style="margin-bottom:8px">${_hp(c.char_current_hp, c.char_max_hp)}</div>
              ${c.char_id ? `<button class="btn btn-sm" data-hi-open-inspector style="width:100%;margin-bottom:8px" onclick="_campOpenInspector(${c.char_id})">🧍 Otwórz inspektora</button>` : ''}
              ${(c.char_id && c.char_current_hp != null && c.char_current_hp <= 0) ? `<button class="btn btn-primary btn-sm" style="width:100%;margin-bottom:8px" onclick="_campModalResurrect(${c.char_id},'${_esc(c.char_name||'Bohater')}',this)">✦ Wskrześ bohatera</button>` : ''}
              <div style="font-size:0.75rem;color:var(--t2);font-weight:600;margin-bottom:4px">Kondycje</div>
              <div style="display:flex;gap:4px;flex-wrap:wrap">${condArr.length ? condArr.map(cd => `<span class="badge badge-amber">${_esc(cd)}</span>`).join('') : '<span class="td-muted">Brak</span>'}</div>
              ${c.arc_title ? `<div style="margin-top:10px;font-size:0.75rem;color:var(--t2);font-weight:600">Aktywny arc</div><div style="font-size:0.82rem;color:var(--t1);margin-top:2px">${_esc(c.arc_title)}</div>` : ''}
              ${c.scene_total ? `<div style="font-size:0.75rem;color:var(--t3);margin-top:4px">Scena ${c.scene_current??'?'} / ${c.scene_total}</div>` : ''}
            </div>
          </div>
          ${c.last_turn_player ? `<div style="font-size:0.75rem;color:var(--t2);font-weight:600;margin-bottom:6px">Ostatnia tura</div>
            <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:10px 12px;font-size:0.8rem;color:var(--t2);margin-bottom:6px">${_esc((c.last_turn_player||'').slice(0,200))}</div>
            <div style="background:var(--blue-light);border:1px solid var(--blue-border);border-radius:var(--r);padding:10px 12px;font-size:0.8rem;color:var(--blue-text)">${_esc((c.last_turn_gm||'').slice(0,300))}</div>` : ''}
          ${c.char_id ? `<div style="margin-top:14px;border-top:1px solid var(--border);padding-top:12px">
            <div style="font-size:0.72rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">⚡ Admin Komendy</div>
            <div style="position:relative">
              <div style="display:flex;gap:6px">
                <input id="camp-cmd-input-${campId}" type="text" class="field-input" autocomplete="off"
                  style="flex:1;font-family:monospace;font-size:0.82rem;padding:4px 8px"
                  placeholder="/debug set-hp 50 · /heal max · /gold 100 · /level 5"
                  oninput="_campCmdSuggest(${campId},this)"
                  onkeydown="_campCmdKey(event,${c.char_id},${campId})" />
                <button class="btn btn-sm btn-secondary" style="white-space:nowrap" onclick="_campCmd(${c.char_id},${campId},this)">▶ Wyślij</button>
              </div>
              <div id="camp-cmd-suggest-${campId}" style="display:none;position:absolute;left:0;right:48px;top:100%;z-index:200;background:var(--card-bg,#1a1a2e);border:1px solid var(--border);border-radius:6px;box-shadow:0 6px 24px rgba(0,0,0,0.5);max-height:240px;overflow-y:auto;margin-top:2px"></div>
            </div>
            <div id="camp-cmd-result-${campId}" style="font-size:0.75rem;margin-top:6px;min-height:18px;font-family:monospace"></div>
          </div>` : ''}`;
        // U5 (#528): async-fetch tag error count badge
        apiFetch(`/api/admin/campaigns/${campId}/tag-error-count`).then(ter => {
          const row = document.getElementById(`tag-err-row-${campId}`);
          if (!row) return;
          const cnt = ter.tag_error_count ?? 0;
          const badge = cnt > 0
            ? `<span class="badge badge-amber" title="Błędy tagów LLM w tej kampanii">${cnt}</span>`
            : `<span class="td-muted">0</span>`;
          row.querySelector('.info-val').innerHTML = badge;
        }).catch(() => {});
      } catch(e) { panel.innerHTML = `<p style="color:var(--red)">${_esc(e.message)}</p>`; }
    }

    else if (tab === 'plan') {
      panel.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>';
      try {
        const d = await apiFetch(`/api/admin/campaigns/${campId}/gm-plan`);
        const plan = typeof d.gm_plan_json === 'string' ? JSON.parse(d.gm_plan_json) : d.gm_plan_json;

        // U8 #532: Story Gravity badge
        const sg = d.story_gravity || {};
        const gravityColors = {0:'var(--t3)',1:'#e6b800',2:'#e07a20',3:'#c0392b'};
        const gravityLabels = {0:'',1:'🟡 Gravity L1',2:'🟠 Gravity L2',3:'🔴 Gravity L3'};
        const gravityBadge = sg.level > 0
          ? `<div style="margin-bottom:12px;padding:8px 12px;border-radius:var(--r);border:1px solid ${gravityColors[sg.level]};background:${gravityColors[sg.level]}22;display:flex;align-items:center;gap:10px">
               <span style="font-weight:700;color:${gravityColors[sg.level]}">${gravityLabels[sg.level]}</span>
               <span style="font-size:0.78rem;color:var(--t2)">${sg.turns_since_beat} tur bez zaliczonego beatu</span>
               ${sg.hint ? `<span style="font-size:0.72rem;color:var(--t3);font-style:italic;margin-left:auto">${_esc(sg.hint)}</span>` : ''}
             </div>`
          : '';

        // #966: degraded-plan banner — weak LLM fell back to a stub plan.
        const degradedBanner = d.plan_degraded
          ? `<div style="margin-bottom:12px;padding:8px 12px;border-radius:var(--r);border:1px solid #f59e0b;background:#f59e0b22;display:flex;align-items:center;gap:10px">
               <span style="font-weight:700;color:#f59e0b">⚠ Plan uproszczony</span>
               <span style="font-size:0.78rem;color:var(--t2)">LLM nie wygenerował pełnego planu MG — użyto planu zapasowego.</span>
               <button class="btn btn-sm btn-primary" style="margin-left:auto" onclick="regenerateCampPlan(${campId}, this)">♻ Regeneruj plan MG</button>
             </div>`
          : '';

        const arcs = plan?.arcs || {};
        const arcList = typeof arcs === 'object' && !Array.isArray(arcs) ? Object.values(arcs) : (Array.isArray(arcs) ? arcs : []);
        if (!arcList.length) {
          // #966: campaign with no plan at all — offer to generate one (needs a hero).
          panel.innerHTML = gravityBadge + degradedBanner +
            `<div style="text-align:center;padding:24px;color:var(--t3)">
               <p style="margin:0 0 14px">Brak planu GM.</p>
               <button class="btn btn-sm btn-primary" onclick="regenerateCampPlan(${campId}, this)">♻ Wygeneruj plan MG</button>
               <p style="font-size:0.72rem;margin:10px 0 0">Wymaga bohatera w kampanii (kontekst postaci).</p>
             </div>`;
          return;
        }
        const activeArcId = plan?.active_arc_id;
        panel.innerHTML = gravityBadge + degradedBanner + arcList.map((arc, arcIdx) => {
          const isActive = arc.status === 'active' || arc.id === activeArcId;
          const currentScene = typeof arc.current_scene_ordinal === 'number' ? arc.current_scene_ordinal : null;
          const goals = arc.scene_goals || [];
          const hooksForScene = arc.hooks || [];
          const scenesHtml = goals.length ? `
            <div style="font-size:0.75rem;color:var(--t3);margin-bottom:6px;font-weight:600;text-transform:uppercase;letter-spacing:.05em">Sceny (${goals.length})</div>
            <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:10px">
              ${goals.map((g, si) => {
                const isCurrent = currentScene !== null && si === currentScene;
                const isDone = currentScene !== null && si < currentScene;
                const goalText = typeof g === 'string' ? g : (g?.goal || g?.description || JSON.stringify(g));
                const extraHtml = isCurrent && hooksForScene.length ? `
                  <div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(var(--accent-rgb,100,160,255),.2)">
                    <div style="font-size:0.72rem;color:var(--accent,#64a0ff);font-weight:600;margin-bottom:4px">Hooki sceny</div>
                    <div style="display:flex;gap:4px;flex-wrap:wrap">${hooksForScene.slice(0,8).map(h=>`<span class="badge badge-slate">${_esc(typeof h==='string'?h:(h.label||h.name||JSON.stringify(h)).slice(0,40))}</span>`).join('')}</div>
                  </div>` : '';
                return `<details open style="border-radius:var(--r);border:1px solid ${isCurrent?'rgba(var(--accent-rgb,100,160,255),.45)':'var(--border)'};background:${isCurrent?'rgba(var(--accent-rgb,100,160,255),.08)':isDone?'var(--surface)':'transparent'};opacity:${isDone?'0.6':'1'}">
                  <summary style="display:flex;align-items:center;gap:8px;padding:7px 10px;cursor:pointer;list-style:none;outline:none">
                    <span style="font-size:0.72rem;font-weight:700;color:${isCurrent?'var(--accent,#64a0ff)':'var(--t3)'};min-width:18px;flex-shrink:0">${isDone?'✓':(isCurrent?'▶':String(si+1))}</span>
                    <span style="font-size:0.78rem;color:var(--t3)">Scena ${si+1}</span>
                  </summary>
                  <div style="padding:6px 10px 10px 36px">
                    <p style="font-size:0.82rem;font-weight:${isCurrent?'600':'400'};color:${isCurrent?'var(--t1)':isDone?'var(--t3)':'var(--t2)'};margin:0 0 ${extraHtml?'8px':'0'}">${_esc(goalText)}</p>
                    ${extraHtml}
                  </div>
                </details>`;
              }).join('')}
            </div>` : '';
          const hooksHtml = arc.hooks?.length && currentScene === null ? `
            <div style="font-size:0.75rem;color:var(--t3);margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:.05em">Hooki</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px">${arc.hooks.slice(0,12).map(h=>`<span class="badge badge-slate">${_esc(typeof h==='string'?h:(h.label||h.name||JSON.stringify(h)).slice(0,40))}</span>`).join('')}</div>` : '';
          const roadmapHtml = arc.roadmap ? `
            <div style="font-size:0.75rem;color:var(--t3);margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:.05em">Roadmapa</div>
            <p style="font-size:0.8rem;color:var(--t2);margin:0 0 10px;background:var(--surface);padding:8px;border-radius:var(--r)">${_esc(arc.roadmap)}</p>` : '';
          return `<div style="margin-bottom:14px;border:1px solid ${isActive?'rgba(var(--accent-rgb,100,160,255),.4)':'var(--border)'};border-radius:var(--r);overflow:hidden">
            <div style="background:var(--surface);padding:10px 14px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border)">
              <span style="font-weight:700;font-size:0.88rem;color:var(--t1)">${_esc(arc.title||arc.id||`Akt ${arcIdx+1}`)}</span>
              <div style="display:flex;align-items:center;gap:6px">
                ${currentScene !== null ? `<span style="font-size:0.72rem;color:var(--t3)">Scena ${currentScene+1}/${goals.length}</span>` : ''}
                <span class="badge ${isActive?'badge-green':'badge-slate'}">${isActive?'● Aktywny':'○ Nieaktywny'}</span>
              </div>
            </div>
            <div style="padding:12px 14px">${roadmapHtml}${scenesHtml}${hooksHtml}</div>
          </div>`;
        }).join('') +
          `<div style="display:flex;gap:8px;justify-content:flex-end;padding-top:8px">
            <button class="btn btn-sm btn-secondary" onclick="regenerateCampPlan(${campId}, this)">♻ Regeneruj plan MG</button>
            <button class="btn btn-sm btn-secondary" onclick="advanceCampScene(${campId}, this)">➡ Następna scena</button>
          </div>`;
      } catch(e) { panel.innerHTML = `<p style="color:var(--red)">${_esc(e.message)}</p>`; }
    }

    else if (tab === 'turns') {
      panel.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>';
      try {
        const d = await apiFetch(`/api/admin/campaigns/${campId}/turns?limit=20`);
        const items = d.items || [];
        if (!items.length) { panel.innerHTML = '<p style="text-align:center;padding:24px;color:var(--t3)">Brak tur.</p>'; return; }

        const renderTurns = (debug) => {
          let _cid = 0;
          const _clamp = (text, lines=5) => {
            if (!text) return '';
            if (text.length <= 150) return _esc(text);
            const id = 'tx953_' + (++_cid);
            const maxH = (lines * 1.6) + 'em';
            return `<div id="${id}" style="overflow:hidden;max-height:${maxH}">${_esc(text)}</div>` +
              `<button onclick="var e=document.getElementById('${id}');if(e.style.maxHeight){e.style.maxHeight='';this.textContent='Zwiń';}else{e.style.maxHeight='${maxH}';this.textContent='Rozwiń';}" style="font-size:0.7rem;color:var(--amber);background:none;border:none;cursor:pointer;padding:2px 0 0;display:block">Rozwiń</button>`;
          };
          return `<div style="padding:0">
            <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 16px;border-bottom:1px solid var(--border);background:var(--surface)">
              <span style="font-size:0.75rem;color:var(--t3)">Ostatnie ${items.length} tur</span>
              <label style="display:flex;align-items:center;gap:6px;font-size:0.75rem;color:var(--t2);cursor:pointer">
                <input type="checkbox" id="turns-debug-toggle" ${debug?'checked':''} style="cursor:pointer"> 🔍 Raw debug
              </label>
            </div>
            ${items.map(t => {
              let narrative = '', parsed = null, tags = [], extraFields = {};
              try {
                parsed = JSON.parse(t.assistant_text || '{}');
                narrative = parsed.narrative || '';
                delete parsed.narrative;
                // Collect interesting non-null fields
                for (const [k,v] of Object.entries(parsed)) {
                  if (v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && !v.length)) {
                    extraFields[k] = v;
                  }
                }
              } catch(e) {
                narrative = (t.assistant_text||'').replace(/\{[\s\S]*\}/,'').trim();
              }
              // Extract tags from raw text
              const rawTags = [...(t.assistant_text||'').matchAll(/\[([A-Z_]+:[^\]]*)\]/g)].map(m=>m[0]);
              const routeBadgeColor = {narrative:'badge-slate',combat:'badge-red',skill_test:'badge-amber',skill_test_keyword:'badge-amber',structured:'badge-green'}[t.route]||'badge-slate';

              if (debug) {
                return `<div style="border-bottom:1px solid var(--border);padding:10px 16px">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                    <span class="badge ${routeBadgeColor}">T${t.turn_number||t.id} · ${_esc(t.route||'?')}</span>
                    <span style="font-size:0.72rem;color:var(--t3)">${_timeAgo(t.created_at)}</span>
                  </div>
                  <div style="background:var(--surface);border-radius:4px;padding:6px 10px;font-size:0.78rem;color:var(--amber);margin-bottom:4px">👤 ${_clamp(t.user_text||'')}</div>
                  ${narrative ? `<div style="font-size:0.78rem;color:var(--t2);margin-bottom:4px;padding:6px 10px;background:var(--surface);border-radius:4px;border-left:2px solid var(--t3)">📖 ${_clamp(narrative)}</div>` : ''}
                  ${rawTags.length ? `<div style="margin-bottom:4px;display:flex;flex-wrap:wrap;gap:4px">${rawTags.map(tag=>`<code style="font-size:0.7rem;background:#1a1a2e;color:#7eb8f7;padding:2px 6px;border-radius:3px">${_esc(tag)}</code>`).join('')}</div>` : ''}
                  ${Object.keys(extraFields).length ? `<details style="margin-top:4px"><summary style="font-size:0.72rem;color:var(--t3);cursor:pointer">JSON fields (${Object.keys(extraFields).length})</summary><pre style="font-size:0.7rem;color:var(--t2);background:#0d0d1a;border-radius:4px;padding:8px;overflow-x:auto;margin-top:4px;max-height:200px;overflow-y:auto">${_esc(JSON.stringify(extraFields,null,2))}</pre></details>` : ''}
                </div>`;
              } else {
                return `<div style="border-bottom:1px solid var(--border);padding:10px 16px">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                    <span class="badge ${routeBadgeColor}">T${t.turn_number||t.id} · ${_esc(t.route||'?')}</span>
                    <span style="font-size:0.72rem;color:var(--t3)">${_timeAgo(t.created_at)}</span>
                  </div>
                  <div style="background:var(--surface);border-radius:4px;padding:6px 10px;font-size:0.8rem;color:var(--t2);margin-bottom:6px">${_clamp(t.user_text||'')}</div>
                  <div style="font-size:0.78rem;color:var(--t3)">${_clamp(narrative)}</div>
                  ${rawTags.length ? `<div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:3px">${rawTags.map(tag=>`<code style="font-size:0.68rem;background:var(--surface);color:var(--t3);padding:1px 5px;border-radius:3px">${_esc(tag)}</code>`).join('')}</div>` : ''}
                </div>`;
              }
            }).join('')}
          </div>`;
        };

        let _turnsDebug = false;
        const reRender = () => {
          panel.innerHTML = renderTurns(_turnsDebug);
          panel.querySelector('#turns-debug-toggle').addEventListener('change', e => {
            _turnsDebug = e.target.checked;
            reRender();
          });
        };
        reRender();
      } catch(e) { panel.innerHTML = `<p style="color:var(--red);padding:16px">${_esc(e.message)}</p>`; }
    }

    else if (tab === 'map') {
      panel.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>';
      try {
        const d = await apiFetch(`/api/admin/campaigns/${campId}/hex-map`);
        const hexes = d.hexes || [];
        const hexTypes = d.hex_types || {};
        const currentHex = d.current_hex || null;
        const overlay_hexes = hexes.filter(h => h.has_overlay || h.discovered || h.campaign_label);
        const svgHtml = _renderAdminHexMap(hexes, hexTypes, currentHex);
        panel.innerHTML = `
          <div style="font-size:0.78rem;color:var(--t3);margin-bottom:8px">${hexes.length} heksów · ${overlay_hexes.length} z nakładką · <span style="color:var(--t3)">Kliknij hex aby edytować</span></div>
          ${svgHtml}
          <div style="margin-top:8px;font-size:0.72rem;color:var(--t3);display:flex;gap:16px;flex-wrap:wrap">
            <span><span style="display:inline-block;width:10px;height:10px;background:#f0c040;border-radius:50%;margin-right:4px"></span>Aktualna pozycja</span>
            <span><span style="display:inline-block;width:10px;height:10px;border:1px solid #4a8a4a;border-radius:50%;margin-right:4px"></span>Odkryty</span>
            <span><span style="display:inline-block;width:10px;height:10px;background:#8af;border-radius:50%;margin-right:4px"></span>Ma etykietę</span>
          </div>`;
        const hexData = {};
        hexes.forEach(h => { hexData[`${h.q},${h.r}`] = h; });
        const svgWrap = panel.querySelector('#admin-hex-map-svg-wrap');
        if (svgWrap) {
          // Desktop click to edit
          svgWrap.addEventListener('click', e => {
            const g = e.target.closest('g[data-q]');
            if (!g) return;
            const q = parseInt(g.dataset.q), r = parseInt(g.dataset.r);
            _showHexEditModal({ campId, q, r, hex: hexData[`${q},${r}`] || {} });
          });
          // Touch: pinch-zoom + 1-finger pan + tap-to-edit (M5)
          const svgEl = svgWrap.querySelector('svg');
          if (svgEl && ('ontouchstart' in window || navigator.maxTouchPoints > 0)) {
            svgWrap.style.overflow = 'hidden';
            svgWrap.style.touchAction = 'none';
            svgEl.style.transformOrigin = '0 0';
            let camZ = 1, camX = 0, camY = 0, camTs = null;
            const applyT = () => { svgEl.style.transform = `translate(${camX}px,${camY}px) scale(${camZ})`; };
            svgWrap.addEventListener('touchstart', (e) => {
              e.preventDefault();
              if (e.touches.length === 1) {
                camTs = { type: 'pan', x: e.touches[0].clientX, y: e.touches[0].clientY,
                  px: camX, py: camY, moved: false };
              } else if (e.touches.length === 2) {
                const dx = e.touches[1].clientX - e.touches[0].clientX;
                const dy = e.touches[1].clientY - e.touches[0].clientY;
                const rect = svgWrap.getBoundingClientRect();
                camTs = { type: 'pinch', dist: Math.hypot(dx, dy), zoom: camZ, px: camX, py: camY,
                  midX: (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left,
                  midY: (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top };
              }
            }, { passive: false });
            svgWrap.addEventListener('touchmove', (e) => {
              e.preventDefault();
              if (!camTs) return;
              if (camTs.type === 'pan' && e.touches.length === 1) {
                const dx = e.touches[0].clientX - camTs.x;
                const dy = e.touches[0].clientY - camTs.y;
                if (Math.abs(dx) > 3 || Math.abs(dy) > 3) camTs.moved = true;
                camX = camTs.px + dx; camY = camTs.py + dy; applyT();
              } else if (camTs.type === 'pinch' && e.touches.length === 2) {
                const dx = e.touches[1].clientX - e.touches[0].clientX;
                const dy = e.touches[1].clientY - e.touches[0].clientY;
                const nz = Math.max(0.3, Math.min(6, camTs.zoom * (Math.hypot(dx, dy) / camTs.dist)));
                camX = camTs.midX - (camTs.midX - camTs.px) * (nz / camTs.zoom);
                camY = camTs.midY - (camTs.midY - camTs.py) * (nz / camTs.zoom);
                camZ = nz; applyT();
              }
            }, { passive: false });
            svgWrap.addEventListener('touchend', (e) => {
              if (camTs?.type === 'pan' && !camTs.moved) {
                const t = e.changedTouches[0];
                const el = document.elementFromPoint(t.clientX, t.clientY);
                const g = el?.closest('g[data-q]');
                if (g) {
                  const q = parseInt(g.dataset.q), r = parseInt(g.dataset.r);
                  _showHexEditModal({ campId, q, r, hex: hexData[`${q},${r}`] || {} });
                }
              }
              camTs = null;
            });
          }
        }
      } catch(e) { panel.innerHTML = `<p style="color:var(--red)">${_esc(e.message)}</p>`; }
    }

    else if (tab === 'npcs') {
      try {
        const d = await apiFetch(`/api/admin/campaigns/${campId}/known-npcs`);
        const npcs = d.npcs || d.items || [];
        if (!npcs.length) { panel.innerHTML = '<div style="color:var(--t3);padding:20px;text-align:center">Postać nie spotkała jeszcze żadnych NPC.</div>'; return; }
        const dispMap = { friendly:['Przyjazny','badge-green'], hostile:['Wrogi','badge-red'], neutral:['Neutralny','badge-amber'] };
        panel.innerHTML = `<div style="display:flex;flex-direction:column;gap:8px">
          ${npcs.map(n => {
            const dispKey = n.is_ally ? 'friendly' : (n.npc_type==='hostile' ? 'hostile' : 'neutral');
            const [dispLabel, dispCls] = dispMap[dispKey];
            const loc = Array.isArray(n.location_keys) ? n.location_keys.join(', ') : (n.location_keys||'—');
            return `<div class="card" style="padding:10px">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
                <div>
                  <div style="font-weight:600">${_esc(n.label||n.key||'(bez imienia)')}</div>
                  <div style="font-size:0.72rem;color:var(--t3);margin-top:2px">${_esc(loc)} · ${_esc(n.npc_type||'—')}</div>
                </div>
                <span class="badge ${dispCls}">${dispLabel}</span>
              </div>
              ${n.description ? `<div style="font-size:0.78rem;color:var(--t2);margin-top:6px">${_esc(n.description.slice(0,200))}${n.description.length>200?'…':''}</div>` : ''}
              ${n.last_interaction ? `<div style="font-size:0.7rem;color:var(--t3);margin-top:4px">Ostatnia interakcja: ${_esc(_timeAgo(n.last_interaction))}</div>` : ''}
            </div>`;
          }).join('')}
        </div>`;
      } catch(e) { panel.innerHTML = `<p style="color:var(--red)">${_esc(e.message)}</p>`; }
    }

    else if (tab === 'workshop') {
      panel.style.display = 'flex';
      panel.style.flexDirection = 'column';
      panel.style.gap = '8px';
      panel.style.padding = '16px';
      panel.innerHTML = `
        <div id="workshop-history" style="flex:1;overflow-y:auto;border:1px solid var(--border);border-radius:var(--r);padding:10px;min-height:140px;background:var(--surface);font-size:0.82rem;color:var(--t2)">
          <em style="color:var(--t3)">Napisz wiadomość, żeby porozmawiać z AI o tej kampanii.</em>
        </div>
        <div style="display:flex;gap:8px">
          <textarea class="form-input" id="workshop-input" rows="2" placeholder="Opisz zmianę w planie GM lub zapytaj o kampanię…" style="flex:1;resize:none"></textarea>
          <button class="btn btn-primary" id="workshop-send-btn" onclick="sendWorkshopMsg(${campId}, this)">Wyślij</button>
        </div>
        <div style="border-top:1px solid var(--border);padding-top:12px;margin-top:4px">
          <div style="font-size:0.78rem;font-weight:600;color:var(--t2);margin-bottom:8px;letter-spacing:0.04em">⚡ WSTRZYKNIJ SPOTKANIE</div>
          <div style="font-size:0.75rem;color:var(--t3);margin-bottom:8px">Wybierz spotkanie — zostanie użyte w następnej turze gracza.</div>
          <div id="workshop-encounter-list" style="display:flex;flex-direction:column;gap:6px;max-height:200px;overflow-y:auto">
            <em style="font-size:0.75rem;color:var(--t3)">Ładowanie spotkań…</em>
          </div>
        </div>`;
      _loadWorkshopEncounters(campId);
    }
    else if (tab === 'world') {
      panel.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>';
      try {
        const d = await apiFetch(`/api/admin/campaigns/${campId}/world-state`);
        const snaps = d.snapshots || [];
        if (!snaps.length) {
          panel.innerHTML = '<div style="padding:24px;text-align:center;color:var(--t3)">Brak snapshotów — graj kilka tur żeby zbudować historię.</div>';
          return;
        }
        const latest = snaps[0];
        const _ws = (s) => {
          const j = s.snapshot_json || {};
          const enemies = (j.scene_enemies||[]);
          const npcs = (j.scene_npcs||[]);
          const quests = (j.active_quests||[]);
          const conds = (j.player_conditions||[]);
          // D6 (#381) — Narrative State (events + active seeds)
          const ns = j.narrative_state || {};
          const nsEvents = (ns.events||[]);
          const nsSeeds = (ns.seeds||[]).filter(x=>(x.status||'active')==='active');
          const nsBlock = (nsEvents.length||nsSeeds.length) ? `
            <div style="margin-top:10px;border-top:1px solid var(--border);padding-top:8px;font-size:0.78rem">
              <div style="font-weight:600;color:var(--t2);margin-bottom:4px">📖 Narrative State</div>
              ${nsEvents.length ? `<div style="color:var(--t3);margin-bottom:2px">Zdarzenia (${nsEvents.length}):</div>${nsEvents.map(e=>`<div style="padding:1px 0">• ${_esc(e.note||e.key||'?')} <span style="color:var(--t3)">(t${e.turn??'?'})</span></div>`).join('')}` : ''}
              ${nsSeeds.length ? `<div style="color:var(--t3);margin:4px 0 2px">Zasiane wątki (${nsSeeds.length}):</div>${nsSeeds.map(x=>`<div style="padding:1px 0">• ${_esc(x.hint||x.key||'?')}</div>`).join('')}` : ''}
            </div>` : '';
          return `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:0.8rem">
              <div>
                <div style="font-weight:600;color:var(--t2);margin-bottom:4px">⚔ Wrogowie (${enemies.length})</div>
                ${enemies.length ? enemies.map(e=>`<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--border)"><span>${_esc(e.name||e.key||'?')}</span><span class="td-mono" style="color:${(e.hp||0)<=0?'var(--red)':'var(--green)'}">HP ${e.hp??'?'}</span></div>`).join('') : '<span style="color:var(--t3)">Brak</span>'}
              </div>
              <div>
                <div style="font-weight:600;color:var(--t2);margin-bottom:4px">👥 NPC (${npcs.length})</div>
                ${npcs.length ? npcs.map(n=>`<div style="padding:2px 0;border-bottom:1px solid var(--border)">${_esc(n.name||n.key||'?')}</div>`).join('') : '<span style="color:var(--t3)">Brak</span>'}
              </div>
              <div>
                <div style="font-weight:600;color:var(--t2);margin-bottom:4px">📋 Questy (${quests.length})</div>
                ${quests.length ? quests.map(q=>{const t=typeof q==='string'?q:(q.title||q.key||'?');const obj=typeof q==='object'&&q.objective?q.objective:'';const rwd=typeof q==='object'&&q.reward?q.reward:'';return`<div style="padding:4px 0;border-bottom:1px solid var(--border)"><div style="font-weight:500">${_esc(t)}</div>${obj?`<div style="font-size:0.75rem;color:var(--t2);margin-top:1px">${_esc(obj)}</div>`:''}${rwd?`<div style="font-size:0.72rem;color:var(--t3)">Nagroda: ${_esc(rwd)}</div>`:''}</div>`;}).join('') : '<span style="color:var(--t3)">Brak</span>'}
              </div>
              <div>
                <div style="font-weight:600;color:var(--t2);margin-bottom:4px">💊 Kondycje (${conds.length})</div>
                <div style="display:flex;flex-wrap:wrap;gap:4px">${conds.length ? conds.map(c=>`<span class="badge badge-amber">${_esc(typeof c==='string'?c:c.key||JSON.stringify(c))}</span>`).join('') : '<span style="color:var(--t3)">Brak</span>'}</div>
              </div>
            </div>${nsBlock}`;
        };
        panel.innerHTML = `
          <div style="margin-bottom:14px">
            <div style="font-size:0.75rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Aktualny stan (tura ${latest.turn_number})</div>
            <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:12px">
              ${_ws(latest)}
            </div>
          </div>
          <div style="font-size:0.75rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Historia (${snaps.length} snapshotów)</div>
          <div style="display:flex;flex-direction:column;gap:6px">
            ${snaps.slice(1).map(s=>`
              <details style="border:1px solid var(--border);border-radius:var(--r)">
                <summary style="padding:8px 12px;cursor:pointer;font-size:0.82rem;display:flex;justify-content:space-between;align-items:center">
                  <span>Tura <strong>${s.turn_number}</strong> — <span style="color:var(--t3)">${s.snapshot_source||'auto'}</span></span>
                  <span style="font-size:0.72rem;color:var(--t3)">${(s.created_at||'').slice(0,16).replace('T',' ')}</span>
                </summary>
                <div style="padding:10px 12px;border-top:1px solid var(--border)">${_ws(s)}</div>
              </details>`).join('')}
          </div>`;
      } catch(e) {
        panel.innerHTML = `<div style="padding:16px;color:var(--red)">Błąd ładowania: ${_esc(String(e))}</div>`;
      }
    }

    else if (tab === 'inspector') {
      panel.innerHTML = `<div style="color:var(--t3);padding:8px 0">Ładowanie stanu…</div>`;
      const _renderInspector = async () => {
        if (!document.body.contains(panel)) {
          clearInterval(window._inspectorTimer); window._inspectorTimer = null; return;
        }
        try {
          const d = await apiFetch(`/api/debug/campaigns/${campId}/state`);
          const intent = d.intent || {};
          const ws = d.world_state || {};
          const gr = d.gate_result || {};
          const blocked = gr.blocked === true;
          const enemies = (ws.scene_enemies || []);
          const aliveEnemies = enemies.filter(e => (e.hp || 0) > 0);
          panel.innerHTML = `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">
              <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:10px">
                <div style="font-size:0.7rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">🧠 Intent</div>
                ${d.intent === null ? `<span style="color:var(--t3)">Brak tur</span>` : `
                  <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
                    <span style="background:var(--blue-light);color:var(--blue-text);border:1px solid var(--blue-border);border-radius:4px;padding:2px 8px;font-size:0.82rem;font-weight:700">${_esc(intent.action_type||'?')}</span>
                    <span style="color:var(--t3);font-size:0.75rem">conf: ${((intent.confidence||0)*100).toFixed(0)}%</span>
                  </div>
                  ${intent.target ? `<div style="color:var(--t2);font-size:0.75rem">target: <span style="color:var(--t1)">${_esc(intent.target)}</span></div>` : ''}
                  <div style="margin-top:4px;padding:4px 6px;background:rgba(0,0,0,.2);border-radius:4px;color:var(--t2);font-size:0.75rem;word-break:break-word">"${_esc((intent.raw_input||'').slice(0,120))}"</div>
                `}
              </div>
              <div style="background:var(--surface);border:1px solid ${blocked?'var(--red)':'var(--green)'};border-radius:var(--r);padding:10px">
                <div style="font-size:0.7rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">🚦 Gate</div>
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
                  <span style="background:${blocked?'var(--red)':'var(--green)'};color:#fff;border-radius:4px;padding:2px 8px;font-size:0.82rem;font-weight:700">${blocked?'BLOCKED':'PASS'}</span>
                  ${gr.reason ? `<span style="color:var(--t3);font-size:0.75rem">${_esc(gr.reason)}</span>` : ''}
                </div>
                ${gr.feedback ? `<div style="color:var(--t2);font-size:0.75rem;margin-top:2px">${_esc(gr.feedback)}</div>` : ''}
              </div>
            </div>
            <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:10px">
              <div style="font-size:0.7rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">🌍 World State <span style="font-weight:400;color:var(--t3)">${ws.scene_cleared?'✓ cleared':aliveEnemies.length+' alive enemies'}</span></div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.78rem">
                <div><span style="color:var(--t3)">Enemies:</span> ${enemies.length ? enemies.map(e=>`<span style="color:${(e.hp||0)<=0?'var(--red)':'var(--green)'}">${_esc(e.name||e.key||'?')}(${e.hp??'?'}hp)</span>`).join(', ') : '<span style="color:var(--t3)">—</span>'}</div>
                <div><span style="color:var(--t3)">NPCs:</span> ${(ws.scene_npcs||[]).length ? (ws.scene_npcs||[]).map(n=>`<span>${_esc(n.name||n.key||'?')}</span>`).join(', ') : '<span style="color:var(--t3)">—</span>'}</div>
                <div><span style="color:var(--t3)">Quests:</span> ${(ws.active_quests||[]).length ? (ws.active_quests||[]).map(q=>`<span>${_esc(typeof q==='string'?q:q.title||q.key||'?')}</span>`).join(', ') : '<span style="color:var(--t3)">—</span>'}</div>
                <div><span style="color:var(--t3)">Conds:</span> ${(ws.player_conditions||[]).length ? (ws.player_conditions||[]).map(c=>`<span class="badge badge-amber">${_esc(typeof c==='string'?c:c.key||'?')}</span>`).join('') : '<span style="color:var(--t3)">—</span>'}</div>
              </div>
            </div>
            ${(() => {
              const ns = d.narrative_state || {};
              const nsEvents = (ns.events||[]);
              const nsSeeds = (ns.seeds||[]).filter(x=>(x.status||'active')==='active');
              if (!nsEvents.length && !nsSeeds.length) return '';
              return `<div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:10px;margin-top:10px">
                <div style="font-size:0.7rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">📖 Narrative State</div>
                <div style="font-size:0.78rem">
                  ${nsEvents.length ? `<div style="color:var(--t3);margin-bottom:2px">Zdarzenia (${nsEvents.length}):</div>${nsEvents.map(e=>`<div style="padding:1px 0">• ${_esc(e.note||e.key||'?')} <span style="color:var(--t3)">(t${e.turn??'?'})</span></div>`).join('')}` : ''}
                  ${nsSeeds.length ? `<div style="color:var(--t3);margin:4px 0 2px">Zasiane wątki (${nsSeeds.length}):</div>${nsSeeds.map(x=>`<div style="padding:1px 0">• ${_esc(x.hint||x.key||'?')}</div>`).join('')}` : ''}
                </div>
              </div>`;
            })()}
            <div style="margin-top:6px;font-size:0.7rem;color:var(--t3);text-align:right">Polling co 1s · ${new Date().toLocaleTimeString()}</div>`;
        } catch(e) {
          if (document.body.contains(panel)) panel.innerHTML = `<div style="color:var(--red);padding:8px">Błąd: ${_esc(String(e))}</div>`;
        }
      };
      await _renderInspector();
      if (window._inspectorTimer) clearInterval(window._inspectorTimer);
      window._inspectorTimer = setInterval(_renderInspector, 1000);
    }

    else if (tab === 'dice') {
      // #754: strukturalny rejestr rzutów kostką tej kampanii.
      panel.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>';
      const TYPE_LABEL = {
        attack_player:'⚔ Atak gracza', attack_enemy:'👹 Atak wroga', skill_test:'🎯 Test skilla',
        dodge:'💨 Unik', shield_block:'🛡 Blok', damage:'💥 Obrażenia', save:'✨ Save',
        loot:'📦 Łup', gold:'🪙 Złoto',
      };
      const OUT_COLOR = (o) => {
        o = (o||'').toLowerCase();
        if (o.includes('crit_success')||o==='success'||o==='hit'||o==='dodged'||o==='blocked'||o==='drop') return 'var(--green)';
        if (o.includes('crit_fail')||o==='fail'||o==='miss') return 'var(--red)';
        return 'var(--t2)';
      };
      const _render = async (filter) => {
        try {
          const qs = filter ? `?roll_type=${encodeURIComponent(filter)}&limit=200` : '?limit=200';
          const d = await apiFetch(`/api/campaigns/${campId}/dice-rolls${qs}`);
          const rolls = d.dice_rolls || [];
          const types = ['', ...Object.keys(TYPE_LABEL)];
          const bar = `<div style="display:flex;gap:6px;flex-wrap:wrap;padding:8px 16px;border-bottom:1px solid var(--border);background:var(--surface)">
            ${types.map(t => `<button class="btn btn-sm dice-filter${(t===(filter||''))?' btn-primary':''}" data-dtype="${t}" style="font-size:0.72rem;padding:2px 8px">${t?TYPE_LABEL[t]:'Wszystkie'}</button>`).join('')}
            <span style="margin-left:auto;font-size:0.72rem;color:var(--t3);align-self:center">${rolls.length} rzutów</span>
          </div>`;
          const body = !rolls.length
            ? '<p style="text-align:center;padding:24px;color:var(--t3)">Brak rzutów. Zagraj turę / walkę, by zarejestrować rzuty.</p>'
            : `<table class="data-table" style="width:100%;font-size:0.78rem">
                <thead><tr>
                  <th style="text-align:left">Typ</th><th>Rzut</th><th>Mod</th><th>Suma</th>
                  <th>DC</th><th style="text-align:left">Wynik</th><th style="text-align:left">Szczegóły</th>
                </tr></thead>
                <tbody>${rolls.map(r => {
                  const raw = Array.isArray(r.raw_rolls) ? r.raw_rolls.join(', ') : (r.raw_rolls ?? '—');
                  const modTotal = (r.modifiers && (r.modifiers.total ?? r.modifiers.total_bonus));
                  const modStr = (modTotal!=null) ? (modTotal>=0?`+${modTotal}`:`${modTotal}`) : '—';
                  const metaBits = [];
                  if (r.meta) {
                    if (r.meta.skill_key) metaBits.push(_esc(r.meta.skill_key));
                    if (r.meta.weapon_key) metaBits.push(_esc(r.meta.weapon_key));
                    if (r.meta.enemy_key||r.meta.enemy_name) metaBits.push(_esc(r.meta.enemy_name||r.meta.enemy_key));
                    if (r.meta.round!=null) metaBits.push('r'+r.meta.round);
                  }
                  // #853: damage rows — pokazuj kalkulację zbroi w Szczegółach
                  let dmgCalc = '';
                  if (r.roll_type === 'damage' && r.meta && r.total != null) {
                    const arm = Number(r.meta.armor_reduction || 0);
                    const fin = r.total;
                    if (r.meta.nat20_ignored_armor) {
                      dmgCalc = ` <span style="color:var(--gold,#f59e0b);font-size:0.7rem">| ${fin} dmg ⚡NAT20</span>`;
                    } else if (arm > 0) {
                      dmgCalc = ` <span style="color:var(--t3);font-size:0.7rem">| ${fin + arm} − ${arm} (zbroja) = ${fin} dmg</span>`;
                    } else {
                      dmgCalc = ` <span style="color:var(--t3);font-size:0.7rem">| ${fin} dmg</span>`;
                    }
                  }
                  return `<tr>
                    <td style="text-align:left">${TYPE_LABEL[r.roll_type]||_esc(r.roll_type)}</td>
                    <td style="text-align:center;font-family:monospace">${_esc(String(raw))}${r.notation?` <span style="color:var(--t3)">${_esc(r.notation)}</span>`:''}</td>
                    <td style="text-align:center;font-family:monospace">${modStr}</td>
                    <td style="text-align:center;font-family:monospace;font-weight:700">${r.total ?? '—'}</td>
                    <td style="text-align:center;font-family:monospace">${r.dc ?? '—'}</td>
                    <td style="text-align:left;color:${OUT_COLOR(r.outcome)};font-weight:600">${_esc(r.outcome||'—')}</td>
                    <td style="text-align:left;color:var(--t3);font-size:0.72rem">${metaBits.join(' · ')}${dmgCalc}</td>
                  </tr>`;
                }).join('')}</tbody>
              </table>`;
          panel.innerHTML = bar + `<div style="padding:0 4px 16px">${body}</div>`;
          panel.querySelectorAll('.dice-filter').forEach(b =>
            b.addEventListener('click', () => _render(b.dataset.dtype || null)));
        } catch(e) { panel.innerHTML = `<p style="color:var(--red);padding:16px">${_esc(e.message)}</p>`; }
      };
      await _render(null);
    }

    else if (tab === 'state') {
      // #761: rejestr zmian zasobów/kondycji gracza.
      panel.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>';
      const RES = { hp:'❤️ HP', mana:'🔵 Mana', condition:'✨ Kondycja', zone:'📍 Strefa' };
      const _render = async (filter) => {
        try {
          const qs = filter ? `?resource=${encodeURIComponent(filter)}&limit=200` : '?limit=200';
          const d = await apiFetch(`/api/campaigns/${campId}/state-changes${qs}`);
          const rows = d.state_changes || [];
          const types = ['', ...Object.keys(RES)];
          const bar = `<div style="display:flex;gap:6px;flex-wrap:wrap;padding:8px 16px;border-bottom:1px solid var(--border);background:var(--surface)">
            ${types.map(t => `<button class="btn btn-sm st-filter${(t===(filter||''))?' btn-primary':''}" data-stype="${t}" style="font-size:0.72rem;padding:2px 8px">${t?RES[t]:'Wszystkie'}</button>`).join('')}
            <span style="margin-left:auto;font-size:0.72rem;color:var(--t3);align-self:center">${rows.length} zmian</span>
          </div>`;
          const fmtDelta = (dl) => dl==null ? '' : (dl>0?`<span style="color:var(--green)">+${dl}</span>`:`<span style="color:var(--red)">${dl}</span>`);
          const body = !rows.length
            ? '<p style="text-align:center;padding:24px;color:var(--t3)">Brak zmian. Zagraj turę / walkę / odpocznij.</p>'
            : `<table class="data-table" style="width:100%;font-size:0.78rem">
                <thead><tr><th style="text-align:left">Zasób</th><th>Było</th><th>Jest</th><th>Δ</th><th style="text-align:left">Powód</th><th style="text-align:left">Szczegóły</th></tr></thead>
                <tbody>${rows.map(r => {
                  const meta = r.meta || {};
                  const bits = [];
                  if (meta.round!=null) bits.push('r'+meta.round);
                  if (meta.enemy_name) bits.push(_esc(meta.enemy_name));
                  if (meta.spell) bits.push(_esc(meta.spell));
                  if (meta.skill_key) bits.push(_esc(meta.skill_key));
                  return `<tr>
                    <td style="text-align:left">${RES[r.resource]||_esc(r.resource)}</td>
                    <td style="text-align:center;font-family:monospace">${r.before_val ?? '—'}</td>
                    <td style="text-align:center;font-family:monospace;font-weight:700">${r.after_val ?? '—'}</td>
                    <td style="text-align:center;font-family:monospace">${fmtDelta(r.delta)}</td>
                    <td style="text-align:left">${_esc(r.cause||'—')}</td>
                    <td style="text-align:left;color:var(--t3);font-size:0.72rem">${bits.join(' · ')}</td>
                  </tr>`;
                }).join('')}</tbody></table>`;
          panel.innerHTML = bar + `<div style="padding:0 4px 16px">${body}</div>`;
          panel.querySelectorAll('.st-filter').forEach(b =>
            b.addEventListener('click', () => _render(b.dataset.stype || null)));
        } catch(e) { panel.innerHTML = `<p style="color:var(--red);padding:16px">${_esc(e.message)}</p>`; }
      };
      await _render(null);
    }

    else if (tab === 'decisions') {
      // #762: rejestr decyzji silnika per tura (intent/route/gate).
      panel.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>';
      try {
        const d = await apiFetch(`/api/campaigns/${campId}/turn-decisions?limit=200`);
        const rows = d.turn_decisions || [];
        const body = !rows.length
          ? '<p style="text-align:center;padding:24px;color:var(--t3)">Brak decyzji. Zagraj turę.</p>'
          : `<table class="data-table" style="width:100%;font-size:0.78rem">
              <thead><tr><th>T</th><th style="text-align:left">Wejście gracza</th><th style="text-align:left">Intent</th><th>Conf</th><th style="text-align:left">Trasa</th><th style="text-align:left">Gate</th></tr></thead>
              <tbody>${rows.map(r => {
                const blocked = r.gate_blocked === true;
                const gate = blocked
                  ? `<span style="color:var(--red);font-weight:600">⛔ ${_esc(r.gate_reason||'blocked')}</span>`
                  : '<span style="color:var(--green)">✓ pass</span>';
                const conf = r.confidence==null ? '—' : `${Math.round(r.confidence*100)}%`;
                return `<tr>
                  <td style="text-align:center;font-family:monospace">${r.turn_number ?? '—'}</td>
                  <td style="text-align:left;color:var(--t2)">${_esc((r.user_text||'').slice(0,80))}</td>
                  <td style="text-align:left"><span class="badge badge-slate">${_esc(r.action_type||'?')}</span></td>
                  <td style="text-align:center;font-family:monospace">${conf}</td>
                  <td style="text-align:left">${_esc(r.route||'—')}</td>
                  <td style="text-align:left">${gate}</td>
                </tr>`;
              }).join('')}</tbody></table>`;
        panel.innerHTML = `<div style="padding:8px 16px;border-bottom:1px solid var(--border);background:var(--surface);font-size:0.72rem;color:var(--t3)">${rows.length} decyzji — czemu silnik zrobił X</div><div style="padding:0 4px 16px">${body}</div>`;
      } catch(e) { panel.innerHTML = `<p style="color:var(--red);padding:16px">${_esc(e.message)}</p>`; }
    }

    else if (tab === 'events') {
      // #781: rejestr zdarzeń narracyjnych+walki per kampania (game_events).
      panel.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>';
      // Ikona + etykieta + kolor severity per typ zdarzenia
      const EV = {
        quest_complete:{i:'📜',l:'Quest ukończony'}, quest_grant:{i:'📜',l:'Nowy quest'},
        xp_grant:{i:'⭐',l:'Punkty doświadczenia'}, item_grant:{i:'🎁',l:'Przedmiot'},
        gold_grant:{i:'💰',l:'Złoto'}, location_new:{i:'🗺️',l:'Nowa lokacja'},
        combat_start:{i:'⚔️',l:'Start walki'}, combat_victory:{i:'🏆',l:'Zwycięstwo'},
        combat_fled:{i:'🏃',l:'Ucieczka'}, player_death:{i:'💀',l:'Śmierć bohatera'},
        beat_complete:{i:'🎬',l:'Beat ukończony'},
      };
      const SEV = { error:'var(--red)', warning:'var(--amber)', info:'var(--t2)' };
      const _render = async (filter) => {
        try {
          const qs = filter ? `?event_type=${encodeURIComponent(filter)}&limit=300` : '?limit=300';
          const d = await apiFetch(`/api/campaigns/${campId}/game-events${qs}`);
          const rows = d.game_events || [];
          // zbiór typów obecnych w danych → filtry
          const present = [...new Set(rows.map(r => r.event_type))];
          const types = ['', ...present];
          const bar = `<div style="display:flex;gap:6px;flex-wrap:wrap;padding:8px 16px;border-bottom:1px solid var(--border);background:var(--surface)">
            ${types.map(t => `<button class="btn btn-sm ev-filter${(t===(filter||''))?' btn-primary':''}" data-evtype="${t}" style="font-size:0.72rem;padding:2px 8px">${t?((EV[t]?.i||'•')+' '+(EV[t]?.l||t)):'Wszystkie'}</button>`).join('')}
            <span style="margin-left:auto;font-size:0.72rem;color:var(--t3);align-self:center">${rows.length} zdarzeń</span>
          </div>`;
          const _detail = (data) => {
            if (!data || typeof data !== 'object') return '';
            const bits = [];
            if (data.quest_title) bits.push(_esc(data.quest_title));
            if (data.item_label) bits.push(_esc(data.item_label));
            if (data.location_key) bits.push(_esc(data.location_key));
            if (data.amount != null) bits.push('+'+data.amount);
            if (data.new_total_gp != null) bits.push('('+data.new_total_gp+' zł)');
            if (data.xp != null && data.amount == null) bits.push(data.xp+' PD');
            if (data.reason) bits.push(_esc(data.reason));
            if (data.enemy) bits.push(_esc(data.enemy));
            if (!bits.length) { try { return _esc(JSON.stringify(data).slice(0,80)); } catch(e){ return ''; } }
            return bits.join(' · ');
          };
          const body = !rows.length
            ? '<p style="text-align:center;padding:24px;color:var(--t3)">Brak zdarzeń. Zagraj turę z questem/łupem/złotem lub stocz walkę.<br><span style="font-size:0.72rem">Stare kampanie sprzed instrumentacji (#777) pozostają puste — zdarzeń nie da się odtworzyć wstecz.</span></p>'
            : `<table class="data-table" style="width:100%;font-size:0.78rem">
                <thead><tr><th style="text-align:left">Typ</th><th style="text-align:left">Szczegóły</th><th>Postać</th><th style="text-align:left">Czas</th></tr></thead>
                <tbody>${rows.map(r => {
                  const ev = EV[r.event_type] || {i:'•', l:r.event_type};
                  const col = SEV[r.severity] || 'var(--t2)';
                  return `<tr>
                    <td style="text-align:left"><span style="color:${col}">${ev.i} ${_esc(ev.l)}</span></td>
                    <td style="text-align:left;color:var(--t2)">${_detail(r.data)}</td>
                    <td style="text-align:center;font-family:monospace;color:var(--t3)">${r.character_id ?? '—'}</td>
                    <td style="text-align:left;color:var(--t3);font-size:0.72rem">${_esc((r.created_at||'').replace('T',' ').slice(0,16))}</td>
                  </tr>`;
                }).join('')}</tbody></table>`;
          panel.innerHTML = bar + `<div style="padding:0 4px 16px">${body}</div>`;
          panel.querySelectorAll('.ev-filter').forEach(b =>
            b.addEventListener('click', () => _render(b.dataset.evtype || null)));
        } catch(e) { panel.innerHTML = `<p style="color:var(--red);padding:16px">${_esc(e.message)}</p>`; }
      };
      await _render(null);
    }

    else if (tab === 'quests') {
      // #779: zakładka Questy+XP — lista questów bohatera + granty XP per kampania
      panel.innerHTML = '<div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>';
      try {
        const d = await apiFetch(`/api/admin/campaigns/${campId}/quests-xp`);
        const quests = d.quests || [];
        const grants = d.xp_grants || [];

        const _statusBadge = (status) => {
          if (status === 'completed') return `<span class="badge badge-green">✓ ukończony</span>`;
          if (status === 'failed') return `<span class="badge badge-red">✗ nieudany</span>`;
          return `<span class="badge badge-amber">◌ aktywny</span>`;
        };
        const _typeLabel = (t) => ({main:'główny',side:'poboczny',daily:'dzienny'})[t] || t;

        const questsHtml = !quests.length
          ? '<p style="text-align:center;padding:16px;color:var(--t3)">Brak questów w tej kampanii.</p>'
          : `<table class="data-table" style="width:100%;font-size:0.78rem">
              <thead><tr>
                <th style="text-align:left">Tytuł</th>
                <th>Typ</th>
                <th>Status</th>
                <th>Tura start</th>
                <th>Tura koniec</th>
              </tr></thead>
              <tbody>${quests.map(q => `<tr>
                <td style="text-align:left;color:var(--t1)">${_esc(q.title)}</td>
                <td style="text-align:center"><span class="badge badge-slate">${_typeLabel(q.quest_type)}</span></td>
                <td style="text-align:center">${_statusBadge(q.status)}</td>
                <td style="text-align:center;font-family:monospace">${q.created_turn ?? '—'}</td>
                <td style="text-align:center;font-family:monospace">${q.completed_turn ?? '—'}</td>
              </tr>`).join('')}</tbody>
            </table>`;

        const totalXp = grants.reduce((s, g) => s + (g.amount || 0), 0);
        const grantsHtml = !grants.length
          ? '<p style="text-align:center;padding:16px;color:var(--t3)">Brak grantów XP w tej kampanii.</p>'
          : `<table class="data-table" style="width:100%;font-size:0.78rem">
              <thead><tr>
                <th>PD</th>
                <th style="text-align:left">Powód</th>
                <th style="text-align:left">Źródło</th>
                <th>Tura</th>
              </tr></thead>
              <tbody>${grants.map(g => `<tr>
                <td style="text-align:center;font-family:monospace;color:var(--green);font-weight:600">+${g.amount}</td>
                <td style="text-align:left;color:var(--t2)">${_esc(g.reason)}</td>
                <td style="text-align:left;color:var(--t3);font-size:0.72rem">${_esc(g.source)}</td>
                <td style="text-align:center;font-family:monospace">${g.turn_number ?? '—'}</td>
              </tr>`).join('')}</tbody>
            </table>`;

        panel.innerHTML = `
          <div style="padding:8px 16px;border-bottom:1px solid var(--border);background:var(--surface);display:flex;gap:16px;font-size:0.72rem;color:var(--t3)">
            <span>📜 ${quests.length} questów (${quests.filter(q=>q.status==='completed').length} ukończonych)</span>
            <span>⭐ ${grants.length} grantów XP — łącznie <strong style="color:var(--t1)">${totalXp} PD</strong></span>
          </div>
          <div style="padding:12px 16px">
            <div style="font-size:0.72rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">📜 Questy</div>
            ${questsHtml}
            <div style="font-size:0.72rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.05em;margin:16px 0 6px">⭐ Punkty doświadczenia</div>
            ${grantsHtml}
          </div>`;
      } catch(e) { panel.innerHTML = `<p style="color:var(--red);padding:16px">${_esc(e.message)}</p>`; }
    }
  }

// ══════════════════════════════════════════════════════════════
//  advanceCampScene / _loadWorkshopEncounters / _injectEncounterFromWorkshop / sendWorkshopMsg
// ══════════════════════════════════════════════════════════════
  async function advanceCampScene(campId, btn) {
    if (!confirm('Przenieść kampanię do następnej sceny?')) return;
    btn.disabled = true;
    try {
      await apiFetch(`/api/admin/campaigns/${campId}/gm-plan/advance-scene`, { method:'POST' });
      showToast('Scena zaawansowana.', 'success');
      btn.closest('[data-loaded]').dataset.loaded = '';
      btn.closest('[data-loaded]').innerHTML = '';
      _loadCampTab(campId, 'plan', btn.closest('[data-loaded]'), btn.closest('.modal-overlay'));
    } catch(e) { showToast('Błąd: '+e.message, 'error'); btn.disabled = false; }
  }

  // #966 — regenerate the GM plan via current LLM; reports ok / still degraded.
  async function regenerateCampPlan(campId, btn) {
    if (!confirm('Zregenerować plan MG? Nadpisze obecny gm_plan_json kampanii.')) return;
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Generuję…';
    try {
      const d = await apiFetch(`/api/admin/campaigns/${campId}/gm-plan/regenerate-initial`, { method:'POST' });
      if (d.plan_degraded) {
        showToast('Nadal uproszczony — sprawdź LLM (model za słaby na JSON-plan).', 'error');
      } else {
        showToast('Plan wygenerowany.', 'success');
      }
      btn.closest('[data-loaded]').dataset.loaded = '';
      btn.closest('[data-loaded]').innerHTML = '';
      _loadCampTab(campId, 'plan', btn.closest('[data-loaded]'), btn.closest('.modal-overlay'));
    } catch(e) { showToast('Błąd: '+e.message, 'error'); btn.disabled = false; btn.textContent = orig; }
  }

  async function _loadWorkshopEncounters(campId) {
    const list = document.getElementById('workshop-encounter-list');
    if (!list) return;
    try {
      const d = await apiFetch('/api/admin/forge/encounters');
      const encs = d.encounters || [];
      if (!encs.length) {
        list.innerHTML = '<em style="font-size:0.75rem;color:var(--t3)">Brak spotkań. Utwórz w Kuźni → Spotkania.</em>';
        return;
      }
      list.innerHTML = encs.map(e => {
        const enemies = (e.encounter?.enemies||[]).map(x => `${x.name}×${x.count||1}`).join(', ');
        return `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background:var(--surface-raised);border:1px solid var(--border);border-radius:var(--r);gap:8px">
          <div style="min-width:0">
            <div style="font-size:0.8rem;font-weight:600;color:var(--t1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_esc(e.encounter?.title||e.hook_title)}</div>
            <div style="font-size:0.72rem;color:var(--t3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_esc(enemies)}</div>
          </div>
          <button class="btn btn-sm btn-primary" style="white-space:nowrap;flex-shrink:0" onclick="_injectEncounterFromWorkshop(${campId},${e.hook_id},this)">⚡ Wstrzyknij</button>
        </div>`;
      }).join('');
    } catch(e) {
      list.innerHTML = `<em style="font-size:0.75rem;color:var(--red)">${_esc(e.message)}</em>`;
    }
  }

  async function _injectEncounterFromWorkshop(campId, hookId, btn) {
    btn.disabled = true; btn.textContent = '⏳';
    try {
      await apiFetch('/api/admin/forge/debug/inject-encounter', {
        method: 'POST',
        body: JSON.stringify({ campaign_id: campId, hook_id: hookId }),
      });
      btn.textContent = '✅';
      _showToast('Spotkanie wstrzyknięte! Następna tura gracza je użyje.', 'success');
      setTimeout(() => { btn.textContent = '⚡ Wstrzyknij'; btn.disabled = false; }, 3000);
    } catch(e) {
      _showToast(e.message||'Błąd.', 'error');
      btn.textContent = '⚡ Wstrzyknij'; btn.disabled = false;
    }
  }

  async function sendWorkshopMsg(campId, btn) {
    const input = btn.previousElementSibling;
    const msg = input.value.trim();
    if (!msg) return;
    const hist = document.getElementById('workshop-history');
    hist.innerHTML += `<div style="margin-bottom:8px"><strong style="color:var(--t1)">Ty:</strong> ${_esc(msg)}</div>`;
    hist.scrollTop = hist.scrollHeight;
    input.value = ''; btn.disabled = true;
    try {
      const d = await apiFetch(`/api/admin/campaigns/${campId}/workshop/message`, {
        method: 'POST', body: JSON.stringify({ message: msg })
      });
      const reply = d.reply || d.assistant_reply || d.message || JSON.stringify(d);
      hist.innerHTML += `<div style="margin-bottom:12px;padding:8px;background:var(--blue-light);border-radius:var(--r);border:1px solid var(--blue-border);color:var(--blue-text)">${_esc(reply)}</div>`;
      hist.scrollTop = hist.scrollHeight;
    } catch(e) { hist.innerHTML += `<div style="color:var(--red);font-size:0.8rem">${_esc(e.message)}</div>`; }
    btn.disabled = false;
  }


// ══════════════════════════════════════════════════════════════
//  Section HTML template
// ══════════════════════════════════════════════════════════════
function _sectionHtml() {
  return `

      <div class="section-header">
        <div>
          <div class="section-heading">Kampanie</div>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          <div class="view-toggle" id="camp-view-toggle" style="display:flex;border:1px solid var(--border);border-radius:6px;overflow:hidden">
            <button class="btn-view active" data-view="table" onclick="_setCampView('table')" style="padding:6px 12px;font-size:0.78rem;border:none;background:var(--blue);color:#fff;cursor:pointer">⊞ Tabela</button>
            <button class="btn-view" data-view="cards" onclick="_setCampView('cards')" style="padding:6px 12px;font-size:0.78rem;border:none;background:var(--bg2);color:var(--t2);cursor:pointer">▥ Karty</button>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="toolbar">
          <div class="search-box">
            <span class="search-box-icon">🔍</span>
            <input type="text" placeholder="Szukaj kampanii…" oninput="filterTableGeneric(this,'campaigns-table','campaign-row-name')">
          </div>
          <div class="filter-group">
            <button class="chip on" onclick="filterCampaigns(this,'')">Wszystkie</button>
            <button class="chip" onclick="filterCampaigns(this,'aktywne')">Aktywne</button>
            <button class="chip" onclick="filterCampaigns(this,'w walce')">W walce</button>
            <button class="chip" onclick="filterCampaigns(this,'zakończone')">Zakończone</button>
            <button class="chip" onclick="filterCampaigns(this,'usunięte')">🗑 Usunięte</button>
          </div>
        </div>

        <div class="selection-bar" id="camp-sel-bar">
          <span class="sel-count" id="camp-sel-count">0 zaznaczonych</span>
          <button class="btn btn-sm btn-secondary">Eksportuj</button>
          <button class="btn btn-sm btn-danger" onclick="_bulkDeleteCampaigns(this)">Usuń zaznaczone</button>
        </div>

        <div class="data-table--cards table-wrap" id="campaigns-table-view">
          <table class="data-table" id="campaigns-table">
            <thead>
              <tr>
                <th class="col-check"><input type="checkbox" id="camp-check-all" onchange="toggleAll('camp', this)"></th>
                <th class="td-sticky"><div class="th-inner sorted">Kampania <span class="sort-icon asc">▲</span></div></th>
                <th><div class="th-inner">Bohater <span class="sort-icon">▲</span></div></th>
                <th><div class="th-inner">Klasa</div></th>
                <th><div class="th-inner">Poz. <span class="sort-icon">▲</span></div></th>
                <th><div class="th-inner">HP</div></th>
                <th><div class="th-inner">Tura <span class="sort-icon">▲</span></div></th>
                <th><div class="th-inner">Status</div></th>
                <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="col-check"><input type="checkbox" class="camp-row-check" onchange="rowCheck('camp')"></td>
                <td class="td-sticky"><div class="campaign-row-name">Pierścień Cienia</div><div class="campaign-row-sub">Aktywna od 14 dni</div></td>
                <td class="td-mono">Aldric Stormhand</td>
                <td><span class="type-badge">Wojownik</span></td>
                <td class="td-mono">6</td>
                <td><div class="hp-wrap"><div class="hp-bar"><div class="hp-fill mid" style="width:65%"></div></div><span class="hp-label">38/58</span></div></td>
                <td class="td-mono">42</td>
                <td><span class="badge badge-red">⚔ W walce</span></td>
                <td class="td-actions"><button class="btn-icon">⊞</button> <button class="btn-icon">✎</button></td>
              </tr>
              <tr>
                <td class="col-check"><input type="checkbox" class="camp-row-check" onchange="rowCheck('camp')"></td>
                <td class="td-sticky"><div class="campaign-row-name">Cień Pustkowia</div><div class="campaign-row-sub">Aktywna od 3 dni</div></td>
                <td class="td-mono">Mira Ashvale</td>
                <td><span class="type-badge">Złodziej</span></td>
                <td class="td-mono">4</td>
                <td><div class="hp-wrap"><div class="hp-bar"><div class="hp-fill low" style="width:33%"></div></div><span class="hp-label" style="color:var(--red)">12/36</span></div></td>
                <td class="td-mono">18</td>
                <td><span class="badge badge-amber">⚠ Krytycz.</span></td>
                <td class="td-actions"><button class="btn-icon">⊞</button> <button class="btn-icon">✎</button></td>
              </tr>
              <tr>
                <td class="col-check"><input type="checkbox" class="camp-row-check" onchange="rowCheck('camp')"></td>
                <td class="td-sticky"><div class="campaign-row-name">Kronika Białych Wzgórz</div><div class="campaign-row-sub">Aktywna od 42 dni</div></td>
                <td class="td-mono">Theo Brightwick</td>
                <td><span class="type-badge">Uczony</span></td>
                <td class="td-mono">8</td>
                <td><div class="hp-wrap"><div class="hp-bar"><div class="hp-fill high" style="width:96%"></div></div><span class="hp-label">52/54</span></div></td>
                <td class="td-mono">67</td>
                <td><span class="badge badge-green">● Aktywna</span></td>
                <td class="td-actions"><button class="btn-icon">⊞</button> <button class="btn-icon">✎</button></td>
              </tr>
              <tr>
                <td class="col-check"><input type="checkbox" class="camp-row-check" onchange="rowCheck('camp')"></td>
                <td class="td-sticky"><div class="campaign-row-name">Morze Zapomniane</div><div class="campaign-row-sub">Oczekuje 1 dzień</div></td>
                <td class="td-mono">Kael Dawnsbreach</td>
                <td><span class="type-badge">Wojownik</span></td>
                <td class="td-mono">3</td>
                <td><div class="hp-wrap"><div class="hp-bar"><div class="hp-fill mid" style="width:74%"></div></div><span class="hp-label">28/38</span></div></td>
                <td class="td-mono">9</td>
                <td><span class="badge badge-slate">○ Oczekuje</span></td>
                <td class="td-actions"><button class="btn-icon">⊞</button> <button class="btn-icon">✎</button></td>
              </tr>
              <tr>
                <td class="col-check"><input type="checkbox" class="camp-row-check" onchange="rowCheck('camp')"></td>
                <td class="td-sticky"><div class="campaign-row-name">Upadłe Miasto</div><div class="campaign-row-sub">Brak bohatera</div></td>
                <td class="td-muted">—</td>
                <td class="td-muted">—</td>
                <td class="td-muted">—</td>
                <td class="td-muted">—</td>
                <td class="td-muted">—</td>
                <td><span class="badge badge-slate">○ Oczekuje</span></td>
                <td class="td-actions"><button class="btn-icon">⊞</button> <button class="btn-icon danger">✕</button></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div id="campaigns-cards-view" style="display:none;padding:14px;display:none">
          <div id="campaigns-cards-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px"></div>
        </div>

        <div class="pagination">
          <span>Pokazuje 5 z 5 kampanii</span>
          <div class="page-btns">
            <button class="page-btn active">1</button>
          </div>
        </div>
      </div>
  `;
}

// ══════════════════════════════════════════════════════════════
//  Module entry — called by modular admin shell on navigation
// ══════════════════════════════════════════════════════════════
export async function init(panel) {
  panel.innerHTML = _sectionHtml();
  Object.assign(window, {
    rowCheck,      // #588 — multi-select helpers (shared)
    toggleAll,     // #588
    filterTableGeneric,
    filterCampaigns,
    _setCampView,
    deleteCampaign,
    _bulkDeleteCampaigns,
    _campCmdSuggest,
    _campCmdPick,
    _campCmdKey,
    _campCmd,
    _campModalResurrect,
    _campOpenInspector,   // HI5 (#628) — link do Inspektora Bohatera
    openCampaignModal,
    advanceCampScene,
    regenerateCampPlan,
    sendWorkshopMsg,
    _injectEncounterFromWorkshop,
  });
  _loadCampaigns();
}
