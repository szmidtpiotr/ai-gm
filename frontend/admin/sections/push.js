/**
 * FADM-P12 (#414) — sekcja Push: powiadomienia push do graczy.
 */
import { apiFetch } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

// ── Helpers ────────────────────────────────────────────────────────────────────
function _esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── State ─────────────────────────────────────────────────────────────────────
let _pushData = [];

// ── Functions ─────────────────────────────────────────────────────────────────

async function _loadPush() {
  const tbody = document.getElementById('push-tbody');
  if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--t3)">Ładowanie…</td></tr>`;
  try {
    _pushData = (await apiFetch('/api/admin/push/subscriptions')).subscriptions || [];
    const total = _pushData.length;
    const subscribed = _pushData.filter(r => r.subscription_count > 0).length;
    document.getElementById('push-total').textContent = total;
    document.getElementById('push-subscribed').textContent = subscribed;
    document.getElementById('push-unsubscribed').textContent = total - subscribed;
    document.getElementById('push-sub').textContent = `${subscribed} z ${total} graczy ma aktywne powiadomienia`;

    // populate select
    const sel = document.getElementById('push-target-user');
    if (sel) {
      sel.innerHTML = '<option value="">— wybierz gracza —</option>' +
        _pushData.map(r => `<option value="${r.user_id}">[${r.subscription_count > 0 ? '✅' : '⬜'}] ${r.username}${r.display_name ? ' — '+r.display_name : ''}</option>`).join('');
    }

    if (tbody) {
      tbody.innerHTML = _pushData.map(r => {
        const hasSub = r.subscription_count > 0;
        const statusBadge = hasSub
          ? `<span style="color:var(--green,#4caf50);font-weight:600">✅ Aktywna</span>`
          : `<span style="color:var(--t3)">⬜ Brak</span>`;
        const lastSub = r.last_subscribed_at ? new Date(r.last_subscribed_at).toLocaleString('pl-PL') : '—';
        return `<tr>
          <td data-label="Gracz"><b>${r.username}</b>${r.display_name ? '<br><span style="color:var(--t3);font-size:12px">'+r.display_name+'</span>' : ''}</td>
          <td data-label="Status">${statusBadge}</td>
          <td data-label="Subskrypcji" style="text-align:center">${r.subscription_count}</td>
          <td data-label="Ostatnia rej." style="font-size:12px;color:var(--t3)">${lastSub}</td>
          <td data-label="Akcja" style="display:flex;gap:6px;align-items:center">
            ${hasSub ? `<button class="btn btn-secondary btn-sm" onclick="_quickTestPush(${r.user_id},'${r.username}')">🔔 Test</button>` : '<span style="color:var(--t3);font-size:12px">—</span>'}
            ${hasSub ? `<button class="btn btn-sm" style="background:rgba(229,57,53,.12);border:1px solid rgba(229,57,53,.3);color:var(--red,#e53935)" onclick="_revokePushSubscription(${r.user_id},'${r.username}')" title="Usuń subskrypcję — gracz będzie pytany o zgodę ponownie">✕ Usuń</button>` : ''}
          </td>
        </tr>`;
      }).join('') || `<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--t3)">Brak użytkowników</td></tr>`;
    }
  } catch(e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--red)">Błąd: ${e.message}</td></tr>`;
  }
}

async function _revokePushSubscription(userId, username) {
  if (!confirm(`Usunąć subskrypcję push dla @${username}?\nGracz będzie pytany o zgodę ponownie przy kolejnym logowaniu.`)) return;
  try {
    await apiFetch(`/api/admin/push/subscriptions/${userId}`, { method: 'DELETE' });
    _loadPush();
  } catch(e) {
    alert('Błąd: ' + e.message);
  }
}

async function _sendTestPush() {
  const userId = parseInt(document.getElementById('push-target-user').value);
  if (!userId) { alert('Wybierz gracza'); return; }
  const title = document.getElementById('push-test-title').value.trim() || 'AI-GM — test powiadomienia';
  const body = document.getElementById('push-test-body').value.trim() || 'Push notifications działają!';
  const icon = document.getElementById('push-test-icon').value.trim() || null;
  const image = document.getElementById('push-test-image').value.trim() || null;
  const vibrateRaw = document.getElementById('push-test-vibrate').value.trim();
  const vibrate = vibrateRaw ? vibrateRaw.split(',').map(v => parseInt(v.trim())).filter(n => !isNaN(n)) : null;
  const url = document.getElementById('push-test-url').value.trim() || '/';
  const resultEl = document.getElementById('push-test-result');
  resultEl.style.display = 'none';
  const payload = { user_id: userId, title, body, url };
  if (icon) payload.icon = icon;
  if (image) payload.image = image;
  if (vibrate && vibrate.length) payload.vibrate = vibrate;
  try {
    await apiFetch('/api/admin/push/send-test', { method:'POST', body: JSON.stringify(payload) });
    resultEl.style.display = 'block';
    resultEl.style.color = 'var(--green,#4caf50)';
    resultEl.textContent = '✅ Powiadomienie wysłane! Sprawdź urządzenie gracza.';
  } catch(e) {
    resultEl.style.display = 'block';
    resultEl.style.color = 'var(--red,#e53935)';
    resultEl.textContent = '❌ Błąd: ' + e.message;
  }
}

async function _quickTestPush(userId, username) {
  try {
    await apiFetch('/api/admin/push/send-test', { method:'POST', body: JSON.stringify({ user_id: userId, body: `Test dla ${username} — powiadomienia działają!` }) });
    showToast(`Push wysłany do ${username}`, 'success');
  } catch(e) {
    showToast('Błąd: ' + e.message, 'error');
  }
}

// ── Init ───────────────────────────────────────────────────────────────────────
export async function init(panel) {
  panel.innerHTML = `<div id="section-push">
      <div class="section-header">
        <div>
          <div class="section-heading">🔔 Push Notifications</div>
          <div class="section-sub" id="push-sub">Status subskrypcji + testy</div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="_loadPush()">⟳ Odśwież</button>
      </div>

      <!-- Stats -->
      <div class="stat-grid" style="margin-bottom:16px">
        <div class="stat-card">
          <div class="stat-label">Łącznie graczy</div>
          <div class="stat-row"><div class="stat-value" id="push-total">—</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Z aktywną subskrypcją</div>
          <div class="stat-row"><div class="stat-value" id="push-subscribed" style="color:var(--green,#4caf50)">—</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Bez subskrypcji</div>
          <div class="stat-row"><div class="stat-value" id="push-unsubscribed" style="color:var(--red,#e53935)">—</div></div>
        </div>
      </div>

      <!-- Send test form -->
      <div class="card" style="margin-bottom:16px;padding:20px">
        <div style="font-weight:600;margin-bottom:14px;font-size:14px">🔔 Wyślij testowe powiadomienie</div>

        <!-- Row 1: target + title + body -->
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
          <div style="flex:1;min-width:150px">
            <div style="font-size:11px;color:var(--t3);margin-bottom:4px">Gracz *</div>
            <select id="push-target-user" class="input" style="width:100%">
              <option value="">— wybierz gracza —</option>
            </select>
          </div>
          <div style="flex:2;min-width:180px">
            <div style="font-size:11px;color:var(--t3);margin-bottom:4px">Tytuł</div>
            <input id="push-test-title" class="input" style="width:100%" placeholder="AI-GM — test powiadomienia" />
          </div>
          <div style="flex:2;min-width:180px">
            <div style="font-size:11px;color:var(--t3);margin-bottom:4px">Treść</div>
            <input id="push-test-body" class="input" style="width:100%" placeholder="Push notifications działają!" />
          </div>
        </div>

        <!-- Row 2: visual options -->
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
          <div style="flex:2;min-width:180px">
            <div style="font-size:11px;color:var(--t3);margin-bottom:4px">Ikona URL <span style="opacity:0.5">(opcjonalnie, zastąpi domyślną)</span></div>
            <input id="push-test-icon" class="input" style="width:100%" placeholder="/front/icon-192.png" />
          </div>
          <div style="flex:2;min-width:180px">
            <div style="font-size:11px;color:var(--t3);margin-bottom:4px">Obraz (baner) URL <span style="opacity:0.5">(Chrome Android)</span></div>
            <input id="push-test-image" class="input" style="width:100%" placeholder="https://... lub /images/..." />
          </div>
          <div style="flex:1;min-width:140px">
            <div style="font-size:11px;color:var(--t3);margin-bottom:4px">Wibracja <span style="opacity:0.5">ms,przerwa,ms</span></div>
            <input id="push-test-vibrate" class="input" style="width:100%" placeholder="200,100,200" />
          </div>
          <div style="flex:1;min-width:140px">
            <div style="font-size:11px;color:var(--t3);margin-bottom:4px">URL po kliknięciu</div>
            <input id="push-test-url" class="input" style="width:100%" placeholder="/" />
          </div>
        </div>

        <div style="display:flex;align-items:center;gap:12px">
          <button class="btn btn-primary btn-sm" onclick="_sendTestPush()">🔔 Wyślij test</button>
          <div id="push-test-result" style="font-size:13px;display:none"></div>
        </div>
      </div>

      <!-- Subscriptions table -->
      <div class="card" style="overflow:hidden">
        <div class="table-wrap data-table--cards" style="overflow-x:auto">
          <table class="data-table" id="push-table">
            <thead><tr>
              <th>Gracz</th>
              <th>Status</th>
              <th>Subskrypcji</th>
              <th>Ostatnia rejestracja</th>
              <th>Akcja</th>
            </tr></thead>
            <tbody id="push-tbody"><tr><td colspan="5" style="text-align:center;padding:32px;color:var(--t3)">Ładowanie…</td></tr></tbody>
          </table>
        </div>
      </div>
  </div>`;
  _loadPush();
}

Object.assign(window, { _sendTestPush, _quickTestPush, _revokePushSubscription, _loadPush });
