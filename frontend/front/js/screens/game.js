// ============================================================================
// Game Screen
// ============================================================================
// ── In-game clock (T5) ───────────────────────────────────────────────────
// Renders "Dzień 3, 14:00 Popołudnie" in the header. Mirrors backend state
// from clock_service.get_clock_state() — single source of truth is server.
function renderClock(state) {
    const el = elements.headerClock;
    if (el) {
        if (!state || typeof state.display !== 'string') {
            el.textContent = '';
            el.hidden = true;
        } else {
            // #952 — chip "☀ Rano · 08:00" (ikona+kolor = pora dnia, słowo pory + godzina).
            const period = state.period || '';
            const icon = (period === 'Noc' || period === 'Wieczór') ? '🌙' : '☀';
            const hour = state.hour_str || '';
            const parts = [period, hour].filter(Boolean).join(' · ');
            el.textContent = parts ? `${icon} ${parts}` : `${icon}`;
            el.title = state.display; // pełny opis (Dzień N, ...) w tooltipie
            el.hidden = false;
            el.dataset.period = period;
        }
    }
    // Time-of-day overlay — re-apply with current period
    applyTimeOfDayOverlay(state?.period || null);
}

async function fetchAndRenderClock(campaignId) {
    if (!campaignId) { renderClock(null); return; }
    try {
        const state = await apiRequest('GET', `/campaigns/${campaignId}/clock`);
        renderClock(state);
    } catch {
        renderClock(null);
    }
}

// ── Time-of-day overlay (visual configuration) ─────────────────────────
// Reads visual settings from `/api/visual/public` once per session, caches
// them, and applies a discreet color frame on the chat container per the
// current clock period. Admin-configurable in Admin → Wygląd.

let _visualSettings = null;
const _PERIOD_KEY_MAP = {
    'Rano':       'time_of_day.rano',
    'Popołudnie': 'time_of_day.popoludnie',
    'Wieczór':    'time_of_day.wieczor',
    'Noc':        'time_of_day.noc',
};

async function loadVisualSettings() {
    try {
        const res = await apiRequest('GET', '/visual/public');
        _visualSettings = res?.settings || null;
    } catch {
        _visualSettings = null;
    }
}

function applyTimeOfDayOverlay(period) {
    const root = document.documentElement;
    const settings = _visualSettings;
    // No settings loaded or feature disabled → strip CSS vars + class
    if (!settings || settings['time_of_day.enabled'] === false) {
        root.style.removeProperty('--tod-color');
        root.style.removeProperty('--tod-accent');
        root.style.removeProperty('--tod-intensity');
        root.dataset.todMode = 'off';
        root.dataset.todPeriod = '';
        return;
    }
    const periodKey = _PERIOD_KEY_MAP[period] || 'time_of_day.popoludnie';
    const periodColors = settings[periodKey] || { color: '#c9a54a', accent: '#d4b65e' };
    const mode = settings['time_of_day.mode'] || 'frame';
    const intensity = Math.max(0, Math.min(100, Number(settings['time_of_day.intensity']) || 60));

    root.style.setProperty('--tod-color', periodColors.color);
    root.style.setProperty('--tod-accent', periodColors.accent);
    root.style.setProperty('--tod-intensity', String(intensity / 100));
    root.dataset.todMode = mode;
    root.dataset.todPeriod = period || '';
}

async function enterGame(campaign, opts = {}) {
    // #1008: clear any stale death/victory overlay before (re)entering a live campaign.
    // The overlay only auto-hides via player-initiated actions; if the hero is revived from
    // another surface (admin card #1002), the leftover #death-screen (fixed, inset:0,
    // body{overflow:hidden}) would cover the rendered chat → "po wskrzeszeniu brak treści".
    hideDeathScreen();
    hideVictoryScreen();
    // #950: Clear party chat panel before entering any game type (single/dungeon).
    // activate() is called separately only for MP — without this, the panel stays
    // visible (sticky state) if the player visited MP earlier in the same browser session.
    window.multiplayerUI?.deactivate?.();
    // Belt-and-suspenders: directly clean up in case display:flex overrides [hidden] (Safari)
    // or deactivate() ran before the DOM element existed.
    const _cp = document.getElementById('party-chat-panel');
    if (_cp) {
        _cp.hidden = true;
        _cp.classList.remove('party-chat-panel--minimized', 'party-chat-panel--floating');
        _cp.style.left = '';
    }

    // Persist session so F5 restores to this exact state
    try {
        if (currentHero?.id) localStorage.setItem('aigm_hero_id', currentHero.id);
        if (campaign?.id) localStorage.setItem('aigm_campaign_id', campaign.id);
    } catch {}

    elements.characterNameDisplay.textContent = characterData?.name || 'Bohater';
    // Set text + bar together via updateHeaderStats so the header HP bar width
    // matches the value on campaign entry (fixes stale bar from a previous hero/session).
    updateHeaderStats();
    elements.chatMessages.innerHTML = '';
    document.getElementById('skill-roll-popup')?.remove();
    const _diceOverlayEl = document.getElementById('dice-overlay');
    if (_diceOverlayEl) _diceOverlayEl.hidden = true;

    // T5 — fetch initial clock state and render in header
    // Visual overlay settings + dice config loaded in parallel; clock render also applies overlay
    Promise.all([loadVisualSettings(), _fetchDice3DConfig()]).then(() => {
        fetchAndRenderClock(campaign.id);
    });

    try {
        const [response, combatHist] = await Promise.all([
            apiRequest('GET', `/campaigns/${campaign.id}/turns`),
            fetch(`/api/campaigns/${campaign.id}/combat/turns/history`).then(r => r.ok ? r.json() : { turns: [] }).catch(() => ({ turns: [] })),
        ]);
        const turns = response.turns || (Array.isArray(response) ? response : []);
        const combatRows = Array.isArray(combatHist.turns) ? combatHist.turns : [];

        // Build interleaved timeline by created_at. campaign_turns are wrapped, combat_turns flow
        // in between. Combat-roll player turns ("__AI_GM_COMBAT_ROLL_V1__") render GM narrative only —
        // the visual roll card comes from the corresponding combat_turns row.
        const timeline = [];
        for (const t of turns) timeline.push({ kind: 'turn', at: t.created_at || '', data: t });
        for (const c of combatRows) timeline.push({ kind: 'combat', at: c.created_at || '', data: c });
        // Normalize timestamps before sort: campaign_turns use space separator ("2026-06-25 12:58:01")
        // while combat_turns use ISO T+Z ("2026-06-25T10:27:08Z"). Space (0x20) < T (0x54) makes
        // string compare wrong — campaign turns always sort before combat turns regardless of time.
        const normTs = ts => String(ts || '').replace(' ', 'T').replace(/Z$/, '');
        timeline.sort((a, b) => {
            const ta = normTs(a.at), tb = normTs(b.at);
            if (ta !== tb) return ta < tb ? -1 : 1;
            // Same timestamp: combat events first (they fired before the wrapping campaign turn)
            if (a.kind !== b.kind) return a.kind === 'combat' ? -1 : 1;
            return Number(a.data.id || 0) - Number(b.data.id || 0);
        });

        if (timeline.length > 0) {
            for (const item of timeline) {
                // #1008: render each item in isolation — a single malformed combat/turn row
                // must NOT abort the whole history render (which left the chat blank for
                // combat-heavy campaigns after resurrect). Skip the bad row, keep the rest.
                try {
                    if (item.kind === 'combat') {
                        const row = item.data;
                        const evt = String(row.event_type || '');
                        // Re-use live renderer for attack/death; skip system events (start/end/initiative)
                        if (evt === 'attack' || evt === 'death' || evt === 'zone_change') {
                            appendCombatTurnCard(row);
                            lastRenderedCombatTurnId = Math.max(lastRenderedCombatTurnId, Number(row.id) || 0);
                        }
                        continue;
                    }
                    const turn = item.data;
                    const utext = turn.user_text || '';
                    if (utext && !utext.startsWith('__AI_GM')) {
                        // Skill test rich format: "[Rzut: Skill — d20 +mod = total — Outcome]"
                        let displayText = utext;
                        const richM = utext.match(/^\[Rzut:\s*(.+?)\s*[—-]\s*(\d+)\s*([+\-−])\s*(\d+)\s*=\s*(\d+)\s*[—-]\s*(.+?)\]$/);
                        const simpleM = !richM && utext.match(/^\[Rzut:\s*(.+?)\s*[—-]\s*(\d+)\]$/);
                        if (richM) {
                            const sign = richM[3] === '−' ? '−' : richM[3];
                            displayText = `🎲 ${richM[1]}: ${richM[2]} ${sign}${richM[4]} = ${richM[5]} — ${richM[6]}`;
                        } else if (simpleM) {
                            displayText = `🎲 ${simpleM[1]}: rzut ${simpleM[2]}`;
                        }
                        appendMessage({ role: 'user', content: displayText, created_at: turn.created_at, turn_number: turn.turn_number, route: turn.route, turn_id: turn.id }, { autoSpeak: false });
                    }
                    if (turn.assistant_text) {
                        const { narrative: gmContent, ...gmMeta } = parseGmFull(turn.assistant_text);
                        if (gmContent && gmContent.trim()) {
                            appendMessage({ role: 'assistant', content: gmContent, created_at: turn.created_at, turn_number: turn.turn_number, route: turn.route, debugMeta: gmMeta, turn_id: turn.id }, { autoSpeak: false });
                        }
                    }
                } catch (itemErr) {
                    console.warn('[enterGame] skipped a malformed history item:', itemErr, item);
                }
            }
        } else {
            // No turns yet — new campaign. Send an empty opening turn to trigger plan gen + opening scene
            showScreen('game');
            updateAdminSettingsVisibility();
            if (characterData) populateCharacterSheet(characterData);
            scrollToBottom();
            startCombatPolling();
            const typingIndicator = showTypingIndicator();
            try {
                const openingResp = await apiRequest('POST', `/campaigns/${campaign.id}/turns`, {
                    text: '__AI_GM_OPEN',
                    character_id: characterData?.id,
                });
                typingIndicator.remove();
                const gmText = openingResp.prose || openingResp.result?.message || openingResp.assistant_text || '';
                if (gmText) {
                    const { narrative: gmContent } = parseGmFull(gmText);
                    if (gmContent) appendMessage({ role: 'assistant', content: gmContent, created_at: new Date() });
                }
            } catch (_e) {
                typingIndicator.remove();
                const fallback = opts.dungeonFallbackNarrative || 'Witaj, bohaterze. Twoja przygoda się zaczyna…';
                appendMessage({ role: 'assistant', content: fallback, created_at: new Date() });
            }
            scrollToBottom();
            return; // already called showScreen + startCombatPolling above
        }
    } catch (error) {
        console.error('Failed to load chat history:', error);
        // #1008: never leave a silently blank chat — if nothing rendered, surface a hint
        // so the player knows to retry instead of staring at an empty screen.
        if (elements.chatMessages && elements.chatMessages.children.length === 0) {
            const note = document.createElement('div');
            note.className = 'chat-bubble chat-bubble--system';
            note.style.cssText = 'opacity:0.7;text-align:center;padding:14px;font-size:0.85rem';
            note.textContent = 'Nie udało się załadować historii kampanii. Odśwież stronę, aby spróbować ponownie.';
            elements.chatMessages.appendChild(note);
        }
    }

    if (characterData) {
        populateCharacterSheet(characterData);
    }

    updateAdminSettingsVisibility();
    showScreen('game');
    _refreshBugReportFab();
    scrollToBottom();
    window.clog?.setContext({ campaign_id: campaign.id, character_id: characterData?.id, screen: 'game' });
    window.clog?.event('game_entered', { campaign_id: campaign.id, character_id: characterData?.id });
    startCombatPolling();

    // U19 (#571) — recap card after a >24h gap (backend decides should_show).
    maybeShowRecap(campaign.id);

    // E1 (#416) — load active quests into the quest bar on campaign entry / resume.
    // Without this, the bar stays hidden until after the first turn of the session.
    try {
        const qResp = await fetch(`/api/campaigns/${campaign.id}/quests`).then(r => r.ok ? r.json() : null).catch(() => null);
        if (qResp?.active_quests) renderQuestBar(qResp.active_quests);
    } catch (_e) {}

    // Stage 10-C+ Bug 1 fix — on F5 / resume, the campaign GET payload carries
    // any pending_skill_test. Re-mount the roll popup so the player can't
    // walk away from a bad roll by refreshing.
    if (campaign?.pending_skill_test) {
        try { showSkillTestPopup(campaign.pending_skill_test); } catch (e) {
            console.warn('[skill-roll] could not restore pending popup on resume:', e);
        }
    }
    // #1045: restore advantage gate card if pending_zaskoczony was set before F5
    if (campaign?.pending_advantage_gate) {
        try { renderAdvantageGate(campaign.pending_advantage_gate); } catch (e) {
            console.warn('[advantage-gate] could not restore on resume:', e);
        }
    }
}

function appendMessage(msg, opts = {}) {
    const bubble = document.createElement('div');
    const isGm = msg.role === 'assistant' || msg.actor === 'gm';
    const isSystem = msg.role === 'system';
    const variant = isSystem ? 'system' : (isGm ? 'gm' : 'user');
    bubble.className = `chat-bubble chat-bubble--${variant}`;

    if (!isSystem) {
        const name = isGm
            ? 'MG — Mistrz Gry'
            : (characterData?.name || currentUser?.username || 'Gracz').toUpperCase();
        const turnNum = msg.turn_number != null ? String(msg.turn_number) : null;
        const route = msg.route ? String(msg.route).toUpperCase() : null;
        const dt = formatDateTime(msg.created_at || msg.timestamp);

        const namePart = `<span class="bubble-meta__name">${escapeHtml(name)}</span>`;
        const turnPart = turnNum ? `<span class="bubble-meta__turn">TURA ${escapeHtml(turnNum)}</span>` : '';
        const routePart = route && route !== 'NARRATIVE' ? `<span class="bubble-meta__route">${escapeHtml(route)}</span>` : '';
        const dtPart = dt ? `<span class="bubble-meta__datetime">${escapeHtml(dt)}</span>` : '';
        // Debug mode: show DB turn id as clickable chip
        const turnId = msg.turn_id || msg.id || null;
        const dbIdPart = (debugMode && turnId) ? `<span class="bubble-debug-id" data-turn-id="${turnId}" title="Kliknij aby skopiować turn id">#${turnId}</span>` : '';

        const rereadBtn = isGm ? `<button type="button" class="bubble-reread-btn" title="Przeczytaj ponownie">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
        </button>` : '';

        bubble.innerHTML = `
            <div class="chat-bubble__content">${isGm ? formatGmNarrative(msg.content || msg.text || '') : formatMessageContent(msg.content || msg.text || '')}</div>
            <div class="chat-bubble__meta">
                <span class="bubble-meta__left">${namePart}${turnPart ? ' ' + turnPart : ''}${dbIdPart}</span>
                <span class="bubble-meta__right">${routePart}${dtPart}${rereadBtn}</span>
            </div>
        `;

        // Debug id chip — click to copy turn id
        bubble.querySelector('.bubble-debug-id')?.addEventListener('click', function() {
            navigator.clipboard?.writeText(`turn_id:${this.dataset.turnId}`).then(() =>
                showToast(`Skopiowano #${this.dataset.turnId}`, 'info', 1500)
            );
        });

        if (isGm) {
            const btn = bubble.querySelector('.bubble-reread-btn');
            const rawText = msg.content || msg.text || '';
            btn?.addEventListener('click', () => {
                window.voiceUI?.speakNowFromUserGesture?.(rawText);
            });
        }
    } else {
        bubble.innerHTML = `<div class="chat-bubble__content">${formatMessageContent(msg.content || msg.text || '')}</div>`;
    }

    elements.chatMessages.appendChild(bubble);

    // Auto-speak GM narrative via TTS (skip for history replay)
    if (isGm && opts.autoSpeak !== false) {
        const rawText = msg.content || msg.text || '';
        if (rawText) window.voiceUI?.speakGMText?.(rawText);
    }

}

function formatDateTime(dateStr) {
    if (!dateStr) return '';
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return '';
        const day = String(d.getDate()).padStart(2, '0');
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const year = d.getFullYear();
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        const ss = String(d.getSeconds()).padStart(2, '0');
        return `${day}.${month}.${year}, ${hh}:${mm}:${ss}`;
    } catch (_e) { return ''; }
}

// Strip every [ALLCAPS_TAG: ...] emitted by the LLM — generics cover all current
// and future mechanic tags. Mirrors backend strip_all_mechanic_tags().
function stripMechanicTags(s) {
    return String(s || '').replace(/\s*\[[A-Z][A-Z0-9_]+:[^\]]*\]/g, '').trim();
}

function parseGmFull(text) {
    if (!text) return { narrative: '', locationIntent: null };
    let raw = String(text).trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim();
    const stripInternalTags = s => stripMechanicTags(s);
    try {
        const data = JSON.parse(raw);
        if (data && typeof data === 'object') {
            return {
                narrative: stripInternalTags(typeof data.narrative === 'string' ? data.narrative : ''),
                locationIntent: data.location_intent || null,
                raw: data,
            };
        }
    } catch (_e) {}
    return { narrative: parseGmResponse(text), locationIntent: null };
}

function parseGmResponse(text) {
    const stripExtra = s => stripMechanicTags(s);

    if (!text) return '';
    if (text === 'Walka dobiegła końca.') return text;

    // Strip __AI_GM prefix lines before parsing
    let raw = String(text).trim();
    if (raw.startsWith('__AI_GM')) {
        const lines = raw.split('\n').filter(l => !l.startsWith('__AI_GM') && !l.startsWith('{"skill"'));
        raw = lines.join('\n').trim();
    }

    // Strip markdown code fences
    const cleaned = raw
        .replace(/^```(?:json)?\s*/i, '')
        .replace(/\s*```$/i, '')
        .trim();

    // Try full JSON parse first
    try {
        const data = JSON.parse(cleaned);
        if (data && typeof data === 'object' && typeof data.narrative === 'string') {
            return stripExtra(data.narrative);
        }
    } catch (_e) { /* fallthrough */ }

    // Manual extraction of "narrative" value (handles LLM non-standard output)
    const keyIndex = cleaned.indexOf('"narrative"');
    if (keyIndex >= 0) {
        const colonIndex = cleaned.indexOf(':', keyIndex);
        const quoteIndex = colonIndex >= 0 ? cleaned.indexOf('"', colonIndex + 1) : -1;
        if (quoteIndex >= 0) {
            let out = '';
            let escaped = false;
            for (let i = quoteIndex + 1; i < cleaned.length; i++) {
                const ch = cleaned[i];
                if (escaped) {
                    if (ch === 'n') out += '\n';
                    else if (ch === 't') out += '\t';
                    else out += ch;
                    escaped = false;
                    continue;
                }
                if (ch === '\\') { escaped = true; continue; }
                if (ch === '"') {
                    const tail = cleaned.slice(i + 1).trimStart();
                    if (tail.startsWith(',') || tail.startsWith('}')) return stripExtra(out);
                }
                out += ch;
            }
        }
    }

    return stripExtra(raw);
}

function formatMessageContent(content) {
    return escapeHtml(content)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

// Issue #989 — polska konwencja dialogu. LLM (lub legacy tury) bywa wpleciony
// w cudzysłów inline: `"Coś tam" mówi nisko.` Zamieniamy taką kwestię na osobną
// linię od myślnika: `\n— Coś tam — mówi nisko.`, którą renderer pokaże jako
// akapit dialogu. Cudzysłowy bez czasownika mówienia w sąsiedztwie (cytat z
// listu/pergaminu) zostawiamy nietknięte.
const SPEECH_VERB_RE = /mów|szepc|szepn|warcz|warkn|pyta|spyta|zapyta|odpowiad|odrzek|rzek|rzuc|mrucz|mruk|woł|krzycz|krzykn|sycz|cedzi|dodaj|dodał|burk|stwierdz|wtrąc|wykrztu|chrypi|jęcz|jękn|prych|parsk|kontynu|oznajm|wyzna|szydz|kpi|prosi|błag|ostrzeg|odezw|odzyw|zaśmia|śmieje|wita|żegna|odpar|odrzu|wycedz|zaprasz|przedstaw/i;

function splitInlineDialogue(content) {
    if (!content || (content.indexOf('"') < 0 && content.indexOf('„') < 0 && content.indexOf('“') < 0)) {
        return content;
    }
    // quote (PL „…", straight "…", curly "…") + opcjonalne didaskalia do końca zdania
    const re = /(„[^”]{1,400}”|"[^"]{1,400}"|“[^”]{1,400}”)([\s,;:—–-]*)([^\n.!?]{0,90}[.!?])?/g;
    return content.replace(re, (m, quote, sep, trail, offset, str) => {
        const inner = quote.slice(1, -1).trim();
        if (!inner) return m;
        const before = str.slice(Math.max(0, offset - 60), offset);
        const trailHasVerb = trail && SPEECH_VERB_RE.test(trail);
        const beforeHasVerb = SPEECH_VERB_RE.test(before);
        if (!trailHasVerb && !beforeHasVerb) return m;   // brak czasownika mówienia → cytat/list, zostaw
        if (trailHasVerb) {
            return '\n— ' + inner + ' — ' + trail.trim();
        }
        // czasownik przed kwestią (np. „Strażnik warczy:") — didaskalia zostają w narracji nad kwestią
        return '\n— ' + inner + (sep || '') + (trail || '');
    });
}

function formatGmNarrative(content) {
    content = splitInlineDialogue(content);
    const paragraphs = content.split(/\n+/);
    return paragraphs.map(para => {
        if (!para.trim()) return '';

        // Escape HTML first
        let html = escapeHtml(para)
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>');

        // Em-dash dialog line (Polish direct speech: — Coś mówi.)
        if (/^—\s/.test(para.trim())) {
            return `<p class="gm-p gm-p--speech">${html}</p>`;
        }

        // Inline Polish quotes „..." → speech span
        html = html.replace(/„([^”]{1,300})”/g,
            '<span class="gm-speech">„$1”</span>');

        // Inline English curly quotes "..." (not escaped since we escape " → &quot; before)
        // These survived as &quot; so won't match — no action needed for straight quotes

        return `<p class="gm-p">${html}</p>`;
    }).filter(Boolean).join('');
}

// Returns true if the command was handled (do not send to turns API)
async function handleSlashCommand(text) {
    const t = text.trim();

    if (/^\/help(\s|$)/i.test(t)) {
        const lines = SLASH_COMMANDS
            .filter(c => !c.adminOnly || playerIsAdmin())
            .map(c => `\`${c.cmd}\` — ${c.desc}`)
            .join('\n');
        appendMessage({ role: 'system', content: `**Komendy:**\n${lines}`, created_at: new Date() });
        scrollToBottom();
        return true;
    }

    // Stage 8 D1 — /debug subcommands (admin only).
    if (/^\/debug(\s|$)/i.test(t)) {
        if (!playerIsAdmin()) {
            showToast('Brak uprawnień — /debug wymaga konta admina.', 'error');
            return true;
        }
        // Bare `/debug` with no subcommand → show usage in chat, don't silently dump.
        const tail = t.replace(/^\/debug\s*/i, '').trim();
        if (!tail || tail === 'help') {
            const helpLines = [
                '**🐛 /debug — komendy debugowe (admin only)**',
                '`/debug dump-state` — zrzut stanu postaci + ostatniej tury (drawer otwiera się sam)',
                '`/debug set-hp N` — ustaw HP (przycinane do [0, max_hp])',
                '`/debug set-state STATE` — wymuś state_machine (`NARRATIVE`, `COMBAT`, `SKILL_TEST_PENDING`)',
                '`/debug reset-cooldowns` — wyzeruj krótkie odpoczynki, death saves i cooldowny lochów',
                '`/debug preview-death` — 👁 podgląd ekranu śmierci (bez zmian w DB)',
                '`/debug preview-victory` — 👁 podgląd ekranu zwycięstwa (bez zmian w DB)',
                '',
                'Otwórz **🐛 drawer** (prawa-góra) aby zobaczyć szczegóły. Ustawienia → "🐛 Pokaż debug pod wiadomościami GM" musi być ON.'
            ].join('\n');
            appendMessage({ role: 'system', content: helpLines, created_at: new Date() });
            scrollToBottom();
            return true;
        }
        // Stage 9 P5/P6 preview commands — purely client-side, no DB mutation.
        // Mounts the screen with sample data so admin can verify layout/animation
        // without having to engineer a real death or victory in-game.
        if (tail === 'preview-death') {
            _previewDeathScreen();
            return true;
        }
        if (tail === 'preview-victory') {
            _previewVictoryScreen();
            return true;
        }
        if (!characterData?.id) {
            showToast('Brak aktywnego bohatera.', 'error');
            return true;
        }
        try {
            const r = await fetch('/api/debug/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ character_id: characterData.id, text: t, user_id: currentUser?.id }),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) {
                showToast(`/debug: ${data?.detail || 'błąd'}`, 'error');
                return true;
            }
            const result = data?.result || data;
            const sub = result?.sub || 'debug';
            const summary = (() => {
                if (sub === 'set-hp')          return `HP → ${result.current_hp}/${result.max_hp}${result.clamped ? ' (wartość przycięta)' : ''}`;
                if (sub === 'set-state')       return `state: ${result.previous} → ${result.state}${result.warning ? '\n⚠ ' + result.warning : ''}`;
                if (sub === 'reset-cooldowns')return 'Cooldowns wyzerowane (rest + dungeon).';
                if (sub === 'dump-state')      return `Stan zrzucony — bohater ${result.name} (id ${result.character_id}). Patrz drawer 🐛.`;
                return JSON.stringify(result).slice(0, 200);
            })();
            appendMessage({ role: 'system', content: `🐛 ${summary}`, created_at: new Date() });
            await refreshCharacterData();
            // If the drawer is open, refresh its data immediately.
            if (document.getElementById('debug-drawer')?.classList.contains('debug-drawer--open')) {
                _refreshDebugDrawer();
            }
        } catch (e) {
            showToast(`/debug: ${e.message || e}`, 'error');
        }
        return true;
    }

    // /roll [skill_key] [intent] — admin-only: seeds a pending_skill_test and shows the dice popup
    if (/^\/roll(\s|$)/i.test(t)) {
        if (!playerIsAdmin()) {
            showToast('Brak uprawnień — /roll wymaga konta admina.', 'error');
            return true;
        }
        if (!characterData?.id) {
            showToast('Brak aktywnego bohatera — wejdź do kampanii.', 'error');
            return true;
        }
        // Parse: /roll <skill_key> [intent...]
        const rollArgs = t.replace(/^\/roll\s*/i, '').trim();
        const [skillKey, ...intentParts] = rollArgs.split(/\s+/);
        const skillArg = skillKey || 'athletics';
        const intent = intentParts.join(' ').trim(); // optional free-text context

        try {
            const r = await fetch('/api/debug/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    character_id: characterData.id,
                    text: `/roll ${skillArg}`,
                    user_id: currentUser?.id,
                    intent,          // passed through for context display
                }),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) {
                showToast(`/roll: ${data?.detail || 'błąd'}`, 'error');
                return true;
            }
            // Show dice popup with the seeded pending_skill_test
            const stp = data?.skill_test_pending;
            if (stp) {
                if (intent) stp._admin_intent = intent; // attach intent for overlay subtitle
                showSkillTestPopup(stp);
            } else {
                const res = data?.result || {};
                appendMessage({ role: 'system', content: `🎲 /roll ${res.skill_label || skillArg} — DC ${res.dc}, mod ${res.modifier >= 0 ? '+' : ''}${res.modifier}`, created_at: new Date() });
            }
        } catch (e) {
            showToast(`/roll: ${e.message || e}`, 'error');
        }
        return true;
    }

    if (/^\/sheet(\s|$)/i.test(t)) {
        openSheetPanel();
        return true;
    }

    if (/^\/mem(\s|$)/i.test(t)) {
        const question = t.replace(/^\/mem\s*/i, '').trim();
        if (!question) {
            appendMessage({ role: 'system', content: 'Użyj: <code>/mem [pytanie]</code> — pytanie o przeszłość z podsumowań.', created_at: new Date() });
            scrollToBottom();
            return true;
        }
        await handleMemCommand(question, t);
        return true;
    }

    if (/^\/helpme(\s|$)/i.test(t)) {
        const topic = t.replace(/^\/helpme\s*/i, '').trim();
        await handleHelpmeCommand(topic, t);
        return true;
    }

    if (/^\/admin(\s|$)/i.test(t)) {
        await handleAdminCommand(t);
        return true;
    }

    if (/^\/czar(\s|$)/i.test(t)) {
        const spellKey = t.replace(/^\/czar\s*/i, '').trim().toLowerCase();
        if (!spellKey) {
            appendMessage({ role: 'system', content: '**Użyj:** `/czar [klucz_zaklęcia]`\nNp. `/czar mend_wounds` lub `/czar magic_light`', created_at: new Date() });
            scrollToBottom();
            return true;
        }
        await castSpellOutOfCombat(spellKey);
        return true;
    }

    return false; // let other commands pass through to turns API
}

// ============================================================================
// /admin commands — GM cheat console
// ============================================================================

const ADMIN_CMD_TREE = {
    add:    { gold: {}, health: {}, item: {}, weapon: {}, stat: {} },
    set:    { gold: {}, health: {}, level: {}, location: {} },
    remove: { item: {} },
    clear:  { inventory: {} },
    combat: { end: {} },
    quest:  { add: {}, complete: {} },
    show:   { state: {} },
};

const ADMIN_CMD_HINTS = {
    'add gold':        { hint: 'Dodaj złoto',          placeholder: '[ilość]' },
    'add health':      { hint: 'Dodaj HP',             placeholder: '[ilość lub max]' },
    'add item':        { hint: 'Dodaj przedmiot',      placeholder: '[item_key]' },
    'add weapon':      { hint: 'Dodaj broń',           placeholder: '[weapon_key]' },
    'add stat':        { hint: 'Dodaj do statystyki',  placeholder: '[STR|DEX|CON|INT|WIS|CHA] [wartość]' },
    'set gold':        { hint: 'Ustaw złoto',          placeholder: '[ilość]' },
    'set health':      { hint: 'Ustaw HP',             placeholder: '[ilość lub max]' },
    'set level':       { hint: 'Ustaw poziom',         placeholder: '[1-20]' },
    'set location':    { hint: 'Teleportuj postać',    placeholder: '[location_key]' },
    'remove item':     { hint: 'Usuń przedmiot',       placeholder: '[item_key]' },
    'clear inventory': { hint: 'Wyczyść cały plecak',  placeholder: '' },
    'combat end':      { hint: 'Zakończ aktywną walkę', placeholder: '' },
    'quest add':       { hint: 'Dodaj questa',         placeholder: '[quest_key]' },
    'quest complete':  { hint: 'Ukończ questa',        placeholder: '[quest_key]' },
    'show state':      { hint: 'Pokaż stan postaci',   placeholder: '' },
};

// Stage 8 follow-up — /debug subcommand tree for autocomplete.
// Mirrors ADMIN_CMD_TREE shape so we can reuse the same suggestion-popup plumbing.
const DEBUG_CMD_TREE = {
    'dump-state':       {},
    'set-hp':           {},
    'set-state':        { 'NARRATIVE': {}, 'COMBAT': {}, 'SKILL_TEST_PENDING': {} },
    'reset-cooldowns':  {},
    'preview-death':    {},
    'preview-victory':  {},
};
const DEBUG_CMD_HINTS = {
    'dump-state':      { hint: 'Zrzut stanu postaci + ostatniej tury (drawer)' },
    'set-hp':          { hint: 'Ustaw HP postaci', placeholder: '<N>' },
    'set-state':       { hint: 'Wymuś state_machine', placeholder: '<NARRATIVE|COMBAT|SKILL_TEST_PENDING>' },
    'set-state NARRATIVE':         { hint: 'Tryb narracyjny — domyślny stan' },
    'set-state COMBAT':            { hint: 'Tryb walki' },
    'set-state SKILL_TEST_PENDING':{ hint: 'Oczekiwanie na rzut umiejętności' },
    'reset-cooldowns': { hint: 'Wyzeruj short_rests + death_saves + cooldowny lochów' },
    'preview-death':   { hint: '👁 Podgląd ekranu śmierci (bez zmian w DB)' },
    'preview-victory': { hint: '👁 Podgląd ekranu zwycięstwa (bez zmian w DB)' },
};

// /roll [skill] [intent] autocomplete — skill list seeded from game_config_skills
// Populated at page load / first use and cached for the session.
let _rollSkillCache = null;

async function _fetchRollSkills() {
    if (_rollSkillCache) return _rollSkillCache;
    try {
        const r = await fetch('/api/mechanics/skills');
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const data = await r.json();
        const rows = data?.skills || data || [];
        _rollSkillCache = rows.map(s => ({ key: s.key || s.skill_key, label: s.label }))
            .filter(s => s.key && s.label);
    } catch (_e) {
        // Fallback: hardcoded from game_config_skills (matches DB as of stage 11)
        _rollSkillCache = [
            { key: 'acrobatics',    label: 'Akrobatyka' },
            { key: 'arcana',        label: 'Arkana' },
            { key: 'attack',        label: 'Atak' },
            { key: 'athletics',     label: 'Atletyka' },
            { key: 'two_handed',    label: 'Broń dwuręczna' },
            { key: 'investigation', label: 'Dochodzenie' },
            { key: 'initiative',    label: 'Inicjatywa' },
            { key: 'medicine',      label: 'Medycyna' },
            { key: 'deception',     label: 'Oszustwo' },
            { key: 'lockpick',      label: 'Otwieranie zamków' },
            { key: 'persuasion',    label: 'Perswazja' },
            { key: 'survival',      label: 'Przetrwanie' },
            { key: 'stealth',       label: 'Skradanie' },
            { key: 'awareness',     label: 'Spostrzegawczość' },
            { key: 'lore',          label: 'Wiedza' },
            { key: 'insight',       label: 'Wnikliwość' },
            { key: 'intimidation',  label: 'Zastraszanie' },
        ];
    }
    return _rollSkillCache;
}

let _czarSpellCache = null;

async function _fetchCzarSpells() {
    if (_czarSpellCache && _czarSpellCache._charId === characterData?.id) return _czarSpellCache;
    try {
        const token = localStorage.getItem('aigm_access_token');
        const r = await fetch(`/api/characters/${characterData.id}/spells`,
            token ? { headers: { Authorization: `Bearer ${token}` } } : {});
        const data = await r.json();
        const spells = (data?.spells || []).filter(s =>
            s.spell_type !== 'attack' && s.spell_type !== 'attack_aoe' && s.spell_type !== 'effect'
        );
        _czarSpellCache = spells;
        _czarSpellCache._charId = characterData?.id;
    } catch {
        _czarSpellCache = [];
        _czarSpellCache._charId = characterData?.id;
    }
    return _czarSpellCache;
}

function getCzarSuggestions(afterCzar, spells) {
    const typed = afterCzar.trimStart().toLowerCase();
    if (afterCzar.trimStart().includes(' ')) return [];
    const ICONS = { heal: '💚', defense: '🛡', narrative: '🕯', effect: '✨' };
    return (spells || [])
        .filter(s => !typed || s.spell_key.startsWith(typed) || (s.label || '').toLowerCase().startsWith(typed))
        .slice(0, 8)
        .map(s => ({
            cmd: `/czar ${s.spell_key}`,
            desc: `${ICONS[s.spell_type] || '✨'} ${s.label || s.spell_key}${s.mana_cost ? ` (🔮${s.mana_cost})` : ' (bezpłatne)'}`,
        }));
}

function getRollSuggestions(afterRoll, cachedSkills) {
    const parts = afterRoll.trimStart().split(/\s+/);
    const typed = (parts[0] || '').toLowerCase();
    const hasSkill = afterRoll.trimStart().includes(' ');

    // Skill already picked — hide popup so Enter submits the full command normally
    if (hasSkill) return [];

    // Still typing the skill name — filter by key or Polish label prefix
    return (cachedSkills || [])
        .filter(s => s.key.startsWith(typed) || s.label.toLowerCase().startsWith(typed))
        .slice(0, 10)
        .map(s => ({ cmd: `/roll ${s.key}`, desc: s.label }));
}

function getDebugSuggestions(afterDebug) {
    const parts = afterDebug.trimStart().split(/\s+/);
    const t0 = (parts[0] || '').toLowerCase();
    const t1 = (parts[1] || '').toUpperCase();
    const hasSpace1 = afterDebug.trimStart().includes(' ');

    // After "/debug set-state " (with trailing space or partial) → suggest STATE values
    if (hasSpace1 && DEBUG_CMD_TREE[t0] && Object.keys(DEBUG_CMD_TREE[t0]).length > 0) {
        const sub = DEBUG_CMD_TREE[t0];
        return Object.keys(sub)
            .filter(k => k.toUpperCase().startsWith(t1))
            .map(k => {
                const full = `${t0} ${k}`;
                const meta = DEBUG_CMD_HINTS[full] || {};
                return { cmd: `/debug ${full}`, desc: meta.hint || '' };
            });
    }

    // First word — list top-level subcommands matching what's typed so far.
    return Object.keys(DEBUG_CMD_TREE)
        .filter(k => k.startsWith(t0))
        .map(k => {
            const meta = DEBUG_CMD_HINTS[k] || {};
            const desc = meta.hint
                ? `${meta.hint}${meta.placeholder ? '  ' + meta.placeholder : ''}`
                : '';
            return { cmd: `/debug ${k}`, desc };
        });
}

function getAdminSuggestions(afterAdmin) {
    const parts = afterAdmin.trimStart().split(/\s+/);
    const t0 = (parts[0] || '').toLowerCase();
    const t1 = (parts[1] || '').toLowerCase();
    const hasSpace1 = afterAdmin.trimStart().includes(' ');

    if (hasSpace1 && ADMIN_CMD_TREE[t0]) {
        const sub = ADMIN_CMD_TREE[t0];
        return Object.keys(sub)
            .filter(k => k.startsWith(t1))
            .map(k => {
                const full = `${t0} ${k}`;
                const meta = ADMIN_CMD_HINTS[full] || {};
                return {
                    cmd: `/admin ${full}`,
                    desc: meta.hint ? `${meta.hint}${meta.placeholder ? '  ' + meta.placeholder : ''}` : '',
                };
            });
    }

    return Object.keys(ADMIN_CMD_TREE)
        .filter(k => k.startsWith(t0))
        .map(k => {
            const sub = ADMIN_CMD_TREE[k];
            const subKeys = Object.keys(sub);
            return {
                cmd: `/admin ${k}`,
                desc: subKeys.length ? subKeys.join(' | ') : '',
            };
        });
}

function parseAdminCommand(raw) {
    const t = (raw || '').trim().replace(/^\/admin\s*/i, '');
    const parts = t.split(/\s+/);
    if (!parts[0]) return null;
    const p0 = parts[0].toLowerCase();
    const p1 = (parts[1] || '').toLowerCase();
    const rest = parts.slice(2).join(' ');

    if (p0 === 'add' && (p1 === 'gold' || p1 === 'health')) {
        const v = rest.toLowerCase() === 'max' ? 'max' : parseInt(rest, 10);
        return { cmd: `add ${p1}`, value: Number.isNaN(v) ? rest : v };
    }
    if (p0 === 'add' && p1 === 'weapon') return { cmd: 'add item', key: rest || undefined, kind: 'weapon' };
    if (p0 === 'add' && p1 === 'consumable') return { cmd: 'add item', key: rest || undefined, kind: 'consumable' };
    if (p0 === 'add' && p1 === 'item') return { cmd: 'add item', key: rest || undefined };
    if (p0 === 'add' && p1 === 'stat') {
        const stat = (parts[2] || '').toUpperCase();
        const val = parseInt(parts[3] || '1', 10);
        return { cmd: 'add stat', stat, value: Number.isNaN(val) ? 1 : val };
    }
    if (p0 === 'set' && (p1 === 'gold' || p1 === 'health' || p1 === 'level')) {
        const v = rest.toLowerCase() === 'max' ? 'max' : parseInt(rest, 10);
        return { cmd: `set ${p1}`, value: Number.isNaN(v) ? rest : v };
    }
    if (p0 === 'set' && p1 === 'location') return { cmd: 'set location', key: rest || undefined };
    if (p0 === 'remove' && p1 === 'item') return { cmd: 'remove item', key: rest || undefined };
    if (p0 === 'clear' && p1 === 'inventory') return { cmd: 'clear inventory' };
    if (p0 === 'combat' && p1 === 'end') return { cmd: 'combat end' };
    if (p0 === 'quest' && (p1 === 'add' || p1 === 'complete')) return { cmd: `quest ${p1}`, key: rest || undefined };
    if (p0 === 'show' && p1 === 'state') return { cmd: 'show state' };
    return null;
}

async function handleAdminCommand(rawInput) {
    if (!playerIsAdmin()) {
        appendMessage({ role: 'system', content: '🛠 **Admin:** brak uprawnień (zaloguj się w panelu admina, zapisz token).', created_at: new Date() });
        scrollToBottom();
        return;
    }
    const charId = characterData?.id;
    if (!charId) {
        appendMessage({ role: 'system', content: '🛠 **Admin:** brak wybranej postaci.', created_at: new Date() });
        scrollToBottom();
        return;
    }
    const token = localStorage.getItem('aigm_admin_token');
    if (!token) {
        appendMessage({ role: 'system', content: '🛠 **Admin:** brak `aigm_admin_token` w localStorage.', created_at: new Date() });
        scrollToBottom();
        return;
    }

    const body = parseAdminCommand(rawInput);
    if (!body) {
        appendMessage({ role: 'system', content: `🛠 **Admin:** nieznana komenda — \`${rawInput}\``, created_at: new Date() });
        scrollToBottom();
        return;
    }

    try {
        const resp = await fetch(`/api/admin/cheat/${charId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify(body),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
            const detail = typeof data.detail === 'object' ? JSON.stringify(data.detail) : String(data.detail || resp.status);
            appendMessage({ role: 'system', content: `🛠 **Admin:** ❌ ${detail}`, created_at: new Date() });
        } else {
            const display = await _formatAdminResult(body, data.result || data);
            appendMessage({ role: 'system', content: `🛠 **Admin:** ✅ \`${body.cmd}\` → ${display}`, created_at: new Date() });
            await refreshCharacterData();
            if (characterData) populateCharacterSheet(characterData);
            await pollCombatState?.();
        }
    } catch (err) {
        appendMessage({ role: 'system', content: `🛠 **Admin:** ❌ ${err.message || String(err)}`, created_at: new Date() });
    }
    scrollToBottom();
}

function playerIsAdmin() {
    return !!localStorage.getItem('aigm_admin_token');
}

// Catalog cache for /admin add item|weapon autocomplete
const _ADMIN_CATALOG_CACHE = { items: { rows: null, at: 0 }, weapons: { rows: null, at: 0 } };
const _ADMIN_CATALOG_TTL_MS = 60_000;

async function _fetchAdminCatalog(kind) {
    const now = Date.now();
    const slot = _ADMIN_CATALOG_CACHE[kind];
    if (slot.rows && now - slot.at < _ADMIN_CATALOG_TTL_MS) return slot.rows;
    const token = localStorage.getItem('aigm_admin_token');
    if (!token) return [];
    try {
        const r = await fetch(`/api/admin/${kind}`, {
            headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
        });
        if (!r.ok) return [];
        const data = await r.json();
        const rows = Array.isArray(data.items) ? data.items : [];
        slot.rows = rows;
        slot.at = now;
        return rows;
    } catch (_e) {
        return [];
    }
}

function _adminCatalogContext(afterAdmin) {
    // Returns {kind, query} when typing "/admin add item|weapon <query>"
    const m = afterAdmin.trimStart().match(/^add\s+(item|weapon)\s*(.*)$/i);
    if (!m) return null;
    return { kind: m[1].toLowerCase() === 'item' ? 'items' : 'weapons', query: (m[2] || '').trim() };
}

async function _resolveCatalogLabel(key) {
    if (!key) return null;
    const k = String(key).trim();
    // Try items, then weapons
    for (const kind of ['items', 'weapons']) {
        const rows = await _fetchAdminCatalog(kind);
        const hit = rows.find(r => String(r.key) === k);
        if (hit?.label) return String(hit.label);
    }
    return null;
}

async function _formatAdminResult(body, result) {
    if (!result || typeof result !== 'object') return String(result ?? '');
    const cmd = body.cmd;

    // add item / add weapon → resolve key to label (label only, no raw key)
    if (cmd === 'add item') {
        const key = result.added || body.key;
        const label = await _resolveCatalogLabel(key);
        return label ? `**${label}**` : `\`${key}\``;
    }
    if (cmd === 'remove item') {
        const key = result.removed || body.key;
        const label = await _resolveCatalogLabel(key);
        return label ? `**${label}**` : `\`${key}\``;
    }
    if (cmd === 'add gold' || cmd === 'set gold') {
        return `${result.gold_gp ?? '?'} GP`;
    }
    if (cmd === 'add health' || cmd === 'set health') {
        const hp = result.current_hp ?? result.hp ?? '?';
        const max = result.max_hp ? `/${result.max_hp}` : '';
        return `${hp}${max} HP`;
    }
    if (cmd === 'set level') return `Poziom ${result.level ?? '?'}`;
    if (cmd === 'set location') return `📍 ${result.location || body.key || '?'}`;
    if (cmd === 'clear inventory') return `wyczyszczono (${result.removed_count ?? '?'} przedmiotów)`;
    if (cmd === 'combat end') return 'walka zakończona';

    // Default: compact JSON
    return JSON.stringify(result, null, 0);
}

async function fetchAdminCatalogSuggestions(afterAdmin) {
    const ctx = _adminCatalogContext(afterAdmin);
    if (!ctx) return null;
    const rows = await _fetchAdminCatalog(ctx.kind);
    const q = ctx.query.toLowerCase();
    const filtered = rows
        .filter(row => {
            const active = row.is_active !== false && row.is_active !== 0;
            if (!active) return false;
            if (!q) return true;
            const label = String(row.label ?? '').toLowerCase();
            const key = String(row.key ?? '').toLowerCase();
            return label.includes(q) || key.includes(q);
        })
        .sort((a, b) =>
            String(a.label || a.key || '').localeCompare(String(b.label || b.key || ''),
                undefined, { sensitivity: 'base' })
        )
        .slice(0, 40);

    const branch = ctx.kind === 'items' ? 'item' : 'weapon';
    return filtered.map(row => {
        const key = String(row.key ?? '').trim();
        const label = String(row.label ?? key).trim();
        return { cmd: `/admin add ${branch} ${key}`, desc: `${label}` };
    });
}

async function handleMemCommand(question, fullText) {
    if (!characterData?.id || !currentUser?.id) return;
    appendMessage({ role: 'user', content: fullText, created_at: new Date() });
    const typing = showTypingIndicator();
    try {
        const url = `/campaigns/${currentCampaignId}/memory/ask?user_id=${currentUser.id}`;
        const resp = await apiRequest('POST', url, {
            character_id: characterData.id,
            question,
            user_line: fullText,
        });
        typing.remove();
        const answer = resp.answer || '';
        if (answer) {
            appendMessage({ role: 'assistant', content: answer, created_at: resp.created_at || new Date(), turn_number: resp.turn_number, route: 'memory' });
        }
    } catch (e) {
        typing.remove();
        // Stage 9 P3 — pretty-print the historia cooldown 429 response.
        const detail = e?.body?.detail;
        if (detail && typeof detail === 'object' && detail.error === 'historia_cooldown') {
            appendMessage({
                role: 'system',
                content: `🕯 ${detail.message}`,
                created_at: new Date(),
            });
        } else {
            showToast(e.message || 'Błąd /mem', 'error');
        }
    }
    scrollToBottom();
}

async function handleHelpmeCommand(topic, fullText) {
    if (!characterData?.id || !currentUser?.id) return;
    appendMessage({ role: 'user', content: fullText, created_at: new Date() });
    const typing = showTypingIndicator();
    try {
        const url = `/campaigns/${currentCampaignId}/helpme?user_id=${currentUser.id}`;
        const resp = await apiRequest('POST', url, {
            character_id: characterData.id,
            topic: topic || '',
            user_line: fullText,
        });
        typing.remove();
        const answer = resp.answer || '';
        if (answer) {
            appendMessage({ role: 'assistant', content: answer, created_at: resp.created_at || new Date(), turn_number: resp.turn_number, route: 'helpme' });
        }
    } catch (e) {
        typing.remove();
        showToast(e.message || 'Błąd /helpme', 'error');
    }
    scrollToBottom();
}

// T33: Render suggested action buttons
function renderSuggestedActions(actions) {
    const container = document.getElementById('suggested-actions');
    if (!container) return;
    container.innerHTML = '';
    if (!actions || !actions.length) {
        container.style.display = 'none';
        return;
    }
    container.style.display = 'flex';
    actions.forEach((a, i) => {
        const btn = document.createElement('button');
        let cls = 'suggested-action-btn' + (a.enabled ? '' : ' disabled');
        if (a.type === 'travel') cls += ' suggested-action-btn--travel';
        btn.className = cls;
        btn.style.setProperty('--i', i);
        btn.textContent = (a.icon ? a.icon + ' ' : '') + a.label;
        if (!a.enabled) {
            btn.disabled = true;
            btn.title = a.reason || '';
        } else {
            btn.addEventListener('click', () => sendStructuredAction(a.action, a.label));
        }
        container.appendChild(btn);
    });
}

// #780: bramka intencji po zdobyciu przewagi (Stealth/grapple/ogłuszenie).
// Renderuje 3 przyciski (Atak z zaskoczenia / Zastraszenie / Wycofaj). Każda opcja
// to gotowy tekst tury gracza — silnik decyduje co dalej (walka vs test Zastraszenia).
function renderAdvantageGate(gate) {
    if (!gate || !Array.isArray(gate.options) || !gate.options.length) return;
    const wrap = document.createElement('div');
    wrap.className = 'advantage-gate-card';
    const title = document.createElement('div');
    title.className = 'advantage-gate-title';
    title.textContent = '✅ ' + (gate.title || 'Masz przewagę.');
    wrap.appendChild(title);
    const row = document.createElement('div');
    row.className = 'advantage-gate-options';
    gate.options.forEach((opt, i) => {
        const btn = document.createElement('button');
        btn.className = 'advantage-gate-btn advantage-gate-btn--' + (opt.id || 'x');
        btn.style.setProperty('--i', i);
        btn.innerHTML = `<span class="ag-label">${(opt.icon ? opt.icon + ' ' : '') + (opt.label || '')}</span>` +
                        (opt.hint ? `<span class="ag-hint">${opt.hint}</span>` : '');
        btn.addEventListener('click', () => {
            wrap.remove();
            sendTurn(opt.action, 'free_text', opt.label);
        });
        row.appendChild(btn);
    });
    wrap.appendChild(row);
    if (elements.chatMessages) {
        elements.chatMessages.appendChild(wrap);
        wrap.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

// U32: Show/hide anti-stuck travel banner (level 0=hidden, 1=pills only, 2=banner)
let _travelEscalationLevel = 0;
function renderTravelEscalation(level) {
    _travelEscalationLevel = level || 0;
    const banner = document.getElementById('travel-stuck-banner');
    if (!banner) return;
    if (_travelEscalationLevel >= 2) {
        banner.innerHTML = `
          <span class="travel-stuck-banner__text">🗺 Świat czeka — może czas ruszyć w drogę?</span>
          <button type="button" class="travel-stuck-banner__dismiss" title="Zamknij" onclick="this.closest('#travel-stuck-banner').hidden=true">✕</button>`;
        banner.hidden = false;
    } else {
        banner.hidden = true;
    }
}

// C10: Render quest chips in the header quest bar
function renderQuestBar(quests) {
    const bar = document.getElementById('quest-bar');
    if (bar) {
        if (!quests || !quests.length) {
            bar.hidden = true;
        } else {
            bar.hidden = false;
            bar.innerHTML = quests.map(q =>
                `<span class="quest-chip" title="${escapeHtml(q.objective||'')} | ${escapeHtml(q.reward||'')}">📜 ${escapeHtml(q.title)}</span>`
            ).join('');
        }
    }
    // Render full quest cards in sheet panel stats tab
    const section = document.getElementById('sheet-quests-section');
    const list = document.getElementById('sheet-quests-list');
    if (section && list) {
        if (!quests || !quests.length) {
            section.style.display = 'none';
        } else {
            section.style.display = '';
            list.innerHTML = quests.map(q => `
                <div class="quest-card">
                    <div class="quest-card__title">📜 ${escapeHtml(q.title)}</div>
                    ${q.objective ? `<div class="quest-card__objective">${escapeHtml(q.objective)}</div>` : ''}
                    ${q.reward ? `<div class="quest-card__reward">Nagroda: ${escapeHtml(q.reward)}</div>` : ''}
                </div>`).join('');
        }
    }
}

// T33: Send a structured action (button click)
async function sendStructuredAction(actionStr, displayLabel) {
    const input = elements.chatInput;
    if (input) input.value = '';
    hideCharCounter();

    // Stage 2B R4: BUILD_CAMP goes through a dedicated endpoint, not the narrator.
    if (actionStr === 'BUILD_CAMP') {
        await handleBuildCamp();
        return;
    }

    // REST:long opens the long-rest modal (which calls /rest API for HP restore).
    if (actionStr === 'REST:long') {
        const sheet = characterData?.sheet_json || {};
        openLongRestModal(characterData, sheet);
        return;
    }

    // U32: TRAVEL:q:r — mechanical hex travel from pill button (POST /travel, same as map click)
    if (actionStr.startsWith('TRAVEL:')) {
        const parts = actionStr.split(':');
        if (parts.length === 3) {
            const tq = parseInt(parts[1], 10);
            const tr = parseInt(parts[2], 10);
            if (!isNaN(tq) && !isNaN(tr)) {
                await _executeTravelFromPill(tq, tr, displayLabel);
                return;
            }
        }
    }

    await sendTurn(actionStr, 'structured', displayLabel);
}

// U32: Execute hex travel from a travel pill button (mirrors _wmExecuteTravel but no map modal)
async function _executeTravelFromPill(q, r, label) {
    if (!currentCampaignId || !characterData?.id) return;
    renderSuggestedActions([]);
    renderTravelEscalation(0);
    try {
        const response = await apiRequest('POST', `/campaigns/${currentCampaignId}/travel`, {
            character_id: characterData.id,
            target_hex: { q, r },
        });

        if (response.clock) renderClock(response.clock);

        const hours = response.total_hours || 0;
        const arrivedData = response.hex_data || {};
        const hexTypeName = (_wmap.hexTypes?.[arrivedData.hex_type]?.label) || arrivedData.hex_type || '';
        const rawLabel = label && !label.match(/^[→📜]\s*\([-\d]+,[-\d]+\)$/) ? label.replace(/^[→📜\s]+/, '').replace(/\s*\(\d+h\)$/, '').trim() : null;
        const destLabel = rawLabel || arrivedData.label || null;

        const cinTip = await _pickTravelTip(response);  // #665
        await _showTravelCinematic({
            hexType: arrivedData.hex_type,
            destLabel: destLabel || hexTypeName || null,
            atmo: arrivedData.atmosphere,
            tip: cinTip,
        });

        let prose;
        if (hours > 0) {
            const hStr = Number.isInteger(hours) ? `${hours}` : hours.toFixed(1);
            const hWord = hours === 1 ? 'godzinę' : (hours < 5 ? 'godziny' : 'godzin');
            prose = destLabel
                ? `Dotarłeś do **${destLabel}**. Droga zajęła ${hStr} ${hWord}.`
                : `Dotarłeś do celu. Droga zajęła ${hStr} ${hWord}.`;
        } else {
            prose = `Przenosisz się${destLabel ? ` do ${escapeHtml(destLabel)}` : ''}.`;
        }
        appendMessage({ role: 'assistant', content: prose, created_at: new Date() });
        scrollToBottom();

        const enc = response.encounter;
        if (enc && enc.enemy_key) {
            appendMessage({
                role: 'system',
                content: `⚔️ Napotkałeś wroga na szlaku: **${enc.enemy_label || enc.enemy_key}**!`,
                created_at: new Date(),
            });
        }

        // Refresh character + map
        await refreshCharacterData();
        if (typeof updateWorldMap === 'function') updateWorldMap();
    } catch (e) {
        showToast(`Błąd podróży: ${e.message || e}`, 'error');
    }
}

// Stage 2B R4: client-side handler for the "Rozbij obóz" suggested action.
async function handleBuildCamp() {
    if (!currentCampaignId) {
        showToast('Brak aktywnej kampanii.', 'error');
        return;
    }
    renderSuggestedActions([]);
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/build-camp`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
            const msg = data?.detail || `HTTP ${r.status}`;
            showToast(msg, 'error');
            renderSuggestedActions(_suggestedActions);
            return;
        }
        const clockStr = data?.current_clock?.display ? ` Zegar: ${data.current_clock.display}.` : '';
        appendMessage({
            role: 'system',
            content: `🔥 Rozbijasz tymczasowy obóz. Możesz tu teraz odpocząć, ale ogień przyciągnie uwagę.${clockStr}`,
            created_at: new Date(),
        });
        scrollToBottom();
        // Patch local suggested actions: drop BUILD_CAMP, enable REST.
        _suggestedActions = (_suggestedActions || [])
            .filter(a => a.action !== 'BUILD_CAMP')
            .map(a => (a.action === 'REST:long' ? { ...a, enabled: true, reason: null } : a));
        renderSuggestedActions(_suggestedActions);
    } catch (e) {
        showToast(`Błąd: ${e.message || e}`, 'error');
        renderSuggestedActions(_suggestedActions);
    }
}

// T33: Update input placeholder based on game/combat state
function updateInputPlaceholder() {
    const input = elements.chatInput;
    if (!input) return;
    if (combatActive) {
        input.placeholder = 'Twoja akcja... (lub użyj przycisków powyżej)';
    } else {
        input.placeholder = 'Co robisz? Możesz pisać swobodnie...';
    }
}

// T33: Character counter
function updateCharCounter() {
    const input = elements.chatInput;
    const counter = document.getElementById('char-counter');
    if (!input || !counter) return;
    const len = input.value.length;
    if (len > 400) {
        counter.textContent = `${len}/500`;
        counter.style.display = 'block';
    } else {
        counter.style.display = 'none';
    }
}

function hideCharCounter() {
    const counter = document.getElementById('char-counter');
    if (counter) counter.style.display = 'none';
}

// T33: Core send function used by both free text and structured actions
async function sendTurn(text, inputType = 'free_text', displayLabel = null) {
    if (!characterData?.id) {
        showToast('Brak postaci - odśwież stronę', 'error');
        return;
    }

    // Stop any in-flight TTS immediately — every player action interrupts reading.
    try { window.voiceUI?.stopPlayback?.(); } catch (_e) {}
    window.voiceUI?.unlockAudio?.();

    elements.btnSend.disabled = true;
    renderSuggestedActions([]);

    const displayText = displayLabel || text;
    appendMessage({ role: 'user', content: displayText, created_at: new Date() });
    scrollToBottom();

    const typingIndicator = showTypingIndicator();
    let _skillTestPending = false;

    try {
        const result = await _sendTurnStream(text, inputType, typingIndicator);

        if (result.skill_test_pending) {
            _skillTestPending = true;
            showSkillTestPopup(result.skill_test_pending);
            scrollToBottom();
            return;
        }

        _suggestedActions = result.suggested_actions || _suggestedActions || [];
        renderSuggestedActions(_suggestedActions);
        renderTravelEscalation(result.travel_escalation_level || 0);
        if (result.active_quests) renderQuestBar(result.active_quests);

        await refreshCharacterData();
        await refreshEquippedDurability();  // U16: świeży stan trwałości dla HUD walki
        await pollCombatState();
        updateInputPlaceholder();

        // U16 (#564): NPC-handlarz w narracji → otwórz interaktywny sklep
        if (result.open_shop && result.open_shop.npc_key) {
            openShopModal(result.open_shop.npc_key);
        }

        // E25: show onboarding cards for first-time mechanic triggers
        if (result.onboarding_cards && result.onboarding_cards.length > 0) {
            showOnboardingCards(result.onboarding_cards);
        }

        // L20b (#724): NPC portrait modal on [NPC_INTERACTION] tag
        if (result.npc_interaction && result.npc_interaction.image_url) {
            showEnemyPortraitModal([result.npc_interaction]).catch(() => {});
        }

        // T38 (#1009): campaign reached its victory condition this turn —
        // auto-raise the victory overlay (previously only via /debug preview-victory).
        if (result.campaign_ended) {
            showVictoryScreen().catch(() => {});
        }

        // #1086: beat/quest completion notifications
        if (result.completed_beats?.length || result.completed_quests?.length) {
            renderCompletionNotifications(result.completed_beats, result.completed_quests);
        }
    } catch (error) {
        typingIndicator.remove();
        renderSuggestedActions(_suggestedActions);
        console.error('Send message error:', error);
        showToast(error.message || 'Nie udało się wysłać wiadomości', 'error');
    } finally {
        if (!_skillTestPending) elements.btnSend.disabled = false;
        scrollToBottom();
    }
}

// Extract just the narrative text from a partially-received JSON response.
// The LLM wraps its output in {"narrative":"...","location_intent":...}
// During streaming we receive this incrementally — strip the JSON prefix/suffix
// so the player only sees clean prose while tokens arrive.
function _extractStreamingNarrative(raw) {
    // Try: once we have at least {"narrative": " we can strip the prefix
    const m = raw.match(/^\{"narrative"\s*:\s*"([\s\S]*)/);
    if (m) {
        // Cut at the first unescaped closing quote to avoid leaking trailing
        // JSON fields (grant_item, location_intent, etc.) into the live bubble.
        let body = m[1];
        let end = -1;
        for (let i = 0; i < body.length; i++) {
            if (body[i] === '"' && body[i - 1] !== '\\') { end = i; break; }
        }
        if (end >= 0) body = body.substring(0, end);
        const text = body.replace(/\\"/g, '"').replace(/\\n/g, '\n').replace(/\\t/g, '\t');
        return stripMechanicTags(text);
    }
    // Not yet past the JSON prefix — hide it (show nothing until narrative starts)
    if (raw.startsWith('{') && !raw.includes('"narrative"')) return '';
    return stripMechanicTags(raw);
}

// Streaming implementation — returns {skill_test_pending, suggested_actions} on completion
async function _sendTurnStream(text, inputType, typingIndicator) {
    const headers = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('aigm_access_token');
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const _skipNarr = inputType === 'combat_roll' && localStorage.getItem('aigm_skip_combat_narrative') === '1';
    const resp = await fetch(`/api/campaigns/${currentCampaignId}/turns/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ text, character_id: characterData.id, input_type: inputType, skip_narrative: _skipNarr }),
    });

    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    let streamBubble = null;        // the live GM bubble element
    let contentEl = null;           // its .chat-bubble__content div
    let rawTokens = '';             // accumulated raw LLM text
    let firstToken = true;
    const result = {};

    // Parse SSE line-by-line
    const processLine = (line) => {
        if (!line.startsWith('data: ')) return;
        const payload = line.slice(6);

        if (payload.startsWith('[ERROR]')) {
            throw new Error(payload.slice(7).trim() || 'Streaming error');
        }

        if (payload.startsWith('[DONE]')) {
            const meta = payload.length > 6 ? JSON.parse(payload.slice(6)) : {};
            if (meta.skill_test_pending)       result.skill_test_pending       = meta.skill_test_pending;
            if (meta.campaign_ended)           result.campaign_ended           = true; // T38 (#1009)
            if (meta.current_location)         result.current_location         = meta.current_location;
            if (meta.suggested_actions)        result.suggested_actions        = meta.suggested_actions;
            if (meta.active_quests)            result.active_quests            = meta.active_quests;
            if (meta.travel_escalation_level != null) result.travel_escalation_level = meta.travel_escalation_level;
            if (meta.clock)              renderClock(meta.clock);
            if (meta.onboarding_cards)   result.onboarding_cards   = meta.onboarding_cards;
            if (meta.narrative_append)   result.narrative_append   = meta.narrative_append;
            if (meta.completed_beats)    result.completed_beats    = meta.completed_beats;
            if (meta.completed_quests)   result.completed_quests   = meta.completed_quests;
            // U30: sync map pin after each narrative turn (text movement updates current_hex).
            // If the hex changed AND the panel is open, re-fetch the map so the newly
            // discovered destination hex (not in the stale client cache) renders live —
            // otherwise the pin would have no tile until a full page reload.
            if (meta.current_hex) {
                const prev = _wmap.currentHex;
                const changed = !prev || prev.q !== meta.current_hex.q || prev.r !== meta.current_hex.r;
                _wmap.currentHex = meta.current_hex;
                if (changed && _wmap.panel && !_wmap.panel.hasAttribute('hidden')) {
                    _wmRefresh(false).catch(() => _wmRender());
                }
            }
            return;
        }

        if (payload.startsWith('[COMBAT_STARTED]')) {
            result.combat_started = JSON.parse(payload.slice(16));
            return;
        }
        if (payload.startsWith('[COMBAT]')) {
            result.combat = JSON.parse(payload.slice(8));
            return;
        }
        if (payload.startsWith('[COMBAT_ENDED]')) {
            result.combat_ended = JSON.parse(payload.slice(14));
            return;
        }
        if (payload.startsWith('[GM_ROLL]')) {
            result.gm_roll = JSON.parse(payload.slice(9));
            return;
        }
        if (payload.startsWith('[OPEN_SHOP]')) {
            result.open_shop = JSON.parse(payload.slice(11));
            return;
        }
        // L20b (#724): NPC portrait on interaction (dead hook before L20b)
        if (payload.startsWith('[NPC_INTERACTION]')) {
            result.npc_interaction = JSON.parse(payload.slice(17));
            return;
        }

        // Raw narrative token
        const token = payload.replace(/\\n/g, '\n');
        rawTokens += token;

        if (firstToken) {
            firstToken = false;
            typingIndicator.remove();

            // Create the streaming GM bubble
            streamBubble = document.createElement('div');
            streamBubble.className = 'chat-bubble chat-bubble--gm chat-bubble--streaming';
            contentEl = document.createElement('div');
            contentEl.className = 'chat-bubble__content';
            streamBubble.appendChild(contentEl);
            elements.chatMessages.appendChild(streamBubble);
        }

        // Display cleaned text with cursor. The response is JSON-wrapped
        // ({narrative: "..."}), so extract just the narrative value while streaming
        // to avoid showing raw JSON syntax to the player.
        if (contentEl) {
            const display = _extractStreamingNarrative(rawTokens);
            contentEl.textContent = display + '▌';
            scrollToBottom();
        }
    };

    // Read the SSE stream — yield to the browser every 6 lines so intermediate
    // token batches can paint before the next chunk arrives.
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (let i = 0; i < lines.length; i++) {
            processLine(lines[i].trim());
            if (i > 0 && i % 6 === 0) {
                // Yield back to the event loop so the browser can paint the current tokens
                await new Promise(r => setTimeout(r, 0));
            }
        }
    }
    if (buf.trim()) processLine(buf.trim());

    // Finalize streaming bubble — apply full GM formatting
    if (streamBubble && contentEl && rawTokens) {
        let { narrative: gmContent } = parseGmFull(rawTokens);
        // U6 (#530): server-side correction computed after stream (e.g. rejected grant_item)
        if (result.narrative_append) {
            gmContent = (gmContent || '').replace(/\s+$/, '') + '\n\n' + result.narrative_append;
        }
        streamBubble.classList.remove('chat-bubble--streaming');
        // Replace textContent with formatted HTML + meta footer
        const name    = 'MG — Mistrz Gry';
        const dt      = formatDateTime(new Date());
        const rereadBtn = `<button type="button" class="bubble-reread-btn" title="Przeczytaj ponownie">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
        </button>`;
        streamBubble.innerHTML = `
            <div class="chat-bubble__content">${formatGmNarrative(gmContent)}</div>
            <div class="chat-bubble__meta">
                <span class="bubble-meta__left"><span class="bubble-meta__name">${escapeHtml(name)}</span></span>
                <span class="bubble-meta__right"><span class="bubble-meta__datetime">${escapeHtml(dt)}</span>${rereadBtn}</span>
            </div>`;
        streamBubble.querySelector('.bubble-reread-btn')?.addEventListener('click', () => {
            window.voiceUI?.speakNowFromUserGesture?.(gmContent);
        });
        // TTS — speak the full text once streaming is done
        if (gmContent) window.voiceUI?.speakGMText?.(gmContent);

    } else if (firstToken) {
        // No tokens at all — remove typing indicator if still present
        typingIndicator.remove();
    }

    return result;
}

async function handleSendMessage() {
    const content = elements.chatInput.value.trim();
    if (!content) return;

    // MP mode: delegate before clearing input — handleSubmit reads + clears input internally
    if (window.multiplayerUI?.isActive?.()) {
        await window.multiplayerUI.handleSubmit();
        return;
    }

    elements.chatInput.value = '';
    hideCharCounter();

    if (content.startsWith('/')) {
        const handled = await handleSlashCommand(content);
        if (handled) return;
    }

    await sendTurn(content, 'free_text');
}

// ── Skill Test Roll Popup — dice.js 3D physics (issue #65) ──────────────────

// Singleton dice box — created once and reused so Three.js/Cannon don't re-init
let _diceBox = null;

// Stored so the ✕ dismiss button (static HTML onclick) can call it
window._currentDicePending = null;

window.dismissDiceRoll = async function() {
    const overlay = document.getElementById('dice-overlay');
    if (overlay) overlay.hidden = true;
    const pending = window._currentDicePending;
    window._currentDicePending = null;
    if (pending?.skill_test_id) {
        try {
            // Resolve with committed value — clears server state so reload is clean
            await resolveSkillTest(pending.skill_test_id, pending.committed_d20 ?? 10, null);
        } catch (_e) {
            // Resolve failed — navigate to campaigns directly so player isn't stuck
        }
    }
    // Go back to campaign chooser
    currentCampaignId = null;
    currentCampaign = null;
    characterData = null;
    await loadCampaigns();
    showScreen('campaigns');
};

function showSkillTestPopup(pending) {
    // Stop TTS immediately
    try { window.voiceUI?.stopPlayback?.(); } catch (_e) {}

    const mod   = pending.modifier_breakdown || {};
    const total = mod.total || 0;
    const sign  = total >= 0 ? '+' : '';
    const name  = (pending.skill_label || pending.skill_key || 'Umiejętność').toUpperCase();
    const intent = pending._admin_intent || '';
    const committedD20 = (typeof pending.committed_d20 === 'number')
        ? Math.max(1, Math.min(20, parseInt(pending.committed_d20, 10)))
        : null;

    window._currentDicePending = pending;

    const overlay    = document.getElementById('dice-overlay');
    const container  = document.getElementById('dice-container');
    const skillCard  = document.getElementById('dice-skill-card');
    const resultCard = document.getElementById('dice-result-card');
    const resultSkill  = document.getElementById('dice-result-skill');
    const resultIntent = document.getElementById('dice-result-intent');
    const resultNum  = document.getElementById('dice-result-num');
    const resultTot  = document.getElementById('dice-result-total');
    const resultVerd = document.getElementById('dice-result-verdict');
    const stakeBanner = document.getElementById('dice-stake-banner');

    // SF6 (#635) — hazard: pokaż stawkę „Ryzykujesz X zł" przez cały rzut (czyta payload).
    if (stakeBanner) {
        const stakeLbl = sf6StakeLabel(pending);
        stakeBanner.textContent = stakeLbl || '';
        stakeBanner.hidden = !stakeLbl;
    }

    // Pre-populate result card header (shown after roll)
    if (resultSkill)  resultSkill.textContent  = name;
    if (resultIntent) { resultIntent.textContent = intent; resultIntent.hidden = !intent; }

    // SF8 (#637) — rozbicie po nazwanym źródle (polskie nazwy stata, kolory składników).
    const modParts = sf8SkillBreakdown(mod);
    const modHtml = sf8BreakdownHtml(modParts);
    if (resultTot) resultTot.innerHTML = (modHtml ? modHtml + ' · ' : '') + `Bonus ${sign}${total}`;

    resultNum.textContent  = '';
    resultNum.className    = '';
    resultVerd.textContent = '';
    resultVerd.className   = '';
    resultCard.hidden = true;

    // Hide the pre-roll skill card — no button, roll is automatic
    if (skillCard) skillCard.hidden = true;

    // Show overlay — container gets real dimensions after this
    overlay.hidden = false;

    // Helper to show result and schedule auto-close
    function _showResult(rolled) {
        const sum   = rolled + total;
        const nat20 = rolled === 20;
        const nat1  = rolled === 1;

        resultNum.textContent = rolled;
        resultNum.className   = nat20 ? 'nat20' : nat1 ? 'nat1' : '';

        // Overwrite the mod line with the final sum (SF8 — z rozbiciem + kolorami)
        if (resultTot) resultTot.innerHTML =
            `🎲 ${rolled} ` + (modHtml ? modHtml : '') + `  =  <strong>${sum}</strong>`;

        if (nat20) {
            resultVerd.textContent = '✦ Krytyczny sukces!';
            resultVerd.className   = 'nat20';
        } else if (nat1) {
            resultVerd.textContent = '✧ Krytyczna porażka';
            resultVerd.className   = 'nat1';
        } else {
            const dc = pending.dc || 12;
            resultVerd.textContent = sum >= dc ? 'Sukces' : 'Porażka';
            resultVerd.className   = sum >= dc ? 'success' : 'failure';
        }
        resultCard.hidden = false;

        // Close after 5.5 s, or immediately on tap/click anywhere on the overlay
        let _closed = false;
        async function _closeResult() {
            if (_closed) return;
            _closed = true;
            overlay.removeEventListener('click', _closeResult);
            overlay.hidden = true;
            if (skillCard) skillCard.hidden = false;
            if (stakeBanner) stakeBanner.hidden = true; // SF6 — sprzątnij baner stawki
            await resolveSkillTest(pending.skill_test_id, rolled, null);
        }
        setTimeout(_closeResult, 5500);
        overlay.addEventListener('click', _closeResult, { once: true });
    }

    // One frame later — container dimensions are non-zero
    requestAnimationFrame(() => {
        // Fallback: if DICE library didn't load, animate the number in the roll btn
        if (typeof DICE === 'undefined' || typeof DICE.dice_box !== 'function') {
            _showSimpleFallbackRoll(pending, _showResult);
            return;
        }

        try {
            if (!_diceBox) {
                _diceBox = new DICE.dice_box(container);
            } else {
                _diceBox.clear();
                _diceBox.reinit(container);
            }
            _diceBox.setDice('1d20');
        } catch (_err) {
            _showSimpleFallbackRoll(pending, _showResult);
            return;
        }

        // Auto-start — no button click needed
        const beforeRoll = committedD20 !== null ? () => [committedD20] : null;
        _diceBox.start_throw(beforeRoll, (notation) => {
            // Brief settle pause before revealing result card
            setTimeout(() => _showResult(notation.result[0]), 600);
        });
    });
}

// Lightweight number-spinning fallback when dice.js/Three.js fail to load
function _showSimpleFallbackRoll(pending, onResult) {
    const committedD20 = (typeof pending.committed_d20 === 'number')
        ? Math.max(1, Math.min(20, parseInt(pending.committed_d20, 10)))
        : null;
    // Show result card immediately so spinning number is visible
    const resultCard = document.getElementById('dice-result-card');
    const spinEl     = document.getElementById('dice-result-num');
    if (resultCard) resultCard.hidden = false;
    let ticks = 0;
    const iv = setInterval(() => {
        if (spinEl) spinEl.textContent = Math.ceil(Math.random() * 20);
        if (++ticks >= 18) {
            clearInterval(iv);
            const rolled = committedD20 !== null ? committedD20 : Math.ceil(Math.random() * 20);
            onResult(rolled);
        }
    }, 60);
}

async function resolveSkillTest(skillTestId, d20Roll, popupEl) {
    try {
        const response = await apiRequest('POST', `/campaigns/${currentCampaignId}/skill-test/resolve`, {
            character_id: characterData.id,
            skill_test_id: skillTestId,
            d20_roll: d20Roll,
        });

        popupEl?.remove();

        // Show the roll result as a user message in chat history
        const sr = response.skill_test_result || {};
        let rollBubbleEl = null;
        if (sr.skill_label || sr.skill_key) {
            const skillName = sr.skill_label || sr.skill_key || 'Test';
            // S1 (#581) — 4 stopnie wg marginesu; nat 20/1 mają pierwszeństwo.
            const margin = (typeof sr.margin === 'number')
                ? sr.margin
                : (sr.player_total - sr.opponent_total);
            const marginStr = (margin >= 0 ? '+' : '') + margin;
            // SF6 (#635) — słowny stopień marginesu (krytyki zostają czyste, są samowyjaśniające).
            const _deg = sf6MarginDegree(margin);
            const _degStr = _deg ? ` (${_deg})` : '';
            let outcome;
            if (sr.outcome === 'CRITICAL_SUCCESS' || sr.nat20) outcome = ` — Krytyczny sukces ${marginStr}`;
            else if (sr.outcome === 'CRITICAL_FAILURE' || sr.nat1) outcome = ` — Krytyczna porażka ${marginStr}`;
            else if (sr.outcome === 'SUCCESS' || sr.success) outcome = ` — Sukces ${marginStr}${_degStr}`;
            else outcome = ` — Porażka ${marginStr}${_degStr}`;
            const rollLine = `🎲 ${skillName}: ${sr.d20_roll} +${sr.modifier} = ${sr.player_total}${outcome}`;
            appendMessage({ role: 'user', content: rollLine, created_at: new Date() });
            // Keep reference to roll bubble so we can scroll to it (not the very bottom)
            rollBubbleEl = elements.chatMessages.lastElementChild;
        }
        // Crit flash (T34) — skill-test path
        if (sr.nat20) triggerCritFlash('crit');
        else if (sr.nat1) triggerCritFlash('fumble');
        // SF5 (#634) — zły omen (S11) zepsuł rzut → ulotny komunikat w logu.
        if (sr.omen_applied) flashCombatEvent('omen');

        if (response.prose) {
            const { narrative: gmContent } = parseGmFull(response.prose);
            appendMessage({
                role: 'assistant',
                content: gmContent,
                created_at: new Date(),
                turn_number: response.turn_number,
            });
        }

        // S11 (#606) — inspired: nieudany test → przycisk przerzutu (keep-best).
        if (sr.reroll_available && !sr.rerolled) {
            _renderInspiredRerollButton(skillTestId, sr.reroll_available);
        }

        // #780 — bramka intencji po sukcesie Stealth (przewaga): Atak/Zastraszenie/Wycofaj.
        if (response.advantage_gate) {
            renderAdvantageGate(response.advantage_gate);
        }

        // Update HP if trap dealt damage
        await refreshCharacterData();
        await pollCombatState();
        // Scroll to the roll bubble (not the very bottom) so the triggering action is visible above
        if (rollBubbleEl) {
            rollBubbleEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } else {
            scrollToBottom();
        }

        // Re-enable input + restore suggested actions
        if (elements.btnSend) elements.btnSend.disabled = false;
        if (response.suggested_actions) {
            _suggestedActions = response.suggested_actions;
            renderSuggestedActions(_suggestedActions);
        }
        renderTravelEscalation(response.travel_escalation_level || 0);
        if (response.active_quests) renderQuestBar(response.active_quests);
    } catch (err) {
        popupEl?.remove();
        showToast(err.message || 'Błąd rozwiązania testu', 'error');
        if (elements.btnSend) elements.btnSend.disabled = false;
    }
}

// ── S11 (#606) — przerzut "Zainspirowany" (player_keep_best) ───────────────────

function _renderInspiredRerollButton(skillTestId, offer) {
    const label = offer?.label || 'Zainspirowany';
    const wrap = document.createElement('div');
    wrap.className = 'message system inspired-reroll-offer';
    wrap.style.cssText = 'text-align:center;margin:8px 0;';
    const btn = document.createElement('button');
    btn.className = 'btn btn-secondary';
    btn.textContent = `🎲 Przerzuć (${label})`;
    btn.onclick = async () => {
        btn.disabled = true;
        try {
            const resp = await apiRequest('POST', `/campaigns/${currentCampaignId}/skill-test/reroll`, {
                character_id: characterData.id,
                skill_test_id: skillTestId,
            });
            wrap.remove();
            const sr = resp.skill_test_result || {};
            const margin = (typeof sr.margin === 'number') ? sr.margin : (sr.player_total - sr.opponent_total);
            const marginStr = (margin >= 0 ? '+' : '') + margin;
            // SF6 (#635) — słowny stopień marginesu (krytyki czyste).
            const _deg = sf6MarginDegree(margin);
            const _degStr = _deg ? ` (${_deg})` : '';
            let outcome;
            if (sr.outcome === 'CRITICAL_SUCCESS' || sr.nat20) outcome = ` — Krytyczny sukces ${marginStr}`;
            else if (sr.outcome === 'CRITICAL_FAILURE' || sr.nat1) outcome = ` — Krytyczna porażka ${marginStr}`;
            else if (sr.outcome === 'SUCCESS' || sr.success) outcome = ` — Sukces ${marginStr}${_degStr}`;
            else outcome = ` — Porażka ${marginStr}${_degStr}`;
            const skillName = sr.skill_label || sr.skill_key || 'Test';
            appendMessage({ role: 'user', content: `🎲 ↻ ${skillName}: ${sr.d20_roll} +${sr.modifier} = ${sr.player_total}${outcome}`, created_at: new Date() });
            if (sr.nat20) triggerCritFlash('crit'); else if (sr.nat1) triggerCritFlash('fumble');
            if (resp.prose) {
                const { narrative: gmContent } = parseGmFull(resp.prose);
                appendMessage({ role: 'assistant', content: gmContent, created_at: new Date(), turn_number: resp.turn_number });
            }
            await refreshCharacterData();
            await pollCombatState();
            scrollToBottom();
        } catch (err) {
            btn.disabled = false;
            showToast(err.message || 'Błąd przerzutu', 'error');
        }
    };
    wrap.appendChild(btn);
    elements.chatMessages.appendChild(wrap);
}

// ── #1086: Beat/quest completion notification bubbles ─────────────────────────

function renderCompletionNotifications(beats, quests) {
    if (!elements.chatMessages) return;
    const items = [
        ...(beats || []).map(b => `✓ Cel wykonany: ${b.label || b.key}`),
        ...(quests || []).map(q => q.xp > 0 ? `✓ Quest: ${q.title} — +${q.xp} XP` : `✓ Quest: ${q.title}`),
    ];
    for (const text of items) {
        const el = document.createElement('div');
        el.className = 'chat-bubble chat-bubble--completion';
        el.textContent = text;
        elements.chatMessages.appendChild(el);
    }
}

// ── UI state recovery ─────────────────────────────────────────────────────────

function _resetInputState() {
    // Re-enable send button if stuck
    if (elements.btnSend) elements.btnSend.disabled = false;
    // Hide TTS overlay if stuck visible
    const ttsOverlay = document.getElementById('tts-reading-overlay');
    if (ttsOverlay && !ttsOverlay.hidden) {
        window.voiceUI?.stopPlayback?.();
        ttsOverlay.hidden = true;
    }
    // Remove any orphaned skill test popup
    document.getElementById('skill-roll-popup')?.remove();
}

// Escape key: dismiss skill test popup or reset stuck input state
document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const popup = document.getElementById('skill-roll-popup');
    if (popup) { popup.remove(); _resetInputState(); return; }
    // If send is stuck disabled and we're in game screen, reset
    if (elements.btnSend?.disabled) _resetInputState();
});

// Tab refocus: recover from any stuck state (e.g. async call hung in background)
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && elements.btnSend?.disabled) {
        // Only reset if we're in the game screen (not mid-login or wizard)
        if (document.getElementById('game-screen')?.classList.contains('screen--active')) {
            _resetInputState();
        }
    }
});

// ─────────────────────────────────────────────────────────────────────────────

async function refreshCharacterData() {
    if (!currentCampaignId || !characterData?.id) return;
    try {
        const response = await apiRequest('GET', `/campaigns/${currentCampaignId}/characters`);
        const characters = response.characters || (Array.isArray(response) ? response : []);
        const updated = characters.find(c => c.id === characterData.id);
        if (updated) {
            characterData = updated;
            populateCharacterSheet(characterData);
            updateHeaderStats();
        }
    } catch (e) {
        // Ignore refresh errors
    }
}

// #664: shared sheet extractor — parses sheet_json when it's a JSON string
// (so /campaigns/{id}/characters string payloads don't fall through to fallbacks).
function getSheet(characterData) {
    let sheet = characterData?.sheet_json || characterData;
    if (typeof sheet === 'string') { try { sheet = JSON.parse(sheet); } catch { sheet = {}; } }
    return sheet || {};
}

function updateHeaderStats() {
    if (!characterData) return;
    const sheet = getSheet(characterData);
    const level = sheet.level || characterData.level || 1;
    const hp = sheet.current_hp ?? characterData.hp ?? 29;
    const maxHp = sheet.max_hp ?? characterData.max_hp ?? 29;
    elements.characterStatsDisplay.textContent = `${hp}/${maxHp} HP`;

    if (elements.headerHpBarFill && maxHp > 0) {
        const pct = Math.max(0, Math.min(100, (hp / maxHp) * 100));
        elements.headerHpBarFill.style.width = `${pct}%`;
        elements.headerHpBarFill.classList.toggle('header-hp-bar__fill--low', pct <= _woundThresholds.moderate_pct && pct > _woundThresholds.critical_pct);
        elements.headerHpBarFill.classList.toggle('header-hp-bar__fill--critical', pct <= _woundThresholds.critical_pct);
    }

    // #664: mana bar in header — visible only for casters (max_mana > 0)
    const mana = sheet.current_mana ?? 0;
    const maxMana = sheet.max_mana ?? 0;
    if (elements.headerManaBar) {
        elements.headerManaBar.hidden = !(maxMana > 0);
        if (elements.headerManaBarFill && maxMana > 0) {
            elements.headerManaBarFill.style.width = `${Math.max(0, Math.min(100, (mana / maxMana) * 100))}%`;
        }
    }
}

function showTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'chat-bubble chat-bubble--gm chat-bubble--typing';
    indicator.innerHTML = `
        <div class="chat-bubble__content">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
        </div>
    `;
    elements.chatMessages.appendChild(indicator);
    scrollToBottom();
    return indicator;
}

function scrollToBottom() {
    // Flaga w app.js: scroll programmatyczny nie chowa paska przygody (#952 bugfix).
    if (typeof _suppressAutoHide !== 'undefined') _suppressAutoHide = true;
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    requestAnimationFrame(() => {
        if (typeof _suppressAutoHide !== 'undefined') _suppressAutoHide = false;
    });
}

// ============================================================================
// Character Sheet Panel
// ============================================================================
let sheetOpenedAt = 0;

function toggleCharacterSheet() {
    isSheetOpen = !isSheetOpen;
    elements.sheetPanel.classList.toggle('sheet-panel--open', isSheetOpen);
    // Hide dungeon HUD so it doesn't cover sheet tabs
    const hud = document.getElementById('dungeon-hud');
    if (hud && !hud.hidden) hud.style.visibility = isSheetOpen ? 'hidden' : '';
    if (isSheetOpen) {
        sheetOpenedAt = Date.now();
        setTimeout(() => {
            elements.overlay.classList.add('panel-overlay--active');
        }, 350);
    } else {
        elements.overlay.classList.toggle('panel-overlay--active', isSettingsOpen);
    }
}

function closeCharacterSheet() {
    isSheetOpen = false;
    elements.sheetPanel.classList.remove('sheet-panel--open');
    const hud = document.getElementById('dungeon-hud');
    if (hud && !hud.hidden) hud.style.visibility = '';
    if (!isSettingsOpen && !isJournalOpen) {
        elements.overlay.classList.remove('panel-overlay--active');
    }
}

// Stage 4 S12: mobile bottom-tab bar — three top-level views (Gra/Postać/Ekwipunek).
// Only visible below 768px (CSS-gated). Routes to existing sheet open + inner-tab switch.
function _setMobileBarActive(view) {
    document.querySelectorAll('#mobile-bottom-bar .mbb-btn').forEach(btn => {
        btn.classList.toggle('mbb-btn--active', btn.dataset.mbb === view);
    });
}
function _switchSheetTab(tabId) {
    const tab = document.querySelector(`.sheet-tab[data-tab="${tabId}"]`);
    if (!tab) return;
    document.querySelectorAll('.sheet-tab').forEach(t => t.classList.remove('sheet-tab--active'));
    tab.classList.add('sheet-tab--active');
    document.querySelectorAll('.sheet-tab-content').forEach(c => {
        c.classList.toggle('sheet-tab-content--active', c.id === `tab-${tabId}`);
    });
}
function handleMobileBarClick(e) {
    const btn = e.target.closest('.mbb-btn');
    if (!btn) return;
    const view = btn.dataset.mbb;
    if (view === 'game') {
        if (isSheetOpen) closeCharacterSheet();
    } else if (view === 'character') {
        if (!isSheetOpen) toggleCharacterSheet();
        _switchSheetTab('stats');
    } else if (view === 'inventory') {
        if (!isSheetOpen) toggleCharacterSheet();
        _switchSheetTab('inventory');
    }
    _setMobileBarActive(view);
}

function handleSheetTabClick(e) {
    const tab = e.target.closest('.sheet-tab');
    if (!tab) return;

    const tabId = tab.dataset.tab;

    elements.sheetTabs.forEach(t => t.classList.remove('sheet-tab--active'));
    tab.classList.add('sheet-tab--active');

    document.querySelectorAll('.sheet-tab-content').forEach(content => {
        content.classList.toggle('sheet-tab-content--active', content.id === `tab-${tabId}`);
    });
}

function populateCharacterSheet(character) {
    if (!character) return;

    let sheet = getSheet(character);  // #664: shared parser (removes drift vs updateHeaderStats)
    elements.sheetCharacterName.textContent = character.name || 'Bohater';

    // Stage 4 S1: location badge in sheet header
    const locBadge = document.getElementById('sheet-location-badge');
    const locLabel = document.getElementById('sheet-location-label');
    if (locBadge && locLabel) {
        const locName = character.current_location_label;
        if (locName) {
            locLabel.textContent = locName;
            locBadge.style.display = '';
        } else {
            locBadge.style.display = 'none';
        }
    }

    // Race badge + racial traits (#977 R8)
    const race = (character.race || sheet.race || 'human').toLowerCase();
    const raceBadge = document.getElementById('sheet-race-badge');
    const raceIcon = document.getElementById('sheet-race-icon');
    const raceLabel = document.getElementById('sheet-race-label');
    if (raceBadge && raceIcon && raceLabel) {
        const RACE_META = {
            human: { icon: '🧑', label: 'Człowiek' },
            dwarf: { icon: '⛏️', label: 'Krasnolud' },
        };
        const meta = RACE_META[race] || { icon: '🧬', label: race };
        raceIcon.textContent = meta.icon;
        raceLabel.textContent = meta.label;
        raceBadge.style.display = race !== 'human' ? '' : 'none';
    }
    const racialSection = document.getElementById('sheet-racial-section');
    const racialTraits = document.getElementById('sheet-racial-traits');
    if (racialSection && racialTraits && race === 'dwarf') {
        racialSection.style.display = '';
        racialTraits.innerHTML = [
            { name: 'Twardy jak kamień', desc: '-2 obrażenia od trucizny, mroku i Rdzenia' },
            { name: 'Kowalskie oko', desc: '15% zniżki w sklepie · przycisk "Reperuj" (+20 PŻ za 20 sz)' },
            { name: 'Wzrok górnika', desc: '+3 percepcja w lochu · ludzie: -4 w ciemności' },
            { name: 'Rdzeń-magia', desc: 'Uczony: miscast na Nat1+Nat2 · ekskluzywne czary Rdzenia' },
        ].map(t => `<div class="racial-trait"><span class="racial-trait__name">${t.name}</span><span class="racial-trait__desc">${t.desc}</span></div>`).join('');
    } else if (racialSection) {
        racialSection.style.display = 'none';
    }

    // HP
    const hp = sheet.current_hp ?? character.hp ?? 29;
    const maxHp = Math.max(1, sheet.max_hp ?? character.max_hp ?? 29);
    elements.sheetHp.textContent = `${hp} / ${maxHp}`;
    elements.sheetHpBar.style.width = `${Math.max(0, Math.min(100, (hp / maxHp) * 100))}%`;
    flashHpOnDamage(hp);  // S8

    // Wound label (T24 / W1) — appears below HP bar when HP ≤ 75%
    const hpCard = elements.sheetHp?.closest('.stat-card--hp');
    if (hpCard) {
        let woundEl = hpCard.querySelector('.wound-label');
        const html = renderWoundLabelHTML(hp, maxHp);
        if (html) {
            if (!woundEl) { hpCard.insertAdjacentHTML('beforeend', html); }
            else { woundEl.outerHTML = html; }
        } else if (woundEl) {
            woundEl.remove();
        }
    }

    // Mana (Scholar)
    const mana = sheet.current_mana ?? 0;
    const maxMana = sheet.max_mana ?? 0;
    const manaCard = document.getElementById('sheet-mana-card');
    if (manaCard) {
        manaCard.style.display = maxMana > 0 ? '' : 'none';
        const manaEl = document.getElementById('sheet-mana');
        const manaBar = document.getElementById('sheet-mana-bar');
        if (manaEl) manaEl.textContent = `${mana} / ${maxMana}`;
        if (manaBar) manaBar.style.width = `${maxMana > 0 ? (mana / maxMana) * 100 : 0}%`;
    }

    // X2: Level label — "Poz. N" derived from lifetime XP (100 XP per level, max 10)
    const xpLifetime = parseInt(sheet.xp_lifetime_earned ?? 0);
    const level = Math.min(10, Math.max(1, Math.floor(xpLifetime / 100) + 1));
    elements.sheetLevel.textContent = `Poz. ${level}`;

    // X1: XP bar — shows spendable XP as fill toward next 100-XP milestone
    const xpAvail = parseInt(sheet.xp_available ?? 0);
    const xpPending = parseInt(sheet.pending_xp ?? 0);
    const xpEl = document.getElementById('sheet-xp');
    const xpBarFill = document.getElementById('sheet-xp-bar-fill');
    const xpPendingEl = document.getElementById('sheet-xp-pending');
    const xpNextEl = document.getElementById('sheet-xp-next');
    const nextMilestone = level * 100;
    const xpToNext = Math.max(0, nextMilestone - xpAvail);
    const xpPct = level >= 10 ? 100 : Math.min(100, (xpAvail % 100));
    if (xpEl) xpEl.textContent = xpAvail;
    if (xpBarFill) xpBarFill.style.width = `${xpPct}%`;
    if (xpPendingEl) xpPendingEl.textContent = xpPending > 0 ? `+${xpPending} oczekujące` : '';
    pulseXpOnGain(xpAvail);  // S10
    if (xpNextEl) xpNextEl.textContent = level < 10 ? `${xpToNext} do mil. ${nextMilestone}` : 'MAX';

    // X5: Rest buttons — show/hide based on safe_for_rest from current location
    renderRestButtons(character, sheet);

    // Arcane Points (Scholar)
    const apCard = document.getElementById('sheet-ap-card');
    const apEl = document.getElementById('sheet-arcane-points');
    if (apCard && apEl) {
        const ap = sheet.arcane_points ?? 0;
        apCard.style.display = sheet.archetype === 'scholar' ? '' : 'none';
        apEl.textContent = ap;
    }

    // Stage 4 S2+S3 + merged: stat→skill grouped list
    renderStatSkillList(sheet);

    // Stage 4 S5+S6+S11: conditions w/ tooltip, auto-expand, fade transitions
    renderConditionsBlock(sheet.conditions || []);

    // Show/hide spells tab for Scholar
    const spellsTabBtn = document.getElementById('sheet-tab-spells');
    if (spellsTabBtn) {
        spellsTabBtn.style.display = sheet.archetype === 'scholar' ? '' : 'none';
    }

    renderSpellsTab(character, sheet);
    renderInventoryTab(character);

    // Combined lore tab — data from GM-generated identity block.
    // Display reads BOTH V2 (bonds[].description, weaknesses[].description) AND V1
    // (identity.bond, identity.flaw) fields, so heroes created in either format
    // render correctly. Multiple entries are joined with " · ".
    const identity = sheet.identity || {};
    const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val || '—';
    };
    const joinEntries = (arr, fallbackKey) => {
        if (!Array.isArray(arr)) return '';
        return arr
            .map(e => (typeof e === 'string' ? e : (e?.description || e?.text || e?.[fallbackKey] || '')).trim())
            .filter(Boolean)
            .join(' · ');
    };
    const bondText = joinEntries(identity.bonds, 'bond') || identity.bond || sheet.bond || '';
    const flawText = joinEntries(identity.weaknesses, 'flaw') || identity.flaw || sheet.flaw || '';
    setText('sheet-backstory-text', sheet.backstory || identity.backstory);
    setText('sheet-appearance-text', identity.appearance || sheet.appearance);
    setText('sheet-personality-text', identity.personality || sheet.personality);
    setText('sheet-flaw-text', flawText);
    setText('sheet-bond-text', bondText);
}

// ============================================================================
// X5: Rest buttons + X6/X7/X8 Awansuj panel + X9 XP log
// ============================================================================

async function refreshCharacterSheet() {
    if (!characterData?.id) return;
    try {
        const updated = await apiRequest('GET', `/characters/${characterData.id}`);
        characterData = updated;
        populateCharacterSheet(characterData);
    } catch (e) {
        console.warn('[refreshCharacterSheet] failed:', e);
    }
}

function renderRestButtons(character, sheet) {
    const container = document.getElementById('sheet-rest-actions');
    if (!container) return;
    const shortUsed = parseInt(sheet.short_rests_used ?? 0);
    const shortLeft = Math.max(0, 2 - shortUsed);
    const safeForRest = !!character.safe_for_rest;
    const race = (character.race || sheet.race || 'human').toLowerCase();

    container.innerHTML = `
        <div class="rest-actions">
            <div class="rest-actions__label">Odpoczynek</div>
            <div class="rest-actions__row">
                <button class="rest-btn rest-btn--short ${!safeForRest || shortLeft === 0 ? 'rest-btn--disabled' : ''}"
                    id="btn-short-rest"
                    ${!safeForRest || shortLeft === 0 ? 'disabled' : ''}>
                    ☽ Krótki <span class="rest-charges">${shortLeft}/2</span>
                </button>
                <button class="rest-btn rest-btn--long ${!safeForRest ? 'rest-btn--disabled' : ''}"
                    id="btn-long-rest"
                    ${!safeForRest ? 'disabled' : ''}>
                    ★ Długi
                </button>
                <button class="rest-btn rest-btn--upgrade" id="btn-awansuj">
                    ⬆ Awansuj${sheet.xp_available > 0 ? ` (${sheet.xp_available} PD)` : ''}
                </button>
                ${race === 'dwarf' ? '<button class="rest-btn rest-btn--repair" id="btn-dwarf-repair">⛏️ Reperuj <span class="rest-charges">20 gp</span></button>' : ''}
            </div>
            ${!safeForRest ? '<div class="rest-actions__note">Musisz być w bezpiecznym miejscu</div>' : ''}
        </div>`;

    container.querySelector('#btn-short-rest')?.addEventListener('click', () => doRest('short', character, sheet));
    container.querySelector('#btn-long-rest')?.addEventListener('click', () => openLongRestModal(character, sheet));
    container.querySelector('#btn-awansuj')?.addEventListener('click', () => openAwansujPanel(character, sheet));
    container.querySelector('#btn-dwarf-repair')?.addEventListener('click', () => doDwarfRepair(character));
}

async function doDwarfRepair(character) {
    try {
        const r = await fetch(`/api/characters/${character.id}/dwarf-repair?user_id=${currentUser?.id}`, { method: 'POST' });
        const data = await r.json();
        if (!r.ok) {
            showToast(data.detail || 'Błąd akcji Reperuj', 'error');
            return;
        }
        showToast(data.message || `Naprawiono za ${data.cost_gp} gp.`, 'success');
        await refreshCharacterSheet();
    } catch (e) {
        showToast('Błąd akcji Reperuj: ' + e.message, 'error');
    }
}

function openLongRestModal(character, sheet) {
    const existing = document.getElementById('long-rest-choice-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'long-rest-choice-modal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-box rest-choice-box">
            <div class="modal-box__header">
                <h3>Długi odpoczynek</h3>
                <button class="modal-close" id="long-rest-close">✕</button>
            </div>
            <div class="rest-choice-body">
                <p class="rest-choice-intro">Masz <strong>${sheet.xp_available ?? 0} PD</strong> do wydania. Co chcesz zrobić tej nocy?</p>
                <div class="rest-choice-btns">
                    <button class="btn btn--primary" id="rest-choice-learn">
                        📖 Ucz się
                        <span class="rest-choice-sub">Wydaj PD na umiejętności i statystyki</span>
                    </button>
                    <button class="btn btn--secondary" id="rest-choice-sleep">
                        🌙 Śpij i odpocznij
                        <span class="rest-choice-sub">Odbuduj HP i manę, zachowaj PD na później</span>
                    </button>
                </div>
            </div>
        </div>`;
    document.body.appendChild(modal);

    modal.querySelector('#long-rest-close').addEventListener('click', () => modal.remove());
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });

    modal.querySelector('#rest-choice-learn').addEventListener('click', () => {
        modal.remove();
        openAwansujPanel(character, sheet);
    });
    modal.querySelector('#rest-choice-sleep').addEventListener('click', async () => {
        modal.remove();
        await doRest('long', character, sheet);
    });
}

async function doRest(type, character, sheet) {
    const label = type === 'long' ? 'długi' : 'krótki';
    if (!confirm(`Wykonać ${label} odpoczynek?`)) return;
    try {
        const r = await fetch(
            `/api/characters/${character.id}/rest?type=${type}&user_id=${currentUser?.id}`,
            { method: 'POST' }
        );
        const data = await r.json();
        if (!r.ok) {
            const msg = { not_safe_for_rest: 'Nie jesteś w bezpiecznym miejscu.', short_rest_exhausted: 'Brak ładunków krótkiego odpoczynku. Wykonaj długi odpoczynek.' }[data.detail] || data.detail;
            showToast(msg, 'error');
            return;
        }
        if (type === 'long') {
            const xpMsg = data.xp_unlocked > 0 ? ` Odblokowano ${data.xp_unlocked} PD.` : '';
            showToast(`Długi odpoczynek. HP: ${data.hp_after}/${sheet.max_hp}. +8h.${xpMsg}`, 'success');
        } else {
            showToast(`Krótki odpoczynek. HP: ${data.hp_before}→${data.hp_after} (+${data.hp_after - data.hp_before}). +1h. Pozostało: ${data.short_rests_remaining}/2`, 'success');
        }
        await refreshCharacterSheet();
    } catch (e) {
        showToast('Błąd odpoczynku: ' + e.message, 'error');
    }
}

async function openAwansujPanel(character, sheet) {
    const modal = document.getElementById('awansuj-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    document.getElementById('awansuj-close')?.addEventListener('click', () => { modal.style.display = 'none'; }, { once: true });

    const body = document.getElementById('awansuj-body');
    if (!body) return;
    body.innerHTML = '<div class="camp-loading">Ładowanie…</div>';

    try {
        const [xpData, creatorHelp] = await Promise.all([
            apiRequest('GET', `/characters/${character.id}/xp?user_id=${currentUser?.id}`),
            fetch('/api/mechanics/creator-help').then(r => r.ok ? r.json() : { skills: [], stats: [] })
        ]);
        const xpAvail = xpData.xp_available ?? 0;
        const xpLifetime = xpData.xp_lifetime_earned ?? 0;
        const skills = sheet.skills || {};
        const stats = sheet.stats || {};
        const mods = sheet.stat_modifiers || {};
        const rankCosts = xpData.rank_up_costs || {};
        const statCosts = xpData.stat_point_costs || {};
        const skillRankCeiling = xpData.skill_rank_ceiling ?? 3;
        const statValueCeiling = xpData.stat_value_ceiling ?? 19;
        const isScholar = (sheet.archetype || '').toLowerCase() === 'scholar';

        const skillInfoMap = {};
        (creatorHelp.skills || []).forEach(s => { skillInfoMap[s.key] = s; });

        const LEGACY_SKILLS = {
            sleight_of_hand: { label: 'Zręczność rąk', stat: 'DEX', description: 'Manipulacja, kieszonkowość, ukrywanie przedmiotów.' },
            melee_attack:    { label: 'Atak wręcz',     stat: 'STR', description: 'Skuteczny cios: celowanie, siła i timing ataku.' },
            ranged_attack:   { label: 'Atak dystansowy', stat: 'DEX', description: 'Strzelanie i miotanie — precyzja na odległość.' },
            spell_attack:    { label: 'Atak czarów',    stat: 'INT', description: 'Koncentracja przy wyrzucaniu zaklęć ofensywnych.' },
        };

        const STAT_LABELS = { STR:'Siła', DEX:'Zręczność', CON:'Kondycja', INT:'Inteligencja', WIS:'Mądrość', CHA:'Charyzma', LCK:'Szczęście' };
        const STAT_DESC = {
            STR: 'Siła fizyczna i moc ciosu. Modyfikuje ataki bronią białą i test Atletyki.',
            DEX: 'Zwinność, skradanie, refleks. Decyduje o inicjatywie i atakach dystansowych.',
            CON: 'Wytrzymałość i zdrowie. Zwiększa maks. PŻ i odporność na trucizny.',
            INT: 'Wiedza i magia. Zasila zaklęcia i pulę many Uczonego.',
            WIS: 'Spostrzegawczość i intuicja. Wchodzi do wykrywania zagrożeń i medycyny.',
            CHA: 'Perswazja i charyzma. Wpływa na negocjacje, zastraszanie, podszęp.',
            LCK: 'Szczęście i traf. Modyfikuje rzuty łutowe i szanse na bonus.',
        };

        function _notchTrack(current, ceiling) {
            let html = '<div class="awrow__track">';
            for (let i = 1; i <= ceiling; i++) {
                if (i <= current) html += '<div class="awrow__notch awrow__notch--filled" title="Ranga ' + i + ' ✓"></div>';
                else if (i === current + 1) html += '<div class="awrow__notch awrow__notch--next" title="Następna ranga"></div>';
                else html += '<div class="awrow__notch" title="Ranga ' + i + ' — zablokowane"></div>';
            }
            return html + '</div>';
        }

        function _awRow(opts) {
            const missing = typeof opts.cost === 'number' ? opts.cost - opts.xpAvail : 0;
            const rightHtml = opts.canAfford
                ? `<button class="awrow__commit" data-action="${opts.action}" data-key="${escapeHtml(opts.dataKey)}" data-cost="${opts.cost}">${opts.cost} PD</button>`
                : `<span class="awrow__gap">brakuje ${missing > 0 ? missing : '?'} PD</span>`;
            return `<div class="awrow ${opts.canAfford ? 'awrow--affordable' : 'awrow--locked'} ${opts.cls || ''}">
  <div class="awrow__left">
    <span class="awrow__name">${opts.nameHtml}</span>${opts.statBadge ? `<span class="awrow__stat">${opts.statBadge}</span>` : ''}
    ${opts.descHtml ? `<span class="awrow__desc">${opts.descHtml}</span>` : ''}
  </div>
  <div class="awrow__mid">
    ${opts.track || ''}
    <div class="awrow__rank-lbl">${opts.rankLbl || ''}</div>
  </div>
  ${rightHtml}
</div>`;
        }

        let skillRows = '';
        Object.entries(skills).forEach(([key, rank]) => {
            if (!skillInfoMap[key]) return; // #1052: hide non-catalog skills (melee_attack etc.)
            if (rank >= skillRankCeiling) return;
            const newRank = rank + 1;
            const cost = rankCosts[newRank] || rankCosts[String(newRank)];
            if (!cost) return;
            const canAfford = xpAvail >= cost;
            const info = skillInfoMap[key] || {};
            skillRows += _awRow({
                nameHtml: escapeHtml(info.label || key),
                statBadge: info.stat || '',
                descHtml: escapeHtml(info.description || ''),
                track: _notchTrack(rank, skillRankCeiling),
                rankLbl: `Ranga ${rank} → ${newRank}`,
                action: 'skill',
                dataKey: key,
                cost,
                canAfford,
                xpAvail,
            });
        });

        let statRows = '';
        Object.entries(stats).forEach(([key, val]) => {
            const newVal = val + 1;
            const cost = statCosts[newVal] || statCosts[String(newVal)];
            if (!cost || newVal > statValueCeiling) return;
            const canAfford = xpAvail >= cost;
            const mod = mods[key] ?? Math.floor((val - 10) / 2);
            const newMod = Math.floor((newVal - 10) / 2);
            statRows += _awRow({
                nameHtml: escapeHtml(STAT_LABELS[key] || key),
                statBadge: '',
                descHtml: escapeHtml(STAT_DESC[key] || ''),
                track: '',
                rankLbl: `${val} (${mod >= 0 ? '+' : ''}${mod}) → ${newVal} (${newMod >= 0 ? '+' : ''}${newMod})`,
                action: 'stat',
                dataKey: key,
                cost,
                canAfford,
                xpAvail,
            });
        });

        let spellRows = '';
        if (isScholar) {
            const [knownSpells, allSpells] = await Promise.all([
                fetch(`/api/characters/${character.id}/spells`).then(r => r.json()),
                fetch('/api/spells').then(r => r.ok ? r.json() : { spells: [] })
            ]);
            const knownMap = {};
            (knownSpells.spells || []).forEach(s => { knownMap[s.spell_key] = s.rank; });
            (allSpells.spells || []).forEach(spell => {
                const currentRank = knownMap[spell.key] ?? 0;
                if (currentRank >= 3) return;
                const cost = currentRank === 0 ? 75 : currentRank === 1 ? 50 : 100;
                const canAfford = xpAvail >= cost;
                spellRows += _awRow({
                    cls: 'awrow--spell',
                    nameHtml: escapeHtml(spell.label),
                    statBadge: 'INT',
                    descHtml: escapeHtml(spell.description || ''),
                    track: _notchTrack(currentRank, 3),
                    rankLbl: currentRank === 0 ? 'Naucz (Ranga 1)' : `Ranga ${currentRank} → ${currentRank + 1}`,
                    action: currentRank === 0 ? 'spell-learn' : 'spell-upgrade',
                    dataKey: spell.key,
                    cost,
                    canAfford,
                    xpAvail,
                });
            });
        }

        body.innerHTML = `
<div class="awansuj-hero-bar">
  <div class="awansuj-pd-col">
    <span class="awansuj-pd-label">Dostępne PD</span>
    <span class="awansuj-pd-value">${xpAvail}</span>
  </div>
  <div class="awansuj-pd-col" style="text-align:right">
    <span class="awansuj-pd-label">Łącznie zdobyte</span>
    <span class="awansuj-pd-lifetime">${xpLifetime} PD</span>
  </div>
</div>
${skillRows ? `<div class="awansuj-section"><div class="awansuj-section-hdr">Umiejętności</div>${skillRows}</div>` : ''}
${statRows ? `<div class="awansuj-section"><div class="awansuj-section-hdr">Cechy</div>${statRows}</div>` : ''}
${isScholar && spellRows ? `<div class="awansuj-section"><div class="awansuj-section-hdr">Zaklęcia</div>${spellRows}</div>` : ''}
<div class="awansuj-section">
  <div class="awansuj-section-hdr">Historia PD</div>
  <div id="awansuj-xp-log"><div class="camp-loading">Ładowanie…</div></div>
</div>`;

        loadXpLog(character, document.getElementById('awansuj-xp-log'));

        body.querySelectorAll('.awrow__commit').forEach(btn => {
            btn.addEventListener('click', () => {
                const row = btn.closest('.awrow');
                if (!row) return;
                row.querySelector('.awrow__confirm')?.remove();
                const { action, key, cost } = btn.dataset;
                const strip = document.createElement('div');
                strip.className = 'awrow__confirm';
                strip.innerHTML = `<span>Wydać <strong>${cost} PD</strong>?</span>
<button class="awrow__confirm-yes" data-action="${action}" data-key="${escapeHtml(key)}" data-cost="${cost}">Tak, rozwijaj się</button>
<button class="awrow__confirm-no">Anuluj</button>`;
                row.appendChild(strip);
                strip.querySelector('.awrow__confirm-no').addEventListener('click', () => strip.remove());
                strip.querySelector('.awrow__confirm-yes').addEventListener('click', async () => {
                    strip.innerHTML = '<span style="color:var(--text-muted)">Zapisuję…</span>';
                    let url, payload;
                    if (action === 'skill') {
                        url = `/api/characters/${character.id}/xp/spend-skill`;
                        payload = { skill_key: key, user_id: currentUser?.id };
                    } else if (action === 'stat') {
                        url = `/api/characters/${character.id}/xp/spend-stat`;
                        payload = { stat_key: key, user_id: currentUser?.id };
                    } else if (action === 'spell-learn') {
                        url = `/api/characters/${character.id}/xp/spend-spell-learn`;
                        payload = { spell_key: key, user_id: currentUser?.id };
                    } else if (action === 'spell-upgrade') {
                        url = `/api/characters/${character.id}/xp/spend-spell-upgrade`;
                        payload = { spell_key: key, user_id: currentUser?.id };
                    }
                    try {
                        const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                        const data = await r.json();
                        if (!r.ok) throw new Error(data.detail || 'error');
                        showToast(`Zapisano! Pozostało: ${data.xp_available} PD`, 'success');
                        await refreshCharacterSheet();
                        await openAwansujPanel(characterData, getSheet(characterData));
                    } catch (e) {
                        showToast('Błąd: ' + e.message, 'error');
                        strip.remove();
                    }
                });
            });
        });
    } catch (e) {
        body.innerHTML = `<p style="color:var(--accent-red)">${escapeHtml(e.message)}</p>`;
    }
}

// XP grant log
async function loadXpLog(character, container) {
    if (!container) return;
    try {
        const data = await apiRequest('GET', `/characters/${character.id}/xp/grant-log?user_id=${currentUser?.id}&limit=20`);
        const grants = data.grants || [];
        if (!grants.length) { container.innerHTML = '<p class="section-note">Brak historii PD.</p>'; return; }
        container.innerHTML = `<table class="xp-log-table">
            <thead><tr><th>Powód</th><th>PD</th><th>Kiedy</th></tr></thead>
            <tbody>${grants.map(g => {
                const amt = g.amount > 0 ? `+${g.amount}` : String(g.amount);
                const cls = g.amount > 0 ? 'xp-pos' : 'xp-neg';
                const date = (g.created_at || '').slice(0, 16).replace('T', ' ');
                return `<tr><td>${escapeHtml(g.reason || g.source || '—')}</td><td class="${cls}">${amt}</td><td>${date}</td></tr>`;
            }).join('')}</tbody>
        </table>`;
    } catch (e) {
        container.innerHTML = `<p style="color:var(--accent-red)">Błąd ładowania historii.</p>`;
    }
}

// Skills tab — trained skills with rank/ceiling and tap-for-description
// ============================================================================

const SKILL_META_CACHE = { byKey: null, descByKey: null, fetchedAt: 0 };
const SKILL_META_TTL_MS = 5 * 60_000;

async function _ensureSkillMeta() {
    const now = Date.now();
    if (SKILL_META_CACHE.byKey && now - SKILL_META_CACHE.fetchedAt < SKILL_META_TTL_MS) return;

    // Public: descriptions via /mechanics/metadata
    let descByKey = {};
    try {
        const r = await fetch('/api/mechanics/metadata').then(r => r.ok ? r.json() : null);
        if (r?.test_descriptions) descByKey = r.test_descriptions;
    } catch (_e) {}

    // Optional: full skill catalog via /admin/skills if we have a token (gives rank_ceiling)
    let byKey = null;
    const token = localStorage.getItem('aigm_admin_token');
    if (token) {
        try {
            const r = await fetch('/api/admin/skills', {
                headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
            }).then(r => r.ok ? r.json() : null);
            const items = r?.items || [];
            byKey = Object.fromEntries(items.map(it => [it.key, it]));
        } catch (_e) {}
    }

    SKILL_META_CACHE.descByKey = descByKey;
    SKILL_META_CACHE.byKey = byKey || {};
    SKILL_META_CACHE.fetchedAt = now;
}

// Stage 4 S5: condition tooltip — cache labels + descriptions from public endpoint
const CONDITION_META_CACHE = { byKey: null, fetchedAt: 0 };
const CONDITION_META_TTL_MS = 5 * 60_000;
async function _ensureConditionMeta() {
    const now = Date.now();
    if (CONDITION_META_CACHE.byKey && now - CONDITION_META_CACHE.fetchedAt < CONDITION_META_TTL_MS) return;
    try {
        const r = await fetch('/api/mechanics/conditions').then(r => r.ok ? r.json() : null);
        const items = r?.conditions || [];
        CONDITION_META_CACHE.byKey = Object.fromEntries(items.map(c => [c.key, c]));
    } catch (_e) {
        CONDITION_META_CACHE.byKey = {};
    }
    CONDITION_META_CACHE.fetchedAt = now;
}

// Stage 4 S4: stat tooltip — Polish names + role hints for the 7 core stats
const STAT_TOOLTIPS = {
    STR: 'Siła — walka wręcz, dźwiganie, fizyczna moc. Modyfikator wchodzi do ataków bronią białą i Atletyki.',
    DEX: 'Zręczność — akrobacja, skradanie, refleks. Modyfikator wchodzi do Inicjatywy i ataków dystansowych.',
    CON: 'Kondycja — wytrzymałość. Modyfikator wpływa na maks. PŻ i opieranie się truciznom.',
    INT: 'Inteligencja — wiedza, magia, dochodzenie. Modyfikator wpływa na pulę many Uczonego.',
    WIS: 'Mądrość — spostrzegawczość, intuicja, medycyna. Modyfikator wchodzi do wykrywania zagrożeń.',
    CHA: 'Charyzma — perswazja, zastraszanie, oszustwo. Modyfikator wchodzi do testów społecznych.',
    LCK: 'Szczęście — wyłapanie szczęśliwego trafu. Modyfikator dodatkowo wpływa na rzuty łutowe.',
};

// Stage 4 S5/S6/S11: conditions section — tooltip per chip, auto-expand when any,
// fade-in for new conditions and fade-out for removed ones (diffed against last render).
let _lastConditionKeys = new Set();
async function renderConditionsBlock(conditions) {
    const condSection = document.getElementById('sheet-conditions-section');
    const condEl = document.getElementById('sheet-conditions');
    if (!condSection || !condEl) return;

    await _ensureConditionMeta();
    const meta = CONDITION_META_CACHE.byKey || {};

    const normalized = (conditions || []).map(c => {
        if (typeof c === 'string') return { key: c, label: c };
        return { key: c.key || c.label || '', label: c.label || c.key || '' };
    }).filter(c => c.key);

    if (normalized.length === 0) {
        // Fade out everything still rendered, then hide section.
        condSection.classList.remove('sheet-conditions--expanded');
        condEl.querySelectorAll('.condition-chip').forEach(el => el.classList.add('condition-chip--leaving'));
        setTimeout(() => {
            condEl.innerHTML = '';
            condSection.style.display = 'none';
        }, 220);
        _lastConditionKeys = new Set();
        return;
    }

    condSection.style.display = '';
    condSection.classList.add('sheet-conditions--expanded');  // S6: auto-expand
    const currentKeys = new Set(normalized.map(c => c.key));

    condEl.innerHTML = normalized.map(c => {
        const m = meta[c.key] || {};
        const desc = m.description || 'Brak opisu w bazie.';
        const label = m.label || c.label || c.key;
        const isNew = !_lastConditionKeys.has(c.key);
        const cls = `condition-chip${isNew ? ' condition-chip--entering' : ''}`;
        return `<span class="${cls}" title="${escapeHtml(desc)}" tabindex="0">${escapeHtml(label)}</span>`;
    }).join('');

    _lastConditionKeys = currentKeys;
}

// Stage 4 S8/S9/S10: animation helpers — fire when values change between renders.
const _lastVitals = { hp: null, gold: null, xp_available: null };

function pulseElement(el, cls, durationMs = 600) {
    if (!el) return;
    el.classList.remove(cls);
    void el.offsetWidth;
    el.classList.add(cls);
    setTimeout(() => el.classList.remove(cls), durationMs);
}

function flashHpOnDamage(currentHp) {
    if (_lastVitals.hp == null) { _lastVitals.hp = currentHp; return; }
    if (currentHp < _lastVitals.hp) {
        // Took damage — red flash on the whole card + brief tick on the number.
        pulseElement(document.querySelector('.stat-card--hp'), 'stat-card--damaged', 600);
        pulseElement(document.getElementById('sheet-hp'), 'stat-card__value--ticked', 480);
    }
    _lastVitals.hp = currentHp;
}

function pulseGoldOnChange(currentGold) {
    if (_lastVitals.gold == null) { _lastVitals.gold = currentGold; return; }
    if (currentGold !== _lastVitals.gold) {
        pulseElement(document.querySelector('.inv-gold'), 'inv-gold--pulsing', 700);
    }
    _lastVitals.gold = currentGold;
}

function pulseXpOnGain(currentXpAvail) {
    if (_lastVitals.xp_available == null) { _lastVitals.xp_available = currentXpAvail; return; }
    if (currentXpAvail > _lastVitals.xp_available) {
        pulseElement(document.querySelector('.xp-bar-card'), 'xp-bar-card--gained', 1100);
        pulseElement(document.getElementById('sheet-xp-bar-fill'), 'xp-bar__fill--filling', 1000);
    }
    _lastVitals.xp_available = currentXpAvail;
}

// Stage 4 S2+S3 + merged stats/skills tab: one block per stat, with its trained skills nested.
// Bar visualizes base stat on a 0-20 scale; right strip reserved for future item bonuses.
// Rank shown as 5 dots (●●●○○) with a +2 prof pill at rank ≥ 3.
async function renderStatSkillList(sheet) {
    const container = document.getElementById('sheet-stat-skill-list');
    if (!container) return;

    const stats = sheet?.stats || {};
    const mods = sheet?.stat_modifiers || {};
    const skills = sheet?.skills || {};

    await _ensureSkillMeta();
    const labelByKey = Object.fromEntries(ALL_SKILL_ROWS.map(r => [r.key, r.label]));

    const STAT_LABELS = {
        STR: 'Siła', DEX: 'Zręczność', CON: 'Kondycja',
        INT: 'Inteligencja', WIS: 'Mądrość', CHA: 'Charyzma', LCK: 'Szczęście',
    };
    const STAT_ORDER = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA', 'LCK'];

    // Resolve every trained skill (rank>0) and bucket by its linked stat.
    const trainedByStat = Object.fromEntries(STAT_ORDER.map(s => [s, []]));
    Object.entries(skills).forEach(([k, v]) => {
        const rank = Number(v) || 0;
        if (rank <= 0) return;
        const meta = SKILL_META_CACHE.byKey?.[k] || {};
        const linked = String(meta.linked_stat || (ALL_SKILL_ROWS.find(r => r.key === k)?.stat) || '').toUpperCase();
        if (!STAT_ORDER.includes(linked)) return;
        trainedByStat[linked].push({
            key: k,
            label: meta.label || labelByKey[k] || _formatSkillLabel(k),
            rank,
            ceiling: Number(meta.rank_ceiling) || 5,
            description: SKILL_META_CACHE.descByKey?.[k] || meta.description || '',
        });
    });
    // Sort skills inside each stat alphabetically by Polish label.
    STAT_ORDER.forEach(s => trainedByStat[s].sort((a, b) => a.label.localeCompare(b.label)));

    const renderDots = (rank, ceiling) => {
        const max = Math.max(5, ceiling || 5);
        let out = '';
        for (let i = 0; i < max; i++) {
            out += `<span class="stat-skill-row__dot ${i < rank ? 'stat-skill-row__dot--filled' : ''}"></span>`;
        }
        return out;
    };

    container.innerHTML = STAT_ORDER.map(stat => {
        const val = Number(stats[stat] ?? stats[stat.toLowerCase()] ?? 10);
        const mod = Number(mods[stat] ?? Math.floor((val - 10) / 2));
        const modStr = mod >= 0 ? `+${mod}` : `${mod}`;
        const modCls = mod > 0 ? 'mod--pos' : mod < 0 ? 'mod--neg' : 'mod--zero';
        // Bar: 0-20 scale. Future hook: itemBonus splits the fill into base + bonus.
        const itemBonus = 0;
        const basePct = Math.max(0, Math.min(100, (Math.min(val, 20) / 20) * 100));
        const bonusPct = Math.max(0, Math.min(100 - basePct, (Math.min(itemBonus, 20) / 20) * 100));
        const skillRows = trainedByStat[stat].map(s => {
            const profPill = s.rank >= 3 ? '<span class="stat-skill-row__prof" title="Premia biegłości">+2</span>' : '';
            const rollBonus = mod + s.rank + (s.rank >= 3 ? 2 : 0);
            const rollStr = rollBonus >= 0 ? `+${rollBonus}` : `${rollBonus}`;
            const desc = s.description || 'Brak opisu w bazie.';
            return `
                <div class="stat-skill-row" data-skill-key="${escapeHtml(s.key)}" title="${escapeHtml(desc)}">
                    <span class="stat-skill-row__name">${escapeHtml(s.label)}</span>
                    <span class="stat-skill-row__dots-wrap">${renderDots(s.rank, s.ceiling)}</span>
                    ${profPill}
                    <span class="stat-skill-row__roll">${rollStr}</span>
                </div>`;
        }).join('');
        const skillsBlock = skillRows
            ? `<div class="stat-skill-group__skills">${skillRows}</div>`
            : `<div class="stat-skill-group__empty">brak wytrenowanych</div>`;
        return `
            <div class="stat-skill-group" data-stat="${stat}">
                <div class="stat-skill-group__header">
                    <span class="stat-skill-group__code" title="${escapeHtml(STAT_TOOLTIPS[stat] || STAT_LABELS[stat] || stat)}" tabindex="0">${stat}</span>
                    <span class="stat-skill-group__val">${val}</span>
                    <span class="stat-skill-group__mod ${modCls}">${modStr}</span>
                    <div class="stat-skill-group__bar">
                        <div class="stat-skill-group__bar-base" style="width:${basePct}%"></div>
                        <div class="stat-skill-group__bar-bonus" style="width:${bonusPct}%"></div>
                    </div>
                    <span class="stat-skill-group__cap">20</span>
                </div>
                ${skillsBlock}
            </div>`;
    }).join('');
}

async function renderSkillsTab(sheet) {
    const skills = sheet?.skills || {};
    if (typeof skills !== 'object' || Array.isArray(skills)) {
        elements.sheetSkills.innerHTML = '<p class="muted">Brak umiejętności</p>';
        return;
    }

    await _ensureSkillMeta();
    const labelByKey = Object.fromEntries(ALL_SKILL_ROWS.map(r => [r.key, r.label]));

    const entries = Object.entries(skills)
        .filter(([_, v]) => Number(v) > 0) // only trained
        .map(([k, v]) => {
            const meta = SKILL_META_CACHE.byKey?.[k] || {};
            return {
                key: k,
                label: meta.label || labelByKey[k] || _formatSkillLabel(k),
                rank: Number(v) || 0,
                ceiling: Number(meta.rank_ceiling) || 5,
                description: SKILL_META_CACHE.descByKey?.[k] || meta.description || '',
                stat: meta.linked_stat || (ALL_SKILL_ROWS.find(r => r.key === k)?.stat) || '',
            };
        })
        .sort((a, b) => a.label.localeCompare(b.label));

    if (!entries.length) {
        elements.sheetSkills.innerHTML = '<p class="muted">Brak wytrenowanych umiejętności</p>';
        return;
    }

    elements.sheetSkills.innerHTML = entries.map(s => {
        const desc = s.description || 'Brak opisu w bazie.';
        const stat = s.stat ? `<span class="skill-item__stat">${escapeHtml(s.stat)}</span>` : '';
        return `
            <div class="skill-item skill-item--clickable" data-skill-key="${escapeHtml(s.key)}" title="${escapeHtml(desc)}">
                <div class="skill-item__row">
                    <span class="skill-item__name">${escapeHtml(s.label)}</span>
                    <span class="skill-item__meta">${stat}<span class="skill-item__rank">${s.rank}/${s.ceiling}</span></span>
                </div>
                <div class="skill-item__desc" hidden>${escapeHtml(desc)}</div>
            </div>`;
    }).join('');

    // Tap toggles description for mobile (desktop has native title= tooltip on hover too)
    elements.sheetSkills.querySelectorAll('.skill-item--clickable').forEach(el => {
        el.addEventListener('click', () => {
            const desc = el.querySelector('.skill-item__desc');
            if (!desc) return;
            const isOpen = !desc.hasAttribute('hidden');
            // close all others
            elements.sheetSkills.querySelectorAll('.skill-item__desc').forEach(d => d.setAttribute('hidden', ''));
            elements.sheetSkills.querySelectorAll('.skill-item--clickable').forEach(d => d.classList.remove('skill-item--open'));
            if (!isOpen) {
                desc.removeAttribute('hidden');
                el.classList.add('skill-item--open');
            }
        });
    });
}

function _formatSkillLabel(key) {
    const k = String(key || '').trim().toLowerCase();
    const map = {
        sleight_of_hand: 'Sleight of Hand',
        melee_attack: 'Melee Attack',
        ranged_attack: 'Ranged Attack',
        spell_attack: 'Spell Attack',
    };
    if (map[k]) return map[k];
    return k.split('_').filter(Boolean).map(w => w[0].toUpperCase() + w.slice(1)).join(' ');
}

// ============================================================================
// Inventory rendering — Adventurer's Pack
// ============================================================================

// Stage 5 E5: anatomical 8-slot definitions.
// Each entry carries a grid-area name + Polish label + body-part wound keys
// (used by E7 to tint the slot red when a matching condition is active).
const INV_SLOT_DEFS = [
    { key: 'head',      label: 'Głowa',           icon: 'helm',   area: 'head',      wound: ['head_wound'] },
    { key: 'l_arm',     label: 'Lewe ramię',      icon: 'gaunt',  area: 'larm',      wound: ['arm_wound', 'arm_wound_left',  'l_arm_wound'] },
    { key: 'torso',     label: 'Tors',            icon: 'armor',  area: 'torso',     wound: ['torso_wound', 'chest_wound'] },
    { key: 'r_arm',     label: 'Prawe ramię',     icon: 'gaunt',  area: 'rarm',      wound: ['arm_wound', 'arm_wound_right', 'r_arm_wound'] },
    { key: 'hands',     label: 'Rękawice',        icon: 'gaunt',  area: 'hands',     wound: ['hand_wound'] },
    { key: 'l_leg',     label: 'Lewa noga',       icon: 'greave', area: 'lleg',      wound: ['leg_wound', 'leg_wound_left',   'l_leg_wound'] },
    { key: 'r_leg',     label: 'Prawa noga',      icon: 'greave', area: 'rleg',      wound: ['leg_wound', 'leg_wound_right',  'r_leg_wound'] },
    { key: 'main_hand', label: 'Główna ręka',     icon: 'sword',  area: 'mainh',     wound: [] },
    { key: 'off_hand',  label: 'Pomocnicza',      icon: 'shield', area: 'offh',      wound: [] },
];

const INV_ICONS = {
    sword: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 17.5L3 6V3h3l11.5 11.5"/><path d="M13 19l6-6"/><path d="M16 16l4 4"/><path d="M19 21l2-2"/></svg>`,
    shield: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
    armor: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20.4 7.4l-3.4-3a1 1 0 0 0-1.3.1l-1.7 2-1.5-1a1 1 0 0 0-1 0l-1.5 1-1.7-2a1 1 0 0 0-1.3-.1l-3.4 3a1 1 0 0 0-.3 1.1L5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6l1.7-4.5a1 1 0 0 0-.3-1.1z"/><path d="M12 6v15"/></svg>`,
    // Stage 5 E5: simple line-art glyphs for the anatomical slots.
    helm: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13c0-4 3-7 7-7s7 3 7 7v4H5z"/><path d="M9 13v-1"/><path d="M15 13v-1"/><path d="M10 17v3h4v-3"/></svg>`,
    gaunt: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8 4v9l-2 1 2 5h7l3-4V8l-2-1V4"/><path d="M11 8v3"/><path d="M14 8v3"/></svg>`,
    greave: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6v6l-2 8-1 4h-2l-1-4-2-8z"/><path d="M9 9h6"/><path d="M10 13h4"/></svg>`,
    potion: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2h4"/><path d="M11 2v4.5L6 14a4 4 0 0 0 4 7h4a4 4 0 0 0 4-7L13 6.5V2"/></svg>`,
    scroll: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8a3 3 0 0 0 3-3V8H8"/><path d="M19 8V5a3 3 0 0 0-3-3H5v13a3 3 0 0 0 3 3"/><path d="M5 5h11"/></svg>`,
    pack: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h16v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8z"/><path d="M8 8V5a4 4 0 0 1 8 0v3"/><path d="M9 13h6"/></svg>`,
    chain: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>`,
    blood: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C9 7 6 11 6 15a6 6 0 0 0 12 0c0-4-3-8-6-13z"/></svg>`,
    // #764: amunicja (strzały/bełty) — kołczan ze strzałą.
    quiver: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21L21 3"/><path d="M21 3l-5 1 4 4 1-5z"/><path d="M3 21l3.5-.7"/><path d="M3 21l.7-3.5"/></svg>`,
};

// Map item_type → inventory section + icon glyph
function _invIconKind(item) {
    const t = String(item.item_type || '').toLowerCase();
    const k = String(item.key || item.label || '').toLowerCase();
    if (item.is_ammo || /^(arrows|bolts)$/.test(k))     return 'quiver';  // #764
    if (t === 'weapon')                                 return /bow|łuk/.test(k) ? 'sword' : 'sword';
    if (t === 'armor' && /shield|tarcz/.test(k))        return 'shield';
    if (t === 'armor')                                  return 'armor';
    if (t === 'consumable')                             return 'potion';
    return 'scroll';
}

// Stage 5 E4/E6: pick the right equip slot for a backpack item.
// Armor → driven by item.armor_coverage; weapons → driven by item.weapon_slot.
function _invPickEquipSlot(item, occupied) {
    const t = String(item.item_type || '').toLowerCase();
    if (t === 'armor') {
        const k = String(item.key || item.label || '').toLowerCase();
        if (/shield|tarcz/.test(k)) return 'off_hand';
        const cov = String(item.armor_coverage || '').toLowerCase();
        if (cov === 'head') return 'head';
        if (cov === 'hands') return 'hands';   // #743: rękawice → slot dłoni, nie torso
        if (cov === 'limb_arm') return occupied.l_arm ? 'r_arm' : 'l_arm';
        if (cov === 'limb_leg') return occupied.l_leg ? 'r_leg' : 'l_leg';
        if (cov === 'full') return 'torso';
        return 'torso';
    }
    if (t === 'weapon') {
        // Stage 5 follow-up: respect weapon_slot enum.
        const ws = String(item.weapon_slot || 'main_hand').toLowerCase();
        if (ws === 'two_handed')    return 'main_hand';
        if (ws === 'off_hand_only') return 'off_hand';
        // #863: 'either' do off_hand TYLKO gdy lekka (finesse); ciężka → zawsze main.
        if (ws === 'either')        return (occupied.main_hand && item.is_light === true) ? 'off_hand' : 'main_hand';
        return 'main_hand';
    }
    return null;
}

// Stage 5 E6: only show weapons in the right slot when filtering.
function _itemFitsSlot__weapon(item, slot) {
    const ws = String(item.weapon_slot || 'main_hand').toLowerCase();
    if (slot === 'main_hand') return ws === 'main_hand' || ws === 'two_handed' || ws === 'either';
    // #863: off_hand = tarcze/buklery (off_hand_only) + LEKKIE bronie 'either'. Ciężka 'either' → tylko main.
    if (slot === 'off_hand')  return ws === 'off_hand_only' || (ws === 'either' && item.is_light === true);
    return false;
}

// Pre-existing helper continues below — left intact.
function _invPickEquipSlot__legacy(item, occupied) {
    const t = String(item.item_type || '').toLowerCase();
    if (t === 'weapon') {
        if (!occupied.main_hand) return 'main_hand';
        if (!occupied.off_hand)  return 'off_hand';
        return 'main_hand';
    }
    return null;
}

function _invIsUsable(item) {
    const t = String(item.item_type || '').toLowerCase();
    if (t === 'weapon' || t === 'armor') return true;  // equippable
    return item.can_use === true;                       // consumable / ammo (#764)
}

// ── Spells Tab (Scholar) ──────────────────────────────────────────────────────

async function renderSpellsTab(character, sheet) {
    const listEl = document.getElementById('sheet-spells-list');
    const summaryEl = document.getElementById('spells-mana-summary');
    if (!listEl) return;
    if (sheet.archetype !== 'scholar') { listEl.innerHTML = ''; return; }

    const mana = sheet.current_mana ?? 0;
    const maxMana = sheet.max_mana ?? 0;
    const ap = sheet.arcane_points ?? 0;
    if (summaryEl) {
        summaryEl.innerHTML = `
            <div class="spell-resource">
                <span class="spell-resource__label">Mana</span>
                <span class="spell-resource__val">${mana} / ${maxMana}</span>
            </div>
            <div class="spell-resource">
                <span class="spell-resource__label">Punkty Arkanów</span>
                <span class="spell-resource__val">${ap}</span>
            </div>`;
    }

    try {
        const resp = await apiRequest('GET', `/characters/${character.id}/spells`);
        const spells = resp.spells || [];
        if (!spells.length) {
            listEl.innerHTML = '<p class="sheet-lore-text">Brak wyuczonych zaklęć.</p>';
            return;
        }
        const TYPE_ICONS = { attack:'⚔', heal:'💚', defense:'🛡', effect:'✨', attack_aoe:'💥', narrative:'🕯' };
        const currentMana = sheet.current_mana ?? 0;
        listEl.innerHTML = spells.map(s => {
            const icon = TYPE_ICONS[s.spell_type] || '✨';
            const rankPips = Array.from({length: 3}, (_, i) =>
                `<span class="spell-rank-pip${i < (s.rank || 1) ? ' active' : ''}"></span>`
            ).join('');
            const isOffensive = s.spell_type === 'attack' || s.spell_type === 'attack_aoe';
            const manaOk = (s.mana_cost || 0) === 0 || currentMana >= (s.mana_cost || 0);
            let castBtn;
            if (isOffensive) {
                castBtn = `<button class="spell-card__cast-btn spell-card__cast-btn--combat-only" disabled title="Tylko w walce — użyj panelu walki">⚔ w walce</button>`;
            } else if (combatActive) {
                castBtn = `<button class="spell-card__cast-btn spell-card__cast-btn--combat-only" disabled title="Jesteś w walce — użyj przycisku Zaklęcie w panelu walki">↕ panel walki</button>`;
            } else if (!manaOk) {
                castBtn = `<button class="spell-card__cast-btn spell-card__cast-btn--nomana" disabled title="Za mało many">🔮 mana</button>`;
            } else {
                const btnLabel = s.spell_type === 'narrative' ? 'Użyj' : s.spell_type === 'heal' ? 'Lecz' : 'Rzuć';
                castBtn = `<button class="spell-card__cast-btn" data-spell-key="${escapeHtml(s.spell_key)}" title="Rzuć zaklęcie">🔮 ${btnLabel}</button>`;
            }
            return `<div class="spell-card">
                <div class="spell-card__header">
                    <span class="spell-card__icon">${icon}</span>
                    <span class="spell-card__name">${escapeHtml(s.label || s.spell_key)}</span>
                    <span class="spell-card__mana">🔮 ${s.mana_cost}</span>
                </div>
                <div class="spell-card__meta">
                    ${s.damage_die ? `<span class="spell-card__die">⚔ ${escapeHtml(s.damage_die)}</span>` : ''}
                    ${s.heal_die ? `<span class="spell-card__die heal">💚 ${escapeHtml(s.heal_die)}</span>` : ''}
                    <span class="spell-card__ranks" title="Ranga">${rankPips}</span>
                </div>
                ${s.description ? `<p class="spell-card__desc">${escapeHtml(s.description)}</p>` : ''}
                <div class="spell-card__actions">${castBtn}</div>
            </div>`;
        }).join('');
        listEl.querySelectorAll('.spell-card__cast-btn:not(:disabled)').forEach(btn => {
            // #653: async handler — disable button for the duration of the spell cast
            // (animation holds ~4s; without this a fast double-click double-casts).
            btn.addEventListener('click', async () => {
                btn.disabled = true;
                try { await castSpellOutOfCombat(btn.dataset.spellKey); }
                finally { btn.disabled = false; }
            });
        });
    } catch {
        listEl.innerHTML = '<p class="sheet-lore-text">Błąd ładowania zaklęć.</p>';
    }
}

async function renderInventoryTab(character) {
    if (!character?.id) return;

    // Fetch live inventory + gold from dedicated endpoints (sheet_json doesn't include them)
    let items = [];
    let goldGp = 0;
    try {
        const [invResp, goldResp] = await Promise.all([
            fetch(`/api/inventory/${character.id}`).then(r => r.json()).catch(() => ({})),
            fetch(`/api/characters/${character.id}/gold`).then(r => r.json()).catch(() => ({})),
        ]);
        if (invResp?.ok && Array.isArray(invResp.data)) items = invResp.data;
        if (goldResp?.ok && goldResp.data?.gold_gp != null) goldGp = goldResp.data.gold_gp;
    } catch (e) {
        console.warn('[inventory] fetch failed:', e);
    }

    // Gold tally
    elements.sheetGold.innerHTML = `
        <div class="inv-gold__icon" aria-hidden="true">G</div>
        <div class="inv-gold__label">Złoto</div>
        <div class="inv-gold__value">${goldGp}</div>
        <div class="inv-gold__unit">zł</div>
    `;
    pulseGoldOnChange(goldGp);  // S9

    // Stage 5 E4-E7: bucket items + compute synthetic slot coverage for full-armor anchors.
    const equipped = {};   // slot → item (real slot OR synthetic locked-by-full)
    const lockedByFull = {}; // slot → anchor item (so the UI shows a chain)
    const backpack = [];
    const lore = [];
    const occupied = { head: false, torso: false, l_arm: false, r_arm: false,
                       l_leg: false, r_leg: false, main_hand: false, off_hand: false };

    // U16: odśwież cache trwałości założonej broni/zbroi (dla ostrzeżenia w HUD walki).
    const _eqDura = { weapon: null, armor: null };
    let _foundShield = false;  // SF2 (#620): status tarczy dla gatingu „Blok"
    for (const item of items) {
        if (Number(item.equipped) === 1 && item.slot) {
            equipped[item.slot] = item;
            occupied[item.slot] = true;
            if (item.durability) {
                const t = String(item.item_type || '').toLowerCase();
                if (t === 'weapon' && !_eqDura.weapon) _eqDura.weapon = { ...item.durability, label: item.label };
                if (t === 'armor' && !_eqDura.armor) _eqDura.armor = { ...item.durability, label: item.label };
            }
            if (String(item.slot) === 'off_hand' &&
                (String(item.item_type || '').toLowerCase() === 'armor' ||
                 /shield|tarcz/.test(String(item.item_key || item.label || '').toLowerCase()))) {
                _foundShield = true;
            }
            // Full-coverage armor: stamp the limb slots as locked.
            for (const cs of (item.covered_slots || [])) {
                if (cs !== item.slot) {
                    lockedByFull[cs] = item;
                    occupied[cs] = true;
                }
            }
        } else if (_invIsUsable(item)) {
            backpack.push(item);
        } else {
            lore.push(item);
        }
    }
    _equippedDurability = _eqDura;
    _equippedShield = _foundShield;  // SF2 (#620)
    if (combatActive && lastCombatState) renderCombatUI(lastCombatState);  // odśwież gating „Blok" po zmianie ekwipunku

    // Stage 5 E7: gather body-part wound conditions from sheet.
    const woundSet = _collectWoundSet();

    // E5: anatomical diagram
    renderAnatomyDiagram(equipped, lockedByFull, woundSet);

    // Stage 5 E6: backpack filter — when user clicks an empty slot, only items
    // equippable in that slot are shown. _inventoryFilter is module-scope so it
    // survives equip actions (which re-render the tab).
    const filter = _inventoryFilter;
    const filteredBackpack = filter ? backpack.filter(it => _itemFitsSlot(it, filter)) : backpack;

    // Backpack
    const bpCount = document.getElementById('inv-backpack-count');
    const bpList = document.getElementById('sheet-backpack');
    if (bpCount) bpCount.textContent = backpack.length;
    if (bpList) {
        const filterPill = filter
            ? `<div class="anatomy-filter-pill">
                 Filtr: <strong>${escapeHtml(_slotLabel(filter))}</strong>
                 <button type="button" class="anatomy-filter-pill__clear" data-action="clear-filter" aria-label="Wyczyść filtr">✕</button>
               </div>`
            : '';
        const body = filteredBackpack.length
            ? filteredBackpack.map(item => _renderBackpackRow(item, occupied)).join('')
            : `<div class="inv-empty">${filter ? 'Brak przedmiotów pasujących do tego slotu' : 'Plecak jest pusty'}</div>`;
        bpList.innerHTML = filterPill + body;
    }

    // Lore — #1088: grouped by category into collapsible <details> sections
    const loreCount = document.getElementById('inv-lore-count');
    const loreList = document.getElementById('sheet-lore');
    if (loreCount) loreCount.textContent = lore.length;
    if (loreList) {
        loreList.innerHTML = lore.length
            ? _renderLoreGrouped(lore)
            : `<div class="inv-empty">Brak przedmiotów nieużywalnych</div>`;
    }

    _wireInventoryActions();
    _wireItemView();
}

// Stage 5 E6: per-render backpack filter — slot key set by clicking an empty slot.
let _inventoryFilter = null;

function _slotLabel(key) {
    const d = INV_SLOT_DEFS.find(x => x.key === key);
    return d ? d.label : key;
}

// Wound conditions affecting body parts — read from sheet.conditions.
function _collectWoundSet() {
    const out = new Set();
    try {
        const sheet = currentCharacter?.sheet_json || characterData?.sheet_json || {};
        const conditions = sheet?.conditions || [];
        for (const c of conditions) {
            const key = (typeof c === 'string' ? c : (c?.key || c?.label || '')).toString().toLowerCase();
            if (key) out.add(key);
        }
    } catch (_e) {}
    return out;
}

// Stage 5 E6 (+ follow-up): check whether a backpack item is equippable in a given slot.
function _itemFitsSlot(item, slot) {
    const t = String(item.item_type || '').toLowerCase();
    if (t === 'weapon') return _itemFitsSlot__weapon(item, slot);
    if (t !== 'armor') return false;
    const cov = String(item.armor_coverage || '').toLowerCase();
    if (slot === 'head')               return cov === 'head';
    if (slot === 'torso')              return cov === 'torso' || cov === 'full';
    if (slot === 'l_arm' || slot === 'r_arm') return cov === 'limb_arm' || cov === 'full';
    if (slot === 'l_leg' || slot === 'r_leg') return cov === 'limb_leg' || cov === 'full';
    if (slot === 'hands')              return cov === 'hands';
    return false;
}

// Stage 5 E5/E7: anatomical diagram renderer.
function renderAnatomyDiagram(equipped, lockedByFull, woundSet) {
    const host = document.getElementById('sheet-anatomy');
    if (!host) return;

    const cards = INV_SLOT_DEFS.map(def => _renderAnatomySlot(def, equipped[def.key], lockedByFull[def.key], woundSet)).join('');

    // Central decorative element — heraldic warrior silhouette in golden line-art.
    const silhouette = `
        <svg class="anatomy__silhouette" viewBox="0 0 60 120" aria-hidden="true">
          <!-- Head -->
          <circle cx="30" cy="14" r="8" />
          <!-- Torso -->
          <path d="M16 26 L44 26 L42 64 L18 64 Z" />
          <!-- Belt -->
          <line x1="18" y1="60" x2="42" y2="60" />
          <!-- Spine accent -->
          <line x1="30" y1="26" x2="30" y2="64" stroke-dasharray="2 3" />
          <!-- Arms -->
          <path d="M16 28 L8  56 L11 70" />
          <path d="M44 28 L52 56 L49 70" />
          <!-- Legs -->
          <path d="M22 64 L20 110" />
          <path d="M38 64 L40 110" />
          <!-- Heraldic crest -->
          <path d="M27 36 L30 32 L33 36 L33 46 L30 50 L27 46 Z" class="anatomy__crest" />
        </svg>`;

    host.innerHTML = `
        <div class="anatomy__frame">
          ${silhouette}
          <div class="anatomy__grid">${cards}</div>
        </div>`;
}

function _renderAnatomySlot(def, item, lockingAnchor, woundSet) {
    const wounded = (def.wound || []).some(k => woundSet.has(k));
    // A slot is "locked by full" when a full-coverage anchor is equipped on
    // a different slot and this slot is in its covered list.
    const isLockedByFull = !item && !!lockingAnchor;
    const isFiltering = _inventoryFilter === def.key;

    const classes = ['anatomy-slot', `anatomy-slot--${def.area}`];
    if (item)            classes.push('anatomy-slot--filled');
    else if (isLockedByFull) classes.push('anatomy-slot--locked');
    else                 classes.push('anatomy-slot--empty');
    if (wounded)         classes.push('anatomy-slot--wounded');
    if (isFiltering)     classes.push('anatomy-slot--filtering');

    let body, action;
    if (item) {
        const slotDura = item.durability ? _durabilityBarHTML(item.durability, { compact: true }) : '';
        body = `<div class="anatomy-slot__name">${escapeHtml(item.label || item.key || '?')}</div>${slotDura}`;
        action = `<button type="button" class="anatomy-slot__unequip" data-action="unequip" data-inventory-id="${item.id}" title="Zdejmij">✕</button>`;
    } else if (isLockedByFull) {
        const lockKind = (lockingAnchor?.item_type || '').toLowerCase() === 'weapon'
            ? 'Zajęte przez broń oburęczną'
            : 'Cz. pełnej zbroi';
        body = `<div class="anatomy-slot__name anatomy-slot__name--locked">
                  <span class="anatomy-slot__chain">${INV_ICONS.chain}</span>
                  <span>${lockKind}</span>
                </div>`;
        action = '';
    } else {
        body = `<div class="anatomy-slot__name anatomy-slot__name--empty">—</div>`;
        action = '';
    }

    const woundDecoration = wounded
        ? `<span class="anatomy-slot__blood" aria-label="rana">${INV_ICONS.blood}</span>`
        : '';

    return `
        <div class="${classes.join(' ')}"
             data-slot="${def.key}"
             ${item ? `data-inventory-id="${item.id}"` : ''}
             ${!item && !isLockedByFull ? 'data-action="filter-slot"' : ''}
             role="button" tabindex="0">
          <div class="anatomy-slot__head">
            <span class="anatomy-slot__icon">${INV_ICONS[def.icon] || ''}</span>
            <span class="anatomy-slot__type">${def.label}</span>
            ${woundDecoration}
          </div>
          ${body}
          ${action}
        </div>`;
}

// U16 (#564) — pasek trwałości. d = {current,max,pct,broken,penalty_pct} albo null.
// Tylko pokazuje stan z mechaniki (Zasady 1-5) — nic nie zmienia.
function _durabilityBarHTML(d, opts = {}) {
    if (!d) return '';
    const pct = Math.max(0, Math.min(100, Number(d.pct) || 0));
    const tier = d.broken ? 'broken' : (pct <= 20 ? 'low' : (pct <= 50 ? 'mid' : 'high'));
    const label = d.broken
        ? `Pęknięta (−${d.penalty_pct}%)`
        : `Trwałość ${d.current}/${d.max}`;
    return `
        <div class="dura ${opts.compact ? 'dura--compact' : ''}" title="${escapeHtml(label)}">
            <div class="dura__bar"><div class="dura__fill dura__fill--${tier}" style="width:${pct}%"></div></div>
            ${opts.compact ? '' : `<div class="dura__label dura__label--${tier}">${escapeHtml(label)}</div>`}
        </div>`;
}

// U16 — cache trwałości założonej broni/zbroi, żeby HUD walki mógł ostrzec przy ≤20%
// bez dodatkowego zapytania na każdy render. Odświeżane przy renderze ekwipunku i po turze.
let _equippedDurability = { weapon: null, armor: null };

async function refreshEquippedDurability() {
    if (!characterData?.id) return;
    try {
        const resp = await fetch(`/api/inventory/${characterData.id}`).then(r => r.json());
        if (!resp?.ok || !Array.isArray(resp.data)) return;
        const next = { weapon: null, armor: null };
        for (const it of resp.data) {
            if (Number(it.equipped) !== 1 || !it.durability) continue;
            const t = String(it.item_type || '').toLowerCase();
            if (t === 'weapon' && !next.weapon) next.weapon = { ...it.durability, label: it.label };
            if (t === 'armor' && !next.armor) next.armor = { ...it.durability, label: it.label };
        }
        _equippedDurability = next;
    } catch (_e) { /* best effort */ }
}

function _renderBackpackRow(item, occupied) {
    const kind = _invIconKind(item);
    const t = String(item.item_type || '').toLowerCase();
    const canEquip = t === 'weapon' || t === 'armor';
    const canUse = t === 'consumable' && !!item.can_use;
    const slot = canEquip ? _invPickEquipSlot(item, occupied) : null;
    const qty = item.quantity > 1 ? `<span class="inv-row__qty">×${item.quantity}</span>` : '';

    let action = '';
    if (canEquip && slot) {
        action = `<button type="button" class="inv-equip-btn" data-action="equip" data-inventory-id="${item.id}" data-slot="${slot}">Załóż</button>`;
    } else if (canUse) {
        action = `<button type="button" class="inv-equip-btn inv-equip-btn--use" data-action="use" data-inventory-id="${item.id}">Użyj</button>`;
    }

    const dura = (item.durability && (canEquip)) ? _durabilityBarHTML(item.durability, { compact: true }) : '';
    const iconContent = item.image_url
        ? `<img src="${escapeHtml(item.image_url)}" alt="" loading="lazy" onerror="this.style.display='none'">`
        : INV_ICONS[kind];
    const dropBtn = `<button type="button" class="inv-row__drop-btn" data-action="drop" data-inventory-id="${item.id}" title="Wyrzuć przedmiot">✕</button>`;
    return `
        <div class="inv-row" data-inventory-id="${item.id}">
            <div class="inv-row__icon">${iconContent}</div>
            <div class="inv-row__info">
                <div class="inv-row__name">${escapeHtml(item.label || item.key || '?')}${qty}</div>
                ${dura}
            </div>
            <div class="inv-row__actions">${action}${dropBtn}</div>
        </div>`;
}

// #1088: category classification — mirrors inventory_category.py lore_category_key()
const _LORE_CATS = {
    scrolls: { label: 'Zwoje i pergaminy', icon: INV_ICONS.scroll },
    books:   { label: 'Księgi i traktaty', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>` },
    keys:    { label: 'Klucze', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>` },
    quest:   { label: 'Przedmioty fabularne', icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>` },
    misc:    { label: 'Inne przedmioty', icon: INV_ICONS.pack },
};
const _CAT_ORDER = ['scrolls', 'books', 'keys', 'quest', 'misc'];

function _loreCategoryKey(item) {
    const lab = String(item.label || item.key || '');
    const t   = String(item.item_type || '').toLowerCase();
    if (/pergamin|zwój|zwoj|list|pismo|manuskrypt|skrawek|świstek|swistek|kartka|notatka|wiadomość|wiadomosc|rozkaz|ulotka|liścik|liscik|doniesienie|raport|wypis|przepustka|zezwolenie|dokument/i.test(lab)) return 'scrolls';
    if (/księga|ksiega|książka|ksiazka|kodeks|kronika|traktat|tome|zapis|dziennik|pamiętnik|pamietnik|grimuar|grimoire|atlas|bestiariusz/i.test(lab)) return 'books';
    if (/klucz/i.test(lab)) return 'keys';
    if (t === 'quest') return 'quest';
    return 'misc';
}

function _stackLoreItems(items) {
    const map = new Map();
    for (const item of items) {
        const key = String(item.label || item.key || '').toLowerCase().trim();
        if (map.has(key)) {
            const ex = map.get(key);
            ex.quantity = (ex.quantity || 1) + (item.quantity || 1);
        } else {
            map.set(key, { ...item, quantity: item.quantity || 1 });
        }
    }
    return [...map.values()];
}

function _renderLoreGrouped(lore) {
    const groups = {};
    for (const item of lore) {
        const cat = _loreCategoryKey(item);
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(item);
    }
    const sessionKey = 'lore-cat-open';
    let openCats;
    try { openCats = new Set(JSON.parse(sessionStorage.getItem(sessionKey) || '[]')); }
    catch (_) { openCats = new Set(); }

    const parts = [];
    for (const cat of _CAT_ORDER) {
        const items = groups[cat];
        if (!items || !items.length) continue;
        const stacked = _stackLoreItems(items);
        const meta = _LORE_CATS[cat] || _LORE_CATS.misc;
        const isOpen = openCats.has(cat) || cat === 'misc';
        const rows = stacked.map(item => _renderLoreRow(item, cat)).join('');
        parts.push(`
            <details class="lore-group" data-lore-cat="${cat}"${isOpen ? ' open' : ''}>
                <summary class="lore-group__header">
                    <span class="lore-group__icon">${meta.icon}</span>
                    <span class="lore-group__label">${meta.label}</span>
                    <span class="lore-group__count">×${stacked.length}</span>
                    <span class="lore-group__chevron" aria-hidden="true">▾</span>
                </summary>
                <div class="lore-group__body">${rows}</div>
            </details>`);
    }
    return parts.join('') || '<div class="inv-empty">Brak przedmiotów</div>';
}

// #1088: persist open/closed state in sessionStorage
document.addEventListener('toggle', (ev) => {
    const el = ev.target.closest?.('.lore-group');
    if (!el) return;
    const cat = el.dataset.loreCat;
    if (!cat) return;
    const key = 'lore-cat-open';
    let set;
    try { set = new Set(JSON.parse(sessionStorage.getItem(key) || '[]')); }
    catch (_) { set = new Set(); }
    el.open ? set.add(cat) : set.delete(cat);
    sessionStorage.setItem(key, JSON.stringify([...set]));
}, true);

function _renderLoreRow(item, cat) {
    const qty = item.quantity > 1 ? `<span class="inv-row__qty">×${item.quantity}</span>` : '';
    // D5 (#380): old hover tooltip removed — the click-to-open detail modal replaces it
    // (was duplicating the description with the new modal).
    // Stage 4 S7: quest items can never be dropped — story-critical, no escape hatch.
    const isQuest = item.item_type === 'quest' || item.is_quest === true;
    const dropBtn = !isQuest
        ? `<button class="inv-row__drop-btn" data-action="drop" data-inventory-id="${item.id}" title="Wyrzuć przedmiot">✕</button>`
        : '';
    // #1088: use item image_url if present, else category icon, else generic scroll
    const catIcon = (cat && _LORE_CATS[cat]) ? _LORE_CATS[cat].icon : INV_ICONS.scroll;
    const iconContent = item.image_url
        ? `<img src="${escapeHtml(item.image_url)}" alt="" loading="lazy" onerror="this.style.display='none'">`
        : catIcon;
    return `
        <div class="inv-row" data-inventory-id="${item.id}">
            <div class="inv-row__icon">${iconContent}</div>
            <div class="inv-row__info">
                <div class="inv-row__name">${escapeHtml(item.label || item.key || '?')}${qty}</div>
                ${item.description ? `<div class="inv-row__desc">${escapeHtml(item.description)}</div>` : ''}
            </div>
            ${dropBtn}
        </div>`;
}

// D5 (#380) — Item VIEW: click an inventory row/slot to see full detail.
function _wireItemView() {
    document.querySelectorAll('#tab-inventory [data-inventory-id]').forEach(el => {
        if (el.__viewWired) return;
        el.__viewWired = true;
        el.style.cursor = 'pointer';
        el.addEventListener('click', async (ev) => {
            // Action buttons (Załóż / Użyj / Zdejmij / Wyrzuć) keep their own handlers.
            if (ev.target.closest('[data-action]')) return;
            const id = parseInt(el.dataset.inventoryId, 10);
            if (!id || !characterData?.id) return;
            try {
                const r = await fetch(`/api/inventory/${characterData.id}/${id}/detail`);
                const j = await r.json();
                if (j && j.ok && j.data) _showItemDetailModal(j.data);
            } catch (e) {
                console.warn('[item-view] fetch failed', e);
            }
        });
    });
}

function _showItemDetailModal(d) {
    document.getElementById('item-view-modal')?.remove();
    const typePl = { weapon: 'Broń', armor: 'Zbroja', consumable: 'Mikstura',
                     quest: 'Przedmiot fabularny', misc: 'Przedmiot', narrative: 'Przedmiot' };
    const rows = [];
    rows.push(['Typ', typePl[d.item_type] || d.item_type || '—']);
    if (d.weapon && d.weapon.damage_die) {
        rows.push(['Obrażenia', d.weapon.damage_die + (d.weapon.attack_bonus ? ` (+${d.weapon.attack_bonus})` : '')]);
        if (d.weapon.linked_stat) rows.push(['Statystyka', d.weapon.linked_stat]);
    }
    if (d.armor) {
        rows.push(['Pancerz (AC)', '+' + (d.armor.ac_bonus || 0)]);
        if (d.armor.coverage) rows.push(['Pokrycie', d.armor.coverage]);
    }
    if (d.consumable) {
        const eff = [d.consumable.effect_type, d.consumable.effect_dice,
                     d.consumable.effect_bonus ? `+${d.consumable.effect_bonus}` : '']
                    .filter(Boolean).join(' ');
        if (eff) rows.push(['Efekt', eff]);
        if (d.consumable.effect_target) rows.push(['Cel', d.consumable.effect_target]);
    }
    if (d.value_gp != null) rows.push(['Wartość', d.value_gp + ' GP']);
    if (d.quantity > 1) rows.push(['Ilość', '×' + d.quantity]);
    if (d.note) rows.push(['Notatka', d.note]);

    const statRows = rows.map(([k, v]) =>
        `<div style="display:flex;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.06)">
            <span style="color:#9aa">${escapeHtml(k)}</span>
            <span style="color:#eee;text-align:right">${escapeHtml(String(v))}</span>
         </div>`).join('');

    const _EFFECT_LABELS = {
        damage_bonus: v => `+${v} obrażeń`,
        heal_on_hit: v => `Leczenie ${v} HP przy trafieniu`,
        ac_bonus: v => `+${v} do AC`,
        static_stat_modifier: (v, e) => `${e.stat || '?'} ${v > 0 ? '+' : ''}${v}`,
        apply_condition: (v, e) => `Nakłada: ${e.condition_key || '?'}${e.duration_rounds ? ` (${e.duration_rounds}r)` : ''}`,
        narrative_only: () => 'Efekt narracyjny',
    };
    const affixHtml = (d.affixes && d.affixes.length > 0)
        ? `<div style="margin-top:12px;border-top:1px solid rgba(245,158,11,.15);padding-top:10px">
            <div style="color:#f5a623;font-size:.75rem;font-weight:600;letter-spacing:.05em;margin-bottom:6px">AFIKSY</div>
            ${d.affixes.map(a => {
                const fx = (a.effects || []).map(e => {
                    const fn = _EFFECT_LABELS[e.type];
                    return fn ? fn(e.value, e) : e.type;
                }).filter(Boolean).join(', ');
                return `<div style="display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.04)">
                    <span style="color:#f5c842;font-size:.85rem">${escapeHtml(a.name)}</span>
                    ${fx ? `<span style="color:#aaa;font-size:.8rem;text-align:right">${escapeHtml(fx)}</span>` : ''}
                </div>`;
            }).join('')}
           </div>`
        : '';

    const overlay = document.createElement('div');
    overlay.id = 'item-view-modal';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px';
    const itemImgHtml = d.image_url
        ? `<img src="${escapeHtml(d.image_url)}" alt="" loading="lazy" style="width:100%;max-height:180px;object-fit:cover;border-radius:8px;margin-bottom:12px;display:block">`
        : '';
    overlay.innerHTML = `
        <div style="background:#14141c;border:1px solid rgba(245,158,11,.25);border-radius:12px;max-width:420px;width:100%;padding:18px;box-shadow:0 10px 40px rgba(0,0,0,.5)">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:8px">
                <div style="font-size:1.05rem;font-weight:700;color:#f5deb3">${escapeHtml(d.name || '?')}</div>
                <button id="item-view-close" style="background:none;border:none;color:#999;font-size:1.2rem;cursor:pointer;line-height:1">✕</button>
            </div>
            ${itemImgHtml}
            ${d.description ? `<div style="color:#bbb;font-size:.88rem;line-height:1.5;margin-bottom:12px">${escapeHtml(d.description)}</div>` : ''}
            <div>${statRows}</div>
            ${d.durability ? `<div style="margin-top:12px">${_durabilityBarHTML(d.durability)}</div>` : ''}
            ${affixHtml}
            <div id="item-actions" style="margin-top:14px"></div>
        </div>`;
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#item-view-close').addEventListener('click', () => overlay.remove());
    document.body.appendChild(overlay);
    // U16 (#564): cost-preview dla naprawy + kuźni afiksów — dociągamy ceny async.
    _populateItemActions(d, overlay);
}

// U16 (#564) — okno sklepu (kup/sprzedaj) + cost-preview + komunikat anti-farm.
async function openShopModal(npcKey) {
    if (!characterData?.id) return;
    document.getElementById('shop-modal')?.remove();
    let data = null;
    try {
        const r = await fetch(`/api/shop/by-key/${encodeURIComponent(npcKey)}?character_id=${characterData.id}`);
        const j = await r.json();
        if (j?.ok) data = j.data;
    } catch (_e) { /* ignore */ }
    if (!data) { showToast('Handlarz nie ma teraz nic na sprzedaż', 'error'); return; }

    // S6 (#586): badge rabatu/narzutu z targowania (haggle_discount > 0 = taniej).
    const _hg = Number(data.haggle_discount) || 0;
    const haggleBadge = _hg
        ? `<div style="margin:6px 18px 0;padding:5px 10px;border-radius:8px;font-size:.82rem;font-weight:600;${_hg > 0 ? 'background:rgba(34,197,94,.15);color:#4ade80;border:1px solid rgba(34,197,94,.35)' : 'background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.35)'}">${_hg > 0 ? '🤝 −' + Math.round(_hg * 100) + '% po targowaniu (jednorazowo)' : '😠 +' + Math.round(-_hg * 100) + '% — kupiec urażony'}</div>`
        : '';

    const overlay = document.createElement('div');
    overlay.id = 'shop-modal';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px';
    overlay.innerHTML = `
        <div style="background:#14141c;border:1px solid rgba(245,158,11,.3);border-radius:12px;max-width:560px;width:100%;max-height:88vh;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.6)">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;padding:16px 18px 8px">
                <div style="font-size:1.05rem;font-weight:700;color:#f5deb3">🏪 ${escapeHtml(data.npc?.label || 'Handlarz')}</div>
                <button id="shop-close" style="background:none;border:none;color:#999;font-size:1.3rem;cursor:pointer;line-height:1">✕</button>
            </div>
            <div style="padding:0 18px;display:flex;align-items:center;gap:8px;color:#f5c842;font-size:.9rem">
                <span>Twoje złoto:</span><strong id="shop-gold">${data.character_gold}</strong><span>zł</span>
            </div>
            ${haggleBadge}
            <div style="display:flex;gap:6px;padding:10px 18px 0">
                <button id="shop-tab-buy" class="shop-tab shop-tab--active" data-tab="buy">Kup</button>
                <button id="shop-tab-sell" class="shop-tab" data-tab="sell">Sprzedaj</button>
            </div>
            <div id="shop-body" style="overflow-y:auto;padding:12px 18px 18px;flex:1"></div>
        </div>`;
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#shop-close').addEventListener('click', () => overlay.remove());
    document.body.appendChild(overlay);

    let _gold = Number(data.character_gold) || 0;
    const goldEl = overlay.querySelector('#shop-gold');
    const bodyEl = overlay.querySelector('#shop-body');
    const setGold = (g) => { _gold = g; if (goldEl) goldEl.textContent = g; };

    const renderBuy = () => {
        const items = data.items || [];
        bodyEl.innerHTML = items.length ? items.map((it, i) => {
            const price = Number(it.buy_price_gp ?? it.value_gp ?? 0);
            const after = _gold - price;
            const afford = after >= 0;
            return `<div class="shop-row">
                <div class="shop-row__info">
                    <div class="shop-row__name">${escapeHtml(it.label || it.key)}</div>
                    <div class="shop-row__preview">${price} zł → zostanie ${after} zł</div>
                </div>
                <button class="shop-buy-btn" data-i="${i}" ${afford ? '' : 'disabled'}>${afford ? 'Kup' : 'Za mało'}</button>
            </div>`;
        }).join('') : '<div class="inv-empty">Handlarz nie ma nic na sprzedaż</div>';
        bodyEl.querySelectorAll('.shop-buy-btn').forEach(b => b.addEventListener('click', async () => {
            const it = items[Number(b.dataset.i)];
            b.disabled = true;
            try {
                const r = await fetch(`/api/shop/${data.npc.id}/buy`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ character_id: characterData.id, item_type: it.type, item_key: it.key }),
                });
                const j = await r.json();
                if (!r.ok) throw new Error(j.detail || 'Nie udało się kupić');
                setGold(j.data.gold_gp);
                showToast(`Kupiono: ${it.label} za ${j.data.paid_gp} zł`, 'success');
                await refreshCharacterData();
                renderBuy();
            } catch (e) { showToast(e.message || 'Błąd zakupu', 'error'); b.disabled = false; }
        }));
    };

    const renderSell = () => {
        const items = data.sell_items || [];
        bodyEl.innerHTML = items.length ? items.map((it, i) => {
            const price = Number(it.sell_price_gp ?? 0);
            const after = _gold + price;
            const qty = it.quantity > 1 ? ` ×${it.quantity}` : '';
            return `<div class="shop-row">
                <div class="shop-row__info">
                    <div class="shop-row__name">${escapeHtml(it.label || it.key)}${qty}</div>
                    <div class="shop-row__preview">+${price} zł → razem ${after} zł</div>
                </div>
                <button class="shop-sell-btn" data-i="${i}" ${price > 0 ? '' : 'disabled'}>${price > 0 ? 'Sprzedaj' : '—'}</button>
            </div>`;
        }).join('') : '<div class="inv-empty">Nie masz nic do sprzedania</div>';
        bodyEl.querySelectorAll('.shop-sell-btn').forEach(b => b.addEventListener('click', async () => {
            const it = items[Number(b.dataset.i)];
            b.disabled = true;
            try {
                const r = await fetch(`/api/shop/${data.npc.id}/sell`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ character_id: characterData.id, inventory_id: it.inventory_id }),
                });
                const j = await r.json();
                if (!r.ok) throw new Error(j.detail || 'Nie udało się sprzedać');
                const d = j.data;
                setGold(d.gold_gp);
                if (d.oversupply) {
                    showToast(`Cena obniżona (nadpodaż): ${d.base_sell_gp} zł → ${d.earned_gp} zł. Handlarz kupił już ${d.recent_sell_count} szt. w ciągu doby.`, 'warning');
                } else {
                    showToast(`Sprzedano: ${it.label} za ${d.earned_gp} zł`, 'success');
                }
                // odśwież listę sprzedaży z serwera (ilości się zmieniły)
                try {
                    const rr = await fetch(`/api/shop/by-key/${encodeURIComponent(npcKey)}?character_id=${characterData.id}`);
                    const jj = await rr.json();
                    if (jj?.ok) { data.sell_items = jj.data.sell_items; data.items = jj.data.items; }
                } catch (_e) { /* keep old */ }
                await refreshCharacterData();
                renderSell();
            } catch (e) { showToast(e.message || 'Błąd sprzedaży', 'error'); b.disabled = false; }
        }));
    };

    const tabBuy = overlay.querySelector('#shop-tab-buy');
    const tabSell = overlay.querySelector('#shop-tab-sell');
    tabBuy.addEventListener('click', () => { tabBuy.classList.add('shop-tab--active'); tabSell.classList.remove('shop-tab--active'); renderBuy(); });
    tabSell.addEventListener('click', () => { tabSell.classList.add('shop-tab--active'); tabBuy.classList.remove('shop-tab--active'); renderSell(); });
    renderBuy();
}

// U16 (#564) — dociąga ceny naprawy i kuźni afiksów; wstawia karty akcji z podglądem kosztu.
async function _populateItemActions(d, overlay) {
    const host = overlay.querySelector('#item-actions');
    if (!host || !characterData?.id) return;
    const cid = characterData.id;
    const isGear = d.item_type === 'weapon' || d.item_type === 'armor';
    if (!isGear) return;

    let gold = 0;
    try {
        const g = await apiRequest('GET', `/characters/${cid}/gold`);
        if (g?.ok && g.data?.gold_gp != null) gold = g.data.gold_gp;
        else if (g?.gold_gp != null) gold = g.gold_gp;
    } catch (_e) { /* ignore */ }

    const cards = [];

    // ── Naprawa ──
    if (d.durability && (d.durability.broken || Number(d.durability.pct) < 100)) {
        try {
            const r = await apiRequest('GET', `/characters/${cid}/inventory/${d.id}/repair-cost`);
            if (r && r.ok && Number(r.cost) > 0) {
                const after = gold - r.cost;
                const afford = after >= 0;
                cards.push(`
                    <div class="item-action-card">
                        <div class="item-action-card__title">🔧 Naprawa</div>
                        <div class="item-action-card__preview">Koszt ${r.cost} zł → zostanie ${after} zł (${r.missing_pts} pkt)</div>
                        <button class="item-action-btn" data-act="repair" ${afford ? '' : 'disabled'}>${afford ? 'Napraw' : 'Za mało złota'}</button>
                    </div>`);
            }
        } catch (_e) { /* skip */ }
    }

    // ── Kuźnia afiksów ──
    try {
        const a = await apiRequest('GET', `/characters/${cid}/inventory/${d.id}/affix-costs`);
        if (a && a.ok) {
            const apply = a.apply_costs || {};
            const applyBtns = Object.keys(apply).map(tier => {
                const cost = apply[tier]; const after = gold - cost; const afford = after >= 0;
                return `<button class="item-action-btn item-action-btn--sm" data-act="apply" data-tier="${tier}" data-cost="${cost}" ${afford ? '' : 'disabled'}>T${tier}: ${cost} zł → ${after}</button>`;
            }).join('');
            const existing = (a.current_affixes || []).map(af => {
                const rr = af.reroll_cost != null ? `<button class="item-action-btn item-action-btn--sm" data-act="reroll" data-affix="${escapeHtml(af.affix_key)}" data-cost="${af.reroll_cost}" ${gold >= af.reroll_cost ? '' : 'disabled'}>Reroll ${af.reroll_cost} zł → ${gold - af.reroll_cost}</button>` : '';
                const up = af.upgrade_cost != null ? `<button class="item-action-btn item-action-btn--sm" data-act="upgrade" data-affix="${escapeHtml(af.affix_key)}" data-cost="${af.upgrade_cost}" ${gold >= af.upgrade_cost ? '' : 'disabled'}>Ulepsz ${af.upgrade_cost} zł → ${gold - af.upgrade_cost}</button>` : '';
                return (rr || up) ? `<div class="item-action-card__row"><span class="item-action-card__affix">${escapeHtml(af.affix_key)}</span>${rr}${up}</div>` : '';
            }).join('');
            cards.push(`
                <div class="item-action-card">
                    <div class="item-action-card__title">⚒ Kuźnia afiksów</div>
                    <div class="item-action-card__preview">Nałóż nowy afiks:</div>
                    <div class="item-action-card__btns">${applyBtns}</div>
                    ${existing}
                </div>`);
        }
    } catch (_e) { /* skip */ }

    host.innerHTML = cards.join('');

    const refreshAfter = async () => {
        overlay.remove();
        renderInventoryTab(characterData);
        try {
            const rr = await apiRequest('GET', `/inventory/${cid}/${d.id}/detail`);
            if (rr?.ok && rr.data) _showItemDetailModal(rr.data);
        } catch (_e) { /* ignore */ }
    };

    host.querySelectorAll('[data-act]').forEach(btn => btn.addEventListener('click', async () => {
        const act = btn.dataset.act;
        btn.disabled = true;
        try {
            let body, url;
            if (act === 'repair') {
                url = `/characters/${cid}/repair-item`; body = { inventory_id: d.id };
            } else if (act === 'apply') {
                url = `/characters/${cid}/craft/apply-affix`; body = { inventory_id: d.id, tier: Number(btn.dataset.tier) };
            } else if (act === 'reroll') {
                url = `/characters/${cid}/craft/reroll-affix`; body = { inventory_id: d.id, affix_key: btn.dataset.affix };
            } else if (act === 'upgrade') {
                url = `/characters/${cid}/craft/upgrade-affix`; body = { inventory_id: d.id, affix_key: btn.dataset.affix };
            }
            await apiRequest('POST', url, body);
            showToast(act === 'repair' ? 'Naprawiono!' : 'Gotowe!', 'success');
            await refreshAfter();
        } catch (e) { showToast(e.message || 'Błąd', 'error'); btn.disabled = false; }
    }));
}

// ── #400 — Admin spectator + resume ──────────────────────────────────────────
async function _openAdminSpectator() {
    const uid = currentUser?.id;
    if (!uid) return;
    document.getElementById('admin-spectate-modal')?.remove();
    const overlay = document.createElement('div');
    overlay.id = 'admin-spectate-modal';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;z-index:9998;padding:16px';
    overlay.innerHTML = `
      <div style="background:#14141c;border:1px solid rgba(245,158,11,.25);border-radius:12px;max-width:560px;width:100%;max-height:85vh;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.5)">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;padding:16px 18px 8px">
          <div style="font-size:1.05rem;font-weight:700;color:#f5deb3">🛡 Kampanie (admin)</div>
          <button id="admin-spectate-close" style="background:none;border:none;color:#999;font-size:1.2rem;cursor:pointer">✕</button>
        </div>
        <div style="padding:0 18px 10px;display:flex;align-items:center;gap:8px">
          <label style="color:#9aa;font-size:.8rem">Gracz:</label>
          <div id="admin-spectate-user-dd" style="flex:1;position:relative">
            <button type="button" id="asp-user-trigger" style="width:100%;display:flex;justify-content:space-between;align-items:center;gap:8px;background:#0e0e16;border:1px solid rgba(255,255,255,.12);color:#eee;border-radius:8px;padding:9px 12px;cursor:pointer;font-size:.85rem">
              <span id="asp-user-label">—</span><span style="color:#888">▾</span>
            </button>
            <div id="asp-user-options" style="display:none;position:absolute;top:calc(100% + 4px);left:0;right:0;background:#14141c;border:1px solid rgba(245,158,11,.25);border-radius:8px;max-height:240px;overflow-y:auto;z-index:10;box-shadow:0 8px 24px rgba(0,0,0,.6)"></div>
          </div>
        </div>
        <div id="admin-spectate-list" style="overflow-y:auto;padding:4px 18px 18px;flex:1">
          <div style="color:#888;text-align:center;padding:20px">Ładowanie…</div>
        </div>
      </div>`;
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#admin-spectate-close').addEventListener('click', () => overlay.remove());
    document.body.appendChild(overlay);

    try {
        const ru = await fetch(`/api/admin-spectate/users?admin_user_id=${uid}`);
        const ju = await ru.json();
        _aspRenderUserDropdown(overlay, ju.users || [], uid);
    } catch (e) { console.warn('[admin-spectate] users', e); }

    _adminSpectateLoad(uid); // default = own
}

// Custom dark dropdown (native <select> opens an OS picker that clashes with the theme).
function _aspRenderUserDropdown(overlay, users, selectedId) {
    const trigger = overlay.querySelector('#asp-user-trigger');
    const label = overlay.querySelector('#asp-user-label');
    const opts = overlay.querySelector('#asp-user-options');
    if (!trigger || !label || !opts) return;
    const nameOf = (u) => (u.display_name || ('user ' + u.id)) + (u.is_admin ? ' (admin)' : '');
    const cur = users.find(u => Number(u.id) === Number(selectedId)) || users[0];
    if (cur) label.textContent = nameOf(cur);
    opts.innerHTML = users.map(u =>
        `<div data-uid="${u.id}" style="padding:10px 12px;cursor:pointer;color:#eee;font-size:.85rem;border-bottom:1px solid rgba(255,255,255,.05)">${escapeHtml(nameOf(u))}</div>`).join('');
    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        opts.style.display = opts.style.display === 'none' ? 'block' : 'none';
    });
    document.addEventListener('click', () => { opts.style.display = 'none'; });
    opts.querySelectorAll('[data-uid]').forEach(o => o.addEventListener('click', (e) => {
        e.stopPropagation();
        const u = users.find(x => Number(x.id) === Number(o.dataset.uid));
        if (!u) return;
        label.textContent = nameOf(u);
        opts.style.display = 'none';
        _adminSpectateLoad(u.id);
    }));
}

async function _adminSpectateLoad(userId) {
    const uid = currentUser?.id;
    const listEl = document.getElementById('admin-spectate-list');
    if (!listEl) return;
    listEl.innerHTML = '<div style="color:#888;text-align:center;padding:20px">Ładowanie…</div>';
    try {
        const r = await fetch(`/api/admin-spectate/campaigns?admin_user_id=${uid}&user_id=${userId}`);
        const j = await r.json();
        const camps = j.campaigns || [];
        if (!camps.length) { listEl.innerHTML = '<div style="color:#888;text-align:center;padding:20px">Brak kampanii</div>'; return; }
        listEl.innerHTML = camps.map(c => {
            const hero = c.character_name ? escapeHtml(c.character_name) : '—';
            const meta = `${escapeHtml(c.owner_name || '?')} · ${hero} · tura ${c.last_turn || 0} · ${escapeHtml(c.status || '')}`;
            return `<div style="border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:10px 12px;margin-bottom:8px;background:#0e0e16">
                <div style="font-weight:600;color:#eee;font-size:.92rem">${escapeHtml(c.title || ('Kampania ' + c.id))} <span style="color:#777;font-weight:400;font-size:.78rem">#${c.id}</span></div>
                <div style="color:#8aa;font-size:.72rem;margin:3px 0 8px">${meta}</div>
                <div style="display:flex;gap:8px">
                  <button data-act="preview" data-id="${c.id}" style="flex:1;background:#1a2230;border:1px solid rgba(120,160,255,.3);color:#cde;border-radius:8px;padding:7px;cursor:pointer">👁 Podgląd</button>
                  <button data-act="resume" data-id="${c.id}" style="flex:1;background:#22301a;border:1px solid rgba(160,255,120,.3);color:#dfd;border-radius:8px;padding:7px;cursor:pointer">▶ Wznów</button>
                </div>
              </div>`;
        }).join('');
        listEl.querySelectorAll('[data-act]').forEach(b => b.addEventListener('click', () => {
            const id = parseInt(b.dataset.id, 10);
            if (b.dataset.act === 'preview') _adminSpectatePreview(id);
            else _adminSpectateResume(id);
        }));
    } catch (e) {
        listEl.innerHTML = `<div style="color:#e88;text-align:center;padding:20px">Błąd: ${escapeHtml(String(e.message || e))}</div>`;
    }
}

function _extractNarrativePreview(text) {
    try { const o = JSON.parse(text); return o.narrative || text; } catch { return text; }
}

async function _adminSpectatePreview(campaignId) {
    const uid = currentUser?.id;
    try {
        const r = await fetch(`/api/admin-spectate/campaigns/${campaignId}/view?admin_user_id=${uid}&limit=20`);
        const j = await r.json();
        const turns = j.turns || [];
        document.getElementById('admin-spectate-preview')?.remove();
        const ov = document.createElement('div');
        ov.id = 'admin-spectate-preview';
        ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.75);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px';
        const rows = turns.map(t => {
            const who = t.user_text ? `<div style="color:#9bd;font-size:.8rem;margin-top:10px">▸ ${escapeHtml(t.user_text)}</div>` : '';
            const gm = t.assistant_text ? `<div style="color:#ccc;font-size:.82rem;line-height:1.5">${escapeHtml(_extractNarrativePreview(t.assistant_text).slice(0, 600))}</div>` : '';
            return who + gm;
        }).join('');
        ov.innerHTML = `<div style="background:#14141c;border:1px solid rgba(245,158,11,.25);border-radius:12px;max-width:560px;width:100%;max-height:85vh;display:flex;flex-direction:column">
            <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 18px"><div style="color:#f5deb3;font-weight:700">${escapeHtml(j.campaign?.title || 'Podgląd')} <span style="color:#888;font-weight:400;font-size:.8rem">#${campaignId}</span> · tylko odczyt</div><button id="asp-close" style="background:none;border:none;color:#999;font-size:1.2rem;cursor:pointer">✕</button></div>
            <div style="overflow-y:auto;padding:0 18px 18px">${rows || '<div style="color:#888">Brak tur</div>'}</div>
          </div>`;
        ov.addEventListener('click', e => { if (e.target === ov) ov.remove(); });
        ov.querySelector('#asp-close').addEventListener('click', () => ov.remove());
        document.body.appendChild(ov);
    } catch (e) { showToast('Błąd podglądu', 'error'); }
}

async function _adminSpectateResume(campaignId) {
    const uid = currentUser?.id;
    if (!confirm('Wznowić tę kampanię? Bohater zostanie podpięty i kampania aktywowana.')) return;
    try {
        const r = await fetch(`/api/admin-spectate/campaigns/${campaignId}/resume?admin_user_id=${uid}`, { method: 'POST' });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(j.detail || 'resume failed');
        showToast('Kampania wznowiona — pojawi się na liście Twoich bohaterów.', 'success');
        document.getElementById('admin-spectate-modal')?.remove();
        if (typeof loadCampaigns === 'function') loadCampaigns();
    } catch (e) { showToast('Błąd wznawiania: ' + (e.message || e), 'error'); }
}

function _wireInventoryActions() {
    document.querySelectorAll('#tab-inventory [data-action]').forEach(btn => {
        if (btn.__wired) return;
        btn.__wired = true;
        btn.addEventListener('click', async (ev) => {
            const action = btn.dataset.action;
            // Stage 5 E6: filter-slot + clear-filter don't need a character / inventory id.
            if (action === 'filter-slot') {
                const slot = btn.dataset.slot;
                _inventoryFilter = (_inventoryFilter === slot) ? null : slot;
                renderInventoryTab(characterData);
                return;
            }
            if (action === 'clear-filter') {
                ev.stopPropagation();
                _inventoryFilter = null;
                renderInventoryTab(characterData);
                return;
            }
            const id = parseInt(btn.dataset.inventoryId, 10);
            if (!id || !characterData?.id) return;
            btn.disabled = true;
            try {
                if (action === 'drop') {
                    const itemName = btn.closest('.inv-row')?.querySelector('.inv-row__name')?.textContent?.trim() || 'przedmiot';
                    if (!window.confirm(`Wyrzucić „${itemName}"? Tej operacji nie można cofnąć.`)) {
                        btn.disabled = false;
                        return;
                    }
                    const r = await fetch(`/api/inventory/${characterData.id}/${id}`, {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                    });
                    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'błąd usuwania');
                    btn.closest('.inv-row')?.remove();
                    showToast('Przedmiot wyrzucony.', 'info');
                    await refreshCharacterData();
                    return;
                } else if (action === 'use') {
                    const r = await fetch(`/api/inventory/${characterData.id}/use`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ inventory_id: id }),
                    });
                    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'błąd użycia');
                } else {
                    const body = { inventory_id: id };
                    if (action === 'equip') body.slot = btn.dataset.slot;
                    const r = await fetch(`/api/inventory/${characterData.id}/equip`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body),
                    });
                    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'błąd ekwipowania');

                    if (action === 'equip') {
                        const slotEl = document.querySelector(`.inv-slot[data-slot="${btn.dataset.slot}"]`);
                        if (slotEl) {
                            slotEl.classList.add('inv-slot--just-equipped');
                            setTimeout(() => slotEl.classList.remove('inv-slot--just-equipped'), 750);
                        }
                    }
                }

                await refreshCharacterData();
                renderInventoryTab(characterData);
            } catch (err) {
                console.error('[inventory] action failed:', err);
                showToast(err?.message || 'Nie udało się zmienić ekwipunku', 'error');
                btn.disabled = false;
            }
        });
    });
}

// ============================================================================
// Settings Panel
// ============================================================================
let settingsOpenedAt = 0;

function toggleSettings() {
    isSettingsOpen = !isSettingsOpen;
    elements.settingsPanel.classList.toggle('settings-panel--open', isSettingsOpen);
    if (isSettingsOpen) {
        settingsOpenedAt = Date.now();
        setTimeout(() => {
            elements.overlay.classList.add('panel-overlay--active');
        }, 350);
    } else {
        elements.overlay.classList.toggle('panel-overlay--active', isSheetOpen);
    }
}

function closeSettings() {
    isSettingsOpen = false;
    elements.settingsPanel.classList.remove('settings-panel--open');
    if (!isSheetOpen && !isJournalOpen) {
        elements.overlay.classList.remove('panel-overlay--active');
    }
}

let journalOpenedAt = 0;

function toggleJournal() {
    isJournalOpen = !isJournalOpen;
    elements.journalPanel.classList.toggle('journal-panel--open', isJournalOpen);
    if (isJournalOpen) {
        journalOpenedAt = Date.now();
        if (isSettingsOpen) closeSettings();
        if (isSheetOpen) closeCharacterSheet();
        loadJournalContent(false);
        setTimeout(() => {
            elements.overlay.classList.add('panel-overlay--active');
        }, 350);
    } else {
        elements.overlay.classList.toggle('panel-overlay--active', isSheetOpen || isSettingsOpen);
    }
}

function closeJournal() {
    isJournalOpen = false;
    elements.journalPanel.classList.remove('journal-panel--open');
    if (!isSheetOpen && !isSettingsOpen) {
        elements.overlay.classList.remove('panel-overlay--active');
    }
}

// ── U19 (#571) — Recap "Poprzednio w Twojej przygodzie…" ────────────────────
// Card shown automatically on campaign entry after a >24h real gap (backend
// decides should_show). Read-only: it surfaces the saved summary + last turns +
// active quests, never calls the LLM.

let _recapShownForCampaign = null;  // avoid re-nagging within one session

async function fetchRecap(cid) {
    try {
        const r = await fetch(`/api/campaigns/${cid}/recap`, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {},
        });
        if (!r.ok) return null;
        return await r.json();
    } catch (_e) {
        return null;
    }
}

function renderRecapCard(data) {
    const gapEl = document.getElementById('recap-gap');
    const bodyEl = document.getElementById('recap-body');
    if (!gapEl || !bodyEl) return;

    const hrs = data.hours_since_last;
    if (hrs != null) {
        const days = Math.floor(hrs / 24);
        gapEl.textContent = days >= 1
            ? `Wróciłeś po ${days} ${days === 1 ? 'dniu' : 'dniach'} przerwy.`
            : 'Wróciłeś po dłuższej przerwie.';
    } else {
        gapEl.textContent = '';
    }

    const parts = [];
    if (data.summary) {
        parts.push(`<div class="recap-section">
            <h3 class="recap-section__title">Streszczenie</h3>
            <p class="recap-summary">${escapeHtml(data.summary)}</p>
        </div>`);
    }
    if (Array.isArray(data.recent_turns) && data.recent_turns.length) {
        const turns = data.recent_turns.slice().reverse().map(t => {
            const p = t.player ? `<p class="recap-turn__player">🗣 ${escapeHtml(t.player)}</p>` : '';
            const g = t.gm ? `<p class="recap-turn__gm">${escapeHtml(t.gm)}</p>` : '';
            return `<div class="recap-turn"><span class="recap-turn__num">Tura ${t.turn_number}</span>${p}${g}</div>`;
        }).join('');
        parts.push(`<div class="recap-section">
            <h3 class="recap-section__title">Ostatnio wydarzyło się</h3>
            ${turns}
        </div>`);
    }
    if (Array.isArray(data.active_quests) && data.active_quests.length) {
        const quests = data.active_quests.map(q =>
            `<li class="recap-quest"><strong>${escapeHtml(q.title || 'Zadanie')}</strong>${q.narrative ? ` — ${escapeHtml(q.narrative)}` : ''}</li>`
        ).join('');
        parts.push(`<div class="recap-section">
            <h3 class="recap-section__title">Aktywne zadania</h3>
            <ul class="recap-quests">${quests}</ul>
        </div>`);
    }
    if (!parts.length) {
        parts.push('<p class="recap-empty">Brak zapisanych wspomnień — po prostu graj dalej.</p>');
    }
    bodyEl.innerHTML = parts.join('');
}

function showRecapCard(data) {
    renderRecapCard(data);
    const ov = document.getElementById('recap-overlay');
    if (ov) ov.hidden = false;
}

function closeRecapCard() {
    const ov = document.getElementById('recap-overlay');
    if (ov) ov.hidden = true;
}

// Auto-trigger on entry: show only when backend says should_show and not yet
// shown for this campaign in this session.
async function maybeShowRecap(cid) {
    if (!cid || _recapShownForCampaign === cid) return;
    const data = await fetchRecap(cid);
    if (data && data.should_show) {
        _recapShownForCampaign = cid;
        showRecapCard(data);
    }
}

// Manual "Przypomnij mi" from the journal panel — always shows, even ≤24h.
async function openRecapManually() {
    const cid = currentCampaignId;
    if (!cid) return;
    const data = await fetchRecap(cid);
    if (data) {
        if (typeof closeJournal === 'function') closeJournal();
        showRecapCard(data);
    }
}

async function loadJournalContent(forceRegenerate) {
    const { journalBody, journalEmpty, journalLoading, journalBanner } = elements;
    const cid = currentCampaignId;

    console.log('[Journal] loadJournalContent', { cid, forceRegenerate, currentUser });

    if (!cid) {
        console.log('[Journal] no campaign id, showing empty');
        showJournalEmpty();
        return;
    }

    // U18 (#570): structured sections (Zadania / Wątki / Kronika) — read-only,
    // independent of the LLM recap below. Loaded in parallel, never blocks recap.
    loadJournalSections(cid);

    journalLoading.style.display = 'flex';
    journalBody.style.display = 'none';
    journalEmpty.style.display = 'none';
    journalBanner.style.display = 'none';

    try {
        let data;
        if (forceRegenerate) {
            const uid = currentUser?.id || currentUser?.user_id || 1;
            const qs = new URLSearchParams({ user_id: String(uid), persist: 'true', max_turns: '200' });
            const url = `/api/campaigns/${cid}/history/summary?${qs}`;
            console.log('[Journal] POST', url);
            const r = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {}) },
                body: '{}'
            });
            data = await r.json().catch(() => ({}));
            console.log('[Journal] POST response', r.status, data);
            if (!r.ok) {
                journalLoading.style.display = 'none';
                let errMsg = 'Nie udało się wygenerować nowego podsumowania.';
                const detail = data?.detail;
                if (typeof detail === 'string') {
                    errMsg = detail;
                } else if (detail && typeof detail === 'object') {
                    if (detail.message) errMsg = detail.message;
                    else if (detail.error) errMsg = detail.error;
                }
                if (r.status === 429) {
                    errMsg = `Cooldown: ${errMsg}`;
                } else if (r.status === 403) {
                    errMsg = `Brak uprawnień: ${errMsg} (jesteś userId=${uid}, kampania należy do innego użytkownika)`;
                } else if (r.status === 502) {
                    errMsg = `Błąd LLM: ${errMsg}`;
                }
                showJournalBanner(errMsg, 'error');
                const fb = await fetchSavedJournal(cid);
                if (fb) showJournalText(fb);
                else showJournalEmpty();
                return;
            }
        } else {
            const uid = currentUser?.id || currentUser?.user_id || 1;
            const qs = new URLSearchParams({ user_id: String(uid), stale_after_turns: '5' });
            const url = `/api/campaigns/${cid}/history/summary/ensure?${qs}`;
            console.log('[Journal] POST ensure', url);
            const r = await fetch(url, {
                method: 'POST',
                headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
            });
            data = await r.json().catch(() => ({}));
            console.log('[Journal] ensure response', r.status, data);
            if (!r.ok) {
                console.warn('[Journal] ensure failed, falling back to saved');
                const fb = await fetchSavedJournal(cid);
                journalLoading.style.display = 'none';
                if (fb) {
                    showJournalText(fb);
                } else {
                    showJournalEmpty();
                }
                return;
            }
        }

        journalLoading.style.display = 'none';
        const summary = data.summary;
        console.log('[Journal] summary value:', summary);
        if (summary && String(summary).trim()) {
            showJournalText(String(summary));
        } else {
            showJournalEmpty();
        }
    } catch (e) {
        console.error('[Journal] error:', e);
        journalLoading.style.display = 'none';
        showJournalEmpty();
    }
}

async function fetchSavedJournal(cid) {
    try {
        const qs = new URLSearchParams({ audience: 'player' });
        const r = await fetch(`/api/campaigns/${cid}/history/summary?${qs}`, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) return null;
        const s = data.summary;
        return (s && String(s).trim()) ? String(s) : null;
    } catch (_e) {
        return null;
    }
}

function showJournalText(text) {
    elements.journalBody.innerHTML = renderJournalMarkdown(text);
    elements.journalBody.style.display = 'block';
    elements.journalEmpty.style.display = 'none';
}

// ── U18 (#570): Dziennik gracza — structured sections ───────────────────────
async function loadJournalSections(cid) {
    const host = elements.journalSections;
    if (!host) return;
    try {
        const r = await fetch(`/api/campaigns/${cid}/journal`, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        if (!r.ok) { host.style.display = 'none'; return; }
        const data = await r.json().catch(() => null);
        if (!data) { host.style.display = 'none'; return; }
        renderJournalSections(data);
    } catch (e) {
        console.warn('[Journal] sections load failed', e);
        host.style.display = 'none';
    }
}

function renderJournalSections(data) {
    const host = elements.journalSections;
    if (!host) return;
    const quests = Array.isArray(data.quests) ? data.quests : [];
    const threads = Array.isArray(data.threads) ? data.threads : [];
    const chronicle = Array.isArray(data.chronicle) ? data.chronicle : [];

    if (!quests.length && !threads.length && !chronicle.length) {
        host.style.display = 'none';
        return;
    }

    const parts = [];

    // Zadania
    if (quests.length) {
        const items = quests.map(q => {
            const done = q.status === 'completed';
            const cls = done ? 'journal-quest journal-quest--done' : 'journal-quest';
            const mark = done ? '✓' : '◔';
            const narr = q.narrative ? `<div class="journal-quest__narr">${escapeHtml(q.narrative)}</div>` : '';
            return `<li class="${cls}"><span class="journal-quest__mark">${mark}</span><div><div class="journal-quest__title">${escapeHtml(q.title || '')}</div>${narr}</div></li>`;
        }).join('');
        parts.push(`<section class="journal-section"><h3 class="journal-section__title">📜 Zadania</h3><ul class="journal-list">${items}</ul></section>`);
    }

    // Wątki
    if (threads.length) {
        const items = threads.map(t => {
            const turn = t.turn ? `<span class="journal-thread__turn">tura ${t.turn}</span>` : '';
            return `<li class="journal-thread"><span class="journal-thread__hint">${escapeHtml(t.hint || '')}</span>${turn}</li>`;
        }).join('');
        parts.push(`<section class="journal-section"><h3 class="journal-section__title">🧵 Wątki</h3><ul class="journal-list">${items}</ul></section>`);
    }

    // Kronika
    if (chronicle.length) {
        const items = chronicle.map(e => {
            const icon = e.type === 'beat' ? '⭐' : '•';
            const turn = e.turn ? `<span class="journal-chron__turn">tura ${e.turn}</span>` : '';
            return `<li class="journal-chron"><span class="journal-chron__icon">${icon}</span><span class="journal-chron__text">${escapeHtml(e.text || '')}</span>${turn}</li>`;
        }).join('');
        parts.push(`<section class="journal-section"><h3 class="journal-section__title">📖 Kronika</h3><ul class="journal-list">${items}</ul></section>`);
    }

    host.innerHTML = parts.join('');
    host.style.display = 'block';
}

// Wound label — U15: derives from the single source of truth (WOUND_TIERS,
// served by /config/wound-thresholds; fallback _WOUND_TIERS_FALLBACK). So the
// player-facing label, its colour and the mechanical penalty never drift apart.
// Returns { label, tier, color } or null when HP > 75% (healthy, no label).
function getWoundLabel(currentHp, maxHp) {
    const hp = Math.max(0, Number(currentHp) || 0);
    const max = Math.max(1, Number(maxHp) || 1);
    const pct = (hp / max) * 100;
    const tiers = Array.isArray(_woundThresholds.tiers) ? _woundThresholds.tiers : _WOUND_TIERS_FALLBACK;
    let row = tiers.find(t => pct > t.min_pct) || tiers[tiers.length - 1];
    if (!row || !row.label) return null;
    return { label: row.label, tier: row.tier, color: row.color };
}

// Render markup for a wound label, or empty string when above threshold.
// Colour is taken inline from the tier (authoritative) so it stays correct even
// for tier keys without a dedicated CSS class; the tier class still drives the
// near_death animation hook.
function renderWoundLabelHTML(currentHp, maxHp) {
    const w = getWoundLabel(currentHp, maxHp);
    if (!w) return '';
    return `<div class="wound-label wound-label--${w.tier}" style="color:${w.color}" aria-label="${w.label}"><span class="wound-label__orn">❦</span><span class="wound-label__text">${w.label}</span><span class="wound-label__orn">❦</span></div>`;
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderInlineMarkdown(line) {
    let s = escapeHtml(line);
    s = s.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*([^*\n]+?)\*/g, '<em>$1</em>');
    s = s.replace(/__([^_\n]+?)__/g, '<strong>$1</strong>');
    s = s.replace(/_([^_\n]+?)_/g, '<em>$1</em>');
    s = s.replace(/`([^`\n]+?)`/g, '<code>$1</code>');
    return s;
}

function renderJournalMarkdown(text) {
    const lines = String(text).replace(/\r\n/g, '\n').split('\n');
    const html = [];
    let inList = false;
    let paragraph = [];

    const flushParagraph = () => {
        if (paragraph.length) {
            html.push(`<p>${paragraph.map(renderInlineMarkdown).join(' ')}</p>`);
            paragraph = [];
        }
    };
    const closeList = () => {
        if (inList) { html.push('</ul>'); inList = false; }
    };

    for (const raw of lines) {
        const line = raw.trim();
        if (!line) {
            flushParagraph();
            closeList();
            continue;
        }

        const h = line.match(/^(#{1,4})\s+(.+)$/);
        if (h) {
            flushParagraph();
            closeList();
            const lvl = Math.min(h[1].length + 1, 5);
            html.push(`<h${lvl} class="journal-h journal-h--${h[1].length}">${renderInlineMarkdown(h[2])}</h${lvl}>`);
            continue;
        }

        const bullet = line.match(/^[-*•]\s+(.+)$/);
        if (bullet) {
            flushParagraph();
            if (!inList) { html.push('<ul class="journal-list">'); inList = true; }
            html.push(`<li>${renderInlineMarkdown(bullet[1])}</li>`);
            continue;
        }

        if (inList) closeList();
        paragraph.push(line);
    }
    flushParagraph();
    closeList();
    return html.join('\n');
}

function showJournalEmpty() {
    elements.journalBody.style.display = 'none';
    elements.journalEmpty.style.display = 'flex';
}

function showJournalBanner(text, kind) {
    const el = elements.journalBanner;
    el.textContent = text;
    el.style.display = 'block';
    if (kind === 'error') {
        el.style.borderLeftColor = '#c62828';
        el.style.background = 'rgba(198,40,40,0.08)';
    } else {
        el.style.borderLeftColor = 'var(--gold)';
        el.style.background = 'rgba(201,165,74,0.06)';
    }
}

function initPanelSwipeDown(panel, closeFn) {
    if (!panel) return;
    let startY = 0;
    let currentY = 0;
    let dragging = false;
    let isDragClose = false;

    panel.addEventListener('touchstart', (e) => {
        startY = e.touches[0].clientY;
        currentY = startY;
        dragging = true;
        // Only start drag-to-close when content scroll is at the very top.
        // If user is scrolled down inside the panel, let native scroll handle it.
        const content = panel.querySelector('.sheet-panel__content');
        isDragClose = !content || content.scrollTop <= 0;
        if (isDragClose) panel.style.transition = 'none';
    }, { passive: true });

    panel.addEventListener('touchmove', (e) => {
        if (!dragging || !isDragClose) return;
        currentY = e.touches[0].clientY;
        const diff = currentY - startY;
        if (diff > 0) {
            panel.style.transform = `translateY(${diff}px)`;
        }
    }, { passive: true });

    panel.addEventListener('touchend', () => {
        if (!dragging) return;
        dragging = false;
        panel.style.transition = '';
        if (isDragClose) {
            const diff = currentY - startY;
            if (diff > 80) {
                panel.style.transform = '';
                closeFn();
            } else {
                panel.style.transform = '';
            }
        }
        startY = 0;
        currentY = 0;
        isDragClose = false;
    });
}

function initSheetTabSwipe(panel) {
    if (!panel) return;
    const content = panel.querySelector('.sheet-panel__content');
    if (!content) return;

    let startX = 0, startY = 0, moved = false;

    content.addEventListener('touchstart', (e) => {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        moved = false;
    }, { passive: true });

    content.addEventListener('touchmove', () => { moved = true; }, { passive: true });

    content.addEventListener('touchend', (e) => {
        if (!moved) return;
        const dx = e.changedTouches[0].clientX - startX;
        const dy = e.changedTouches[0].clientY - startY;
        if (Math.abs(dx) < 40 || Math.abs(dy) > Math.abs(dx)) return;

        // Build order from visible tabs only — handles dynamic spells tab (mage only)
        const visibleTabs = Array.from(panel.querySelectorAll('.sheet-tab'))
            .filter(el => el.offsetParent !== null);
        const activeTab = panel.querySelector('.sheet-tab--active');
        const currentIdx = visibleTabs.indexOf(activeTab);
        if (currentIdx === -1) return;

        const nextIdx = dx < 0
            ? Math.min(currentIdx + 1, visibleTabs.length - 1)
            : Math.max(currentIdx - 1, 0);
        if (nextIdx === currentIdx) return;

        visibleTabs[nextIdx]?.click();
    }, { passive: true });
}

function updateAdminSettingsVisibility() {
    const isAdmin = currentUser?.is_admin === 1 || currentUser?.is_admin === true;
    const adminSection = document.getElementById('admin-settings-section');
    const adminDivider = document.getElementById('admin-settings-divider');

    if (adminSection) adminSection.style.display = isAdmin ? 'block' : 'none';
    if (adminDivider) adminDivider.style.display = isAdmin ? 'flex' : 'none';

    // Stage 8 D3 — show the 🐛 toggle only when (admin) AND (debugMode on
    // via Settings → "🐛 Pokaż debug pod wiadomościami GM"). Hidden otherwise
    // to keep the production view clean.
    _refreshDebugToggleVisibility();

    // Tester bug-report FAB — show in game screen for is_tester=1 users
    _refreshBugReportFab();

    if (isAdmin) pollServiceHealth();
}

function _refreshDebugToggleVisibility() {
    const isAdmin = currentUser?.is_admin === 1 || currentUser?.is_admin === true;
    const dbgToggle = document.getElementById('debug-drawer-toggle');
    if (!dbgToggle) return;
    dbgToggle.hidden = !(isAdmin && debugMode);
    // If the toggle is hidden but the drawer is open, close it too.
    if (dbgToggle.hidden) {
        document.getElementById('debug-drawer')?.classList.remove('debug-drawer--open');
    }
    // B7 — DEV Inspector toggle mirrors same condition
    const inspToggle = document.getElementById('dev-inspector-toggle');
    if (inspToggle) inspToggle.hidden = !(isAdmin && debugMode);
}

// ── Tester bug-report FAB + modal ────────────────────────────────────────────

async function _refreshBugReportFab() {
    const fab = document.getElementById('bug-report-fab');
    if (!fab) return;
    // #668: odśwież is_tester z serwera (localStorage/JWT bywają nieaktualne po nadaniu flagi).
    // Lazy, raz na wejście do gry; błąd sieci → użyj tego co w currentUser.
    if (currentUser && currentUser._testerChecked !== true) {
        try {
            const me = await apiRequest('GET', '/auth/me');
            if (me && me.is_tester != null) {
                currentUser.is_tester = me.is_tester;
                try { localStorage.setItem('user', JSON.stringify(currentUser)); } catch {}
            }
            currentUser._testerChecked = true;
        } catch { /* offline / brak endpointu — degrade do bieżącego stanu */ }
    }
    const isTester = currentUser?.is_tester === 1 || currentUser?.is_tester === true;
    // #668: aktywny ekran ma klasę `screen--active` (nie `active`) — stary warunek
    // zawsze dawał false, więc FAB nigdy się nie pokazywał mimo is_tester=1.
    const onGameScreen = document.getElementById('game-screen')?.classList.contains('screen--active');
    fab.hidden = !(isTester && onGameScreen);
}

(function _initBugReportFab() {
    const fab = document.getElementById('bug-report-fab');
    const modal = document.getElementById('bug-report-modal');
    if (!fab || !modal) return;

    function openModal() {
        document.getElementById('bug-report-observation').value = '';
        document.getElementById('bug-report-reproduction').value = '';
        document.getElementById('bug-report-type').value = 'bug';
        document.getElementById('bug-report-status').textContent = '';
        const sc = document.getElementById('bug-report-screenshot');
        if (sc) sc.value = '';
        const prev = document.getElementById('bug-report-screenshot-preview');
        if (prev) prev.style.display = 'none';
        modal.style.display = 'flex';
    }

    // Compress screenshot to JPEG ≤800px, base64, before send.
    function _compressScreenshot(file) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    const MAX = 800;
                    let w = img.width, h = img.height;
                    if (w > MAX) { h = Math.round(h * MAX / w); w = MAX; }
                    const canvas = document.createElement('canvas');
                    canvas.width = w; canvas.height = h;
                    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                    resolve(canvas.toDataURL('image/jpeg', 0.72));
                };
                img.onerror = () => resolve(null);
                img.src = e.target.result;
            };
            reader.onerror = () => resolve(null);
            reader.readAsDataURL(file);
        });
    }

    const scInput = document.getElementById('bug-report-screenshot');
    scInput?.addEventListener('change', () => {
        const file = scInput.files?.[0];
        const prev = document.getElementById('bug-report-screenshot-preview');
        const img = document.getElementById('bug-report-screenshot-img');
        if (file && prev && img) {
            const url = URL.createObjectURL(file);
            img.src = url;
            img.onload = () => URL.revokeObjectURL(url);
            prev.style.display = 'block';
        } else if (prev) {
            prev.style.display = 'none';
        }
    });

    // #668: pionowe przeciąganie FAB — tester sam ustawia wysokość. Pozycja w localStorage.
    // Click otwiera modal tylko gdy NIE był to drag (ruch < progu).
    const FAB_POS_KEY = 'bugFabBottomPx';
    function clampBottom(px) {
        const min = 8, max = window.innerHeight - fab.offsetHeight - 8;
        return Math.max(min, Math.min(max, px));
    }
    try {
        const saved = parseFloat(localStorage.getItem(FAB_POS_KEY));
        if (!Number.isNaN(saved)) fab.style.bottom = clampBottom(saved) + 'px';
    } catch {}

    let dragging = false, moved = false, startY = 0, startBottom = 0;
    fab.addEventListener('pointerdown', e => {
        dragging = true; moved = false;
        startY = e.clientY;
        startBottom = parseFloat(getComputedStyle(fab).bottom) || 0;
        fab.setPointerCapture?.(e.pointerId);
    });
    fab.addEventListener('pointermove', e => {
        if (!dragging) return;
        const dy = startY - e.clientY; // w górę = większy bottom
        if (Math.abs(dy) > 4) moved = true;
        fab.style.bottom = clampBottom(startBottom + dy) + 'px';
    });
    function endDrag(e) {
        if (!dragging) return;
        dragging = false;
        fab.releasePointerCapture?.(e.pointerId);
        if (moved) {
            try { localStorage.setItem(FAB_POS_KEY, String(parseFloat(fab.style.bottom))); } catch {}
        }
    }
    fab.addEventListener('pointerup', endDrag);
    fab.addEventListener('pointercancel', endDrag);

    fab.addEventListener('click', () => { if (!moved) openModal(); });

    function closeModal() { modal.style.display = 'none'; }
    document.getElementById('bug-report-close')?.addEventListener('click', closeModal);
    document.getElementById('bug-report-cancel')?.addEventListener('click', closeModal);
    modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });

    document.getElementById('bug-report-submit')?.addEventListener('click', async () => {
        const observation = document.getElementById('bug-report-observation').value.trim();
        const reproduction = document.getElementById('bug-report-reproduction').value.trim();
        const report_type = document.getElementById('bug-report-type').value;
        const statusEl = document.getElementById('bug-report-status');
        const submitBtn = document.getElementById('bug-report-submit');

        if (!observation) {
            statusEl.style.color = '#e74c3c';
            statusEl.textContent = 'Opisz co się stało — pole jest wymagane.';
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = '⏳ Wysyłam…';
        statusEl.textContent = '';

        try {
            const campaign_id = currentCampaign?.id || null;
            const js_errors = window.clog?._state?.queue
                ?.filter(e => e.level === 'error')
                ?.slice(-5)
                ?.map(e => ({ message: e.message || e.event, filename: e.error?.filename, lineno: e.error?.lineno }))
                ?? [];

            const scFile = document.getElementById('bug-report-screenshot')?.files?.[0];
            const screenshot_base64 = scFile ? await _compressScreenshot(scFile) : null;

            const resp = await fetch('/api/bug-report', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`,
                },
                body: JSON.stringify({ observation, reproduction, report_type, campaign_id, js_errors, screenshot_base64 }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data?.detail || `HTTP ${resp.status}`);

            statusEl.style.color = '#2ecc71';
            statusEl.textContent = data.github_issue_url
                ? `✅ Zgłoszono! Issue: ${data.github_issue_url}`
                : '✅ Zgłoszenie zapisane. Dziękujemy!';
            submitBtn.textContent = '✓ Wysłano';
            setTimeout(() => { if (modal.style.display !== 'none') closeModal(); }, 2500);
        } catch (e) {
            statusEl.style.color = '#e74c3c';
            statusEl.textContent = `❌ Błąd: ${e.message}`;
            submitBtn.disabled = false;
            submitBtn.textContent = 'Wyślij zgłoszenie';
        }
    });
})();

// B7 — DEV Inspector modal for player UI (admin + debugMode)
let _inspectorModalTimer = null;

function _openInspectorModal() {
    if (!currentCampaignId) { alert('Brak aktywnej kampanii'); return; }
    const existing = document.getElementById('dev-inspector-modal');
    if (existing) { existing.remove(); if (_inspectorModalTimer) { clearInterval(_inspectorModalTimer); _inspectorModalTimer = null; } return; }

    const modal = document.createElement('div');
    modal.id = 'dev-inspector-modal';
    modal.style.cssText = 'position:fixed;top:60px;right:16px;width:380px;max-height:80vh;overflow-y:auto;background:#0f172a;border:1px solid #334155;border-radius:10px;z-index:9000;box-shadow:0 8px 32px rgba(0,0,0,0.6);font-family:monospace;font-size:0.78rem;color:#cbd5e1';
    modal.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid #334155;background:#1e293b;border-radius:10px 10px 0 0">
        <span style="font-weight:700;color:#94a3b8;font-size:0.75rem;text-transform:uppercase;letter-spacing:.06em">🔍 DEV Inspector</span>
        <button onclick="document.getElementById('dev-inspector-modal').remove();clearInterval(window._inspectorModalTimer);window._inspectorModalTimer=null" style="background:none;border:none;color:#64748b;cursor:pointer;font-size:1rem;padding:0 4px">✕</button>
      </div>
      <div id="dev-inspector-body" style="padding:12px">Ładowanie…</div>`;
    document.body.appendChild(modal);

    const _esc = s => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

    const _render = async () => {
        if (!document.getElementById('dev-inspector-modal')) { clearInterval(_inspectorModalTimer); _inspectorModalTimer = null; return; }
        try {
            const tok = localStorage.getItem('aigm_access_token');
            const r = await fetch(`/api/debug/campaigns/${currentCampaignId}/state`, {
                headers: tok ? { 'Authorization': `Bearer ${tok}` } : {}
            });
            if (!r.ok) { document.getElementById('dev-inspector-body').innerHTML = `<span style="color:#f87171">Błąd ${r.status} — brak uprawnień?</span>`; return; }
            const d = await r.json();
            const intent = d.intent || {};
            const ws = d.world_state || {};
            const gr = d.gate_result || {};
            const blocked = gr.blocked === true;
            const enemies = (ws.scene_enemies || []);
            const aliveEnemies = enemies.filter(e => (e.hp ?? null) !== null && (e.hp || 0) > 0);
            const spawnEnemies = enemies.filter(e => e.hp === null || e.hp === undefined);
            // #825: header label — distinguish "alive" (in combat, hp>0) from "spawned" (pre-combat, no hp)
            const wsLabel = ws.scene_cleared ? '✓ cleared'
              : aliveEnemies.length ? aliveEnemies.length + ' alive'
              : spawnEnemies.length ? spawnEnemies.length + ' spawned'
              : '—';
            document.getElementById('dev-inspector-body').innerHTML = `
              <div style="margin-bottom:10px">
                <div style="color:#64748b;font-size:0.68rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Intent</div>
                ${d.intent === null ? `<span style="color:#475569">Brak tur</span>` : `
                  <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
                    <span style="background:#1d4ed8;color:#bfdbfe;border-radius:4px;padding:1px 8px;font-weight:700">${_esc(intent.action_type||'?')}</span>
                    <span style="color:#475569">conf: ${((intent.confidence||0)*100).toFixed(0)}%</span>
                  </div>
                  ${intent.target ? `<div style="color:#64748b">→ <span style="color:#94a3b8">${_esc(intent.target)}</span></div>` : ''}
                  <div style="padding:4px 6px;background:#0a0f1e;border-radius:4px;color:#64748b;margin-top:2px;word-break:break-word">"${_esc((intent.raw_input||'').slice(0,100))}"</div>
                `}
              </div>
              <div style="margin-bottom:10px">
                <div style="color:#64748b;font-size:0.68rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Gate</div>
                <div style="display:flex;align-items:center;gap:6px">
                  <span style="background:${blocked?'#7f1d1d':'#14532d'};color:${blocked?'#fca5a5':'#86efac'};border-radius:4px;padding:1px 8px;font-weight:700">${blocked?'BLOCKED':'PASS'}</span>
                  ${gr.reason ? `<span style="color:#475569">${_esc(gr.reason)}</span>` : ''}
                </div>
                ${gr.feedback ? `<div style="color:#64748b;margin-top:2px">${_esc(gr.feedback)}</div>` : ''}
              </div>
              <div>
                <div style="color:#64748b;font-size:0.68rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">World State <span style="color:#334155;font-weight:400">${wsLabel}</span></div>
                <div style="display:flex;flex-direction:column;gap:2px">
                  <div><span style="color:#334155">Enemies:</span> ${enemies.length ? enemies.map(e=>`<span style="color:${(e.hp??null)===null?'#f59e0b':(e.hp||0)<=0?'#f87171':'#4ade80'}">${_esc(e.name||e.key||'?')}${(e.hp??null)===null?'(spawn)':'('+e.hp+')'}</span>`).join(' ') : '<span style="color:#334155">—</span>'}</div>
                  <div><span style="color:#334155">NPCs:</span> ${(ws.scene_npcs||[]).map(n=>_esc(n.name||n.key||'?')).join(', ')||'<span style="color:#334155">—</span>'}</div>
                  <div><span style="color:#334155">Quests:</span> ${(ws.active_quests||[]).length || '<span style="color:#334155">—</span>'}</div>
                </div>
              </div>
              ${(()=>{const c1=d.c1_debug||{};if(!Object.keys(c1).length)return'';const active=c1.story_stale_active;const n=c1.turns_at_location??0;const thr=c1.story_stale_threshold??5;return`<div style="margin-top:8px;border-top:1px solid #1e293b;padding-top:8px"><div style="color:#64748b;font-size:0.68rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">C1 STORY_STALE</div><div style="display:flex;flex-direction:column;gap:2px"><div><span style="color:#334155">Turns@loc:</span> <span style="color:${active?'#fbbf24':'#4ade80'};font-weight:700">${n}/${thr}</span>${active?' <span style="background:#78350f;color:#fde68a;border-radius:4px;padding:0 5px;font-size:0.7rem">AKTYWNY</span>':''}</div><div style="color:#475569;font-size:0.65rem">hex: ${c1.current_hex?`${c1.current_hex.q},${c1.current_hex.r}`:'—'} prev: ${c1.prev_turn_hex?`${c1.prev_turn_hex.q},${c1.prev_turn_hex.r}`:'—'}</div></div></div>`;})()}
              <div style="margin-top:8px;color:#1e293b;font-size:0.65rem;text-align:right">${new Date().toLocaleTimeString()}</div>`;
        } catch(e) {
            const body = document.getElementById('dev-inspector-body');
            if (body) body.innerHTML = `<span style="color:#f87171">Błąd: ${_esc(String(e))}</span>`;
        }
    };

    _render();
    window._inspectorModalTimer = setInterval(_render, 1000);
}

// Stage 9 P4 — Command palette modal.
// Single source of truth: SLASH_COMMANDS for top-level commands + DEBUG_CMD_TREE
// for /debug subcommands (admin only) + a curated /admin example subset.
// Opens via ⌘ button in composer OR Ctrl+/ keybinding. Closes on Esc / backdrop.
const _PALETTE_STATE = { items: [], filtered: [], highlighted: 0 };

function _buildPaletteItems() {
    const items = [];
    // Top-level slash commands
    for (const c of SLASH_COMMANDS) {
        if (c.adminOnly && !playerIsAdmin()) continue;
        items.push({
            label: c.cmd,
            desc: c.desc || '',
            insert: c.cmd + ' ',
            // Cursor offset from end (negative = backwards). 0 = end-of-line.
            cursorOffset: 0,
        });
    }
    // /debug subcommands when admin
    if (playerIsAdmin()) {
        for (const sub of Object.keys(DEBUG_CMD_TREE)) {
            const hint = DEBUG_CMD_HINTS[sub]?.hint || '';
            const ph = DEBUG_CMD_HINTS[sub]?.placeholder || '';
            items.push({
                label: `/debug ${sub}${ph ? ' ' + ph : ''}`,
                desc: hint,
                insert: `/debug ${sub}${ph ? ' ' : ''}`,
                cursorOffset: 0,
            });
        }
    }
    return items;
}

function _renderPaletteList() {
    const list = document.getElementById('cp-list');
    if (!list) return;
    if (_PALETTE_STATE.filtered.length === 0) {
        list.innerHTML = '<li class="command-palette__empty">Brak pasujących komend.</li>';
        return;
    }
    list.innerHTML = _PALETTE_STATE.filtered.map((item, i) => `
        <li class="command-palette__item ${i === _PALETTE_STATE.highlighted ? 'command-palette__item--active' : ''}"
            role="option"
            aria-selected="${i === _PALETTE_STATE.highlighted}"
            data-cp-index="${i}">
          <span class="command-palette__cmd">${escapeHtml(item.label)}</span>
          <span class="command-palette__desc">${escapeHtml(item.desc)}</span>
        </li>
    `).join('');
    // Scroll active row into view if needed
    const active = list.querySelector('.command-palette__item--active');
    if (active) active.scrollIntoView({ block: 'nearest' });
}

function _filterPalette(query) {
    const q = (query || '').toLowerCase().trim().replace(/^\//, '');
    if (!q) {
        _PALETTE_STATE.filtered = _PALETTE_STATE.items.slice();
    } else {
        _PALETTE_STATE.filtered = _PALETTE_STATE.items.filter(it => {
            const cmd = it.label.toLowerCase().replace(/^\//, '');
            return cmd.startsWith(q) || cmd.includes(q) || it.desc.toLowerCase().includes(q);
        });
    }
    _PALETTE_STATE.highlighted = 0;
    _renderPaletteList();
}

function openCommandPalette() {
    const modal = document.getElementById('command-palette');
    if (!modal) return;
    _PALETTE_STATE.items = _buildPaletteItems();
    _PALETTE_STATE.filtered = _PALETTE_STATE.items.slice();
    _PALETTE_STATE.highlighted = 0;
    const search = document.getElementById('cp-search');
    if (search) {
        search.value = '';
        search.focus();
    }
    modal.hidden = false;
    _renderPaletteList();
}
function closeCommandPalette() {
    const modal = document.getElementById('command-palette');
    if (modal) modal.hidden = true;
}
function _paletteAcceptCurrent() {
    const it = _PALETTE_STATE.filtered[_PALETTE_STATE.highlighted];
    if (!it) return;
    closeCommandPalette();
    const input = elements.chatInput;
    if (!input) return;
    input.value = it.insert;
    input.focus();
    // Place cursor after the inserted text minus any reserved offset.
    const pos = it.insert.length + (it.cursorOffset || 0);
    try { input.setSelectionRange(pos, pos); } catch {}
}

function _wirePaletteEvents() {
    document.getElementById('palette-btn')?.addEventListener('click', openCommandPalette);

    const modal = document.getElementById('command-palette');
    if (!modal) return;
    modal.addEventListener('click', (e) => {
        if (e.target.dataset?.cpAction === 'close') closeCommandPalette();
        const item = e.target.closest('[data-cp-index]');
        if (item) {
            _PALETTE_STATE.highlighted = parseInt(item.dataset.cpIndex, 10) || 0;
            _paletteAcceptCurrent();
        }
    });
    document.getElementById('cp-search')?.addEventListener('input', (e) => {
        _filterPalette(e.target.value);
    });
    document.getElementById('cp-search')?.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { e.preventDefault(); closeCommandPalette(); return; }
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            _PALETTE_STATE.highlighted = Math.min(_PALETTE_STATE.filtered.length - 1, _PALETTE_STATE.highlighted + 1);
            _renderPaletteList();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            _PALETTE_STATE.highlighted = Math.max(0, _PALETTE_STATE.highlighted - 1);
            _renderPaletteList();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            _paletteAcceptCurrent();
        }
    });

    // Global keybinding: Ctrl+/ (or Cmd+/ on macOS)
    document.addEventListener('keydown', (e) => {
        if (e.key === '/' && (e.ctrlKey || e.metaKey)) {
            const isModalOpen = !document.getElementById('command-palette')?.hidden;
            if (isModalOpen) { e.preventDefault(); closeCommandPalette(); return; }
            // Only open when game screen is active (palette is gameplay-oriented).
            if (currentScreen === 'game') {
                e.preventDefault();
                openCommandPalette();
            }
        }
    });
}

// Stage 8 D3+D4 — admin debug drawer.
// Lazy-mounted on first toggle; pulls from /api/debug/last-turn.
let _debugDrawerTab = 'state';
async function _toggleDebugDrawer() {
    let drawer = document.getElementById('debug-drawer');
    if (!drawer) {
        drawer = document.createElement('aside');
        drawer.id = 'debug-drawer';
        drawer.className = 'debug-drawer';
        drawer.innerHTML = `
          <header class="debug-drawer__header">
            <h3>🐛 Debug</h3>
            <div class="debug-drawer__actions">
              <button type="button" class="debug-drawer__refresh" data-action="refresh" title="Odśwież">↻</button>
              <button type="button" class="debug-drawer__copy" data-action="copy" title="Kopiuj aktywną sekcję">⧉</button>
              <button type="button" class="debug-drawer__close" data-action="close" title="Zamknij" aria-label="Zamknij">✕</button>
            </div>
          </header>
          <div class="debug-drawer__tabs" role="tablist">
            <button type="button" class="debug-tab debug-tab--active" data-tab="state">🌍 State</button>
            <button type="button" class="debug-tab" data-tab="intent">🎯 Intent</button>
            <button type="button" class="debug-tab" data-tab="mechanic">⚙ Mechanic</button>
            <button type="button" class="debug-tab" data-tab="llm">🤖 LLM</button>
            <button type="button" class="debug-tab" data-tab="narrator">📜 Narrator</button>
            <button type="button" class="debug-tab" data-tab="timing">⏱ Timing</button>
          </div>
          <pre class="debug-drawer__body" id="debug-drawer-body">Brak danych — wykonaj turę, aby zobaczyć debug.</pre>
        `;
        document.body.appendChild(drawer);
        drawer.addEventListener('click', _handleDebugDrawerClick);
    }
    drawer.classList.toggle('debug-drawer--open');
    if (drawer.classList.contains('debug-drawer--open')) {
        await _refreshDebugDrawer();
    }
}

function _handleDebugDrawerClick(e) {
    const action = e.target.dataset.action;
    const tab    = e.target.dataset.tab;
    if (action === 'close') {
        document.getElementById('debug-drawer')?.classList.remove('debug-drawer--open');
    } else if (action === 'refresh') {
        _refreshDebugDrawer();
    } else if (action === 'copy') {
        const body = document.getElementById('debug-drawer-body');
        if (body && navigator.clipboard) {
            navigator.clipboard.writeText(body.textContent || '').then(
                () => showToast('Skopiowane do schowka.', 'success'),
                () => showToast('Kopia nieudana.', 'error')
            );
        }
    } else if (tab) {
        _debugDrawerTab = tab;
        document.querySelectorAll('#debug-drawer .debug-tab').forEach(
            b => b.classList.toggle('debug-tab--active', b.dataset.tab === tab)
        );
        _renderDebugDrawerBody();
    }
}

let _debugDrawerSnapshot = null;
async function _refreshDebugDrawer() {
    const body = document.getElementById('debug-drawer-body');
    if (!body) return;
    if (!characterData?.id) {
        body.textContent = 'Brak aktywnego bohatera.';
        return;
    }
    body.textContent = 'Wczytywanie…';
    try {
        const r = await fetch(`/api/debug/last-turn?character_id=${characterData.id}&user_id=${currentUser?.id ?? ''}`);
        if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            body.textContent = `Błąd: ${err?.detail || r.status}`;
            return;
        }
        _debugDrawerSnapshot = await r.json();
        _renderDebugDrawerBody();
    } catch (e) {
        body.textContent = `Błąd: ${e.message || e}`;
    }
}

function _renderDebugDrawerBody() {
    const body = document.getElementById('debug-drawer-body');
    if (!body) return;
    const snap = _debugDrawerSnapshot;
    if (!snap) {
        body.textContent = 'Brak danych — wykonaj turę, aby zobaczyć debug.';
        return;
    }
    const tabMap = {
        state:     snap.game_state,
        intent:    snap.last_intent,
        mechanic:  snap.mechanic_result,
        llm:       snap.llm_prompts,
        narrator:  snap.narrator_output,
        timing:    snap.performance_timing,
    };
    const val = tabMap[_debugDrawerTab];
    if (val == null) {
        body.textContent = `(brak danych dla zakładki '${_debugDrawerTab}')`;
        return;
    }
    body.textContent = typeof val === 'string' ? val : JSON.stringify(val, null, 2);
}

let _healthPollTimer = null;

async function pollServiceHealth() {
    clearTimeout(_healthPollTimer);
    const setDot = (el, state, title) => {
        if (!el) return;
        el.className = `service-dot ${state}`;
        if (title) el.title = title;
    };
    try {
        const resp = await fetch('/api/health');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        setDot(elements.svcDotBackend, 'ok', 'Backend: OK');
        setDot(elements.svcDotLlm,
            data.llm?.reachable ? 'ok' : 'warn',
            `LLM: ${data.llm?.reachable ? 'OK' : 'niedostępny'}`
        );
        const loki = data.loki;
        if (!loki || loki.configured === false) {
            setDot(elements.svcDotLoki, 'unknown', 'Loki: nie skonfigurowany');
        } else if (loki.reachable) {
            setDot(elements.svcDotLoki, 'ok', 'Loki: OK');
        } else {
            setDot(elements.svcDotLoki, 'warn', `Loki: ${loki.error || 'niedostępny'}`);
        }
    } catch (_e) {
        setDot(elements.svcDotBackend, 'error', 'Backend: błąd połączenia');
        setDot(elements.svcDotLlm, 'error', 'LLM: nieznany');
        setDot(elements.svcDotLoki, 'unknown', 'Loki: nieznany');
    }
    _healthPollTimer = setTimeout(pollServiceHealth, 15000);
}

async function handleGoToCampaigns() {
    closeSettings();
    closeJournal();
    currentCampaignId = null;
    currentCampaign = null;
    characterData = null;
    await loadCampaigns();
    showScreen('campaigns');
}

// ============================================================================
// Death Screen
// ============================================================================
// Stage 9 P5 — Death screen with live LLM-generated epitaph from /api/campaigns/{id}/end-summary.
// Stage 11 R8 — cached resurrect-preview shape so the confirm modal can render
// the actual cost line ("Stracisz 250 PD") without a second fetch on click.
let _resurrectPreviewCache = null;

async function showDeathScreen(characterName) {
    const deathScreen = document.getElementById('death-screen');
    const nameElement = document.getElementById('death-character-name');
    const epitaphElement = document.getElementById('death-epitaph-text');

    if (nameElement && characterName) {
        nameElement.textContent = characterName;
    }

    if (deathScreen) {
        deathScreen.hidden = false;
        document.body.style.overflow = 'hidden';
        // Fade-in animation: opacity + letter-spacing collapse over 2s.
        if (epitaphElement) {
            epitaphElement.classList.remove('death-epitaph--lit');
            // Default placeholder while we fetch.
            epitaphElement.textContent = 'Ciemność pochłonęła kolejną duszę...';
        }
        // Pull the live epitaph from the backend (LLM-generated when death lands).
        if (currentCampaignId && epitaphElement) {
            try {
                const r = await fetch(`/api/campaigns/${currentCampaignId}/end-summary`);
                if (r.ok) {
                    const data = await r.json();
                    if (data?.outcome === 'death' && data?.epitaph) {
                        epitaphElement.textContent = data.epitaph;
                    }
                    _renderRunStats('death-stats', data?.stats);
                }
            } catch (_e) { /* keep default */ }
            // Trigger the fade-in animation after the text is in place.
            requestAnimationFrame(() => epitaphElement.classList.add('death-epitaph--lit'));
        }

        // Stage 11 R8 — un-hide #resurrect-btn only if admin enabled it for this user.
        const resBtn = document.getElementById('resurrect-btn');
        _resurrectPreviewCache = null;
        if (resBtn && characterData?.id) {
            resBtn.hidden = true;
            try {
                _resurrectPreviewCache = await apiRequest('GET', `/characters/${characterData.id}/resurrect-preview`);
                if (_resurrectPreviewCache?.enabled) {
                    resBtn.hidden = false;
                    resBtn.disabled = false;
                    resBtn.textContent = '✦ Wskrześ bohatera';
                }
            } catch (_e) { /* leave hidden */ }
        }
    }
}

// ─── SF9 (#638): różnicowany komunikat „dlaczego wskrzeszenie niedostępne" ───
// „Mechanika decyduje, LLM narruje": front CZYTA gotowy preview.reason z backendu (cost_preview),
// NIC nie liczy. Pure-helper (bez DOM) — mapuje reason → polski komunikat. Fallback bez wyjątku na null.
function sf9DisabledReason(preview) {
    switch (String(preview?.reason || '')) {
        case 'resurrection_disabled':
            return 'Wskrzeszenia wyłączone przez Mistrza Gry.';
        case 'no_uses_remaining':
            return 'Brak pozostałych wskrzeszeń.';
        default:
            return 'Wskrzeszenie nie jest dostępne dla tego konta.';
    }
}
// Wystaw na window dla kontraktu Playwright (funkcja deklarowana lokalnie nie trafia na window).
window.sf9DisabledReason = sf9DisabledReason;

function _formatResurrectCostLine(preview) {
    const cost = preview?.cost || {};
    switch (cost.mode) {
        case 'admin_free':
            return 'Wskrzeszenie nie będzie kosztować nic.';
        case 'gold_percent':
            return `Stracisz <strong>${cost.gold_lost} GP</strong> (${cost.percent}% z ${cost.current_gold} GP).`;
        case 'gold_recent_days':
            return `Stracisz <strong>${cost.gold_lost} GP</strong> — sumę zarobków z ostatnich ${cost.window_days} dni gry, ograniczoną do ${cost.cap_percent}% obecnego złota.`;
        case 'xp_revert': {
            const lines = [`Cofnięte zostanie <strong>${cost.xp_lost} PD</strong> (${cost.grants_count} ostatnich nadań).`];
            if ((cost.current_xp ?? 0) - (cost.xp_lost ?? 0) < 0) {
                lines.push('Twoja postać może spaść o poziom — straconych zostaną też zakupione w tym czasie awanse umiejętności i zaklęć.');
            }
            return lines.join(' ');
        }
        case 'item_loss':
            if (cost.fallback_to_free) {
                return 'Brak funkcjonalnych przedmiotów do utraty — wskrzeszenie będzie bezpłatne.';
            }
            return `Stracisz losowo wybrany przedmiot spośród ${cost.eligible_count} założonych funkcjonalnych przedmiotów.`;
        default:
            return 'Koszt zostanie obliczony.';
    }
}

// E3/E4 (#418/#419) — render the campaign run stats block on death/victory screens.
function _renderRunStats(elId, stats) {
    const el = document.getElementById(elId);
    if (!el) return;
    if (!stats) { el.hidden = true; return; }
    const items = [
        ['🎲', 'Tury', stats.turn_count ?? 0],
        ['💰', 'Złoto', stats.gold ?? 0],
        ['🧑', 'NPC poznani', stats.npcs_met ?? 0],
        ['📜', 'Questy ukończone', stats.quests_completed ?? 0],
    ];
    // #1016 — side-quest counter (X/Y zrobione). Hidden when no side quests (0/0).
    const sideTotal = stats.side_quests_total ?? 0;
    if (sideTotal > 0) {
        items.push(['🧭', 'Poboczne', `${stats.side_quests_completed ?? 0}/${sideTotal}`]);
    }
    el.innerHTML = items.map(([icon, label, val]) =>
        `<div class="run-stat"><span class="run-stat__icon">${icon}</span>` +
        `<span class="run-stat__val">${val}</span>` +
        `<span class="run-stat__label">${label}</span></div>`
    ).join('');
    el.hidden = false;
}

function hideDeathScreen() {
    const deathScreen = document.getElementById('death-screen');
    if (deathScreen) {
        deathScreen.hidden = true;
        document.body.style.overflow = '';
        document.getElementById('death-epitaph-text')?.classList.remove('death-epitaph--lit');
    }
}

// Stage 9 P6 — Victory screen (warm-gold mirror of death-screen).
async function showVictoryScreen() {
    const screen = document.getElementById('victory-screen');
    if (!screen) return;
    screen.hidden = false;
    document.body.style.overflow = 'hidden';
    if (!currentCampaignId) return;
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/end-summary`);
        if (!r.ok) return;
        const data = await r.json();
        if (data?.outcome !== 'victory') return;
        const nameEl  = document.getElementById('victory-character-name');
        const metaEl  = document.getElementById('victory-character-meta');
        const titleEl = document.getElementById('victory-ending-title');
        const sumEl   = document.getElementById('victory-ending-summary');
        if (nameEl)  nameEl.textContent  = data.character_name || 'Bohater';
        if (metaEl)  metaEl.textContent  = `${data.character_class || ''} · Poz. ${data.level || 1} · ${data.xp_lifetime_earned ?? 0} PD`;
        if (titleEl) titleEl.textContent = data.ending_title || '';
        if (sumEl)   sumEl.textContent   = data.ending_summary || '';
        // #1058: dynamic tone label based on ending type
        const toneEl = document.getElementById('victory-tone-label');
        if (toneEl) {
            const toneMap = { primary: 'triumfalnego końca', alternate: 'nieoczekiwanego końca', failure: 'gorzkiego końca' };
            toneEl.textContent = toneMap[data.ending_type] || 'niezwykłego końca';
        }
        _renderRunStats('victory-stats', data?.stats);
    } catch (_e) {}
}

function hideVictoryScreen() {
    const screen = document.getElementById('victory-screen');
    if (screen) {
        screen.hidden = true;
        document.body.style.overflow = '';
    }
}
// Exposed on window for manual testing — proper auto-trigger via [CAMPAIGN_END]
// tag is a separate task (see #62 Sub-phase 9-B / Stage 9 notes).
window.showVictoryScreen = showVictoryScreen;

// Stage 9 P5/P6 — preview commands.
// Mount the screens with sample data without hitting the backend or mutating DB.
// Useful for visual review and motion tuning. Triggered by /debug preview-death|preview-victory.
function _previewDeathScreen() {
    const heroName = characterData?.name || currentHero?.name || 'Bohater testowy';
    const epitaphElement = document.getElementById('death-epitaph-text');
    const nameElement = document.getElementById('death-character-name');
    const deathScreen = document.getElementById('death-screen');
    if (nameElement) nameElement.textContent = heroName;
    if (epitaphElement) {
        epitaphElement.classList.remove('death-epitaph--lit');
        epitaphElement.textContent =
            'Tu spoczywa imię, które wiatr już zapomniał. ' +
            'Ostrze zawiodło, kości się rozsypały, świece zgasły — ' +
            'a mrok wziął co swoje. Niech ziemia będzie mu lekka.';
    }
    if (deathScreen) {
        deathScreen.hidden = false;
        document.body.style.overflow = 'hidden';
        requestAnimationFrame(() => epitaphElement?.classList.add('death-epitaph--lit'));
    }
    showToast('👁 Podgląd: ekran śmierci (sample epitaph)', 'info', 2500);
}

function _previewVictoryScreen() {
    const heroName = characterData?.name || currentHero?.name || 'Bohater testowy';
    const sheet = characterData?.sheet_json || currentHero?.sheet_json || {};
    const arch = sheet.archetype || 'warrior';
    const level = (sheet.xp_lifetime_earned != null)
        ? Math.max(1, Math.min(10, Math.floor(Number(sheet.xp_lifetime_earned) / 100) + 1))
        : (sheet.level || 1);
    const xp = sheet.xp_lifetime_earned ?? 0;

    const screen = document.getElementById('victory-screen');
    if (!screen) return;
    const nameEl  = document.getElementById('victory-character-name');
    const metaEl  = document.getElementById('victory-character-meta');
    const titleEl = document.getElementById('victory-ending-title');
    const sumEl   = document.getElementById('victory-ending-summary');
    if (nameEl)  nameEl.textContent  = heroName;
    if (metaEl)  metaEl.textContent  = `${arch} · Poz. ${level} · ${xp} PD`;
    if (titleEl) titleEl.textContent = 'Świt nad Korytarzem Cieni';
    if (sumEl)   sumEl.textContent   =
        'Po długiej walce z mrokiem cieni, twój bohater odnalazł utracony ' +
        'Klucz Pradawnych. Ścieżka wiedzie dalej w nieznane, lecz dziś — ' +
        'tylko dziś — jest zwycięstwo. Tarcza spoczywa na ołtarzu, miecz na ziemi, ' +
        'a serce bije wreszcie spokojnie.';
    screen.hidden = false;
    document.body.style.overflow = 'hidden';
    showToast('👁 Podgląd: ekran zwycięstwa (sample ending)', 'info', 2500);
}
window._previewDeathScreen = _previewDeathScreen;
window._previewVictoryScreen = _previewVictoryScreen;

// Stage 9 P7 — Shared post-end options handler. Wired via data-end-action.
async function handleEndAction(action) {
    hideDeathScreen();
    hideVictoryScreen();
    const hero = currentHero || characterData;
    const sameWorldCampaign = currentCampaign;  // capture before clearing
    // Always free up campaign state — the player is moving on.
    currentCampaignId = null;
    currentCampaign = null;
    characterData = null;
    if (action === 'new-hero') {
        currentHero = null;
        await loadHeroes();
        showScreen('heroes');
        return;
    }
    if (action === 'new-world') {
        // Same hero, pick a different campaign.
        if (hero) {
            currentHero = hero;
            if (elements.welcomeUser) elements.welcomeUser.textContent = `Bohater: ${hero.name}`;
        }
        await loadCampaigns();
        showScreen('campaigns');
        return;
    }
    if (action === 'new-adventure') {
        // Same hero, same world theme — route to new-campaign screen so the
        // player can mint a fresh campaign keeping the world flavor. MVP: this
        // is the same as new-world for now; future work can pre-fill world tags.
        if (hero) {
            currentHero = hero;
            if (elements.welcomeUser) elements.welcomeUser.textContent = `Bohater: ${hero.name}`;
        }
        showScreen('newCampaign');
        showToast('Stwórz nową przygodę dla tego samego bohatera.', 'info', 3000);
        return;
    }
    // Fallback — return to campaigns chooser.
    await loadCampaigns();
    showScreen('campaigns');
}

async function handleResurrect() {
    // Stage 11 R8 — real resurrection flow. Confirmation modal shows the
    // server-computed cost, then POSTs /resurrect, then reloads the campaign
    // state so the player resumes mid-game.
    if (!characterData?.id || !currentCampaignId) {
        showToast('Brak aktywnej kampanii / bohatera.', 'error');
        return;
    }
    const preview = _resurrectPreviewCache || await (async () => {
        try { return await apiRequest('GET', `/characters/${characterData.id}/resurrect-preview`); }
        catch { return null; }
    })();
    if (!preview?.enabled) {
        // SF9 (#638) — rozróżnij powód z payloadu (resurrection_disabled / no_uses_remaining).
        showToast(sf9DisabledReason(preview), 'error');
        return;
    }
    const costLine = _formatResurrectCostLine(preview);
    const usesLine = (preview.config?.uses_remaining !== null && preview.config?.uses_remaining !== undefined)
        ? `<p style="opacity:0.7; font-size:0.9rem; margin-top:8px;">Pozostałych wskrzeszeń: ${preview.config.uses_remaining}</p>`
        : '';

    // Build a lightweight confirmation overlay (reuses death-screen z-stack)
    const modal = document.createElement('div');
    modal.id = 'resurrect-confirm';
    modal.style.cssText = `
        position: fixed; inset: 0; z-index: 10001;
        background: rgba(8, 4, 14, 0.86); backdrop-filter: blur(6px);
        display: flex; align-items: center; justify-content: center;
        padding: 24px;
    `;
    modal.innerHTML = `
      <div style="max-width: 520px; background: #1a1525; border: 1px solid #4a3a6a; border-radius: 14px; padding: 28px; color: #ece6f8; box-shadow: 0 12px 48px rgba(0,0,0,0.6);">
        <h2 style="margin: 0 0 12px; font-family: 'Cinzel', serif; color: #c8a8ff;">Wskrzeszenie</h2>
        <p style="line-height: 1.5; margin: 0 0 16px;">${costLine}</p>
        ${usesLine}
        <div style="display: flex; gap: 12px; margin-top: 20px;">
          <button id="res-cancel" style="flex:1; padding: 10px; background: #2a1f3a; color: #c0b8d0; border: 1px solid #4a3a6a; border-radius: 6px; cursor: pointer;">Anuluj</button>
          <button id="res-confirm" style="flex:2; padding: 10px; background: linear-gradient(135deg, #c8a8ff, #8868c0); color: #1a0e2a; border: none; border-radius: 6px; font-weight: bold; cursor: pointer;">✦ Wskrześ</button>
        </div>
      </div>`;
    document.body.appendChild(modal);

    modal.querySelector('#res-cancel').addEventListener('click', () => modal.remove());
    modal.querySelector('#res-confirm').addEventListener('click', async () => {
        const btn = modal.querySelector('#res-confirm');
        btn.disabled = true;
        btn.textContent = 'Wskrzeszanie…';
        try {
            const result = await apiRequest('POST', `/characters/${characterData.id}/resurrect`);
            modal.remove();
            hideDeathScreen();
            // Brief toast with the actual cost paid
            const paid = result.cost_applied || {};
            let msg = `✦ ${characterData.name || 'Bohater'} wstał — HP ${result.revived_hp}/${result.max_hp}.`;
            if (paid.gold_lost) msg += ` Strata: ${paid.gold_lost} GP.`;
            if (paid.xp_subtracted) msg += ` Cofnięto: ${paid.xp_subtracted} PD.`;
            if (paid.item_lost) msg += ` Utracono: ${paid.item_lost.label}.`;
            showToast(msg, 'success');
            // Reload campaign state so chat / sheet / map all reflect the revival.
            if (currentCampaign) {
                await enterGame(currentCampaign);
            } else {
                await loadCampaigns();
                showScreen('campaigns');
            }
        } catch (e) {
            modal.remove();
            showToast(e?.message || 'Wskrzeszenie nieudane.', 'error');
        }
    });
}

async function handleDeathReturn() {
    hideDeathScreen();
    currentCampaignId = null;
    currentCampaign = null;
    characterData = null;
    await loadCampaigns();
    showScreen('campaigns');
}

// ============================================================================
// Utility Functions
// ============================================================================
function formatTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return '';
    return date.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
}

function handleOverlayClick() {
    if (isSheetOpen) closeCharacterSheet();
    if (isSettingsOpen) closeSettings();
    if (isJournalOpen) closeJournal();
}

function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey && currentScreen === 'game') {
        e.preventDefault();
        handleSendMessage();
    }
}

