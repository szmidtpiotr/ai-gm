// FADM-P0 (#402) — pomocnik tabel + escape (port z monolitu, _ROW_REGISTRY).
export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
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
