// FADM-P0 (#402) — pomocnik tabel + escape (port z monolitu, _ROW_REGISTRY).
export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

/**
 * Wire click-to-sort on all <th> containing .sort-icon.
 * Reads data-sort-val from <td> cells (positional — col index of th).
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

  ths.forEach((th, colIdx) => {
    const inner = th.querySelector('.th-inner');
    const icon = inner && inner.querySelector('.sort-icon');
    if (!icon) return; // not sortable

    let asc = icon.classList.contains('asc');

    inner.style.cursor = 'pointer';
    inner.addEventListener('click', () => {
      // Toggle direction; first click → asc (unless already active+asc → switch to desc)
      const wasActive = inner.classList.contains('sorted');
      asc = wasActive ? !asc : true;

      // Reset all headers
      ths.forEach(t => {
        const i2 = t.querySelector('.th-inner');
        const s2 = i2 && i2.querySelector('.sort-icon');
        if (i2) i2.classList.remove('sorted');
        if (s2) { s2.classList.remove('asc', 'desc'); }
      });

      // Mark this one active
      inner.classList.add('sorted');
      icon.classList.add(asc ? 'asc' : 'desc');

      // Sort tbody rows
      const tbody = table.querySelector('tbody');
      if (!tbody) return;
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const numeric = rows.every(r => {
        const td = r.querySelectorAll('td')[colIdx];
        const v = td ? td.dataset.sortVal : '';
        return v === '' || v === undefined || !isNaN(Number(v));
      });

      rows.sort((a, b) => {
        const tda = a.querySelectorAll('td')[colIdx];
        const tdb = b.querySelectorAll('td')[colIdx];
        const va = tda ? (tda.dataset.sortVal ?? '') : '';
        const vb = tdb ? (tdb.dataset.sortVal ?? '') : '';
        let cmp = numeric
          ? (Number(va) || 0) - (Number(vb) || 0)
          : va.localeCompare(vb, 'pl', { sensitivity: 'base' });
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
