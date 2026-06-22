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
    } catch(e) {
        console.warn('[AdvCards] Could not sync game modes:', e);
    }
}

async function loadCampaigns() {
    console.log('[Campaigns] Loading for user:', currentUser?.id);
    _syncAdvCardsFromModes();
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
            // Hide ended/archived campaigns
            if (c.status === 'ended' || c.status === 'archived' || c.status === 'discarded') return false;
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

        console.log('[Campaigns] Filtered:', campaigns.length, 'of', allCampaigns.length);
        renderCampaigns(campaigns);
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

// D9 (#384) — Hub kampanii: 5 trybów z flagą dostępności (no broken states).
async function _openCampaignModesHub() {
    if (!currentHero?.id) {
        showToast('Najpierw wybierz bohatera.', 'info', 3000);
        loadHeroes().then(() => showScreen('heroes'));
        return;
    }
    document.getElementById('campaign-modes-hub')?.remove();
    let modes = [];
    try { const d = await apiRequest('GET', '/campaign-modes'); modes = d.modes || []; }
    catch (e) { modes = [{ key: 'nowa', label: 'Nowa kampania', description: '', available: true }]; }

    const routes = {
        nowa: () => handleNewCampaignWithHero(),
        loch: () => (typeof openDungeonPicker === 'function' ? openDungeonPicker() : showToast('Loch chwilowo niedostępny', 'info')),
        gotowa: () => _openReadyCampaignPicker(),
        loch_kafelki: () => showToast('Loch z kafelkami — wkrótce w tym miejscu', 'info', 3000),
        multiplayer: () => (typeof openMultiplayerLobby === 'function' ? openMultiplayerLobby() : showToast('Multiplayer — lobby pojawi się tutaj', 'info', 3000)),
    };

    const overlay = document.createElement('div');
    overlay.id = 'campaign-modes-hub';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;z-index:9998;padding:16px';
    const cards = modes.map(m => {
        const dis = !m.available;
        const cnt = (m.count != null && m.count > 0) ? ` <span style="color:#888;font-size:.72rem">(${m.count})</span>` : '';
        // U3: multiplayer shows "Wkrótce" badge instead of generic "— niedostępne"
        const isMpDisabled = dis && m.key === 'multiplayer';
        const disLabel = isMpDisabled
            ? ` <span style="font-size:.68rem;color:#888;background:rgba(255,255,255,.07);padding:1px 7px;border-radius:10px;vertical-align:middle" data-mp-soon>Wkrótce</span>`
            : (dis ? ' — niedostępne' : '');
        return `<button data-mode="${m.key}" ${dis ? 'disabled' : ''} style="text-align:left;background:${dis ? '#0a0a0f' : '#0e0e16'};border:1px solid ${dis ? 'rgba(255,255,255,.05)' : 'rgba(245,158,11,.25)'};border-radius:10px;padding:12px 14px;cursor:${dis ? 'not-allowed' : 'pointer'};opacity:${dis ? .5 : 1};width:100%">
            <div style="font-weight:600;color:#eee">${escapeHtml(m.label)}${cnt}${isMpDisabled ? disLabel : ''}</div>
            <div style="font-size:.76rem;color:#9aa;margin-top:3px">${escapeHtml(m.description || '')}${!isMpDisabled && dis ? ' — niedostępne' : ''}</div>
          </button>`;
    }).join('');
    overlay.innerHTML = `<div style="background:#14141c;border:1px solid rgba(245,158,11,.25);border-radius:12px;max-width:460px;width:100%;padding:18px;display:flex;flex-direction:column;gap:10px;max-height:88vh;overflow-y:auto">
        <div style="display:flex;justify-content:space-between;align-items:center"><div style="font-weight:700;color:#f5deb3;font-size:1.05rem">Wybierz tryb gry</div><button id="cmh-close" style="background:none;border:none;color:#999;font-size:1.2rem;cursor:pointer">✕</button></div>
        ${cards}
      </div>`;
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#cmh-close').addEventListener('click', () => overlay.remove());
    overlay.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => {
        const k = b.dataset.mode; overlay.remove(); (routes[k] || (() => {}))();
    }));
    document.body.appendChild(overlay);
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

