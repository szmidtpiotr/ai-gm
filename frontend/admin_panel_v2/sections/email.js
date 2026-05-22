/* Stage 11-C C14 — Email / SMTP config section */
export async function init(panel) {
    panel.innerHTML = renderEmailSection();
    await loadEmailConfig();
    bindEvents();
}

function renderEmailSection() {
    return `
<div class="section-header">
  <h2 class="section-title">&#9881; Konfiguracja Email (SMTP)</h2>
  <p class="section-desc">Ustawienia serwera email do wysyłania zaproszeń, weryfikacji i resetowania haseł.</p>
</div>

<div class="card" style="padding: 24px; margin-bottom: 24px;">
  <h3 style="margin-bottom: 16px; color: var(--text-muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em;">Serwer SMTP</h3>
  <div class="form-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">
    <div class="form-group" style="grid-column: 1 / -1">
      <label class="form-label">Host SMTP</label>
      <input type="text" id="smtp-host" class="form-input" placeholder="smtp.gmail.com">
    </div>
    <div class="form-group">
      <label class="form-label">Port</label>
      <input type="number" id="smtp-port" class="form-input" placeholder="587" value="587">
    </div>
    <div class="form-group">
      <label class="form-label">TLS (STARTTLS)</label>
      <select id="smtp-use-tls" class="form-input">
        <option value="true">Włączone (port 587)</option>
        <option value="false">Wyłączone (SSL port 465)</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Użytkownik SMTP</label>
      <input type="text" id="smtp-username" class="form-input" placeholder="noreply@example.com" autocomplete="off">
    </div>
    <div class="form-group">
      <label class="form-label">Hasło SMTP</label>
      <input type="password" id="smtp-password" class="form-input" placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;" autocomplete="new-password">
    </div>
    <div class="form-group">
      <label class="form-label">Adres nadawcy (From)</label>
      <input type="email" id="smtp-from-address" class="form-input" placeholder="noreply@aigm.app">
    </div>
    <div class="form-group">
      <label class="form-label">Nazwa nadawcy (From Name)</label>
      <input type="text" id="smtp-from-name" class="form-input" placeholder="AI-GM">
    </div>
  </div>

  <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">
    <button class="btn btn-primary" id="smtp-save-btn">Zapisz konfigurację SMTP</button>
    <div style="flex: 1; min-width: 200px; display: flex; gap: 8px; align-items: center;">
      <input type="email" id="smtp-test-email" class="form-input" placeholder="test@email.com" style="flex:1">
      <button class="btn btn-secondary" id="smtp-test-btn">&#128232; Wyślij test</button>
    </div>
  </div>
</div>

<div class="card" style="padding: 24px;">
  <h3 style="margin-bottom: 16px; color: var(--text-muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em;">Rejestracja</h3>
  <div style="display: flex; align-items: center; justify-content: space-between;">
    <div>
      <div style="font-size: 0.95rem; margin-bottom: 4px;">Otwarta rejestracja</div>
      <div style="font-size: 0.8rem; color: var(--text-muted)">Gdy włączona — gracze mogą rejestrować się bez zaproszenia</div>
    </div>
    <label class="toggle-switch">
      <input type="checkbox" id="reg-open-toggle">
      <span class="toggle-slider"></span>
    </label>
  </div>
  <div style="margin-top: 16px;">
    <button class="btn btn-secondary" id="reg-save-btn">Zapisz</button>
  </div>
</div>
`;
}

async function loadEmailConfig() {
    const { adminFetch } = await import('../shared/api.js');
    try {
        const cfg = await adminFetch('/api/admin/email/config');
        document.getElementById('smtp-host').value = cfg.smtp_host || '';
        document.getElementById('smtp-port').value = cfg.smtp_port || '587';
        document.getElementById('smtp-username').value = cfg.smtp_username || '';
        document.getElementById('smtp-from-address').value = cfg.smtp_from_address || '';
        document.getElementById('smtp-from-name').value = cfg.smtp_from_name || 'AI-GM';
        if (cfg.smtp_use_tls !== undefined) {
            document.getElementById('smtp-use-tls').value = cfg.smtp_use_tls === 'false' ? 'false' : 'true';
        }
        document.getElementById('reg-open-toggle').checked = cfg.registration_open === 'true' || cfg.registration_open === '1';
        // Don't pre-fill password (security)
    } catch (e) {
        console.error('Failed to load email config:', e);
    }
}

function bindEvents() {
    document.getElementById('smtp-save-btn').addEventListener('click', saveSmtpConfig);
    document.getElementById('smtp-test-btn').addEventListener('click', sendTestEmail);
    document.getElementById('reg-save-btn').addEventListener('click', saveRegistrationConfig);
}

async function saveSmtpConfig() {
    const { adminFetch } = await import('../shared/api.js');
    const { showToast } = await import('../shared/toast.js');
    const btn = document.getElementById('smtp-save-btn');
    btn.disabled = true;
    btn.textContent = 'Zapisywanie...';
    try {
        const passwordVal = document.getElementById('smtp-password').value;
        const payload = {
            smtp_host: document.getElementById('smtp-host').value.trim(),
            smtp_port: document.getElementById('smtp-port').value.trim(),
            smtp_username: document.getElementById('smtp-username').value.trim(),
            smtp_from_address: document.getElementById('smtp-from-address').value.trim(),
            smtp_from_name: document.getElementById('smtp-from-name').value.trim(),
            smtp_use_tls: document.getElementById('smtp-use-tls').value,
        };
        // Only send password if user typed something
        if (passwordVal) {
            payload.smtp_password = passwordVal;
        }
        await adminFetch('/api/admin/email/config', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        showToast('Konfiguracja SMTP zapisana', 'success');
    } catch (e) {
        showToast(e.message || 'Błąd zapisu', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Zapisz konfigurację SMTP';
    }
}

async function sendTestEmail() {
    const { adminFetch } = await import('../shared/api.js');
    const { showToast } = await import('../shared/toast.js');
    const to = document.getElementById('smtp-test-email').value.trim();
    if (!to) { showToast('Podaj adres email do testu', 'error'); return; }
    const btn = document.getElementById('smtp-test-btn');
    btn.disabled = true;
    btn.textContent = 'Wysyłanie...';
    try {
        await adminFetch('/api/admin/email/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ to }),
        });
        showToast(`Email testowy wysłany na ${to}`, 'success');
    } catch (e) {
        showToast(e.message || 'Błąd wysyłania — sprawdź konfigurację SMTP', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '&#128232; Wyślij test';
    }
}

async function saveRegistrationConfig() {
    const { adminFetch } = await import('../shared/api.js');
    const { showToast } = await import('../shared/toast.js');
    const open = document.getElementById('reg-open-toggle').checked;
    const btn = document.getElementById('reg-save-btn');
    btn.disabled = true;
    try {
        await adminFetch('/api/admin/email/config', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ registration_open: open ? 'true' : 'false' }),
        });
        showToast(`Rejestracja: ${open ? 'otwarta' : 'zamknięta'}`, 'success');
    } catch (e) {
        showToast(e.message || 'Błąd zapisu', 'error');
    } finally {
        btn.disabled = false;
    }
}
