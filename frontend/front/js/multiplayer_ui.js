// Multiplayer round UI — manages round submission, polling, and narration display.
// Activated when campaign.mode === 'multiplayer'.
// Uses the normal composer — injects a status bar, disables send when waiting.
// GF6 (#926): supports spectator mode (isSpectator=true) — read-only, no action submission.
// Exposes window.multiplayerUI = { activate, deactivate, isActive, handleSubmit, leave, isSpectator }

(function () {
    let _campaignId = null;
    let _characterId = null;
    let _characterName = null;
    let _pollTimer = null;
    let _active = false;
    let _lastShownRoundId = null;
    let _sendEnabled = true;
    let _currentActionBubble = null;
    let _isHost = false;
    let _isSpectator = false;
    let _campaignTimerMinutes = 1440;
    let _currentDeadline = null;
    let _countdownInterval = null;
    let _currentRoundNumber = null;

    // ── Party Chat ──────────────────────────────────────────────────────
    let _chatLastId = 0;
    let _chatOpen = false;
    let _chatUnread = 0;
    let _chatPollTimer = null;
    let _minimized = false;
    let _sessionPlayers = new Set(); // character names seen in this session (excludes self)

    const POLL_WAITING_MS = 2000;
    const POLL_NARRATING_MS = 2000;

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
        const countEl = bar.querySelector('.mp-bar-count');
        const stateEl = bar.querySelector('.mp-bar-state');
        if (countEl) countEl.textContent = total > 0 ? `${submitted}/${total}` : '';
        if (deadline !== undefined) _startCountdown(deadline);
        if (stateEl) stateEl.textContent = statusText || '';
    }

    function _tickCountdown() {
        const el = _statusBar()?.querySelector('.mp-bar-timer');
        if (!el || !_currentDeadline) return;
        const diff = new Date(_currentDeadline) - Date.now();
        if (diff <= 0) { el.textContent = 'Koniec'; return; }
        const h = Math.floor(diff / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const s = Math.floor((diff % 60000) / 1000);
        const pad = n => String(n).padStart(2, '0');
        el.textContent = h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
    }

    function _startCountdown(deadline) {
        _stopCountdown();
        _currentDeadline = deadline || null;
        const el = _statusBar()?.querySelector('.mp-bar-timer');
        if (!_currentDeadline) { if (el) el.textContent = '—:—:—'; return; }
        _tickCountdown();
        _countdownInterval = setInterval(_tickCountdown, 1000);
    }

    function _stopCountdown() {
        if (_countdownInterval) { clearInterval(_countdownInterval); _countdownInterval = null; }
    }

    function _appendRoundDivider(roundNumber) {
        const chat = _chat();
        if (!chat) return;
        const div = document.createElement('div');
        div.className = 'mp-round-divider';
        div.innerHTML = `<div class="mp-round-divider__pill">Runda ${roundNumber}</div>`;
        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
    }

    function _setComposerState(enabled, placeholder) {
        _sendEnabled = enabled;
        const inp = _input();
        if (inp) {
            if (placeholder && inp.placeholder !== placeholder) inp.placeholder = placeholder;
            // #1173: disable the input element too — Enter bypasses the disabled send
            // button and would resubmit the round mid-narration. Spectators keep the
            // input live so they can still type /whisper party-chat commands.
            inp.disabled = !enabled && !_isSpectator;
        }
        _syncSendBtn();
    }

    function _syncSendBtn() {
        const btn = _sendBtn();
        const inp = _input();
        if (!btn) return;
        const isSlash = (inp?.value || '').startsWith('/');
        const shouldEnable = _sendEnabled || isSlash;
        if (btn.disabled !== !shouldEnable) { btn.disabled = !shouldEnable; btn.style.opacity = shouldEnable ? '' : '0.3'; }
    }

    function _onInputEvent() { _syncSendBtn(); }

    function _injectStatusBar(spectator = false) {
        if (document.getElementById('mp-status-bar')) return;
        const composer = document.getElementById('composer');
        if (!composer) return;
        const bar = document.createElement('div');
        bar.id = 'mp-status-bar';
        const bgColor = spectator ? 'rgba(100,100,255,.07)' : 'rgba(124,77,255,.07)';
        bar.style.cssText = `display:flex;align-items:center;gap:8px;padding:5px 12px 4px;font-size:12px;border-bottom:1px solid rgba(255,255,255,.07);background:${bgColor}`;
        if (spectator) {
            bar.innerHTML = `
                <span style="font-weight:700;font-size:13px;font-family:'Cinzel',serif;color:#9b9bff;letter-spacing:.05em">👁 WIDZ</span>
                <span class="mp-bar-state" style="opacity:.65;flex:1;font-size:11px">Tryb obserwatora — tylko odczyt</span>
            `;
        } else {
            bar.innerHTML = `
                <span class="mp-bar-timer" style="font-weight:700;font-size:15px;font-family:'Cinzel',serif;color:var(--accent,#c9a54a);min-width:60px;letter-spacing:.02em">—:—:—</span>
                <span class="mp-bar-count" style="opacity:.65;background:rgba(255,255,255,.06);padding:1px 6px;border-radius:99px;font-size:11px"></span>
                <span class="mp-bar-state" style="opacity:.65;flex:1;font-size:11px"></span>
            `;
        }
        composer.insertBefore(bar, composer.firstChild);
    }

    function _removeStatusBar() {
        _statusBar()?.remove();
    }

    function _safe(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function _chatMessages() { return document.getElementById('mp-chat-messages'); }
    function _chatBadge() { return document.getElementById('mp-chat-badge'); }
    function _chatNavBadge() { return document.getElementById('mp-chat-nav-badge'); }

    function _appendWhisperToMainChat(msg) {
        const mainChat = document.getElementById('chat-messages');
        if (!mainChat) return;
        const bubble = document.createElement('div');
        const side = msg.is_mine ? 'sent' : 'recv';
        bubble.className = 'chat-bubble chat-bubble--whisper chat-bubble--whisper-' + side;
        const label = msg.is_mine
            ? '🤫 → ' + _safe(msg.whisper_to)
            : '🤫 ' + _safe(msg.character_name) + ' → Ty';
        bubble.innerHTML =
            '<div class="chat-bubble__content"><em>' + _safe(msg.message) + '</em></div>' +
            '<div class="chat-bubble__meta"><span class="bubble-meta__left"><span class="bubble-meta__name">' + label + '</span></span></div>';
        mainChat.appendChild(bubble);
        mainChat.scrollTop = mainChat.scrollHeight;
    }

    function _appendChatMessage(msg) {
        const isWhisper = !!msg.whisper_to;
        if (isWhisper) {
            _appendWhisperToMainChat(msg);
            return;
        }
        const el = document.createElement('div');
        el.className = 'mp-chat-msg ' + (msg.is_mine ? 'mp-chat-msg--mine' : 'mp-chat-msg--other');
        el.innerHTML = '<div class="mp-chat-msg__name">' + _safe(msg.character_name) + '</div>' + _safe(msg.message);
        const container = _chatMessages();
        if (container) {
            container.appendChild(el);
            container.scrollTop = container.scrollHeight;
        }
    }

    function _updateChatBadge() {
        const badge = _chatBadge();
        const navBadge = _chatNavBadge();
        if (badge) {
            if (_chatUnread > 0) { badge.hidden = false; badge.textContent = _chatUnread; }
            else badge.hidden = true;
        }
        if (navBadge) navBadge.hidden = _chatUnread === 0;
    }

    async function _pollChat() {
        if (!_active || !_campaignId) return;
        try {
            const data = await _apiFetch('/multiplayer/campaigns/' + _campaignId + '/chat?since_id=' + _chatLastId);
            for (const msg of (data.messages || [])) {
                _appendChatMessage(msg);
                if (_chatLastId < msg.id) _chatLastId = msg.id;
                if (!msg.is_mine && msg.character_name) _sessionPlayers.add(msg.character_name);
                if (!_chatOpen && !msg.is_mine) _chatUnread++;
            }
            _updateChatBadge();
        } catch (e) {
            // non-critical poll errors ignored
        }
        if (_active) _chatPollTimer = setTimeout(_pollChat, 5000);
    }

    function _startChatPoll() {
        if (_chatPollTimer) return;
        _chatPollTimer = setTimeout(_pollChat, 1000);
    }

    function _stopChatPoll() {
        clearTimeout(_chatPollTimer);
        _chatPollTimer = null;
    }

    function minimizePartyChat() {
        _minimized = !_minimized;
        const panel = document.getElementById('party-chat-panel');
        if (!panel) return;
        panel.classList.toggle('party-chat-panel--minimized', _minimized);
        if (!_minimized) {
            _chatUnread = 0;
            _updateChatBadge();
        }
        try { localStorage.setItem('aigm_chat_minimized', _minimized ? '1' : '0'); } catch {}
    }

    function _restorePosition(panel) {
        try {
            localStorage.removeItem('aigm_chat_left');   // clean up stale key from v1
            const savedTop = localStorage.getItem('aigm_chat_top');
            if (savedTop) {
                const clamped = Math.max(10, Math.min(window.innerHeight - 120, parseInt(savedTop)));
                panel.style.bottom = 'auto';
                panel.style.top = clamped + 'px';
            } else {
                panel.style.top = '';
                panel.style.bottom = '';   // fall back to CSS default: bottom: 80px
            }
        } catch {}
    }

    function _initDrag(panel) {
        if (!panel || panel._dragInitialized) return;
        panel._dragInitialized = true;
        const header = panel.querySelector('.party-chat-panel__header');
        if (!header) return;

        header.addEventListener('pointerdown', e => {
            if (e.target.closest('button')) return;
            const startY = e.clientY;
            const startTop = panel.getBoundingClientRect().top;
            panel.style.bottom = 'auto';
            panel.style.top = startTop + 'px';
            header.style.cursor = 'grabbing';
            e.preventDefault();

            function onMove(ev) {
                const newTop = Math.max(10, Math.min(window.innerHeight - 120, startTop + ev.clientY - startY));
                panel.style.top = newTop + 'px';
            }
            function onUp() {
                header.style.cursor = '';
                try { localStorage.setItem('aigm_chat_top', panel.style.top); } catch {}
                document.removeEventListener('pointermove', onMove);
                document.removeEventListener('pointerup', onUp);
            }
            document.addEventListener('pointermove', onMove);
            document.addEventListener('pointerup', onUp);
        });
    }

    function togglePartyChat() {
        if (_minimized) { minimizePartyChat(); return; }
        _chatOpen = !_chatOpen;
        const body = document.getElementById('mp-chat-body');
        const toggle = document.querySelector('.mp-chat-panel__toggle');
        if (body) body.hidden = !_chatOpen;
        if (toggle) toggle.setAttribute('aria-expanded', String(_chatOpen));
        if (_chatOpen) {
            _chatUnread = 0;
            _updateChatBadge();
            const container = _chatMessages();
            if (container) container.scrollTop = container.scrollHeight;
        }
    }

    async function _sendPartyMessage(message) {
        if (!_campaignId || !message.trim()) return;
        let whisperTo = null;
        let actualMsg = message.trim();
        const whisperMatch = actualMsg.match(/^\/whisper\s+(\S+)\s+(.+)$/i);
        if (whisperMatch) {
            whisperTo = whisperMatch[1];
            actualMsg = whisperMatch[2];
        }
        try {
            await _apiFetch('/multiplayer/campaigns/' + _campaignId + '/chat', {
                method: 'POST',
                body: JSON.stringify({
                    message: actualMsg,
                    character_name: _characterName || 'Gracz',
                    whisper_to: whisperTo,
                }),
            });
        } catch (e) {
            console.warn('[Chat] send error:', e);
        }
    }

    function _appendUserAction(text) {
        const chat = _chat();
        if (!chat) return;
        if (_currentActionBubble) {
            const textEl = _currentActionBubble.querySelector('.mp-action-text');
            if (textEl) textEl.textContent = text;
            if (!_currentActionBubble.querySelector('.mp-action-edited')) {
                const tag = document.createElement('span');
                tag.className = 'mp-action-edited';
                tag.style.cssText = 'font-size:10px;opacity:.4;display:block;margin-top:4px;text-align:right;font-style:italic';
                tag.textContent = 'edytowano';
                _currentActionBubble.appendChild(tag);
            }
            return;
        }
        const b = document.createElement('div');
        b.className = 'chat-bubble chat-bubble--user';
        const textEl = document.createElement('div');
        textEl.className = 'mp-action-text';
        textEl.textContent = text;
        b.appendChild(textEl);
        chat.appendChild(b);
        chat.scrollTop = chat.scrollHeight;
        _currentActionBubble = b;
    }

    function _appendActionBubble(characterName, text) {
        const isMe = characterName === _characterName;
        const chat = _chat();
        if (!chat) return;
        if (isMe && typeof appendMessage === 'function') {
            appendMessage({ role: 'user', content: text, created_at: new Date() });
            return;
        }
        const b = document.createElement('div');
        b.className = 'chat-bubble chat-bubble--user';
        b.style.opacity = isMe ? '1' : '0.8';
        b.innerHTML = `<div style="font-size:11px;font-weight:700;opacity:.55;margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em">${_safe(characterName)}</div><div>${_safe(text)}</div>`;
        chat.appendChild(b);
        chat.scrollTop = chat.scrollHeight;
    }

    function _appendRound(round, skipOwnAction = false) {
        for (const action of (round.actions || [])) {
            if (skipOwnAction && action.character_name === _characterName) continue;
            if (action.character_name && action.character_name !== _characterName) {
                _sessionPlayers.add(action.character_name);
            }
            _appendActionBubble(action.character_name, action.action_text);
        }
        _appendNarration(round.narrative || '', round.my_note || null);
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
            _showNote(myNote);
        } else {
            _hideNote();
        }
        chat.scrollTop = chat.scrollHeight;
    }

    function _showNote(text) {
        const noteEl = _noteEl();
        if (!noteEl) return;
        noteEl.hidden = false;
        const body = noteEl.querySelector('.mp-note-body');
        if (body) body.textContent = text;
        noteEl.classList.add('mp-note--open');
        const tab = noteEl.querySelector('.mp-note__tab');
        if (tab) tab.setAttribute('aria-expanded', 'true');
    }

    function _hideNote() {
        const noteEl = _noteEl();
        if (!noteEl) return;
        noteEl.hidden = true;
        noteEl.classList.remove('mp-note--open');
        const body = noteEl.querySelector('.mp-note-body');
        if (body) body.textContent = '';
        const tab = noteEl.querySelector('.mp-note__tab');
        if (tab) tab.setAttribute('aria-expanded', 'false');
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
            if (s.host_note) {
                _showNote(s.host_note);
                // Receiving host_note means this user is now host (backend only sends it to new host_user_id)
                _isHost = true;
                const mpTimerSection = document.getElementById('mp-timer-section');
                if (mpTimerSection) {
                    mpTimerSection.style.display = '';
                    const inp = document.getElementById('mp-timer-input');
                    if (inp) { inp.value = _campaignTimerMinutes; updateMpTimerHint?.(); }
                }
            }
            const roundNum = s.round_number;
            if (_currentRoundNumber !== null && roundNum !== _currentRoundNumber) {
                _appendRoundDivider(roundNum);
            }
            _currentRoundNumber = roundNum;
            const base = { roundNumber: roundNum, submitted: s.submitted_count, total: s.total_players, deadline: s.deadline };

            if (s.status === 'none' || (s.status === 'collecting' && !s.my_submitted)) {
                _setComposerState(true, 'Twoja akcja w tej rundzie...');
                _updateStatusBar({ ...base, statusText: s.submitted_count > 0 ? `${s.submitted_count} z ${s.total_players} oddało` : '' });
                _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
                return;
            }
            if (s.status === 'collecting' && s.my_submitted) {
                // Keep enabled — player can edit/resubmit until round fully closes
                _setComposerState(true, 'Możesz zmienić swoją akcję...');
                _updateStatusBar({ ...base, statusText: `czekasz na ${s.total_players - s.submitted_count} z ${s.total_players}` });
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
            _appendRound(n, true); // skip own action — already shown by handleSubmit
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
        _currentActionBubble = null;
        _setComposerState(true, 'Twoja akcja w tej rundzie...');
        _poll();
    }

    async function handleSubmit() {
        const inp = _input();
        if (!inp || !_active) return;
        const text = inp.value.trim();
        if (!text) return;

        // GF6: spectators can only send party chat (e.g. /whisper), not game actions
        if (_isSpectator) {
            await _sendPartyMessage(text);
            inp.value = '';
            return;
        }

        // #1173: block resubmit while the composer is disabled ("GM tworzy narrację…").
        // Enter reaches handleSubmit even when the send button is greyed out; without
        // this guard it resubmits the round and breaks the _pollTimer chain.
        if (!_sendEnabled) return;

        _stopPolling(); // prevent concurrent poll during submit
        inp.value = '';
        _appendUserAction(text); // show immediately as chat bubble
        _setComposerState(false, 'Wysyłanie...');

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
                // Still collecting — allow editing until all players submit
                _setComposerState(true, 'Możesz zmienić swoją akcję...');
                _updateStatusBar({ submitted: result.submitted, total: result.total, statusText: `czekasz na ${result.total - result.submitted} z ${result.total}` });
                _pollTimer = setTimeout(_poll, POLL_WAITING_MS);
            }
        } catch (e) {
            console.warn('[MP] submit error:', e);
            _setComposerState(true, 'Twoja akcja w tej rundzie...');
        }
    }

    // GF6 (#926): isSpectator=true → read-only mode, no action submission, no round polling
    async function activate(campaignId, characterId, characterName, isHost = false, timerMinutes = 1440, isSpectator = false) {
        _campaignId = campaignId;
        _characterId = characterId;
        _characterName = characterName;
        _active = true;
        _lastShownRoundId = null;
        _sendEnabled = !isSpectator;
        _isHost = isHost;
        _isSpectator = isSpectator;
        _campaignTimerMinutes = timerMinutes;

        const inp = _input();
        if (inp) { inp.removeEventListener('input', _onInputEvent); inp.addEventListener('input', _onInputEvent); }

        _injectStatusBar(isSpectator);
        _hideNote();
        const mpSection = document.getElementById('mp-multiplayer-section');
        if (mpSection) mpSection.style.display = '';
        const mpTimerSection = document.getElementById('mp-timer-section');
        if (mpTimerSection) {
            mpTimerSection.style.display = (_isHost && !isSpectator) ? '' : 'none';
        }

        if (isSpectator) {
            // Spectator: disable composer, set hint, open party chat for /whisper support
            _setComposerState(false, 'Widz — wpisz /whisper <postać> <tekst> aby podpowiedzieć');
            const btn = _sendBtn();
            if (btn) {
                btn.disabled = false;
                btn.style.opacity = '';
                // Re-enable for /whisper (party chat send, not action submit)
            }
        } else {
            // Normal player: load round history + start polling
            try {
                const hist = await _apiFetch(`/campaigns/${_campaignId}/rounds/history`);
                if (!_active) return;
                for (const round of (hist.rounds || [])) {
                    _appendRound(round);
                    _lastShownRoundId = round.round_id;
                }
            } catch (_) {}

            try {
                const s = await _apiFetch(`/campaigns/${_campaignId}/round/status`);
                if (!_active) return;
                if (s.my_submitted && s.my_action && s.status === 'collecting') {
                    _appendUserAction(s.my_action);
                    const i = _input();
                    if (i && !i.value.trim()) i.value = s.my_action;
                }
            } catch (_) {}

            _poll();
        }

        const chatPanel = document.getElementById('party-chat-panel');
        if (chatPanel) {
            chatPanel.hidden = false;
            _initDrag(chatPanel);
            _restorePosition(chatPanel);
            try { _minimized = localStorage.getItem('aigm_chat_minimized') === '1'; } catch { _minimized = false; }
            chatPanel.classList.toggle('party-chat-panel--minimized', _minimized);
        }

        _chatLastId = 0;
        _chatUnread = 0;
        _chatOpen = false;
        _startChatPoll();
    }

    function deactivate() {
        _active = false;
        _stopPolling();
        _stopCountdown();
        _stopChatPoll();
        _chatLastId = 0;
        _chatUnread = 0;
        _chatOpen = false;
        _minimized = false;
        _sessionPlayers.clear();
        const chatPanel = document.getElementById('party-chat-panel');
        if (chatPanel) {
            chatPanel.hidden = true;
            chatPanel.classList.remove('party-chat-panel--minimized', 'party-chat-panel--floating');
            chatPanel.style.left = '';
        }
        const chatContainer = _chatMessages();
        if (chatContainer) chatContainer.innerHTML = '';
        _currentRoundNumber = null;
        _currentDeadline = null;
        _campaignId = null;
        _characterId = null;
        _characterName = null;
        _currentActionBubble = null;
        _sendEnabled = true;
        _isSpectator = false;

        const inp = _input();
        if (inp) { inp.removeEventListener('input', _onInputEvent); inp.placeholder = 'Co robisz? Możesz pisać swobodnie...'; }

        _removeStatusBar();
        const btn = _sendBtn();
        if (btn) { btn.disabled = false; btn.style.opacity = ''; }
        _hideNote();
        const mpSection = document.getElementById('mp-multiplayer-section');
        if (mpSection) mpSection.style.display = 'none';
        const mpTimerSection = document.getElementById('mp-timer-section');
        if (mpTimerSection) mpTimerSection.style.display = 'none';
    }

    async function leave() {
        const leaveMsg = _isSpectator
            ? 'Zakończyć obserwację?'
            : 'Opuścić grę multiplayer? Twoja akcja w bieżącej rundzie zostanie zachowana.';
        if (!confirm(leaveMsg)) return;
        try {
            await _apiFetch(`/multiplayer/campaigns/${_campaignId}/leave`, { method: 'POST' });
        } catch (e) {
            console.warn('[MP] leave error:', e);
        }
        deactivate();
        if (typeof loadCampaigns === 'function') {
            loadCampaigns().then(() => { if (typeof showScreen === 'function') showScreen('campaigns'); });
        }
    }

    window.multiplayerUI = { activate, deactivate, isActive: () => _active, handleSubmit, leave, togglePartyChat, minimizePartyChat, _sendChat: _sendPartyMessage, _getCampaignId: () => _campaignId, getSessionPlayers: () => Array.from(_sessionPlayers), isSpectator: () => _isSpectator, isHost: () => _isHost };
})();

// GF4 (#924) — router from hub: open create-lobby-screen with default AI mode
function openMultiplayerLobby() {
    document.getElementById('campaign-modes-hub')?.remove();
    setLobbyMode('ai');
    if (typeof showScreen === 'function') showScreen('create-lobby');
}

async function inviteFromGame() {
    const input = document.getElementById('game-invite-username');
    const msgEl = document.getElementById('game-invite-msg');
    const username = (input?.value || '').trim().replace(/^@/, '');
    const campaignId = window.multiplayerUI?._getCampaignId();
    if (!username || !campaignId) return;
    try {
        const token = localStorage.getItem('aigm_access_token') || localStorage.getItem('token') || '';
        const resp = await fetch(`/api/multiplayer/campaigns/${campaignId}/invite/username`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ username }),
        });
        if (!resp.ok) { const d = await resp.json().catch(() => ({})); throw new Error(d.detail || `HTTP ${resp.status}`); }
        if (msgEl) { msgEl.textContent = `✅ Zaproszono @${username}`; msgEl.style.color = 'var(--green,#4caf50)'; }
        if (input) input.value = '';
    } catch (e) {
        if (msgEl) { msgEl.textContent = '❌ ' + e.message; msgEl.style.color = 'var(--red,#e53935)'; }
    }
    setTimeout(() => { if (msgEl) msgEl.textContent = ''; }, 4000);
}

function _formatMinutes(m) {
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60), rem = m % 60;
    return rem > 0 ? `${h} h ${rem} min` : `${h} h`;
}

function setLobbyTimer(minutes) {
    const inp = document.getElementById('lobby-timer');
    if (inp) { inp.value = minutes; updateLobbyTimerHint(); }
}

function updateLobbyTimerHint() {
    const inp = document.getElementById('lobby-timer');
    const hint = document.getElementById('lobby-timer-hint');
    const val = parseInt(inp?.value) || 0;
    if (hint) hint.textContent = _formatMinutes(val);
    document.querySelectorAll('.lf-chip[data-minutes]').forEach(chip => {
        chip.classList.toggle('lf-chip--on', parseInt(chip.dataset.minutes) === val);
    });
}

function setLobbyMaxPlayers(n) {
    const sel = document.getElementById('lobby-max-players');
    if (sel) sel.value = String(n);
    document.querySelectorAll('.lf-tile[data-players]').forEach(tile => {
        tile.classList.toggle('lf-tile--on', parseInt(tile.dataset.players) === n);
    });
}

function updateMpTimerHint() {
    const inp = document.getElementById('mp-timer-input');
    const hint = document.getElementById('mp-timer-hint');
    if (inp && hint) hint.textContent = `= ${_formatMinutes(parseInt(inp.value) || 0)}`;
}

async function saveMpTimer() {
    const inp = document.getElementById('mp-timer-input');
    const msg = document.getElementById('mp-timer-msg');
    const minutes = parseInt(inp?.value);
    if (!minutes || minutes < 1 || minutes > 4320) {
        if (msg) { msg.textContent = 'Nieprawidłowa wartość (1–4320 min)'; msg.style.color = 'var(--red,#e53935)'; }
        return;
    }
    const token = localStorage.getItem('aigm_access_token') || localStorage.getItem('token') || '';
    const campaignId = window.multiplayerUI?._getCampaignId?.() || window.currentCampaignId;
    if (!campaignId) return;
    try {
        const resp = await fetch(`/api/multiplayer/campaigns/${campaignId}/timer`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ round_timer_minutes: minutes }),
        });
        if (!resp.ok) throw new Error(await resp.text());
        if (msg) { msg.textContent = `✓ Zapisano — ${_formatMinutes(minutes)}`; msg.style.color = 'var(--green,#4caf50)'; }
        setTimeout(() => { if (msg) msg.textContent = ''; }, 3000);
    } catch (e) {
        if (msg) { msg.textContent = '❌ ' + e.message; msg.style.color = 'var(--red,#e53935)'; }
    }
}

function mpNoteToggle() {
    const noteEl = document.getElementById('multiplayer-private-note');
    if (!noteEl) return;
    const isOpen = noteEl.classList.toggle('mp-note--open');
    const tab = noteEl.querySelector('.mp-note__tab');
    if (tab) tab.setAttribute('aria-expanded', String(isOpen));
}

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

// ── Lobby mode & template selection ──────────────────────────────────────────

let _lobbyMode = 'ai'; // 'ai' | 'prebuilt'
let _lobbyTemplateId = null;
let _lobbyTemplates = [];

function setLobbyMode(mode) {
    _lobbyMode = mode;
    document.getElementById('lobby-mode-ai')?.classList.toggle('lf-tile--on', mode === 'ai');
    document.getElementById('lobby-mode-prebuilt')?.classList.toggle('lf-tile--on', mode === 'prebuilt');
    const tplSection = document.getElementById('lobby-template-section');
    if (tplSection) tplSection.style.display = mode === 'prebuilt' ? '' : 'none';
    // Hide name input in prebuilt mode — title comes from template
    const nameSection = document.getElementById('lobby-name-section');
    if (nameSection) nameSection.style.display = mode === 'prebuilt' ? 'none' : '';
    if (mode === 'prebuilt' && !_lobbyTemplates.length) _loadLobbyTemplates();
    if (mode === 'ai') { _lobbyTemplateId = null; document.getElementById('lobby-tpl-summary')?.style.setProperty('display','none'); }
}

async function _loadLobbyTemplates() {
    const list = document.getElementById('lobby-template-list');
    if (!list) return;
    try {
        const data = await _lobbyFetch('/campaign-templates');
        _lobbyTemplates = data.items || [];
        if (!_lobbyTemplates.length) {
            list.innerHTML = '<div style="opacity:.5;font-size:13px;padding:8px 0">Brak opublikowanych przygód</div>';
            return;
        }
        list.innerHTML = '';
        for (const t of _lobbyTemplates) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'lf-tpl-card';
            btn.dataset.tplId = t.id;
            btn.innerHTML = `<span class="lf-tpl-card__title">${t.title}</span>${t.difficulty_rating ? `<span class="lf-tpl-card__diff">★${t.difficulty_rating}</span>` : ''}`;
            btn.addEventListener('click', () => selectLobbyTemplate(t.id));
            list.appendChild(btn);
        }
    } catch (e) {
        list.innerHTML = '<div style="opacity:.5;font-size:13px;padding:8px 0">Błąd ładowania szablonów</div>';
    }
}

function selectLobbyTemplate(id) {
    _lobbyTemplateId = id;
    const tpl = _lobbyTemplates.find(t => t.id === id);
    document.querySelectorAll('.lf-tpl-card').forEach(c => c.classList.toggle('lf-tpl-card--on', parseInt(c.dataset.tplId) === id));
    // Show summary
    const summary = document.getElementById('lobby-tpl-summary');
    if (summary && tpl) {
        const desc = tpl.description || '';
        const atm = tpl.atmosphere ? `<em style="opacity:.6;font-size:11px">${tpl.atmosphere}</em>` : '';
        summary.innerHTML = (desc ? `<p style="margin:0 0 4px">${desc}</p>` : '') + atm;
        summary.style.display = desc || tpl.atmosphere ? '' : 'none';
    }
}

async function createLobby() {
    const timerMinutes = parseInt(document.getElementById('lobby-timer')?.value || '1440');
    const maxPlayers = parseInt(document.getElementById('lobby-max-players')?.value || '4');
    const errEl = document.getElementById('create-lobby-error');
    const btn = document.querySelector('#create-lobby-screen .lf-create-btn');

    let title;
    if (_lobbyMode === 'prebuilt') {
        if (!_lobbyTemplateId) {
            if (errEl) { errEl.textContent = 'Wybierz przygodę z listy'; errEl.style.display = 'block'; }
            return;
        }
        title = _lobbyTemplates.find(t => t.id === _lobbyTemplateId)?.title || 'Kampania';
    } else {
        title = document.getElementById('lobby-title')?.value.trim();
        if (!title) { if (errEl) { errEl.textContent = 'Podaj nazwę sesji'; errEl.style.display = 'block'; } return; }
    }

    if (timerMinutes < 1 || timerMinutes > 4320) {
        if (errEl) { errEl.textContent = 'Timer: 1–4320 minut'; errEl.style.display = 'block'; }
        return;
    }
    // Disable to prevent duplicate creation on double-click or page refresh
    if (btn) { btn.disabled = true; btn.textContent = 'Przyzywanie…'; }
    const payload = { title, round_timer_minutes: timerMinutes, max_players: maxPlayers };
    if (_lobbyMode === 'prebuilt' && _lobbyTemplateId) payload.template_id = _lobbyTemplateId;
    try {
        const data = await _lobbyFetch('/multiplayer/campaigns', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        _lobbyId = data.campaign_id;
        // Reset mode state for next lobby creation
        _lobbyMode = 'ai'; _lobbyTemplateId = null; _lobbyTemplates = [];
        await _showLobbyScreen(_lobbyId);
    } catch (e) {
        if (errEl) { errEl.textContent = 'Błąd: ' + e.message; errEl.style.display = 'block'; }
        if (btn) { btn.disabled = false; btn.innerHTML = '<span class="lf-create-btn__ornament" aria-hidden="true">✦</span> Utwórz Lobby <span class="lf-create-btn__ornament" aria-hidden="true">✦</span>'; }
    }
}

function _leaveLobbyNavOnly() {
    // Navigate back to campaigns WITHOUT leaving the lobby — player stays in the lobby,
    // can return to it via the "my lobbies" list on the campaigns page.
    _stopLobbyPoll();
    if (typeof loadCampaigns === 'function') loadCampaigns();
    if (typeof showScreen === 'function') showScreen('campaigns');
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
    const timerMin = data.round_timer_minutes || (data.round_timer_hours * 60);
    if (subEl) subEl.textContent = `${_formatMinutes(timerMin)}/runda · max ${data.max_players} graczy`;

    const membersEl = document.getElementById('lobby-members-list');
    if (membersEl) {
        const memberSlots = data.members.map(m => {
            const isAccepted = m.status === 'accepted';
            const isPending = m.status === 'pending';
            const modClass = isAccepted ? 'lf-party-slot--joined' : isPending ? 'lf-party-slot--pending' : '';
            const initials = (m.display_name || m.username || '?')[0].toUpperCase();
            const meta = m.role === 'owner' ? 'Host' : isPending ? 'zaproszony…' : 'dołączył';
            const kickBtn = data.is_host && m.role !== 'owner'
                ? `<button onclick="kickPlayer(${m.user_id})" class="lf-party-slot__kick" title="Wyrzuć gracza">✕</button>`
                : '';
            return `<div class="lf-party-slot ${modClass}">
                <div class="lf-party-slot__avatar">${initials}</div>
                <div class="lf-party-slot__info">
                    <div class="lf-party-slot__name">${m.display_name}</div>
                    <div class="lf-party-slot__meta">${meta}</div>
                </div>
                ${kickBtn}
            </div>`;
        }).join('');
        const ghostCount = Math.max(0, data.max_players - data.members.length);
        const ghostSlots = Array.from({length: ghostCount}, () =>
            `<div class="lf-party-slot lf-party-slot--empty">
                <div class="lf-party-slot__avatar lf-party-slot__avatar--empty">✦</div>
                <div class="lf-party-slot__info">
                    <div class="lf-party-slot__name">Wolne miejsce</div>
                </div>
            </div>`
        ).join('');
        membersEl.innerHTML = memberSlots + ghostSlots;
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
    if (!confirm('Opuścić lobby? Stracisz swoje miejsce w sesji.')) return;
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

// Init lobby form hints on load
document.addEventListener('DOMContentLoaded', () => {
    updateLobbyTimerHint();
    setLobbyMaxPlayers(4);
});

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

async function sendPartyMessage() {
    const input = document.getElementById('mp-chat-input');
    const msg = (input?.value || '').trim();
    if (!msg) return;
    if (input) input.value = '';
    await window.multiplayerUI?._sendChat?.(msg);
}

// #959/#960: enter a started MP game by campaign ID — fetches campaign then activates MP UI.
// enterGame() calls multiplayerUI.deactivate() as cleanup, so activate() must be called
// explicitly here to start round polling + show the party chat panel.
async function enterMpGame(campaignId) {
    try {
        const campaign = await _lobbyFetch(`/campaigns/${campaignId}`);
        if (typeof enterGame === 'function') {
            await enterGame(campaign);
        }
        if (campaign.mode === 'multiplayer' && window.multiplayerUI?.activate) {
            let timerMin = 1440, isSpectator = false;
            let charId = null, charName = 'Bohater';
            try {
                const lobby = await _lobbyFetch(`/multiplayer/campaigns/${campaignId}/lobby`);
                timerMin = lobby.round_timer_minutes ?? 1440;
                const me = (lobby.members || []).find(m => m.user_id === currentUser?.id);
                isSpectator = me?.role === 'spectator';
                charId = me?.character_id ?? null;
            } catch (_) {}
            if (!charId) {
                charId = (typeof currentHero !== 'undefined' ? currentHero?.id : null)
                      ?? (typeof characterData !== 'undefined' ? characterData?.id : null);
            }
            charName = (typeof currentHero !== 'undefined' && currentHero?.name) ? currentHero.name
                     : (typeof characterData !== 'undefined' && characterData?.name) ? characterData.name
                     : 'Bohater';
            if (isSpectator && typeof _enterGameAsSpectator === 'function') {
                await _enterGameAsSpectator(campaign, Math.max(1, Math.round(timerMin / 60)));
                return;
            }
            await window.multiplayerUI.activate(campaign.id, charId, charName, false, timerMin, isSpectator);
        }
    } catch (e) {
        console.error('[MP] enterMpGame failed:', e);
        if (typeof loadCampaigns === 'function') {
            await loadCampaigns();
            if (typeof showScreen === 'function') showScreen('campaigns');
        }
    }
}
