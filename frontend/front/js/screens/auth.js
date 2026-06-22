// ============================================================================
// Authentication
// ============================================================================
async function handleLogin(e) {
    e.preventDefault();
    console.log('[Login] Starting login...');

    const username = elements.usernameInput.value.trim();
    const password = elements.passwordInput.value;

    if (!username || !password) {
        showToast('Wprowadź login i hasło', 'error');
        return;
    }

    const submitBtn = elements.loginForm.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="btn__icon">⏳</span> Logowanie...';

    try {
        console.log('[Login] Calling API...');
        const response = await apiRequest('POST', '/auth/login', { username, password });
        console.log('[Login] Response:', response);

        if (response.ok || response.user_id) {
            currentUser = {
                id: response.user_id,
                username: response.username || username,
                display_name: response.display_name,
                is_admin: response.is_admin,
                is_tester: response.is_tester || 0,
                role: response.role || (response.is_admin ? 'admin' : 'player'),
            };
            // Stage 10 A2 — store JWT pair when present (backend now emits them).
            // Backward compat: legacy `token` key keeps the sentinel for old code paths.
            if (response.access_token) {
                localStorage.setItem('aigm_access_token', response.access_token);
            }
            if (response.refresh_token) {
                localStorage.setItem('aigm_refresh_token', response.refresh_token);
            }
            authToken = response.access_token || `user:${currentUser.id}`;
            localStorage.setItem('token', authToken);
            localStorage.setItem('user', JSON.stringify(currentUser));
            window.clog?.setContext({ user_id: currentUser.id, username: currentUser.username });
            window.clog?.event('login_success', { user_id: currentUser.id });

            console.log('[Login] Success, loading heroes...');
            const displayName = currentUser.display_name || currentUser.username;
            if (elements.heroesWelcome) elements.heroesWelcome.textContent = `Witaj, ${displayName}`;
            if (elements.welcomeUser) elements.welcomeUser.textContent = `Witaj, ${displayName}`;
            updateAdminSettingsVisibility();
            try {
                await loadHeroes();
                if (await tryRestoreSession()) return;
            } catch (e) {
                console.error('[Login] loadHeroes failed:', e);
            }
            if (response.game_mode_flags) {
                try {
                    const flags = typeof response.game_mode_flags === 'string'
                        ? JSON.parse(response.game_mode_flags) : response.game_mode_flags;
                    if (flags?.visual_theme) _applyTheme(flags.visual_theme);
                } catch (_) {}
            }
            if (await consumePendingJoin()) return;
            if (!response.onboarded_at) {
                showOnboardingCinematic();
            } else {
                showScreen('heroes');
            }
        } else {
            console.error('[Login] Invalid response:', response);
            showToast('Nieprawidłowa odpowiedź serwera', 'error');
        }
    } catch (error) {
        console.error('[Login] Error:', error);
        if (error.status === 403 && error.body?.detail?.error === 'email_unverified') {
            _canResendVerify = false;
            document.getElementById('verify-email-desc').textContent =
                'Potwierdź swój adres email, aby kontynuować przygodę.';
            document.getElementById('resend-verify-btn').hidden = true;
            showScreen('verifyEmail');
        } else {
            showToast(error.message || 'Błąd logowania', 'error');
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span class="btn__icon">✨</span> Zaloguj się';
    }
}

function handleLogout() {
    authToken = null;
    currentUser = null;
    currentHero = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    // Stage 10 A2 — clear JWT pair on logout.
    localStorage.removeItem('aigm_access_token');
    localStorage.removeItem('aigm_refresh_token');
    localStorage.removeItem('aigm_hero_id');
    localStorage.removeItem('aigm_campaign_id');
    try { sessionStorage.removeItem('aigm_hero_id'); sessionStorage.removeItem('aigm_active_session'); } catch {}
    // D10 E2 — reset theme on logout so next user gets theirs
    _selectedTheme = 'dark_fantasy';
    document.body.dataset.theme = '';
    showScreen('login');
}

function handleSessionExpired() {
    showToast('Sesja wygasła — zaloguj się ponownie.', 'error', 5000);
    // Clear auth credentials but KEEP aigm_hero_id / aigm_campaign_id so
    // tryRestoreSession() can resume the game after re-login.
    authToken = null;
    currentUser = null;
    currentHero = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('aigm_access_token');
    localStorage.removeItem('aigm_refresh_token');
    _selectedTheme = 'dark_fantasy';
    document.body.dataset.theme = '';
    showScreen('login');
}

// ── Registration ──────────────────────────────────────────────────────────
async function loadInviteInfo(code) {
    try {
        const resp = await apiRequest('GET', `/auth/invite/${code}`);
        if (resp.inviter_name) {
            document.getElementById('register-inviter-avatar').textContent =
                resp.inviter_name.charAt(0).toUpperCase();
            document.getElementById('register-inviter-name').textContent = resp.inviter_name;
            document.getElementById('register-inviter-card').hidden = false;
            if (resp.message) {
                const msgEl = document.getElementById('register-inviter-msg');
                msgEl.textContent = `"${resp.message}"`;
                msgEl.hidden = false;
            }
        }
        if (resp.email) {
            const emailInput = document.getElementById('register-email');
            emailInput.value = resp.email;
            emailInput.readOnly = true;
            emailInput.style.opacity = '0.65';
        }
        if (resp.expires_at) {
            const expiry = new Date(resp.expires_at);
            const hours = Math.round((expiry - Date.now()) / 3_600_000);
            if (hours > 0) {
                document.getElementById('register-expiry').textContent =
                    `Zaproszenie ważne jeszcze ${hours} ${hours === 1 ? 'godzinę' : 'godzin'}`;
            }
        }
    } catch (e) {
        showToast('Nieprawidłowe lub wygasłe zaproszenie', 'error');
        showScreen('login');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const email    = document.getElementById('register-email').value.trim();
    const username = document.getElementById('register-username').value.trim();
    const password = document.getElementById('register-password').value;
    const confirm  = document.getElementById('register-password-confirm')?.value ?? '';
    const errEl    = document.getElementById('register-error');
    errEl.hidden   = true;

    if (!email || !username || !password || !confirm) {
        errEl.textContent = 'Wypełnij wszystkie pola';
        errEl.hidden = false;
        return;
    }
    if (password !== confirm) {
        errEl.textContent = 'Hasła nie są zgodne';
        errEl.hidden = false;
        return;
    }
    if (password.length < 8) {
        errEl.textContent = 'Hasło musi mieć minimum 8 znaków';
        errEl.hidden = false;
        return;
    }

    const btn = document.querySelector('#register-form button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn__icon">⏳</span> Tworzenie konta...';

    try {
        const resp = await apiRequest('POST', '/auth/register', {
            username, email, password, invite_code: _inviteCode
        });
        if (resp.access_token) {
            localStorage.setItem('aigm_access_token', resp.access_token);
            if (resp.refresh_token) localStorage.setItem('aigm_refresh_token', resp.refresh_token);
            authToken = resp.access_token;
            localStorage.setItem('token', authToken);
            currentUser = { id: resp.user_id, username, is_admin: false, role: 'player' };
            localStorage.setItem('user', JSON.stringify(currentUser));
        }
        _verifyEmailAddress = email;
        _canResendVerify = !!resp.access_token;
        document.getElementById('verify-email-desc').textContent =
            `Wysłaliśmy link aktywacyjny na ${email}`;
        document.getElementById('resend-verify-btn').hidden = !_canResendVerify;
        showScreen('verifyEmail');
    } catch (e) {
        errEl.textContent = e.message || 'Błąd rejestracji';
        errEl.hidden = false;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn__icon">⚔</span> Dołącz do przygody';
    }
}

// ── Email verification ────────────────────────────────────────────────────
async function autoVerifyEmail(token) {
    try {
        const resp = await apiRequest('POST', '/auth/verify-email', { token });
        if (resp.access_token) {
            localStorage.setItem('aigm_access_token', resp.access_token);
            if (resp.refresh_token) localStorage.setItem('aigm_refresh_token', resp.refresh_token);
            authToken = resp.access_token;
            localStorage.setItem('token', authToken);
            currentUser = {
                id: resp.user_id, username: resp.username,
                display_name: resp.display_name,
                is_admin: resp.is_admin || false,
                is_tester: resp.is_tester || 0,
                role: resp.role || 'player'
            };
            localStorage.setItem('user', JSON.stringify(currentUser));
            updateAdminSettingsVisibility();
        }
        showToast('Email potwierdzony! Witaj w AI-GM.', 'success');
        await loadHeroes();
        if (await consumePendingJoin()) return;
        if (!resp.onboarded_at) {
            showOnboardingCinematic();
        } else {
            showScreen('heroes');
        }
    } catch (e) {
        showToast('Link weryfikacyjny jest nieprawidłowy lub wygasł', 'error');
        showScreen('login');
    }
    history.replaceState({}, '', window.location.pathname);
}

async function handleResendVerification() {
    if (_resendCountdownInterval) return;
    const btn         = document.getElementById('resend-verify-btn');
    const countdownEl = document.getElementById('resend-countdown');
    try {
        await apiRequest('POST', '/auth/resend-verification');
        showToast('Link weryfikacyjny wysłany ponownie', 'info');
        let secs = 120;
        btn.disabled = true;
        countdownEl.hidden = false;
        countdownEl.textContent = `Możesz wysłać ponownie za ${secs}s`;
        _resendCountdownInterval = setInterval(() => {
            secs--;
            countdownEl.textContent = `Możesz wysłać ponownie za ${secs}s`;
            if (secs <= 0) {
                clearInterval(_resendCountdownInterval);
                _resendCountdownInterval = null;
                btn.disabled = false;
                countdownEl.hidden = true;
            }
        }, 1000);
    } catch (e) {
        const wait = e.body?.detail?.retry_after_seconds;
        if (wait) {
            showToast(`Odczekaj jeszcze ${wait}s przed ponownym wysłaniem`, 'warning');
        } else {
            showToast(e.message || 'Błąd wysyłania', 'error');
        }
    }
}

// ── Forgot / reset password ───────────────────────────────────────────────
async function handleForgotPassword(e) {
    e.preventDefault();
    const email     = document.getElementById('forgot-email').value.trim();
    const successEl = document.getElementById('forgot-success');
    const btn       = document.getElementById('forgot-submit-btn');
    if (!email) { showToast('Podaj adres email', 'error'); return; }

    btn.disabled = true;
    btn.innerHTML = '<span class="btn__icon">⏳</span> Wysyłanie...';
    successEl.hidden = true;

    try {
        await apiRequest('POST', '/auth/forgot-password', { email });
    } catch (_) { /* always show success */ }

    successEl.hidden = false;
    btn.hidden = true;
    btn.disabled = false;
    btn.innerHTML = '<span class="btn__icon">📨</span> Wyślij link';
}

async function handleResetPassword(e) {
    e.preventDefault();
    const password = document.getElementById('reset-password').value;
    const confirm  = document.getElementById('reset-password-confirm').value;
    const errEl    = document.getElementById('reset-error');
    errEl.hidden   = true;

    if (!password || password.length < 8) {
        errEl.textContent = 'Hasło musi mieć minimum 8 znaków';
        errEl.hidden = false;
        return;
    }
    if (password !== confirm) {
        errEl.textContent = 'Hasła nie są identyczne';
        errEl.hidden = false;
        return;
    }

    const btn = document.querySelector('#reset-form button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn__icon">⏳</span> Zapisywanie...';

    try {
        const resp = await apiRequest('POST', '/auth/reset-password', {
            token: _resetToken, new_password: password
        });
        if (resp.access_token) {
            localStorage.setItem('aigm_access_token', resp.access_token);
            if (resp.refresh_token) localStorage.setItem('aigm_refresh_token', resp.refresh_token);
            authToken = resp.access_token;
            localStorage.setItem('token', authToken);
            currentUser = {
                id: resp.user_id, username: resp.username,
                display_name: resp.display_name,
                is_admin: resp.is_admin || false,
                is_tester: resp.is_tester || 0,
                role: resp.role || 'player'
            };
            localStorage.setItem('user', JSON.stringify(currentUser));
            updateAdminSettingsVisibility();
        }
        showToast('Hasło zmienione! Witaj ponownie.', 'success');
        await loadHeroes();
        showScreen('heroes');
        history.replaceState({}, '', window.location.pathname);
    } catch (e) {
        errEl.textContent = e.message || 'Link wygasł lub jest nieprawidłowy';
        errEl.hidden = false;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn__icon">✓</span> Ustaw nowe hasło';
    }
}

// ── URL-based routing (invite / verify / reset links from emails) ─────────
function checkUrlRouting() {
    const path   = window.location.pathname;
    const params = new URLSearchParams(window.location.search);

    if (path === '/verify-email') {
        const token = params.get('token');
        if (token) { autoVerifyEmail(token); return true; }
    }
    if (path === '/reset-password') {
        const token = params.get('token');
        if (token) { _resetToken = token; showScreen('resetPassword'); return true; }
    }
    if (path === '/register' || params.get('invite')) {
        const code = params.get('invite');
        if (code) {
            _inviteCode = code;
            showScreen('register');
            loadInviteInfo(code);
            return true;
        }
    }
    const joinToken = params.get('join');
    if (joinToken) {
        localStorage.setItem('pendingJoinToken', joinToken);
        history.replaceState({}, '', window.location.pathname);
        if (!localStorage.getItem('token')) {
            const notice = document.getElementById('register-mp-join-notice');
            if (notice) notice.hidden = false;
            showScreen('register');
            return true;
        }
        // logged in — fall through; init() will call consumePendingJoin()
        return false;
    }
    return false;
}

async function consumePendingJoin() {
    const token = localStorage.getItem('pendingJoinToken');
    if (!token) return false;
    localStorage.removeItem('pendingJoinToken');
    try {
        const resp = await apiRequest('GET', `/multiplayer/join/${token}`);
        showToast(`Dołączyłeś do kampanii: ${resp.title || ''}`, 'success');
        await loadCampaigns();
        showScreen('campaigns');
        return true;
    } catch (e) {
        const status = e?.status || 0;
        if (status === 410) showToast('Link zaproszenia wygasł lub został już użyty', 'warning');
        else if (status === 400) showToast('Lobby jest pełne lub już wystartowało', 'warning');
        else if (status === 404) showToast('Link zaproszenia jest nieprawidłowy', 'error');
        else showToast('Nie udało się dołączyć do kampanii', 'error');
        return false;
    }
}

function checkAuth() {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');

    if (token && user) {
        authToken = token;
        currentUser = JSON.parse(user);
        elements.welcomeUser.textContent = `Witaj, ${currentUser.username || ''}`;
        return true;
    }
    return false;
}

