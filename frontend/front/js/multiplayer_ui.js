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
