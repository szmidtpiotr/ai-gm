// Multiplayer round UI — manages round submission, polling, and narration display.
// Activated when campaign.mode === 'multiplayer'.
// Uses the normal composer — injects a status bar, disables send when waiting.
// Exposes window.multiplayerUI = { activate, deactivate, isActive, handleSubmit, leave }

(function () {
    let _campaignId = null;
    let _characterId = null;
    let _characterName = null;
    let _pollTimer = null;
    let _active = false;
    let _lastShownRoundId = null;

    const POLL_WAITING_MS = 4000;
    const POLL_NARRATING_MS = 3000;

    function _input()     { return document.getElementById('chat-input'); }
    function _sendBtn()   { return document.getElementById('send-btn'); }
    function _statusBar() { return document.getElementById('mp-status-bar'); }
    function _noteEl()    { return document.getElementById('multiplayer-private-note'); }
    function _chat()      { return document.getElementById('chat-messages'); }

    function _token() {
        return localStorage.getItem('aigm_access_token') || localStorage.getItem('token') || '';
    }

    async function _apiFetch(path, opts = {}) {
        const resp = await fetch('/api' + path, {
            ...opts,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${_token()}`,
                ...(opts.headers || {}),
            },
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    }

    function _formatDeadline(deadline) {
        if (!deadline) return '';
        const diff = new Date(deadline) - Date.now();
        if (diff <= 0) return 'Runda zamknięta';
        const h = Math.floor(diff / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        return h > 0 ? `${h}h ${m}m` : `${m}m`;
    }

    function _updateStatusBar({ roundNumber, submitted, total, statusText, deadline } = {}) {
        const bar = _statusBar();
        if (!bar) return;
        const roundEl = bar.querySelector('.mp-bar-round');
        const countEl = bar.querySelector('.mp-bar-count');
        const timerEl = bar.querySelector('.mp-bar-timer');
        const stateEl = bar.querySelector('.mp-bar-state');
        if (roundEl && roundNumber) roundEl.textContent = `Runda ${roundNumber}`;
        if (countEl) countEl.textContent = total > 0 ? `${submitted}/${total}` : '';
        if (timerEl) timerEl.textContent = _formatDeadline(deadline);
        if (stateEl) stateEl.textContent = statusText || '';
    }

    function _setComposerState(enabled, placeholder) {
        const inp = _input();
        const btn = _sendBtn();
        if (inp) {
            if (inp.disabled !== !enabled) inp.disabled = !enabled;
            if (placeholder && inp.placeholder !== placeholder) inp.placeholder = placeholder;
        }
        if (btn) {
            if (btn.disabled !== !enabled) { btn.disabled = !enabled; btn.style.opacity = enabled ? '' : '0.3'; }
        }
    }

    function _injectStatusBar() {
        if (document.getElementById('mp-status-bar')) return;
        const composer = document.getElementById('composer');
        if (!composer) return;
        const bar = document.createElement('div');
        bar.id = 'mp-status-bar';
        bar.style.cssText = 'display:flex;align-items:center;gap:8px;padding:5px 12px 4px;font-size:12px;border-bottom:1px solid rgba(255,255,255,.07);background:rgba(124,77,255,.07)';
        bar.innerHTML = `
            <span class="mp-bar-round" style="font-weight:700;color:var(--accent,#7c4dff)">Runda 1</span>
            <span class="mp-bar-count" style="opacity:.65;background:rgba(255,255,255,.06);padding:1px 6px;border-radius:99px"></span>
            <span class="mp-bar-state" style="opacity:.65;flex:1"></span>
            <span class="mp-bar-timer" style="opacity:.5;font-size:11px"></span>
            <button style="font-size:11px;opacity:.45;background:none;border:none;cursor:pointer;color:inherit;padding:2px 6px;margin-left:4px" onclick="window.multiplayerUI.leave()">Opuść grę</button>
        `;
        composer.insertBefore(bar, composer.firstChild);
    }

    function _removeStatusBar() {
        _statusBar()?.remove();
    }

    function _appendNarration(narrative, myNote) {
        const chat = _chat();
        if (!chat) return;
        const bubble = document.createElement('div');
        bubble.className = 'message message--gm';
        bubble.style.cssText = 'border-left:3px solid var(--accent,#7c4dff);padding:12px 16px;margin:8px 0;white-space:pre-wrap;line-height:1.6';
        bubble.textContent = narrative;
        chat.appendChild(bubble);
        if (myNote) {
            const noteEl = _noteEl();
            if (noteEl) {
                noteEl.hidden = false;
                const body = noteEl.querySelector('.mp-note-body');
                if (body) body.textContent = myNote;
            }
        }
        chat.scrollTop = chat.scrollHeight;
    }

    function _hideNote() {
        const noteEl = _noteEl();
        if (!noteEl) return;
        noteEl.hidden = true;
        const body = noteEl.querySelector('.mp-note-body');
        if (body) body.textContent = '';
    }

    function _stopPolling() {
        if (_pollTimer) { clearTimeout(_pollTimer); _pollTimer = null; }
    }

    async function _poll() {
        if (!_active || !_campaignId) return;
        _stopPolling();
        try {
            const s = await _apiFetch(`/campaigns/${_campaignId}/round/status`);
            if (!_active) return;
            const base = { roundNumber: s.round_number, submitted: s.submitted_count, total: s.total_players, deadline: s.deadline };

            if (s.status === 'none' || (s.status === 'collecting' && !s.my_submitted)) {
                _setComposerState(true, 'Twoja akcja w tej rundzie...');
                _updateStatusBar({ ...base, statusText: s.submitted_count > 0 ? `${s.submitted_count} z ${s.total_players} oddało` : '' });
                _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
                return;
            }
            if (s.status === 'collecting' && s.my_submitted) {
                _setComposerState(false, `Czekasz na pozostałych... (${s.submitted_count}/${s.total_players})`);
                _updateStatusBar({ ...base, statusText: 'czekasz na pozostałych' });
                _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
                return;
            }
            if (s.status === 'narrating') {
                _setComposerState(false, 'GM tworzy narrację...');
                _updateStatusBar({ ...base, statusText: 'GM pisze...' });
                _pollTimer = setTimeout(_fetchNarration, POLL_NARRATING_MS);
                return;
            }
            if (s.status === 'done') {
                if (s.round_id === _lastShownRoundId) {
                    // Narration already shown; new round not yet created — keep enabled
                    _setComposerState(true, 'Twoja akcja w tej rundzie...');
                    _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
                } else {
                    _setComposerState(false, 'GM tworzy narrację...');
                    _updateStatusBar({ ...base, statusText: 'GM pisze...' });
                    await _fetchNarration();
                }
                return;
            }
        } catch (e) {
            console.warn('[MP] poll error:', e);
            _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
        }
    }

    async function _fetchNarration() {
        if (!_active || !_campaignId) return;
        try {
            const n = await _apiFetch(`/campaigns/${_campaignId}/round/narration`);
            if (!_active) return;
            if (n.round_id === _lastShownRoundId) {
                // Already displayed — wait for new round without toggling UI
                _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
                return;
            }
            _lastShownRoundId = n.round_id;
            _appendNarration(n.narrative || '', n.my_note || null);
            _updateStatusBar({ statusText: 'Przygotuj kolejną akcję...' });
            // Auto-unblock after 2s so player can read narration
            _pollTimer = setTimeout(_startNextRound, 2000);
        } catch (e) {
            if (e.message.includes('404')) {
                _pollTimer = setTimeout(_fetchNarration, POLL_NARRATING_MS);
            } else {
                console.warn('[MP] narration error:', e);
                _pollTimer = setTimeout(_fetchNarration, POLL_NARRATING_MS);
            }
        }
    }

    function _startNextRound() {
        if (!_active) return;
        _hideNote();
        _setComposerState(true, 'Twoja akcja w tej rundzie...');
        _poll();
    }

    async function handleSubmit() {
        const inp = _input();
        if (!inp || !_active) return;
        const text = inp.value.trim();
        if (!text) return;

        _setComposerState(false, 'Wysyłanie...');
        inp.value = '';

        try {
            const result = await _apiFetch(`/campaigns/${_campaignId}/round/submit`, {
                method: 'POST',
                body: JSON.stringify({
                    action_text: text,
                    character_id: _characterId,
                    character_name: _characterName,
                }),
            });

            if (result.status === 'narrating' || result.status === 'done') {
                _setComposerState(false, 'GM tworzy narrację...');
                _updateStatusBar({ statusText: 'GM pisze...' });
                _pollTimer = setTimeout(_fetchNarration, POLL_NARRATING_MS);
            } else {
                _setComposerState(false, `Czekasz na pozostałych... (${result.submitted}/${result.total})`);
                _updateStatusBar({ submitted: result.submitted, total: result.total, statusText: 'czekasz na pozostałych' });
                _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
            }
        } catch (e) {
            console.warn('[MP] submit error:', e);
            _setComposerState(true, 'Twoja akcja w tej rundzie...');
        }
    }

    function activate(campaignId, characterId, characterName) {
        _campaignId = campaignId;
        _characterId = characterId;
        _characterName = characterName;
        _active = true;
        _lastShownRoundId = null;

        _injectStatusBar();
        _hideNote();
        _poll();
    }

    function deactivate() {
        _active = false;
        _stopPolling();
        _campaignId = null;
        _characterId = null;
        _characterName = null;

        _removeStatusBar();
        _setComposerState(true, 'Co robisz? Możesz pisać swobodnie...');
        _hideNote();
    }

    function leave() {
        deactivate();
        if (typeof loadCampaigns === 'function') {
            loadCampaigns().then(() => { if (typeof showScreen === 'function') showScreen('campaigns'); });
        }
    }

    window.multiplayerUI = { activate, deactivate, isActive: () => _active, handleSubmit, leave };
})();

// ── Lobby UI (global functions called from HTML onclick) ─────────────────────

let _lobbyId = null;
let _lobbyPollTimer = null;
let _inviteLinkToken = null;

function _lobbyToken() {
    return localStorage.getItem('aigm_access_token') || localStorage.getItem('token') || '';
}

async function _lobbyFetch(path, opts = {}) {
    const resp = await fetch('/api' + path, {
        ...opts,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${_lobbyToken()}`,
            ...(opts.headers || {}),
        },
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || resp.statusText);
    }
    return resp.json();
}

async function createLobby() {
    const title = document.getElementById('lobby-title')?.value.trim();
    const timer = parseInt(document.getElementById('lobby-timer')?.value || '24');
    const maxPlayers = parseInt(document.getElementById('lobby-max-players')?.value || '4');
    const errEl = document.getElementById('create-lobby-error');
    if (!title) { if (errEl) { errEl.textContent = 'Podaj nazwę sesji'; errEl.style.display = 'block'; } return; }
    try {
        const data = await _lobbyFetch('/multiplayer/campaigns', {
            method: 'POST',
            body: JSON.stringify({ title, round_timer_hours: timer, max_players: maxPlayers }),
        });
        _lobbyId = data.campaign_id;
        await _showLobbyScreen(_lobbyId);
    } catch (e) {
        if (errEl) { errEl.textContent = 'Błąd: ' + e.message; errEl.style.display = 'block'; }
    }
}

async function _showLobbyScreen(campaignId) {
    _lobbyId = campaignId;
    localStorage.setItem('aigm_lobby_id', String(campaignId));
    if (typeof showScreen === 'function') showScreen('lobby-screen');
    await _refreshLobby();
    _startLobbyPoll();
}

function _clearLobbySession() {
    _lobbyId = null;
    localStorage.removeItem('aigm_lobby_id');
    _stopLobbyPoll();
}

async function tryRestoreLobbySession() {
    const saved = localStorage.getItem('aigm_lobby_id');
    if (!saved) return false;
    try {
        // Verify lobby still open and user is a member
        const data = await _lobbyFetch(`/multiplayer/campaigns/${saved}/lobby`);
        if (data.lobby_status !== 'open') { _clearLobbySession(); return false; }
        await _showLobbyScreen(Number(saved));
        return true;
    } catch (e) {
        _clearLobbySession();
        return false;
    }
}

async function _refreshLobby() {
    if (!_lobbyId) return;
    try {
        const data = await _lobbyFetch(`/multiplayer/campaigns/${_lobbyId}/lobby`);
        _renderLobby(data);
    } catch (e) {
        console.warn('[Lobby] refresh error:', e);
    }
}

function _renderLobby(data) {
    const titleEl = document.getElementById('lobby-screen-title');
    const subEl = document.getElementById('lobby-screen-subtitle');
    if (titleEl) titleEl.textContent = data.title;
    if (subEl) subEl.textContent = `${data.round_timer_hours}h/runda · max ${data.max_players} graczy`;

    const membersEl = document.getElementById('lobby-members-list');
    if (membersEl) {
        membersEl.innerHTML = data.members.map(m => {
            const badge = m.status === 'accepted' ? '✅' : m.status === 'pending' ? '⏳' : '❌';
            const kickBtn = data.is_host && m.role !== 'owner'
                ? `<button onclick="kickPlayer(${m.user_id})" style="font-size:11px;opacity:.6;background:none;border:none;cursor:pointer;color:var(--t3)">✕</button>`
                : '';
            return `<div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border,.1)">
                <span style="font-size:18px">${badge}</span>
                <span style="flex:1">${m.display_name}<span style="opacity:.5;font-size:12px"> @${m.username}</span></span>
                <span style="font-size:11px;opacity:.5">${m.role === 'owner' ? 'Host' : ''}</span>
                ${kickBtn}
            </div>`;
        }).join('');
    }

    const inviteSection = document.getElementById('lobby-invite-section');
    const guestSection = document.getElementById('lobby-guest-section');
    const startSection = document.getElementById('lobby-start-section');
    const joinSection = document.getElementById('lobby-join-link-section');

    if (inviteSection) inviteSection.style.display = data.is_host ? 'block' : 'none';
    if (guestSection) guestSection.style.display = data.is_host ? 'none' : 'block';
    if (startSection) startSection.style.display = data.is_host ? 'block' : 'none';
    if (joinSection) joinSection.style.display = data.is_host ? 'none' : 'none'; // hidden for now

    if (data.is_host) {
        const startBtn = document.getElementById('lobby-start-btn');
        const hint = document.getElementById('lobby-start-hint');
        const canStart = data.accepted_count >= 2;
        if (startBtn) startBtn.disabled = !canStart;
        if (hint) hint.textContent = canStart ? `${data.accepted_count} graczy gotowych` : `Potrzeba min. 2 graczy (${data.accepted_count}/${data.max_players})`;
    }

    if (data.lobby_status === 'started') {
        _clearLobbySession();
        if (typeof enterMpGame === 'function') {
            enterMpGame(data.campaign_id);
        } else if (typeof loadCampaigns === 'function') {
            loadCampaigns().then(() => { if (typeof showScreen === 'function') showScreen('campaigns'); });
        }
    }
}

function _startLobbyPoll() {
    _stopLobbyPoll();
    _lobbyPollTimer = setInterval(_refreshLobby, 5000);
}

function _stopLobbyPoll() {
    if (_lobbyPollTimer) { clearInterval(_lobbyPollTimer); _lobbyPollTimer = null; }
}

async function inviteByUsername() {
    const input = document.getElementById('lobby-invite-username');
    const msgEl = document.getElementById('lobby-invite-msg');
    const username = input?.value.trim();
    if (!username || !_lobbyId) return;
    try {
        await _lobbyFetch(`/multiplayer/campaigns/${_lobbyId}/invite/username`, {
            method: 'POST',
            body: JSON.stringify({ username }),
        });
        if (msgEl) { msgEl.textContent = `✅ Zaproszono @${username}`; msgEl.style.color = 'var(--green,#4caf50)'; }
        if (input) input.value = '';
        await _refreshLobby();
    } catch (e) {
        if (msgEl) { msgEl.textContent = '❌ ' + e.message; msgEl.style.color = 'var(--red,#e53935)'; }
    }
}

async function generateInviteLink() {
    if (!_lobbyId) return;
    const boxEl = document.getElementById('lobby-invite-link-box');
    const textEl = document.getElementById('lobby-invite-link-text');
    const msgEl = document.getElementById('lobby-invite-msg');
    try {
        const data = await _lobbyFetch(`/multiplayer/campaigns/${_lobbyId}/invite-link`, { method: 'POST' });
        _inviteLinkToken = data.token;
        const url = `${location.origin}/?join=${data.token}`;
        if (textEl) textEl.textContent = url;
        if (boxEl) boxEl.style.display = 'block';
        if (msgEl) { msgEl.textContent = `Ważny do: ${new Date(data.expires_at).toLocaleDateString('pl-PL')}`; msgEl.style.color = ''; }
    } catch (e) {
        if (msgEl) { msgEl.textContent = '❌ ' + e.message; msgEl.style.color = 'var(--red,#e53935)'; }
    }
}

function copyInviteLink() {
    const textEl = document.getElementById('lobby-invite-link-text');
    if (textEl?.textContent) navigator.clipboard?.writeText(textEl.textContent).catch(() => {});
}

async function startLobby() {
    if (!_lobbyId) return;
    const id = _lobbyId;
    try {
        await _lobbyFetch(`/multiplayer/campaigns/${id}/start`, { method: 'POST' });
        _clearLobbySession();
        if (typeof enterMpGame === 'function') {
            await enterMpGame(id);
        } else if (typeof loadCampaigns === 'function') {
            await loadCampaigns();
            if (typeof showScreen === 'function') showScreen('campaigns');
        }
    } catch (e) {
        const hint = document.getElementById('lobby-start-hint');
        if (hint) { hint.textContent = '❌ ' + e.message; hint.style.color = 'var(--red,#e53935)'; }
    }
}

async function kickPlayer(targetUserId) {
    if (!_lobbyId) return;
    try {
        await _lobbyFetch(`/multiplayer/campaigns/${_lobbyId}/players/${targetUserId}`, { method: 'DELETE' });
        await _refreshLobby();
    } catch (e) {
        console.warn('[Lobby] kick error:', e);
    }
}

async function joinViaToken() {
    const input = document.getElementById('lobby-join-token-input');
    const msgEl = document.getElementById('lobby-join-msg');
    const token = input?.value.trim();
    if (!token) return;
    try {
        const data = await _lobbyFetch(`/multiplayer/join/${token}`);
        _lobbyId = data.campaign_id;
        if (msgEl) { msgEl.textContent = `✅ Dołączyłeś do "${data.title}"`; msgEl.style.color = 'var(--green,#4caf50)'; }
        await _showLobbyScreen(data.campaign_id);
    } catch (e) {
        if (msgEl) { msgEl.textContent = '❌ ' + e.message; msgEl.style.color = 'var(--red,#e53935)'; }
    }
}

async function leaveMpLobbyFromScreen() {
    if (!_lobbyId) return;
    const id = _lobbyId;
    try {
        await _lobbyFetch(`/multiplayer/campaigns/${id}/decline`, { method: 'POST' });
        _clearLobbySession();
        if (typeof loadCampaigns === 'function') await loadCampaigns();
        if (typeof showScreen === 'function') showScreen('campaigns');
    } catch (e) {
        console.warn('[Lobby] leave error:', e);
    }
}

// Handle ?join=TOKEN in URL on page load
(function _checkJoinParam() {
    const params = new URLSearchParams(location.search);
    const token = params.get('join');
    if (!token) return;
    // Remove param from URL without reload
    history.replaceState(null, '', location.pathname);
    // Wait for auth before processing
    window._pendingJoinToken = token;
})();
