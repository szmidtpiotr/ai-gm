/**
 * FADM-P7 (#409) — Dungeons section (modular admin/).
 * Port of section-dungeons from admin_panel_v3/index.html.
 * Exported: init(panel).
 */
import { apiFetch }  from '../shared/api.js';
import { showToast } from '../shared/toast.js';

// ─── Module-local helpers ────────────────────────────────────────────────────
function _esc(s) { return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function _loading(n=3) { return `<tr><td colspan="${n}" style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</td></tr>`; }
function _errRow(n, msg) { return `<tr><td colspan="${n}" style="text-align:center;padding:24px;color:var(--red)">${_esc(msg)}</td></tr>`; }
function _showToast(msg, type) { showToast(msg, type); }
function filterTableGeneric(input, tableId, nameClass) {
  const q = input.value.toLowerCase();
  document.querySelectorAll(`#${tableId} tbody tr`).forEach(row => {
    const name = row.querySelector(`.${nameClass}`)?.textContent.toLowerCase() || '';
    row.style.display = name.includes(q) ? '' : 'none';
  });
}

// ─── Section HTML ─────────────────────────────────────────────────────────────
function _sectionHtml() { return `
    <div id="section-dungeons">
      <div class="section-header">
        <div>
          <div class="section-heading">Lochy</div>
          <div class="section-sub">Farmowalne lokacje niezależne od kampanii</div>
        </div>
        <div style="display:flex;gap:8px" id="dungeons-header-btns">
          <button class="btn btn-primary btn-sm" onclick="openNewDungeonModal()">+ Nowy loch</button>
        </div>
      </div>

      <div class="card">
        <div class="stab-bar" id="dungeons-stab-bar">
          <button class="stab active" data-dtab="dungeons">Lochy</button>
          <button class="stab" data-dtab="riddles">Zagadki</button>
          <button class="stab" data-dtab="tiles">Kafelki</button>
          <button class="stab" data-dtab="tilecats">Kategorie</button>
        </div>

        <!-- Lochy tab -->
        <div class="stab-panel active" id="dtab-dungeons">
        <div class="toolbar">
          <div class="search-box">
            <span class="search-box-icon">🔍</span>
            <input type="text" placeholder="Szukaj lochu…" oninput="filterTableGeneric(this,'dungeons-table','td-name')">
          </div>
          <div class="filter-group">
            <button class="chip on" onclick="filterDungeons(this,'')">Wszystkie</button>
            <button class="chip" onclick="filterDungeons(this,'aktywne')">Aktywne</button>
            <button class="chip" onclick="filterDungeons(this,'w przygotowaniu')">W przygotowaniu</button>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table" id="dungeons-table">
            <thead>
              <tr>
                <th class="col-check"><input type="checkbox" onchange="toggleAll('dung', this)"></th>
                <th class="td-sticky"><div class="th-inner sorted">Klucz <span class="sort-icon asc">▲</span></div></th>
                <th><div class="th-inner">Nazwa</div></th>
                <th><div class="th-inner">Poz. wrogów</div></th>
                <th><div class="th-inner">Pokoje <span class="sort-icon">▲</span></div></th>
                <th><div class="th-inner">Tier łupów</div></th>
                <th><div class="th-inner">Cooldown</div></th>
                <th><div class="th-inner">Aktywne biegi</div></th>
                <th><div class="th-inner">Status</div></th>
                <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="col-check"><input type="checkbox" class="dung-row-check" onchange="rowCheck('dung')"></td>
                <td class="td-sticky td-mono">dungeon_goblin_warren</td>
                <td class="td-name">Nory Goblinów</td>
                <td class="td-muted">1–3</td>
                <td class="td-mono editable" onclick="startEdit(this)">5</td>
                <td><span class="badge badge-green">common</span></td>
                <td class="td-mono editable" onclick="startEdit(this)">8h</td>
                <td class="td-mono">2</td>
                <td><span class="badge badge-green">● Aktywny</span></td>
                <td class="td-actions"><button class="btn-icon" title="Edytuj">✎</button> <button class="btn-icon danger">✕</button></td>
              </tr>
              <tr>
                <td class="col-check"><input type="checkbox" class="dung-row-check" onchange="rowCheck('dung')"></td>
                <td class="td-sticky td-mono">dungeon_crypt</td>
                <td class="td-name">Krypta Umarłych</td>
                <td class="td-muted">4–6</td>
                <td class="td-mono editable" onclick="startEdit(this)">8</td>
                <td><span class="badge badge-blue">uncommon</span></td>
                <td class="td-mono editable" onclick="startEdit(this)">12h</td>
                <td class="td-mono">1</td>
                <td><span class="badge badge-green">● Aktywny</span></td>
                <td class="td-actions"><button class="btn-icon" title="Edytuj">✎</button> <button class="btn-icon danger">✕</button></td>
              </tr>
              <tr>
                <td class="col-check"><input type="checkbox" class="dung-row-check" onchange="rowCheck('dung')"></td>
                <td class="td-sticky td-mono">dungeon_wizard_tower</td>
                <td class="td-name">Wieża Maga</td>
                <td class="td-muted">7–9</td>
                <td class="td-mono editable" onclick="startEdit(this)">10</td>
                <td><span class="badge badge-amber">rare</span></td>
                <td class="td-mono editable" onclick="startEdit(this)">24h</td>
                <td class="td-mono">0</td>
                <td><span class="badge badge-green">● Aktywny</span></td>
                <td class="td-actions"><button class="btn-icon" title="Edytuj">✎</button> <button class="btn-icon danger">✕</button></td>
              </tr>
              <tr>
                <td class="col-check"><input type="checkbox" class="dung-row-check" onchange="rowCheck('dung')"></td>
                <td class="td-sticky td-mono">dungeon_dragon_lair</td>
                <td class="td-name">Jaskinia Smoka</td>
                <td class="td-muted">10–12</td>
                <td class="td-mono editable" onclick="startEdit(this)">6</td>
                <td><span class="badge badge-red">epic</span></td>
                <td class="td-mono editable" onclick="startEdit(this)">48h</td>
                <td class="td-mono">0</td>
                <td><span class="badge badge-slate">○ Wkrótce</span></td>
                <td class="td-actions"><button class="btn-icon" title="Edytuj">✎</button> <button class="btn-icon danger">✕</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="pagination"><span id="dungeons-count">—</span></div>
        </div><!-- /dtab-dungeons -->

        <!-- Zagadki tab -->
        <div class="stab-panel" id="dtab-riddles">
          <div class="toolbar">
            <div class="search-box">
              <span class="search-box-icon">🔍</span>
              <input type="text" placeholder="Szukaj zagadki…" oninput="filterTableGeneric(this,'riddles-table','td-name')">
            </div>
            <div class="filter-group">
              <button class="chip on" onclick="filterRiddles(this,'')">Wszystkie</button>
              <button class="chip" onclick="filterRiddles(this,'1')">Łatwe</button>
              <button class="chip" onclick="filterRiddles(this,'2')">Średnie</button>
              <button class="chip" onclick="filterRiddles(this,'3')">Trudne</button>
            </div>
          </div>
          <div class="table-wrap">
            <table class="data-table" id="riddles-table">
              <thead><tr>
                <th class="td-sticky"><div class="th-inner">Treść</div></th>
                <th><div class="th-inner">Odpowiedź</div></th>
                <th><div class="th-inner">Motyw</div></th>
                <th><div class="th-inner">Trudność</div></th>
                <th><div class="th-inner">Podpowiedzi</div></th>
                <th><div class="th-inner">Aktywna</div></th>
                <th><div class="th-inner" style="justify-content:flex-end">Akcje</div></th>
              </tr></thead>
              <tbody><tr><td colspan="7" style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</td></tr></tbody>
            </table>
          </div>
          <div class="pagination"><span id="riddles-count">—</span></div>
        </div><!-- /dtab-riddles -->

        <!-- Kafelki tab (Dungeon Tile Card System, issue #224) -->
        <div class="stab-panel" id="dtab-tiles">
          <div class="toolbar" style="flex-wrap:wrap;gap:10px">
            <div class="search-box"><span class="search-box-icon">🔍</span>
              <input type="text" id="tile-search" placeholder="Szukaj kafelka…" oninput="_filterTiles()">
            </div>
            <div class="filter-group" id="tile-cat-filter">
              <button class="chip on" data-cat="">Wszystkie</button>
              <!-- categories populated by JS -->
            </div>
            <label style="display:flex;align-items:center;gap:6px;font-size:.78rem;color:var(--t3);cursor:pointer;margin-left:auto">
              <input type="checkbox" id="tile-show-inactive" onchange="_renderTilesGrid()">
              Pokaż nieaktywne
            </label>
            <span class="td-muted" style="font-size:0.78rem" id="tiles-count-info">—</span>
            <button id="tile-ai-gen-btn" class="btn btn-secondary btn-sm" onclick="_aiGenerateTile()" style="display:none;margin-left:6px">✨ Generuj kafelek AI</button>
          </div>
          <div id="tiles-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:14px;padding:8px 4px">
            <div style="grid-column:1/-1;text-align:center;padding:32px;color:var(--t3)">Ładowanie…</div>
          </div>
        </div><!-- /dtab-tiles -->

        <!-- Kategorie tab -->
        <div class="stab-panel" id="dtab-tilecats">
          <div class="table-wrap">
            <table class="data-table" id="tilecats-table">
              <thead><tr>
                <th>Klucz</th><th>Nazwa</th><th>Opis</th><th>Styl prompt</th>
                <th>Aktywna</th><th class="td-actions">Akcje</th>
              </tr></thead>
              <tbody><tr><td colspan="6" style="text-align:center;padding:24px;color:var(--t3)">Ładowanie…</td></tr></tbody>
            </table>
          </div>
        </div><!-- /dtab-tilecats -->

      </div>
    </div>
`; }

// ─── Filter ───────────────────────────────────────────────────────────────────
  function filterDungeons(chip, status) {
    document.querySelectorAll('#section-dungeons .filter-group .chip').forEach(c => c.classList.remove('on'));
    chip.classList.add('on');
    document.querySelectorAll('#dungeons-table tbody tr').forEach(row => {
      if (!status) { row.style.display = ''; return; }
      const allBadges = [...row.querySelectorAll('.badge')].map(b=>b.textContent.toLowerCase()).join(' ');
      const statusMap = { 'aktywne': 'aktywny', 'w przygotowaniu': 'nieaktywny' };
      row.style.display = allBadges.includes(statusMap[status] || status) ? '' : 'none';
    });
  }

// ─── Dungeon functions ────────────────────────────────────────────────────────
  async function _dungeonTileCatOptions(selected) {
    try {
      const d = await apiFetch('/api/admin/dungeon-tile-categories');
      const cats = d.categories || d.items || [];
      return `<option value="">— (tryb proceduralny) —</option>` +
        cats.map(c=>`<option value="${_esc(c.key)}" ${c.key===selected?'selected':''}>${_esc(c.label)} (${_esc(c.key)})</option>`).join('');
    } catch { return `<option value="">— błąd ładowania kategorii —</option>`; }
  }

  async function _dungeonBossTileOptions(categoryKey, selectedId) {
    if (!categoryKey) return `<option value="">— wybierz kategorię —</option>`;
    try {
      const d = await apiFetch(`/api/admin/dungeon-tiles?category_key=${encodeURIComponent(categoryKey)}&include_inactive=false`);
      const tiles = (d.tiles || d.items || []).filter(t => t.is_boss_tile);
      if (!tiles.length) return `<option value="">— brak kafelków boss w kategorii —</option>`;
      return `<option value="">Losowy boss z kategorii</option>` +
        tiles.map(t=>`<option value="${t.id}" ${t.id==selectedId?'selected':''}>${_esc(t.label)}</option>`).join('');
    } catch { return `<option value="">— błąd ładowania —</option>`; }
  }

  function _dungeonModeToggle(prefix) {
    const cat = document.getElementById(`${prefix}-tile-cat`)?.value || '';
    const tileSection = document.getElementById(`${prefix}-tile-section`);
    const legacySection = document.getElementById(`${prefix}-legacy-section`);
    if (tileSection) tileSection.style.display = cat ? '' : 'none';
    if (legacySection) legacySection.style.display = cat ? 'none' : '';
  }

  async function openNewDungeonModal() {
    const catOpts = await _dungeonTileCatOptions('');
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `<div class="modal-box" style="width:600px">
      <div class="modal-head"><span class="modal-title">Nowy loch</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
      <div class="modal-body" style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div class="form-row" style="grid-column:1/-1"><label class="form-label">Klucz * (snake_case)</label><input id="nd-key" class="form-input form-mono" placeholder="np. dungeon_forest"></div>
        <div class="form-row" style="grid-column:1/-1"><label class="form-label">Nazwa *</label><input id="nd-label" class="form-input" placeholder="Leśna Jaskinia"></div>
        <div class="form-row" style="grid-column:1/-1"><label class="form-label">Klucz lokacji</label><input id="nd-loc" class="form-input form-mono" placeholder="Zostaw puste = jak klucz lochu"></div>
        <div class="form-row"><label class="form-label">Min. poziom</label><input id="nd-lvl" class="form-input" type="number" value="1" min="1" max="20"></div>
        <div class="form-row"><label class="form-label">Cooldown (h)</label><input id="nd-cool" class="form-input" type="number" value="72" min="1" max="720"></div>
        <div class="form-row" style="grid-column:1/-1"><label class="form-label">Atmosfera</label><textarea id="nd-atmo" class="form-input" rows="2" placeholder="Ciasne tunele, smród gnijącego mięsa…"></textarea></div>

        <div class="form-row" style="grid-column:1/-1;border-top:1px solid var(--accent);padding-top:8px;margin-top:4px">
          <label class="form-label" style="font-weight:700;color:var(--accent)">🗺 Tryb Kafelkowy</label>
          <span style="font-size:0.75rem;color:var(--t3);display:block;margin-top:2px">Wybierz kategorię kafelków aby włączyć tryb kafelkowy. Pozostaw puste dla trybu proceduralnego (stary system).</span>
        </div>
        <div class="form-row" style="grid-column:1/-1"><label class="form-label">Kategoria kafelków</label>
          <select id="nd-tile-cat" class="form-input" onchange="_dungeonModeToggle('nd'); _ndReloadBossTiles()">${catOpts}</select>
        </div>

        <div id="nd-tile-section" style="display:none;grid-column:1/-1;display:none">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
            <div class="form-row"><label class="form-label">Liczba kafelków (bez bossa)</label><input id="nd-tile-count" class="form-input" type="number" value="3" min="1" max="20" placeholder="3"></div>
            <div class="form-row"><label class="form-label">Kafelek boss</label>
              <select id="nd-boss-tile" class="form-input"><option value="">Losowy boss z kategorii</option></select>
            </div>
          </div>
        </div>

        <div id="nd-legacy-section" style="grid-column:1/-1">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
            <div class="form-row" style="grid-column:1/-1"><label class="form-label" style="color:var(--t3)">Pokoje (1–20)</label><input id="nd-rooms" class="form-input" type="number" value="5" min="1" max="20"></div>
            <div class="form-row"><label class="form-label" style="color:var(--t3)">Jakość łupów</label>
              <select id="nd-loot" class="form-input">
                <option value="poor">Słabe</option><option value="standard" selected>Standardowe</option><option value="rich">Bogate</option>
              </select>
            </div>
            <div class="form-row" style="grid-column:1/-1"><label class="form-label" style="color:var(--t3)">Pula wrogów (klucze oddzielone przecinkami)</label><input id="nd-pool" class="form-input form-mono" placeholder='goblin_warrior,skeleton_archer'></div>
            <div class="form-row" style="grid-column:1/-1"><label class="form-label" style="color:var(--t3)">Boss (klucz wroga)</label><input id="nd-boss" class="form-input form-mono" placeholder="goblin_shaman"></div>
            <div class="form-row"><label class="form-label" style="color:var(--t3)">Łupy ze skrzyń</label><input id="nd-chest" class="form-input form-mono"></div>
            <div class="form-row"><label class="form-label" style="color:var(--t3)">Łupy z bossa</label><input id="nd-bloot" class="form-input form-mono"></div>
            <div class="form-row"><label class="form-label" style="color:var(--t3)">Szansa łupu z komnaty</label><input id="nd-rloot" class="form-input" type="number" value="0.15" min="0" max="1" step="0.05"></div>
          </div>
        </div>

        <div class="form-row" style="grid-column:1/-1;display:flex;align-items:center;gap:8px;border-top:1px solid var(--border);padding-top:8px;margin-top:4px">
          <input type="checkbox" id="nd-active" checked style="margin:0">
          <label for="nd-active" class="form-label" style="margin:0;cursor:pointer">Aktywny</label>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
        <button class="btn btn-primary" onclick="_doCreateDungeon(this)">Utwórz loch</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#nd-key').focus();
  }

  async function _ndReloadBossTiles() {
    const cat = document.getElementById('nd-tile-cat')?.value || '';
    const sel = document.getElementById('nd-boss-tile');
    if (!sel) return;
    sel.innerHTML = await _dungeonBossTileOptions(cat, null);
    _dungeonModeToggle('nd');
  }

  async function _doCreateDungeon(btn) {
    const g = id => document.getElementById(id);
    const key = g('nd-key')?.value?.trim();
    const label = g('nd-label')?.value?.trim();
    if (!key || !label) { _showToast('Klucz i nazwa są wymagane.','error'); return; }
    const tileMode = !!(g('nd-tile-cat')?.value);
    const poolRaw = g('nd-pool')?.value?.trim() || '';
    const enemy_pool = poolRaw ? JSON.stringify(poolRaw.split(',').map(s=>s.trim()).filter(Boolean)) : '[]';
    const body = { key, label,
      location_key: g('nd-loc')?.value?.trim() || key,
      min_level: parseInt(g('nd-lvl')?.value)||1,
      cooldown_hours: parseInt(g('nd-cool')?.value)||72,
      atmosphere: g('nd-atmo')?.value?.trim()||null,
      is_active: g('nd-active')?.checked ? 1 : 0,
      tile_category_key: g('nd-tile-cat')?.value || null,
      tile_count: tileMode ? (parseInt(g('nd-tile-count')?.value)||3) : null,
      boss_tile_id: tileMode ? (parseInt(g('nd-boss-tile')?.value)||null) : null,
      // legacy fields
      rooms: tileMode ? 5 : (parseInt(g('nd-rooms')?.value)||5),
      loot_tier: tileMode ? 'standard' : (g('nd-loot')?.value||'standard'),
      enemy_pool: tileMode ? '[]' : enemy_pool,
      boss_enemy: tileMode ? null : (g('nd-boss')?.value?.trim()||null),
      chest_loot_table_key: tileMode ? null : (g('nd-chest')?.value?.trim()||null),
      boss_loot_table_key: tileMode ? null : (g('nd-bloot')?.value?.trim()||null),
      room_loot_chance: tileMode ? 0.15 : (parseFloat(g('nd-rloot')?.value)||0.15),
      riddle_source: 'database', riddle_max_hints: 2,
    };
    btn.disabled = true; btn.textContent = '⏳';
    try {
      await apiFetch('/api/admin/dungeons', { method:'POST', body: JSON.stringify(body) });
      _showToast('Loch utworzony.','success');
      btn.closest('.modal-overlay').remove();
      _loadDungeons();
    } catch(e) { _showToast(e.message||'Błąd.','error'); btn.disabled = false; btn.textContent = 'Utwórz loch'; }
  }

  async function deleteDungeon(key, btn) {
    if (!confirm(`Usunąć loch "${key}"?`)) return;
    btn.disabled = true;
    try {
      await apiFetch(`/api/admin/dungeons/${key}`, { method:'DELETE' });
      _showToast('Loch usunięty.','success');
      _loadDungeons();
    } catch(e) { _showToast(e.message||'Błąd.','error'); btn.disabled = false; }
  }

  async function openEditDungeonModal(dg) {
    const poolArr = (() => { try { const p = typeof dg.enemy_pool==='string' ? JSON.parse(dg.enemy_pool||'[]') : (dg.enemy_pool||[]); return p.join(','); } catch { return ''; } })();
    const selLoot = ['poor','standard','rich'].map(v=>`<option value="${v}" ${(dg.loot_tier||'standard')===v?'selected':''}>${{poor:'Słabe',standard:'Standardowe',rich:'Bogate'}[v]}</option>`).join('');
    const catOpts = await _dungeonTileCatOptions(dg.tile_category_key||'');
    const bossOpts = await _dungeonBossTileOptions(dg.tile_category_key||'', dg.boss_tile_id);
    const isTile = !!(dg.tile_category_key);
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `<div class="modal-box" style="width:600px">
      <div class="modal-head"><span class="modal-title">Edytuj: ${_esc(dg.label||dg.key)}</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
      <div class="modal-body" style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div class="form-row" style="grid-column:1/-1"><label class="form-label">Klucz</label><input class="form-input form-mono" value="${_esc(dg.key)}" disabled></div>
        <div class="form-row" style="grid-column:1/-1"><label class="form-label">Nazwa</label><input id="ed-label" class="form-input" value="${_esc(dg.label||'')}"></div>
        <div class="form-row" style="grid-column:1/-1"><label class="form-label">Klucz lokacji</label><input id="ed-loc" class="form-input form-mono" value="${_esc(dg.location_key||'')}"></div>
        <div class="form-row"><label class="form-label">Min. poziom</label><input id="ed-lvl" class="form-input" type="number" value="${dg.min_level||1}" min="1" max="20"></div>
        <div class="form-row"><label class="form-label">Cooldown (h)</label><input id="ed-cool" class="form-input" type="number" value="${dg.cooldown_hours||72}" min="1" max="720"></div>
        <div class="form-row"><label class="form-label">Trudność (D1–D5)</label><input id="ed-diff" class="form-input" type="number" value="${dg.dungeon_difficulty||1}" min="1" max="5"></div>
        <div class="form-row" style="grid-column:1/-1"><label class="form-label">Atmosfera</label><textarea id="ed-atmo" class="form-input" rows="2">${_esc(dg.atmosphere||'')}</textarea></div>

        <div class="form-row" style="grid-column:1/-1;border-top:1px solid var(--accent);padding-top:8px;margin-top:4px">
          <label class="form-label" style="font-weight:700;color:var(--accent)">🗺 Tryb Kafelkowy</label>
        </div>
        <div class="form-row" style="grid-column:1/-1"><label class="form-label">Kategoria kafelków</label>
          <select id="ed-tile-cat" class="form-input" onchange="_dungeonModeToggle('ed'); _edReloadBossTiles()">${catOpts}</select>
        </div>

        <div id="ed-tile-section" style="${isTile?'':'display:none;'}grid-column:1/-1">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
            <div class="form-row"><label class="form-label">Liczba kafelków (bez bossa)</label><input id="ed-tile-count" class="form-input" type="number" value="${dg.tile_count||3}" min="1" max="20"></div>
            <div class="form-row"><label class="form-label">Kafelek boss</label>
              <select id="ed-boss-tile" class="form-input">${bossOpts}</select>
            </div>
          </div>
        </div>

        <div id="ed-legacy-section" style="${isTile?'display:none;':''}grid-column:1/-1">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
            <div class="form-row" style="grid-column:1/-1"><label class="form-label" style="color:var(--t3)">Pokoje (1–20)</label><input id="ed-rooms" class="form-input" type="number" value="${dg.rooms||5}" min="1" max="20"></div>
            <div class="form-row"><label class="form-label" style="color:var(--t3)">Jakość łupów</label><select id="ed-loot" class="form-input">${selLoot}</select></div>
            <div class="form-row" style="grid-column:1/-1"><label class="form-label" style="color:var(--t3)">Pula wrogów (klucze oddzielone przecinkami)</label><input id="ed-pool" class="form-input form-mono" value="${_esc(poolArr)}"></div>
            <div class="form-row" style="grid-column:1/-1"><label class="form-label" style="color:var(--t3)">Boss (klucz wroga)</label><input id="ed-boss" class="form-input form-mono" value="${_esc(dg.boss_enemy||'')}"></div>
            <div class="form-row"><label class="form-label" style="color:var(--t3)">Łupy ze skrzyń</label><input id="ed-chest" class="form-input form-mono" value="${_esc(dg.chest_loot_table_key||'')}"></div>
            <div class="form-row"><label class="form-label" style="color:var(--t3)">Łupy z bossa</label><input id="ed-bloot" class="form-input form-mono" value="${_esc(dg.boss_loot_table_key||'')}"></div>
            <div class="form-row"><label class="form-label" style="color:var(--t3)">Szansa łupu z komnaty</label><input id="ed-rloot" class="form-input" type="number" value="${dg.room_loot_chance??0.15}" min="0" max="1" step="0.05"></div>
          </div>
        </div>

        <div class="form-row" style="grid-column:1/-1;display:flex;align-items:center;gap:8px;border-top:1px solid var(--border);padding-top:8px;margin-top:4px">
          <input type="checkbox" id="ed-active" ${dg.is_active?'checked':''} style="margin:0">
          <label for="ed-active" class="form-label" style="margin:0;cursor:pointer">Aktywny</label>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
        <button class="btn btn-primary" onclick="_doSaveDungeon('${_esc(dg.key)}',this)">Zapisz</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);
  }

  async function _edReloadBossTiles() {
    const cat = document.getElementById('ed-tile-cat')?.value || '';
    const sel = document.getElementById('ed-boss-tile');
    if (!sel) return;
    sel.innerHTML = await _dungeonBossTileOptions(cat, null);
    _dungeonModeToggle('ed');
  }

  async function _doSaveDungeon(key, btn) {
    const g = id => document.getElementById(id);
    const tileMode = !!(g('ed-tile-cat')?.value);
    const poolRaw = g('ed-pool')?.value?.trim() || '';
    const enemy_pool = JSON.stringify(poolRaw ? poolRaw.split(',').map(s=>s.trim()).filter(Boolean) : []);
    const body = {
      label: g('ed-label')?.value?.trim(),
      location_key: g('ed-loc')?.value?.trim()||key,
      min_level: parseInt(g('ed-lvl')?.value)||1,
      cooldown_hours: parseInt(g('ed-cool')?.value)||72,
      dungeon_difficulty: parseInt(g('ed-diff')?.value)||1,
      is_active: g('ed-active')?.checked ? 1 : 0,
      atmosphere: g('ed-atmo')?.value?.trim()||null,
      tile_category_key: g('ed-tile-cat')?.value || null,
      tile_count: tileMode ? (parseInt(g('ed-tile-count')?.value)||3) : null,
      boss_tile_id: tileMode ? (parseInt(g('ed-boss-tile')?.value)||null) : null,
      rooms: tileMode ? 5 : (parseInt(g('ed-rooms')?.value)||5),
      loot_tier: tileMode ? 'standard' : (g('ed-loot')?.value||'standard'),
      enemy_pool: tileMode ? '[]' : enemy_pool,
      boss_enemy: tileMode ? null : (g('ed-boss')?.value?.trim()||null),
      chest_loot_table_key: tileMode ? null : (g('ed-chest')?.value?.trim()||null),
      boss_loot_table_key: tileMode ? null : (g('ed-bloot')?.value?.trim()||null),
      room_loot_chance: tileMode ? 0.15 : (parseFloat(g('ed-rloot')?.value)||0.15),
      riddle_source: 'database', riddle_max_hints: 2,
    };
    btn.disabled = true; btn.textContent = '⏳';
    try {
      await apiFetch(`/api/admin/dungeons/${key}`, { method:'PATCH', body: JSON.stringify(body) });
      _showToast('Zapisano.','success');
      btn.closest('.modal-overlay').remove();
      _loadDungeons();
    } catch(e) { _showToast(e.message||'Błąd.','error'); btn.disabled = false; btn.textContent = 'Zapisz'; }
  }

  async function _loadDungeons() {
    const tbody = document.querySelector('#dungeons-table tbody');
    if (!tbody) return;
    tbody.innerHTML = _loading(10);
    try {
      const d = await apiFetch('/api/admin/dungeons');
      const items = d.items || [];
      if (!items.length) { tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:24px;color:var(--t3)">Brak lochów</td></tr>`; return; }
      const tierBadge = t => ({common:'badge-green',uncommon:'badge-blue',rare:'badge-amber',epic:'badge-red',legendary:'badge-red'}[t]||'badge-slate');
      tbody.innerHTML = items.map(dg => `<tr>
        <td class="col-check"><input type="checkbox" class="dung-row-check" onchange="rowCheck('dung')"></td>
        <td class="td-sticky td-mono">${_esc(dg.key)}</td>
        <td class="td-name">${_esc(dg.label||dg.key)}</td>
        <td class="td-muted">${dg.min_level?dg.min_level+'+':'—'}</td>
        <td>${dg.tile_category_key ? `<span class="badge badge-blue" title="Tryb kafelkowy: ${_esc(dg.tile_category_key)}">🗺 ${_esc(dg.tile_category_key)}</span>` : `<span class="badge badge-slate" title="Tryb proceduralny">⚙ ${dg.rooms??'?'}p</span>`}</td>
        <td class="td-mono editable" onclick="startEdit(this)">${dg.cooldown_hours?dg.cooldown_hours+'h':'—'}</td>
        <td class="td-mono">${dg.active_runs ?? dg.active_runs_count ?? dg.runs_active ?? '—'}</td>
        <td><span class="badge ${dg.is_active?'badge-green':'badge-slate'}">${dg.is_active?'● Aktywny':'○ Nieaktywny'}</span></td>
        <td class="td-actions"><button class="btn-icon" title="Edytuj" onclick="openEditDungeonModal(${JSON.stringify(dg).replace(/"/g,'&quot;')})">✎</button> <button class="btn-icon danger" title="Usuń" onclick="deleteDungeon('${_esc(dg.key)}',this)">✕</button></td>
      </tr>`).join('');
      const pg = document.getElementById('dungeons-count');
      if (pg) pg.textContent = `${items.length} lochów`;
    } catch(e) { tbody.innerHTML = _errRow(10, e.message); }
  }


// ─── Dungeon Tiles ────────────────────────────────────────────────────────────
  const IMAGE_GEN_DEFAULT_MODEL = 'flux1-schnell-Q5_K_S.gguf';
  let _tileCategoriesCache = null;
  let _tilesCache = [];
  let _tileEnemyImgCache = {};  // key → image_url, used by tile grid card overlay render

  async function _ensureTileCategories(force) {
    if (_tileCategoriesCache && !force) return _tileCategoriesCache;
    const d = await apiFetch('/api/admin/dungeon-tile-categories');
    _tileCategoriesCache = d.categories || [];
    return _tileCategoriesCache;
  }

  async function _loadDungeonTiles() {
    const grid = document.getElementById('tiles-grid');
    const filter = document.getElementById('tile-cat-filter');
    if (!grid) return;
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:32px;color:var(--t3)">Ładowanie…</div>';
    try {
      const cats = await _ensureTileCategories();
      if (filter) {
        filter.innerHTML = '<button class="chip on" data-cat="">Wszystkie</button>' +
          cats.map(c => `<button class="chip" data-cat="${_esc(c.key)}">${_esc(c.label)}</button>`).join('');
        filter.querySelectorAll('.chip').forEach(b => b.addEventListener('click', () => {
          filter.querySelectorAll('.chip').forEach(x => x.classList.remove('on'));
          b.classList.add('on');
          _renderTilesGrid();
        }));
      }
      const [r, er] = await Promise.all([
        apiFetch('/api/admin/dungeon-tiles?include_inactive=true'),
        apiFetch('/api/admin/enemies').catch(()=>({items:[]})),
      ]);
      _tilesCache = r.tiles || [];
      _tileEnemyImgCache = Object.fromEntries((er.items||[]).filter(e=>e.image_url).map(e=>[e.key, e.image_url]));
      _renderTilesGrid();
    } catch (e) {
      grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:32px;color:#ef4444">Błąd: ${_esc(e.message)}</div>`;
    }
  }

  function _renderTilesGrid() {
    const grid = document.getElementById('tiles-grid');
    if (!grid) return;
    const activeCat = document.querySelector('#tile-cat-filter .chip.on')?.dataset.cat || '';
    const q = (document.getElementById('tile-search')?.value || '').toLowerCase().trim();
    const showInactive = document.getElementById('tile-show-inactive')?.checked;
    const list = _tilesCache.filter(t =>
      (showInactive || t.is_active !== false) &&
      (!activeCat || t.category_key === activeCat) &&
      (!q || (t.label || '').toLowerCase().includes(q))
    );
    const info = document.getElementById('tiles-count-info');
    if (info) info.textContent = `${list.length}/${_tilesCache.length} kafli`;
    const aiBtn = document.getElementById('tile-ai-gen-btn');
    if (aiBtn) aiBtn.style.display = activeCat ? '' : 'none';
    if (!list.length) {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:32px;color:var(--t3)">Brak kafli — kliknij „+ Nowy kafelek"</div>';
      return;
    }
    grid.innerHTML = list.map(t => _renderTileCard(t)).join('');
  }

  function _renderTileCard(t) {
    const doors = (t.doors || []).join('+') || '—';
    const hasContent = (t.enemies||[]).length || (t.items||[]).length || t.riddle_key;
    const bossBadge    = t.is_boss_tile ? '<span style="background:#dc2626;color:#fff;border-radius:4px;padding:1px 6px;font-size:.6rem;font-weight:700;letter-spacing:.05em">BOSS</span>' : '';
    const inactiveBadge = !t.is_active ? '<span style="background:rgba(0,0,0,.6);color:#888;border-radius:4px;padding:1px 5px;font-size:.6rem">OFF</span>' : '';
    const contentDot   = hasContent ? '<span style="background:rgba(245,158,11,.9);width:6px;height:6px;border-radius:50%;display:inline-block" title="Zawiera wrogów/przedmioty"></span>' : '';
    const imgHtml = t.image_url
      ? `<img src="${_esc(t.image_url)}" style="width:100%;height:100%;object-fit:cover;display:block;transition:transform .2s" class="tc-img">`
      : `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--t3);font-size:.72rem;text-align:center;padding:10px;gap:6px;background:linear-gradient(135deg,#0a0a12,#0f0f1e)"><span style="font-size:1.8rem;opacity:.3">🏰</span>Brak obrazu</div>`;
    // Read-only sprite overlay using saved positions per enemy
    let overlayHtml = '';
    if (t.image_url && Array.isArray(t.enemies)) {
      const sprites = [];
      t.enemies.forEach(e => {
        const url = _tileEnemyImgCache[e.enemy_key];
        if (!url) return;
        const ovs = Array.isArray(e.overlays) ? e.overlays : [];
        ovs.forEach(o => o && sprites.push({ url, ...o }));
      });
      overlayHtml = sprites.map(s =>
        `<img src="${_esc(s.url)}" style="position:absolute;left:${s.x*100}%;top:${s.y*100}%;width:${(s.scale||.35)*100}%;height:${(s.scale||.35)*100}%;transform:translate(-50%,-50%) rotate(${s.rot||0}deg);object-fit:contain;mix-blend-mode:screen;pointer-events:none">`
      ).join('');
    }
    return `<div class="tile-card" style="background:#111120;border:1px solid #222235;border-radius:10px;overflow:hidden;cursor:pointer;transition:border-color .15s,transform .12s;position:relative" onclick="openEditTileModal(${t.id})" onmouseenter="this.style.borderColor='#f59e0b33';this.querySelector('.tc-img')&&(this.querySelector('.tc-img').style.transform='scale(1.04)')" onmouseleave="this.style.borderColor='#222235';this.querySelector('.tc-img')&&(this.querySelector('.tc-img').style.transform='')">
      <div style="position:relative;aspect-ratio:1;background:#0a0a0f;overflow:hidden">
        ${imgHtml}
        ${overlayHtml}
        <div style="position:absolute;inset:0;background:linear-gradient(to bottom,transparent 55%,rgba(0,0,0,.75));pointer-events:none"></div>
        <div style="position:absolute;top:6px;left:6px;display:flex;gap:4px;align-items:center">${bossBadge}${inactiveBadge}${contentDot}</div>
        <div style="position:absolute;top:6px;right:6px;background:rgba(0,0,0,.75);color:#facc15;padding:2px 7px;border-radius:4px;font-size:.62rem;font-family:monospace;border:1px solid rgba(245,158,11,.3)">${_esc(doors)}</div>
      </div>
      <div style="padding:8px 10px 10px">
        <div style="font-weight:600;font-size:.82rem;line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${_esc(t.label || '—')}</div>
        <div style="color:var(--t3);font-size:.68rem;margin-top:2px;opacity:.7">${_esc(t.category_key)}</div>
      </div>
    </div>`;
  }

  function _filterTiles() { _renderTilesGrid(); }

  async function openNewTileModal() {
    const cats = await _ensureTileCategories();
    if (!cats.length) { showToast('Brak kategorii. Najpierw utwórz kategorię.', 'warn'); return; }
    _openTileForm(null, cats);
  }

  async function openEditTileModal(tileId) {
    try {
      const r = await apiFetch(`/api/admin/dungeon-tiles/${tileId}`);
      const cats = await _ensureTileCategories();
      _openTileForm(r.tile, cats);
    } catch (e) { showToast('Nie można pobrać kafelka: ' + e.message, 'error'); }
  }

  function _openTileForm(prefill, cats) {
    const p = prefill || {};

    // Inject tile-form styles once
    if (!document.getElementById('tf-styles')) {
      const s = document.createElement('style'); s.id = 'tf-styles';
      s.textContent = `
        /* Sections */
        .tf-section{background:rgba(6,6,16,.8);border:1px solid rgba(255,255,255,.07);border-radius:8px;padding:14px 16px}
        .tf-section-head{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:#f59e0b;margin-bottom:10px;display:flex;align-items:center;gap:7px}
        .tf-chips-row{display:flex;flex-wrap:wrap;gap:6px;min-height:8px;margin-bottom:10px}
        .tf-chip{display:inline-flex;align-items:center;gap:5px;background:#0e0e1c;border:1px solid #1a1a2e;border-radius:6px;padding:3px 8px;font-size:.79rem;line-height:1.35}
        .tf-chip-del{background:none;border:none;color:#555;cursor:pointer;padding:0 2px;font-size:.82rem;line-height:1}
        .tf-chip-del:hover{color:#ef4444}
        .tf-add-row{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap}
        /* Door compass */
        .tf-dc-wrap{display:inline-grid;grid-template-columns:44px 46px 44px;grid-template-rows:32px 46px 32px;gap:4px;align-items:center;justify-items:center}
        .tf-dc-center{width:46px;height:46px;display:flex;align-items:center;justify-content:center;background:#07070f;border:1px solid rgba(255,255,255,.07);border-radius:7px;color:#1e1e38;font-size:1.1rem;pointer-events:none}
        .tf-door-btn{display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-family:monospace;font-weight:700;font-size:.72rem;letter-spacing:.04em;color:#32324e;background:#08081a;border:1.5px solid #16163a;border-radius:6px;transition:all .15s;user-select:none;width:44px;height:28px}
        .tf-door-e,.tf-door-w{width:28px;height:46px}
        .tf-door-btn.on{border-color:#f59e0b;color:#f59e0b;background:rgba(245,158,11,.1);box-shadow:0 0 10px rgba(245,158,11,.14)}
        .tf-door-btn:hover{border-color:#c87d20;color:#c87d20;background:rgba(200,125,32,.1)}
        /* Toggle */
        .tf-toggle{display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none}
        .tf-toggle input[type=checkbox]{display:none}
        .tf-toggle-track{width:34px;height:18px;background:#0c0c1e;border:1px solid #1c1c36;border-radius:9px;position:relative;transition:all .2s;flex-shrink:0}
        .tf-toggle-track::after{content:'';position:absolute;top:2px;left:2px;width:12px;height:12px;background:#2a2a4a;border-radius:50%;transition:transform .2s,background .2s}
        .tf-toggle input:checked~.tf-toggle-track{background:rgba(245,158,11,.1);border-color:#f59e0b}
        .tf-toggle input:checked~.tf-toggle-track::after{transform:translateX(16px);background:#f59e0b}
        .tf-toggle-label{font-size:.8rem;color:#666}
        /* Image studio */
        .tf-studio{background:#04040c;border:1px solid rgba(255,255,255,.07);border-radius:9px;padding:12px 14px;display:flex;flex-direction:column;gap:9px}
        .tf-studio-head{font-size:.61rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:#c87d20;display:flex;align-items:center;gap:6px;margin-bottom:2px}
        .tf-studio-lbl{font-size:.64rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:#383858;margin-bottom:3px}
        /* Image frame */
        .tf-img-frame{width:100%;aspect-ratio:1;background:#03030a;border:1px solid rgba(245,158,11,.1);border-radius:10px;overflow:hidden;display:flex;align-items:center;justify-content:center;transition:border-color .2s}
        .tf-img-frame:hover{border-color:rgba(245,158,11,.28)}
        .tf-img-frame img{width:100%;height:100%;object-fit:cover;display:block}
        /* Misc */
        .tf-param-lbl{font-size:.72rem;color:#777;display:flex;flex-direction:column;gap:3px}
        .tf-modal-body::-webkit-scrollbar{width:5px}
        .tf-modal-body::-webkit-scrollbar-thumb{background:#111128;border-radius:3px}
        .tf-ov-sprite{transition:outline-color .1s}
        .tf-ov-sprite:hover{outline-color:#f59e0b !important}
        .tf-ov-collide{outline:2px solid #ef4444 !important}
      `;
      document.head.appendChild(s);
    }

    // ── Mutable state ─────────────────────────────────────────
    let _tfEnemies = JSON.parse(JSON.stringify(p.enemies        || []));
    let _tfItems   = JSON.parse(JSON.stringify(p.items          || []));
    let _tfStates  = JSON.parse(JSON.stringify(p.active_states  || []));
    let _tfExits   = JSON.parse(JSON.stringify(p.exit_conditions|| []));
    let _tfDoorOverlays = JSON.parse(JSON.stringify(p.door_overlays || {}));

    // Door defaults — MUST mirror backend tile_compositor.DEFAULT_DOOR_OVERLAYS
    // (TILE_SIZE=512, WALL_BORDER=70 → 35/512 = 0.0684, 477/512 = 0.9316)
    const DOOR_DEFAULTS = {
      N: {x: 0.5,    y: 0.0684, scale: 1.0, rot: 0},
      S: {x: 0.5,    y: 0.9316, scale: 1.0, rot: 180},
      E: {x: 0.9316, y: 0.5,    scale: 1.0, rot: 270},
      W: {x: 0.0684, y: 0.5,    scale: 1.0, rot: 90},
    };
    const DOOR_W_REL = 90/512;   // base sprite W as fraction of tile
    const DOOR_H_REL = 70/512;   // base sprite H as fraction of tile

    // ── Pools loaded async ────────────────────────────────────
    let _epPool = [];
    let _ipPool = { item:[], weapon:[], consumable:[] };
    let _rpPool = [];

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `
<div class="modal-box" style="width:940px;max-height:94vh;display:flex;flex-direction:column;overflow:hidden">

  <!-- Header -->
  <div class="modal-head" style="flex-shrink:0;background:#07070e;border-bottom:1px solid rgba(255,255,255,.07);padding:11px 18px;display:flex;align-items:center;justify-content:space-between;gap:12px">
    <div style="display:flex;align-items:center;gap:10px;overflow:hidden;min-width:0">
      <span class="modal-title" style="font-size:.86rem;flex-shrink:0">${p.id ? '✎ Edytuj kafelek' : '＋ Nowy kafelek'}</span>
      ${p.label ? `<span style="font-size:.78rem;color:#f59e0b;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">— ${_esc(p.label)}</span>` : ''}
      ${p.id ? `<code style="flex-shrink:0;font-size:.64rem;color:#303050;background:#0a0a16;border:1px solid #181830;border-radius:4px;padding:2px 7px;font-family:monospace">#${p.id}</code>` : ''}
    </div>
    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
  </div>

  <!-- Scrollable body -->
  <div class="tf-modal-body" style="overflow-y:auto;flex:1;display:flex;flex-direction:column">

    <!-- TOP: two-column grid -->
    <div style="display:grid;grid-template-columns:288px 1fr;border-bottom:1px solid rgba(255,255,255,.06)">

      <!-- LEFT: image column -->
      <div style="padding:16px;background:#050510;border-right:1px solid rgba(255,255,255,.06);display:flex;flex-direction:column;gap:12px">
        <div style="font-size:.61rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#282844">Obraz kafelka</div>

        <!-- Image preview — id required by _generateTileImage -->
        <div id="tf-img-preview" class="tf-img-frame">
          ${p.image_url
            ? `<img src="${_esc(p.image_url)}" style="width:100%;height:100%;object-fit:cover">`
            : `<div style="display:flex;flex-direction:column;align-items:center;gap:7px;color:#202038;text-align:center;padding:16px">
                <span style="font-size:2.2rem;opacity:.15">🏰</span>
                <span style="font-size:.72rem;line-height:1.8">Brak obrazu<br><span style="font-size:.65rem;opacity:.55">Zapisz kafelek,<br>potem Generuj</span></span>
              </div>`
          }
        </div>

        <!-- Image Studio -->
        <div class="tf-studio">
          <div class="tf-studio-head">⚙ Studio obrazu</div>

          <div>
            <div class="tf-studio-lbl">Prompt (EN)</div>
            <textarea id="tf-img-prompt" class="form-input" rows="4" style="resize:vertical;font-size:.71rem;font-family:monospace;line-height:1.5" placeholder="English room description for image gen…">${_esc(p.image_gen_prompt||'')}</textarea>
          </div>

          <button class="btn btn-secondary btn-sm" id="tf-gen-prompt-btn" style="width:100%;padding:6px 10px;font-size:.79rem">
            ✨ Generuj prompt AI
          </button>

          <div>
            <div class="tf-studio-lbl">Model</div>
            <select id="tf-img-model" class="form-input" style="font-size:.77rem">
              <option value="">⏳ Ładowanie…</option>
            </select>
          </div>

          <button class="btn btn-primary btn-sm" id="tf-generate-btn" style="width:100%;padding:7px 10px;font-size:.79rem;letter-spacing:.02em" ${!p.id?'disabled':''}>
            🔄 Generuj / Regeneruj obraz
          </button>
        </div>
      </div>

      <!-- RIGHT: form fields -->
      <div style="padding:18px 22px;display:flex;flex-direction:column;gap:14px">

        <!-- Name + Category -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div>
            <label class="form-label">Nazwa <span style="color:#f59e0b">*</span></label>
            <input id="tf-label" class="form-input" value="${_esc(p.label || '')}" placeholder="np. Komnata strażników">
          </div>
          <div>
            <label class="form-label">Kategoria <span style="color:#f59e0b">*</span></label>
            <select id="tf-cat" class="form-input">
              ${cats.map(c => `<option value="${_esc(c.key)}" ${p.category_key===c.key?'selected':''}>${_esc(c.label)}</option>`).join('')}
            </select>
          </div>
        </div>

        <!-- Door compass -->
        <div>
          <label class="form-label">Drzwi <span style="color:#f59e0b">*</span> <span style="font-size:.68rem;color:var(--t3);font-weight:400">(N=góra  S=dół  E=prawo  W=lewo)</span></label>
          <div id="tf-doors" style="margin-top:10px">
            <div class="tf-dc-wrap">
              <div></div>
              <label class="tf-door-btn tf-door-n${(p.doors||[]).includes('N')?' on':''}" data-d="N"><input type="checkbox" data-door="N" ${(p.doors||[]).includes('N')?'checked':''} style="display:none"><span>N</span></label>
              <div></div>
              <label class="tf-door-btn tf-door-w${(p.doors||[]).includes('W')?' on':''}" data-d="W"><input type="checkbox" data-door="W" ${(p.doors||[]).includes('W')?'checked':''} style="display:none"><span>W</span></label>
              <div class="tf-dc-center">◈</div>
              <label class="tf-door-btn tf-door-e${(p.doors||[]).includes('E')?' on':''}" data-d="E"><input type="checkbox" data-door="E" ${(p.doors||[]).includes('E')?'checked':''} style="display:none"><span>E</span></label>
              <div></div>
              <label class="tf-door-btn tf-door-s${(p.doors||[]).includes('S')?' on':''}" data-d="S"><input type="checkbox" data-door="S" ${(p.doors||[]).includes('S')?'checked':''} style="display:none"><span>S</span></label>
              <div></div>
            </div>
          </div>
        </div>

        <!-- Toggles -->
        <div style="display:flex;gap:22px">
          <label class="tf-toggle"><input type="checkbox" id="tf-boss" ${p.is_boss_tile?'checked':''}><span class="tf-toggle-track"></span><span class="tf-toggle-label">Kafelek bossa</span></label>
          <label class="tf-toggle"><input type="checkbox" id="tf-active" ${p.is_active!==false?'checked':''}><span class="tf-toggle-track"></span><span class="tf-toggle-label">Aktywny</span></label>
        </div>

        <!-- Room description -->
        <div style="flex:1;display:flex;flex-direction:column">
          <label class="form-label" style="display:flex;align-items:center;gap:.5rem">
            Opis pokoju <span style="font-size:.7rem;color:var(--t3);font-weight:400">(AI GM + prompt obrazu)</span>
            <button type="button" id="tf-gen-desc-btn" class="btn btn-sm" style="margin-left:auto;font-size:.7rem;padding:.2rem .6rem" onclick="_aiGenerateDescription(this.closest('.modal-overlay'))">✨ Generuj opis AI</button>
          </label>
          <textarea id="tf-desc" class="form-input" rows="6" style="resize:vertical;flex:1" placeholder="np. Stara komnata strażnicza z rdzawą zbroją na ścianie i poczerniałymi pochodniami…">${_esc(p.room_description||'')}</textarea>
        </div>

      </div>
    </div>

    <!-- SECTIONS -->
    <div style="padding:14px 18px 18px;display:flex;flex-direction:column;gap:12px">

      <!-- Enemies -->
      <div class="tf-section">
        <div class="tf-section-head">⚔ Wrogowie</div>
        <div id="tf-enemies-chips" class="tf-chips-row"></div>
        <div class="tf-add-row">
          <select id="tf-enemy-sel" class="form-input" style="flex:1;min-width:200px"><option value="">⏳ Ładowanie…</option></select>
          <label class="tf-param-lbl">Ilość<input id="tf-enemy-count" type="number" class="form-input" value="1" min="1" max="20" style="width:68px"></label>
          <button class="btn btn-secondary btn-sm" id="tf-enemy-add-btn">+ Dodaj</button>
        </div>
      </div>

      <!-- Sprite overlay editor -->
      <div class="tf-section" id="tf-overlay-section" style="${p.image_url?'':'display:none'}">
        <div class="tf-section-head" style="display:flex;align-items:center;gap:10px;justify-content:space-between;margin-bottom:8px">
          <span>🎯 Pozycje sprite'ów na kafelku</span>
          <span style="display:flex;gap:8px;align-items:center;font-weight:400;text-transform:none;letter-spacing:0">
            <button type="button" class="btn btn-secondary btn-sm" id="tf-ov-arrange" title="Rozmieść automatycznie (siatka, bez kolizji)">🎲 Auto</button>
            <label class="tf-toggle" style="font-size:.72rem"><input type="checkbox" id="tf-ov-collision-warn" checked><span class="tf-toggle-track"></span><span class="tf-toggle-label">Pokaż kolizje</span></label>
          </span>
        </div>
        <div style="font-size:.72rem;color:var(--t3);margin-bottom:8px">Przeciągnij = przesuń &nbsp;|&nbsp; kółko myszy = skala &nbsp;|&nbsp; Shift+przeciągnij = obrót</div>
        <div id="tf-overlay-surface" style="position:relative;width:100%;max-width:520px;aspect-ratio:1;background:#060610;border:1px solid var(--border);border-radius:10px;overflow:hidden;user-select:none;touch-action:none">
          <div id="tf-overlay-empty" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:.78rem;text-align:center;padding:14px">Brak obrazu kafelka lub wrogów<br><span style="font-size:.7rem;opacity:.6">Wygeneruj obraz kafelka i dodaj wroga z obrazem (🖼)</span></div>
        </div>
      </div>

      <!-- Door overlay editor -->
      <div class="tf-section" id="tf-door-overlay-section" style="${p.image_url?'':'display:none'}">
        <div class="tf-section-head" style="display:flex;align-items:center;gap:10px;justify-content:space-between;margin-bottom:8px">
          <span>🚪 Pozycje drzwi <span style="font-weight:400;text-transform:none;letter-spacing:0;color:var(--t3);font-size:.7rem">(kompozytor backend)</span></span>
          <span style="display:flex;gap:8px;align-items:center;font-weight:400;text-transform:none;letter-spacing:0">
            <button type="button" class="btn btn-secondary btn-sm" id="tf-door-reset" title="Powrót do kanonicznych pozycji domyślnych">🎲 Auto</button>
            <button type="button" class="btn btn-primary btn-sm" id="tf-door-apply" title="Zapisz pozycje i zrekomponuj obraz (bez nowej generacji AI)">✓ Zastosuj</button>
          </span>
        </div>
        <div style="font-size:.72rem;color:var(--t3);margin-bottom:8px">Przeciągnij łuk = przesuń &nbsp;|&nbsp; kółko myszy = skala &nbsp;|&nbsp; Shift+przeciągnij = obrót</div>
        <div id="tf-door-overlay-surface" style="position:relative;width:100%;max-width:520px;aspect-ratio:1;background:#060610;border:1px solid var(--border);border-radius:10px;overflow:hidden;user-select:none;touch-action:none">
          <div id="tf-door-overlay-empty" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:.78rem;text-align:center;padding:14px">Brak obrazu kafelka lub aktywnych drzwi<br><span style="font-size:.7rem;opacity:.6">Wygeneruj obraz i wybierz drzwi (kompas powyżej)</span></div>
        </div>
      </div>

      <!-- Items -->
      <div class="tf-section">
        <div class="tf-section-head">💎 Przedmioty / łupy</div>
        <div id="tf-items-chips" class="tf-chips-row"></div>
        <div class="tf-add-row">
          <select id="tf-item-type" class="form-input" style="width:148px">
            <option value="item">Przedmiot</option>
            <option value="weapon">Broń</option>
            <option value="consumable">Konsumable</option>
          </select>
          <select id="tf-item-sel" class="form-input" style="flex:1;min-width:180px"><option value="">⏳ Ładowanie…</option></select>
          <label class="tf-param-lbl">Szansa %<input id="tf-item-chance" type="number" class="form-input" value="50" min="1" max="100" style="width:68px"></label>
          <button class="btn btn-secondary btn-sm" id="tf-item-add-btn">+ Dodaj</button>
        </div>
      </div>

      <!-- Riddle -->
      <div class="tf-section">
        <div class="tf-section-head">❓ Zagadka <span style="font-size:.7rem;font-weight:400;text-transform:none;letter-spacing:0;color:var(--t3)">(opcjonalna — wymaga osobnego warunku wyjścia riddle_solved)</span></div>
        <select id="tf-riddle-sel" class="form-input" style="max-width:520px"><option value="">⏳ Ładowanie…</option></select>
      </div>

      <!-- Active States -->
      <div class="tf-section">
        <div class="tf-section-head">🔥 Aktywne stany <span style="font-size:.7rem;font-weight:400;text-transform:none;letter-spacing:0;color:var(--t3)">(efekty oddziałujące co turę na gracza)</span></div>
        <div id="tf-states-chips" class="tf-chips-row"></div>
        <div class="tf-add-row">
          <select id="tf-state-type" class="form-input" style="width:185px">
            <option value="burning">🔥 Płonący (burning)</option>
            <option value="flooding">🌊 Zalany (flooding)</option>
            <option value="poison_gas">☠ Trujący gaz</option>
            <option value="cold">❄ Zimno (cold)</option>
            <option value="lightning">⚡ Błyskawica</option>
            <option value="cursed">💀 Przeklęty (cursed)</option>
          </select>
          <div id="tf-state-params" style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end"></div>
          <button class="btn btn-secondary btn-sm" id="tf-state-add-btn" style="margin-left:auto;flex-shrink:0">+ Dodaj</button>
        </div>
      </div>

      <!-- Exit Conditions -->
      <div class="tf-section">
        <div class="tf-section-head">🚪 Warunki wyjścia</div>
        <div style="font-size:.74rem;color:var(--t3);margin-bottom:8px">Brak warunków = wyjście zawsze otwarte. Dodaj warunek by zablokować przejście.</div>
        <div id="tf-exits-chips" class="tf-chips-row"></div>
        <div class="tf-add-row">
          <select id="tf-exit-type" class="form-input" style="width:220px">
            <option value="enemies_cleared">⚔ Wrogowie pokonani</option>
            <option value="riddle_solved">❓ Zagadka rozwiązana</option>
            <option value="item_in_inventory">🎒 Przedmiot w ekwipunku</option>
            <option value="stat_roll">🎲 Test statystyki</option>
          </select>
          <div id="tf-exit-params" style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end"></div>
          <button class="btn btn-secondary btn-sm" id="tf-exit-add-btn" style="margin-left:auto;flex-shrink:0">+ Dodaj</button>
        </div>
      </div>

    </div>
  </div>

  <!-- Footer -->
  <div class="modal-foot" style="flex-shrink:0;display:flex;gap:8px;justify-content:flex-end;padding:11px 16px;border-top:1px solid rgba(255,255,255,.07)">
    ${p.id?`<button class="btn btn-secondary btn-sm" id="tf-del-btn">🗑 Usuń</button>`:''}
    <button class="btn btn-secondary btn-sm" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
    <button class="btn btn-primary btn-sm" id="tf-save-btn">💾 Zapisz kafelek</button>
  </div>
</div>`;
    if (p.id) overlay.dataset.tileId = p.id;
    document.body.appendChild(overlay);

    // ── Door buttons ──────────────────────────────────────────
    overlay.querySelectorAll('#tf-doors .tf-door-btn').forEach(lbl => {
      lbl.addEventListener('click', () => {
        const cb = lbl.querySelector('input');
        cb.checked = !cb.checked;
        lbl.classList.toggle('on', cb.checked);
        // Refresh door overlay editor — active doors changed
        if (typeof _renderDoorEditor === 'function') _renderDoorEditor();
      });
    });

    // ── Render chips ──────────────────────────────────────────
    const STATE_ICON = { burning:'🔥', flooding:'🌊', poison_gas:'☠', cold:'❄', lightning:'⚡', cursed:'💀' };
    const EXIT_LABEL = { enemies_cleared:'Wrogowie pokonani', riddle_solved:'Zagadka rozwiązana', item_in_inventory:'Przedmiot w ekwipunku', stat_roll:'Test statystyki' };
    const EXIT_ICON  = { enemies_cleared:'⚔', riddle_solved:'❓', item_in_inventory:'🎒', stat_roll:'🎲' };
    const TIER_CLS   = { boss:'badge-red', elite:'badge-amber', 4:'badge-red', 3:'badge-amber', 2:'badge-blue', 1:'badge-slate' };

    function _rfEnemy() {
      const el = overlay.querySelector('#tf-enemies-chips');
      if (!el) return;
      if (!_tfEnemies.length) { el.innerHTML = '<span style="font-size:.75rem;color:var(--t3)">Brak wrogów</span>'; return; }
      el.innerHTML = _tfEnemies.map((e,i)=>{
        const info = _epPool.find(x=>x.key===e.enemy_key);
        const t = info?.tier; const tcls = TIER_CLS[t]||'badge-slate';
        const tierBadge = t!=null ? `<span class="badge ${tcls}" style="font-size:.62rem">${t}</span>` : '';
        const hasImg = info?.image_url ? ' style="color:#f59e0b"' : '';
        return `<span class="tf-chip">⚔ <b>${_esc(info?.label||e.enemy_key)}</b> ${tierBadge} <span style="color:#f59e0b;font-family:monospace;font-size:.85em">×${e.count||1}</span><button class="tf-chip-del" data-type="enemy-img" data-key="${_esc(e.enemy_key)}" title="Generuj obraz wroga"${hasImg}>🖼</button><button class="tf-chip-del" data-type="enemy" data-idx="${i}" title="Usuń">✕</button></span>`;
      }).join('');
      // Sync sprite overlay editor whenever enemy chips re-render
      if (typeof _renderOverlayEditor === 'function') _renderOverlayEditor();
    }
    function _rfItem() {
      const el = overlay.querySelector('#tf-items-chips');
      if (!el) return;
      if (!_tfItems.length) { el.innerHTML = '<span style="font-size:.75rem;color:var(--t3)">Brak przedmiotów</span>'; return; }
      const TC = { item:'badge-blue', weapon:'badge-red', consumable:'badge-green' };
      const TL = { item:'item', weapon:'broń', consumable:'kons.' };
      el.innerHTML = _tfItems.map((it,i)=>{
        const tp = it.weapon_key?'weapon':it.consumable_key?'consumable':'item';
        const key = it.weapon_key||it.consumable_key||it.item_key||'?';
        const pool = [...(_ipPool.item||[]),...(_ipPool.weapon||[]),...(_ipPool.consumable||[])];
        const info = pool.find(x=>x.key===key);
        const pct = Math.round((it.chance||0.5)*100);
        return `<span class="tf-chip">💎 <b>${_esc(info?.label||key)}</b> <span class="badge ${TC[tp]}" style="font-size:.62rem">${TL[tp]}</span> <span style="color:#f59e0b;font-family:monospace;font-size:.85em">${pct}%</span><button class="tf-chip-del" data-type="item" data-idx="${i}" title="Usuń">✕</button></span>`;
      }).join('');
    }
    function _rfState() {
      const el = overlay.querySelector('#tf-states-chips');
      if (!el) return;
      if (!_tfStates.length) { el.innerHTML = '<span style="font-size:.75rem;color:var(--t3)">Brak stanów</span>'; return; }
      el.innerHTML = _tfStates.map((s,i)=>{
        let d = `${STATE_ICON[s.type]||'●'} <b>${s.type}</b>`;
        if (s.damage_die) d += ` <span style="color:#f59e0b">${s.damage_die}</span>`;
        if (s.save_stat)  d += ` save:<span style="color:#93c5fd">${s.save_stat}</span>`;
        if (s.dc)         d += ` DC<span style="color:#f59e0b">${s.dc}</span>`;
        return `<span class="tf-chip">${d}<button class="tf-chip-del" data-type="state" data-idx="${i}" title="Usuń">✕</button></span>`;
      }).join('');
    }
    function _rfExit() {
      const el = overlay.querySelector('#tf-exits-chips');
      if (!el) return;
      if (!_tfExits.length) { el.innerHTML = '<span style="font-size:.75rem;color:var(--t3)">Brak warunków — wyjście zawsze otwarte</span>'; return; }
      el.innerHTML = _tfExits.map((x,i)=>{
        let d = `${EXIT_ICON[x.type]||'●'} <b>${EXIT_LABEL[x.type]||x.type}</b>`;
        if (x.item_key) {
          const pool = [...(_ipPool.item||[]),...(_ipPool.weapon||[]),...(_ipPool.consumable||[])];
          d += `: ${_esc(pool.find(it=>it.key===x.item_key)?.label||x.item_key)}`;
        }
        if (x.stat) d += ` <span style="color:#93c5fd">${x.stat}</span>`;
        if (x.dc)   d += ` DC<span style="color:#f59e0b">${x.dc}</span>`;
        return `<span class="tf-chip">${d}<button class="tf-chip-del" data-type="exit" data-idx="${i}" title="Usuń">✕</button></span>`;
      }).join('');
    }

    // ── Sprite overlay editor ─────────────────────────────────
    // Each _tfEnemies[i] gets `overlays: [{x, y, scale, rot}]` length=count.
    // x,y: 0–1 relative to tile surface. scale: 0.1–0.8. rot: degrees.
    function _ensureOverlays(entry) {
      const want = Math.max(1, entry.count || 1);
      entry.overlays = Array.isArray(entry.overlays) ? entry.overlays.slice(0, want) : [];
      while (entry.overlays.length < want) entry.overlays.push(null); // placeholder, auto-filled
    }
    function _autoArrangeOverlays() {
      // Collect all sprite indices (enemyIdx, instIdx) for entries with image_url
      const slots = [];
      _tfEnemies.forEach((e, ei) => {
        const info = _epPool.find(x => x.key === e.enemy_key);
        if (!info?.image_url) return;
        _ensureOverlays(e);
        for (let ii = 0; ii < e.overlays.length; ii++) slots.push([ei, ii]);
      });
      const N = slots.length;
      if (!N) return;
      const cols = Math.ceil(Math.sqrt(N));
      const rows = Math.ceil(N / cols);
      const cellW = 1 / cols, cellH = 1 / rows;
      const baseScale = Math.min(0.75 / cols, 0.55);
      slots.forEach(([ei, ii], i) => {
        const col = i % cols, row = Math.floor(i / cols);
        _tfEnemies[ei].overlays[ii] = {
          x: (col + 0.5) * cellW,
          y: (row + 0.5) * cellH,
          scale: baseScale,
          rot: 0,
        };
      });
      _renderOverlayEditor();
    }
    function _spriteBounds(t) {
      // Approximate sprite bbox in unit coords (square sprite of size = scale)
      const s = t.scale;
      return { l: t.x - s/2, r: t.x + s/2, t: t.y - s/2, b: t.y + s/2 };
    }
    function _spritesOverlap(a, b) {
      const A = _spriteBounds(a), B = _spriteBounds(b);
      return !(A.r < B.l || A.l > B.r || A.b < B.t || A.t > B.b);
    }
    function _renderOverlayEditor() {
      const sec = overlay.querySelector('#tf-overlay-section');
      const surf = overlay.querySelector('#tf-overlay-surface');
      if (!sec || !surf) return;
      const tileImg = overlay.querySelector('#tf-img-preview img')?.src || p.image_url || '';
      // Build sprite list from enemies with image_url
      const sprites = [];
      _tfEnemies.forEach((e, ei) => {
        const info = _epPool.find(x => x.key === e.enemy_key);
        if (!info?.image_url) return;
        _ensureOverlays(e);
        // Auto-fill any null overlays via auto-arrange — but only those
        e.overlays.forEach((t, ii) => {
          if (!t) {
            // initial placement: center-ish, will be re-laid out via Auto button
            e.overlays[ii] = { x: 0.5, y: 0.5, scale: 0.35, rot: 0 };
          }
          sprites.push({ enemyIdx: ei, instIdx: ii, info, t: e.overlays[ii] });
        });
      });
      sec.style.display = tileImg && sprites.length ? '' : 'none';
      if (!tileImg || !sprites.length) {
        surf.innerHTML = `<div id="tf-overlay-empty" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:.78rem;text-align:center;padding:14px">Brak obrazu kafelka lub wrogów<br><span style="font-size:.7rem;opacity:.6">Wygeneruj obraz kafelka i dodaj wroga z obrazem (🖼)</span></div>`;
        return;
      }
      const showColl = overlay.querySelector('#tf-ov-collision-warn')?.checked !== false;
      // Compute collision pairs
      const colliding = new Set();
      if (showColl) {
        for (let i = 0; i < sprites.length; i++)
          for (let j = i+1; j < sprites.length; j++)
            if (_spritesOverlap(sprites[i].t, sprites[j].t)) { colliding.add(i); colliding.add(j); }
      }
      surf.innerHTML = `<img src="${_esc(tileImg)}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;pointer-events:none">` +
        sprites.map((sp, i) => {
          const collCls = colliding.has(i) ? 'tf-ov-collide' : '';
          const sizePct = sp.t.scale * 100;
          return `<div class="tf-ov-sprite ${collCls}" data-spr="${i}" data-ei="${sp.enemyIdx}" data-ii="${sp.instIdx}"
            style="position:absolute;left:${sp.t.x*100}%;top:${sp.t.y*100}%;width:${sizePct}%;height:${sizePct}%;transform:translate(-50%,-50%) rotate(${sp.t.rot}deg);cursor:grab;outline:${collCls?'2px solid #ef4444':'1px dashed rgba(245,158,11,.5)'};outline-offset:-1px;border-radius:4px">
            <img src="${_esc(sp.info.image_url)}" draggable="false" style="width:100%;height:100%;object-fit:contain;mix-blend-mode:screen;pointer-events:none">
            <div style="position:absolute;bottom:-18px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.8);color:#facc15;font-size:.62rem;padding:1px 5px;border-radius:3px;white-space:nowrap;pointer-events:none;font-family:monospace">${_esc(sp.info.label||sp.info.key)} ${(sp.t.scale*100|0)}%${sp.t.rot?` ${sp.t.rot|0}°`:''}</div>
          </div>`;
        }).join('');
    }
    // Drag/scale/rotate via pointer events on surface
    let _ovDrag = null;
    function _onSurfDown(ev) {
      const sprite = ev.target.closest('.tf-ov-sprite');
      if (!sprite) return;
      ev.preventDefault();
      const ei = parseInt(sprite.dataset.ei, 10);
      const ii = parseInt(sprite.dataset.ii, 10);
      const surf = overlay.querySelector('#tf-overlay-surface');
      const rect = surf.getBoundingClientRect();
      const t = _tfEnemies[ei].overlays[ii];
      _ovDrag = {
        ei, ii, rect,
        shift: ev.shiftKey,
        startX: ev.clientX, startY: ev.clientY,
        origX: t.x, origY: t.y, origRot: t.rot || 0,
      };
      sprite.style.cursor = ev.shiftKey ? 'ew-resize' : 'grabbing';
      surf.setPointerCapture?.(ev.pointerId);
    }
    function _onSurfMove(ev) {
      if (!_ovDrag) return;
      const t = _tfEnemies[_ovDrag.ei].overlays[_ovDrag.ii];
      if (_ovDrag.shift) {
        // Rotate: dx in pixels → degrees
        const dx = ev.clientX - _ovDrag.startX;
        t.rot = (_ovDrag.origRot + dx) % 360;
      } else {
        // Move
        const dx = (ev.clientX - _ovDrag.startX) / _ovDrag.rect.width;
        const dy = (ev.clientY - _ovDrag.startY) / _ovDrag.rect.height;
        t.x = Math.max(0.02, Math.min(0.98, _ovDrag.origX + dx));
        t.y = Math.max(0.02, Math.min(0.98, _ovDrag.origY + dy));
      }
      _renderOverlayEditor();
    }
    function _onSurfUp() { _ovDrag = null; }
    function _onSurfWheel(ev) {
      const sprite = ev.target.closest('.tf-ov-sprite');
      if (!sprite) return;
      ev.preventDefault();
      const ei = parseInt(sprite.dataset.ei, 10);
      const ii = parseInt(sprite.dataset.ii, 10);
      const t = _tfEnemies[ei].overlays[ii];
      const delta = ev.deltaY < 0 ? 0.04 : -0.04;
      t.scale = Math.max(0.08, Math.min(0.85, (t.scale || 0.35) + delta));
      _renderOverlayEditor();
    }
    // Wire surface events once
    {
      const surf = overlay.querySelector('#tf-overlay-surface');
      if (surf) {
        surf.addEventListener('pointerdown', _onSurfDown);
        surf.addEventListener('pointermove', _onSurfMove);
        surf.addEventListener('pointerup', _onSurfUp);
        surf.addEventListener('pointercancel', _onSurfUp);
        surf.addEventListener('wheel', _onSurfWheel, { passive: false });
      }
      overlay.querySelector('#tf-ov-arrange')?.addEventListener('click', _autoArrangeOverlays);
      overlay.querySelector('#tf-ov-collision-warn')?.addEventListener('change', _renderOverlayEditor);
    }

    // ── Door overlay editor (Phase 7) ─────────────────────────
    function _getDoorOverlay(side) {
      return { ...DOOR_DEFAULTS[side], ...(_tfDoorOverlays[side] || {}) };
    }
    function _setDoorOverlay(side, patch) {
      _tfDoorOverlays[side] = { ..._getDoorOverlay(side), ...patch };
    }
    function _renderDoorEditor() {
      const sec  = overlay.querySelector('#tf-door-overlay-section');
      const surf = overlay.querySelector('#tf-door-overlay-surface');
      if (!sec || !surf) return;
      const tileImg = overlay.querySelector('#tf-img-preview img')?.src || p.image_url || '';
      const activeDoors = Array.from(overlay.querySelectorAll('#tf-doors input:checked'))
        .map(i => i.dataset.door);
      if (!tileImg || !activeDoors.length) {
        sec.style.display = 'none';
        surf.innerHTML = `<div id="tf-door-overlay-empty" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:.78rem;text-align:center;padding:14px">Brak obrazu kafelka lub aktywnych drzwi<br><span style="font-size:.7rem;opacity:.6">Wygeneruj obraz i wybierz drzwi (kompas powyżej)</span></div>`;
        return;
      }
      sec.style.display = '';
      surf.innerHTML = `<img src="${_esc(tileImg)}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;pointer-events:none">` +
        activeDoors.map(side => {
          const ov = _getDoorOverlay(side);
          // Base sprite is W×H = 90×70; after rot 90/270 dims swap
          const rotMod = ((ov.rot % 360) + 360) % 360;
          const isSwapped = (rotMod === 90 || rotMod === 270);
          const wRel = (isSwapped ? DOOR_H_REL : DOOR_W_REL) * ov.scale;
          const hRel = (isSwapped ? DOOR_W_REL : DOOR_H_REL) * ov.scale;
          return `<div class="tf-door-h" data-side="${side}"
            style="position:absolute;left:${ov.x*100}%;top:${ov.y*100}%;width:${wRel*100}%;height:${hRel*100}%;
                   transform:translate(-50%,-50%);
                   border:2px dashed #f59e0b;background:rgba(245,158,11,.22);
                   cursor:grab;border-radius:6px;display:flex;align-items:center;justify-content:center;gap:3px;
                   color:#fff;font-weight:700;font-size:.95rem;font-family:monospace;user-select:none;
                   text-shadow:0 0 4px rgba(0,0,0,.85);box-shadow:0 0 14px rgba(245,158,11,.35)">
            ${side}<sub style="font-size:.52rem;opacity:.7;font-weight:500;letter-spacing:0">${(ov.scale*100|0)}%${ov.rot?` ${ov.rot|0}°`:''}</sub>
          </div>`;
        }).join('');
    }

    let _ddDrag = null;
    function _onDoorDown(ev) {
      const h = ev.target.closest('.tf-door-h');
      if (!h) return;
      ev.preventDefault();
      const side = h.dataset.side;
      const surf = overlay.querySelector('#tf-door-overlay-surface');
      const rect = surf.getBoundingClientRect();
      const ov = _getDoorOverlay(side);
      _ddDrag = {
        side, rect, shift: ev.shiftKey,
        startX: ev.clientX, startY: ev.clientY,
        origX: ov.x, origY: ov.y, origRot: ov.rot,
      };
      h.style.cursor = ev.shiftKey ? 'ew-resize' : 'grabbing';
      surf.setPointerCapture?.(ev.pointerId);
    }
    function _onDoorMove(ev) {
      if (!_ddDrag) return;
      if (_ddDrag.shift) {
        const dx = ev.clientX - _ddDrag.startX;
        _setDoorOverlay(_ddDrag.side, { rot: Math.round(_ddDrag.origRot + dx) % 360 });
      } else {
        const dx = (ev.clientX - _ddDrag.startX) / _ddDrag.rect.width;
        const dy = (ev.clientY - _ddDrag.startY) / _ddDrag.rect.height;
        _setDoorOverlay(_ddDrag.side, {
          x: Math.max(0.02, Math.min(0.98, _ddDrag.origX + dx)),
          y: Math.max(0.02, Math.min(0.98, _ddDrag.origY + dy)),
        });
      }
      _renderDoorEditor();
    }
    function _onDoorUp() { _ddDrag = null; }
    function _onDoorWheel(ev) {
      const h = ev.target.closest('.tf-door-h');
      if (!h) return;
      ev.preventDefault();
      const side = h.dataset.side;
      const ov = _getDoorOverlay(side);
      const delta = ev.deltaY < 0 ? 0.08 : -0.08;
      _setDoorOverlay(side, { scale: Math.max(0.3, Math.min(2.5, +(ov.scale + delta).toFixed(2))) });
      _renderDoorEditor();
    }
    {
      const dsurf = overlay.querySelector('#tf-door-overlay-surface');
      if (dsurf) {
        dsurf.addEventListener('pointerdown', _onDoorDown);
        dsurf.addEventListener('pointermove', _onDoorMove);
        dsurf.addEventListener('pointerup',   _onDoorUp);
        dsurf.addEventListener('pointercancel', _onDoorUp);
        dsurf.addEventListener('wheel', _onDoorWheel, { passive: false });
      }
      overlay.querySelector('#tf-door-reset')?.addEventListener('click', () => {
        _tfDoorOverlays = {};
        _renderDoorEditor();
        showToast('Pozycje drzwi przywrócone do domyślnych — kliknij Zastosuj', 'info');
      });
      overlay.querySelector('#tf-door-apply')?.addEventListener('click', async () => {
        if (!p.id) { showToast('Najpierw zapisz kafelek', 'warn'); return; }
        const btn = overlay.querySelector('#tf-door-apply');
        btn.disabled = true;
        const orig = btn.textContent;
        btn.textContent = '⏳ Kompozytor…';
        try {
          await apiFetch(`/api/admin/dungeon-tiles/${p.id}`, {
            method: 'PATCH',
            body: JSON.stringify({ door_overlays: _tfDoorOverlays }),
          });
          const r = await apiFetch(`/api/admin/dungeon-tiles/${p.id}/recomposite`, { method: 'POST' });
          // Update image preview
          const prev = overlay.querySelector('#tf-img-preview');
          if (prev && r.image_url) {
            prev.innerHTML = `<img src="${_esc(r.image_url)}?_t=${Date.now()}" style="width:100%;height:100%;object-fit:cover">`;
          }
          _renderDoorEditor();
          showToast('Pozycje drzwi zastosowane', 'success');
        } catch (e) {
          showToast('Błąd: ' + e.message, 'error');
        } finally {
          btn.disabled = false;
          btn.textContent = orig;
        }
      });
    }

    // ── Chip delete (delegated) ───────────────────────────────
    ['#tf-enemies-chips','#tf-items-chips','#tf-states-chips','#tf-exits-chips'].forEach(sel => {
      overlay.querySelector(sel).addEventListener('click', ev => {
        const btn = ev.target.closest('.tf-chip-del');
        if (!btn) return;
        const idx = parseInt(btn.dataset.idx, 10);
        const t = btn.dataset.type;
        if (t==='enemy') { _tfEnemies.splice(idx,1); _rfEnemy(); }
        else if (t==='item')  { _tfItems.splice(idx,1);   _rfItem(); }
        else if (t==='state') { _tfStates.splice(idx,1);  _rfState(); }
        else if (t==='exit')  { _tfExits.splice(idx,1);   _rfExit(); }
        else if (t==='enemy-img') {
          const key = btn.dataset.key;
          const info = _epPool.find(x=>x.key===key) || { key };
          // Enrich enemy context with tile room_description for thematic match
          const roomDesc = overlay.querySelector('#tf-desc')?.value?.trim() || '';
          const enriched = Object.assign({}, info, {
            description: [info.description||info.label||key, roomDesc ? `dungeon setting: ${roomDesc}` : ''].filter(Boolean).join('. '),
            _tileContext: true,  // triggers top-down perspective in _buildEnemyImagePrompt
          });
          openEnemyImageModal(key, enriched);
          // Refresh chip after modal closes to pick up new image_url in pool
          const obs = new MutationObserver(() => {
            if (!document.getElementById('enemy-img-modal')) {
              obs.disconnect();
              // re-fetch enemy to update pool image_url
              apiFetch('/api/admin/enemies').then(r => {
                _epPool = r.items || _epPool;
                _rfEnemy();
              }).catch(()=>{});
            }
          });
          obs.observe(document.body, { childList: true });
        }
      });
    });

    // ── State params ──────────────────────────────────────────
    const DICE_OPTS = ['1d4','1d6','1d8','1d10','1d12','2d4','2d6'];
    const STATS_LIST = ['STR','DEX','CON','INT','WIS','CHA'];
    function _renderStateParams() {
      const type = overlay.querySelector('#tf-state-type').value;
      const el = overlay.querySelector('#tf-state-params');
      if (!['burning','flooding','poison_gas','cold','lightning'].includes(type)) {
        el.innerHTML = `<span style="font-size:.75rem;color:var(--t3)">Brak parametrów</span>`; return;
      }
      el.innerHTML = `
        <label class="tf-param-lbl">Kostka obrażeń
          <select id="tf-state-die" class="form-input" style="width:88px">${DICE_OPTS.map(d=>`<option value="${d}">${d}</option>`).join('')}</select>
        </label>
        <label class="tf-param-lbl">Stat ucieczki
          <select id="tf-state-save" class="form-input" style="width:88px">${STATS_LIST.map(s=>`<option value="${s}"${s==='DEX'?' selected':''}>${s}</option>`).join('')}</select>
        </label>
        <label class="tf-param-lbl">DC
          <input id="tf-state-dc" type="number" class="form-input" value="12" min="1" max="30" style="width:68px">
        </label>`;
    }
    overlay.querySelector('#tf-state-type').addEventListener('change', _renderStateParams);
    _renderStateParams();

    // ── Exit params ───────────────────────────────────────────
    function _renderExitParams() {
      const type = overlay.querySelector('#tf-exit-type').value;
      const el = overlay.querySelector('#tf-exit-params');
      if (type==='enemies_cleared'||type==='riddle_solved') {
        el.innerHTML = `<span style="font-size:.75rem;color:var(--t3)">Brak parametrów</span>`; return;
      }
      if (type==='item_in_inventory') {
        const allItems = [...(_ipPool.item||[]),...(_ipPool.weapon||[]),...(_ipPool.consumable||[])];
        el.innerHTML = `<label class="tf-param-lbl">Przedmiot
          <select id="tf-exit-item-key" class="form-input" style="min-width:200px">
            <option value="">— wybierz —</option>
            ${allItems.map(it=>`<option value="${_esc(it.key)}">${_esc(it.label||it.key)}</option>`).join('')}
          </select></label>`; return;
      }
      if (type==='stat_roll') {
        el.innerHTML = `
          <label class="tf-param-lbl">Statystyka
            <select id="tf-exit-stat" class="form-input" style="width:88px">${STATS_LIST.map(s=>`<option value="${s}">${s}</option>`).join('')}</select>
          </label>
          <label class="tf-param-lbl">DC
            <input id="tf-exit-dc" type="number" class="form-input" value="14" min="1" max="30" style="width:68px">
          </label>`; return;
      }
    }
    overlay.querySelector('#tf-exit-type').addEventListener('change', _renderExitParams);
    _renderExitParams();

    // ── Add handlers ──────────────────────────────────────────
    overlay.querySelector('#tf-enemy-add-btn').addEventListener('click', () => {
      const key = overlay.querySelector('#tf-enemy-sel').value;
      const cnt = parseInt(overlay.querySelector('#tf-enemy-count').value, 10) || 1;
      if (!key) { showToast('Wybierz wroga', 'warn'); return; }
      if (_tfEnemies.find(e=>e.enemy_key===key)) { showToast('Ten wróg już dodany', 'warn'); return; }
      _tfEnemies.push({ enemy_key: key, count: cnt });
      _rfEnemy();
    });

    overlay.querySelector('#tf-item-type').addEventListener('change', () => _populateItemSel(overlay.querySelector('#tf-item-type').value));

    overlay.querySelector('#tf-item-add-btn').addEventListener('click', () => {
      const type = overlay.querySelector('#tf-item-type').value;
      const key  = overlay.querySelector('#tf-item-sel').value;
      const pct  = parseFloat(overlay.querySelector('#tf-item-chance').value) || 50;
      if (!key) { showToast('Wybierz przedmiot', 'warn'); return; }
      const entry = { chance: Math.round(pct)/100 };
      if (type==='weapon') entry.weapon_key = key;
      else if (type==='consumable') entry.consumable_key = key;
      else entry.item_key = key;
      _tfItems.push(entry);
      _rfItem();
    });

    overlay.querySelector('#tf-state-add-btn').addEventListener('click', () => {
      const type = overlay.querySelector('#tf-state-type').value;
      const hasDmg = ['burning','flooding','poison_gas','cold','lightning'].includes(type);
      const entry = { type };
      if (hasDmg) {
        entry.damage_die = overlay.querySelector('#tf-state-die')?.value  || '1d4';
        entry.save_stat  = overlay.querySelector('#tf-state-save')?.value || 'DEX';
        entry.dc         = parseInt(overlay.querySelector('#tf-state-dc')?.value || '12', 10);
      }
      _tfStates.push(entry);
      _rfState();
    });

    overlay.querySelector('#tf-exit-add-btn').addEventListener('click', () => {
      const type = overlay.querySelector('#tf-exit-type').value;
      const entry = { type };
      if (type==='item_in_inventory') {
        const key = overlay.querySelector('#tf-exit-item-key')?.value;
        if (!key) { showToast('Wybierz przedmiot', 'warn'); return; }
        entry.item_key = key;
      } else if (type==='stat_roll') {
        entry.stat = overlay.querySelector('#tf-exit-stat')?.value || 'STR';
        entry.dc   = parseInt(overlay.querySelector('#tf-exit-dc')?.value || '14', 10);
      }
      if (_tfExits.find(x=>x.type===entry.type&&x.item_key===entry.item_key&&x.stat===entry.stat&&x.dc===entry.dc)) {
        showToast('Ten warunek już istnieje', 'warn'); return;
      }
      _tfExits.push(entry);
      _rfExit();
    });

    // ── Pool population helpers ───────────────────────────────
    function _populateEnemySel(pool) {
      const sel = overlay.querySelector('#tf-enemy-sel');
      if (!sel) return;
      const groups = {};
      pool.forEach(e => { const t = String(e.tier||'—'); (groups[t]=groups[t]||[]).push(e); });
      let html = '<option value="">— wybierz wroga —</option>';
      Object.keys(groups).sort().forEach(t => {
        html += `<optgroup label="Tier: ${_esc(t)}">`;
        html += groups[t].map(e=>`<option value="${_esc(e.key)}">${_esc(e.label||e.key)} (HP:${e.hp_base||'?'})</option>`).join('');
        html += '</optgroup>';
      });
      sel.innerHTML = html;
    }

    function _populateItemSel(type) {
      const sel = overlay.querySelector('#tf-item-sel');
      if (!sel) return;
      const pool = _ipPool[type] || [];
      sel.innerHTML = `<option value="">— wybierz —</option>` +
        pool.map(it=>`<option value="${_esc(it.key)}">${_esc(it.label||it.key)}</option>`).join('');
    }

    function _populateRiddleSel(pool) {
      const sel = overlay.querySelector('#tf-riddle-sel');
      if (!sel) return;
      sel.innerHTML = '<option value="">— brak zagadki —</option>' +
        pool.map(r=>`<option value="${_esc(r.key)}" ${r.key===p.riddle_key?'selected':''}>${_esc((r.text||r.key).substring(0,70))}</option>`).join('');
    }

    // ── Async pool load ───────────────────────────────────────
    (async () => {
      try {
        const [er, ir, wr, cr, rr] = await Promise.all([
          apiFetch('/api/admin/enemies'),
          apiFetch('/api/admin/items'),
          apiFetch('/api/admin/weapons'),
          apiFetch('/api/admin/consumables'),
          apiFetch('/api/admin/riddles'),
        ]);
        _epPool = er.items || [];
        _ipPool.item        = (ir.items||[]).filter(it=>!it.item_type||it.item_type!=='armor');
        _ipPool.weapon      = wr.items || [];
        _ipPool.consumable  = cr.items || [];
        _rpPool             = rr.items || [];
        _populateEnemySel(_epPool);
        _populateItemSel(overlay.querySelector('#tf-item-type').value || 'item');
        _populateRiddleSel(_rpPool);
        _rfEnemy(); _rfItem(); _rfExit(); // re-render with names resolved
      } catch(err) { console.warn('[tile-form] pool load failed', err); }
    })();

    // Initial chip render (before pools arrive)
    _rfEnemy(); _rfItem(); _rfState(); _rfExit();
    // Initial door overlay editor render
    _renderDoorEditor();

    // ── Save & actions ────────────────────────────────────────
    overlay.querySelector('#tf-save-btn').addEventListener('click', () => _saveTile(overlay, p.id, {
      enemies:          _tfEnemies,
      items:            _tfItems,
      active_states:    _tfStates,
      exit_conditions:  _tfExits,
      riddle_key:       overlay.querySelector('#tf-riddle-sel')?.value || null,
      door_overlays:    _tfDoorOverlays,
    }));

    overlay.querySelector('#tf-gen-prompt-btn')?.addEventListener('click', () => _aiGeneratePrompt(overlay));
    if (p.id) {
      overlay.querySelector('#tf-generate-btn')?.addEventListener('click', () => _generateTileImage(p.id, overlay));
      overlay.querySelector('#tf-del-btn')?.addEventListener('click', () => deleteTile(p.id));
    }
    // Populate model dropdown — prefer global checkpoint from visual_config, fall back to hardcoded default
    Promise.all([
      apiFetch('/api/admin/images/models'),
      apiFetch('/api/admin/images/config').catch(() => ({})),
    ]).then(([data, cfg]) => {
      const sel = overlay.querySelector('#tf-img-model');
      if (!sel) return;
      const models = data.models || [];
      if (!models.length) { sel.innerHTML = '<option value="">Brak modeli</option>'; return; }
      const globalDefault = (cfg.checkpoint || '').trim() || IMAGE_GEN_DEFAULT_MODEL;
      sel.innerHTML = models.map(m => `<option value="${_esc(m.key)}"${m.key===globalDefault?' selected':''}>${_esc(m.label)} — ${_esc(m.hint||'')}</option>`).join('');
    }).catch(() => {
      const sel = overlay.querySelector('#tf-img-model');
      if (sel) sel.innerHTML = '<option value="">Błąd ładowania</option>';
    });
    // Expose overlay editor refresh so out-of-closure callers can trigger re-render
    overlay._refreshOverlayEditor = _renderOverlayEditor;
    overlay._refreshDoorEditor    = _renderDoorEditor;
  }

  async function _saveTile(overlay, tileId, dynData) {
    try {
      const dyn = dynData || {};
      const payload = {
        label:            overlay.querySelector('#tf-label').value.trim(),
        category_key:     overlay.querySelector('#tf-cat').value,
        doors:            Array.from(overlay.querySelectorAll('#tf-doors input:checked')).map(i=>i.dataset.door),
        door_overlays:    dyn.door_overlays    || {},
        room_description: overlay.querySelector('#tf-desc').value,
        image_gen_prompt: overlay.querySelector('#tf-img-prompt')?.value || '',
        enemies:          dyn.enemies          || [],
        items:            dyn.items            || [],
        active_states:    dyn.active_states    || [],
        exit_conditions:  dyn.exit_conditions  || [],
        riddle_key:       dyn.riddle_key       || null,
        is_boss_tile:     overlay.querySelector('#tf-boss').checked,
        is_active:        overlay.querySelector('#tf-active').checked,
      };
      if (!payload.label) throw new Error('Nazwa jest wymagana');
      if (!payload.doors.length) throw new Error('Wybierz przynajmniej 1 drzwi');
      if (tileId) {
        await apiFetch(`/api/admin/dungeon-tiles/${tileId}`, { method:'PATCH', body:JSON.stringify(payload) });
        showToast('Zapisano', 'success');
      } else {
        const r = await apiFetch('/api/admin/dungeon-tiles', { method:'POST', body:JSON.stringify(payload) });
        showToast(`Utworzono kafelek #${r.id}`, 'success');
      }
      overlay.remove();
      _loadDungeonTiles();
    } catch (e) {
      showToast('Błąd: ' + e.message, 'error');
    }
  }

  async function deleteTile(tileId) {
    const ok = await _adminConfirm('Usunąć kafelek?', 'Kafelek zostanie oznaczony jako nieaktywny (można przywrócić).');
    if (!ok) return;
    try {
      await apiFetch(`/api/admin/dungeon-tiles/${tileId}`, { method: 'DELETE' });
      showToast('Kafelek usunięty', 'success');
      // Close the tile form modal specifically (may be nested among other overlays)
      (document.querySelector('#tf-del-btn')?.closest('.modal-overlay')
        || document.querySelector('.modal-overlay'))?.remove();
      _loadDungeonTiles();
    } catch (e) { showToast('Błąd: ' + e.message, 'error'); }
  }

  function _adminConfirm(title, detail = '') {
    return new Promise(resolve => {
      const ov = document.createElement('div');
      ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:9999;display:flex;align-items:center;justify-content:center';
      ov.innerHTML = `
        <div style="background:#12121e;border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:24px 28px;max-width:360px;width:90%;display:flex;flex-direction:column;gap:14px">
          <div style="font-size:.95rem;font-weight:600;color:#e8e8f8">${_esc(title)}</div>
          ${detail ? `<div style="font-size:.82rem;color:#888;line-height:1.5">${_esc(detail)}</div>` : ''}
          <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:4px">
            <button class="btn btn-secondary btn-sm" id="_ac-cancel">Anuluj</button>
            <button class="btn btn-danger btn-sm" id="_ac-ok">Usuń</button>
          </div>
        </div>`;
      document.body.appendChild(ov);
      const cleanup = val => { ov.remove(); resolve(val); };
      ov.querySelector('#_ac-ok').addEventListener('click', () => cleanup(true));
      ov.querySelector('#_ac-cancel').addEventListener('click', () => cleanup(false));
      ov.addEventListener('click', e => { if (e.target === ov) cleanup(false); });
    });
  }

  async function _aiGenerateTile() {
    const activeCat = document.querySelector('#tile-cat-filter .chip.on')?.dataset.cat || '';
    if (!activeCat) { showToast('Wybierz kategorię kafelków przed generowaniem', 'error'); return; }
    const btn = document.getElementById('tile-ai-gen-btn');
    const orig = btn?.textContent;
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Generuję…'; }
    try {
      const catLabel = document.querySelector(`#tile-cat-filter .chip.on`)?.textContent || activeCat;
      const r = await apiFetch('/api/admin/dungeon-tiles/ai-create', {
        method: 'POST',
        body: JSON.stringify({ category_key: activeCat }),
      });
      showToast(`Kafelek „${r.tile.label}" utworzony`, 'success');
      await _loadDungeonTiles();
      const cats = await _ensureTileCategories();
      openEditTileModal(r.tile.id);
    } catch (e) {
      showToast('Błąd AI: ' + e.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = orig; }
    }
  }

  async function _aiGeneratePrompt(overlay) {
    const catSel = overlay.querySelector('#tf-cat');
    const promptTA = overlay.querySelector('#tf-img-prompt');
    const descTA = overlay.querySelector('#tf-desc');
    const btn = overlay.querySelector('#tf-gen-prompt-btn');
    if (!catSel || !promptTA) return;
    const catKey = catSel.value;
    if (!catKey) { showToast('Wybierz kategorię przed generowaniem promptu', 'error'); return; }
    const orig = btn?.textContent;
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Generuję…'; }
    try {
      const hint = (descTA?.value || '').trim().slice(0, 200);
      const r = await apiFetch('/api/admin/dungeon-tiles/generate-image-prompt', {
        method: 'POST',
        body: JSON.stringify({ category_key: catKey, ...(hint ? { description_hint: hint } : {}) }),
      });
      promptTA.value = r.image_gen_prompt;
      showToast('Prompt wygenerowany', 'success');
    } catch (e) {
      showToast('Błąd AI: ' + e.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = orig; }
    }
  }

  async function _aiGenerateDescription(overlay) {
    if (!overlay) return;
    const tileId = overlay.dataset.tileId;
    if (!tileId) { showToast('Zapisz kafelek przed generowaniem opisu', 'error'); return; }
    const btn = overlay.querySelector('#tf-gen-desc-btn');
    const descTA = overlay.querySelector('#tf-desc');
    if (!descTA) return;
    const orig = btn?.textContent;
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Generuję…'; }
    try {
      const r = await apiFetch(`/api/admin/dungeon-tiles/${tileId}/generate-description`, { method: 'POST' });
      descTA.value = r.room_description;
      showToast('Opis wygenerowany', 'success');
    } catch (e) {
      showToast('Błąd AI: ' + e.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = orig; }
    }
  }

  async function _generateTileImage(tileId, overlay) {
    const btn = overlay.querySelector('#tf-generate-btn');
    const preview = overlay.querySelector('#tf-img-preview');
    if (!btn || !preview) return;
    btn.disabled = true;
    btn.textContent = '⏳ Generowanie (~30s)…';
    preview.innerHTML = '<div style="color:var(--t3)">Generowanie…</div>';
    try {
      const imgPromptVal = (overlay.querySelector('#tf-img-prompt')?.value || '').trim();
      const modelVal = overlay.querySelector('#tf-img-model')?.value || '';
      const body = {};
      if (imgPromptVal) body.image_gen_prompt = imgPromptVal;
      if (modelVal) body.model = modelVal;
      const r = await apiFetch(`/api/admin/dungeon-tiles/${tileId}/generate-image`, { method: 'POST', body: JSON.stringify(body) });
      preview.innerHTML = `<img src="${_esc(r.image_url)}?t=${Date.now()}" style="width:100%;height:100%;object-fit:cover">`;
      showToast('Obraz wygenerowany (zapisz aby zaktualizować inne pola)', 'success');
      overlay._refreshOverlayEditor?.();
      overlay._refreshDoorEditor?.();
      _loadDungeonTiles();
    } catch (e) {
      preview.innerHTML = `<div style="color:#ef4444;padding:14px;text-align:center;font-size:0.78rem">${_esc(e.message)}</div>`;
      showToast('Błąd generacji: ' + e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '🎨 Generuj obraz';
    }
  }

  // ── Tile categories ─────────────────────────────────────────────────────────
  async function _loadTileCategories() {
    const tbody = document.querySelector('#tilecats-table tbody');
    if (!tbody) return;
    tbody.innerHTML = _loading(6);
    try {
      const r = await apiFetch('/api/admin/dungeon-tile-categories');
      const items = r.categories || [];
      _tileCategoriesCache = items;
      if (!items.length) { tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--t3)">Brak kategorii</td></tr>`; return; }
      tbody.innerHTML = items.map(c => `<tr data-key="${_esc(c.key)}">
        <td class="td-sticky td-mono">${_esc(c.key)}</td>
        <td class="td-name">${_esc(c.label)}</td>
        <td class="td-muted">${_esc(c.description || '—')}</td>
        <td class="td-muted" style="font-size:0.72rem">${_esc(c.style_modifier || '—')}</td>
        <td>${c.is_active ? '<span class="badge badge-green">●</span>' : '<span class="badge badge-slate">○</span>'}</td>
        <td class="td-actions">
          <button class="btn-icon" title="Edytuj" onclick='openEditTileCategoryModal(${JSON.stringify(c).replace(/"/g,"&quot;")})'>✎</button>
        </td>
      </tr>`).join('');
    } catch (e) { tbody.innerHTML = _errRow(6, e.message); }
  }

  function openNewTileCategoryModal() { _openTileCatForm(null); }
  function openEditTileCategoryModal(c) { _openTileCatForm(c); }

  function _openTileCatForm(prefill) {
    const p = prefill || {};
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `<div class="modal-box" style="width:560px">
      <div class="modal-head"><span class="modal-title">${p.key ? 'Edytuj kategorię' : 'Nowa kategoria'}</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
      <div class="modal-body">
        <label class="form-label">Klucz (kebab-case) *</label>
        <input id="tcf-key" class="form-input" value="${_esc(p.key || '')}" ${p.key ? 'disabled' : ''}>
        <label class="form-label" style="margin-top:10px">Nazwa *</label>
        <input id="tcf-label" class="form-input" value="${_esc(p.label || '')}">
        <label class="form-label" style="margin-top:10px">Opis</label>
        <textarea id="tcf-desc" class="form-input" rows="2">${_esc(p.description || '')}</textarea>
        <label class="form-label" style="margin-top:10px">Modyfikator stylu (do promptu obrazu)</label>
        <textarea id="tcf-style" class="form-input" rows="2" style="font-family:monospace;font-size:0.78rem">${_esc(p.style_modifier || '')}</textarea>
        <span style="font-size:0.7rem;color:var(--t3)">np. <code>dark stone dungeon walls, torch sconces, medieval</code></span>

        <div style="margin-top:14px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <label class="form-label" style="margin:0;flex:1;min-width:180px">System Prompt MG (kontekst narracji) 🤖</label>
          <button class="btn btn-secondary btn-sm" id="tcf-gen-btn" style="font-size:0.75rem;padding:4px 10px" ${!p.key ? 'disabled title="Zapisz kategorię najpierw, aby wygenerować prompt"' : ''}>
            ✨ Generuj AI
          </button>
        </div>
        <textarea id="tcf-sysprompt" class="form-input" rows="5" style="font-size:0.78rem;line-height:1.5;margin-top:6px" placeholder="Opis klimatu i instrukcje dla MG jak prowadzić narrację w tym lochu...">${_esc(p.system_prompt || '')}</textarea>
        <span style="font-size:0.7rem;color:var(--t3)">Injektowany do LLM gdy gracz wchodzi do lochu tej kategorii. Nadpisuje domyślny kontekst lokacji.</span>
      </div>
      <div class="modal-foot" style="display:flex;gap:8px;justify-content:flex-end;padding:14px">
        <button class="btn btn-secondary btn-sm" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
        <button class="btn btn-primary btn-sm" id="tcf-save">Zapisz</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);

    // AI generate button
    overlay.querySelector('#tcf-gen-btn')?.addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      const key = p.key || overlay.querySelector('#tcf-key').value.trim();
      if (!key) { showToast('Zapisz kategorię najpierw', 'error'); return; }
      btn.disabled = true; btn.textContent = '⏳ Generuję…';
      try {
        const r = await apiFetch(`/api/admin/dungeon-tile-categories/${key}/generate-system-prompt`, { method: 'POST' });
        if (r.system_prompt) {
          overlay.querySelector('#tcf-sysprompt').value = r.system_prompt;
          showToast('Prompt wygenerowany', 'success');
        }
      } catch (e) { showToast('Błąd generowania: ' + e.message, 'error'); }
      finally { btn.disabled = false; btn.textContent = '✨ Generuj AI'; }
    });

    overlay.querySelector('#tcf-save').addEventListener('click', async () => {
      const key = overlay.querySelector('#tcf-key').value.trim();
      const label = overlay.querySelector('#tcf-label').value.trim();
      if (!key || !label) { showToast('Klucz i nazwa są wymagane', 'error'); return; }
      const payload = {
        key, label,
        description: overlay.querySelector('#tcf-desc').value,
        style_modifier: overlay.querySelector('#tcf-style').value,
        system_prompt: overlay.querySelector('#tcf-sysprompt').value,
      };
      try {
        if (p.key) {
          await apiFetch(`/api/admin/dungeon-tile-categories/${p.key}`, { method: 'PATCH', body: JSON.stringify(payload) });
          showToast('Zapisano', 'success');
        } else {
          await apiFetch('/api/admin/dungeon-tile-categories', { method: 'POST', body: JSON.stringify(payload) });
          showToast('Utworzono kategorię', 'success');
        }
        overlay.remove();
        _tileCategoriesCache = null;
        _loadTileCategories();
      } catch (e) { showToast('Błąd: ' + e.message, 'error'); }
    });
  }

  // ── Riddles (Zagadki) ─────────────────────────────────────────────────────────
  function filterRiddles(chip, diff) {
    document.querySelectorAll('#dtab-riddles .filter-group .chip').forEach(c => c.classList.remove('on'));
    chip.classList.add('on');
    document.querySelectorAll('#riddles-table tbody tr').forEach(row => {
      if (!diff) { row.style.display = ''; return; }
      const td = row.querySelector('.diff-badge')?.textContent || '';
      row.style.display = td === diff ? '' : 'none';
    });
  }

  async function _loadRiddles() {
    const tbody = document.querySelector('#riddles-table tbody');
    if (!tbody) return;
    tbody.innerHTML = _loading(7);
    try {
      const d = await apiFetch('/api/admin/riddles');
      const items = d.items || [];
      if (!items.length) { tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--t3)">Brak zagadek</td></tr>`; return; }
      const diffLabel = n => (['','Łatwa','Średnia','Trudna','Bardzo trudna','Legendarna'][n] || `${n}`);
      const diffBadge = n => n <= 1 ? 'badge-green' : n <= 2 ? 'badge-blue' : n <= 3 ? 'badge-amber' : 'badge-red';
      tbody.innerHTML = items.map(r => `<tr data-key="${_esc(r.key)}">
        <td class="td-sticky td-name" style="max-width:220px;white-space:normal;font-size:0.82rem">${_esc(r.text)}</td>
        <td class="td-muted" style="font-size:0.82rem">${_esc(r.answer)}</td>
        <td class="td-muted">${_esc(r.theme||'—')}</td>
        <td><span class="badge ${diffBadge(r.difficulty)} diff-badge">${r.difficulty}</span></td>
        <td class="td-mono">${Array.isArray(r.hints)?r.hints.length:0}</td>
        <td>${r.is_active?'<span class="badge badge-green">●</span>':'<span class="badge badge-slate">○</span>'}</td>
        <td class="td-actions">
          <button class="btn-icon" title="Edytuj" onclick="openEditRiddleModal(${JSON.stringify(r).replace(/"/g,'&quot;')})">✎</button>
          <button class="btn-icon danger" title="Usuń" onclick="deleteRiddle('${_esc(r.key)}',this)">✕</button>
        </td>
      </tr>`).join('');
      const pg = document.getElementById('riddles-count');
      if (pg) pg.textContent = `${items.length} zagadek`;
    } catch(e) { tbody.innerHTML = _errRow(7, e.message); }
  }

  function _openRiddleForm(prefill) {
    const p = prefill || {};
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `<div class="modal-box" style="width:520px">
      <div class="modal-head"><span class="modal-title">${p.key ? 'Edytuj zagadkę' : 'Nowa zagadka'}</span><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button></div>
      <div class="modal-body">
        <div class="form-row"><label class="form-label">Treść zagadki *</label><textarea id="rf-text" class="form-input" rows="3" placeholder="Mam zęby, ale nie gryzę. Co jestem?">${_esc(p.text||'')}</textarea></div>
        <div class="form-row" style="margin-top:8px"><label class="form-label">Odpowiedź *</label><input id="rf-answer" class="form-input" value="${_esc(p.answer||'')}" placeholder="grzebień"></div>
        <div class="form-row" style="margin-top:8px"><label class="form-label">Alternatywne odpowiedzi (oddzielone przecinkami)</label><input id="rf-alts" class="form-input form-mono" value="${_esc(Array.isArray(p.answer_alts)?p.answer_alts.join(','):'')}" placeholder="grzebień,ząbkowany"></div>
        <div class="form-row" style="margin-top:8px"><label class="form-label">Podpowiedzi (oddzielone | )</label><input id="rf-hints" class="form-input" value="${_esc(Array.isArray(p.hints)?p.hints.join(' | '):'')}" placeholder="Jest w łazience | Używasz jej codziennie"></div>
        <div class="form-row" style="margin-top:8px;display:flex;gap:12px">
          <div style="flex:1"><label class="form-label">Trudność (1–5)</label><input id="rf-diff" class="form-input" type="number" min="1" max="5" value="${p.difficulty||1}"></div>
          <div style="flex:1"><label class="form-label">Motyw</label><input id="rf-theme" class="form-input" value="${_esc(p.theme||'general')}" placeholder="general"></div>
        </div>
        <div class="form-row" style="margin-top:8px;align-items:center"><label><input type="checkbox" id="rf-active" ${p.is_active!==false?'checked':''} style="margin-right:6px"> Aktywna</label></div>
        <div style="display:flex;gap:8px;margin-top:16px">
          <button class="btn btn-primary" id="rf-save-btn">Zapisz</button>
          <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
        </div>
      </div>
    </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#rf-text').focus();
    return overlay;
  }

  function openNewRiddleModal() {
    const overlay = _openRiddleForm(null);
    overlay.querySelector('#rf-save-btn').onclick = async () => {
      const text = document.getElementById('rf-text')?.value?.trim();
      const answer = document.getElementById('rf-answer')?.value?.trim();
      if (!text || !answer) { _showToast('Treść i odpowiedź są wymagane.','error'); return; }
      const altsRaw = document.getElementById('rf-alts')?.value?.trim() || '';
      const hintsRaw = document.getElementById('rf-hints')?.value?.trim() || '';
      const body = { text, answer,
        answer_alts: altsRaw ? altsRaw.split(',').map(s=>s.trim()).filter(Boolean) : [],
        hints: hintsRaw ? hintsRaw.split('|').map(s=>s.trim()).filter(Boolean) : [],
        difficulty: parseInt(document.getElementById('rf-diff')?.value)||1,
        theme: document.getElementById('rf-theme')?.value?.trim()||'general',
        is_active: document.getElementById('rf-active')?.checked,
      };
      try {
        await apiFetch('/api/admin/riddles', { method:'POST', body: JSON.stringify(body) });
        _showToast('Zagadka dodana.','success'); overlay.remove(); _loadRiddles();
      } catch(e) { _showToast(e.message||'Błąd.','error'); }
    };
  }

  function openEditRiddleModal(r) {
    if (typeof r === 'string') { try { r = JSON.parse(r); } catch { return; } }
    const overlay = _openRiddleForm(r);
    overlay.querySelector('#rf-save-btn').onclick = async () => {
      const text = document.getElementById('rf-text')?.value?.trim();
      const answer = document.getElementById('rf-answer')?.value?.trim();
      if (!text || !answer) { _showToast('Treść i odpowiedź są wymagane.','error'); return; }
      const altsRaw = document.getElementById('rf-alts')?.value?.trim() || '';
      const hintsRaw = document.getElementById('rf-hints')?.value?.trim() || '';
      const body = { text, answer,
        answer_alts: altsRaw ? altsRaw.split(',').map(s=>s.trim()).filter(Boolean) : [],
        hints: hintsRaw ? hintsRaw.split('|').map(s=>s.trim()).filter(Boolean) : [],
        difficulty: parseInt(document.getElementById('rf-diff')?.value)||1,
        theme: document.getElementById('rf-theme')?.value?.trim()||'general',
        is_active: document.getElementById('rf-active')?.checked,
      };
      try {
        await apiFetch(`/api/admin/riddles/${r.key}`, { method:'PATCH', body: JSON.stringify(body) });
        _showToast('Zapisano.','success'); overlay.remove(); _loadRiddles();
      } catch(e) { _showToast(e.message||'Błąd.','error'); }
    };
  }

  async function deleteRiddle(key, btn) {
    if (!confirm(`Usunąć zagadkę "${key}"?`)) return;
    btn.disabled = true;
    try {
      await apiFetch(`/api/admin/riddles/${key}`, { method:'DELETE' });
      _showToast('Usunięto.','success'); _loadRiddles();
    } catch(e) { _showToast(e.message||'Błąd.','error'); btn.disabled = false; }
  }

// ─── Module entry ─────────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = _sectionHtml();

  // Stab-bar tab switcher (was inline at monolith script-load; moved here)
  panel.querySelector('#dungeons-stab-bar')?.addEventListener('click', e => {
    const btn = e.target.closest('.stab[data-dtab]');
    if (!btn) return;
    const tab = btn.dataset.dtab;
    document.querySelectorAll('#dungeons-stab-bar .stab').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('#section-dungeons .stab-panel').forEach(p => p.classList.toggle('active', p.id === `dtab-${tab}`));
    const hdrBtn = document.getElementById('dungeons-header-btns');
    if (hdrBtn) {
      if (tab === 'riddles')       hdrBtn.innerHTML = '<button class="btn btn-primary btn-sm" onclick="openNewRiddleModal()">+ Nowa zagadka</button>';
      else if (tab === 'tiles')    hdrBtn.innerHTML = '<button class="btn btn-primary btn-sm" onclick="openNewTileModal()">+ Nowy kafelek</button>';
      else if (tab === 'tilecats') hdrBtn.innerHTML = '<button class="btn btn-primary btn-sm" onclick="openNewTileCategoryModal()">+ Nowa kategoria</button>';
      else                          hdrBtn.innerHTML = '<button class="btn btn-primary btn-sm" onclick="openNewDungeonModal()">+ Nowy loch</button>';
    }
    if (tab === 'riddles'  && !document.querySelector('#riddles-table tbody tr[data-key]')) _loadRiddles();
    if (tab === 'tiles'    && !document.querySelector('#tiles-grid .tile-card')) _loadDungeonTiles();
    if (tab === 'tilecats' && !document.querySelector('#tilecats-table tbody tr[data-key]')) _loadTileCategories();
    if (typeof _fabUpdate === 'function') _fabUpdate();
  });

  Object.assign(window, {
    filterTableGeneric, filterDungeons,
    openNewDungeonModal, openEditDungeonModal, deleteDungeon,
    openNewTileModal, openEditTileModal, deleteTile, _generateTileImage, _aiGenerateTile, _aiGenerateDescription, _filterTiles,
    openNewTileCategoryModal, openEditTileCategoryModal,
    openNewRiddleModal, openEditRiddleModal, deleteRiddle,
    filterRiddles,
  });
  _loadDungeons();
}
