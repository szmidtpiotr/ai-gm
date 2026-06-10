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

  // Skip action columns (last th if it has no visible label or is "Akcje")
  const actionColIdx = ths.findIndex(th => {
    const txt = th.textContent?.trim().toLowerCase();
    return txt === 'akcje' || txt === 'actions' || !txt;
  });

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
      const rows = Array.from(tbody.querySelectorAll('tr:not([style*="display: none"])'));

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
