// FADM-P0 (#402) — pomocniki formularzy (port z monolitu).
import { esc } from './table.js';

// Pole tekstowe/number/select; fields = [{name,label,type,options?,value?}].
export function renderForm(fields) {
  return fields.map(f => {
    const id = `f-${f.name}`;
    let input;
    if (f.type === 'select') {
      input = `<select id="${id}" class="adm-input">${(f.options || []).map(o =>
        `<option value="${esc(o.value)}"${o.value === f.value ? ' selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`;
    } else if (f.type === 'textarea') {
      input = `<textarea id="${id}" class="adm-input" rows="3">${esc(f.value ?? '')}</textarea>`;
    } else {
      input = `<input id="${id}" class="adm-input" type="${f.type || 'text'}" value="${esc(f.value ?? '')}">`;
    }
    return `<div style="display:flex;flex-direction:column;gap:4px;margin-bottom:10px">
      <label style="font-size:.76rem;color:#9aa">${esc(f.label)}</label>${input}</div>`;
  }).join('');
}

export function readForm(fields) {
  const out = {};
  for (const f of fields) {
    const el = document.getElementById(`f-${f.name}`);
    if (!el) continue;
    out[f.name] = f.type === 'number' ? (parseFloat(el.value) || 0) : el.value;
  }
  return out;
}
