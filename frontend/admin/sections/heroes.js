/**
 * HI2 (#625) — sekcja „Bohaterowie": lista hero-first + szkielet modalu Inspektora.
 * HI3 (#626) — zakładka Arkusz: pełna edycja liczb bohatera (staty/skille/HP/mana/poziom/
 *              kondycje/złoto/XP) przez REUSE endpointów (admin_cheat z inspector:true → guard
 *              live_locked + audyt; XP przez xp/grant-mg). Po zapisie re-fetch /full + re-render.
 *
 * Lista przez wzbogacony GET /api/admin/characters (LEFT JOIN → idle widoczni; kolumny
 * archetyp/poziom/status/HP/właściciel). Klik wiersza → modal Inspektora ze szkieletem
 * zakładek (Arkusz [HI3] / Ekwipunek / Zaklęcia / Questy [HI4]), który ładuje
 * GET /api/admin/characters/{id}/full. Banery: #1013 (konto obserwowane) + live-lock.
 */
import { apiFetch, APIError } from '../shared/api.js';
import { showToast } from '../shared/toast.js';
import { confirmDialog } from '../shared/modal.js';

const OBSERVED_OWNER_ID = 1013; // PiotrSzmidt — konto obserwowane (read-only protocol)
// Staty edytowalne przez cheat „add stat" (delta). LCK celowo poza — backend add stat go nie wspiera.
const EDITABLE_STATS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];
let _condCatalog = null; // cache katalogu kondycji (GET /api/admin/conditions)
// HI6 (#629): tryb „Wymuś edycję" — omija live-lock (walka/tura), NIE #1013.
// Per modal (otwarcie resetuje); helpery dołączają force do payloadów mutacji.
let _forceEdit = false;

function _esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const _STATUS_LABEL = {
  idle: 'Wolny',
  in_campaign: 'W kampanii',
  in_dungeon: 'W lochu',
};

const _ARCHETYPE_LABEL = {
  warrior: 'Wojownik',
  scholar: 'Uczony',
  rogue: 'Łotrzyk',
  ranger: 'Łowca',
};

let _heroes = [];          // ostatnio pobrana lista
let _statusFilter = 'all'; // all | idle | playing
let _search = '';

// ── Lista ────────────────────────────────────────────────────────────────────

function _matches(h) {
  if (_statusFilter === 'idle' && h.status !== 'idle') return false;
  if (_statusFilter === 'playing' && h.status === 'idle') return false;
  if (_search) {
    const hay = `${h.name || ''} ${h.owner_name || ''}`.toLowerCase();
    if (!hay.includes(_search)) return false;
  }
  return true;
}

function _renderRows() {
  const tbody = document.getElementById('heroes-tbody');
  if (!tbody) return;
  const rows = _heroes.filter(_matches);
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:28px;color:var(--t3);font-size:0.8rem">Brak bohaterów dla tego filtra.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(h => {
    const observed = Number(h.user_id) === OBSERVED_OWNER_ID;
    const hp = (h.hp != null && h.max_hp != null) ? `${h.hp}/${h.max_hp}` : '—';
    const statusLbl = _STATUS_LABEL[h.status] || h.status || '—';
    const arch = _ARCHETYPE_LABEL[h.archetype] || h.archetype || '—';
    return `<tr data-hero-id="${h.id}" style="cursor:pointer">
      <td class="td-name">${_esc(h.name || '—')}${observed ? ' <span title="Konto obserwowane (#1013)" style="color:var(--red)">👁</span>' : ''}</td>
      <td>${_esc(arch)}</td>
      <td data-sort-val="${h.level ?? 0}">${h.level ?? '—'}</td>
      <td>${_esc(h.owner_name || ('#' + (h.user_id ?? '?')))}</td>
      <td><span class="badge">${_esc(statusLbl)}</span></td>
      <td>${_esc(h.campaign_title || '—')}</td>
      <td data-sort-val="${h.hp ?? 0}">${hp}</td>
      <td style="text-align:center">${observed
        ? '<span title="Konto obserwowane (#1013) — usuwanie zablokowane" style="color:var(--t3)">🔒</span>'
        : `<button class="btn btn-sm" data-hero-del="${h.id}" title="Usuń bohatera" style="color:var(--red)">🗑</button>`}</td>
    </tr>`;
  }).join('');
  tbody.querySelectorAll('tr[data-hero-id]').forEach(tr => {
    tr.addEventListener('click', () => openInspector(Number(tr.dataset.heroId)));
  });
  tbody.querySelectorAll('[data-hero-del]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation(); // nie otwieraj Inspektora przy kliknięciu kosza
      const h = _heroes.find(x => Number(x.id) === Number(btn.dataset.heroDel));
      if (h) _deleteHero(h);
    });
  });
}

// Usuń bohatera (DELETE /api/admin/characters/{id}) — twardo blokowane dla #1013, z potwierdzeniem.
async function _deleteHero(h) {
  if (Number(h.user_id) === OBSERVED_OWNER_ID) {
    showToast('👁 Konto obserwowane (#1013) — usuwanie zablokowane.', 'error');
    return;
  }
  const label = h.name || ('#' + h.id);
  const ok = await confirmDialog(
    `Usunąć bohatera „${label}"? Operacji NIE można cofnąć — usunięte zostaną też wszystkie tury tej postaci. Kampania pozostaje.`
  );
  if (!ok) return;
  try {
    await apiFetch(`/api/admin/characters/${h.id}`, { method: 'DELETE' });
    showToast(`Bohater „${label}" usunięty`, 'success');
    await _loadList();
  } catch (e) {
    showToast(`Błąd usuwania: ${e.message}`, 'error');
  }
}

async function _loadList() {
  const tbody = document.getElementById('heroes-tbody');
  if (tbody) tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:28px;color:var(--t3)">Ładowanie…</td></tr>`;
  try {
    const res = await apiFetch('/api/admin/characters');
    _heroes = (res && res.items) || [];
    _renderRows();
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:28px;color:var(--red)">Błąd: ${_esc(e.message)}</td></tr>`;
  }
}

// ── Modal Inspektora (szkielet — zakładki wypełniane w HI3–HI4) ───────────────

const _TABS = [
  { key: 'sheet', label: '📊 Arkusz' },
  { key: 'inventory', label: '🎒 Ekwipunek' },
  { key: 'spells', label: '✨ Zaklęcia' },
  { key: 'quests', label: '📜 Questy' },
];

// ── Edycja: wywołania backendu (REUSE) ────────────────────────────────────────

async function _loadCondCatalog() {
  if (_condCatalog) return _condCatalog;
  try {
    const res = await apiFetch('/api/admin/conditions');
    _condCatalog = (res && res.items) || [];
  } catch {
    _condCatalog = [];
  }
  return _condCatalog;
}

/** Mutacja przez admin_cheat z flagą inspector:true (guard live_locked + audyt). */
async function _cheat(heroId, payload) {
  try {
    await apiFetch(`/api/admin/cheat/${heroId}`, {
      method: 'POST',
      body: JSON.stringify({ ...payload, inspector: true, force: _forceEdit }),
    });
    return true;
  } catch (e) {
    if (e instanceof APIError && e.status === 409) {
      showToast('⚔ Bohater w trakcie walki/tury — edycja zablokowana.', 'error');
    } else {
      showToast(`Błąd zapisu: ${e.message}`, 'error');
    }
    return false;
  }
}

/** XP — reuse xp/grant-mg (wymaga właściciela kampanii; tylko bohater w kampanii). */
async function _grantXp(heroId, ownerId, amount, reason) {
  try {
    await apiFetch(`/api/characters/${heroId}/xp/grant-mg?user_id=${ownerId}`, {
      method: 'POST',
      body: JSON.stringify({ amount, reason }),
    });
    return true;
  } catch (e) {
    showToast(`Błąd przyznania XP: ${e.message}`, 'error');
    return false;
  }
}

// ── HI4: katalogi (cache) + mutacje equip/zaklęć ──────────────────────────────

let _itemCatalog = null;  // [{key,label,kind}] z weapons+items+consumables
let _spellCatalog = null; // [{key,label,tier}] z /admin/spells

async function _loadItemCatalog() {
  if (_itemCatalog) return _itemCatalog;
  const out = [];
  const sources = [
    { ep: '/api/admin/weapons', kind: 'weapon' },
    { ep: '/api/admin/items', kind: 'item' },
    { ep: '/api/admin/consumables', kind: 'consumable' },
  ];
  for (const s of sources) {
    try {
      const res = await apiFetch(s.ep);
      const list = (res && (res.items || res)) || [];
      list.forEach(r => {
        // Zbroja żyje w game_config_items (item_type='armor') — wydziel ją jako osobną
        // kategorię „armor", by była łatwa do znalezienia w katalogu i poprawnie auto-zakładana
        // na slot 'armor' (backend cheat „add item" + _auto_equip_new_inventory_row).
        const kind = (s.kind === 'item' && String(r.item_type || '').toLowerCase() === 'armor')
          ? 'armor' : s.kind;
        out.push({ key: r.key, label: r.label || r.name || r.key, kind });
      });
    } catch { /* pomiń jedno źródło */ }
  }
  _itemCatalog = out;
  return out;
}

async function _loadSpellCatalog() {
  if (_spellCatalog) return _spellCatalog;
  try {
    const res = await apiFetch('/api/admin/spells');
    const list = (res && (res.items || res)) || [];
    _spellCatalog = list.map(r => ({ key: r.key, label: r.label || r.name || r.key, tier: r.tier }));
  } catch {
    _spellCatalog = [];
  }
  return _spellCatalog;
}

/** Załóż/zdejmij (slot=null → zdejmij). Inspector:true → guard live-lock + audyt. */
async function _equip(heroId, inventoryId, slot) {
  try {
    await apiFetch(`/api/inventory/${heroId}/equip`, {
      method: 'POST',
      body: JSON.stringify({ inventory_id: inventoryId, slot: slot ?? null, inspector: true, force: _forceEdit }),
    });
    return true;
  } catch (e) {
    if (e instanceof APIError && e.status === 409) {
      showToast('⚔ Bohater w trakcie walki/tury — edycja zablokowana.', 'error');
    } else {
      showToast(`Błąd: ${e.message}`, 'error');
    }
    return false;
  }
}

/** Naucz/awansuj zaklęcie. Inspector:true → guard live-lock + audyt. */
async function _spellAction(heroId, action, spellKey) {
  try {
    await apiFetch(`/api/admin/characters/${heroId}/spells/${action}`, {
      method: 'POST',
      body: JSON.stringify({ spell_key: spellKey, inspector: true, force: _forceEdit }),
    });
    return true;
  } catch (e) {
    if (e instanceof APIError && e.status === 409) {
      showToast('⚔ Bohater w trakcie walki/tury — edycja zablokowana.', 'error');
    } else {
      showToast(`Błąd: ${e.message}`, 'error');
    }
    return false;
  }
}

const _ITEM_TYPE_GROUPS = [
  { key: 'weapon', label: 'Broń' },
  { key: 'armor', label: 'Zbroja' },
  { key: 'consumable', label: 'Konsumpcja' },
  { key: 'item', label: 'Przedmioty' },
  { key: 'quest', label: 'Zadaniowe' },
  { key: 'narrative', label: 'Narracyjne' },
];

// ── Modal Inspektora ──────────────────────────────────────────────────────────

// HI5 (#628): wyeksportowany — monitor kampanii (campaigns.js) reużywa TEN SAM modal.
export async function openInspector(heroId) {
  _forceEdit = false; // HI6: każde otwarcie startuje z wyłączonym wymuszeniem
  document.getElementById('hero-inspector-overlay')?.remove();
  const overlay = document.createElement('div');
  overlay.id = 'hero-inspector-overlay';
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="width:min(960px,96vw);max-height:94vh;display:flex;flex-direction:column">
      <div class="modal-head">
        <span class="modal-title" id="hero-modal-title">Bohater #${heroId}</span>
        <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
      </div>
      <div id="hero-banners" style="padding:0 16px"></div>
      <div class="stab-row" style="display:flex;gap:2px;padding:0 16px;border-bottom:1px solid var(--border)">
        ${_TABS.map((t, i) => `<button class="stab${i === 0 ? ' active' : ''}" data-htab="${t.key}" style="border-radius:0;border-bottom:none;margin-bottom:-1px">${t.label}</button>`).join('')}
      </div>
      <div class="modal-body" style="flex:1;overflow-y:auto;padding:16px" id="hero-modal-body">
        <div style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</div>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });

  let _activeTab = 'sheet';
  let full = null;

  async function _fetchFull() {
    full = await apiFetch(`/api/admin/characters/${heroId}/full`);
  }

  // Re-fetch /full + przerysuj aktywną zakładkę (świeży stan po każdym zapisie).
  async function refresh() {
    try {
      await _fetchFull();
    } catch (e) {
      showToast(`Błąd odświeżania: ${e.message}`, 'error');
      return;
    }
    _renderBanners();
    _renderTab(_activeTab);
  }

  // #1013 (konto obserwowane) → blokada TWARDA, nieprzełamywalna.
  function _observedLocked() {
    return Boolean(full && Number(full.owner_id) === OBSERVED_OWNER_ID);
  }
  // Edycja zablokowana gdy: #1013 (zawsze) LUB live-lock i NIE włączono wymuszenia (HI6).
  function _editLocked() {
    if (!full) return false;
    if (_observedLocked()) return true;
    if (full.is_live_locked && !_forceEdit) return true;
    return false;
  }

  function _renderBanners() {
    const banners = [];
    if (Number(full.owner_id) === OBSERVED_OWNER_ID) {
      banners.push(`<div class="hero-banner" style="margin:10px 0;padding:8px 12px;border-radius:6px;background:rgba(220,60,60,.12);border:1px solid var(--red);color:var(--red);font-size:0.82rem">👁 Konto obserwowane (#1013) — protokół tylko-do-odczytu. Edycja zablokowana.</div>`);
    }
    // Live-lock: pokaż baner + toggle „Wymuś edycję" (HI6) — ale NIE dla #1013 (twarda blokada).
    if (full.is_live_locked && !_observedLocked()) {
      if (_forceEdit) {
        banners.push(`<div class="hero-banner" style="margin:10px 0;padding:8px 12px;border-radius:6px;background:rgba(220,60,60,.16);border:1px solid var(--red);color:var(--red);font-size:0.82rem;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          <span>🔓 <b>Tryb wymuszonej edycji</b> — zmiany zapisują się MIMO blokady (${_esc(full.live_lock_reason || 'live_locked')}). Ryzyko desyncu z grą. Każda zmiana jest audytowana.</span>
          <button class="btn btn-sm" data-hi-force-toggle style="margin-left:auto">Wyłącz wymuszenie</button>
        </div>`);
      } else {
        banners.push(`<div class="hero-banner" style="margin:10px 0;padding:8px 12px;border-radius:6px;background:rgba(230,170,40,.14);border:1px solid #e6aa28;color:#e6aa28;font-size:0.82rem;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          <span>⚔ Bohater w trakcie walki/tury (${_esc(full.live_lock_reason || 'live_locked')}) — edycja zablokowana.</span>
          <button class="btn btn-sm" data-hi-force-toggle style="margin-left:auto">🔓 Wymuś edycję</button>
        </div>`);
      }
    } else if (full.is_live_locked) {
      // #1013 + live-lock: pokaż info bez toggle (force nie omija #1013).
      banners.push(`<div class="hero-banner" style="margin:10px 0;padding:8px 12px;border-radius:6px;background:rgba(230,170,40,.14);border:1px solid #e6aa28;color:#e6aa28;font-size:0.82rem">⚔ Bohater w trakcie walki/tury (${_esc(full.live_lock_reason || 'live_locked')}) — edycja zablokowana.</div>`);
    }
    const el = document.getElementById('hero-banners');
    if (el) el.innerHTML = banners.join('');
    // Bind toggle (HI6): przełącz tryb force i przerysuj banery + aktywną zakładkę.
    el?.querySelector('[data-hi-force-toggle]')?.addEventListener('click', () => {
      _forceEdit = !_forceEdit;
      _renderBanners();
      _renderTab(_activeTab);
    });
  }

  // ── Zakładka Arkusz (HI3) — pełna edycja przez reuse endpointów ──────────────

  function _sheetHtml() {
    const locked = _editLocked();
    const dis = locked ? 'disabled' : '';
    const stats = full.stats || {};
    const mods = full.stat_modifiers || {};

    // 7 statów: 6 edytowalnych (stepper ±1) + LCK read-only (cheat add stat go nie wspiera).
    const statCells = EDITABLE_STATS.map(k => {
      const v = stats[k] ?? 0;
      const m = mods[k] != null ? (mods[k] >= 0 ? `+${mods[k]}` : `${mods[k]}`) : '';
      return `<div class="hi-stat" style="display:flex;flex-direction:column;align-items:center;gap:4px;padding:8px;border:1px solid var(--border);border-radius:8px">
        <b style="font-size:0.75rem;color:var(--t2)">${k}</b>
        <span style="font-size:1.3rem"><span data-hi-stat-val="${k}">${v}</span> <small style="color:var(--t3)">(${m})</small></span>
        <div style="display:flex;gap:4px">
          <button class="btn btn-sm" data-hi-stat="${k}" data-hi-delta="-1" ${dis}>−</button>
          <button class="btn btn-sm" data-hi-stat="${k}" data-hi-delta="1" ${dis}>+</button>
        </div>
      </div>`;
    }).join('');
    const lck = stats.LCK != null
      ? `<div class="hi-stat" style="display:flex;flex-direction:column;align-items:center;gap:4px;padding:8px;border:1px dashed var(--border);border-radius:8px">
          <b style="font-size:0.75rem;color:var(--t3)">LCK</b>
          <span style="font-size:1.3rem">${stats.LCK}</span>
          <small style="color:var(--t3)">tylko odczyt</small>
        </div>` : '';

    // Skille z rankami — input 0..ceiling (backend waliduje).
    // HI7 (#630): grupowanie „Posiadane" (rank ≥1) nad „Niewyuczone" (rank 0); każda grupa A→Z.
    const skills = full.skills || {};
    const allSkillKeys = Object.keys(skills).sort();
    const knownKeys = allSkillKeys.filter(k => (skills[k] ?? 0) >= 1);
    const noneKeys = allSkillKeys.filter(k => (skills[k] ?? 0) < 1);
    const _skillRow = (k, group) => `<div data-hi-skill-group="${group}" data-hi-skill-key="${_esc(k)}" style="display:flex;align-items:center;gap:8px;padding:3px 0">
          <span style="flex:1">${_esc(k)}</span>
          <input type="number" class="form-input" data-hi-skill-input="${k}" value="${skills[k] ?? 0}" min="0" style="width:70px" ${dis}>
          <button class="btn btn-sm" data-hi-save="skill" data-hi-skill="${k}" ${dis}>Zapisz</button>
        </div>`;
    const _skillSep = (group, label, n) => `<div data-hi-skill-sep="${group}" style="font-size:0.72rem;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.04em;margin:6px 0 2px;padding-top:6px;border-top:1px solid var(--border)">${label} (${n})</div>`;
    const skillRows = allSkillKeys.length
      ? [
          knownKeys.length ? _skillSep('known', 'Posiadane', knownKeys.length) + knownKeys.map(k => _skillRow(k, 'known')).join('') : '',
          noneKeys.length ? _skillSep('none', 'Niewyuczone', noneKeys.length) + noneKeys.map(k => _skillRow(k, 'none')).join('') : '',
        ].join('')
      : '<div style="color:var(--t3);font-size:0.8rem">brak skilli w arkuszu</div>';

    // Kondycje — chipy z ✕ + dropdown katalogu + Dodaj.
    const conds = full.conditions || [];
    const condChips = conds.length
      ? conds.map(c => {
          const ck = typeof c === 'string' ? c : (c.key || '');
          const cl = typeof c === 'string' ? c : (c.label || c.key || '');
          return `<span class="badge" style="display:inline-flex;align-items:center;gap:4px;margin:2px">${_esc(cl)}${locked ? '' : ` <a href="#" data-hi-cond-remove="${_esc(ck)}" style="color:var(--red);text-decoration:none">✕</a>`}</span>`;
        }).join('')
      : '<span style="color:var(--t3)">brak</span>';

    const manaBlock = (full.max_mana > 0)
      ? `<div style="display:flex;align-items:center;gap:8px">
          <b style="width:64px">Mana</b>
          <input type="number" class="form-input" id="hi-mana-input" value="${full.mana}" min="0" max="${full.max_mana}" style="width:90px" ${dis}>
          <span style="color:var(--t3)">/ ${full.max_mana}</span>
          <button class="btn btn-sm" data-hi-save="mana" ${dis}>Zapisz</button>
          <button class="btn btn-sm" data-hi-save="mana-max" ${dis}>Max</button>
        </div>` : '';

    const inCampaign = full.campaign_id != null;
    const xpBlock = inCampaign
      ? `<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <b style="width:64px">XP</b>
          <span>obecnie: ${full.xp}</span>
          <input type="number" class="form-input" id="hi-xp-input" placeholder="+ ile" min="1" style="width:90px" ${dis}>
          <input type="text" class="form-input" id="hi-xp-reason" placeholder="powód" style="width:160px" ${dis}>
          <button class="btn btn-sm" data-hi-save="xp" ${dis}>Przyznaj</button>
        </div>`
      : `<div style="display:flex;align-items:center;gap:8px"><b style="width:64px">XP</b><span>obecnie: ${full.xp}</span>
          <span style="color:var(--t3);font-size:0.8rem">— przyznanie XP tylko dla bohatera w kampanii (xp/grant-mg)</span></div>`;

    return `<div id="hero-sheet-edit" style="display:grid;gap:16px">
      <fieldset style="border:1px solid var(--border);border-radius:8px;padding:10px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">Liczby</legend>
        <div style="display:grid;gap:10px">
          <div style="display:flex;align-items:center;gap:8px">
            <b style="width:64px">HP</b>
            <input type="number" class="form-input" id="hi-hp-input" value="${full.hp}" min="0" max="${full.max_hp}" style="width:90px" ${dis}>
            <span style="color:var(--t3)">/ ${full.max_hp}</span>
            <button class="btn btn-sm" data-hi-save="hp" ${dis}>Zapisz</button>
            <button class="btn btn-sm" data-hi-save="hp-max" ${dis}>Max</button>
          </div>
          ${manaBlock}
          <div style="display:flex;align-items:center;gap:8px">
            <b style="width:64px">Poziom</b>
            <input type="number" class="form-input" id="hi-level-input" value="${full.level}" min="1" style="width:90px" ${dis}>
            <button class="btn btn-sm" data-hi-save="level" ${dis}>Zapisz</button>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            <b style="width:64px">Złoto</b>
            <input type="number" class="form-input" id="hi-gold-input" value="${full.gold_gp}" min="0" style="width:110px" ${dis}>
            <span style="color:var(--t3)">zł</span>
            <button class="btn btn-sm" data-hi-save="gold" ${dis}>Zapisz</button>
          </div>
          ${xpBlock}
        </div>
      </fieldset>

      <fieldset style="border:1px solid var(--border);border-radius:8px;padding:10px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">Statystyki</legend>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px">${statCells}${lck}</div>
      </fieldset>

      <fieldset style="border:1px solid var(--border);border-radius:8px;padding:10px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">Umiejętności (rank)</legend>
        <div style="display:grid;gap:2px">${skillRows}</div>
      </fieldset>

      <fieldset style="border:1px solid var(--border);border-radius:8px;padding:10px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">Kondycje</legend>
        <div style="margin-bottom:8px">${condChips}</div>
        <div style="display:flex;align-items:center;gap:8px">
          <select class="form-input" id="hi-cond-select" style="max-width:220px" ${dis}><option value="">— wybierz kondycję —</option></select>
          <button class="btn btn-sm" data-hi-save="cond-add" ${dis}>Dodaj</button>
        </div>
      </fieldset>
    </div>`;
  }

  function _bindSheet() {
    const root = document.getElementById('hero-sheet-edit');
    if (!root) return;

    // Wypełnij dropdown kondycji (z katalogu, pomijając już posiadane).
    _loadCondCatalog().then(cat => {
      const sel = root.querySelector('#hi-cond-select');
      if (!sel) return;
      const have = new Set((full.conditions || []).map(c => typeof c === 'string' ? c : (c.key || '')));
      cat.filter(c => !have.has(c.key)).forEach(c => {
        const o = document.createElement('option');
        o.value = c.key; o.textContent = c.label || c.key;
        sel.appendChild(o);
      });
    });

    // Staty ±1
    root.querySelectorAll('[data-hi-stat]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const ok = await _cheat(heroId, { cmd: 'add stat', stat: btn.dataset.hiStat, value: Number(btn.dataset.hiDelta) });
        if (ok) refresh();
      });
    });

    // Skille — set skill rank
    root.querySelectorAll('[data-hi-save="skill"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const key = btn.dataset.hiSkill;
        const inp = root.querySelector(`[data-hi-skill-input="${CSS.escape(key)}"]`);
        const ok = await _cheat(heroId, { cmd: 'set skill', key, value: Number(inp.value) });
        if (ok) { showToast('Rank zapisany', 'success'); refresh(); }
      });
    });

    // HP
    root.querySelector('[data-hi-save="hp"]')?.addEventListener('click', async () => {
      const ok = await _cheat(heroId, { cmd: 'set health', value: Number(root.querySelector('#hi-hp-input').value) });
      if (ok) refresh();
    });
    root.querySelector('[data-hi-save="hp-max"]')?.addEventListener('click', async () => {
      const ok = await _cheat(heroId, { cmd: 'set health', value: 'max' });
      if (ok) refresh();
    });

    // Mana
    root.querySelector('[data-hi-save="mana"]')?.addEventListener('click', async () => {
      const ok = await _cheat(heroId, { cmd: 'set mana', value: Number(root.querySelector('#hi-mana-input').value) });
      if (ok) refresh();
    });
    root.querySelector('[data-hi-save="mana-max"]')?.addEventListener('click', async () => {
      const ok = await _cheat(heroId, { cmd: 'set mana', value: 'max' });
      if (ok) refresh();
    });

    // Poziom
    root.querySelector('[data-hi-save="level"]')?.addEventListener('click', async () => {
      const ok = await _cheat(heroId, { cmd: 'set level', value: Number(root.querySelector('#hi-level-input').value) });
      if (ok) refresh();
    });

    // Złoto
    root.querySelector('[data-hi-save="gold"]')?.addEventListener('click', async () => {
      const ok = await _cheat(heroId, { cmd: 'set gold', value: Number(root.querySelector('#hi-gold-input').value) });
      if (ok) refresh();
    });

    // XP — grant-mg
    root.querySelector('[data-hi-save="xp"]')?.addEventListener('click', async () => {
      const amount = Number(root.querySelector('#hi-xp-input').value);
      const reason = (root.querySelector('#hi-xp-reason').value || '').trim() || 'inspector';
      if (!amount || amount < 1) { showToast('Podaj dodatnią wartość XP', 'error'); return; }
      const ok = await _grantXp(heroId, full.owner_id, amount, reason);
      if (ok) { showToast(`Przyznano ${amount} XP`, 'success'); refresh(); }
    });

    // Kondycja — dodaj
    root.querySelector('[data-hi-save="cond-add"]')?.addEventListener('click', async () => {
      const key = root.querySelector('#hi-cond-select').value;
      if (!key) { showToast('Wybierz kondycję', 'error'); return; }
      const ok = await _cheat(heroId, { cmd: 'add condition', key });
      if (ok) refresh();
    });
    // Kondycja — usuń
    root.querySelectorAll('[data-hi-cond-remove]').forEach(a => {
      a.addEventListener('click', async e => {
        e.preventDefault();
        const ok = await _cheat(heroId, { cmd: 'remove condition', key: a.dataset.hiCondRemove });
        if (ok) refresh();
      });
    });
  }

  // ── Zakładka Ekwipunek (HI4) — grupowana lista + dodaj/usuń/załóż ─────────────

  function _inventoryHtml() {
    const locked = _editLocked();
    const dis = locked ? 'disabled' : '';
    const inv = Array.isArray(full.inventory) ? full.inventory : [];
    const groups = {};
    inv.forEach(it => { const t = it.item_type || 'item'; (groups[t] = groups[t] || []).push(it); });

    const sections = _ITEM_TYPE_GROUPS.filter(g => (groups[g.key] || []).length).map(g => {
      const rows = groups[g.key].map(it => {
        const d = it.durability;
        const dur = (d && d.max) ? ` <small style="color:var(--t3)">[${d.current ?? '?'}/${d.max}]</small>` : '';
        const eq = it.equipped ? ` <span class="badge" style="background:rgba(120,180,100,.2)">założone${it.slot ? ' · ' + _esc(it.slot) : ''}</span>` : '';
        const qty = (it.quantity && it.quantity > 1) ? ` ×${it.quantity}` : '';
        const canEquip = (it.item_type === 'weapon' || it.item_type === 'armor');
        const equipBtn = canEquip
          ? (it.equipped
              ? `<button class="btn btn-sm" data-hi-unequip="${it.id}" ${dis}>Zdejmij</button>`
              : `<button class="btn btn-sm" data-hi-equip="${it.id}" data-hi-itype="${_esc(it.item_type)}" ${dis}>Załóż</button>`)
          : '';
        const rmKey = it.key || '';
        const rmBtn = rmKey ? `<button class="btn btn-sm" data-hi-item-remove="${_esc(rmKey)}" ${dis}>Usuń</button>` : '';
        return `<div style="display:flex;align-items:center;gap:8px;padding:3px 0">
          <span style="flex:1">${_esc(it.label || it.key || '—')}${qty}${dur}${eq}</span>
          ${equipBtn}${rmBtn}
        </div>`;
      }).join('');
      return `<fieldset style="border:1px solid var(--border);border-radius:8px;padding:8px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">${g.label}</legend>
        <div style="display:grid;gap:2px">${rows}</div>
      </fieldset>`;
    }).join('');
    const empty = inv.length ? '' : '<div style="color:var(--t3);font-size:0.8rem">Ekwipunek pusty.</div>';

    return `<div style="display:grid;gap:14px">
      <fieldset style="border:1px solid var(--border);border-radius:8px;padding:8px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">Dodaj z katalogu</legend>
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <select class="form-input" id="hi-item-select" style="max-width:320px" ${dis}><option value="">— ładowanie katalogu… —</option></select>
          <button class="btn btn-sm" data-hi-item-add ${dis}>Dodaj</button>
        </div>
      </fieldset>
      ${sections}${empty}
    </div>`;
  }

  function _bindInventory() {
    const body = document.getElementById('hero-modal-body');
    if (!body) return;
    _loadItemCatalog().then(cat => {
      const sel = body.querySelector('#hi-item-select');
      if (!sel) return;
      sel.innerHTML = '<option value="">— wybierz przedmiot —</option>';
      const lbl = { weapon: 'Broń', armor: 'Zbroja', item: 'Przedmiot', consumable: 'Konsumpcja' };
      const order = { weapon: 0, armor: 1, item: 2, consumable: 3 };
      const sorted = [...cat].sort((a, b) =>
        (order[a.kind] ?? 9) - (order[b.kind] ?? 9) || String(a.label).localeCompare(String(b.label), 'pl'));
      sorted.forEach(c => {
        const o = document.createElement('option');
        o.value = `${c.kind}|${c.key}`;
        o.textContent = `[${lbl[c.kind] || c.kind}] ${c.label}`;
        sel.appendChild(o);
      });
    });
    body.querySelector('[data-hi-item-add]')?.addEventListener('click', async () => {
      const v = body.querySelector('#hi-item-select').value;
      if (!v) { showToast('Wybierz przedmiot', 'error'); return; }
      const sep = v.indexOf('|');
      const kind = v.slice(0, sep);
      const key = v.slice(sep + 1);
      const ok = await _cheat(heroId, { cmd: 'add item', key, kind });
      if (ok) { showToast('Dodano przedmiot', 'success'); refresh(); }
    });
    body.querySelectorAll('[data-hi-item-remove]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const ok = await _cheat(heroId, { cmd: 'remove item', key: btn.dataset.hiItemRemove });
        if (ok) { showToast('Usunięto przedmiot', 'success'); refresh(); }
      });
    });
    body.querySelectorAll('[data-hi-equip]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const slot = btn.dataset.hiItype === 'armor' ? 'armor' : 'main_hand';
        const ok = await _equip(heroId, Number(btn.dataset.hiEquip), slot);
        if (ok) refresh();
      });
    });
    body.querySelectorAll('[data-hi-unequip]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const ok = await _equip(heroId, Number(btn.dataset.hiUnequip), null);
        if (ok) refresh();
      });
    });
  }

  // ── Zakładka Zaklęcia (HI4) — naucz + awansuj rank ───────────────────────────

  function _spellsHtml() {
    const locked = _editLocked();
    const dis = locked ? 'disabled' : '';
    const spells = Array.isArray(full.spells) ? full.spells : [];
    const rows = spells.length
      ? spells.map(s => {
          const rank = s.rank ?? 1;
          const canUp = rank < 3;
          return `<div style="display:flex;align-items:center;gap:8px;padding:3px 0">
            <span style="flex:1">${_esc(s.label || s.spell_key)} <small style="color:var(--t3)">(rank ${rank}${s.tier ? ', tier ' + s.tier : ''})</small></span>
            ${canUp ? `<button class="btn btn-sm" data-hi-spell-up="${_esc(s.spell_key)}" ${dis}>Awansuj →${rank + 1}</button>` : '<small style="color:var(--t3)">max</small>'}
          </div>`;
        }).join('')
      : '<div style="color:var(--t3);font-size:0.8rem">Bohater nie zna zaklęć.</div>';
    return `<div style="display:grid;gap:14px">
      <fieldset style="border:1px solid var(--border);border-radius:8px;padding:8px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">Naucz zaklęcia</legend>
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <select class="form-input" id="hi-spell-select" style="max-width:320px" ${dis}><option value="">— ładowanie… —</option></select>
          <button class="btn btn-sm" data-hi-spell-learn ${dis}>Naucz</button>
        </div>
      </fieldset>
      <fieldset style="border:1px solid var(--border);border-radius:8px;padding:8px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">Znane zaklęcia (${spells.length})</legend>
        <div style="display:grid;gap:2px">${rows}</div>
      </fieldset>
    </div>`;
  }

  function _bindSpells() {
    const body = document.getElementById('hero-modal-body');
    if (!body) return;
    _loadSpellCatalog().then(cat => {
      const sel = body.querySelector('#hi-spell-select');
      if (!sel) return;
      const known = new Set((full.spells || []).map(s => s.spell_key));
      sel.innerHTML = '<option value="">— wybierz zaklęcie —</option>';
      cat.filter(s => !known.has(s.key)).forEach(s => {
        const o = document.createElement('option');
        o.value = s.key; o.textContent = s.tier ? `${s.label} (tier ${s.tier})` : s.label;
        sel.appendChild(o);
      });
    });
    body.querySelector('[data-hi-spell-learn]')?.addEventListener('click', async () => {
      const key = body.querySelector('#hi-spell-select').value;
      if (!key) { showToast('Wybierz zaklęcie', 'error'); return; }
      const ok = await _spellAction(heroId, 'learn', key);
      if (ok) { showToast('Nauczono zaklęcia', 'success'); refresh(); }
    });
    body.querySelectorAll('[data-hi-spell-up]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const ok = await _spellAction(heroId, 'upgrade', btn.dataset.hiSpellUp);
        if (ok) { showToast('Rank zaklęcia podniesiony', 'success'); refresh(); }
      });
    });
  }

  // ── Zakładka Questy (HI4) — dodaj + zalicz ───────────────────────────────────

  function _questsHtml() {
    const locked = _editLocked();
    const dis = locked ? 'disabled' : '';
    const active = full.quests_active || [];
    const completed = full.quests_completed || [];
    const activeRows = active.length
      ? active.map(q => `<div style="display:flex;align-items:center;gap:8px;padding:3px 0">
          <span style="flex:1">${_esc(q)}</span>
          <button class="btn btn-sm" data-hi-quest-complete="${_esc(q)}" ${dis}>Zalicz ✓</button>
        </div>`).join('')
      : '<div style="color:var(--t3);font-size:0.8rem">Brak aktywnych questów.</div>';
    const compRows = completed.length
      ? completed.map(q => `<div style="padding:3px 0;color:var(--t3)">✓ ${_esc(q)}</div>`).join('')
      : '<div style="color:var(--t3);font-size:0.8rem">Brak ukończonych.</div>';
    return `<div style="display:grid;gap:14px">
      <fieldset style="border:1px solid var(--border);border-radius:8px;padding:8px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">Dodaj quest</legend>
        <div style="display:flex;align-items:center;gap:8px">
          <input type="text" class="form-input" id="hi-quest-input" placeholder="klucz questa (np. quest_intro)" style="max-width:280px" ${dis}>
          <button class="btn btn-sm" data-hi-quest-add ${dis}>Dodaj</button>
        </div>
      </fieldset>
      <fieldset style="border:1px solid var(--border);border-radius:8px;padding:8px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">Aktywne (${active.length})</legend>
        <div style="display:grid;gap:2px">${activeRows}</div>
      </fieldset>
      <fieldset style="border:1px solid var(--border);border-radius:8px;padding:8px 12px">
        <legend style="font-size:0.78rem;color:var(--t2);padding:0 6px">Ukończone (${completed.length})</legend>
        <div style="display:grid;gap:2px">${compRows}</div>
      </fieldset>
    </div>`;
  }

  function _bindQuests() {
    const body = document.getElementById('hero-modal-body');
    if (!body) return;
    body.querySelector('[data-hi-quest-add]')?.addEventListener('click', async () => {
      const key = (body.querySelector('#hi-quest-input').value || '').trim();
      if (!key) { showToast('Podaj klucz questa', 'error'); return; }
      const ok = await _cheat(heroId, { cmd: 'quest add', key });
      if (ok) { showToast('Quest dodany', 'success'); refresh(); }
    });
    body.querySelectorAll('[data-hi-quest-complete]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const ok = await _cheat(heroId, { cmd: 'quest complete', key: btn.dataset.hiQuestComplete });
        if (ok) { showToast('Quest zaliczony', 'success'); refresh(); }
      });
    });
  }

  function _renderTab(tab) {
    _activeTab = tab;
    const body = document.getElementById('hero-modal-body');
    if (!body) return;
    if (tab === 'sheet') { body.innerHTML = _sheetHtml(); _bindSheet(); }
    else if (tab === 'inventory') { body.innerHTML = _inventoryHtml(); _bindInventory(); }
    else if (tab === 'spells') { body.innerHTML = _spellsHtml(); _bindSpells(); }
    else if (tab === 'quests') { body.innerHTML = _questsHtml(); _bindQuests(); }
  }

  // Pierwsze ładowanie
  try {
    await _fetchFull();
  } catch (e) {
    document.getElementById('hero-modal-body').innerHTML =
      `<div style="text-align:center;padding:24px;color:var(--red)">Błąd ładowania: ${_esc(e.message)}</div>`;
    return;
  }

  document.getElementById('hero-modal-title').textContent =
    `${full.name || 'Bohater'} — ${_ARCHETYPE_LABEL[full.archetype] || full.archetype || '?'} (poz. ${full.level})`;
  _renderBanners();
  _renderTab('sheet');

  overlay.querySelectorAll('[data-htab]').forEach(btn => {
    btn.addEventListener('click', () => {
      overlay.querySelectorAll('[data-htab]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _renderTab(btn.dataset.htab);
    });
  });
}

// ── Init ───────────────────────────────────────────────────────────────────

export async function init(panel) {
  _heroes = []; _statusFilter = 'all'; _search = '';
  panel.innerHTML = `
    <div id="section-heroes">
      <div class="section-head" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px">
        <h2 style="margin:0">Bohaterowie</h2>
        <div class="filter-group" id="heroes-status-filter" style="display:flex;gap:4px">
          <button class="chip on" data-status="all">Wszyscy</button>
          <button class="chip" data-status="idle">Wolni</button>
          <button class="chip" data-status="playing">W grze</button>
        </div>
        <input id="heroes-search" class="form-input" placeholder="Szukaj po imieniu / właścicielu…" style="max-width:260px">
        <button class="btn" id="heroes-refresh" style="margin-left:auto">↻ Odśwież</button>
      </div>
      <table class="data-table" id="heroes-table">
        <thead><tr>
          <th>Imię</th><th>Archetyp</th><th>Poziom</th><th>Właściciel</th><th>Status</th><th>Kampania</th><th>HP</th><th></th>
        </tr></thead>
        <tbody id="heroes-tbody"></tbody>
      </table>
    </div>`;

  panel.querySelectorAll('#heroes-status-filter .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      panel.querySelectorAll('#heroes-status-filter .chip').forEach(c => c.classList.remove('on'));
      chip.classList.add('on');
      _statusFilter = chip.dataset.status;
      _renderRows();
    });
  });
  panel.querySelector('#heroes-search').addEventListener('input', e => {
    _search = e.target.value.toLowerCase().trim();
    _renderRows();
  });
  panel.querySelector('#heroes-refresh').addEventListener('click', _loadList);

  await _loadList();
}
