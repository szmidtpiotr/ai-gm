// Multiplayer round UI — manages round submission, polling, and narration display.
// Activated when campaign.mode === 'multiplayer'.
// Exposes window.multiplayerUI = { activate, deactivate }

(function () {
    let _campaignId = null;
    let _characterId = null;
    let _characterName = null;
    let _pollTimer = null;
    let _active = false;

    const POLL_WAITING_MS = 4000;
    const POLL_NARRATING_MS = 3000;

    function _composer() { return document.getElementById('multiplayer-composer'); }
    function _normalComposer() { return document.getElementById('composer'); }
    function _combatComposer() { return document.getElementById('combat-composer'); }
    function _statusEl() { return document.getElementById('mp-status'); }
    function _actionInput() { return document.getElementById('mp-action-input'); }
    function _submitBtn() { return document.getElementById('mp-submit-btn'); }
    function _counterEl() { return document.getElementById('mp-counter'); }
    function _privateNoteEl() { return document.getElementById('multiplayer-private-note'); }
    function _chatMessages() { return document.getElementById('chat-messages'); }

    function _token() {
        return localStorage.getItem('aigm_access_token') || localStorage.getItem('token') || '';
    }

    async function _apiFetch(path, opts = {}) {
        const token = _token();
        const resp = await fetch('/api' + path, {
            ...opts,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token ? `Bearer ${token}` : '',
                ...(opts.headers || {}),
            },
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    }

    function _setState(state, data = {}) {
        const statusEl = _statusEl();
        const actionInput = _actionInput();
        const submitBtn = _submitBtn();
        const counterEl = _counterEl();
        if (!statusEl) return;

        const { submitted = 0, total = 0 } = data;

        if (state === 'submit') {
            statusEl.textContent = 'Wyślij swoją akcję na tę rundę:';
            if (actionInput) { actionInput.hidden = false; actionInput.disabled = false; actionInput.value = ''; }
            if (submitBtn) { submitBtn.hidden = false; submitBtn.disabled = false; }
            if (counterEl) counterEl.textContent = total > 0 ? `${submitted}/${total} graczy` : '';
        } else if (state === 'waiting') {
            statusEl.textContent = `Czekasz na pozostałych graczy... ⏳`;
            if (actionInput) actionInput.disabled = true;
            if (submitBtn) submitBtn.disabled = true;
            if (counterEl) counterEl.textContent = total > 0 ? `${submitted}/${total} wysłało` : '';
        } else if (state === 'narrating') {
            statusEl.textContent = 'GM tworzy narrację... 🖊️';
            if (actionInput) { actionInput.disabled = true; actionInput.hidden = true; }
            if (submitBtn) submitBtn.hidden = true;
            if (counterEl) counterEl.textContent = '';
        } else if (state === 'done') {
            statusEl.textContent = '';
            if (actionInput) { actionInput.hidden = true; }
            if (submitBtn) { submitBtn.hidden = true; }
            if (counterEl) counterEl.textContent = '';
            _showNextRoundBtn();
        }
    }

    function _showNextRoundBtn() {
        const composer = _composer();
        if (!composer) return;
        let btn = composer.querySelector('.mp-next-round-btn');
        if (!btn) {
            btn = document.createElement('button');
            btn.className = 'mp-next-round-btn composer__send';
            btn.style.cssText = 'width:100%;margin:8px 0;padding:10px;font-size:15px';
            btn.textContent = '▶ Następna runda';
            btn.addEventListener('click', _startNextRound);
            composer.appendChild(btn);
        }
        btn.hidden = false;
    }

    async function _startNextRound() {
        const btn = _composer()?.querySelector('.mp-next-round-btn');
        if (btn) btn.hidden = true;
        _hidePrivateNote();
        _setState('submit');
        await _poll();
    }

    function _appendNarration(narrative, myNote) {
        const chat = _chatMessages();
        if (!chat) return;

        const bubble = document.createElement('div');
        bubble.className = 'message message--gm';
        bubble.style.cssText = 'border-left: 3px solid var(--accent,#7c4dff); padding: 12px 16px; margin: 8px 0; white-space: pre-wrap; line-height: 1.6;';
        bubble.textContent = narrative;
        chat.appendChild(bubble);

        if (myNote) {
            const noteEl = _privateNoteEl();
            if (noteEl) {
                noteEl.hidden = false;
                noteEl.querySelector('.mp-note-body').textContent = myNote;
            }
        }

        chat.scrollTop = chat.scrollHeight;
    }

    function _hidePrivateNote() {
        const noteEl = _privateNoteEl();
        if (noteEl) {
            noteEl.hidden = true;
            const body = noteEl.querySelector('.mp-note-body');
            if (body) body.textContent = '';
        }
    }

    function _stopPolling() {
        if (_pollTimer) { clearTimeout(_pollTimer); _pollTimer = null; }
    }

    async function _poll() {
        if (!_active || !_campaignId) return;
        _stopPolling();

        try {
            const status = await _apiFetch(`/campaigns/${_campaignId}/round/status`);
            if (!_active) return;

            if (status.status === 'none') {
                _setState('submit', { submitted: 0, total: status.total_players });
                _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
                return;
            }

            if (status.status === 'collecting') {
                if (status.my_submitted) {
                    _setState('waiting', { submitted: status.submitted_count, total: status.total_players });
                    _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
                } else {
                    _setState('submit', { submitted: status.submitted_count, total: status.total_players });
                }
                return;
            }

            if (status.status === 'narrating') {
                _setState('narrating');
                _pollTimer = setTimeout(_fetchNarration, POLL_NARRATING_MS);
                return;
            }

            if (status.status === 'done') {
                await _fetchNarration();
                return;
            }
        } catch (e) {
            console.warn('[Multiplayer] poll error:', e);
            _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
        }
    }

    async function _fetchNarration() {
        if (!_active || !_campaignId) return;
        try {
            const narration = await _apiFetch(`/campaigns/${_campaignId}/round/narration`);
            if (!_active) return;
            _appendNarration(narration.narrative || '', narration.my_note || null);
            _setState('done');
        } catch (e) {
            if (e.message.includes('404')) {
                // Not ready yet — keep polling
                _pollTimer = setTimeout(_fetchNarration, POLL_NARRATING_MS);
            } else {
                console.warn('[Multiplayer] narration fetch error:', e);
                _pollTimer = setTimeout(_fetchNarration, POLL_NARRATING_MS);
            }
        }
    }

    async function _handleSubmit() {
        const input = _actionInput();
        if (!input) return;
        const text = input.value.trim();
        if (!text) return;

        const submitBtn = _submitBtn();
        if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = '⏳'; }

        try {
            const result = await _apiFetch(`/campaigns/${_campaignId}/round/submit`, {
                method: 'POST',
                body: JSON.stringify({
                    action_text: text,
                    character_id: _characterId,
                    character_name: _characterName,
                }),
            });
            _setState('waiting', { submitted: result.submitted, total: result.total });

            if (result.status === 'narrating' || result.status === 'done') {
                _setState('narrating');
                _pollTimer = setTimeout(_fetchNarration, POLL_NARRATING_MS);
            } else {
                _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
            }
        } catch (e) {
            console.warn('[Multiplayer] submit error:', e);
            if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Wyślij akcję'; }
        }
    }

    function activate(campaignId, characterId, characterName) {
        _campaignId = campaignId;
        _characterId = characterId;
        _characterName = characterName;
        _active = true;

        const normal = _normalComposer();
        const combat = _combatComposer();
        if (normal) normal.hidden = true;
        if (combat) combat.hidden = true;

        const mp = _composer();
        if (mp) {
            mp.hidden = false;
            const existingBtn = mp.querySelector('.mp-next-round-btn');
            if (existingBtn) existingBtn.hidden = true;
        }

        const submitBtn = _submitBtn();
        if (submitBtn) {
            submitBtn.removeEventListener('click', _handleSubmit);
            submitBtn.addEventListener('click', _handleSubmit);
        }

        const input = _actionInput();
        if (input) {
            input.removeEventListener('keydown', _onInputKeydown);
            input.addEventListener('keydown', _onInputKeydown);
        }

        _hidePrivateNote();
        _poll();
    }

    function _onInputKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            _handleSubmit();
        }
    }

    function deactivate() {
        _active = false;
        _stopPolling();
        _campaignId = null;

        const mp = _composer();
        if (mp) mp.hidden = true;

        const normal = _normalComposer();
        if (normal) normal.hidden = false;

        _hidePrivateNote();
    }

    window.multiplayerUI = { activate, deactivate };
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
        if (typeof loadCampaigns === 'function') {
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
    try {
        await _lobbyFetch(`/multiplayer/campaigns/${_lobbyId}/start`, { method: 'POST' });
        _clearLobbySession();
        if (typeof loadCampaigns === 'function') {
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
