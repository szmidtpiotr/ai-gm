// FADM-P0 (#402) — shared API helper, wyciągnięte 1:1 z admin_panel_v3 monolitu.
// Sygnatura apiFetch bez zmian: sekcje portowane bez przepisywania wywołań.
export const ADMIN_TOKEN_KEY = 'aigm_admin_token';

export class APIError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'APIError';
    this.status = status;
  }
}

function _buildUrl(path) {
  const p = String(path);
  if (p.startsWith('http')) return p;
  return p.startsWith('/') ? p : `/${p}`;
}

// Identyczne zachowanie co monolit: Bearer token z localStorage, JSON domyślnie,
// 401 → zdarzenie 'admin-unauthorized' (skorupa pokazuje login), błąd → APIError.
export async function apiFetch(path, opts = {}) {
  const token = localStorage.getItem(ADMIN_TOKEN_KEY);
  const h = { ...(opts.headers || {}) };
  if (!h['Content-Type'] && !(opts.body instanceof FormData)) h['Content-Type'] = 'application/json';
  if (token) h['Authorization'] = `Bearer ${token}`;

  const r = await fetch(_buildUrl(path), { ...opts, headers: h });
  if (r.status === 401) {
    window.dispatchEvent(new CustomEvent('admin-unauthorized'));
    throw new APIError('401', 401);
  }
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    const det = e.detail;
    const msg = Array.isArray(det)
      ? det.map(d => d.msg || JSON.stringify(d)).join('; ')
      : (det || `HTTP ${r.status}`);
    throw new APIError(msg, r.status);
  }
  // Niektóre endpointy zwracają 204/no-body.
  const txt = await r.text();
  return txt ? JSON.parse(txt) : null;
}
