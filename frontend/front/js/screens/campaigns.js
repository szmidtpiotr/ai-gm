// ============================================================================
// Campaigns
// ============================================================================
async function _syncAdvCardsFromModes() {
    try {
        const data = await apiRequest('GET', '/campaign-modes');
        const modes = {};
        (data.modes || []).forEach(m => { modes[m.key] = m; });

        const nowaBtn = document.getElementById('new-campaign-btn');
        if (nowaBtn && modes.nowa) {
            const avail = modes.nowa.available;
            nowaBtn.disabled = !avail;
            nowaBtn.classList.toggle('adv-card--disabled', !avail);
        }

        const readyBtn = document.getElementById('ready-campaign-btn');
        if (readyBtn && modes.gotowa) {
            const avail = modes.gotowa.available;
            readyBtn.disabled = !avail;
            readyBtn.classList.toggle('adv-card--disabled', !avail);
            const tag = readyBtn.querySelector('.adv-card__tag');
            if (tag) tag.textContent = avail ? `${modes.gotowa.count || 0} scenariuszy` : 'Wkrótce';
            if (!readyBtn.__wiredReady) {
                readyBtn.__wiredReady = true;
                readyBtn.addEventListener('click', () => { if (!readyBtn.disabled) _openReadyCampaignPicker(); });
            }
        }

        const dungeonBtn = document.getElementById('dungeon-picker-btn');
        if (dungeonBtn && modes.loch) {
            const avail = modes.loch.available;
            dungeonBtn.disabled = !avail;
            dungeonBtn.classList.toggle('adv-card--disabled', !avail);
        }

        const mpBtn = document.getElementById('mp-btn');
        if (mpBtn && modes.multiplayer) {
            const avail = modes.multiplayer.available;
            mpBtn.disabled = !avail;
            mpBtn.classList.toggle('adv-card--disabled', !avail);
            const tag = mpBtn.querySelector('.adv-card__tag');
            const arrow = mpBtn.querySelector('.adv-card__arrow');
            if (avail) {
                if (tag) tag.remove();
                if (!mpBtn.querySelector('.adv-card__arrow')) {
                    const a = document.createElement('span');
                    a.className = 'adv-card__arrow';
                    a.textContent = '›';
                    mpBtn.appendChild(a);
                }
            } else {
                if (arrow) arrow.remove();
                if (tag) tag.textContent = 'Wkrótce';
            }
            if (!mpBtn.__wiredMp) {
                mpBtn.__wiredMp = true;
                mpBtn.addEventListener('click', () => {
                    if (!mpBtn.disabled && typeof openMultiplayerLobby === 'function') openMultiplayerLobby();
                });
            }
        }
    } catch(e) {
        console.warn('[AdvCards] Could not sync game modes:', e);
    }
}

// GF5 (#925) — MP sections: invites / lobbies / active games
async function _loadMpSections() {
    try {
        const [invRes, lobRes, gameRes] = await Promise.all([
            apiRequest('GET', '/multiplayer/my-invites').catch(() => ({ invites: [] })),
            apiRequest('GET', '/multiplayer/my-lobbies').catch(() => ({ lobbies: [] })),
            apiRequest('GET', '/multiplayer/my-active-games').catch(() => ({ games: [] })),
        ]);
        _renderMpInvites(invRes.invites || []);
        _renderMpLobbies(lobRes.lobbies || []);
        _renderMpActiveGames(gameRes.games || []);
    } catch (e) {
        console.warn('[MP] Could not load MP sections:', e);
    }
}

function _renderMpInvites(invites) {
    const section = document.getElementById('mp-invites-section');
    const list = document.getElementById('mp-invites-list');
    if (!section || !list) return;
    if (!invites.length) { section.style.display = 'none'; return; }
    section.style.display = '';
    list.innerHTML = invites.map(inv => `
        <div class="campaign-card" style="margin-bottom:10px;cursor:default">
            <div class="campaign-card__icon"><span>📨</span></div>
            <div class="campaign-card__content">
                <h3>${escapeHtml(inv.title || 'Gra wieloosobowa')}</h3>
                <p>Zaprosił: ${escapeHtml(inv.host_username || '?')} · Timer: ${inv.round_timer_hours ? Math.round(inv.round_timer_hours * 60) + ' min' : '—'}</p>
            </div>
            <div style="display:flex;flex-direction:column;gap:6px;min-width:90px">
                <button class="mp-invite-accept" data-id="${inv.campaign_id}" style="padding:6px 10px;border-radius:8px;background:rgba(76,175,80,.15);border:1px solid rgba(76,175,80,.4);color:#4caf50;cursor:pointer;font-size:.8rem">Akceptuj</button>
                <button class="mp-invite-spectate" data-id="${inv.campaign_id}" style="padding:6px 10px;border-radius:8px;background:rgba(100,100,255,.1);border:1px solid rgba(100,100,255,.3);color:#9b9bff;cursor:pointer;font-size:.8rem">👁 Jako widz</button>
                <button class="mp-invite-decline" data-id="${inv.campaign_id}" style="padding:6px 10px;border-radius:8px;background:rgba(229,57,53,.1);border:1px solid rgba(229,57,53,.3);color:#e57373;cursor:pointer;font-size:.8rem">Odrzuć</button>
            </div>
        </div>`).join('');
    list.querySelectorAll('.mp-invite-accept').forEach(btn => {
        btn.addEventListener('click', () => _acceptMpInvite(Number(btn.dataset.id)));
    });
    list.querySelectorAll('.mp-invite-spectate').forEach(btn => {
        btn.addEventListener('click', () => _acceptMpInviteAsSpectator(Number(btn.dataset.id)));
    });
    list.querySelectorAll('.mp-invite-decline').forEach(btn => {
        btn.addEventListener('click', () => _declineMpInvite(Number(btn.dataset.id)));
    });
}

async function _acceptMpInvite(campaignId) {
    if (!currentHero?.id) {
        showToast('Najpierw wybierz bohatera, aby dołączyć do gry wieloosobowej.', 'info', 3000);
        return;
    }
    try {
        await apiRequest('POST', `/multiplayer/campaigns/${campaignId}/accept`, {
            character_id: currentHero.id,
        });
        showToast('Dołączyłeś do lobby!', 'success', 2500);
        if (typeof _showLobbyScreen === 'function') {
            _showLobbyScreen(campaignId);
        } else {
            await _loadMpSections();
        }
    } catch (e) {
        showToast(e.message || 'Błąd akceptacji zaproszenia', 'error');
    }
}

// GF6 (#926) — join as spectator (no character required)
async function _acceptMpInviteAsSpectator(campaignId) {
    try {
        await apiRequest('POST', `/multiplayer/campaigns/${campaignId}/accept`, {
            as_spectator: true,
        });
        showToast('Dołączyłeś jako widz!', 'success', 2500);
        if (typeof _showLobbyScreen === 'function') {
            _showLobbyScreen(campaignId);
        } else {
            await _loadMpSections();
        }
    } catch (e) {
        showToast(e.message || 'Błąd dołączania jako widz', 'error');
    }
}

async function _declineMpInvite(campaignId) {
    try {
        await apiRequest('POST', `/multiplayer/campaigns/${campaignId}/decline`);
        showToast('Zaproszenie odrzucone.', 'info', 2000);
        await _loadMpSections();
    } catch (e) {
        showToast(e.message || 'Błąd odrzucania zaproszenia', 'error');
    }
}

function _renderMpLobbies(lobbies) {
    const section = document.getElementById('mp-lobbies-section');
    const list = document.getElementById('mp-lobbies-list');
    if (!section || !list) return;
    if (!lobbies.length) { section.style.display = 'none'; return; }
    section.style.display = '';
    list.innerHTML = lobbies.map(lob => {
        const isHost = lob.host_username === currentUser?.username;
        const removeBtn = isHost
            ? `<button class="mp-lobby-remove" data-id="${lob.campaign_id}" data-host="1" title="Rozwiąż lobby" style="padding:6px 10px;border-radius:8px;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.35);color:#f87171;cursor:pointer;font-size:.8rem;margin-left:6px">🗑</button>`
            : `<button class="mp-lobby-remove" data-id="${lob.campaign_id}" data-host="0" title="Opuść lobby" style="padding:6px 10px;border-radius:8px;background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);color:#f87171;cursor:pointer;font-size:.8rem;margin-left:6px">Opuść</button>`;
        return `
        <div class="campaign-card" style="margin-bottom:10px;cursor:default">
            <div class="campaign-card__icon"><span>🏠</span></div>
            <div class="campaign-card__content">
                <h3>${escapeHtml(lob.title || 'Lobby')}</h3>
                <p>Gracze: ${lob.accepted_count || 1} / ${lob.max_players || '?'} · Host: ${escapeHtml(lob.host_username || '?')}</p>
            </div>
            <button class="mp-lobby-return" data-id="${lob.campaign_id}" style="padding:8px 14px;border-radius:8px;background:rgba(245,158,11,.15);border:1px solid rgba(245,158,11,.4);color:#f5b342;cursor:pointer;font-size:.8rem;white-space:nowrap">Wróć do lobby</button>
            ${removeBtn}
        </div>`;
    }).join('');
    list.querySelectorAll('.mp-lobby-return').forEach(btn => {
        btn.addEventListener('click', () => {
            if (typeof _showLobbyScreen === 'function') {
                _showLobbyScreen(Number(btn.dataset.id));
            } else {
                showToast('Lobby niedostępne — odśwież stronę.', 'error');
            }
        });
    });
    list.querySelectorAll('.mp-lobby-remove').forEach(btn => {
        btn.addEventListener('click', () => _handleMpRemove(Number(btn.dataset.id), btn.dataset.host === '1'));
    });
}

async function _handleMpRemove(campaignId, isHost) {
    const label = isHost ? 'Rozwiąż lobby / grę dla wszystkich?' : 'Opuścić tę kampanię?';
    if (!confirm(label)) return;
    try {
        if (isHost) {
            await apiRequest('DELETE', `/campaigns/${campaignId}`);
            showToast('Kampania usunięta', 'success');
        } else {
            await apiRequest('POST', `/multiplayer/campaigns/${campaignId}/leave`);
            showToast('Opuściłeś kampanię', 'success');
        }
        await _loadMpSections();
    } catch (e) {
        showToast(e.message || 'Błąd operacji', 'error');
    }
}

function _renderMpActiveGames(games) {
    const section = document.getElementById('mp-games-section');
    const list = document.getElementById('mp-games-list');
    if (!section || !list) return;
    if (!games.length) { section.style.display = 'none'; return; }
    section.style.display = '';
    list.innerHTML = games.map(g => {
        const isSpectator = g.role === 'spectator';
        const isHost = g.host_username === currentUser?.username;
        const icon = isSpectator ? '👁' : '⚔️';
        const spectatorBadge = isSpectator
            ? '<span style="font-size:10px;background:rgba(100,100,255,.15);border:1px solid rgba(100,100,255,.3);color:#9b9bff;border-radius:4px;padding:1px 5px;margin-left:6px;vertical-align:middle">WIDZ</span>'
            : '';
        const btnLabel = isSpectator ? '👁 Oglądaj' : 'Dołącz';
        const btnColor = isSpectator
            ? 'background:rgba(100,100,255,.1);border:1px solid rgba(100,100,255,.3);color:#9b9bff'
            : 'background:rgba(76,175,80,.15);border:1px solid rgba(76,175,80,.4);color:#4caf50';
        const removeLabel = isHost ? '🗑' : 'Opuść';
        return `
        <div class="campaign-card" style="margin-bottom:10px;cursor:default">
            <div class="campaign-card__icon"><span>${icon}</span></div>
            <div class="campaign-card__content">
                <h3>${escapeHtml(g.title || 'Gra wieloosobowa')}${spectatorBadge}</h3>
                <p>Gracze: ${g.player_count || '?'} · Host: ${escapeHtml(g.host_username || '?')}</p>
            </div>
            <button class="mp-game-join" data-id="${g.campaign_id}" data-timer="${g.round_timer_hours || 24}" data-role="${g.role || 'player'}" style="padding:8px 14px;border-radius:8px;${btnColor};cursor:pointer;font-size:.8rem;white-space:nowrap">${btnLabel}</button>
            <button class="mp-game-remove" data-id="${g.campaign_id}" data-host="${isHost ? 1 : 0}" title="${isHost ? 'Rozwiąż grę' : 'Opuść grę'}" style="padding:6px 10px;border-radius:8px;background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);color:#f87171;cursor:pointer;font-size:.8rem;margin-left:6px">${removeLabel}</button>
        </div>`;
    }).join('');
    list.querySelectorAll('.mp-game-join').forEach(btn => {
        btn.addEventListener('click', () => _joinMpActiveGame(Number(btn.dataset.id), Number(btn.dataset.timer), btn.dataset.role));
    });
    list.querySelectorAll('.mp-game-remove').forEach(btn => {
        btn.addEventListener('click', () => _handleMpRemove(Number(btn.dataset.id), btn.dataset.host === '1'));
    });
}

async function _joinMpActiveGame(campaignId, timerHours, role) {
    const isSpectator = role === 'spectator';
    if (!isSpectator && !currentHero?.id) {
        showToast('Najpierw wybierz bohatera, aby dołączyć do gry.', 'info', 3000);
        return;
    }
    try {
        const campResp = await apiRequest('GET', `/campaigns/${campaignId}`);
        const camp = campResp.campaign || campResp;
        currentCampaignId = campaignId;
        currentCampaign = camp;
        if (isSpectator) {
            await _enterGameAsSpectator(camp, timerHours);
        } else {
            characterData = currentHero;
            await enterGame(camp);
            // GF7 (#939): activate MP round UI for non-spectator player joining active MP game
            if (camp.mode === 'multiplayer' && window.multiplayerUI && typeof window.multiplayerUI.activate === 'function') {
                const timerMin = (timerHours || 24) * 60;
                await window.multiplayerUI.activate(camp.id, currentHero?.id, currentHero?.name, false, timerMin, false);
            }
        }
    } catch (e) {
        showToast(e.message || 'Błąd dołączania do gry', 'error');
    }
}

// GF6 (#926) — spectator game view: load history read-only, activate MP UI in spectator mode
async function _enterGameAsSpectator(camp, timerHours) {
    characterData = null;
    if (typeof showScreen === 'function') showScreen('game');
    if (typeof scrollToBottom === 'function') scrollToBottom();

    // Load public turn history
    try {
        const response = await apiRequest('GET', `/campaigns/${camp.id}/turns`);
        const turns = response.turns || (Array.isArray(response) ? response : []);
        for (const turn of turns) {
            if (turn.assistant_text) {
                const parsed = typeof parseGmFull === 'function' ? parseGmFull(turn.assistant_text) : { narrative: turn.assistant_text };
                if (parsed.narrative && parsed.narrative.trim()) {
                    if (typeof appendMessage === 'function') {
                        appendMessage({ role: 'assistant', content: parsed.narrative, created_at: turn.created_at, turn_number: turn.turn_number }, { autoSpeak: false });
                    }
                }
            }
        }
    } catch (_) {}

    if (typeof scrollToBottom === 'function') scrollToBottom();

    // Activate multiplayer UI in spectator mode (no character, no action submission)
    const timerMin = (timerHours || 24) * 60;
    if (window.multiplayerUI && typeof window.multiplayerUI.activate === 'function') {
        await window.multiplayerUI.activate(camp.id, null, 'Widz', false, timerMin, true);
    }
}

async function loadCampaigns() {
    console.log('[Campaigns] Loading for user:', currentUser?.id);
    _syncAdvCardsFromModes();
    _loadMpSections();
    // #400 — admin-only entry to the campaign spectator/resume browser.
    try {
        const adminBtn = document.getElementById('heroes-admin-btn');
        if (adminBtn) {
            adminBtn.style.display = currentUser?.is_admin ? '' : 'none';
            if (!adminBtn.__wired) {
                adminBtn.__wired = true;
                adminBtn.addEventListener('click', _openAdminSpectator);
            }
        }
    } catch {}
    try {
        const response = await apiRequest('GET', '/campaigns');
        console.log('[Campaigns] Raw response:', response);
        const allCampaigns = response.campaigns || (Array.isArray(response) ? response : []);

        // Filter to current user + current hero only (don't show other heroes' campaigns)
        const campaigns = allCampaigns.filter(c => {
            const ownerId = c.owner_user_id ?? c.owneruserid;
            if (Number(ownerId) !== Number(currentUser?.id)) return false;
            // Hide ended/discarded — archived/completed go to history section below
            if (c.status === 'ended' || c.status === 'discarded') return false;
            // #900: archived campaigns go to history, not main list
            if (c.status === 'archived') return false;
            // #1095: completed campaigns (T38 victory) go to history, not main list
            if (c.status === 'completed') return false;
            // If we have a hero, only show campaigns that have this hero as character
            if (currentHero?.id) {
                const campCharId = c.character_id ?? c.char_id;
                // If campaign has a character assigned and it's not this hero → hide
                if (campCharId === null || campCharId === undefined) {
                    // No active character in campaign. Only hide if THIS hero is busy
                    // elsewhere; an idle hero may still re-enter (e.g. after exiting a
                    // dungeon the hero is idle but the original campaign is character-less).
                    const heroIsIdle = currentHero.status === 'idle' || !currentHero.campaign_id;
                    if (!heroIsIdle) return false;
                } else if (Number(campCharId) !== Number(currentHero.id)) {
                    return false;
                }
            }
            return true;
        });

        // #900 + #1095: archived/completed campaigns — read-only history section
        const archived = allCampaigns.filter(c => {
            const ownerId = c.owner_user_id ?? c.owneruserid;
            if (Number(ownerId) !== Number(currentUser?.id)) return false;
            if (c.status !== 'archived' && c.status !== 'completed') return false;
            if (c.mode === 'dungeon') return false;
            // Only show archives that belonged to THIS hero
            if (currentHero?.id) {
                const campCharId = c.character_id ?? c.char_id;
                if (campCharId != null && Number(campCharId) !== Number(currentHero.id)) return false;
            }
            return true;
        });

        console.log('[Campaigns] Filtered:', campaigns.length, 'active,', archived.length, 'archived');
        renderCampaigns(campaigns);
        renderArchivedCampaigns(archived);
    } catch (error) {
        console.error('[Campaigns] Failed to load:', error);
        showToast('Nie udało się załadować kampanii', 'error');
    }
}

function renderCampaigns(campaigns) {
    elements.campaignsList.innerHTML = '';
    const sectionLabel = document.getElementById('campaigns-section-label');

    if (!campaigns || campaigns.length === 0) {
        if (elements.campaignsEmpty) elements.campaignsEmpty.style.display = '';
        if (sectionLabel) sectionLabel.style.display = 'none';
        return;
    }

    if (elements.campaignsEmpty) elements.campaignsEmpty.style.display = 'none';
    if (sectionLabel) sectionLabel.style.display = '';

    campaigns.forEach(campaign => {
        const wrapper = document.createElement('div');
        wrapper.className = 'campaign-swipe-wrapper';

        // Stage 9 follow-up: when the GM plan hasn't finished generating yet,
        // show a poetic placeholder + ⏳ spinner instead of the generic
        // "Przygoda <hero>" working title. Once the plan lands the card
        // shows the LLM-picked title + the premise as description.
        const planReady = campaign.plan_ready !== false;
        const rawTitle = campaign.title || campaign.name || 'Kampania';
        const isGenericTitle = /^(Przygoda\s+\S+|Kampania(\s+#?\d+)?|Nowa kampania)$/i.test(rawTitle);
        const showSpinner = !planReady && isGenericTitle;

        const title = showSpinner ? 'Mglista przygoda…' : rawTitle;
        const desc = showSpinner
            ? 'GM zaplata wątki — wróć za chwilę.'
            : (campaign.description || campaign.system_id || 'Fantasy');
        const icon = showSpinner ? '⏳' : '📜';
        const cardClass = showSpinner ? 'campaign-card campaign-card--brewing' : 'campaign-card';

        wrapper.innerHTML = `
            <div class="campaign-delete-action" data-campaign-id="${campaign.id}">🗑️</div>
            <button type="button" class="${cardClass}" data-campaign-id="${campaign.id}">
                <div class="campaign-card__icon">
                    <span>${icon}</span>
                </div>
                <div class="campaign-card__content">
                    <h3>${escapeHtml(title)}</h3>
                    <p>${escapeHtml(desc)}</p>
                </div>
                <span class="campaign-card__delete" data-campaign-id="${campaign.id}" title="Usuń kampanię" role="button" tabindex="0">×</span>
                <span class="campaign-card__arrow">›</span>
            </button>
        `;

        const card = wrapper.querySelector('.campaign-card');
        const deleteBtn = wrapper.querySelector('.campaign-card__delete');
        const deleteAction = wrapper.querySelector('.campaign-delete-action');

        card.addEventListener('click', (e) => {
            if (e.target.closest('.campaign-card__delete')) return;
            selectCampaign(campaign);
        });

        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleDeleteCampaignFromList(campaign, false);
        });

        deleteAction.addEventListener('click', (e) => {
            e.stopPropagation();
            handleDeleteCampaignFromList(campaign);
        });

        deleteAction.addEventListener('touchend', (e) => {
            e.preventDefault();
            e.stopPropagation();
            handleDeleteCampaignFromList(campaign);
        });

        initSwipeGesture(wrapper, card);

        elements.campaignsList.appendChild(wrapper);
    });
}

// #900: read-only turn-by-turn viewer for an archived campaign
async function _openArchivedCampaignViewer(campaign) {
    document.getElementById('archived-campaign-viewer')?.remove();

    const overlay = document.createElement('div');
    overlay.id = 'archived-campaign-viewer';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:9999;display:flex;flex-direction:column;';
    overlay.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid rgba(245,158,11,.2);background:#0e0e16;flex-shrink:0">
            <div>
                <div style="font-weight:700;color:#f5deb3;font-size:1rem">${escapeHtml(campaign.title || 'Kampania')}</div>
                <div style="font-size:.72rem;color:#888;margin-top:2px">Historia (tylko do odczytu)</div>
            </div>
            <button id="acv-close" style="background:none;border:none;color:#aaa;font-size:1.4rem;cursor:pointer;padding:4px 8px">✕</button>
        </div>
        <div id="acv-body" style="flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:16px">
            <div style="color:#888;text-align:center;padding:24px;font-size:.85rem">Ładowanie historii…</div>
        </div>`;

    overlay.querySelector('#acv-close').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);

    const body = overlay.querySelector('#acv-body');

    const PAGE_SIZE = 50;
    let loadedOffset = 0;
    let totalCount = 0;

    function _renderTurnEntry(t) {
        const entry = document.createElement('div');
        entry.style.cssText = 'display:flex;flex-direction:column;gap:10px';
        if (t.user_text) {
            entry.innerHTML += `<div style="align-self:flex-end;max-width:82%;background:#1a1a2e;border:1px solid rgba(255,255,255,.1);border-radius:12px 12px 4px 12px;padding:10px 12px;font-size:.85rem;color:#ddd;white-space:pre-wrap;word-break:break-word">${escapeHtml(t.user_text)}</div>`;
        }
        if (t.assistant_text) {
            let narr = t.assistant_text;
            try {
                const parsed = JSON.parse(t.assistant_text);
                narr = parsed.narrative || parsed.text || t.assistant_text;
            } catch (_) {}
            const cleaned = narr.replace(/【[^】]*】/g, '').trim();
            entry.innerHTML += `<div style="align-self:flex-start;max-width:88%;background:#14141c;border:1px solid rgba(245,158,11,.15);border-radius:12px 12px 12px 4px;padding:10px 12px;font-size:.85rem;color:#e8d5b0;line-height:1.5;white-space:pre-wrap;word-break:break-word">${escapeHtml(cleaned)}</div>`;
        }
        const turnLabel = document.createElement('div');
        turnLabel.style.cssText = 'font-size:.65rem;color:#555;text-align:center;margin-top:-4px';
        turnLabel.textContent = `— tura ${t.turn_number} —`;
        entry.appendChild(turnLabel);
        return entry;
    }

    function _updateCounter() {
        const el = overlay.querySelector('#acv-counter');
        if (el) el.textContent = `Pokazuję ${Math.min(loadedOffset + PAGE_SIZE, totalCount)} z ${totalCount} tur`;
    }

    async function _loadPage(offset) {
        const data = await apiRequest('GET', `/campaigns/${campaign.id}/turns-history?limit=${PAGE_SIZE}&offset=${offset}`);
        return data;
    }

    try {
        // Load first page (most recent = highest offset so user sees oldest-first within page)
        // Strategy: load from offset=0 → first PAGE_SIZE turns (oldest). Show "Wczytaj starsze" prepends older turns.
        // Actually issue wants: start showing LAST turns, load OLDER ones. So we load from the end.
        // First call: get total, load last page.
        const firstData = await _loadPage(0);
        totalCount = firstData.total_count || 0;
        const allTurns = firstData.turns || [];

        if (!allTurns.length) {
            body.innerHTML = '<div style="color:#888;text-align:center;padding:24px;font-size:.85rem">Brak zapisanych tur w tej kampanii.</div>';
            return;
        }

        // Load most-recent page so user sees current state of story
        const startOffset = Math.max(0, totalCount - PAGE_SIZE);
        const recentData = startOffset > 0 ? await _loadPage(startOffset) : firstData;
        loadedOffset = startOffset;

        body.innerHTML = '';

        // Counter bar at top
        const counterBar = document.createElement('div');
        counterBar.id = 'acv-counter';
        counterBar.style.cssText = 'font-size:.72rem;color:#666;text-align:center;padding:6px 0 2px;flex-shrink:0';
        body.appendChild(counterBar);

        // "Load older" button (prepend older turns above current)
        const loadOlderBtn = document.createElement('button');
        loadOlderBtn.id = 'acv-load-older';
        loadOlderBtn.style.cssText = 'display:block;width:100%;padding:8px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);border-radius:6px;color:#f5deb3;font-size:.78rem;cursor:pointer;margin-bottom:8px';
        loadOlderBtn.textContent = 'Wczytaj starsze';
        if (startOffset <= 0) loadOlderBtn.style.display = 'none';
        body.appendChild(loadOlderBtn);

        // Turn container
        const turnContainer = document.createElement('div');
        turnContainer.id = 'acv-turns';
        turnContainer.style.cssText = 'display:flex;flex-direction:column;gap:16px';
        body.appendChild(turnContainer);

        recentData.turns.forEach(t => turnContainer.appendChild(_renderTurnEntry(t)));
        _updateCounter();

        loadOlderBtn.addEventListener('click', async () => {
            if (loadedOffset <= 0) return;
            loadOlderBtn.disabled = true;
            loadOlderBtn.textContent = 'Ładowanie…';
            try {
                const prevOffset = Math.max(0, loadedOffset - PAGE_SIZE);
                const olderData = await _loadPage(prevOffset);
                const scrollBottom = body.scrollHeight - body.scrollTop;
                olderData.turns.forEach(t => {
                    turnContainer.insertBefore(_renderTurnEntry(t), turnContainer.firstChild);
                });
                // Restore scroll position
                body.scrollTop = body.scrollHeight - scrollBottom;
                loadedOffset = prevOffset;
                if (loadedOffset <= 0) loadOlderBtn.style.display = 'none';
                else { loadOlderBtn.disabled = false; loadOlderBtn.textContent = 'Wczytaj starsze'; }
                _updateCounter();
            } catch (e) {
                loadOlderBtn.disabled = false;
                loadOlderBtn.textContent = 'Błąd — spróbuj ponownie';
            }
        });

        body.scrollTop = body.scrollHeight;
    } catch (err) {
        body.innerHTML = `<div style="color:#c55;text-align:center;padding:24px;font-size:.85rem">Błąd ładowania historii: ${escapeHtml(err.message || '?')}</div>`;
    }
}

// #900: read-only history of campaigns this hero played (status='archived')
function renderArchivedCampaigns(archived) {
    const section = document.getElementById('campaigns-history-section');
    const list = document.getElementById('campaigns-history-list');
    if (!section || !list) return;

    if (!archived || archived.length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = '';
    list.innerHTML = '';

    archived.forEach(campaign => {
        const rawTitle = campaign.title || 'Zamknięta kampania';
        const desc = campaign.description || campaign.system_id || 'Fantasy';
        const turns = campaign.turn_count ? ` · ${campaign.turn_count} tur` : '';

        const card = document.createElement('div');
        card.className = 'campaign-card campaign-card--archived';
        card.setAttribute('role', 'button');
        card.setAttribute('tabindex', '0');
        card.setAttribute('title', 'Historia — tylko do odczytu');
        card.innerHTML = `
            <div class="campaign-card__icon"><span>📖</span></div>
            <div class="campaign-card__content">
                <h3>${escapeHtml(rawTitle)}</h3>
                <p>${escapeHtml(desc)}${escapeHtml(turns)}</p>
            </div>
            <span class="campaign-card__badge">Historia</span>`;

        // Read-only: open history viewer modal
        card.addEventListener('click', () => _openArchivedCampaignViewer(campaign));

        list.appendChild(card);
    });
}

function initSwipeGesture(wrapper, card) {
    let startX = 0;
    let currentX = 0;
    let isSwiping = false;

    card.addEventListener('touchstart', (e) => {
        startX = e.touches[0].clientX;
        isSwiping = true;
        card.style.transition = 'none';
    }, { passive: true });

    card.addEventListener('touchmove', (e) => {
        if (!isSwiping) return;
        currentX = e.touches[0].clientX;
        const diff = currentX - startX;
        if (diff < 0) {
            const translateX = Math.max(diff, -80);
            card.style.transform = `translateX(${translateX}px)`;
        }
    }, { passive: true });

    card.addEventListener('touchend', () => {
        if (!isSwiping) return;
        isSwiping = false;
        card.style.transition = 'transform 0.2s ease-out';

        const diff = currentX - startX;
        if (diff < -40) {
            wrapper.classList.add('swiped');
            card.style.transform = 'translateX(-80px)';
        } else {
            wrapper.classList.remove('swiped');
            card.style.transform = 'translateX(0)';
        }
        startX = 0;
        currentX = 0;
    });

    document.addEventListener('touchstart', (e) => {
        if (!wrapper.contains(e.target) && wrapper.classList.contains('swiped')) {
            wrapper.classList.remove('swiped');
            card.style.transform = 'translateX(0)';
        }
    }, { passive: true });
}

async function handleDeleteCampaignFromList(campaign) {
    const campaignTitle = campaign.title || campaign.name || 'ta kampania';
    const confirmed = await showDeleteCampaignModal(campaignTitle);
    if (!confirmed) return;

    try {
        await apiRequest('DELETE', `/campaigns/${campaign.id}`);
        showToast('Kampania usunięta', 'success');
        // Refresh hero so its campaign_id reflects the unlink
        if (currentHero?.id) {
            try {
                const heroResp = await apiRequest('GET', `/characters/${currentHero.id}`);
                currentHero = heroResp.character || heroResp;
            } catch {}
        }
        await loadCampaigns();
    } catch (error) {
        console.error('[Delete] Campaign error:', error);
        showToast(error.message || 'Błąd usuwania kampanii', 'error');
    }
}

async function selectCampaign(campaign) {
    // #1095: completed/archived campaigns → read-only viewer, never enterGame
    if (campaign.status === 'completed' || campaign.status === 'archived') {
        _openArchivedCampaignViewer(campaign);
        return;
    }

    currentCampaignId = campaign.id;
    currentCampaign = campaign;

    try {
        const response = await apiRequest('GET', `/campaigns/${campaign.id}/characters`);
        const characters = response.characters || (Array.isArray(response) ? response : []);

        // #767: match THIS campaign's hero — prefer the currently-selected hero,
        // otherwise any active character of this user already linked to the campaign.
        // Matching by user_id alone is wrong for multi-hero users (picks wrong hero).
        const myCharacter =
            characters.find(c => currentHero?.id && c.id === currentHero.id) ||
            characters.find(c =>
                c.is_active &&
                (c.user_id === currentUser?.id || c.userid === currentUser?.id)
            );

        // #767: campaign occupied by a DIFFERENT active hero (any user, incl. same
        // user's other hero) → never auto-assign/take over. Block and bounce back.
        const otherHero = characters.find(c =>
            c.is_active &&
            c.id !== currentHero?.id &&
            (c.status === 'in_campaign' || c.campaign_id === campaign.id)
        );
        if (otherHero && !(myCharacter && myCharacter.id === currentHero?.id)) {
            showToast(`Ta kampania należy do bohatera „${otherHero.name}" — nie można przejąć.`, 'error', 4000);
            loadHeroes().then(() => showScreen('heroes'));
            return;
        }

        if (myCharacter) {
            characterData = myCharacter;
            await enterGame(campaign);
            // Restore dungeon HUD if this is a dungeon campaign
            if (campaign.mode === 'dungeon') {
                try {
                    const runResp = await apiRequest('GET', `/campaigns/${campaign.id}/dungeon-run`);
                    if (runResp.dungeon_run && !runResp.dungeon_run.completed && !runResp.dungeon_run.failed) {
                        _activeDungeonRun = runResp.dungeon_run;
                        _dungeonCampaignId = campaign.id;
                        updateDungeonHUD();
                        showDungeonHUD(true);
                        renderCurrentRoom();
                        _maybeShowDungeonCodexCard(runResp.onboarding_cards);
                    }
                } catch {}
            }
        } else if (currentHero?.id) {
            // Hero exists but not in this campaign — assign them
            try {
                await apiRequest('POST', `/characters/${currentHero.id}/assign-campaign`, {
                    campaign_id: campaign.id,
                    user_id: currentUser.id,
                });
                const heroResp = await apiRequest('GET', `/characters/${currentHero.id}`);
                currentHero = heroResp.character || heroResp;
                characterData = currentHero;
                await enterGame(campaign);
                return;
            } catch (err) {
                showToast(err.message || 'Nie można przypisać bohatera', 'error');
            }
            // Hero assignment failed — send back to heroes screen
            showToast('Wróć do ekranu Bohaterowie i wybierz bohatera.', 'info', 3000);
            loadHeroes().then(() => showScreen('heroes'));
        } else {
            // No hero — redirect to heroes screen (hero-first model)
            showToast('Najpierw wybierz lub stwórz bohatera.', 'info', 3000);
            loadHeroes().then(() => showScreen('heroes'));
        }
    } catch (error) {
        console.error('Error loading characters:', error);
        showToast('Błąd ładowania postaci. Wróć do ekranu Bohaterowie.', 'error', 3000);
        loadHeroes().then(() => showScreen('heroes'));
    }
}

function showNewCampaignScreen() {
    if (currentHero && currentHero.id) {
        handleNewCampaignWithHero();
        return;
    }
    showToast('Najpierw wybierz bohatera, aby stworzyć nową kampanię.', 'info', 3000);
    loadHeroes().then(() => showScreen('heroes'));
}

// E8 (#423) — player picker for ready (pre-built) campaigns. Cards show title,
// description and difficulty; a difficulty filter narrows the list; clicking a
// card launches the campaign from that template (copies the GM plan).
const _DIFF_LABELS = { 1: 'Łatwa', 2: 'Średnia', 3: 'Trudna', 4: 'Bardzo trudna', 5: 'Legendarna' };

async function _openReadyCampaignPicker() {
    if (!currentHero?.id) { showToast('Najpierw wybierz bohatera.', 'info', 3000); return; }
    document.getElementById('ready-campaign-picker')?.remove();

    let templates = [];
    try {
        const d = await apiRequest('GET', '/campaign-templates');
        templates = d.items || [];
    } catch (e) {
        showToast('Nie udało się pobrać gotowych kampanii.', 'error', 3000);
        return;
    }
    if (!templates.length) {
        showToast('Brak opublikowanych gotowych kampanii.', 'info', 3000);
        return;
    }

    const overlay = document.createElement('div');
    overlay.id = 'ready-campaign-picker';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;z-index:9998;padding:16px';

    const diffs = [...new Set(templates.map(t => t.difficulty_rating || 2))].sort();
    const filterBtns = `<button data-diff="all" class="rcp-filter rcp-filter--active" style="padding:5px 10px;border-radius:8px;border:1px solid rgba(245,158,11,.3);background:#1a1a24;color:#f5deb3;cursor:pointer;font-size:.74rem">Wszystkie</button>` +
        diffs.map(dv => `<button data-diff="${dv}" class="rcp-filter" style="padding:5px 10px;border-radius:8px;border:1px solid rgba(255,255,255,.12);background:#0e0e16;color:#aaa;cursor:pointer;font-size:.74rem">${'★'.repeat(dv)} ${escapeHtml(_DIFF_LABELS[dv] || dv)}</button>`).join('');

    overlay.innerHTML = `<div style="background:#14141c;border:1px solid rgba(245,158,11,.25);border-radius:12px;max-width:560px;width:100%;padding:18px;display:flex;flex-direction:column;gap:12px;max-height:88vh;overflow-y:auto">
        <div style="display:flex;justify-content:space-between;align-items:center"><div style="font-weight:700;color:#f5deb3;font-size:1.05rem">Wybierz gotową kampanię</div><button id="rcp-close" style="background:none;border:none;color:#999;font-size:1.2rem;cursor:pointer">✕</button></div>
        <div id="rcp-filters" style="display:flex;flex-wrap:wrap;gap:6px">${filterBtns}</div>
        <div id="rcp-list" style="display:flex;flex-direction:column;gap:10px"></div>
      </div>`;

    const listEl = overlay.querySelector('#rcp-list');
    const renderList = (filter) => {
        const shown = filter === 'all' ? templates : templates.filter(t => String(t.difficulty_rating || 2) === String(filter));
        listEl.innerHTML = shown.map(t => {
            const diff = t.difficulty_rating || 2;
            const stars = '★'.repeat(diff) + '☆'.repeat(Math.max(0, 5 - diff));
            const plays = t.play_count ? ` · ${t.play_count}× zagrane` : '';
            return `<button data-tpl="${t.id}" style="text-align:left;background:#0e0e16;border:1px solid rgba(245,158,11,.25);border-radius:10px;padding:12px 14px;cursor:pointer;width:100%">
                <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px">
                    <div style="font-weight:600;color:#eee">${escapeHtml(t.title || 'Kampania')}</div>
                    <div style="font-size:.74rem;color:#f5b342;white-space:nowrap" title="${escapeHtml(_DIFF_LABELS[diff] || '')}">${stars}</div>
                </div>
                <div style="font-size:.76rem;color:#9aa;margin-top:4px">${escapeHtml(t.description || 'Brak opisu.')}</div>
                <div style="font-size:.7rem;color:#778;margin-top:4px">${escapeHtml(t.atmosphere || '')}${plays}</div>
              </button>`;
        }).join('') || '<div style="color:#778;font-size:.8rem;text-align:center;padding:12px">Brak kampanii o tej trudności.</div>';
        listEl.querySelectorAll('[data-tpl]').forEach(b => b.addEventListener('click', () => {
            overlay.remove();
            _launchReadyCampaign(Number(b.dataset.tpl), templates.find(t => String(t.id) === b.dataset.tpl));
        }));
    };
    renderList('all');

    overlay.querySelectorAll('.rcp-filter').forEach(b => b.addEventListener('click', () => {
        overlay.querySelectorAll('.rcp-filter').forEach(x => { x.style.background = '#0e0e16'; x.style.color = '#aaa'; x.style.borderColor = 'rgba(255,255,255,.12)'; });
        b.style.background = '#1a1a24'; b.style.color = '#f5deb3'; b.style.borderColor = 'rgba(245,158,11,.3)';
        renderList(b.dataset.diff);
    }));
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#rcp-close').addEventListener('click', () => overlay.remove());
    document.body.appendChild(overlay);
}

async function _launchReadyCampaign(templateId, tpl) {
    if (!currentHero || !currentUser?.id) return;
    const loadingToast = showToast('Uruchamiam gotową kampanię…', 'info', 0);
    try {
        const title = tpl?.title || `Przygoda ${currentHero.name || 'Bohatera'}`;
        const campaign = await apiRequest('POST', '/campaigns', {
            title,
            system_id: 'fantasy',
            model_id: 'default',
            owner_user_id: currentUser.id,
            language: 'pl',
            mode: 'pre_built',
            status: 'active',
            template_id: templateId,
        });
        currentCampaignId = campaign.id;
        currentCampaign = campaign;
        await apiRequest('POST', `/characters/${currentHero.id}/assign-campaign`, {
            campaign_id: campaign.id,
            user_id: currentUser.id,
        });
        const heroResp = await apiRequest('GET', `/characters/${currentHero.id}`);
        currentHero = heroResp.character || heroResp;
        characterData = currentHero;
        loadingToast?.remove?.();
        showToast(`Kampania "${title}" gotowa! Wkraczasz do gry…`, 'success', 3000);
        await enterGame(campaign);
    } catch (err) {
        loadingToast?.remove?.();
        showToast(err.message || 'Nie udało się uruchomić kampanii.', 'error', 3000);
    }
}

async function handleNewCampaignWithHero() {
    if (!currentHero || !currentUser?.id) return;

    // #900: confirm before silently overwriting an active campaign
    if (currentHero.campaign_id) {
        let campaignTitle = 'aktywną kampanię';
        let turnCount = null;
        try {
            const campResp = await apiRequest('GET', `/campaigns/${currentHero.campaign_id}`);
            const camp = campResp.campaign || campResp;
            if (camp.title) campaignTitle = camp.title;
            if (camp.turn_count != null) turnCount = camp.turn_count;
        } catch (_) {}
        const confirmed = await _confirmNewCampaignOverwrite(
            currentHero.name || 'Bohater', campaignTitle, turnCount
        );
        if (!confirmed) return;
    }

    // E28: offer tutorial for first-time players
    let isTutorial = false;
    try {
        const hc = await apiRequest('GET', `/users/${currentUser.id}/has-campaigns`);
        if (!hc.has_campaigns) {
            isTutorial = await _askTutorial();
        }
    } catch (_) {}

    const loadingToast = showToast('Tworzę kampanię…', 'info', 0);
    try {
        // Auto-generate a working title — GM plan will rename it properly
        const heroName = currentHero.name || 'Bohater';
        const title = isTutorial ? 'Moja Pierwsza Przygoda' : `Przygoda ${heroName}`;
        const campaign = await apiRequest('POST', '/campaigns', {
            title,
            system_id: 'fantasy',
            model_id: 'default',
            owner_user_id: currentUser.id,
            language: 'pl',
            mode: 'solo',
            status: 'active',
            is_tutorial: isTutorial,
        });
        currentCampaignId = campaign.id;
        currentCampaign = campaign;

        // Always assign hero to the new campaign (hero may have been freed from a deleted campaign)
        await apiRequest('POST', `/characters/${currentHero.id}/assign-campaign`, {
            campaign_id: campaign.id,
            user_id: currentUser.id,
        });
        // Reload hero data after assignment
        const heroResp = await apiRequest('GET', `/characters/${currentHero.id}`);
        currentHero = heroResp.character || heroResp;
        characterData = currentHero;

        loadingToast?.remove?.();
        showToast(`Kampania "${title}" gotowa! Wkraczasz do gry…`, 'success', 3000);
        await enterGame(campaign);
    } catch (err) {
        loadingToast?.remove?.();
        showToast(err.message || 'Błąd tworzenia kampanii', 'error');
    }
}

async function handleCreateCampaign(e) {
    e.preventDefault();

    const name = elements.campaignNameInput.value.trim();

    if (!name) {
        showToast('Wprowadź nazwę kampanii', 'error');
        return;
    }

    if (!currentUser?.id) {
        showToast('Nie jesteś zalogowany', 'error');
        return;
    }

    const submitBtn = elements.newCampaignForm.querySelector('button[type="submit"]');
    submitBtn.disabled = true;

    try {
        const campaign = await apiRequest('POST', '/campaigns', {
            title: name,
            system_id: 'fantasy',
            model_id: 'default',
            owner_user_id: currentUser.id,
            language: 'pl',
            mode: 'solo',
            status: 'active'
        });
        currentCampaignId = campaign.id;
        currentCampaign = campaign;
        if (currentHero?.id) {
            // Hero exists — assign and enter game
            await apiRequest('POST', `/characters/${currentHero.id}/assign-campaign`, {
                campaign_id: campaign.id,
                user_id: currentUser.id,
            });
            const heroResp = await apiRequest('GET', `/characters/${currentHero.id}`);
            currentHero = heroResp.character || heroResp;
            characterData = currentHero;
            showToast(`Kampania "${name}" gotowa! Wkraczasz do gry…`, 'success', 3000);
            await enterGame(campaign);
        } else {
            // No hero — send to heroes screen (hero-first model)
            showToast('Kampania stworzona! Teraz wybierz lub stwórz bohatera.', 'info', 3000);
            loadHeroes().then(() => showScreen('heroes'));
        }
    } catch (error) {
        console.error('Create campaign error:', error);
        showToast(error.message || 'Nie udało się utworzyć kampanii', 'error');
    } finally {
        submitBtn.disabled = false;
    }
}

