// FADM-P0 (#402) — toast (port z monolitu, zachowanie zgodne).
export function showToast(msg, type = 'info', ms = 3200) {
  let host = document.getElementById('toast-host');
  if (!host) {
    host = document.createElement('div');
    host.id = 'toast-host';
    host.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:10000;display:flex;flex-direction:column;gap:8px;pointer-events:none';
    document.body.appendChild(host);
  }
  const colors = { info: '#3b82f6', success: '#22c55e', error: '#ef4444', warn: '#f59e0b' };
  const el = document.createElement('div');
  el.textContent = msg;
  el.style.cssText = `pointer-events:auto;background:#14141c;color:#eee;border:1px solid ${colors[type] || colors.info};border-left:3px solid ${colors[type] || colors.info};border-radius:8px;padding:10px 14px;font-size:.85rem;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px`;
  host.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(() => el.remove(), 300); }, ms);
}
