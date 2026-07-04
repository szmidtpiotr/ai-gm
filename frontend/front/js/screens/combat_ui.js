// ============================================================================
// Combat
// ============================================================================
const COMBAT_ROLL_PREFIX = '__AI_GM_COMBAT_ROLL_V1__';
let combatPollTimer = null;
let combatActive = false;
let combatBusy = false;
let lastCombatState = null;
let enemyTurnInFlight = false;
// #700: rozróżnij "realny POST walki w locie" od "zalegającej flagi". Reconciler ufa backendowi,
// gdy ŻADEN z tych fetchy nie trwa — wtedy zdejmuje zaciśnięty overlay/akcję (watchdog re-sync).
let enemyTurnFetchActive = false;     // true tylko między POST enemy-turn a jego odpowiedzią
let playerActionFetchActive = false;  // true tylko między POST akcji gracza a jego odpowiedzią
// #984: blokuje pollCombatState przed wywołaniem handleCombatEnded podczas animacji kości.
// Na zabójczym ciosie combat.status='ended' pojawia się zanim Stage 2 popup zacznie — bez
// tej flagi poll wywołuje handleCombatEnded (victory overlay) w trakcie animacji Stage 2.
let _diceAnimationActive = false;
let _enemyTurnStartedAt = 0;          // timestamp startu POST enemy-turn (awaryjny watchdog)
let reactionPending = false;   // SF10 (#633): okno reakcji otwarte — wstrzymuje pętlę tury wroga
let _reactionTimer = null;     // SF10: handle odliczania 8 s (auto-take)
let pendingLoot = null;
let pendingGold = 0;
let pendingBossLoot = null;   // L8: boss drop (already granted server-side) → reveal-only popup

function startCombatPolling() {
    stopCombatPolling();
    pollCombatState();
    // #730: 2 s combat poll so a desynced „Tura wroga" overlay is reconciled within ≤2 s
    // on a live session (acceptance), not the prior 3.5 s.
    combatPollTimer = setInterval(pollCombatState, 2000);
}

function stopCombatPolling() {
    if (combatPollTimer) { clearInterval(combatPollTimer); combatPollTimer = null; }
}

async function pollCombatState() {
    if (!currentCampaignId) return;
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat`);
        if (!r.ok) return;
        const data = await r.json().catch(() => ({}));
        const cs = data.combat;

        if (!data.active || !cs) {
            if (combatActive) { hideCombatUI(); }
            return;
        }

        if (cs.status === 'ended') {
            lastCombatState = cs;
            // #984: nie wywołuj handleCombatEnded podczas animacji kości Stage 2 —
            // na zabójczym ciosie victory overlay nakryłby Stage 2 popup zanim gracz go zobaczy.
            // _handleCombatAttackResult wywoła handleCombatEnded po zakończeniu animacji.
            if (combatActive && !_diceAnimationActive) {
                window.clog?.event('combat_ended_detected', { reason: cs.ended_reason });
                await handleCombatEnded(cs);
            }
            return;
        }

        if (cs.status !== 'active') {
            if (combatActive) { hideCombatUI(); }
            return;
        }

        const wasActive = combatActive;
        lastCombatState = cs;
        renderCombatUI(cs);

        if (!wasActive) {
            window.clog?.event('combat_started', { round: cs.round, current_turn: cs.current_turn });
            showCombatUI();
            // L20b (#724): show portrait modal for enemies with images on combat start
            const _portraitEnemies = (cs.combatants || []).filter(c => c.type === 'enemy');
            if (_portraitEnemies.length) {
                showEnemyPortraitModal(_portraitEnemies).catch(() => {});
            }
        }

        // #700: reaktywny re-sync z backendem (źródło prawdy). Jeśli backend oddał turę graczowi,
        // a front zaciął się na overlayu/zablokowanej akcji (zalegające combatBusy/enemyTurnInFlight)
        // przy braku realnego fetchu walki w locie — zdejmij overlay, włącz akcję, wyczyść flagi.
        _reconcileCombatTurnUI(cs);

        // Auto-trigger enemy turn when it's not the player's turn
        // SF10 (#633): nie odpalaj kolejnej tury wroga, gdy otwarte jest okno reakcji.
        if (cs.current_turn !== 'player' && !enemyTurnInFlight && !combatBusy && !reactionPending) {
            await handleEnemyTurn();
        }
    } catch (e) {
        window.clog?.warn('combat_poll_exception', { message: String(e?.message || e) });
    }
}

// #700: aplikuj dyrektywy czystego reconcilera (combat_reconcile.js) do realnego UI.
// Wywoływane z pollCombatState (co 3.5 s) i po turze wroga — gwarantuje, że overlay/akcja
// zawsze podążają za backendem, nawet gdy lokalne flagi zacisnęły się pod szybkim inputem.
function _reconcileCombatTurnUI(cs) {
    if (typeof reconcileCombatTurn !== 'function') return;
    const d = reconcileCombatTurn(cs, {
        combatBusy,
        enemyTurnInFlight,
        enemyTurnFetchActive,
        playerActionFetchActive,
        reactionPending,
        enemyTurnStartedAt: _enemyTurnStartedAt,
    }, Date.now());
    // Wyczyść zalegające flagi ZANIM przerysujemy — inaczej renderCombatUI znów je uwzględni.
    if (d.clearEnemyTurnInFlight) enemyTurnInFlight = false;
    if (d.clearCombatBusy) combatBusy = false;
    const watchdog = d.reason === 'watchdog_resync' || d.reason === 'watchdog_timeout';
    if (watchdog) {
        window.clog?.warn('combat_turn_watchdog_resync', {
            reason: d.reason, current_turn: cs?.current_turn ?? null,
            had_busy: combatBusy, had_enemy_inflight: enemyTurnInFlight,
        });
    }
    // #730: ZAWSZE synchronizuj nakładkę z dyrektywą reconcilera (backend = źródło prawdy),
    // nie tylko przy watchdogu. Wcześniej zalegająca nakładka „Tura wroga" z JUŻ wyczyszczonymi
    // flagami (reason 'player_turn') nie była chowana → wisiała, przyciemniała ekran i jej tło
    // przechwytywało kliknięcia (Atak/Akcja/Ucieczka), mimo że backend = tura gracza.
    _showEnemyTurnOverlay(d.overlayVisible);
    // Po zdjęciu nakładki przerysuj, by bramka turowa przywróciła aktywne przyciski.
    if (!d.overlayVisible && lastCombatState) renderCombatUI(lastCombatState);
}

// Stage 7 C2 — toggle the "Tura wroga…" overlay (lazy-creates the DOM node).
function _showEnemyTurnOverlay(show, enemyName) {
    let overlay = document.getElementById('combat-status-overlay');
    if (!show) {
        overlay?.classList.remove('combat-status-overlay--visible');
        return;
    }
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'combat-status-overlay';
        overlay.className = 'combat-status-overlay';
        overlay.setAttribute('aria-live', 'polite');
        overlay.innerHTML = `
            <div class="combat-status-overlay__card">
              <span class="combat-status-overlay__icon" aria-hidden="true">⚔</span>
              <div class="combat-status-overlay__title">
                Tura wroga<span class="combat-status-overlay__dots"><i></i><i></i><i></i></span>
              </div>
              <div class="combat-status-overlay__sub" id="combat-status-overlay-sub"></div>
            </div>`;
        // Mount inside the combat banner so it's scoped to the fight, not the whole screen.
        (elements.combatBanner || document.body).appendChild(overlay);
    }
    // #730: only update the subtext when a name is explicitly passed. Reconciler-driven
    // re-shows pass no name and must NOT wipe the active „Działa: <wróg>" label.
    const sub = document.getElementById('combat-status-overlay-sub');
    if (sub && enemyName !== undefined) sub.textContent = enemyName ? `Działa: ${enemyName}` : '';
    overlay.classList.add('combat-status-overlay--visible');
}

async function handleEnemyTurn() {
    if (enemyTurnInFlight || reactionPending || !currentCampaignId) return;
    enemyTurnInFlight = true;
    setCombatMsg('Tura wroga...');
    // Show the overlay eagerly — `renderCombatUI` will keep it on until the next
    // state poll proves the player has control back. Avoids a flicker window
    // between POST request and the next render.
    _showEnemyTurnOverlay(true);
    // #700: oznacz REALNY POST tury wroga jako w locie (z timestampem dla awaryjnego watchdoga).
    enemyTurnFetchActive = true;
    _enemyTurnStartedAt = Date.now();
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/enemy-turn`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await r.json().catch(() => ({}));
        enemyTurnFetchActive = false;   // #700: POST rozliczony — sieć już nie wisi
        if (!r.ok) {
            setCombatMsg('Błąd tury wroga.', true);
            return;
        }
        const cs = data.combat_state;
        if (cs) {
            lastCombatState = cs;
            renderCombatUI(cs);
            // #700: backend mógł właśnie oddać turę graczowi — od razu zdejmij overlay i włącz akcję,
            // nie czekając na kolejny poll (3.5 s). Zapobiega zawieszeniu "Tura wroga" pod szybkim inputem.
            _reconcileCombatTurnUI(cs);
        }
        await fetchAndAppendNewCombatTurns();
        // SF10 (#633): wróg trafił i gracz ma reakcję → OKNO REAKCJI zamiast obrażeń.
        // Pokaż modal (bez liczby obrażeń); rozliczenie w resolveReaction().
        if (data.reaction_window) {
            _showEnemyTurnOverlay(false);
            showReactionModal(data);
            return;   // turę wstrzymano (backend nie zaawansował) — czekamy na wybór
        }
        if (data.hit) {
            setCombatMsg(`Wróg trafia za ${data.damage ?? '?'} obrażeń!`, true);
        } else {
            setCombatMsg('Wróg pudłuje.');
        }
        await refreshCharacterData();
        if (cs && cs.status === 'ended') {
            await handleCombatEnded(cs);
        }
    } catch (e) {
        window.clog?.warn('enemy_turn_exception', { message: String(e?.message || e) });
    } finally {
        enemyTurnInFlight = false;
        enemyTurnFetchActive = false;   // #700: gwarancja resetu nawet przy wyjątku
    }
}

// SF10 (#633): reaktywne okno uniku/bloku. Modal pokazuje TYLKO dostępne opcje, BEZ
// liczby obrażeń (decyzja Piotra — wybór pozostaje zakładem). Timeout 8 s → auto „take".
function showReactionModal(data) {
    reactionPending = true;
    const opts = Array.isArray(data.reaction_options) ? data.reaction_options : [];
    const enemyName = data.enemy_name || 'Wróg';
    const existing = document.getElementById('reaction-modal');
    if (existing) existing.remove();

    const btn = (choice, label, glyph, cls) =>
        `<button class="reaction-btn ${cls}" data-choice="${choice}">
           <span class="reaction-btn__glyph">${glyph}</span><span>${label}</span>
         </button>`;
    let buttons = btn('take', 'Przyjmij cios', '🛡️✗', 'reaction-btn--take');
    if (opts.includes('dodge')) buttons += btn('dodge', 'Unik (Zręczność)', '🤸', 'reaction-btn--dodge');
    if (opts.includes('shield_block')) buttons += btn('block', 'Blok (tarcza)', '🛡️', 'reaction-btn--block');

    const modal = document.createElement('div');
    modal.id = 'reaction-modal';
    modal.className = 'reaction-modal-overlay';
    modal.innerHTML = `
      <div class="reaction-modal">
        <div class="reaction-modal__title">⚔️ ${escapeHtml(enemyName)} trafia!</div>
        <div class="reaction-modal__sub">Jak reagujesz?</div>
        <div class="reaction-modal__btns">${buttons}</div>
        <div class="reaction-modal__timer"><span id="reaction-countdown">8</span> s — brak wyboru = przyjmujesz cios</div>
      </div>`;
    document.body.appendChild(modal);

    modal.querySelectorAll('.reaction-btn').forEach(b => {
        b.addEventListener('click', () => resolveReaction(b.getAttribute('data-choice')));
    });

    // Odliczanie 8 s → auto „take"
    let left = 8;
    const cd = modal.querySelector('#reaction-countdown');
    if (_reactionTimer) clearInterval(_reactionTimer);
    _reactionTimer = setInterval(() => {
        left -= 1;
        if (cd) cd.textContent = String(Math.max(0, left));
        if (left <= 0) {
            clearInterval(_reactionTimer);
            _reactionTimer = null;
            resolveReaction('take');
        }
    }, 1000);
}

async function resolveReaction(choice) {
    if (_reactionTimer) { clearInterval(_reactionTimer); _reactionTimer = null; }
    const modal = document.getElementById('reaction-modal');
    if (modal) modal.querySelectorAll('.reaction-btn').forEach(b => { b.disabled = true; });
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/resolve-reaction`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ choice: choice || 'take' })
        });
        const data = await r.json().catch(() => ({}));
        if (modal) modal.remove();
        reactionPending = false;
        if (!r.ok) { setCombatMsg('Błąd reakcji.', true); return; }
        const cs = data.combat_state;
        if (cs) { lastCombatState = cs; renderCombatUI(cs); }
        await fetchAndAppendNewCombatTurns();
        const react = data.reaction || {};
        if (choice === 'dodge' && react.dodged) {
            setCombatMsg('Unik! Cios mija — 0 obrażeń.');
        } else if ((choice === 'block') && (react.full_block || (react.reduction || 0) > 0)) {
            setCombatMsg(`Blok! Obrażenia: ${data.damage ?? 0}.`, (data.damage || 0) > 0);
        } else {
            setCombatMsg(`Wróg trafia za ${data.damage ?? 0} obrażeń!`, true);
        }
        await refreshCharacterData();
        if (cs && cs.status === 'ended') { await handleCombatEnded(cs); }
    } catch (e) {
        reactionPending = false;
        if (modal) modal.remove();
        window.clog?.warn('resolve_reaction_exception', { message: String(e?.message || e) });
    }
}

async function handleCombatEnded(cs) {
    const reason = cs?.ended_reason || '';
    window.clog?.event('combat_end_overlay', { reason });
    combatActive = false;
    if (reason === 'victory') {
        const loot = pendingLoot || [];
        const gold = pendingGold;
        pendingLoot = null;
        pendingGold = 0;
        hideCombatUI();
        if (loot.length > 0 || gold > 0) {
            await showLootPopup(loot, gold);
        }
        // L13: In dungeon, check if boss was defeated → show boss choice modal
        if (_dungeonCampaignId) {
            try {
                const runResp = await apiRequest('GET', `/campaigns/${_dungeonCampaignId}/dungeon-run`);
                if (runResp?.dungeon_run) _activeDungeonRun = runResp.dungeon_run;
                if (_activeDungeonRun?.boss_choice_pending) {
                    updateDungeonHUD();
                    // L8: reveal what dropped from the boss (already granted) BEFORE
                    // the go-deeper/exit choice, so the player sees the spoils.
                    if (pendingBossLoot && pendingBossLoot.length) {
                        await showLootPopup(pendingBossLoot, 0, { revealOnly: true });
                        pendingBossLoot = null;
                    }
                    showDungeonBossChoiceModal(_activeDungeonRun);
                    return;
                }
            } catch (_) { /* non-fatal — fall through to normal overlay */ }
            updateDungeonHUD();
            // L13c (#689): clear next-step prompt after clearing a tile so the
            // player knows to pick a door instead of typing free text.
            appendMessage({
                role: 'assistant',
                content: '⚔️ Pomieszczenie wyczyszczone. Wybierz drzwi przyciskami kierunków (prawy dolny róg), aby iść dalej.',
                created_at: new Date(),
            });
            scrollToBottom();
        }
        showCombatEndOverlay('victory', loot, gold);
        // #765: po zwycięstwie zaproponuj odzysk wystrzelonej amunicji (pill 40%).
        await showAmmoRecoveryPill(cs?.campaign_id || currentCampaignId);
    } else if (reason === 'fled') {
        hideCombatUI();
        showCombatEndOverlay('fled', [], 0);
    } else if (reason === 'player_dead') {
        hideCombatUI();
        // L13: In dungeon, handle death via dungeon death modal
        if (_dungeonCampaignId && characterData?.id) {
            await showDungeonDeathModal();
        } else {
            showDeathScreen(characterData?.name || 'Bohater');
        }
    } else {
        hideCombatUI();
    }
}

// #765: pill odzysku amunicji po walce — pokazuje szansę PRZED i wynik PO akcji.
async function showAmmoRecoveryPill(campaignId) {
    if (!campaignId) return;
    try {
        const r = await fetch(`/api/campaigns/${campaignId}/combat/ammo-spent`);
        if (!r.ok) return;
        const d = (await r.json())?.data || {};
        if (!d.can_recover) return;
        const pct = Math.round((Number(d.chance) || 0.4) * 100);
        const fired = Number(d.total) || 0;
        const ammoKey = Object.keys(d.fired || {})[0] || 'arrows';
        const ammoPl = ammoKey === 'bolts' ? 'bełtów' : 'strzał';
        await new Promise((resolve) => {
            const wrap = document.createElement('div');
            wrap.className = 'ammo-recover-pill';
            wrap.innerHTML = `
                <div class="ammo-recover-pill__card">
                  <div class="ammo-recover-pill__title">🏹 Pozbieraj amunicję</div>
                  <div class="ammo-recover-pill__body">Wystrzelono <b>${fired}</b> ${ammoPl}. Szansa odzysku: <b>${pct}%</b> na sztukę.</div>
                  <div class="ammo-recover-pill__actions">
                    <button class="ammo-recover-pill__btn ammo-recover-pill__btn--go">Pozbieraj</button>
                    <button class="ammo-recover-pill__btn ammo-recover-pill__btn--skip">Zostaw</button>
                  </div>
                </div>`;
            document.body.appendChild(wrap);
            const close = () => { wrap.remove(); resolve(); };
            wrap.querySelector('.ammo-recover-pill__btn--skip').onclick = close;
            wrap.querySelector('.ammo-recover-pill__btn--go').onclick = async () => {
                const go = wrap.querySelector('.ammo-recover-pill__btn--go');
                go.disabled = true; go.textContent = 'Zbieram…';
                try {
                    const rr = await fetch(`/api/campaigns/${campaignId}/combat/recover-ammo`, { method: 'POST' });
                    const got = Number((await rr.json())?.data?.total) || 0;
                    wrap.querySelector('.ammo-recover-pill__body').innerHTML = got > 0
                        ? `✅ Odzyskano <b>${got}/${fired}</b> ${ammoPl} — wróciły do plecaka.`
                        : `❌ Nie udało się odzyskać żadnej sztuki.`;
                    wrap.querySelector('.ammo-recover-pill__actions').innerHTML =
                        `<button class="ammo-recover-pill__btn ammo-recover-pill__btn--skip">OK</button>`;
                    wrap.querySelector('.ammo-recover-pill__btn--skip').onclick = close;
                } catch (_) { close(); }
            };
        });
    } catch (_) { /* non-fatal */ }
}

function showCombatEndOverlay(reason, loot, gold) {
    const el = elements.combatEndOverlay;
    if (!el) return;
    if (reason === 'victory') {
        elements.combatEndIcon.textContent = '⚔️';
        elements.combatEndTitle.textContent = 'Zwycięstwo!';
        let lootHtml = '';
        if (loot && loot.length > 0) {
            lootHtml = '<ul class="combat-end-loot-list">' + loot.map(L => {
                const k = String(L?.label || L?.source_key || L?.key || '?').replace(/_/g, ' ');
                const qty = Number(L?.qty ?? L?.quantity ?? 1) || 1;
                return `<li>📦 ${escapeHtml(k)} ×${qty}</li>`;
            }).join('') + '</ul>';
        }
        if (gold > 0) lootHtml += `<p>💰 +${gold} GP</p>`;
        elements.combatEndLoot.innerHTML = lootHtml || '<p>Żadnych łupów.</p>';
    } else {
        elements.combatEndIcon.textContent = '🏃';
        elements.combatEndTitle.textContent = 'Udało ci się uciec!';
        elements.combatEndLoot.innerHTML = '';
    }
    el.hidden = false;
}

function hideCombatEndOverlay() {
    if (elements.combatEndOverlay) elements.combatEndOverlay.hidden = true;
    hideCombatUI();
    refreshCharacterData();
}

function showLootPopup(loot, gold, opts = {}) {
    return new Promise(resolve => {
        const el = elements.combatLootOverlay;
        if (!el) { resolve([]); return; }
        const list = Array.isArray(loot) ? loot : [];
        const goldAmt = Math.max(0, Number(gold || 0));
        // L8: reveal-only mode — boss loot is ALREADY granted (in inventory), so we
        // just show "co wypadło" with an OK button, no checkboxes / no claim POST.
        const revealOnly = !!opts.revealOnly;
        const glyph = revealOnly ? '👑' : '📦';
        let html = list.length === 0
            ? '<p class="combat-loot-empty">Wróg nic nie miał.</p>'
            : '<ul>' + list.map((L, idx) => {
                const k = String(L?.label || L?.source_key || L?.key || '?').replace(/_/g, ' ');
                const qty = Number(L?.qty ?? L?.quantity ?? 1) || 1;
                return revealOnly
                    ? `<li>${glyph} ${escapeHtml(k)} ×${qty}</li>`
                    : `<li><label><input type="checkbox" data-loot-idx="${idx}" checked> ${glyph} ${escapeHtml(k)} ×${qty}</label></li>`;
            }).join('') + '</ul>';
        if (goldAmt > 0) html += `<p>💰 +${goldAmt} ZŁ (dodano)</p>`;
        elements.combatLootList.innerHTML = html;
        el.hidden = false;
        if (revealOnly) {
            // Single confirm — loot already in inventory, nothing to claim/skip.
            if (elements.combatLootClaimBtn) {
                elements.combatLootClaimBtn.textContent = '👑 Zabieram';
                elements.combatLootClaimBtn.onclick = () => { el.hidden = true; resolve([]); };
            }
            if (elements.combatLootSkipBtn) elements.combatLootSkipBtn.style.display = 'none';
            return;
        }
        if (elements.combatLootSkipBtn) elements.combatLootSkipBtn.style.display = '';
        if (elements.combatLootClaimBtn) elements.combatLootClaimBtn.textContent = 'Weź łupy';
        const claim = async () => {
            el.hidden = true;
            const picks = Array.from(el.querySelectorAll('[data-loot-idx]:checked'))
                .map(x => Number(x.getAttribute('data-loot-idx')));
            if (picks.length > 0 && characterData?.id) {
                try {
                    const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/loot/claim`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ character_id: characterData.id, selected_indexes: picks })
                    });
                    // U17 (#565): celebrate affixed/rare drops with a highlighted card + diff vs equipped.
                    const data = await r.json().catch(() => ({}));
                    const specials = (data?.claimed || [])
                        .map(c => c?.comparison)
                        .filter(c => c && c.is_special);
                    if (specials.length > 0) await showDropCelebration(specials);
                } catch (_e) {}
            }
            resolve(picks);
        };
        elements.combatLootClaimBtn.onclick = claim;
        elements.combatLootSkipBtn.onclick = () => { el.hidden = true; resolve([]); };
    });
}

// U17 (#565): affix effect → short human label for the celebration card.
function _affixEffectLabel(eff) {
    const t = String(eff?.type || '').toLowerCase();
    const v = Number(eff?.value ?? 0);
    const sign = v >= 0 ? '+' : '';
    if (t === 'damage_bonus') return `${sign}${v} obrażeń`;
    if (t === 'ac_bonus') return `${sign}${v} pancerza`;
    if (t === 'heal_on_hit') return `${sign}${v} leczenia przy trafieniu`;
    if (t === 'attack_bonus') return `${sign}${v} do trafienia`;
    return t ? `${t} ${sign}${v}` : '';
}

// U17 (#565): one diff row (↑/↓/= or "brak porównania" when nothing equipped).
function _dropDiffRow(label, value) {
    if (value === null || value === undefined) {
        return `<div class="drop-diff drop-diff--none"><span>${escapeHtml(label)}</span><span>— brak porównania</span></div>`;
    }
    const num = Number(value);
    const cls = num > 0 ? 'drop-diff--up' : (num < 0 ? 'drop-diff--down' : 'drop-diff--same');
    const arrow = num > 0 ? '↑' : (num < 0 ? '↓' : '=');
    const shown = num > 0 ? `+${num}` : `${num}`;
    return `<div class="drop-diff ${cls}"><span>${escapeHtml(label)}</span><span>${arrow} ${shown}</span></div>`;
}

function showDropCelebration(specials) {
    return new Promise(resolve => {
        const el = elements.dropCelebrationOverlay;
        if (!el || !Array.isArray(specials) || specials.length === 0) { resolve(); return; }
        const cards = specials.map(c => {
            const rarity = String(c?.rarity_label || 'common');
            const name = String(c?.name || c?.item_type || 'Przedmiot');
            const affixHtml = (c?.affixes || []).map(a => {
                const fx = (a?.effects || []).map(_affixEffectLabel).filter(Boolean).join(', ');
                return `<li class="drop-affix"><strong>${escapeHtml(String(a?.name || ''))}</strong>${fx ? ` — ${escapeHtml(fx)}` : ''}</li>`;
            }).join('');
            const diff = c?.diff || {};
            let diffHtml = '';
            if (c?.item_type === 'weapon') {
                diffHtml += _dropDiffRow('Obrażenia', diff.damage);
                if ('attack_bonus' in diff) diffHtml += _dropDiffRow('Do trafienia', diff.attack_bonus);
            } else if (c?.item_type === 'armor') {
                diffHtml += _dropDiffRow('Pancerz', diff.ac);
            }
            const canEquip = c?.suggested_slot && c?.inventory_id != null;
            const equipBtn = canEquip
                ? `<button type="button" class="combat-end-btn drop-equip-btn" data-drop-equip data-inv="${c.inventory_id}" data-slot="${escapeHtml(String(c.suggested_slot))}">Załóż</button>`
                : '';
            return `
                <div class="drop-card drop-card--${escapeHtml(rarity)}">
                    <div class="drop-card__head">
                        <span class="drop-card__icon">${c?.item_type === 'armor' ? '🛡️' : '⚔️'}</span>
                        <span class="drop-card__name">${escapeHtml(name)}</span>
                        <span class="drop-rarity drop-rarity--${escapeHtml(rarity)}">${escapeHtml(rarity)}</span>
                    </div>
                    ${affixHtml ? `<ul class="drop-affix-list">${affixHtml}</ul>` : ''}
                    <div class="drop-diff-block">${diffHtml}</div>
                    ${equipBtn}
                </div>`;
        }).join('');
        elements.dropCelebrationList.innerHTML = cards;
        el.hidden = false;

        // Załóż buttons — reuse the existing equip endpoint.
        el.querySelectorAll('[data-drop-equip]').forEach(btn => {
            btn.onclick = async () => {
                btn.disabled = true;
                const inv = Number(btn.getAttribute('data-inv'));
                const slot = btn.getAttribute('data-slot');
                try {
                    const r = await fetch(`/api/inventory/${characterData.id}/equip`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ inventory_id: inv, slot })
                    });
                    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'błąd ekwipowania');
                    btn.textContent = '✓ Założono';
                    showToast('Przedmiot założony.', 'info');
                    await refreshCharacterData();
                } catch (err) {
                    btn.disabled = false;
                    showToast(err?.message || 'Nie udało się założyć', 'error');
                }
            };
        });

        const close = () => { el.hidden = true; resolve(); };
        elements.dropCelebrationCloseBtn.onclick = close;
    });
}

function showCombatUI() {
    combatActive = true;
    pendingBossLoot = null;   // L8: clear any stale boss drop from a prior fight
    lastRenderedCombatTurnId = 0;
    elements.combatBanner.hidden = false;
    // #967: w walce blokuj auto-hide nagłówka przez CSS class na body (overriduje translateY).
    document.body.classList.add('combat-active');
    document.querySelector('.header--game')?.classList.remove('header--hidden');
    elements.combatComposer.hidden = false;
    elements.composer?.classList.add('composer--hidden');
    // Show spell button for Scholar
    const sheet = characterData?.sheet_json || characterData || {};
    const parsedSheet = typeof sheet === 'string' ? JSON.parse(sheet) : sheet;
    const spellBtn = document.getElementById('combat-spell-btn');
    if (spellBtn) spellBtn.style.display = parsedSheet.archetype === 'scholar' ? '' : 'none';
    refreshCombatShieldFlag();  // SF2 (#620): status tarczy dla gatingu „Blok"
    updateInputPlaceholder();
}

function hideCombatUI() {
    combatActive = false;
    lastCombatState = null;
    enemyTurnInFlight = false;
    // #1149: wyczyść też flagi akcji gracza na koniec KAŻDEJ walki. Gdy walka się kończy,
    // żaden POST akcji gracza nie jest już istotny dla bramkowania NASTĘPNEJ walki — a
    // zalegające combatBusy/playerActionFetchActive (np. po udanej ucieczce) zatruwały
    // reconciler kolejnego encountera (spawn-z-narracji) → przyciski disabled do F5.
    combatBusy = false;
    playerActionFetchActive = false;
    pendingLoot = null;
    pendingGold = 0;
    elements.combatBanner.hidden = true;
    document.body.classList.remove('combat-active');
    elements.combatComposer.hidden = true;
    closeCombatSheet();  // SF1 (#619): zamknij arkusz akcji na koniec walki
    closeAttackSheet();  // B6c (#651): zamknij też arkusz ataku
    elements.composer?.classList.remove('composer--hidden');
    const _statusBar = document.getElementById('combat-player-status');  // SF4 (#632): schowaj pasek statusu
    if (_statusBar) { _statusBar.hidden = true; _statusBar.innerHTML = ''; }
    if (elements.initiativeTrack) elements.initiativeTrack.innerHTML = '';
    _showEnemyTurnOverlay(false);  // C2: clear overlay on combat end
    _initActedThisRound = new Set();
    _initLastRound = 0;
    _initLastCurrentTurn = null;
    setCombatMsg('');
    updateInputPlaceholder();
}

// SF1 (#619): bottom sheet z pozostałymi akcjami walki (otwierany przyciskiem „Akcja").
function openCombatSheet() {
    if (!elements.combatActionSheet) return;
    if (elements.btnCombatAction?.disabled) return;  // nie tura gracza → nie otwieraj
    elements.combatActionSheet.hidden = false;
    elements.combatActionSheet.classList.add('is-open');
    window.clog?.event('combat_sheet_open', {});
}

function closeCombatSheet() {
    if (!elements.combatActionSheet) return;
    elements.combatActionSheet.classList.remove('is-open');
    elements.combatActionSheet.hidden = true;
}

// ── B6c (#651): rozwijane menu „Atak" dla maga — atak bronią + czary atakujące ──
function _combatIsScholar() {
    const sheet = characterData?.sheet_json || characterData || {};
    const parsed = typeof sheet === 'string' ? (() => { try { return JSON.parse(sheet); } catch { return {}; } })() : sheet;
    return parsed.archetype === 'scholar';
}

function closeAttackSheet() {
    const el = document.getElementById('combat-attack-sheet');
    if (!el) return;
    el.classList.remove('is-open');
    el.hidden = true;
}

function openAttackSheet() {
    const el = document.getElementById('combat-attack-sheet');
    if (!el) return;
    if (elements.btnCombatAttack?.disabled) return;
    el.hidden = false;
    el.classList.add('is-open');
    populateAttackSheet();
}

function _attackSheetWeaponHtml() {
    return `<button type="button" class="combat-btn combat-btn--attack" data-attack-mode="weapon" data-clog="combat_attack_weapon">
        <span class="combat-btn__body"><span class="combat-btn__head">
            <span class="combat-btn__label">⚔ Atak bronią</span>
            <span class="combat-btn__cost combat-btn__cost--action">⏳ tura</span>
        </span><span class="combat-btn__desc">Podstawowy atak (mag: kantryp 1d4, bez many)</span></span>
    </button>`;
}

function _wireAttackSheet(list) {
    list.querySelector('[data-attack-mode="weapon"]')?.addEventListener('click', () => {
        closeAttackSheet(); handleCombatAttack();
    });
    list.querySelectorAll('.combat-btn--spell:not([disabled])').forEach(btn => {
        btn.addEventListener('click', () => { closeAttackSheet(); handleCombatSpellAttack(btn.dataset.spellKey); });
    });
}

async function populateAttackSheet() {
    const list = document.getElementById('combat-attack-sheet-list');
    if (!list) return;
    const sheet = (() => { const s = characterData?.sheet_json || characterData || {}; return typeof s === 'string' ? JSON.parse(s) : s; })();
    const mana = sheet.current_mana ?? 0;
    const weaponBtn = _attackSheetWeaponHtml();
    list.innerHTML = weaponBtn + '<div style="padding:6px 12px;color:#888;font-size:0.75rem">Czary atakujące…</div>';
    _wireAttackSheet(list);  // broń aktywna nawet jeśli czary się nie załadują
    try {
        if (!_cachedSpells || _cachedSpells._charId !== characterData?.id) {
            const resp = await apiRequest('GET', `/characters/${characterData.id}/spells`);
            _cachedSpells = resp.spells || [];
            _cachedSpells._charId = characterData.id;
        }
        const offensive = (_cachedSpells || []).filter(s => s.spell_type === 'attack' || s.spell_type === 'attack_aoe');
        const spellHtml = offensive.map(s => {
            const cost = s.mana_cost || 2;
            const canCast = mana >= cost;
            const icon = s.spell_type === 'attack_aoe' ? '💥' : '🔥';
            return `<button type="button" class="combat-btn combat-btn--spell" data-spell-key="${escapeHtml(s.spell_key)}" ${canCast ? '' : 'disabled'}>
                <span class="combat-btn__body"><span class="combat-btn__head">
                    <span class="combat-btn__label">${icon} ${escapeHtml(s.label || s.spell_key)}</span>
                    <span class="combat-btn__cost combat-btn__cost--action">🔮 ${cost}</span>
                </span><span class="combat-btn__desc">${s.damage_die ? `Obrażenia ${escapeHtml(s.damage_die)}` : 'Czar atakujący'}${canCast ? '' : ' — za mało many'}</span></span>
            </button>`;
        }).join('');
        list.innerHTML = weaponBtn + (spellHtml || '<div style="padding:8px 12px;color:#888;font-size:0.75rem">Brak czarów atakujących.</div>');
        _wireAttackSheet(list);
    } catch {
        list.innerHTML = weaponBtn + '<div style="padding:8px 12px;color:#f87171;font-size:0.75rem">Błąd ładowania czarów.</div>';
        _wireAttackSheet(list);
    }
}

function onCombatAttackButton() {
    if (!combatActive) return;
    if (lastCombatState?.current_turn !== 'player') { setCombatMsg('Nie twoja tura.', true); return; }
    // Mag → menu (atak bronią/kantryp + czary atakujące). Reszta → bezpośredni atak jak dziś.
    if (_combatIsScholar()) { openAttackSheet(); return; }
    handleCombatAttack();
}

function setCombatMsg(text, isError) {
    const el = elements.combatMsg;
    if (!el) return;
    if (!text) { el.hidden = true; el.textContent = ''; return; }
    el.textContent = text;
    el.hidden = false;
    el.classList.toggle('combat-banner__msg--error', !!isError);
}

// ── Crit flash (T34) — Nat 20 / Nat 1 theatrical overlay ─────────────────
let _critFlashTimer = null;
const CRIT_FLASH_COPY = {
    crit:   { title: 'Krytyczny Sukces', sub: 'Naturalny 20 — podwójne obrażenia' },
    fumble: { title: 'Krytyczna Porażka', sub: 'Naturalny 1 — coś poszło nie tak' },
};
function triggerCritFlash(kind) {
    const el = elements.critFlash;
    if (!el) return;
    const copy = CRIT_FLASH_COPY[kind];
    if (!copy) return;
    if (elements.critFlashTitle) elements.critFlashTitle.textContent = copy.title;
    if (elements.critFlashSub)   elements.critFlashSub.textContent   = copy.sub;
    // Clear prior state so re-triggers restart the animation cleanly
    el.classList.remove('crit-flash--active', 'crit-flash--crit', 'crit-flash--fumble');
    document.body.classList.remove('crit-shake');
    if (_critFlashTimer) { clearTimeout(_critFlashTimer); _critFlashTimer = null; }
    // Force reflow so adding the class re-fires the keyframe animation
    void el.offsetWidth;
    el.classList.add('crit-flash--active', kind === 'crit' ? 'crit-flash--crit' : 'crit-flash--fumble');
    if (kind === 'fumble') {
        document.body.classList.add('crit-shake');
        setTimeout(() => document.body.classList.remove('crit-shake'), 220);
    }
    _critFlashTimer = setTimeout(() => {
        el.classList.remove('crit-flash--active', 'crit-flash--crit', 'crit-flash--fumble');
        _critFlashTimer = null;
    }, 720);
    window.clog?.event('crit_flash', { kind });
}

// ── Initiative track state (T34) ────────────────────────────────────────
// Tracks which combatant ids have already acted within the current round.
let _initActedThisRound = new Set();
let _initLastRound = 0;
let _initLastCurrentTurn = null;

// Stage 7 C1 — condition → badge glyph + variant class for animation tint.
// `label` is the human display name (Polish), used in chip tooltip.
// `variant` maps to a CSS modifier (`.init-chip__cond-badge--<variant>`).
const COND_BADGE_MAP = {
    zaskoczony:   { glyph: '⚡', label: 'Zaskoczony',   variant: 'surprise' },
    poisoned:     { glyph: '☠',  label: 'Zatruty',      variant: 'poison'   },
    bleeding:     { glyph: '🩸', label: 'Krwawienie',   variant: 'bleed'    },
    burning:      { glyph: '🔥', label: 'Płonący',      variant: 'burn'     },
    frightened:   { glyph: '😨', label: 'Przerażony',   variant: 'fear'     },
    panicked:     { glyph: '😱', label: 'Spanikowany',  variant: 'panic'    },
    stunned:      { glyph: '💫', label: 'Oszołomiony',  variant: 'stun'     },
    blinded:      { glyph: '🫥', label: 'Oślepiony',    variant: 'blind'    },
    cursed:       { glyph: '🕷', label: 'Przeklęty',    variant: 'curse'    },
    break:        { glyph: '💢', label: 'Złamany',      variant: 'break'    },
    // SF7 (#636) — 8 kondycji FAZY S; klucze = kanon katalogu game_config_conditions.
    on_fire:      { glyph: '🔥', label: 'Podpalony',       variant: 'burn'     },
    exhausted:    { glyph: '😓', label: 'Wyczerpany',      variant: 'exhaust'  },
    hidden:       { glyph: '🌫', label: 'Ukryty',          variant: 'hidden'   },
    rage:         { glyph: '😤', label: 'Furia',           variant: 'rage'     },
    blessed:      { glyph: '✨', label: 'Pobłogosławiony', variant: 'blessed'  },
    hasted:       { glyph: '⚡', label: 'Przyśpieszony',   variant: 'haste'    },
    hemorrhage:   { glyph: '🩸', label: 'Krwotok',         variant: 'bleed'    },
    inspired:     { glyph: '🌟', label: 'Zainspirowany',   variant: 'inspire'  },
};
// SF7 (#636) — wystaw mapę na window dla kontraktu Playwright (const nie trafia na window).
window.COND_BADGE_MAP = COND_BADGE_MAP;

// ─── SF5 (#634): ulotne komunikaty zdarzeń — ujawniają ukrytą mechanikę FAZY S ───
// „Mechanika decyduje, LLM narruje": front CZYTA gotowy sygnał z payloadu, NIC nie liczy.
// Pure-helper (bez DOM) — mapuje sygnał → {icon, text, variant}. null = nic nie migać.
function sf5EphemeralMessage(kind, ctx = {}) {
    switch (String(kind || '')) {
        case 'omen': // S11 — zła wróżba zepsuła rzut umiejętności
            return { icon: '🌑', text: 'Zły omen — klątwa zepsuła rzut', variant: 'curse' };
        case 'extra_action': // S12 — pośpiech: ruch nie zużył tury
            return { icon: '⚡', text: 'Ruch za darmo — pośpiech nie zużył tury', variant: 'haste' };
        case 'behavior': { // S18 — kondycja (confused/berserk/panicked) steruje turą wroga (k4)
            const who = String(ctx.enemy_name || 'Wróg').trim() || 'Wróg';
            const action = String(ctx.action || '');
            let what;
            if (action === 'stand') what = `${who} oszołomiony — traci turę`;
            else if (action === 'flee') what = `${who} ucieka w panice`;
            else if (action === 'attack_random' || action === 'attack_nearest')
                what = `${who} zdezorientowany — atakuje na ślepo (k4)`;
            else what = `${who} miota się w amoku (k4)`;
            return { icon: '🎲', text: what, variant: 'confuse' };
        }
        default:
            return null;
    }
}

// Render ulotnego wpisu w logu walki. `targetEl` opcjonalny (test) → domyślnie strumień czatu.
// Wpis zanika animacją i znika z DOM po czasie ekspozycji (SF5: 6000 ms, fade 600 ms).
function flashCombatEvent(kind, ctx = {}, targetEl = null) {
    const msg = sf5EphemeralMessage(kind, ctx);
    if (!msg) return null;
    const host = targetEl || elements.chatMessages;
    if (!host) return null;
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble chat-bubble--cturn-ephemeral cturn--ephemeral';
    bubble.dataset.sf5 = String(kind);
    bubble.innerHTML =
        `<div class="cturn cturn--ephemeral-row cturn--ephemeral-${msg.variant}">` +
        `<span class="cturn__icon">${msg.icon}</span>` +
        `<span class="cturn__text">${escapeHtml(msg.text)}</span></div>`;
    host.appendChild(bubble);
    // Auto-usuń po ekspozycji; fade odpala CSS animacją na końcu (forwards).
    setTimeout(() => { try { bubble.remove(); } catch (_e) {} }, 6000);
    return bubble;
}

// ─── SF6 (#635): karta rzutu hazardu — stawka + słowny stopień marginesu ─────────
// „Mechanika decyduje, LLM narruje": stawkę niesie pending.gamble.stake (S7/#616),
// margines sr.margin (S1/#581). Front tylko PREZENTUJE — nic nie liczy.
// Pure-helpery (bez DOM) pod test kontraktowy.
function sf6StakeLabel(pending) {
    const stake = Number(pending && pending.gamble ? pending.gamble.stake : NaN);
    if (!Number.isFinite(stake) || stake <= 0) return null;
    return `🪙 Ryzykujesz ${stake} zł`;
}

// Słowny stopień marginesu testu wg |margines|: luźny → ciasny → na włos.
function sf6MarginDegree(margin) {
    const m = Number(margin);
    if (!Number.isFinite(m)) return null;
    const a = Math.abs(m);
    if (a >= 5) return 'z nawiązką';
    if (a >= 2) return 'na styk';
    return 'o włos';
}

// ─── SF8 (#637): karta rzutu — rozbicie wyniku po NAZWANYM źródle ────────────────
// „Mechanika decyduje, front czyta": helpery NIC nie liczą — tylko nazywają już
// policzone składniki z payloadu (atak: attack_roll.*; skill: modifier_breakdown).
// Zero zmian mechaniki/backendu — kondycje/rana nie wchodzą do rzutu GRACZA, więc
// rozbijamy wyłącznie to, co realnie jest w wyniku (osobny ticket = wliczenie kondycji).
const SF8_STAT_LABELS = {
    STR: 'Siła', DEX: 'Zręczność', CON: 'Kondycja',
    INT: 'Inteligencja', WIS: 'Mądrość', CHA: 'Charyzma', LCK: 'Szczęście',
};

// Pure-helper (bez DOM). Zwraca uporządkowaną listę {label, value} składników ataku.
// Stat ZAWSZE obecny (nawet 0); pozostałe składniki = 0 odfiltrowane.
function sf8AttackBreakdown(attackRoll, extras = {}) {
    const ar = attackRoll || {};
    const ex = extras || {};
    const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
    const statKey = String(ar.attack_stat || '').toUpperCase();
    const parts = [{ label: SF8_STAT_LABELS[statKey] || statKey || 'Atak', value: num(ar.stat_mod) }];
    const add = (label, value) => { const v = num(value); if (v !== 0) parts.push({ label, value: v }); };
    add('Ranga', ar.skill_rank);
    add('Biegłość', ar.proficiency);
    add('Oburęczny', ar.weapon_bonus);
    add('Zaskoczenie', ex.surprise);
    add('Zniszczona broń', ex.durability);
    return parts;
}

// Pure-helper. Rozbicie testu umiejętności z modifier_breakdown (U20). Stat zawsze.
function sf8SkillBreakdown(modBreakdown) {
    const mb = modBreakdown || {};
    const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
    const statKey = String(mb.governing_stat || '').toUpperCase();
    const parts = [{ label: SF8_STAT_LABELS[statKey] || statKey || 'Cecha', value: num(mb.stat_mod) }];
    const add = (label, value) => { const v = num(value); if (v !== 0) parts.push({ label, value: v }); };
    add('Ranga', mb.skill_rank);
    add('Biegłość', mb.proficiency);
    return parts;
}

// Wspólny render listy {label,value} → HTML span-y (dodatnie zielone, ujemne czerwone).
function sf8BreakdownHtml(parts) {
    if (!Array.isArray(parts) || !parts.length) return '';
    return parts.map((p) => {
        const v = Number(p.value) || 0;
        const sign = v >= 0 ? '+' : '−';
        const cls = v >= 0 ? 'sf8-part--pos' : 'sf8-part--neg';
        return `<span class="sf8-part ${cls}">${sign}${Math.abs(v)} <i>${escapeHtml(String(p.label))}</i></span>`;
    }).join(' ');
}

// Wystaw helpery na window dla kontraktu Playwright (deklaracje funkcji nie trafiają na window).
window.sf8AttackBreakdown = sf8AttackBreakdown;
window.sf8SkillBreakdown = sf8SkillBreakdown;
window.sf8BreakdownHtml = sf8BreakdownHtml;

function _renderConditionBadges(conds) {
    if (!Array.isArray(conds) || !conds.length) return '';
    const meta = CONDITION_META_CACHE.byKey || {};
    return conds.map(c => {
        const key = String(c?.key || c?.label || '').trim().toLowerCase();
        if (!key) return '';
        const info = COND_BADGE_MAP[key] || { glyph: '•', label: c?.label || key, variant: 'generic' };
        const labelPL = info.label || meta[key]?.label || key;
        const desc = (meta[key]?.description) || '';
        const tip = desc ? `${labelPL} — ${desc}` : labelPL;
        return `<span class="init-chip__cond-badge init-chip__cond-badge--${info.variant}" title="${escapeHtml(tip)}" aria-label="${escapeHtml(labelPL)}">${info.glyph}</span>`;
    }).filter(Boolean).join('');
}

function _renderInitiativeTrack(cs) {
    const track = elements.initiativeTrack;
    if (!track) return;

    // #660: górny pasek inicjatywy wyłączony (duplikował strefy). Aktywną turę
    // pokazuje podświetlenie wiersza w strefach. Tracking _initLastCurrentTurn /
    // _initActedThisRound zostawiony niżej dla zgodności, ale chipów nie renderujemy.
    track.hidden = true;
    track.innerHTML = '';
    return;

    // eslint-disable-next-line no-unreachable
    const combatants = Array.isArray(cs.combatants) ? cs.combatants : [];
    const order = Array.isArray(cs.turn_order) ? cs.turn_order : [];
    const round = Number(cs.round || 1);
    const currentTurnId = String(cs.current_turn ?? '');

    // No order or empty combat → clear
    if (order.length === 0 || combatants.length === 0) {
        track.innerHTML = '';
        return;
    }

    // Round changed → reset acted set and play sweep
    if (round !== _initLastRound) {
        _initActedThisRound = new Set();
        _initLastRound = round;
        track.classList.remove('initiative-track--new-round');
        // Force reflow so animation re-triggers reliably
        void track.offsetWidth;
        track.classList.add('initiative-track--new-round');
        setTimeout(() => track.classList.remove('initiative-track--new-round'), 650);
    }

    // current_turn advanced → previous actor counts as having acted
    if (currentTurnId && _initLastCurrentTurn && currentTurnId !== _initLastCurrentTurn) {
        _initActedThisRound.add(_initLastCurrentTurn);
    }
    _initLastCurrentTurn = currentTurnId;

    // Build chips in initiative order
    const byId = new Map(combatants.map(c => [String(c.id ?? ''), c]));
    const html = order.map(rawId => {
        const id = String(rawId);
        const c = byId.get(id);
        if (!c) return '';
        const isPlayer = c.type === 'player';
        const hpCur = Math.max(0, Number(c.hp_current ?? 0));
        const hpMax = Math.max(1, Number(c.hp_max ?? hpCur ?? 1));
        const pct = Math.max(0, Math.min(100, Math.round((hpCur / hpMax) * 100)));
        const downed = hpCur <= 0;
        const active = !downed && id === currentTurnId;
        const acted = !active && !downed && _initActedThisRound.has(id);
        const tier = pct > _woundThresholds.healthy_pct ? 'high' : (pct > _woundThresholds.critical_pct ? 'mid' : 'low');
        // L20b (#724): use portrait thumbnail for enemies with image_url, fallback to emoji
        const portrait = isPlayer
            ? '🛡️'
            : (downed
                ? '💀'
                : (c.image_url
                    ? `<img class="init-chip__portrait-img" src="${escapeHtml(c.image_url)}" alt="">`
                    : '⚔️'));
        const ini = c.initiative_roll != null ? `INI ${c.initiative_roll}` : '';
        const zone = String(c.zone || 'engaged');
        const zoneGlyph = zone === 'ranged' ? '🏹' : '⚔';
        const cls = [
            'init-chip',
            isPlayer ? 'init-chip--player' : 'init-chip--enemy',
            active ? 'init-chip--active' : '',
            acted ? 'init-chip--acted' : '',
            downed ? 'init-chip--downed' : '',
        ].filter(Boolean).join(' ');
        const name = String(c.name || (isPlayer ? 'Bohater' : c.enemy_key) || '—');
        const zoneLabel = zone === 'ranged' ? 'Dystans' : 'Zwarcie';
        // Stage 7 C1 — render badges for every active condition on this combatant.
        const _conds = Array.isArray(c.conditions) ? c.conditions : [];
        const _badges = _renderConditionBadges(_conds);
        const _badgeNames = _conds.map(cc => {
            const k = String(cc?.key || cc?.label || '').trim();
            if (!k) return '';
            const meta = COND_BADGE_MAP[k.toLowerCase()];
            const label = (meta?.label) || cc?.label || k;
            return `${meta?.glyph || '•'} ${label}`;
        }).filter(Boolean).join(' · ');
        const _condTitleSuffix = _badgeNames ? ' · ' + _badgeNames : '';
        // U15 — visible wound tier on each combatant chip (colour dot + label).
        // Lets the player read "focus the wounded enemy"; hidden while > 75% HP.
        const _wound = downed ? null : getWoundLabel(hpCur, hpMax);
        const _woundHTML = _wound
            ? `<div class="init-chip__wound init-chip__wound--${_wound.tier}" title="${escapeHtml(_wound.label)}"><span class="init-chip__wound-dot" style="background:${_wound.color}"></span><span class="init-chip__wound-label" style="color:${_wound.color}">${escapeHtml(_wound.label)}</span></div>`
            : '';
        const _woundTitleSuffix = _wound ? ' · ' + _wound.label : '';
        return `
            <div class="${cls}" data-combatant-id="${escapeHtml(id)}" title="${escapeHtml(name)}${ini ? ' · ' + ini : ''} · ${zoneLabel}${_woundTitleSuffix}${_condTitleSuffix}">
                <div class="init-chip__zone" aria-label="${zoneLabel}">${zoneGlyph}</div>
                ${_badges ? `<div class="init-chip__cond-row">${_badges}</div>` : ''}
                <div class="init-chip__portrait">${portrait}</div>
                <div class="init-chip__name">${escapeHtml(name)}</div>
                <div class="init-chip__ini">${ini}</div>
                ${_woundHTML}
                <div class="init-chip__hp"><div class="init-chip__hp-fill init-chip__hp-fill--${tier}" style="width: ${pct}%"></div></div>
            </div>`;
    }).join('');

    track.innerHTML = html;

    // Keep the active chip visible in the scroll viewport
    const activeEl = track.querySelector('.init-chip--active');
    if (activeEl && typeof activeEl.scrollIntoView === 'function') {
        try { activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' }); } catch {}
    }
}

// ─── SF4 (#632): pasek statusu gracza — trwała warstwa aktywnych kondycji nad kompozerem ───
// Glif z COND_BADGE_MAP, nazwa z katalogu (CONDITION_META_CACHE) → snapshot `label` → key.
// Poziom „N/M" tylko dla kondycji stackowalnych (effect_json.stacking_levels.max_level > 1).
// Front NIC nie liczy — poziom i etykiety pochodzą ze snapshotu / katalogu (S9 luka: poziom widoczny).
function _sfConditionMaxLevel(cond) {
    let efx = cond?.effect_json;
    if (typeof efx === 'string') {
        try { efx = JSON.parse(efx); } catch { efx = null; }
    }
    const effects = Array.isArray(efx?.effects) ? efx.effects
        : (Array.isArray(cond?.effects) ? cond.effects : []);
    let max = 1;
    for (const e of effects) {
        if (e && String(e.type || '').toLowerCase() === 'stacking_levels') {
            const m = parseInt(e.max_level, 10);
            if (Number.isFinite(m) && m > max) max = m;
        }
    }
    return max;
}

function _sfConditionLevel(cond) {
    const lvl = parseInt(cond?.runtime?.level, 10);
    return Number.isFinite(lvl) && lvl >= 1 ? lvl : 1;
}

function renderPlayerStatusBar(player) {
    const bar = document.getElementById('combat-player-status');
    if (!bar) return;
    const conds = Array.isArray(player?.conditions) ? player.conditions : [];
    if (!conds.length) {
        bar.hidden = true;
        bar.innerHTML = '';
        return;
    }
    const meta = CONDITION_META_CACHE.byKey || {};
    const chips = conds.map(c => {
        const key = String(c?.key || c?.label || '').trim().toLowerCase();
        if (!key) return '';
        const badge = COND_BADGE_MAP[key] || { glyph: '•', variant: 'generic' };
        const labelPL = meta[key]?.label || c?.label || badge.label || key;
        const desc = meta[key]?.description || '';
        const tip = desc ? `${labelPL} — ${desc}` : labelPL;
        const maxLvl = _sfConditionMaxLevel(c);
        let levelHTML = '';
        if (maxLvl > 1) {
            const lvl = Math.min(_sfConditionLevel(c), maxLvl);
            levelHTML = `<span class="combat-status-chip__level">${lvl}/${maxLvl}</span>`;
        }
        return `<span class="combat-status-chip combat-status-chip--${badge.variant}" title="${escapeHtml(tip)}">`
            + `<span class="combat-status-chip__glyph" aria-hidden="true">${badge.glyph}</span>`
            + `<span class="combat-status-chip__label">${escapeHtml(labelPL)}</span>`
            + levelHTML
            + `</span>`;
    }).filter(Boolean).join('');
    bar.innerHTML = chips;
    bar.hidden = !chips;
}
// Kontrakt SF4 (test Playwright #632): render czyta player.conditions[] z dowolnego snapshotu.
window.__sfRenderPlayerStatusBar = renderPlayerStatusBar;

// SF2 (#620): status założonej tarczy (slot off_hand). Czytany z inventory; odświeżany na starcie
// walki (refreshCombatShieldFlag) i przy ładowaniu arkusza postaci. Steruje wyszarzeniem „Blok".
let _equippedShield = false;

// SF2 (#620): ustaw stan dostępności pozycji arkusza — wyszarzona + powód zamiast znikania.
// available=false → klasa is-unavailable + widoczny powód; available=true → powód ukryty.
function setSheetAvail(btn, available, reason) {
    if (!btn) return;
    btn.classList.toggle('is-unavailable', !available);
    const r = btn.querySelector('.combat-btn__reason');
    if (r) {
        if (available || !reason) {
            r.hidden = true;
        } else {
            r.textContent = reason;
            r.hidden = false;
        }
    }
}

// SF3 (#631): reakcja (Unik/Blok) jako toggle „uzbrojony" — wizualnie różny od akcji zużywającej turę.
// CZYTA stan z combat snapshot (player.reaction_declared); nic nie liczy. `declared` == true →
// poświata (.is-armed) + linijka „uzbrojony" + etykieta „✓". Po rozładowaniu (snapshot bez
// reaction_declared) gaśnie. Wystawiony na window dla testu kontraktu Playwright (#631).
function renderReactionToggle(btn, labelEl, declared, baseLabel) {
    if (!btn) return;
    btn.classList.toggle('is-active', !!declared);
    btn.classList.toggle('is-armed', !!declared);
    if (labelEl) labelEl.textContent = declared ? `${baseLabel} ✓` : baseLabel;
    const armed = btn.querySelector('.combat-btn__armed');
    if (armed) armed.hidden = !declared;
}
window.__sfRenderReactionToggle = renderReactionToggle;

// SF2 (#620): odśwież status tarczy na starcie walki (inventory nie zawsze załadowane wcześniej).
async function refreshCombatShieldFlag() {
    if (!characterData?.id) return;
    try {
        const resp = await fetch(`/api/inventory/${characterData.id}`).then(r => r.json());
        const items = Array.isArray(resp?.data) ? resp.data : [];
        _equippedShield = items.some(it =>
            Number(it.equipped) === 1 && String(it.slot) === 'off_hand' &&
            (String(it.item_type || '').toLowerCase() === 'armor' ||
             /shield|tarcz/.test(String(it.item_key || it.label || '').toLowerCase())));
        if (lastCombatState) renderCombatUI(lastCombatState);
    } catch { /* brak danych → zostaw poprzedni stan */ }
}

// #967 — kompaktowa linia uczestnika (Wariant D): JEDNA linia z inline HP barem.
// Nic nie ukryte względem starych kart: HP liczby+pasek, DEF, INI, strefa (🗡/🏹),
// warunki, cel (🎯), a u gracza absorb tarczy + ostrzeżenie trwałości broni.
// Czysta funkcja (zależna tylko od argumentów + globalnych helperów) — wystawiona na window
// dla kontraktu Playwright. opts: { isActive, isTarget }. isTarget=undefined → liczone z selectedTargetId.
function combatLineHtml(c, opts = {}) {
    const isPlayer = c.type === 'player';
    const isActive = !!opts.isActive;
    const hpCur = Math.max(0, Number(c.hp_current ?? 0));
    const hpMax = Math.max(1, Number(c.hp_max ?? hpCur ?? 1));
    const pct = Math.max(0, Math.min(100, Math.round((hpCur / hpMax) * 100)));
    const dead = hpCur <= 0;
    const tier = pct > _woundThresholds.healthy_pct ? 'hi' : (pct > _woundThresholds.critical_pct ? 'mid' : 'lo');
    const def = c.defense != null ? `<span class="cline__def">DEF ${c.defense}</span>` : '';
    const ini = c.initiative_roll != null ? `<span class="cline__ini">INI ${c.initiative_roll}</span>` : '';
    const hpbar = `<span class="cline__hpbar cline__hpbar--${tier}" aria-hidden="true"><i style="width:${pct}%"></i></span>`;
    const wound = !dead ? renderWoundLabelHTML(hpCur, hpMax) : '';
    const activeCls = isActive ? ' cline--active' : '';

    if (isPlayer) {
        const _absorb = Math.max(0, Number(c.absorb_hp ?? 0));   // B10 (#657): pula absorpcji tarczy
        const _pz = String(c.zone || 'engaged');
        const _zoneBadge = _pz === 'ranged'
            ? '<span class="cline__zone" title="Jesteś na dystansie">🏹</span>'
            : '<span class="cline__zone" title="Jesteś w zwarciu">🗡</span>';
        const conds = _renderConditionBadges(Array.isArray(c.conditions) ? c.conditions : []);
        const wpn = _equippedDurability.weapon;
        let duraWarn = '';
        if (wpn && wpn.broken) {
            duraWarn = `<div class="cline__dura cline__dura--broken">⚔ Oręż pęknięty — ciosy słabsze (−${wpn.penalty_pct}%)</div>`;
        } else if (wpn && Number(wpn.pct) <= 20) {
            duraWarn = `<div class="cline__dura">⚔ Oręż ledwo trzyma się rękojeści (${wpn.pct}%)</div>`;
        }
        return `
            <div class="cline cline--you${activeCls}">
                <span class="cline__tag">TY</span>
                <span class="cline__name">${escapeHtml(c.name || 'Bohater')}</span>
                <span class="cline__hp">❤ ${hpCur} / ${hpMax}</span>
                ${hpbar}
                ${_absorb > 0 ? `<span class="cline__absorb" title="Absorpcja tarczy">🛡 ${_absorb}</span>` : ''}
                ${def}${ini}${_zoneBadge}
                ${conds ? `<span class="cline__conds">${conds}</span>` : ''}
                ${wound}
                ${duraWarn}
            </div>`;
    }

    // ── wróg ──
    const name = String(c.name || c.enemy_key || 'Wróg');
    const _rowConds = Array.isArray(c.conditions) ? c.conditions : [];
    const _surprised = _rowConds.some(cc => cc && String(cc.key || '').toLowerCase() === 'zaskoczony');
    const _surpriseBadge = _surprised
        ? `<span class="cline__surprise" title="Zaskoczony — atak +2, pierwsze trafienie podwaja obrażenia">⚡</span>`
        : '';
    const _isTarget = opts.isTarget != null
        ? (!!opts.isTarget && !dead)
        : (!dead && selectedTargetId != null && String(c.id) === String(selectedTargetId));
    const _targetable = !dead ? 'cline--targetable' : '';
    const _targetSel = _isTarget ? 'cline--target' : '';
    const _targetAttr = !dead ? ` data-target-id="${escapeHtml(String(c.id))}" role="button" tabindex="0" title="Kliknij, aby celować w tego wroga"` : '';
    const _targetBadge = _isTarget ? `<span class="cline__target" title="Wybrany cel">🎯</span>` : '';
    const _ez = String(c.zone || 'engaged');
    const _ezBadge = _ez === 'ranged'
        ? '<span class="cline__zone" title="Na dystans — daleko od ciebie">🏹</span>'
        : '<span class="cline__zone" title="W zwarciu — blisko ciebie">🗡</span>';
    const conds = !dead ? _renderConditionBadges(_rowConds) : '';
    return `
        <div class="cline cline--enemy${activeCls} ${dead ? 'cline--dead' : ''} ${_targetable} ${_targetSel}"${_targetAttr}>
            ${dead ? '<span class="cline__zone">💀</span>' : _ezBadge}
            <span class="cline__name${dead ? ' cline__name--dead' : ''}">${escapeHtml(name)}</span>
            <span class="cline__hp">❤ ${hpCur} / ${hpMax}</span>
            ${dead ? '' : hpbar}
            ${def}${ini}
            ${_surpriseBadge}
            ${conds ? `<span class="cline__conds">${conds}</span>` : ''}
            ${wound}
            ${_targetBadge}
        </div>`;
}
window.combatLineHtml = combatLineHtml;

function renderCombatUI(cs) {
    // Stage 7 C1 — warm the condition meta cache so chip tooltips have descriptions.
    // First call hits the network; subsequent calls are cached (5-min TTL).
    _ensureConditionMeta().catch(() => {});

    const round = Number(cs.round || 1);
    elements.combatRound.textContent = `Runda ${round}`;

    const combatants = Array.isArray(cs.combatants) ? cs.combatants : [];
    const player = combatants.find(c => c && c.type === 'player');
    const enemies = combatants.filter(c => c && c.type === 'enemy');
    const isPlayerTurn = cs.current_turn === 'player';

    // #595: jeśli wybrany cel zginął — PRZERZUĆ focus na następnego żywego wroga
    // (kolejność inicjatywy), zamiast czyścić. Dzięki temu 🎯 widocznie przeskakuje
    // na kolejnego, a atak nie idzie w pustkę (gracz nie traci celowania po zabiciu).
    if (selectedTargetId != null) {
        const stillAlive = enemies.some(e => String(e.id) === String(selectedTargetId) && Number(e.hp_current ?? 0) > 0);
        if (!stillAlive) selectedTargetId = _nextLivingEnemyId(enemies, cs.turn_order, selectedTargetId);
    }
    _bindTargetPicker();

    _renderInitiativeTrack(cs);
    renderPlayerStatusBar(player);  // SF4 (#632): trwała warstwa aktywnych kondycji nad kompozerem

    window.clog?.event('combat_render', {
        round, current_turn: String(cs.current_turn ?? 'null'), is_player_turn: isPlayerTurn, enemy_count: enemies.length,
    });

    elements.combatTurnLabel.textContent = isPlayerTurn ? 'Twoja tura' : 'Tura wroga';
    elements.combatTurnLabel.classList.toggle('combat-banner__turn--enemy', !isPlayerTurn);
    elements.combatTurnLabel.classList.toggle('combat-banner__turn--player', isPlayerTurn);

    // Stage 7 C2 — "Tura wroga…" overlay during enemy turns.
    // Names the currently-acting enemy if combat_state pins one.
    const _currentTurnId = String(cs.current_turn ?? '');
    const _actingEnemy = !isPlayerTurn
        ? enemies.find(e => String(e?.id ?? e?.combatant_id ?? '') === _currentTurnId) || enemies[0]
        : null;
    _showEnemyTurnOverlay(!isPlayerTurn && cs.status !== 'ended', _actingEnemy?.name);

    // #967: render linii delegowany do czystej combatLineHtml (Wariant D — kompakt,
    // każdy uczestnik = jedna linia z inline HP barem). Cel liczony wewnątrz z selectedTargetId.
    const combatantRow = (c, _isPlayer, isActive = false) => combatLineHtml(c, { isActive });

    // ── Render combatants (T34 / #667) ──
    // Gracz to STAŁY punkt odniesienia poza kolumnami; kolumny = TYLKO wrogowie
    // względem gracza (engaged = blisko / ranged = daleko).
    const playerZone = String(player?.zone || 'engaged');
    const renderTo = (el, list) => { if (el) el.innerHTML = list.join(''); };
    if (elements.combatYou) elements.combatYou.innerHTML = player ? combatantRow(player, true, isPlayerTurn) : '';
    const rangedItems = [];
    const engagedItems = [];
    enemies.forEach(e => {
        const z = String(e.zone || 'engaged');
        const _enemyActive = !isPlayerTurn && String(e.id ?? e.combatant_id ?? '') === _currentTurnId;
        (z === 'ranged' ? rangedItems : engagedItems).push(combatantRow(e, false, _enemyActive));
    });
    renderTo(elements.combatZoneRanged, rangedItems);
    renderTo(elements.combatZoneEngaged, engagedItems);

    // ── Zone-change button label depends on player's current zone ──
    if (elements.btnCombatMove && elements.combatMoveLabel) {
        if (playerZone === 'engaged') {
            elements.combatMoveLabel.textContent = 'Cofnij się';
            elements.btnCombatMove.dataset.direction = 'retreat';
        } else {
            elements.combatMoveLabel.textContent = 'Zbliż się';
            elements.btnCombatMove.dataset.direction = 'approach';
        }
    }

    // SF2 (#620): pomocnicze dane dostępności — wszystko CZYTANE ze stanu, nic nie liczone.
    const _csheet = (() => { const s = characterData?.sheet_json || characterData || {}; return typeof s === 'string' ? JSON.parse(s) : s; })();
    const _skills = _csheet.skills || {};
    const _curMana = Number(_csheet.current_mana ?? 0);
    const _enemyEngaged = enemies.some(e => String(e.zone || 'engaged') === 'engaged');

    // ── SF10 (#633): pre-deklaracja zastąpiona modelem REAKTYWNYM. Toggle „uzbrojony"
    // (S15/S16) usunięty — unik/blok wybiera się w modalu przy trafieniu wroga
    // (patrz showReactionModal). Przyciski paska reakcji pozostają ukryte.
    if (elements.btnCombatDodge) elements.btnCombatDodge.hidden = true;
    if (elements.btnCombatBlock) elements.btnCombatBlock.hidden = true;

    // ── S17 (#612): zapasy — akcja bojowa. SF2 (#620): zawsze widoczna; w dystansie / bez wroga
    // w zwarciu — wyszarzona z powodem „Wymaga zwarcia" (gracz uczy się zasady).
    const _canWrestle = playerZone === 'engaged' && _enemyEngaged;
    if (elements.btnCombatWrestle) {
        elements.btnCombatWrestle.hidden = false;
        setSheetAvail(elements.btnCombatWrestle, _canWrestle, 'Wymaga zwarcia');
    }

    // ── SF2 (#620): zaklęcie — wyszarzone „Za mało many" gdy poniżej najtańszego czaru (próg startowy 2). ──
    const _spellBtn = document.getElementById('combat-spell-btn');
    const _spellHasMana = _curMana >= 2;
    setSheetAvail(_spellBtn, _spellHasMana, 'Za mało many');

    // Bramka turowa: pozycja klikalna tylko gdy tura gracza ORAZ dostępna (SF2).
    const canAct = isPlayerTurn && !combatBusy;
    const gate = (btn, available) => { if (btn) btn.disabled = !canAct || !available; };
    elements.btnCombatAttack.disabled = !canAct;
    elements.btnCombatFlee.disabled = !canAct;
    if (elements.btnCombatAction) elements.btnCombatAction.disabled = !canAct;  // SF1 (#619)
    if (!canAct) { closeCombatSheet(); closeAttackSheet(); }  // SF1 (#619)/B6c: poza turą arkusze nie wiszą
    gate(elements.btnCombatMove, true);
    gate(elements.btnCombatDodge, true);
    gate(elements.btnCombatBlock, _equippedShield);
    gate(elements.btnCombatWrestle, _canWrestle);
    gate(_spellBtn, _spellHasMana);
    window.clog?.event('combat_buttons_state', { attack_disabled: !canAct, is_player_turn: isPlayerTurn, busy: combatBusy, zone: playerZone });
}

let lastRenderedCombatTurnId = 0;

async function fetchAndAppendNewCombatTurns() {
    if (!currentCampaignId) return;
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/turns`);
        if (!r.ok) return;
        const data = await r.json().catch(() => ({}));
        const rows = Array.isArray(data.turns) ? data.turns : [];
        const newRows = rows
            .filter(row => {
                const et = String(row?.event_type || '');
                return row && (et === 'attack' || et === 'death' || et === 'zone_change' || et === 'reaction' || et === 'wrestling' || et === 'wrestling_followup' || et === 'behavior') &&
                    Number(row.id) > lastRenderedCombatTurnId;
            })
            .sort((a, b) => {
                // Death events always render after attacks in the same batch
                const da = String(a.event_type) === 'death' ? 1 : 0;
                const db = String(b.event_type) === 'death' ? 1 : 0;
                if (da !== db) return da - db;
                return Number(a.id) - Number(b.id);
            });
        for (const row of newRows) {
            appendCombatTurnCard(row);
            lastRenderedCombatTurnId = Math.max(lastRenderedCombatTurnId, Number(row.id));
        }
        if (newRows.length > 0) scrollToBottom();
    } catch (_e) {}
}

// #861: czyste helpery render dual-wield — eksportowane na window dla testów Playwright.
// Front NIC nie liczy — czyta flagi z meta combat_turn ustawione przez silnik (#598).
function combatMetaIsOffhand(meta) {
    return !!(meta && meta.offhand === true);
}
function combatParryBadgeHtml(meta) {
    const parry = Number(meta && meta.parry_bonus || 0);
    if (!(parry > 0)) return '';
    return `<div class="cturn__parry">🛡 Parujesz (+${parry} obrona) — obrażenia zredukowane</div>`;
}
if (typeof window !== 'undefined') {
    window._combatMetaIsOffhand = combatMetaIsOffhand;
    window._combatParryBadgeHtml = combatParryBadgeHtml;
}

function appendCombatTurnCard(row) {
    const evt = String(row.event_type || '');
    const actor = String(row.actor || '');
    let html = '';

    if (evt === 'reaction') {
        // S15 (#610) unik / S16 (#611) blok tarczą — wynik testu reakcji przeciw atakowi wroga.
        let meta = {};
        try { meta = typeof row.narrative === 'string' ? JSON.parse(row.narrative) : {}; } catch (_e) {}
        let txt;
        const rxType = String(meta.reaction || '');
        if (rxType === 'take') {
            txt = `💥 Przyjął cios (${meta.damage ?? 0} obrażeń)`;
        } else if (rxType === 'shield_block') {
            if (meta.full_block === true) {
                txt = `🛡 Blok pełny — atak całkowicie odparty (test ${meta.block_total ?? '?'} vs ${meta.dc ?? '?'})`;
            } else if (Number(meta.reduction || 0) > 0) {
                txt = `🛡 Blok — obrażenia zmniejszone o ${meta.reduction} (test ${meta.block_total ?? '?'} vs ${meta.dc ?? '?'})`;
            } else {
                txt = `🛡 Blok nieudany (test ${meta.block_total ?? '?'} vs ${meta.dc ?? '?'})${meta.durability_hit ? ' — tarcza uszkodzona' : ''}`;
            }
        } else {
            // dodge (or unknown fallback — always has dodge_total + attack_roll from backend)
            const dodged = meta.dodged === true;
            txt = dodged
                ? `🛡 Unik udany — atak mija (test ${meta.dodge_total ?? '?'} vs ${meta.attack_roll ?? '?'})`
                : `🛡 Unik nieudany (test ${meta.dodge_total ?? '?'} vs ${meta.attack_roll ?? '?'})${meta.locked_next_round ? ' — brak reakcji w nast. rundzie' : ''}`;
        }
        html = `<div class="cturn cturn--reaction"><span class="cturn__icon">🛡️</span><span class="cturn__text">${escapeHtml(txt)}</span></div>`;
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble chat-bubble--cturn-player';
        bubble.innerHTML = html;
        elements.chatMessages.appendChild(bubble);
        return;
    }

    if (evt === 'wrestling') {
        // S17 (#612) zapasy — test STR vs STR; stopień wyniku nakłada kondycję.
        let meta = {};
        try { meta = typeof row.narrative === 'string' ? JSON.parse(row.narrative) : {}; } catch (_e) {}
        const oc = String(meta.outcome || '');
        const rolls = `(twój ${meta.player_total ?? '?'} vs ${meta.enemy_total ?? '?'})`;
        const labels = {
            CRITICAL_SUCCESS: `💪 Chwyt mistrzowski — cel unieruchomiony ${rolls}`,
            SUCCESS: `💪 Chwyt udany — cel spowolniony ${rolls}`,
            FAILURE: `💪 Chwyt nieudany ${rolls}`,
            CRITICAL_FAILURE: `💪 Chwyt fatalny — sam przewrócony ${rolls}`
        };
        const txt = labels[oc] || `💪 Zapasy ${rolls}`;
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble chat-bubble--cturn-player';
        bubble.innerHTML = `<div class="cturn cturn--wrestling"><span class="cturn__icon">💪</span><span class="cturn__text">${escapeHtml(txt)}</span></div>`;
        elements.chatMessages.appendChild(bubble);
        return;
    }

    if (evt === 'wrestling_followup') {
        // S17-EXT (#622) — rank ≥ 3: udane zapasy dają słabszy darmowy cios (obrażenia ÷2).
        let meta = {};
        try { meta = typeof row.narrative === 'string' ? JSON.parse(row.narrative) : {}; } catch (_e) {}
        const dmg = meta.damage ?? row.damage ?? '?';
        const dead = meta.enemy_dead === true ? ' — wróg pada' : '';
        const txt = `💪 Dodatkowy cios — wróg traci ${dmg} HP (połowa obrażeń)${dead}`;
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble chat-bubble--cturn-player';
        bubble.innerHTML = `<div class="cturn cturn--wrestling"><span class="cturn__icon">💪</span><span class="cturn__text">${escapeHtml(txt)}</span></div>`;
        elements.chatMessages.appendChild(bubble);
        return;
    }

    if (evt === 'behavior') {
        // SF5 (#634) — kondycja (S18) steruje turą wroga (confused/berserk/panicked, k4).
        // Ulotny wpis ujawnia DLACZEGO wróg zrobił coś nietypowego. Front czyta narrative JSON.
        let meta = {};
        try { meta = typeof row.narrative === 'string' ? JSON.parse(row.narrative) : {}; } catch (_e) {}
        flashCombatEvent('behavior', {
            enemy_name: meta.enemy_name || row.target_name,
            action: meta.action,
            behavior: meta.behavior,
        });
        return;
    }

    if (evt === 'zone_change') {
        let meta = {};
        try { meta = typeof row.narrative === 'string' ? JSON.parse(row.narrative) : {}; } catch (_e) {}
        const who = escapeHtml(String(meta.enemy_name || (actor === 'player' ? 'Bohater' : 'Wróg')));
        const arrow = meta.to === 'engaged' ? '→' : '←';
        const where = meta.to === 'engaged' ? 'zwarcie' : 'dystans';
        const verb = meta.charged ? 'szarżuje' : (actor === 'player' ? 'przemieszcza się' : 'cofa się');
        html = `<div class="cturn cturn--move"><span class="cturn__icon">🚶</span><span class="cturn__text">${who} ${verb} ${arrow} ${where}</span></div>`;
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble chat-bubble--cturn-${actor === 'player' ? 'player' : 'enemy'}`;
        bubble.innerHTML = html;
        elements.chatMessages.appendChild(bubble);
        return;
    }

    if (evt === 'death') {
        const nar = String(row.narrative || '').trim() || 'Wróg wyeliminowany.';
        html = `<div class="cturn cturn--death"><span class="cturn__icon">💀</span><span class="cturn__text">${escapeHtml(nar)}</span></div>`;
    } else if (evt === 'attack' && actor === 'player') {
        const hit = row.hit === 1 || row.hit === true;
        const rv = row.roll_value != null ? Number(row.roll_value) : null;
        const dmg = row.damage != null ? Number(row.damage) : null;
        const tgt = escapeHtml(String(row.target_name || 'wróg'));
        let meta = {};
        try { meta = typeof row.narrative === 'string' ? JSON.parse(row.narrative) : {}; } catch (_e) {}
        // #861: drugi cios off-hand (#598 dual-wield) — osobna, wyróżniona karta.
        const offhand = combatMetaIsOffhand(meta);
        const label = escapeHtml(String(meta.attack_label || 'ATAK'));
        const headIcon = offhand ? '🗡️🗡️' : '⚔️';
        const headLabel = offhand ? `DRUGI CIOS · ${label}` : label;
        const stat = meta.attack_stat ? ` · ${escapeHtml(String(meta.attack_stat).toUpperCase())}` : '';
        const ac = meta.target_ac != null ? ` vs AC ${meta.target_ac}` : '';
        const hitLine = hit
            ? `<span class="cturn__hit">✅ TRAFIENIE · ${dmg != null ? dmg : '?'} obrażeń</span>`
            : `<span class="cturn__miss">❌ PUDŁO</span>`;
        // SF8 (#637) — rozbicie rzutu po nazwanym źródle (z live response, jednorazowo).
        // Off-hand nie konsumuje breakdownu głównego ciosu — należy do main-handa.
        let breakdownLine = '';
        if (!offhand) {
            const bd = window._pendingAttackBreakdown;
            window._pendingAttackBreakdown = null;
            if (bd && Array.isArray(bd.parts) && bd.parts.length) {
                breakdownLine = `<div class="cturn__breakdown">🎲 ${bd.d20} ${sf8BreakdownHtml(bd.parts)} = <strong>${bd.total}</strong></div>`;
            }
        }
        html = `<div class="cturn cturn--player${offhand ? ' cturn--offhand' : ''}">
            <div class="cturn__head">${headIcon} <strong>${escapeHtml(headLabel)}</strong>${stat} → ${tgt}</div>
            <div class="cturn__detail">Rzut: ${rv != null ? rv : '—'}${ac} → ${hitLine}</div>
            ${breakdownLine}
        </div>`;
    } else if (evt === 'attack' && actor === 'enemy') {
        const hit = row.hit === 1 || row.hit === true;
        const rv = row.roll_value != null ? Number(row.roll_value) : null;
        const dmg = row.damage != null ? Number(row.damage) : null;
        let meta = {};
        try { meta = typeof row.narrative === 'string' ? JSON.parse(row.narrative) : {}; } catch (_e) {}
        const rawD20 = meta.raw_d20 != null ? meta.raw_d20 : rv;
        const enemyName = escapeHtml(String(meta.enemy_name || row.target_name || 'Wróg'));
        // #828: pokaż pasywny unik gracza (d20+DEX) gdy dostępny, nie AC (AC = redukcja pancerza, nie próg trafienia)
        const pev = meta.player_evasion;
        const vsLabel = pev && pev.total != null
            ? ` vs Unik ${pev.total} (d20 ${pev.raw}+ZRC ${pev.dex_mod})`
            : (meta.target_ac != null ? ` vs AC ${meta.target_ac}` : '');
        const hitLine = hit
            ? `<span class="cturn__hit">✅ TRAFIENIE · ${dmg != null ? dmg : '?'} obrażeń</span>`
            : `<span class="cturn__miss">❌ PUDŁO</span>`;
        // #861: parowanie (#598) — badge + nota o zredukowanych obrażeniach.
        const parryBadge = combatParryBadgeHtml(meta);
        html = `<div class="cturn cturn--enemy${parryBadge ? ' cturn--parried' : ''}">
            <div class="cturn__head">🗡️ <strong>ATAK WROGA</strong> — ${enemyName}</div>
            <div class="cturn__detail">Rzut: ${rawD20 != null ? rawD20 : '—'}${vsLabel} → ${hitLine}</div>
            ${parryBadge}
        </div>`;
    }

    if (!html) return;
    const bubble = document.createElement('div');
    const side = actor === 'player' ? 'player' : (actor === 'enemy' ? 'enemy' : 'death');
    bubble.className = `chat-bubble chat-bubble--cturn-${side}`;
    bubble.innerHTML = html;
    elements.chatMessages.appendChild(bubble);
}

// #595: cel wybrany ręcznie przez gracza (klik w wiersz wroga). null = auto-wybór
// (pierwszy żywy w inicjatywie). Po śmierci celu — przeskok na następnego żywego.
let selectedTargetId = null;

// #595: następny ŻYWY wróg po zabitym `deadId` (kolejność inicjatywy, z zawijaniem).
// Zwraca id następnego żywego za pozycją deadId; gdy brak za nim — pierwszy żywy
// przed nim; gdy deadId spoza turn_order — pierwszy żywy w ogóle; null gdy brak żywych.
function _nextLivingEnemyId(enemies, turnOrder, deadId) {
    const livingIds = new Set(
        (Array.isArray(enemies) ? enemies : [])
            .filter(e => e && Number(e.hp_current ?? 0) > 0)
            .map(e => String(e.id)),
    );
    if (!livingIds.size) return null;
    const ord = Array.isArray(turnOrder) ? turnOrder.map(String) : [];
    const pos = ord.indexOf(String(deadId));
    if (pos >= 0) {
        for (let i = pos + 1; i < ord.length; i++) if (livingIds.has(ord[i])) return ord[i];
        for (let i = 0; i < pos; i++) if (livingIds.has(ord[i])) return ord[i];
    }
    for (const id of ord) if (livingIds.has(id)) return id;
    return [...livingIds][0];
}
if (typeof window !== 'undefined') window._nextLivingEnemyId = _nextLivingEnemyId;
let _targetPickerBound = false;

// #595: delegacja kliknięć na kolumnach stref — klik/Enter w wiersz wroga ustawia cel.
// Bindowane raz; reaguje na data-target-id wstrzyknięty w combatantRow.
function _bindTargetPicker() {
    if (_targetPickerBound) return;
    const handler = (ev) => {
        const row = ev.target.closest?.('.combat-combatant--targetable');
        if (!row) return;
        const tid = row.dataset.targetId;
        if (!tid) return;
        // toggle: ponowny klik w ten sam cel wraca do auto-wyboru.
        selectedTargetId = (String(selectedTargetId) === String(tid)) ? null : String(tid);
        window.clog?.event('combat_target_selected', { target_id: selectedTargetId });
        if (lastCombatState) renderCombatUI(lastCombatState);
    };
    [elements.combatZoneRanged, elements.combatZoneEngaged].forEach(el => {
        if (!el) return;
        el.addEventListener('click', handler);
        el.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); handler(ev); }
        });
    });
    _targetPickerBound = true;
}

function pickEnemyTarget(cs) {
    const combatants = Array.isArray(cs?.combatants) ? cs.combatants : [];
    const living = combatants.filter(c => c && c.type === 'enemy' && Number(c.hp_current ?? 0) > 0);
    if (!living.length) return null;
    // #595: jeśli gracz kliknął cel i ten cel wciąż żyje — honoruj wybór.
    if (selectedTargetId != null) {
        const chosen = living.find(e => String(e.id) === String(selectedTargetId));
        if (chosen) return chosen;
    }
    const order = Array.isArray(cs.turn_order) ? cs.turn_order : [];
    const livingSet = new Set(living.map(e => String(e.id)));
    for (const tid of order) {
        if (livingSet.has(String(tid))) {
            return living.find(e => String(e.id) === String(tid)) || null;
        }
    }
    return living[0] || null;
}

// #661: build the second-stage (damage / heal) animation descriptor from a
// resolve-attack response. Returns null when there is nothing to roll (miss,
// effect/defense spell, no damage notation). The backend now carries the raw
// per-die results (damage_rolls / heal_rolls) so the 3D box lands on them.
function buildDamageStage(data) {
    if (!data) return null;
    // Heal spell (mend_wounds 2d6 etc.) — show heal dice.
    if (data.spell_type === 'heal' && data.heal_die) {
        const rolls = Array.isArray(data.heal_rolls) ? data.heal_rolls : null;
        const total = Number(data.heal_amount ?? data.healed ?? 0);
        if (total > 0 || (rolls && rolls.length)) {
            return { notation: data.heal_die, rolls, total, modifier: Number(data.heal_modifier ?? 0), label: 'Leczenie', kind: 'heal' };
        }
        return null;
    }
    // Attacking weapon/spell (single + AoE primary) — only on a hit with damage.
    if (data.hit && data.damage_die && Number(data.damage ?? 0) > 0) {
        const rolls = Array.isArray(data.damage_rolls) ? data.damage_rolls : null;
        return {
            notation: data.damage_die,
            rolls,
            total: Number(data.damage ?? 0),
            modifier: Number(data.damage_modifier ?? 0),
            multiplier: Number(data.damage_multiplier ?? 1),
            armorReduction: Number(data.armor_reduction ?? 0),
            label: 'Obrażenia',
            kind: 'damage',
        };
    }
    return null;
}

// #829: modern 3D dice (@3d-dice/dice-box-threejs). Replaces the flaky 2015 dice.js
// for COMBAT rolls — it's maintained (THREE r143 + Cannon-ES), renders reliably on
// mobile, and supports predetermined results (`1d20@15`) so the die lands on the
// value the backend already rolled. Lazy singleton bound to #dice3d-container.
let _dice3d = null;
let _dice3dInit = null;       // Promise that resolves when the box finished async init.
let _dice3dFailed = false;
let _dice3dRemoteConfig = null;  // #850: loaded from /api/game/dice-config on enterGame

// #850: Fetch admin-saved dice config (no auth). Stores result for ensureDice3D() to pick up.
async function _fetchDice3DConfig() {
    try {
        const r = await fetch('/api/game/dice-config');
        if (r.ok) { _dice3dRemoteConfig = (await r.json()).config || null; }
    } catch (_e) {}
}

// #829 RECREATE-PER-ROLL: build a BRAND-NEW dice box + fresh #dice3d-container for THIS roll.
// A reused singleton re-rolls into an already-settled canvas; the mobile compositor never
// repaints it, so only the first 3D roll of a session shows (every later attack/damage roll is
// blank). Admin _previewDiceRoll (system.js) renders a dozen rolls in a row on the SAME phone
// precisely because it destroys the container + WebGL context and rebuilds the box each time.
// We mirror that here: remove the old container, createElement a fresh one, new Ctor. initialize()
// reloads assets but they're browser-cached after the first roll → cheap. Returns the box (init
// promise on `_dice3dInit`) or null if the lib/container is unavailable.
function buildDice3DBox() {
    if (_dice3dFailed) return null;
    const Ctor = window['dice-box-threejs'];
    const overlay = document.getElementById('dice-overlay');
    if (typeof Ctor !== 'function' || !overlay) { _dice3dFailed = true; return null; }
    // Destroy the previous container (clears its canvas + WebGL context), then mount a fresh one
    // right after the legacy #dice-container so stacking/CSS stays identical to the static markup.
    const old = document.getElementById('dice3d-container');
    if (old) { try { old.remove(); } catch (_e) {} }
    const el = document.createElement('div');
    el.id = 'dice3d-container';
    const legacy = document.getElementById('dice-container');
    if (legacy && legacy.parentNode === overlay) overlay.insertBefore(el, legacy.nextSibling);
    else overlay.appendChild(el);
    // #850: merge admin config over defaults; admin may override colorset/texture/physics
    const rc = _dice3dRemoteConfig || {};
    const cc = rc.customColorset || {};
    try {
        _dice3d = new Ctor('#dice3d-container', {
            assetPath: '/vendor/dice-box-threejs/',
            sounds: false,
            shadows: true,
            ...(cc.foreground ? {
                theme_customColorset: {
                    foreground: cc.foreground,
                    background: cc.background || ['#1b1107'],
                    outline: cc.outline || '#c08020',
                    texture: cc.texture || 'fire',
                    material: cc.material || 'plastic',
                },
            } : {
                theme_colorset: 'white',
                theme_texture: '',
                theme_material: 'plastic',
            }),
            gravity_multiplier: rc.gravity_multiplier ?? 400,
            light_intensity: rc.light_intensity ?? 0.9,
            baseScale: rc.baseScale ?? 100,
            strength: rc.strength ?? 1.4,
        });
        // initialize() is async (loads assets, builds scene). roll() before it resolves
        // throws "renderer undefined", so every roll must await this first.
        _dice3dInit = Promise.resolve(_dice3d.initialize());
    } catch (_e) {
        _dice3dFailed = true; _dice3d = null;
        window.clog?.warn?.('dice3d_init_failed', { error: String(_e && _e.message || _e) });
        return null;
    }
    return _dice3d;
}

// Pre-warm the 3D engine so the first combat roll isn't delayed by asset loading. With
// recreate-per-roll the first real roll rebuilds the box anyway, but this primes the browser
// asset cache (textures/lib) so that rebuild is cheap.
function prewarmDice3D() { try { buildDice3DBox(); } catch (_e) {} }

// Clear any settled 3D dice (called on overlay close). With recreate-per-roll the next roll
// rebuilds the container outright, so this just wipes the currently-settled dice.
function clearDice3D() {
    if (!_dice3d) return;
    try { if (typeof _dice3d.clearDice === 'function') _dice3d.clearDice(); else if (typeof _dice3d.clear === 'function') _dice3d.clear(); } catch (_e) {}
}

// Roll `notation` (e.g. '1d20', '2d6') landing on `forced` (per-die results from the
// backend) and call `onComplete` once the dice settle. Builds a FRESH 3D box for this roll
// (recreate-per-roll, see buildDice3DBox); on ANY failure (lib missing, init/roll error, or
// stall) falls back to the reliable 2D dice so the player ALWAYS sees a roll.
// `kind` ('attack'|'damage'|'heal') steers the 2D look.
function rollDiceVisual(notation, forced, kind, onComplete) {
    let _done = false;
    const finish = () => { if (_done) return; _done = true; onComplete(); };
    const el2d = document.getElementById('dice-container');
    const fallback2d = () => { if (_done) return; play2dDiceRoll(el2d, { notation, rolls: forced, kind }, forced, finish); };

    const box = buildDice3DBox();   // #829 RECREATE-PER-ROLL — fresh box + container every roll
    if (!box) { fallback2d(); return; }
    const initPromise = _dice3dInit;

    // Predetermined notation lands each die on the backend's exact result: "2d6@3,5".
    const predet = (Array.isArray(forced) && forced.length)
        ? `${notation}@${forced.join(',')}`
        : String(notation);
    // Backstop: covers async init + animation. If the 3D roll never reports back, show
    // the result anyway (don't hang the veil). Generous because the FIRST roll also waits
    // for asset loading (~1-2s) on top of the ~2.5s animation.
    const backstop = setTimeout(finish, 9000);

    initPromise.then(() => {
        if (!box || box.initialized !== true) throw new Error('dice3d not initialized');
        box.onRollComplete = () => { clearTimeout(backstop); setTimeout(finish, 550); };
        const p = box.roll(predet);
        // roll() may also return a promise; swallow its rejection (onRollComplete drives us).
        if (p && typeof p.catch === 'function') p.catch(() => {});
    }).catch((_e) => {
        clearTimeout(backstop);
        // A roll failure is per-instance with recreate-per-roll; don't latch _dice3dFailed
        // (that would force every later roll to 2D). Just fall back for THIS roll.
        window.clog?.warn?.('dice3d_roll_failed', { error: String(_e && _e.message || _e) });
        fallback2d();
    });
}

// #829: reliable 2D damage-dice animation for Stage 2. The 3D library's second
// throw (after the d20) is invisible on many player devices — the WebGL context
// does not repaint the re-roll and the physics never settles (always backstop).
// This 2D roll is pure DOM/CSS: it tumbles random faces, then lands each die on
// the backend's per-die result. Cannot fail, always visible. `onDone` fires after
// the dice settle so the result card can reveal.
function play2dDiceRoll(container, ds, forced, onDone) {
    // Drop any lingering 3D canvas content (the settled d20) so it doesn't show behind.
    if (_diceBox && typeof _diceBox.clear === 'function') { try { _diceBox.clear(); } catch (_e) {} }
    const sides = Math.max(2, parseInt(String(ds.notation || '1d6').split('d')[1], 10) || 6);
    const finals = (Array.isArray(forced) && forced.length)
        ? forced.slice(0, 8)
        : [Math.max(1, Number(ds.total) || 1)];
    const isHeal = ds.kind === 'heal';

    const wrap = document.createElement('div');
    wrap.className = 'dice2d-wrap';
    finals.forEach(() => {
        const d = document.createElement('div');
        d.className = 'dice2d-die' + (isHeal ? ' dice2d-die--heal' : '');
        d.textContent = '?';
        wrap.appendChild(d);
    });
    container.appendChild(wrap);
    const dice = Array.from(wrap.children);

    let ticks = 0;
    const TICKS = 13;
    const iv = setInterval(() => {
        dice.forEach((d) => { d.textContent = String(1 + Math.floor(Math.random() * sides)); });
        if (++ticks >= TICKS) {
            clearInterval(iv);
            dice.forEach((d, i) => {
                d.textContent = String(finals[i] ?? finals[0]);
                d.classList.add('dice2d-die--land');
            });
            setTimeout(() => { try { wrap.remove(); } catch (_e) {} onDone(); }, 650);
        }
    }, 60);
}

// #569 / #661: visible 3D dice modal for combat rolls. Reuses the skill-test
// dice-overlay + DICE.dice_box. Stage 1 = the d20 attack (lands on pre-rolled
// forcedD20). Stage 2 (optional, `damageStage`) = the NdX damage/heal roll,
// landing on the backend's per-die results. Returns a Promise that resolves when
// the modal closes (auto-dwell or on click) so combat can continue.
function playCombatDiceRoll(forcedD20, label, breakdown = null, damageStage = null, outcome = null) {
    _diceAnimationActive = true;  // #984: blokuj poll przed handleCombatEnded
    return new Promise((resolve) => {
        const overlay     = document.getElementById('dice-overlay');
        const container   = document.getElementById('dice-container');
        const skillCard   = document.getElementById('dice-skill-card');
        const skipBtn     = document.getElementById('dice-skip-btn');
        const resultCard  = document.getElementById('dice-result-card');
        const resultSkill = document.getElementById('dice-result-skill');
        const resultIntent= document.getElementById('dice-result-intent');
        const resultNum   = document.getElementById('dice-result-num');
        const resultTot   = document.getElementById('dice-result-total');
        const resultVerd  = document.getElementById('dice-result-verdict');
        if (!overlay || !container || !resultCard || !resultNum) { _diceAnimationActive = false; resolve(); return; }

        const d20 = Math.max(1, Math.min(20, parseInt(forcedD20, 10) || 1));

        // #669: wyczyść scenę 3D + kartę wyniku PRZED pokazaniem overlay, inaczej
        // przez ≥1 klatkę widać „ducha" poprzedniego rzutu (osiadłą kostkę / stary wynik).
        if (_diceBox && typeof _diceBox.clear === 'function') { try { _diceBox.clear(); } catch (_e) {} }
        resultCard.hidden = true;
        resultNum.textContent = ''; resultNum.className = '';
        if (resultVerd) { resultVerd.textContent = ''; resultVerd.className = ''; }
        if (resultTot)  resultTot.textContent = '';

        if (resultIntent) resultIntent.hidden = true;
        if (skillCard) skillCard.hidden = true;
        if (skipBtn)   skipBtn.style.display = 'none';   // combat roll ≠ skill-test: no "back to campaigns"
        overlay.hidden = false;

        let _done = false;
        let _clickHandler = null;
        const cleanup = () => {
            if (_done) return;
            _done = true;
            if (_clickHandler) overlay.removeEventListener('click', _clickHandler);
            _clickHandler = null;
            overlay.hidden = true;
            // #669: sprzątnij osiadłą kostkę przy zamknięciu, by nie została na poprzednim wyniku.
            if (_diceBox && typeof _diceBox.clear === 'function') { try { _diceBox.clear(); } catch (_e) {} }
            clearDice3D();  // #829: also clear the modern 3D dice
            if (skillCard) skillCard.hidden = false;
            if (skipBtn)   skipBtn.style.display = '';
            _diceAnimationActive = false;  // #984: odblokuj poll — animacja gotowa
            resolve();
        };

        // Arm a timed advance with click-to-skip; the first of timer/click wins.
        const armAdvance = (delay, advance) => {
            let fired = false;
            const go = () => {
                if (fired) return; fired = true;
                if (_clickHandler) overlay.removeEventListener('click', _clickHandler);
                _clickHandler = null;
                advance();
            };
            _clickHandler = go;
            overlay.addEventListener('click', go);
            setTimeout(go, delay);
        };

        // #829 (recydywa): the old inner `throwDice` (legacy DICE.dice_box reuse) was removed —
        // it was dead code (both stages route through rollDiceVisual / dice-box-threejs) and its
        // "reuse the same context" comment misled three earlier fix attempts. Combat dice now
        // recreate the box per roll (see buildDice3DBox / rollDiceVisual above).

        // ── Stage 2: damage / heal ──────────────────────────────────────────
        const runDamageStage = () => {
            const ds = damageStage;
            const forced = (Array.isArray(ds.rolls) && ds.rolls.length) ? ds.rolls : null;
            resultCard.hidden = true;
            resultNum.textContent = ''; resultNum.className = '';
            resultVerd.textContent = ''; resultVerd.className = '';
            if (resultSkill) resultSkill.textContent = String(ds.label || 'Obrażenia').toUpperCase();
            const showDmg = () => {
                const sum = forced ? forced.reduce((a, b) => a + b, 0) : (ds.total || 0);
                const total = (ds.total != null) ? ds.total : sum;
                resultNum.textContent = total;
                resultNum.className = ds.kind === 'heal' ? 'heal' : '';
                if (resultTot) {
                    const unit = ds.kind === 'heal' ? 'HP' : 'obrażeń';
                    let line = forced ? `🎲 ${forced.join(' + ')}` : `🎲 ${ds.notation}`;
                    if (ds.modifier) line += ` ${ds.modifier > 0 ? '+' : '−'} ${Math.abs(ds.modifier)}`;
                    if (ds.armorReduction) line += ` − ${ds.armorReduction} Pancerz`;
                    if (ds.multiplier && ds.multiplier > 1) line += ` ×${ds.multiplier}`;
                    resultTot.innerHTML = `${line}  =  <strong>${total}</strong> ${unit}`;
                }
                resultCard.hidden = false;
                // #829: dłuższe wyświetlanie karty obrażeń — gracz ma zdążyć odczytać wynik
                // (klik nadal pomija od razu). Wartość startowa, Sandbox-tunable.
                armAdvance(3200, cleanup);
            };
            // #829: Stage 2 (rzut obrażeń) — modern 3D dice (predeterminowane na wynik
            // backendu), z automatycznym fallbackiem do animacji 2D gdy WebGL zawiedzie.
            rollDiceVisual(ds.notation, forced, ds.kind || 'damage', showDmg);
        };

        const afterAttack = () => {
            if (damageStage && damageStage.notation) runDamageStage();
            else cleanup();
        };

        // ── Stage 1: d20 attack ─────────────────────────────────────────────
        const showAttack = (rolled) => {
            if (resultSkill) resultSkill.textContent = String(label || 'Atak').toUpperCase();
            resultNum.textContent = rolled;
            resultNum.className   = rolled === 20 ? 'nat20' : rolled === 1 ? 'nat1' : '';
            if (rolled === 20)      { resultVerd.textContent = '✦ Krytyczny sukces!'; resultVerd.className = 'nat20'; }
            else if (rolled === 1)  { resultVerd.textContent = '✧ Krytyczna porażka';  resultVerd.className = 'nat1'; }
            else                    { resultVerd.textContent = ''; resultVerd.className = ''; }
            // SF8 (#637) — rozbicie rzutu w oknie kości (parytet z testem umiejętności).
            let dwell = 1600;
            if (breakdown && Array.isArray(breakdown.parts) && breakdown.parts.length && resultTot) {
                resultTot.innerHTML = `🎲 ${rolled} ${sf8BreakdownHtml(breakdown.parts)}  =  <strong>${breakdown.total}</strong>`;
                dwell = 3600; // dłużej widoczne — gracz ma przeczytać składniki (wartość startowa)
            } else if (resultTot) { resultTot.textContent = 'k20'; }
            // Trafienie to test OPOZYCYJNY: Twój atak vs rzut na unik wroga (k20 + ZRC).
            // Bez tego gracz nie rozumie, czemu wysoki rzut czasem chybia, a niski trafia.
            // nat20 (auto-trafienie) / nat1 (auto-pudło) pomijamy — wróg nie rzuca uniku.
            if (outcome && outcome.dodge && rolled !== 20 && rolled !== 1 && resultTot) {
                const dg = outcome.dodge;
                const atk = Number(outcome.attack_total ?? breakdown?.total ?? rolled);
                const m = Number(dg.modifier || 0);
                const modTxt = m ? (m > 0 ? ` + ${m}` : ` − ${Math.abs(m)}`) : '';
                resultTot.innerHTML += `<div class="dice-dodge-line">🛡 Unik wroga: 🎲 ${dg.raw}${modTxt} = <strong>${dg.total}</strong> vs Twój atak <strong>${atk}</strong></div>`;
                if (outcome.dodged) { resultVerd.textContent = '🛡 Wróg uniknął ciosu'; resultVerd.className = 'dice-verdict-miss'; }
                else { resultVerd.textContent = '✔ Trafienie!'; resultVerd.className = 'dice-verdict-hit'; }
                dwell = Math.max(dwell, 3600);
            }
            resultCard.hidden = false;
            armAdvance(dwell, afterAttack);
        };

        // #653: forcedD20===null means caller wants Stage 2 only (no d20 throw).
        // Used by OOC heal spells: skip the attack roll, show only the NdX heal dice.
        if (forcedD20 === null && damageStage && damageStage.notation) {
            requestAnimationFrame(() => runDamageStage());
            return;
        }

        // #829: Stage 1 (k20 ataku) — modern 3D dice with automatic 2D fallback.
        requestAnimationFrame(() => {
            rollDiceVisual('1d20', [d20], 'attack', () => showAttack(d20));
        });
    });
}

async function handleCombatAttack() {
    window.clog?.event('combat_attack_invoked', { campaign_id: currentCampaignId, busy: combatBusy, current_turn: lastCombatState?.current_turn ?? null });
    if (!combatActive || !currentCampaignId || combatBusy || enemyTurnInFlight) {
        window.clog?.warn('combat_attack_blocked', { reason: !combatActive ? 'no_combat' : 'busy' });
        return;
    }
    if (lastCombatState?.current_turn !== 'player') {
        setCombatMsg('Nie twoja tura.', true);
        return;
    }
    combatBusy = true; playerActionFetchActive = true;  // #700
    elements.btnCombatAttack.disabled = true;
    elements.btnCombatFlee.disabled = true;
    setCombatMsg('Rzucam k20...');

    try {
        const diceResp = await fetch('/api/gm/dice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dice: '1d20' })
        });
        if (!diceResp.ok) throw new Error(`Kość: HTTP ${diceResp.status}`);
        const diceData = await diceResp.json();
        const d20 = Number(diceData.total ?? 0);

        const target = pickEnemyTarget(lastCombatState);
        const body = { raw_d20: d20, attacker: 'player' };
        if (target?.enemy_key) body.enemy_key = String(target.enemy_key);
        if (target?.id) body.target_id = String(target.id);

        // SF8 (#637): rozlicz atak PRZED animacją kości, żeby okno mogło pokazać
        // rozbicie wyniku (składniki liczy silnik). d20 jest predeterminowany —
        // animacja i tak ląduje na nim, więc kolejność nie zmienia wyniku.
        window.clog?.event('combat_resolve_attack_request', { d20 });
        playerActionFetchActive = true;   // #700: realny POST akcji gracza w locie
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/resolve-attack`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await r.json().catch(() => ({}));
        playerActionFetchActive = false;  // #700: POST rozliczony (animacja/narracja to nie sieć)
        window.clog?.event('combat_resolve_attack_response', { status: r.status, hit: !!data.hit, damage: data.damage ?? 0, enemy_dead: !!data.enemy_dead });
        if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);

        // Rozbicie do okna kości + dymka (oba z tych samych policzonych składników).
        const _atk = data.attack_roll || {};
        const _bdParts = _atk.attack_stat
            ? sf8AttackBreakdown(_atk, { surprise: data.surprise_atk_bonus, durability: data.durability_attack_penalty })
            : null;
        const _bdTotal = Number(data.attack_total ?? _atk.total ?? d20);

        // #569: visible 3D dice modal (parity with skill-test rolls). Lands on the
        // already-rolled d20; SF8 — pokazuje rozbicie składników na karcie wyniku.
        // #661: po trafieniu druga animacja — rzut kośćmi obrażeń (NdX).
        const _dodgeOutcome = data.dodge_roll
            ? { dodge: data.dodge_roll, dodged: !!data.dodged, hit: !!data.hit, attack_total: Number(data.attack_total ?? _bdTotal) }
            : null;
        await playCombatDiceRoll(d20, 'Atak', _bdParts ? { parts: _bdParts, total: _bdTotal } : null, buildDamageStage(data), _dodgeOutcome);

        await _handleCombatAttackResult(data, d20, body.enemy_key, target);
    } catch (e) {
        window.clog?.error('combat_attack_exception', { message: String(e?.message || e) });
        setCombatMsg(`Błąd ataku: ${e.message || e}`, true);
    } finally {
        combatBusy = false;
        playerActionFetchActive = false;   // #700: gwarancja resetu nawet przy wyjątku
        if (combatActive) {
            if (lastCombatState && elements.combatEndOverlay?.hidden !== false) renderCombatUI(lastCombatState);
            elements.btnCombatAttack.disabled = false;
            document.getElementById('combat-spell-btn').disabled = false;
            elements.btnCombatFlee.disabled = false;
        }
    }
}

async function _handleCombatAttackResult(data, d20, enemyKey, target) {
    const atkRoll = data.attack_roll || {};
    const total = Number(atkRoll.total ?? data.total ?? d20);
    const mod = Number(atkRoll.modifier ?? 0);
    const dmg = data.damage ?? 0;
    const hit = !!data.hit;
    const targetName = data.target_name || target?.name || 'wróg';

    if (data.mana_insufficient) { setCombatMsg(data.message || 'Brak many!', true); return; }
    if (data.blocked && data.block_reason === 'out_of_range') {
        setCombatMsg(data.message || 'Cel poza zasięgiem — zbliż się.', true);
        if (data.combat_state) { lastCombatState = data.combat_state; renderCombatUI(data.combat_state); }
        return;
    }
    // #764: brak amunicji — strzał zablokowany, tura nietknięta.
    if (data.blocked && data.block_reason === 'no_ammo') {
        setCombatMsg(data.message || 'Brak amunicji — zdobądź strzały/bełty.', true);
        showToast?.(data.message || 'Brak amunicji do strzału!', 'warning');
        if (data.combat_state) { lastCombatState = data.combat_state; renderCombatUI(data.combat_state); }
        return;
    }
    // #764: po udanym strzale dystansowym zasygnalizuj pozostałą amunicję (nie nadpisuje karty trafienia).
    if (data.ammo_key && typeof data.ammo_remaining === 'number') {
        const ammoPl = data.ammo_key === 'bolts' ? 'bełtów' : 'strzał';
        showToast?.(`🏹 Pozostało ${data.ammo_remaining} ${ammoPl}`, data.ammo_remaining <= 3 ? 'warning' : 'info');
    }
    // B9 (#656): czar NIE-atakujący (kondycja) — pojedynek INT vs WIS/CON, NIE obrażenia.
    // Karta pokazuje „łapie / opór / pomyłka", bez liczby obrażeń.
    if (data.spell_type === 'effect' || data.spell_effect || data.block_reason === 'unsupported_effect') {
        const COND_PL = {
            slowed: 'spowolniony', poisoned: 'zatruty', stunned: 'ogłuszony',
            cursed: 'przeklęty', blinded: 'oślepiony', confused: 'zdezorientowany',
        };
        const condPl = COND_PL[data.condition_key] || data.condition_key || 'efekt';
        const se = data.spell_effect || {};
        if (data.block_reason === 'unsupported_effect') {
            setCombatMsg(data.message || 'Ten czar nie działa jeszcze w walce.', true);
        } else if (data.condition_applied) {
            setCombatMsg(`Czar łapie — wróg ${condPl}.`);
        } else if (se.outcome === 'miscast' || data.player_nat1) {
            setCombatMsg('Czar wymyka się spod kontroli!', true);
            triggerCritFlash('fumble');
        } else {
            const refund = Number(data.mana_refund || 0);
            setCombatMsg(`Wróg opiera się${refund ? ` — ${refund} many wraca` : ''}.`);
        }
        const csE = data.combat_state || null;
        if (csE) { lastCombatState = csE; renderCombatUI(csE); }
        await fetchAndAppendNewCombatTurns();
        const payloadE = {
            kind: 'player_attack',
            character_name: characterData?.name || 'Bohater',
            d20, modifiers: [], total: d20,
            hit: !!data.condition_applied, damage: 0,
            target_name: targetName, enemy_key: enemyKey || '',
            attack_mode: 'spell',
            spell_label: data.weapon_label || 'zaklęcie',
            spell_effect: se.outcome || (data.block_reason === 'unsupported_effect' ? 'unsupported' : null),
            condition_applied: !!data.condition_applied,
            condition_pl: condPl,
        };
        await sendCombatNarration(`${COMBAT_ROLL_PREFIX}\n${JSON.stringify(payloadE)}`);
        await refreshCharacterData();
        // #848: trigger enemy turn poll when server already advanced turn after player action
        if (csE && csE.current_turn !== 'player' && csE.status === 'active') await pollCombatState();
        return;
    }
    // B10 (#657): czar OBRONNY — nakłada pulę absorpcji (temp-HP), NIE atakuje wroga.
    if (data.spell_type === 'defense') {
        const absorb = Number(data.absorb_granted || data.absorb_hp || 0);
        setCombatMsg(`🛡 Tarcza aktywna — pochłonie ${absorb} obrażeń.`);
        const csD = data.combat_state || null;
        if (csD) { lastCombatState = csD; renderCombatUI(csD); }
        await fetchAndAppendNewCombatTurns();
        const payloadD = {
            kind: 'player_attack',
            character_name: characterData?.name || 'Bohater',
            d20, modifiers: [], total: d20, hit: true, damage: 0,
            target_name: targetName, enemy_key: enemyKey || '',
            attack_mode: 'spell',
            spell_label: data.weapon_label || 'tarcza',
            spell_defense: true, absorb,
        };
        await sendCombatNarration(`${COMBAT_ROLL_PREFIX}\n${JSON.stringify(payloadD)}`);
        await refreshCharacterData();
        // #848: trigger enemy turn poll when server already advanced turn after player action
        if (csD && csD.current_turn !== 'player' && csD.status === 'active') await pollCombatState();
        return;
    }
    // B11 (#659): czar AoE (attack_aoe) — jeden rzut, obrażenia wielu wrogom.
    if (data.spell_type === 'attack_aoe') {
        const aoeHits = Array.isArray(data.aoe_hits) ? data.aoe_hits : [];
        const killed = aoeHits.filter(h => h.dead).length;
        if (data.miscast || data.player_nat1) {
            setCombatMsg('Czar wymyka się spod kontroli!', true);
            triggerCritFlash('fumble');
        } else if (!hit || !aoeHits.length) {
            setCombatMsg('Pudło — czar nie dosięga celów.');
        } else {
            const killNote = killed ? ` (${killed} pada)` : '';
            setCombatMsg(`💥 ${data.weapon_label || 'AoE'} — ${aoeHits.length} cele trafione${killNote}!`);
            if (data.player_nat20) triggerCritFlash('crit');
        }
        // Loot/złoto z zabitych wrogów (zsumowane ze wszystkich trafień AoE)
        const aoeLoot = [];
        let aoeGold = 0;
        for (const h of aoeHits) {
            if (h.dead) {
                if (Array.isArray(h.loot)) aoeLoot.push(...h.loot);
                aoeGold += Math.max(0, Number(h.gold_drop || 0));
            }
        }
        if (aoeLoot.length || aoeGold) { pendingLoot = aoeLoot; pendingGold = aoeGold; }
        const csA = data.combat_state || null;
        if (csA) { lastCombatState = csA; renderCombatUI(csA); }
        await fetchAndAppendNewCombatTurns();
        const payloadA = {
            kind: 'player_attack',
            character_name: characterData?.name || 'Bohater',
            d20, modifiers: [], total: d20,
            hit: !!hit, damage: Number(data.damage || 0),
            target_name: targetName, enemy_key: enemyKey || '',
            attack_mode: 'spell',
            spell_label: data.weapon_label || 'zaklęcie',
            spell_aoe: true,
            aoe_targets: aoeHits.length,
            aoe_killed: killed,
        };
        await sendCombatNarration(`${COMBAT_ROLL_PREFIX}\n${JSON.stringify(payloadA)}`);
        await refreshCharacterData();
        // #848: trigger enemy turn poll when server already advanced turn after player action
        if (csA && csA.current_turn !== 'player' && csA.status === 'active') await pollCombatState();
        return;
    }
    if (hit) { setCombatMsg(`Trafienie! ${dmg} obrażeń.`); }
    else if (data.player_nat1) { setCombatMsg('Krytyczna porażka!', true); }
    else { setCombatMsg('Pudło.'); }

    // Crit flash (T34) — fire after setCombatMsg so the message also lands
    if (data.player_nat20) triggerCritFlash('crit');
    else if (data.player_nat1) triggerCritFlash('fumble');

    const cs = data.combat_state || null;
    const endedNow = cs && cs.status === 'ended';
    const victoryNow = endedNow && cs.ended_reason === 'victory';

    if (data.enemy_dead) {
        pendingLoot = Array.isArray(data.loot) ? data.loot : [];
        pendingGold = Math.max(0, Number(data.gold_drop || 0));
    }
    // L8: boss drop is granted server-side (already in inventory) — stash it for a
    // reveal-only "co wypadło z bossa" popup shown before the go-deeper/exit choice.
    if (data.dungeon_boss_defeated && Array.isArray(data.dungeon_boss_loot)) {
        pendingBossLoot = data.dungeon_boss_loot;
    }
    // L18 (#732): dungeon-only healing sustain drop — granted server-side, surface a
    // toast so the player knows a heal landed in the plecak after the fight.
    if (data.dungeon_sustain && data.dungeon_sustain.label) {
        showToast(`🧪 W lochu znaleziono: ${data.dungeon_sustain.label} — do plecaka`, 'success', 4000);
    }

    if (cs) { lastCombatState = cs; renderCombatUI(cs); }

    // SF8 (#637) — rozbicie rzutu po nazwanym źródle. Live response niesie wszystkie
    // policzone składniki (attack_roll.* + surprise/durability); karta w feedzie je
    // skonsumuje. Front NIC nie liczy — tylko nazywa. Graceful degrade gdy brak.
    if (atkRoll && atkRoll.attack_stat) {
        window._pendingAttackBreakdown = {
            d20: Number(data.player_raw_d20 ?? atkRoll.raw ?? d20),
            total: Number(data.attack_total ?? atkRoll.total ?? total),
            parts: sf8AttackBreakdown(atkRoll, {
                surprise: data.surprise_atk_bonus,
                durability: data.durability_attack_penalty,
            }),
        };
    }

    await fetchAndAppendNewCombatTurns();

    const payload = {
        kind: 'player_attack',
        character_name: characterData?.name || 'Bohater',
        d20,
        modifiers: mod !== 0 ? [{ name: String(atkRoll.attack_stat || 'STR').toUpperCase(), value: mod }] : [],
        total, hit, damage: dmg,
        target_name: targetName,
        enemy_key: enemyKey || '',
        dodged: !!data.dodged,
        player_nat1: !!data.player_nat1,
        enemy_dead: !!data.enemy_dead,
        combat_victory: !!victoryNow,
    };
    // #650 (B6b): oznacz atak czarem, żeby narracja opisała MAGIĘ, nie cios wyposażoną bronią.
    const _isSpell = (data.weapon_type || atkRoll.weapon_type) === 'spell'
        || (data.attack_test || atkRoll.test) === 'spell_attack';
    if (_isSpell) {
        payload.attack_mode = 'spell';
        payload.spell_label = data.weapon_label || atkRoll.weapon_label || 'zaklęcie';
    }
    const dbLine = `${COMBAT_ROLL_PREFIX}\n${JSON.stringify(payload)}`;
    await sendCombatNarration(dbLine);

    if (endedNow) {
        await handleCombatEnded(cs);
    } else {
        await refreshCharacterData();
        // #848: trigger enemy turn poll when server already advanced turn after player attack
        if (cs && cs.current_turn !== 'player' && cs.status === 'active') await pollCombatState();
    }
}

async function handleCombatMove() {
    window.clog?.event('combat_move_invoked', { campaign_id: currentCampaignId, current_turn: lastCombatState?.current_turn ?? null });
    if (!combatActive || !currentCampaignId || combatBusy || enemyTurnInFlight) {
        window.clog?.warn('combat_move_blocked', { reason: 'busy_or_inactive' });
        return;
    }
    if (lastCombatState?.current_turn !== 'player') {
        setCombatMsg('Nie twoja tura.', true);
        return;
    }
    combatBusy = true; playerActionFetchActive = true;  // #700
    if (elements.btnCombatMove) elements.btnCombatMove.disabled = true;
    elements.btnCombatAttack.disabled = true;
    elements.btnCombatFlee.disabled = true;
    setCombatMsg('Zmiana pozycji…');
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/zone-change`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
        const cs = data.combat_state;
        const moveText = data.to === 'engaged' ? 'Zbliżasz się — wchodzisz w zwarcie.' : 'Cofasz się — przechodzisz na dystans.';
        appendMessage({ role: 'system', content: `🚶 ${moveText}`, created_at: new Date() });
        // SF5 (#634) — pośpiech (S12): ruch nie zużył tury → ulotny komunikat.
        if (data.extra_action_used) flashCombatEvent('extra_action');
        if (cs) { lastCombatState = cs; renderCombatUI(cs); }
        setCombatMsg(data.to === 'engaged' ? 'Jesteś w zwarciu.' : 'Jesteś na dystansie.');
        // Enemy may now act
        if (cs && cs.current_turn !== 'player' && cs.status === 'active') {
            await pollCombatState();
        }
    } catch (e) {
        setCombatMsg(`Błąd ruchu: ${e.message || e}`, true);
        window.clog?.error('combat_move_exception', { message: String(e?.message || e) });
    } finally {
        combatBusy = false; playerActionFetchActive = false;  // #700
        if (lastCombatState) renderCombatUI(lastCombatState);
    }
}

async function handleCombatDodge() {
    // S15 (#610): pre-deklaracja uniku — toggle, NIE zużywa tury. Konsumowana przy pierwszym
    // trafieniu wroga w tej rundzie. Wymaga skilla dodge rank ≥ 1 (inaczej backend → 400).
    if (!combatActive || !currentCampaignId || combatBusy || enemyTurnInFlight) return;
    if (lastCombatState?.current_turn !== 'player') {
        setCombatMsg('Unik deklarujesz w swojej turze.', true);
        return;
    }
    combatBusy = true; playerActionFetchActive = true;  // #700
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/declare-reaction`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reaction_type: 'dodge' })
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
        const cs = data.combat_state;
        if (cs) { lastCombatState = cs; }
        setCombatMsg(data.reaction_declared
            ? 'Unik gotowy — następny cios spróbujesz odbić.'
            : 'Unik anulowany.');
    } catch (e) {
        setCombatMsg(`Unik niedostępny: ${e.message || e}`, true);
    } finally {
        combatBusy = false; playerActionFetchActive = false;  // #700
        if (lastCombatState) renderCombatUI(lastCombatState);
    }
}

async function handleCombatBlock() {
    // S16 (#611): pre-deklaracja bloku tarczą — toggle, NIE zużywa tury. Konsumowana przy
    // pierwszym trafieniu wroga. Wymaga skilla shield_block rank ≥ 1 + założonej tarczy
    // (backend → 400). XOR z unikiem (jedna reakcja/rundę).
    if (!combatActive || !currentCampaignId || combatBusy || enemyTurnInFlight) return;
    if (lastCombatState?.current_turn !== 'player') {
        setCombatMsg('Blok deklarujesz w swojej turze.', true);
        return;
    }
    combatBusy = true; playerActionFetchActive = true;  // #700
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/declare-reaction`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reaction_type: 'shield_block' })
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
        const cs = data.combat_state;
        if (cs) { lastCombatState = cs; }
        setCombatMsg(data.reaction_declared
            ? 'Blok gotowy — następny cios spróbujesz odbić tarczą.'
            : 'Blok anulowany.');
    } catch (e) {
        setCombatMsg(`Blok niedostępny: ${e.message || e}`, true);
    } finally {
        combatBusy = false; playerActionFetchActive = false;  // #700
        if (lastCombatState) renderCombatUI(lastCombatState);
    }
}

async function handleCombatWrestle() {
    // S17 (#612): zapasy — akcja bojowa (test STR vs STR). Wymaga zwarcia (backend → blocked
    // bez konsumpcji tury, gdy cel poza zwarciem). Sukces nakłada kondycję na wroga, krytyk
    // mocniejszą, krytyczna porażka przewraca gracza. Konsumuje turę.
    if (!combatActive || !currentCampaignId || combatBusy || enemyTurnInFlight) return;
    if (lastCombatState?.current_turn !== 'player') {
        setCombatMsg('Zapasy wykonujesz w swojej turze.', true);
        return;
    }
    combatBusy = true; playerActionFetchActive = true;  // #700
    elements.btnCombatAttack.disabled = true;
    if (elements.btnCombatWrestle) elements.btnCombatWrestle.disabled = true;
    setCombatMsg('Próba chwytu…');
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/wrestling`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
        const cs = data.combat_state;
        if (data.blocked) {
            setCombatMsg('Cel poza zwarciem — najpierw się zbliż.', true);
        }
        if (cs) { lastCombatState = cs; renderCombatUI(cs); }
        // S17 (#612) + S17-EXT (#622): chwyt ORAZ ewentualny follow-up (rank ≥ 3 → „Dodatkowy
        // cios") renderują się jako karty z feedu walki — natychmiast i w kolejności. Bez tego
        // follow-up pojawiał się dopiero po turze wroga (out-of-context) → gracz go nie widział.
        // fetchAndAppendNewCombatTurns przesuwa watermark, więc późniejszy poll tury wroga nie dubluje.
        if (!data.blocked) await fetchAndAppendNewCombatTurns();
        if (cs && cs.current_turn !== 'player' && cs.status === 'active') {
            await pollCombatState();
        }
    } catch (e) {
        setCombatMsg(`Zapasy niedostępne: ${e.message || e}`, true);
    } finally {
        combatBusy = false; playerActionFetchActive = false;  // #700
        if (lastCombatState) renderCombatUI(lastCombatState);
    }
}

async function handleCombatFlee() {
    window.clog?.event('combat_flee_invoked', { campaign_id: currentCampaignId, current_turn: lastCombatState?.current_turn ?? null });
    if (!combatActive || !currentCampaignId || combatBusy || enemyTurnInFlight) {
        window.clog?.warn('combat_flee_blocked', { reason: 'busy_or_inactive' });
        return;
    }
    if (!confirm('Uciec z walki?')) { window.clog?.event('combat_flee_cancelled'); return; }

    combatBusy = true; playerActionFetchActive = true;  // #700
    elements.btnCombatAttack.disabled = true;
    elements.btnCombatFlee.disabled = true;
    setCombatMsg('Próba ucieczki...');

    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/flee`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await r.json().catch(() => ({}));
        window.clog?.event('combat_flee_response', { status: r.status, fled: !!data.fled });
        if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);

        const cs = data.combat_state;
        if (cs) { lastCombatState = cs; }

        const enemyName = (() => {
            const combatants = Array.isArray(lastCombatState?.combatants) ? lastCombatState.combatants : [];
            const living = combatants.filter(c => c && c.type === 'enemy' && Number(c.hp_current ?? 0) > 0);
            if (living.length === 1) return String(living[0].name || living[0].enemy_key || 'przeciwnik');
            return 'przeciwnik';
        })();

        const summary = `Uciekam z walki z ${enemyName}! Proszę domknij scenę — gdzie jestem teraz?`;
        appendMessage({ role: 'system', content: `🏃 Ucieczka z walki!`, created_at: new Date() });
        scrollToBottom();

        const payload = { kind: 'player_flee', summary_line: summary, character_name: characterData?.name || 'Bohater', enemy_name: enemyName, success: true };
        const dbLine = `${COMBAT_ROLL_PREFIX}\n${JSON.stringify(payload)}`;
        await sendCombatNarration(dbLine);

        await handleCombatEnded(cs || { status: 'ended', ended_reason: 'fled' });
    } catch (e) {
        window.clog?.error('combat_flee_exception', { message: String(e?.message || e) });
        setCombatMsg(`Błąd ucieczki: ${e.message || e}`, true);
        if (lastCombatState) renderCombatUI(lastCombatState);
    } finally {
        // #1149: SUKCES ucieczki nie miał resetu flag (był tylko w catch) — combatBusy/
        // playerActionFetchActive zostawały true po wyjściu z walki. Następny encounter w
        // podróży widział zalegające flagi → reconciler utykał na 'fetch_in_flight' (brak
        // watchdoga dla playerActionFetchActive) i combatBusy blokował auto-turę wroga →
        // przyciski martwe do F5. Reset w finally domyka OBIE ścieżki (sukces i błąd).
        combatBusy = false; playerActionFetchActive = false;  // #700 / #1149
    }
}

async function sendCombatNarration(dbLine) {
    if (!currentCampaignId || !characterData?.id) return;
    const typingIndicator = showTypingIndicator();
    try {
        // #566: combat-roll narration MUST go through the streaming endpoint. It renders
        // the [GM_ROLL] dice card and skips the "Walka trwa!" block — the non-streaming
        // /turns path mis-blocks this payload the moment the attack passes the turn to the
        // enemy (it lacks the streaming path's current_turn=='player' guard). Using the
        // shared stream reader also keeps GM colour + combat-ended handling consistent.
        await _sendTurnStream(dbLine, 'combat_roll', typingIndicator);
    } catch (e) {
        typingIndicator.remove();
        console.error('[Combat] narration error:', e);
    }
}

