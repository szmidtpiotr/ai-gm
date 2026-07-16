// FADM-P0 (#402) — pomocnik tabel + escape (port z monolitu, _ROW_REGISTRY).
export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

/**
 * Wire click-to-sort on ALL <th> elements in the table.
 * Auto-detects numeric vs string; extracts data-sort-val from cells or uses text content.
 * Call after injecting table HTML. Safe to call multiple times (idempotent).
 *
 * @param {HTMLElement|string} tableOrId — table element or its id
 */
export function initSortableTable(tableOrId) {
  const table = typeof tableOrId === 'string'
    ? document.getElementById(tableOrId)
    : tableOrId;
  if (!table || table._sortWired) return;
  table._sortWired = true;

  const thead = table.querySelector('thead tr');
  if (!thead) return;

  const ths = Array.from(thead.querySelectorAll('th'));
  if (!ths.length) return;

  // Find action column: search from RIGHT for explicit "Akcje"/"Actions" label,
  // then fall back to rightmost unlabeled non-check column.
  let actionColIdx = -1;
  for (let i = ths.length - 1; i >= 0; i--) {
    const txt = ths[i].textContent?.trim().toLowerCase();
    if (txt === 'akcje' || txt === 'actions') { actionColIdx = i; break; }
  }
  if (actionColIdx < 0) {
    for (let i = ths.length - 1; i >= 0; i--) {
      if (!ths[i].classList.contains('col-check') && !ths[i].textContent?.trim()) {
        actionColIdx = i; break;
      }
    }
  }

  ths.forEach((th, colIdx) => {
    // Skip action/checkbox columns
    if (colIdx === actionColIdx || th.classList.contains('col-check')) return;

    const inner = th.querySelector('.th-inner') || th;
    if (!inner.textContent?.trim()) return; // Skip empty headers

    let asc = true;
    let sortActive = false;

    // Ensure sort-icon exists (create if missing)
    let icon = inner.querySelector('.sort-icon');
    if (!icon) {
      icon = document.createElement('span');
      icon.className = 'sort-icon asc';
      icon.textContent = '▲';
      icon.style.marginLeft = '4px';
      icon.style.opacity = '0.3';
      inner.appendChild(icon);
    }

    inner.style.cursor = 'pointer';
    inner.style.userSelect = 'none';

    inner.addEventListener('click', () => {
      // Toggle direction
      const wasActive = sortActive;
      asc = wasActive ? !asc : true;
      sortActive = true;

      // Reset all headers
      ths.forEach(t => {
        const i2 = t.querySelector('.th-inner') || t;
        const s2 = i2.querySelector('.sort-icon');
        if (i2 !== inner) {
          i2.classList.remove('sorted');
          if (s2) { s2.classList.remove('asc', 'desc'); s2.style.opacity = '0.3'; }
        }
      });

      // Mark this one active
      inner.classList.add('sorted');
      icon.classList.remove('asc', 'desc');
      icon.classList.add(asc ? 'asc' : 'desc');
      icon.style.opacity = '1';

      // Sort tbody rows
      const tbody = table.querySelector('tbody');
      if (!tbody) return;
      // Sort ALL rows (filtered-out ones too) so clearing a filter keeps sorted order.
      const rows = Array.from(tbody.querySelectorAll('tr'));

      // Auto-detect numeric
      const numeric = rows.every(r => {
        const td = r.querySelectorAll('td')[colIdx];
        if (!td) return false;
        const v = (td.dataset.sortVal ?? td.textContent ?? '').trim();
        return v === '' || !isNaN(Number(v));
      });

      rows.sort((a, b) => {
        const tda = a.querySelectorAll('td')[colIdx];
        const tdb = b.querySelectorAll('td')[colIdx];

        // Extract value: prefer data-sort-val, fallback to text content
        const getVal = (td) => {
          if (!td) return '';
          return (td.dataset.sortVal ?? td.textContent ?? '').trim();
        };

        const va = getVal(tda);
        const vb = getVal(tdb);

        let cmp;
        if (numeric) {
          cmp = (Number(va) || 0) - (Number(vb) || 0);
        } else {
          cmp = va.localeCompare(vb, 'pl', { sensitivity: 'base' });
        }
        return asc ? cmp : -cmp;
      });

      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

function _resolveTable(tableOrId) {
  return typeof tableOrId === 'string' ? document.getElementById(tableOrId) : tableOrId;
}

function _storageKey(table, suffix) {
  return `aigm-tbl-${table.id || 'unnamed'}-${suffix}`;
}

/**
 * #591 — resizable columns with localStorage persistence.
 * Adds a drag-grip to the right edge of every <th>; widths persist per table id.
 * Idempotent.
 */
export function enableColumnResize(tableOrId) {
  const table = _resolveTable(tableOrId);
  if (!table || table._resizeWired) return;
  const ths = Array.from(table.querySelectorAll('thead tr:first-child th'));
  if (!ths.length) return;
  table._resizeWired = true;

  const key = _storageKey(table, 'colw');
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch { saved = {}; }

  ths.forEach((th, i) => {
    if (saved[i]) th.style.width = saved[i];
    if (getComputedStyle(th).position === 'static') th.style.position = 'relative';
    const grip = document.createElement('span');
    grip.className = 'col-resize-grip';
    grip.style.cssText = 'position:absolute;top:0;right:0;width:6px;height:100%;cursor:col-resize;user-select:none;z-index:2';
    grip.addEventListener('click', e => e.stopPropagation());  // never trigger sort
    grip.addEventListener('mousedown', e => {
      e.preventDefault(); e.stopPropagation();
      const startX = e.pageX;
      const startW = th.offsetWidth;
      const onMove = ev => { th.style.width = Math.max(40, startW + ev.pageX - startX) + 'px'; };
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        saved[i] = th.style.width;
        try { localStorage.setItem(key, JSON.stringify(saved)); } catch { /* quota */ }
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
    th.appendChild(grip);
  });
}

/**
 * #1027 → hybrid rebuild — per-column filter: text <input> (substring, case +
 * Polish-diacritic insensitive) PLUS a ▾ button opening a dropdown of the column's
 * distinct values (built lazily from the current tbody, so async-loaded data works).
 * Picking a value filters by exact match; typing switches back to substring mode.
 * Multiple column filters combine with AND. Idempotent.
 */
export function enableColumnFilters(tableOrId) {
  const table = _resolveTable(tableOrId);
  if (!table || table._filterWired) return;
  const thead = table.querySelector('thead');
  const headRow = thead?.querySelector('tr');
  const tbody = table.querySelector('tbody');
  if (!headRow || !tbody) return;
  table._filterWired = true;

  const ths = Array.from(headRow.querySelectorAll('th'));
  const filterRow = document.createElement('tr');
  filterRow.className = 'col-filter-row';
  ths.forEach((th, colIdx) => {
    const cell = document.createElement('th');
    cell.style.padding = '2px 4px';
    // Mirror visibility classes so the filter cell hides/shows in lockstep with its
    // column (e.g. `detail-col` toggled by "Szczegóły"). Without this the filter row
    // keeps all cells visible while the header/body hide some → inputs shift under
    // the wrong columns (#591).
    if (th.classList.contains('detail-col')) cell.classList.add('detail-col');
    if (th.classList.contains('td-sticky')) cell.classList.add('td-sticky');
    const label = (th.querySelector('.th-inner') || th).textContent?.trim().toLowerCase() || '';
    const skip = th.classList.contains('col-check') || label === 'akcje' || label === 'actions' || !label;
    if (!skip) {
      const wrap = document.createElement('div');
      wrap.className = 'col-filter-wrap';
      const input = document.createElement('input');
      input.type = 'text';
      input.className = 'col-filter-input';
      input.dataset.colIdx = String(colIdx);
      input.placeholder = 'filtruj…';
      // Debounce ~150 ms (starting value) so filtering doesn't fire per keystroke.
      let t = null;
      input.addEventListener('input', () => {
        delete input.dataset.exact;  // typing = substring mode
        clearTimeout(t);
        t = setTimeout(() => _applyColFilters(table), 150);
      });
      input.addEventListener('click', e => e.stopPropagation());  // don't trigger header sort
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'col-filter-toggle';
      btn.textContent = '▾';
      btn.title = 'Wybierz wartość z listy';
      btn.addEventListener('click', e => {
        e.stopPropagation();
        _toggleFilterMenu(table, colIdx, input, btn);
      });
      wrap.appendChild(input);
      wrap.appendChild(btn);
      cell.appendChild(wrap);
    }
    filterRow.appendChild(cell);
  });
  thead.appendChild(filterRow);
}

// ── Dropdown menu for the hybrid column filter ────────────────────────────────
let _openMenu = null;

function _closeFilterMenu() {
  if (!_openMenu) return;
  _openMenu.remove();
  _openMenu = null;
  document.removeEventListener('click', _onDocClick, true);
  window.removeEventListener('scroll', _onAnyScroll, true);
  window.removeEventListener('resize', _closeFilterMenu);
}

function _onDocClick(e) {
  if (_openMenu && !_openMenu.contains(e.target)) _closeFilterMenu();
}

function _onAnyScroll(e) {
  // Scrolling inside the menu itself must not close it.
  if (_openMenu && _openMenu.contains(e.target)) return;
  _closeFilterMenu();
}

function _toggleFilterMenu(table, colIdx, input, btn) {
  const reopenSame = _openMenu && _openMenu._forInput === input;
  _closeFilterMenu();
  if (reopenSame) return;  // second click on the same ▾ = close only

  // Distinct values from the CURRENT tbody (data may have loaded/changed since wire-up).
  const tbody = table.querySelector('tbody');
  const seen = new Map();  // normalized → first display form
  Array.from(tbody?.querySelectorAll('tr') || []).forEach(row => {
    const td = row.querySelectorAll('td')[colIdx];
    const raw = (td?.textContent || '').trim();
    if (!raw) return;
    const norm = _normalizePL(raw);
    if (!seen.has(norm)) seen.set(norm, raw);
  });
  const values = Array.from(seen.values())
    .sort((a, b) => a.localeCompare(b, 'pl', { numeric: true, sensitivity: 'base' }));

  const menu = document.createElement('div');
  menu.className = 'col-filter-menu';
  menu._forInput = input;

  const addOpt = (labelText, { clear = false, active = false } = {}) => {
    const opt = document.createElement('div');
    opt.className = 'col-filter-opt' + (clear ? ' col-filter-opt-clear' : '') + (active ? ' active' : '');
    opt.textContent = labelText;
    opt.addEventListener('click', () => {
      if (clear) {
        input.value = '';
        delete input.dataset.exact;
      } else {
        input.value = labelText;
        input.dataset.exact = '1';  // dropdown pick = exact match
      }
      _applyColFilters(table);
      _closeFilterMenu();
    });
    menu.appendChild(opt);
  };

  addOpt('— wszystkie —', { clear: true, active: !input.value });
  values.forEach(v => addOpt(v, { active: input.dataset.exact === '1' && input.value === v }));
  if (!values.length) {
    const empty = document.createElement('div');
    empty.className = 'col-filter-opt col-filter-opt-empty';
    empty.textContent = '(brak wartości)';
    menu.appendChild(empty);
  }

  // Fixed positioning under the button — escapes the table's overflow container.
  const r = btn.getBoundingClientRect();
  const cellR = btn.closest('th')?.getBoundingClientRect();
  document.body.appendChild(menu);
  const w = Math.max(menu.offsetWidth, cellR ? cellR.width : 0);
  menu.style.minWidth = w + 'px';
  const left = Math.min(cellR ? cellR.left : r.left, window.innerWidth - menu.offsetWidth - 8);
  menu.style.left = Math.max(4, left) + 'px';
  menu.style.top = (r.bottom + 2) + 'px';
  menu.style.maxHeight = Math.max(120, window.innerHeight - r.bottom - 16) + 'px';

  _openMenu = menu;
  document.addEventListener('click', _onDocClick, true);
  window.addEventListener('scroll', _onAnyScroll, true);
  window.addEventListener('resize', _closeFilterMenu);
}

// Lowercase + strip Polish diacritics so "miecz" matches "Miecz", "łuk" matches "luk".
function _normalizePL(s) {
  return (s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')   // combining marks (ó→o, ą→a, ę→e, ć→c…)
    .replace(/ł/g, 'l');          // ł has no NFD decomposition — map explicitly
}

function _applyColFilters(table) {
  const filterRow = table.querySelector('thead .col-filter-row');
  const tbody = table.querySelector('tbody');
  if (!filterRow || !tbody) return;
  const inputs = Array.from(filterRow.querySelectorAll('th')).map(th => th.querySelector('input'));
  const filters = inputs.map(inp => ({
    needle: _normalizePL((inp?.value || '').trim()),
    exact: inp?.dataset.exact === '1',
  }));
  Array.from(tbody.querySelectorAll('tr')).forEach(row => {
    const cells = row.querySelectorAll('td');
    let show = true;
    filters.forEach((f, i) => {
      if (!f.needle) return;
      const txt = _normalizePL((cells[i]?.textContent || '').trim());
      if (f.exact ? txt !== f.needle : !txt.includes(f.needle)) show = false;
    });
    row.style.display = show ? '' : 'none';
  });
}

/**
 * #591 — wire all table enhancements at once: sort + resize + per-column filter.
 * Drop-in replacement for initSortableTable() at section-mount/observer time.
 */
export function enhanceTable(tableOrId) {
  const table = _resolveTable(tableOrId);
  if (!table) return;
  initSortableTable(table);
  enableColumnResize(table);
  enableColumnFilters(table);
}

// Render prostej tabeli: columns = [{key,label,render?}], rows = [obj].
export function renderTable(columns, rows, { empty = 'Brak danych' } = {}) {
  if (!rows || !rows.length) {
    return `<div style="color:#888;text-align:center;padding:24px;font-size:.85rem">${esc(empty)}</div>`;
  }
  const head = columns.map(c => `<th style="text-align:left;padding:8px 10px;color:#9aa;font-size:.74rem;border-bottom:1px solid rgba(255,255,255,.08)">${esc(c.label)}</th>`).join('');
  const body = rows.map(r => '<tr>' + columns.map(c => {
    const v = c.render ? c.render(r) : esc(r[c.key]);
    return `<td style="padding:8px 10px;font-size:.84rem;color:#ddd;border-bottom:1px solid rgba(255,255,255,.04)">${v}</td>`;
  }).join('') + '</tr>').join('');
  return `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse">
    <thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
