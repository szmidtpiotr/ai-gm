// FADM-P0 (#402) — prosty modal/confirm (port z monolitu).
export function openModal(title, contentHtml, { width = 480 } = {}) {
  closeModal();
  const overlay = document.createElement('div');
  overlay.id = 'admin-modal';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px';
  overlay.innerHTML = `<div style="background:#14141c;border:1px solid rgba(245,158,11,.25);border-radius:12px;max-width:${width}px;width:100%;max-height:88vh;overflow-y:auto;box-shadow:0 10px 40px rgba(0,0,0,.5)">
      <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid rgba(255,255,255,.06)">
        <div style="font-weight:700;color:#f5deb3">${title}</div>
        <button id="admin-modal-close" style="background:none;border:none;color:#999;font-size:1.2rem;cursor:pointer">✕</button>
      </div>
      <div style="padding:16px 18px">${contentHtml}</div>
    </div>`;
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
  overlay.querySelector('#admin-modal-close').addEventListener('click', closeModal);
  document.body.appendChild(overlay);
  return overlay;
}

export function closeModal() {
  document.getElementById('admin-modal')?.remove();
}

export function confirmDialog(message) {
  return Promise.resolve(window.confirm(message));
}
