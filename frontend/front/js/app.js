/**
 * AI GM RPG - Mobile-First Frontend Application
 * Task T28.5 - Alternative frontend based on Figma designs v18-20
 */

const API_BASE = '/api';

const SLASH_COMMANDS = [
    { cmd: '/help',    desc: 'Pokaż listę dostępnych komend' },
    { cmd: '/sheet',   desc: 'Otwórz kartę postaci' },
    { cmd: '/mem',     desc: 'Pytanie o przeszłość z podsumowań (bez wpływu na narrację)' },
    { cmd: '/helpme',  desc: 'Doradca OOC — wskazówki poza fabułą' },
    { cmd: '/admin',   desc: 'Komendy admina: add | set | remove | clear | combat | quest | show', adminOnly: true },
    { cmd: '/history', desc: 'Ostatnie 10 tur sesji' },
    { cmd: '/search',  desc: 'Przeszukaj lokację lub postać' },
    { cmd: '/atak',    desc: 'Synchronizuj panel walki lub zacznij walkę' },
];

// ============================================================================
// DOM Elements
// ============================================================================
const screens = {
    login: document.getElementById('login-screen'),
    heroes: document.getElementById('heroes-screen'),
    campaigns: document.getElementById('campaigns-screen'),
    newCampaign: document.getElementById('new-campaign-screen'),
    characterWizard: document.getElementById('character-wizard-screen'),
    game: document.getElementById('game-screen')
};

const elements = {
    // Login
    loginForm: document.getElementById('login-form'),
    usernameInput: document.getElementById('login-username'),
    passwordInput: document.getElementById('login-password'),
    loginError: null,

    // Heroes
    heroesList: document.getElementById('heroes-list'),
    heroesEmpty: document.getElementById('heroes-empty'),
    heroesWelcome: document.getElementById('heroes-welcome'),
    btnNewHero: document.getElementById('new-hero-btn'),
    btnHeroesLogout: document.getElementById('heroes-logout-btn'),

    // Campaigns
    campaignsList: document.getElementById('campaigns-list'),
    campaignsEmpty: document.getElementById('campaigns-empty'),
    btnNewCampaign: document.getElementById('new-campaign-btn'),
    btnLogout: document.getElementById('logout-btn'),
    welcomeUser: document.getElementById('welcome-user'),

    // New Campaign
    newCampaignForm: document.getElementById('new-campaign-form'),
    campaignNameInput: document.getElementById('campaign-name'),
    campaignNameCount: document.getElementById('campaign-name-count'),
    btnNewCampaignBack: document.getElementById('new-campaign-back'),

    // Character Wizard
    wizardContent: document.getElementById('wizard-content'),
    wizardTitle: document.getElementById('wizard-title'),
    wizardStep: document.getElementById('wizard-step'),
    btnWizardPrev: document.getElementById('wizard-prev'),
    btnWizardNext: document.getElementById('wizard-next'),
    btnWizardBack: document.getElementById('wizard-back'),

    // Game
    characterNameDisplay: document.getElementById('character-name-display'),
    characterStatsDisplay: document.getElementById('character-stats-display'),
    headerClock: document.getElementById('header-clock'),
    chatMessages: document.getElementById('chat-messages'),
    chatInput: document.getElementById('chat-input'),
    btnOpenSheet: document.getElementById('open-sheet-btn'),
    btnOpenSettings: document.getElementById('open-settings-btn'),
    btnSend: document.getElementById('send-btn'),

    // Character Sheet Panel
    sheetPanel: document.getElementById('sheet-panel'),
    sheetCharacterName: document.getElementById('sheet-character-name'),
    sheetTabs: document.querySelectorAll('.sheet-tab'),
    sheetHp: document.getElementById('sheet-hp'),
    sheetHpBar: document.getElementById('sheet-hp-bar'),
    sheetLevel: document.getElementById('sheet-level'),
    sheetStats: document.getElementById('sheet-stats'),
    sheetSkills: document.getElementById('sheet-skills'),
    sheetGold: document.getElementById('sheet-gold'),
    sheetInventory: document.getElementById('sheet-inventory'),

    // Settings Panel
    settingsPanel: document.getElementById('settings-panel'),
    btnGoToCampaigns: document.getElementById('go-to-campaigns-btn'),

    // Combat
    composer: document.getElementById('composer'),
    combatBanner: document.getElementById('combat-banner'),
    combatRound: document.getElementById('combat-round'),
    combatTurnLabel: document.getElementById('combat-turn-label'),
    combatEnemies: document.getElementById('combat-enemies'),
    initiativeTrack: document.getElementById('initiative-track'),
    combatZoneRanged: document.getElementById('combat-zone-ranged'),
    combatZoneEngaged: document.getElementById('combat-zone-engaged'),
    btnCombatMove: document.getElementById('combat-move-btn'),
    combatMoveLabel: document.getElementById('combat-move-label'),
    combatMsg: document.getElementById('combat-msg'),
    combatComposer: document.getElementById('combat-composer'),
    btnCombatAttack: document.getElementById('combat-attack-btn'),
    btnCombatFlee: document.getElementById('combat-flee-btn'),

    // Journal Panel
    journalPanel: document.getElementById('journal-panel'),
    btnOpenJournal: document.getElementById('open-journal-btn'),
    journalBody: document.getElementById('journal-body'),
    journalEmpty: document.getElementById('journal-empty'),
    journalLoading: document.getElementById('journal-loading'),
    journalBanner: document.getElementById('journal-banner'),
    btnJournalRegen: document.getElementById('journal-regen-btn'),

    // Overlay
    overlay: document.getElementById('panel-overlay'),

    // Combat End Overlays
    combatEndOverlay: document.getElementById('combat-end-overlay'),
    critFlash: document.getElementById('crit-flash'),
    critFlashTitle: document.getElementById('crit-flash-title'),
    critFlashSub: document.getElementById('crit-flash-sub'),
    combatEndTitle: document.getElementById('combat-end-title'),
    combatEndIcon: document.getElementById('combat-end-icon'),
    combatEndLoot: document.getElementById('combat-end-loot'),
    combatEndBtn: document.getElementById('combat-end-btn'),
    combatLootOverlay: document.getElementById('combat-loot-overlay'),
    combatLootList: document.getElementById('combat-loot-list'),
    combatLootClaimBtn: document.getElementById('combat-loot-claim-btn'),
    combatLootSkipBtn: document.getElementById('combat-loot-skip-btn'),

    // Header HP bar
    headerHpBarFill: document.getElementById('header-hp-bar-fill'),

    // Admin Settings
    adminSettingsSection: document.getElementById('admin-settings-section'),
    btnResetCampaign: document.getElementById('reset-campaign-btn'),
    btnResetCharacter: document.getElementById('reset-character-btn'),

    // Service status dots
    svcDotBackend: document.getElementById('svc-dot-backend'),
    svcDotLlm: document.getElementById('svc-dot-llm'),
    svcDotLoki: document.getElementById('svc-dot-loki')
};

// ============================================================================
// Local State
// ============================================================================
const bubblePrefs = {
    showName: localStorage.getItem('bubble_name') !== 'false',
    showTurn: localStorage.getItem('bubble_turn') !== 'false',
    showDateTime: localStorage.getItem('bubble_datetime') !== 'false',
};

function applyBubblePrefs() {
    document.body.classList.toggle('hide-bubble-name', !bubblePrefs.showName);
    document.body.classList.toggle('hide-bubble-turn', !bubblePrefs.showTurn);
    document.body.classList.toggle('hide-bubble-datetime', !bubblePrefs.showDateTime);
}

let currentScreen = 'login';
let currentCampaignId = null;
let currentCampaign = null;

// T33: Suggested actions state
let _suggestedActions = [];
let wizardStepNum = 0;
let isSheetOpen = false;
let isSettingsOpen = false;
let isJournalOpen = false;
let characterData = null;
let authToken = null;
let currentUser = null;
let debugMode = localStorage.getItem('aigm_debug') === '1';

// --- Wizard state (real 4-step flow) ---
let wizardCreatedChar = null;   // character returned from POST /campaigns/{id}/characters
let wizardStatBases = {};       // base stat values (pre-archetype-bonus), player edits these
let wizardStatOriginal = {};    // original rolled bases (for reset)
let wizardStatUnassigned = 0;   // pool of unspent points (move stat down → fills pool)
let wizardSkillSnapshot = {};   // original rolled skills {key: rank}
let wizardSkillLevels = {};     // current level per original slot key
let wizardSkillSwapMap = {};    // {origKey: newKey} for swapped slots
let wizardSwapModeSlot = null;  // origKey currently showing inline swap select
let wizardIdentityPreview = null;
const WIZARD_MAX_SWAPS = 4;
const WIZARD_STAT_MIN = 8;
const WIZARD_STAT_MAX = 18;
const ARCHETYPE_BONUS = { warrior: { STR: 2, CON: 1 }, scholar: { INT: 2, WIS: 1 }, rogue: { DEX: 2, LCK: 1 } };
const ALL_SKILL_ROWS = [
    { key: 'athletics',       label: 'Atletyka',          stat: 'STR', hint: 'Wspinaczka, sprint, skoki, siłowe wyczyny. Wymagana przy pogoni i ucieczkach.' },
    { key: 'endurance',       label: 'Wytrzymałość',      stat: 'CON', hint: 'Odporność na ból, zmęczenie, trucizny i choroby. Decyduje o przetrwaniu ekstremalnych warunków.' },
    { key: 'stealth',         label: 'Skradanie',         stat: 'DEX', hint: 'Poruszanie się bez hałasu, ukrywanie się, zasadzki. Kluczowe dla złodziei i łowców.' },
    { key: 'sleight_of_hand', label: 'Zręczne Dłonie',   stat: 'DEX', hint: 'Kieszonkowanie, sztuczki karcianie, ukrywanie przedmiotów. Finezja drobnych manipulacji.' },
    { key: 'arcana',          label: 'Magia Arkanów',    stat: 'INT', hint: 'Wiedza o zaklęciach, artefaktach i rytuałach. Identyfikacja magicznych przedmiotów.' },
    { key: 'investigation',   label: 'Badanie',           stat: 'INT', hint: 'Szukanie wskazówek, analiza śladów, rozwiązywanie zagadek i tajemnic.' },
    { key: 'lore',            label: 'Wiedza',            stat: 'INT', hint: 'Historia, legendy, fakty o świecie. Znajomość krain, frakcji i dawnych wydarzeń.' },
    { key: 'awareness',       label: 'Spostrzegawczość',  stat: 'WIS', hint: 'Zauważanie ukrytych wrogów, pułapek i szczegółów. Trudno zaskoczyć kogoś z dobrą percepcją.' },
    { key: 'survival',        label: 'Przetrwanie',       stat: 'WIS', hint: 'Tropienie, orientacja w terenie, rozbijanie obozu, zdobywanie pożywienia w dziczy.' },
    { key: 'medicine',        label: 'Medycyna',          stat: 'WIS', hint: 'Opatrywanie ran, zatrzymywanie krwawienia, diagnozowanie chorób i zatruć.' },
    { key: 'persuasion',      label: 'Perswazja',         stat: 'CHA', hint: 'Przekonywanie, negocjacje i dyplomacja. Zmiana zdania rozmówcy bez użycia siły.' },
    { key: 'intimidation',    label: 'Zastraszanie',      stat: 'CHA', hint: 'Wywoływanie strachu, wymuszanie posłuszeństwa. Może skłonić wroga do ucieczki.' },
    { key: 'melee_attack',    label: 'Atak Wręcz',       stat: 'STR', hint: 'Precyzja i technika w walce mieczem, toporem lub pięściami. Trafienie i siła ciosu.' },
    { key: 'ranged_attack',   label: 'Atak Dystansowy',  stat: 'DEX', hint: 'Celność z łukiem, kuszą i bronią miotaną. Ataki z ukrycia i na dalekie dystanse.' },
    { key: 'spell_attack',    label: 'Atak Magiczny',    stat: 'INT', hint: 'Precyzja rzucania ofensywnych zaklęć. Trafienie celem i kontrola energii arkanów.' },
    { key: 'alchemy',         label: 'Alchemia',          stat: 'INT', hint: 'Tworzenie mikstur, trucizn i eliksirów. Identyfikacja substancji i składników.' },
].sort((a, b) => a.key.localeCompare(b.key));
const RANK_LABEL = ['—', 'Trained', 'Skilled'];
const WIZARD_STEPS = [
    { title: 'Twój bohater', subtitle: 'Krok 1 z 4' },
    { title: 'Statystyki', subtitle: 'Krok 2 z 4' },
    { title: 'Umiejętności', subtitle: 'Krok 3 z 4' },
    { title: 'Tożsamość', subtitle: 'Krok 4 z 4' },
];
function _skillRow(key) { return ALL_SKILL_ROWS.find(r => r.key === key) || { key, label: key, stat: '?' }; }
function _skillBudgetUsed() {
    return ALL_SKILL_ROWS.reduce((s, { key }) => {
        const o = Number(wizardSkillSnapshot[key] || 0);
        if (!o) return s;
        return s + Math.abs((wizardSkillLevels[key] ?? o) - o);
    }, 0);
}
function _canAdjSkill(origKey, delta) {
    const o = Number(wizardSkillSnapshot[origKey] || 0);
    if (!o) return false;
    const cur = wizardSkillLevels[origKey] ?? o;
    const next = cur + delta;
    if (next < 0 || next > 2) return false;
    const test = { ...wizardSkillLevels, [origKey]: next };
    const budget = ALL_SKILL_ROWS.reduce((s, { key }) => {
        const oo = Number(wizardSkillSnapshot[key] || 0);
        if (!oo) return s;
        return s + Math.abs((test[key] ?? oo) - oo);
    }, 0);
    return budget <= WIZARD_MAX_SWAPS;
}

// ============================================================================
// API Helper
// ============================================================================
async function apiRequest(method, endpoint, body = null) {
    const headers = {
        'Content-Type': 'application/json'
    };

    const options = { method, headers };
    if (body) {
        options.body = JSON.stringify(body);
    }

    console.log(`[API] ${method} ${API_BASE}${endpoint}`, body || '');

    const response = await fetch(`${API_BASE}${endpoint}`, options);

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error(`[API] Error ${response.status}:`, errorData);
        throw new Error(errorData.detail || errorData.message || `API Error: ${response.status}`);
    }

    if (response.status === 204 || response.headers.get('content-length') === '0') {
        return null;
    }
    const data = await response.json().catch(() => null);
    console.log(`[API] Response:`, data);
    return data;
}

// ============================================================================
// Screen Navigation
// ============================================================================
function showScreen(screenName) {
    console.log('[Screen] Switching to:', screenName);
    Object.values(screens).forEach(screen => {
        if (screen) screen.classList.remove('screen--active');
    });

    if (screens[screenName]) {
        screens[screenName].classList.add('screen--active');
        currentScreen = screenName;
        window.clog?.setContext({ screen: screenName });
        window.clog?.event('screen_change', { screen: screenName });
        if (screenName !== 'game' && typeof stopCombatPolling === 'function') {
            stopCombatPolling();
            if (typeof hideCombatUI === 'function') hideCombatUI();
        }
        // Hide dungeon HUD on any screen except game
        if (screenName !== 'game') {
            document.getElementById('dungeon-hud')?.setAttribute('hidden', '');
            document.getElementById('dungeon-riddle-panel')?.setAttribute('hidden', '');
            document.getElementById('dungeon-map-overlay')?.setAttribute('hidden', '');
        } else if (_activeDungeonRun && !_activeDungeonRun.completed && !_activeDungeonRun.failed) {
            // Restore HUD when back on game screen with active run
            showDungeonHUD(true);
        }
    } else {
        window.clog?.error('screen_not_found', { name: screenName });
    }
}

// ============================================================================
// Toast Notifications
// ============================================================================
function showToast(message, type = 'info') {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }

    toast.textContent = message;
    toast.className = `toast toast--${type} toast--visible`;

    setTimeout(() => {
        toast.classList.remove('toast--visible');
    }, 3000);
}

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
                is_admin: response.is_admin
            };
            authToken = `user:${currentUser.id}`;
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
            showScreen('heroes');
        } else {
            console.error('[Login] Invalid response:', response);
            showToast('Nieprawidłowa odpowiedź serwera', 'error');
        }
    } catch (error) {
        console.error('[Login] Error:', error);
        showToast(error.message || 'Błąd logowania', 'error');
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
    localStorage.removeItem('aigm_hero_id');
    localStorage.removeItem('aigm_campaign_id');
    try { sessionStorage.removeItem('aigm_hero_id'); sessionStorage.removeItem('aigm_active_session'); } catch {}
    showScreen('login');
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

// ============================================================================
// Heroes (character-first flow — Task 42)
// ============================================================================
let currentHero = null;

async function loadHeroes() {
    if (!currentUser?.id) return;
    const response = await apiRequest('GET', `/characters?user_id=${currentUser.id}`);
    const heroes = response.heroes || [];
    renderHeroes(heroes);
}

function renderHeroes(heroes) {
    const list = elements.heroesList;
    const empty = elements.heroesEmpty;
    if (!list) return;
    list.innerHTML = '';

    if (heroes.length === 0) {
        if (empty) empty.style.display = '';
        return;
    }
    if (empty) empty.style.display = 'none';

    heroes.forEach(hero => {
        const sheet = hero.sheet_json || {};
        const archetype = sheet.archetype || hero.system_id || '?';
        const level = sheet.level || 1;
        const hp = sheet.current_hp ?? sheet.max_hp ?? '?';
        const maxHp = sheet.max_hp ?? '?';
        const status = hero.status || 'idle';
        const statusLabel = { idle: 'Wolny', in_campaign: 'W kampanii', in_dungeon: 'W lochu' }[status] || status;
        const campaignTitle = hero.campaign_title || '';
        const canDelete = true;  // always show — backend enforces safety

        const wrapper = document.createElement('div');
        wrapper.style.cssText = 'position:relative;display:flex;align-items:stretch;margin-bottom:8px';

        const card = document.createElement('div');
        card.className = 'campaign-card';
        card.style.flex = '1';
        card.innerHTML = `
            <div class="campaign-card__icon"><span>⚔</span></div>
            <div class="campaign-card__content">
                <h3>${_esc(hero.name)}</h3>
                <p>${_esc(archetype)} · Poziom ${level} · HP ${hp}/${maxHp}</p>
                ${campaignTitle ? `<p style="font-size:0.8em;opacity:0.6">${_esc(campaignTitle)}</p>` : ''}
            </div>
            <span class="campaign-card__arrow" style="font-size:0.75em;opacity:0.7">${_esc(statusLabel)}</span>
        `;
        card.addEventListener('click', () => selectHero(hero));

        // Delete button
        if (canDelete) {
            const delBtn = document.createElement('button');
            delBtn.style.cssText = 'background:#3a1212;border:none;color:#c94a4a;padding:0 14px;cursor:pointer;border-radius:0 var(--radius-md) var(--radius-md) 0;font-size:1.1rem;';
            delBtn.title = 'Usuń bohatera';
            delBtn.textContent = '🗑';
            delBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const confirmed = await showDeleteHeroModal(hero.name);
                if (!confirmed) return;
                try {
                    await apiRequest('DELETE', `/characters/${hero.id}?user_id=${currentUser.id}`);
                    showToast('Bohater i powiązane kampanie usunięte', 'success');
                    await loadHeroes();
                } catch (err) {
                    showToast(err.message || 'Błąd usuwania', 'error');
                }
            });
            wrapper.appendChild(card);
            wrapper.appendChild(delBtn);
        } else {
            wrapper.appendChild(card);
        }

        list.appendChild(wrapper);
    });
}

async function selectHero(hero) {
    currentHero = hero;
    // Always show campaigns chooser — let player decide (dungeon, new campaign, etc.)
    if (elements.welcomeUser) {
        elements.welcomeUser.textContent = `Bohater: ${hero.name}`;
    }
    // Save hero to session so F5 restores context
    try { localStorage.setItem('aigm_hero_id', hero.id); localStorage.removeItem('aigm_campaign_id'); } catch {}
    await loadCampaigns();
    showScreen('campaigns');
}

// ============================================================================
// Campaigns
// ============================================================================
async function loadCampaigns() {
    console.log('[Campaigns] Loading for user:', currentUser?.id);
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
                // Also hide if campaign has NO active character (hero was deleted)
                if (campCharId === null || campCharId === undefined) return false; // no active char
                if (Number(campCharId) !== Number(currentHero.id)) return false;
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

        const title = campaign.title || campaign.name || 'Kampania';
        const desc = campaign.description || campaign.system_id || 'Fantasy';

        wrapper.innerHTML = `
            <div class="campaign-delete-action" data-campaign-id="${campaign.id}">🗑️</div>
            <button type="button" class="campaign-card" data-campaign-id="${campaign.id}">
                <div class="campaign-card__icon">
                    <span>📜</span>
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
            handleDeleteCampaignFromList(campaign, true);
        });

        deleteAction.addEventListener('touchend', (e) => {
            e.preventDefault();
            e.stopPropagation();
            handleDeleteCampaignFromList(campaign, true);
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

async function handleDeleteCampaignFromList(campaign, skipConfirm = false) {
    if (!skipConfirm) {
        const campaignTitle = campaign.title || campaign.name || 'ta kampania';
        const confirmed = confirm(`USUNĄĆ kampanię "${campaignTitle}"? Ta operacja jest nieodwracalna.`);
        if (!confirmed) return;
    }

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

        // Filter to find current user's character
        const myCharacter = characters.find(c =>
            c.user_id === currentUser?.id || c.userid === currentUser?.id
        );

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
            startCharacterWizard();
        } else {
            startCharacterWizard();
        }
    } catch (error) {
        console.error('Error loading characters:', error);
        startCharacterWizard();
    }
}

function showNewCampaignScreen() {
    // If we already have a hero, skip the title screen entirely
    if (currentHero && currentHero.id) {
        handleNewCampaignWithHero();
        return;
    }
    elements.campaignNameInput.value = '';
    elements.campaignNameCount.textContent = '0';
    showScreen('newCampaign');
}

async function handleNewCampaignWithHero() {
    if (!currentHero || !currentUser?.id) return;
    const loadingToast = showToast('Tworzę kampanię…', 'info', 0);
    try {
        // Auto-generate a working title — GM plan will rename it properly
        const heroName = currentHero.name || 'Bohater';
        const title = `Przygoda ${heroName}`;
        const campaign = await apiRequest('POST', '/campaigns', {
            title,
            system_id: 'fantasy',
            model_id: 'default',
            owner_user_id: currentUser.id,
            language: 'pl',
            mode: 'solo',
            status: 'active',
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
        startCharacterWizard();
    } catch (error) {
        console.error('Create campaign error:', error);
        showToast(error.message || 'Nie udało się utworzyć kampanii', 'error');
    } finally {
        submitBtn.disabled = false;
    }
}

// ============================================================================
// Character Wizard — real 4-step flow
// ============================================================================
function startCharacterWizard() {
    wizardStepNum = 0;
    wizardCreatedChar = null;
    wizardStatBases = {};
    wizardStatOriginal = {};
    wizardStatUnassigned = 0;
    wizardSkillSnapshot = {};
    wizardSkillLevels = {};
    wizardSkillSwapMap = {};
    wizardSwapModeSlot = null;
    wizardIdentityPreview = null;
    _wizardRender();
    showScreen('characterWizard');
}

function _wizardRender() {
    const step = WIZARD_STEPS[wizardStepNum];
    elements.wizardTitle.textContent = step.title;
    elements.wizardStep.textContent = step.subtitle;
    elements.btnWizardPrev.style.display = wizardStepNum === 0 ? 'none' : 'block';
    elements.btnWizardNext.innerHTML = wizardStepNum === WIZARD_STEPS.length - 1
        ? 'Rozpocznij przygodę <span class="btn__icon">✨</span>'
        : 'Dalej <span class="btn__icon">›</span>';
    elements.btnWizardNext.disabled = false;

    const content = elements.wizardContent;
    if (wizardStepNum === 0) _renderStep1(content);
    else if (wizardStepNum === 1) _renderStep2(content);
    else if (wizardStepNum === 2) _renderStep3(content);
    else _renderStep4(content);
}

// Step 1 — Name, background, archetype
function _renderStep1(c) {
    const sheet = wizardCreatedChar?.sheet_json || {};
    const savedName = wizardCreatedChar?.name || '';
    const savedBg = sheet.backstory || '';
    const savedArch = sheet.archetype || 'warrior';
    c.innerHTML = `
        <div class="wizard-hero">
            <span class="wizard-hero__icon">👤</span>
            <h2>Stwórz postać</h2>
            <p>Nie masz jeszcze bohatera w tej kampanii. Przygotuj kartę i zacznij przygodę.</p>
        </div>
        <div class="wizard-form">
            <div class="form-field">
                <label for="char-name">Imię postaci</label>
                <input type="text" id="char-name" placeholder="np. Aldric z Północy" maxlength="40" value="${_esc(savedName)}">
            </div>
            <div class="form-field">
                <label for="char-bg">Historia / tło postaci</label>
                <textarea id="char-bg" rows="4" placeholder="Kim był twój bohater przed początkiem kampanii?">${_esc(savedBg)}</textarea>
            </div>
            <div class="form-field">
                <label>Archetyp</label>
                <div class="archetype-grid">
                    <button type="button" class="archetype-card${savedArch === 'warrior' ? ' archetype-card--selected' : ''}" data-arch="warrior">
                        <span class="archetype-icon">⚔️</span>
                        <span class="archetype-title">Wojownik</span>
                        <span class="archetype-desc">Frontowy wojownik w ciężkiej zbroi. Wysoki HP, silne ciosy, mistrz broni wręcz.</span>
                        <span class="archetype-bonus">+2 STR · +1 KON · HP: 12</span>
                    </button>
                    <button type="button" class="archetype-card${savedArch === 'rogue' ? ' archetype-card--selected' : ''}" data-arch="rogue">
                        <span class="archetype-icon">🏹</span>
                        <span class="archetype-title">Łotrzyk</span>
                        <span class="archetype-desc">Zwinny cień: snajper z ukrycia lub złodziej w ciemnościach. Skradanie, łuk, inteligentna walka.</span>
                        <span class="archetype-bonus">+2 ZRĘ · +1 SZCZ · HP: 8</span>
                    </button>
                    <button type="button" class="archetype-card${savedArch === 'scholar' ? ' archetype-card--selected' : ''}" data-arch="scholar">
                        <span class="archetype-icon">📜</span>
                        <span class="archetype-title">Uczony</span>
                        <span class="archetype-desc">Tkacz arkanów: kruchy, ale niszczycielski dzięki zaklęciom. Zarządza maną i ryzykiem Omylenia.</span>
                        <span class="archetype-bonus">+2 INT · +1 MĄD · HP: 6 · Mana</span>
                    </button>
                </div>
            </div>
        </div>
    `;
    c.querySelectorAll('.archetype-card').forEach(btn => {
        btn.addEventListener('click', () => {
            c.querySelectorAll('.archetype-card').forEach(b => b.classList.remove('archetype-card--selected'));
            btn.classList.add('archetype-card--selected');
        });
    });
}

// Step 2 — Stat redistribution (pool model matching original frontend)
function _wizardCalcHP(archetype, con, level = 1) {
    const base = archetype === 'warrior' ? 12 : archetype === 'rogue' ? 8 : archetype === 'scholar' ? 6 : 8;
    const mod = Math.floor((con - 10) / 2);
    return Math.max(1, base + mod * level);
}

function _wizardCalcMana(archetype, int_, level = 1) {
    if (archetype !== 'scholar') return 0;
    const mod = Math.floor((int_ - 10) / 2);
    return Math.max(1, 8 + mod * level);
}

const STAT_HINTS = {
    STR: 'Siła — obrażenia wręcz, atletyka, dźwiganie, forsowanie drzwi',
    DEX: 'Zręczność — inicjatywa, skradanie, uniki, ataki finezyjne i dystansowe',
    CON: 'Kondycja — punkty życia, odporność na trucizny i ból, wytrzymałość',
    INT: 'Inteligencja — magia arkanów, wiedza, badanie, alchemia',
    WIS: 'Mądrość — percepcja, przetrwanie, medycyna, odporność na strach',
    CHA: 'Charyzma — perswazja, zastraszanie, negocjacje, przywódcze zdolności',
    LCK: 'Szczęście — wpływa na rzuty losowe, jakość łupów, szanse ucieczki i zdarzenia losowe',
};

function _renderStep2(c) {
    const archetype = wizardCreatedChar?.sheet_json?.archetype || 'warrior';
    const bonus = ARCHETYPE_BONUS[archetype] || {};
    const bonusStr = Object.entries(bonus).map(([k, v]) => `+${v} ${k}`).join(', ');

    let rows = '';
    for (const stat of ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA', 'LCK']) {
        const v = wizardStatBases[stat] ?? (stat === 'LCK' ? 8 : 10);
        const mod = Math.floor((v - 10) / 2);
        const modStr = mod >= 0 ? `+${mod}` : `${mod}`;
        const canMinus = v > WIZARD_STAT_MIN;
        const canPlus = v < WIZARD_STAT_MAX && wizardStatUnassigned > 0;
        const hint = STAT_HINTS[stat] || stat;
        rows += `
            <div class="wizard-stat-row" data-stat="${stat}">
                <div class="wizard-stat-label-wrap">
                    <span class="wizard-stat-label">${stat}</span>
                    <span class="wizard-stat-hint" data-tooltip="${hint}">?</span>
                </div>
                <span class="wizard-stat-mod">${modStr}</span>
                <div class="wizard-stat-controls">
                    <button type="button" class="wizard-stat-btn" data-dir="-" ${canMinus ? '' : 'disabled'}>−</button>
                    <span class="wizard-stat-val">${v}</span>
                    <button type="button" class="wizard-stat-btn" data-dir="+" ${canPlus ? '' : 'disabled'}>+</button>
                </div>
            </div>`;
    }

    const previewCon = wizardStatBases['CON'] ?? 10;
    const previewInt = wizardStatBases['INT'] ?? 10;
    const previewHp   = _wizardCalcHP(archetype, previewCon);
    const previewMana = _wizardCalcMana(archetype, previewInt);
    const manaLine = archetype === 'scholar'
        ? `<span class="wizard-preview-item">✨ Mana: <strong>${previewMana}</strong></span>`
        : `<span class="wizard-preview-item wizard-preview-muted">✨ Mana: —</span>`;

    c.innerHTML = `
        <div class="wizard-form">
            <p class="wizard-hint">Przesuń punkty między statystykami. Zmniejsz stat (−) aby dodać do puli, wydaj pulę (+) na inne. Bonusy klasy dodawane automatycznie.</p>
            <div class="wizard-points">Niezapisane punkty: <strong>${wizardStatUnassigned}</strong></div>
            <p class="wizard-class-note">${bonusStr} dodawane automatycznie po potwierdzeniu</p>
            <div class="wizard-stat-grid">${rows}</div>
            <div class="wizard-vitality-preview">
                <span class="wizard-preview-item">❤️ HP: <strong>${previewHp}</strong></span>
                ${manaLine}
            </div>
            <button type="button" class="btn btn--secondary wizard-reset-btn" id="wiz-stat-reset">Reset</button>
        </div>
    `;

    c.querySelectorAll('.wizard-stat-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const stat = btn.closest('.wizard-stat-row').dataset.stat;
            if (btn.dataset.dir === '-') {
                if (wizardStatBases[stat] <= WIZARD_STAT_MIN) return;
                wizardStatBases[stat]--;
                wizardStatUnassigned++;
            } else {
                if (wizardStatBases[stat] >= WIZARD_STAT_MAX || wizardStatUnassigned <= 0) return;
                wizardStatBases[stat]++;
                wizardStatUnassigned--;
            }
            _renderStep2(c);
        });
    });

    document.getElementById('wiz-stat-reset')?.addEventListener('click', () => {
        wizardStatBases = { ...wizardStatOriginal };
        wizardStatUnassigned = 0;
        _renderStep2(c);
    });
}

// Step 3 — Skill swaps + level adjustments (matching original frontend mechanic)
function _renderStep3(c) {
    const budgetUsed = _skillBudgetUsed();
    const slotRows = ALL_SKILL_ROWS.filter(r => Number(wizardSkillSnapshot[r.key] || 0) > 0)
        .sort((a, b) => {
            const db = Number(wizardSkillSnapshot[b.key] || 0) - Number(wizardSkillSnapshot[a.key] || 0);
            return db !== 0 ? db : a.key.localeCompare(b.key);
        });

    // Currently visible keys (original or swapped-in)
    const visibleKeys = new Set(slotRows.map(r => wizardSkillSwapMap[r.key] || r.key));

    // Candidates: unrolled skills not currently visible
    const candidates = ALL_SKILL_ROWS
        .filter(r => !Number(wizardSkillSnapshot[r.key] || 0) && !visibleKeys.has(r.key))
        .sort((a, b) => a.label.localeCompare(b.label));

    let rows = slotRows.map(({ key: origKey }) => {
        const isSwapped = origKey in wizardSkillSwapMap;
        const currentKey = isSwapped ? wizardSkillSwapMap[origKey] : origKey;
        const curRow = _skillRow(currentKey);
        const inSwapMode = wizardSwapModeSlot === origKey;

        if (inSwapMode) {
            const opts = candidates.map(cd =>
                `<option value="${cd.key}" title="${_esc(cd.hint||'')}">${_esc(cd.label)} — ${cd.stat}</option>`
            ).join('');
            return `
                <div class="wizard-skill-row wizard-skill-row--swapping" data-orig="${origKey}">
                    <div class="wizard-skill-swap-row">
                        <select class="wizard-skill-swap-sel" data-orig="${origKey}">
                            <option value="">— Wybierz umiejętność —</option>${opts}
                        </select>
                        <button type="button" class="wizard-stat-btn" data-cancel-swap="${origKey}" title="Anuluj">✕</button>
                    </div>
                </div>`;
        }

        const rank = wizardSkillLevels[origKey] ?? Number(wizardSkillSnapshot[origKey] || 0);
        const rankName = RANK_LABEL[rank] || rank;
        const canPlus = _canAdjSkill(origKey, 1);
        const canMinus = _canAdjSkill(origKey, -1);
        const changed = isSwapped || rank !== Number(wizardSkillSnapshot[origKey] || 0);
        const swapBtn = isSwapped
            ? `<button type="button" class="wizard-skill-swap-btn wizard-skill-swap-btn--revert" data-revert="${origKey}" title="Cofnij zamianę">↩</button>`
            : `<button type="button" class="wizard-skill-swap-btn" data-swap="${origKey}" title="Zamień skill">↔</button>`;

        const skillHint = curRow.hint || '';
        return `
            <div class="wizard-skill-row${changed ? ' wizard-skill-row--changed' : ''}" data-orig="${origKey}">
                <span class="wizard-skill-name">
                    ${_esc(curRow.label)} <span class="wizard-skill-stat">— ${curRow.stat}</span>
                    ${skillHint ? `<span class="wizard-stat-hint" data-tooltip="${_esc(skillHint)}">?</span>` : ''}
                    ${swapBtn}
                </span>
                <div class="wizard-stat-controls wizard-skill-controls">
                    <button type="button" class="wizard-stat-btn" data-skill-dir="-" data-orig="${origKey}" ${canMinus ? '' : 'disabled'}>−</button>
                    <span class="wizard-skill-rank">${rank} · ${rankName}</span>
                    <button type="button" class="wizard-stat-btn" data-skill-dir="+" data-orig="${origKey}" ${canPlus ? '' : 'disabled'}>+</button>
                </div>
            </div>`;
    }).join('');

    c.innerHTML = `
        <div class="wizard-form">
            <p class="wizard-hint">Wylosowane umiejętności. Zamiana (↔) na inną bezpłatna. Zmiana poziomu (±) kosztuje punkty budżetu. Max ${WIZARD_MAX_SWAPS} łącznie.</p>
            <div class="wizard-swaps">Zmieniono: <strong>${budgetUsed} / ${WIZARD_MAX_SWAPS}</strong></div>
            <div class="wizard-skill-list">${rows}</div>
            <button type="button" class="btn btn--secondary wizard-reset-btn" id="wiz-skill-reset">Reset</button>
        </div>
    `;

    // Swap mode open
    c.querySelectorAll('[data-swap]').forEach(btn => {
        btn.addEventListener('click', () => { wizardSwapModeSlot = btn.dataset.swap; _renderStep3(c); });
    });
    // Swap mode cancel
    c.querySelectorAll('[data-cancel-swap]').forEach(btn => {
        btn.addEventListener('click', () => { wizardSwapModeSlot = null; _renderStep3(c); });
    });
    // Swap select chosen
    c.querySelectorAll('.wizard-skill-swap-sel').forEach(sel => {
        sel.addEventListener('change', () => {
            if (!sel.value) return;
            wizardSkillSwapMap[sel.dataset.orig] = sel.value;
            wizardSwapModeSlot = null;
            _renderStep3(c);
        });
    });
    // Revert swap
    c.querySelectorAll('[data-revert]').forEach(btn => {
        btn.addEventListener('click', () => {
            delete wizardSkillSwapMap[btn.dataset.revert];
            wizardSwapModeSlot = null;
            _renderStep3(c);
        });
    });
    // Level +/-
    c.querySelectorAll('[data-skill-dir]').forEach(btn => {
        btn.addEventListener('click', () => {
            const origKey = btn.dataset.orig;
            const delta = btn.dataset.skillDir === '+' ? 1 : -1;
            if (!_canAdjSkill(origKey, delta)) return;
            const cur = wizardSkillLevels[origKey] ?? Number(wizardSkillSnapshot[origKey] || 0);
            wizardSkillLevels[origKey] = cur + delta;
            _renderStep3(c);
        });
    });
    // Reset
    document.getElementById('wiz-skill-reset')?.addEventListener('click', () => {
        wizardSkillLevels = {};
        wizardSkillSwapMap = {};
        wizardSwapModeSlot = null;
        _renderStep3(c);
    });
}

// Step 4 — Identity review (LLM-generated)
const BOND_TYPES   = ['person','place','object','ideal'];
const WEAKNESS_TYPES = ['fear','flaw','addiction','trauma'];
const BOND_TYPE_LABELS     = {person:'Osoba',place:'Miejsce',object:'Przedmiot',ideal:'Ideał'};
const WEAKNESS_TYPE_LABELS = {fear:'Strach',flaw:'Wada',addiction:'Nałóg',trauma:'Trauma'};

function _typeSelect(id, options, labels, current) {
    return `<select id="${id}" class="wizard-type-select">${
        options.map(o => `<option value="${o}"${o===current?' selected':''}>${labels[o]||o}</option>`).join('')
    }</select>`;
}

function _renderStep4(c) {
    const p = wizardIdentityPreview;
    if (!p) {
        c.innerHTML = `<div class="wizard-form"><p class="wizard-hint">GM konsultuje starsze, mroczniejsze księgi...</p></div>`;
        return;
    }
    const bonds     = p.bonds     || [{description:p.bond||'',type:'ideal'},{description:'',type:'ideal'}];
    const weaknesses= p.weaknesses|| [{description:p.flaw||'',type:'flaw'},{description:'',type:'flaw'}];

    const _mkSelect = (id, types, labels, val) =>
      `<select class="wiz-identity-type" id="${id}">
        ${types.map(t=>`<option value="${t}"${val===t?' selected':''}>${labels[t]||t}</option>`).join('')}
       </select>`;

    const bondsHtml = bonds.slice(0,2).map((b,i) => `
        <div class="wiz-identity-pair">
          <div class="wiz-identity-pair-header">
            ${_mkSelect(`wiz-bond-type-${i}`, BOND_TYPES, BOND_TYPE_LABELS, b.type||'ideal')}
          </div>
          <textarea id="wiz-bond-${i}" rows="2" class="wiz-identity-textarea"
            placeholder="Opisz więź…">${_esc(b.description||'')}</textarea>
        </div>`).join('');

    const weakHtml = weaknesses.slice(0,2).map((w,i) => `
        <div class="wiz-identity-pair">
          <div class="wiz-identity-pair-header">
            ${_mkSelect(`wiz-weak-type-${i}`, WEAKNESS_TYPES, WEAKNESS_TYPE_LABELS, w.type||'flaw')}
          </div>
          <textarea id="wiz-weak-${i}" rows="2" class="wiz-identity-textarea"
            placeholder="Opisz słabość…">${_esc(w.description||'')}</textarea>
        </div>`).join('');

    c.innerHTML = `
        <div class="wiz-identity-grid">
          <div class="wiz-identity-card">
            <div class="wiz-identity-label">Wygląd</div>
            <textarea id="wiz-appearance" rows="3" class="wiz-identity-textarea"
              placeholder="Jak wygląda twój bohater?">${_esc(p.appearance)}</textarea>
          </div>
          <div class="wiz-identity-card">
            <div class="wiz-identity-label">Osobowość</div>
            <textarea id="wiz-personality" rows="3" class="wiz-identity-textarea"
              placeholder="Jak zachowuje się twój bohater?">${_esc(p.personality)}</textarea>
          </div>
          <div class="wiz-identity-card">
            <div class="wiz-identity-label">Więzi</div>
            ${bondsHtml}
          </div>
          <div class="wiz-identity-card">
            <div class="wiz-identity-label">Słabości</div>
            ${weakHtml}
          </div>
          <div class="wiz-identity-hint">GM zna też to, o czym sam nie wiesz. Objawi się w swoim czasie.</div>
        </div>
    `;
}

function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function handleWizardPrev() {
    if (wizardStepNum > 0) {
        wizardStepNum--;
        _wizardRender();
    }
}

function _wizardSetLoading(loading) {
    const btn = elements.btnWizardNext;
    btn.disabled = loading;
    if (loading) {
        btn.dataset.prevText = btn.innerHTML;
        btn.innerHTML = '<span class="wiz-loading-dots"></span>';
    } else if (btn.dataset.prevText) {
        btn.innerHTML = btn.dataset.prevText;
    }
}

async function handleWizardNext() {
    _wizardSetLoading(true);
    try {
        if (wizardStepNum === 0) {
            await _wizardStep1Submit();
        } else if (wizardStepNum === 1) {
            wizardStepNum = 2;
            _wizardRender();
        } else if (wizardStepNum === 2) {
            await _wizardStep3Submit();
        } else {
            await _wizardFinalizeAndEnter();
        }
    } catch (err) {
        showToast(err.message || 'Błąd kreatora postaci', 'error');
    } finally {
        _wizardSetLoading(false);
    }
}

async function _wizardStep1Submit() {
    const name = document.getElementById('char-name')?.value?.trim();
    const bg = document.getElementById('char-bg')?.value?.trim() || '';
    const archBtn = elements.wizardContent.querySelector('.archetype-card--selected');
    const archetype = archBtn?.dataset?.arch || 'warrior';

    if (!name) { showToast('Podaj imię postaci', 'error'); elements.btnWizardNext.disabled = false; return; }

    let char;
    if (wizardCreatedChar && wizardCreatedChar.name === name && (wizardCreatedChar.sheet_json?.archetype === archetype)) {
        char = wizardCreatedChar;
    } else if (currentCampaignId) {
        // Classic flow: campaign already exists, create character inside it
        char = await apiRequest('POST', `/campaigns/${currentCampaignId}/characters`, {
            user_id: currentUser?.id,
            name,
            system_id: currentCampaign?.system_id || 'fantasy',
            sheet_json: { archetype, background_note: bg, backstory: bg },
        });
    } else {
        // Hero-first flow: create standalone character, no campaign yet
        char = await apiRequest('POST', `/characters`, {
            user_id: currentUser?.id,
            name,
            system_id: 'fantasy',
            sheet_json: { archetype, background_note: bg, backstory: bg },
        });
    }

    wizardCreatedChar = char;
    const sheet = char.sheet_json || {};
    const archKey = sheet.archetype || 'warrior';
    const bonus = ARCHETYPE_BONUS[archKey] || {};
    const storedStats = sheet.stats || {};

    // Reverse-engineer pre-bonus base values (LCK defaults to 8)
    for (const k of ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA', 'LCK']) {
        const bonVal = bonus[k] || 0;
        const defVal = k === 'LCK' ? 8 : 10;
        wizardStatBases[k] = Math.max(WIZARD_STAT_MIN, (storedStats[k] || defVal) - bonVal);
    }
    wizardStatOriginal = { ...wizardStatBases };
    wizardStatUnassigned = 0;

    // Build skill snapshot from skills_at_creation
    const skillsOrig = sheet.skills_at_creation || sheet.skills || {};
    wizardSkillSnapshot = {};
    wizardSkillLevels = {};
    wizardSkillSwapMap = {};
    wizardSwapModeSlot = null;
    for (const { key } of ALL_SKILL_ROWS) {
        const v = Math.max(0, Math.min(2, Number(skillsOrig[key] || 0)));
        wizardSkillSnapshot[key] = v;
        if (v > 0) wizardSkillLevels[key] = v;
    }

    wizardStepNum = 1;
    _wizardRender();
}

async function _wizardStep3Submit() {
    // Generate identity while transitioning to step 4
    elements.wizardContent.innerHTML = `<div class="wizard-form"><p class="wizard-hint">Generowanie tożsamości postaci przez AI...</p></div>`;
    wizardStepNum = 3;
    elements.wizardStep.textContent = WIZARD_STEPS[3].subtitle;
    elements.wizardTitle.textContent = WIZARD_STEPS[3].title;
    elements.btnWizardPrev.style.display = 'block';
    elements.btnWizardNext.innerHTML = 'Rozpocznij przygodę <span class="btn__icon">✨</span>';

    const charId = wizardCreatedChar?.id || wizardCreatedChar?.character_id;
    wizardIdentityPreview = await apiRequest('POST', `/characters/${charId}/generate-identity`);
    _renderStep4(elements.wizardContent);
    elements.btnWizardNext.disabled = false;
}

async function _wizardFinalizeAndEnter() {
    const charId = wizardCreatedChar?.id || wizardCreatedChar?.character_id;

    // Build stat_overrides from redistributed bases
    const statOverrides = { ...wizardStatBases };

    // Build skills dict and skill_slot_current from new state model
    const finalSkills = {};
    const skillSlotCurrent = {};
    for (const { key } of ALL_SKILL_ROWS) finalSkills[key] = 0;
    for (const { key: origKey } of ALL_SKILL_ROWS) {
        const snap = Number(wizardSkillSnapshot[origKey] || 0);
        if (!snap) continue;
        const tgt = wizardSkillSwapMap[origKey] || origKey;
        const lv = Math.max(0, Math.min(2, wizardSkillLevels[origKey] ?? snap));
        finalSkills[tgt] = lv;
        skillSlotCurrent[origKey] = tgt;
    }

    // Identity overrides — V2 structured format
    const appearance = document.getElementById('wiz-appearance')?.value?.trim() || wizardIdentityPreview?.appearance || '';
    const personality = document.getElementById('wiz-personality')?.value?.trim() || wizardIdentityPreview?.personality || '';

    const bonds = [0,1].map(i => ({
        description: document.getElementById(`wiz-bond-${i}`)?.value?.trim() || '',
        type: document.getElementById(`wiz-bond-type-${i}`)?.value || 'ideal',
    })).filter(b => b.description);

    const weaknesses = [0,1].map(i => ({
        description: document.getElementById(`wiz-weak-${i}`)?.value?.trim() || '',
        type: document.getElementById(`wiz-weak-type-${i}`)?.value || 'flaw',
    })).filter(w => w.description);

    const result = await apiRequest('POST', `/characters/${charId}/finalize-sheet`, {
        stat_overrides: statOverrides,
        skills: finalSkills,
        skill_slot_current: Object.keys(skillSlotCurrent).length > 0 ? skillSlotCurrent : null,
        identity_overrides: {
            appearance,
            personality,
            bonds: bonds.length > 0 ? bonds : null,
            weaknesses: weaknesses.length > 0 ? weaknesses : null,
        },
    });

    if (currentCampaignId) {
        // Classic flow: reload from campaign and enter game
        const chars = await apiRequest('GET', `/campaigns/${currentCampaignId}/characters`);
        const charList = chars.characters || (Array.isArray(chars) ? chars : []);
        characterData = charList.find(c => c.id === charId) || wizardCreatedChar;
        if (result?.sheet_json) characterData.sheet_json = result.sheet_json;
        await enterGame(currentCampaign);
    } else {
        // Hero-first flow: hero created standalone → go to campaigns chooser
        currentHero = wizardCreatedChar;
        if (elements.welcomeUser) elements.welcomeUser.textContent = `Bohater: ${wizardCreatedChar.name}`;
        showToast(`Bohater ${wizardCreatedChar.name} gotowy! Wybierz przygodę.`, 'success', 3000);
        await loadCampaigns();
        showScreen('campaigns');
    }
}

// ============================================================================
// Game Screen
// ============================================================================
// ── In-game clock (T5) ───────────────────────────────────────────────────
// Renders "Dzień 3, 14:00 Popołudnie" in the header. Mirrors backend state
// from clock_service.get_clock_state() — single source of truth is server.
function renderClock(state) {
    const el = elements.headerClock;
    if (!el) return;
    if (!state || typeof state.display !== 'string') {
        el.textContent = '';
        el.hidden = true;
        return;
    }
    el.textContent = state.display;
    el.hidden = false;
    // Tone-aware accent: night gets cooler colour, evening warmer
    el.dataset.period = state.period || '';
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

async function enterGame(campaign) {
    // Persist session so F5 restores to this exact state
    try {
        if (currentHero?.id) localStorage.setItem('aigm_hero_id', currentHero.id);
        if (campaign?.id) localStorage.setItem('aigm_campaign_id', campaign.id);
    } catch {}

    const sheet = characterData?.sheet_json || characterData || {};
    elements.characterNameDisplay.textContent = characterData?.name || 'Bohater';
    const level = sheet.level || characterData?.level || 1;
    const hp = sheet.current_hp ?? characterData?.hp ?? 29;
    const maxHp = sheet.max_hp ?? characterData?.max_hp ?? 29;
    elements.characterStatsDisplay.textContent = `Poziom ${level} • ${hp}/${maxHp} HP`;
    elements.chatMessages.innerHTML = '';

    // T5 — fetch initial clock state and render in header
    fetchAndRenderClock(campaign.id);

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
        timeline.sort((a, b) => {
            const ta = String(a.at || ''), tb = String(b.at || '');
            if (ta !== tb) return ta < tb ? -1 : 1;
            // Same timestamp: combat events first (they fired before the wrapping campaign turn)
            if (a.kind !== b.kind) return a.kind === 'combat' ? -1 : 1;
            return Number(a.data.id || 0) - Number(b.data.id || 0);
        });

        if (timeline.length > 0) {
            for (const item of timeline) {
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
                appendMessage({ role: 'assistant', content: 'Witaj, bohaterze. Twoja przygoda się zaczyna…', created_at: new Date() });
            }
            scrollToBottom();
            return; // already called showScreen + startCombatPolling above
        }
    } catch (error) {
        console.error('Failed to load chat history:', error);
    }

    if (characterData) {
        populateCharacterSheet(characterData);
    }

    updateAdminSettingsVisibility();
    showScreen('game');
    scrollToBottom();
    window.clog?.setContext({ campaign_id: campaign.id, character_id: characterData?.id, screen: 'game' });
    window.clog?.event('game_entered', { campaign_id: campaign.id, character_id: characterData?.id });
    startCombatPolling();
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

    // Debug block — plain div (avoid <details> overflow:hidden bug in Chrome)
    if (msg.role === 'assistant' || msg.actor === 'gm') {
        const m = msg.debugMeta || {};
        const cs = typeof lastCombatState !== 'undefined' ? lastCombatState : null;

        let locLine = 'LOCATION: (brak)';
        let locJson = '';
        if (m.locationIntent) {
            const li = m.locationIntent;
            locLine = `▼ LOCATION: ${li.action || '—'} → ${li.target_label || ''}`;
            locJson = JSON.stringify(li, null, 2);
        }

        const dbg = document.createElement('div');
        dbg.className = 'debug-block';
        dbg.dataset.stale = '1';
        dbg.style.display = debugMode ? 'block' : 'none';
        _renderDebugCombatLine(dbg, cs);
        dbg.innerHTML += `<span class="debug-block__loc">${escapeHtml(locLine)}${locJson ? '\n' + escapeHtml(locJson) : ''}</span>`;
        elements.chatMessages.appendChild(dbg);
    }
}

function _renderDebugCombatLine(dbg, cs) {
    const line = cs && cs.active
        ? `COMBAT: active=true, turn=${cs.current_turn ?? '—'}, round=${cs.round ?? '—'}`
        : cs
            ? `COMBAT: active=false (turn=${cs.current_turn ?? '—'}, round=${cs.round ?? '—'})`
            : 'COMBAT: (brak — active=false)';
    let el = dbg.querySelector('.debug-block__combat');
    if (!el) {
        el = document.createElement('pre');
        el.className = 'debug-block__pre debug-block__combat';
        dbg.prepend(el);
    }
    el.textContent = line;
}

function _refreshDebugBlocks() {
    const cs = typeof lastCombatState !== 'undefined' ? lastCombatState : null;
    document.querySelectorAll('.debug-block[data-stale]').forEach(dbg => {
        _renderDebugCombatLine(dbg, cs);
        delete dbg.dataset.stale;
    });
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

function parseGmFull(text) {
    if (!text) return { narrative: '', locationIntent: null };
    let raw = String(text).trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim();
    try {
        const data = JSON.parse(raw);
        if (data && typeof data === 'object') {
            return {
                narrative: typeof data.narrative === 'string' ? data.narrative : '',
                locationIntent: data.location_intent || null,
                raw: data,
            };
        }
    } catch (_e) {}
    return { narrative: parseGmResponse(text), locationIntent: null };
}

function parseGmResponse(text) {
    const stripExtra = s => String(s || '')
        .replace(/\s*\[LOCATION_BLOCKED:[^\]]*\]/g, '')
        .trim();

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

function formatGmNarrative(content) {
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
        showToast(e.message || 'Błąd /mem', 'error');
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
        btn.className = 'suggested-action-btn' + (a.enabled ? '' : ' disabled');
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

// T33: Send a structured action (button click)
async function sendStructuredAction(actionStr, displayLabel) {
    const input = elements.chatInput;
    if (input) input.value = '';
    hideCharCounter();
    await sendTurn(actionStr, 'structured', displayLabel);
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

    // Unlock audio from this user gesture
    window.voiceUI?.unlockAudio?.();

    elements.btnSend.disabled = true;
    renderSuggestedActions([]);  // Clear buttons while waiting

    const displayText = displayLabel || text;
    const userMsgPlaceholder = { role: 'user', content: displayText, created_at: new Date() };
    appendMessage(userMsgPlaceholder);
    scrollToBottom();

    const typingIndicator = showTypingIndicator();
    let _skillTestPending = false;

    try {
        const response = await apiRequest('POST', `/campaigns/${currentCampaignId}/turns`, {
            text: text,
            character_id: characterData.id,
            input_type: inputType,
        });

        typingIndicator.remove();

        // Store and render suggested actions
        _suggestedActions = response.suggested_actions || [];
        renderSuggestedActions(_suggestedActions);

        // ── Skill test pending? Show Roll Popup instead of (or before) prose ──
        if (response.skill_test_pending) {
            if (response.prose) {
                const { narrative: preText } = parseGmFull(response.prose);
                appendMessage({ role: 'assistant', content: preText, created_at: new Date() });
            }
            _skillTestPending = true;  // prevent finally from re-enabling send
            showSkillTestPopup(response.skill_test_pending);
            scrollToBottom();
            return;  // resolveSkillTest will re-enable send when done
        }

        // Backend returns: { result: { message: "..." } } or { result: "..." }
        let gmText = null;
        if (response.result) {
            gmText = typeof response.result === 'string'
                ? response.result
                : (response.result.message || response.result.narrative);
        }
        // Fallback to other possible fields
        gmText = gmText || response.prose || response.assistant_text || response.gm_response || response.content;

        if (gmText) {
            const { narrative: gmContent, ...gmMeta } = parseGmFull(gmText);
            appendMessage({
                role: 'assistant',
                content: gmContent,
                created_at: response.created_at || new Date(),
                turn_number: response.turn_number,
                route: response.route,
                debugMeta: gmMeta,
            });
        }

        // Refresh character data after turn
        await refreshCharacterData();
        // GM may have initiated combat — refresh combat state
        await pollCombatState();
        // Update stale debug blocks with fresh combat state
        _refreshDebugBlocks();
        // Update input placeholder based on current combat state
        updateInputPlaceholder();
    } catch (error) {
        typingIndicator.remove();
        renderSuggestedActions(_suggestedActions);  // Restore previous buttons on error
        console.error('Send message error:', error);
        showToast(error.message || 'Nie udało się wysłać wiadomości', 'error');
    } finally {
        if (!_skillTestPending) elements.btnSend.disabled = false;
        scrollToBottom();
    }
}

async function handleSendMessage() {
    const content = elements.chatInput.value.trim();
    if (!content) return;

    elements.chatInput.value = '';
    hideCharCounter();

    if (content.startsWith('/')) {
        const handled = await handleSlashCommand(content);
        if (handled) return;
    }

    await sendTurn(content, 'free_text');
}

// ── Skill Test Roll Popup v3 — compact staged ────────────────────────────────

function showSkillTestPopup(pending) {
    const existing = document.getElementById('skill-roll-popup');
    if (existing) existing.remove();

    const mod   = pending.modifier_breakdown || {};
    const total = mod.total || 0;
    const sign  = total >= 0 ? '+' : '';
    const name  = (pending.skill_label || pending.skill_key || 'Umiejętność').toUpperCase();

    // Compact modifier summary — single line, only non-zero parts
    const modParts = [
        mod.skill_rank  ? `Ranga <span>+${mod.skill_rank}</span>`  : '',
        mod.stat_mod    ? `Mod.${mod.governing_stat||'STAT'} <span>${mod.stat_mod>=0?'+':''}${mod.stat_mod}</span>` : '',
        mod.proficiency ? `Biegłość <span>+${mod.proficiency}</span>` : '',
    ].filter(Boolean).join(' · ');
    const modsHTML = modParts || `Bonus <span>${sign}${total}</span>`;

    // Compact SVG d20 (decagon + inner triangle)
    const D20 = `<svg viewBox="0 0 200 200" class="srp-die-svg" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="srpGrad" cx="50%" cy="42%" r="58%">
          <stop offset="0%" stop-color="#1c1408"/>
          <stop offset="100%" stop-color="#060403"/>
        </radialGradient>
      </defs>
      <polygon class="srp-d20-outer"
        points="100,5 155.8,23.1 190.4,70.6 190.4,129.4 155.8,176.9 100,195 44.2,176.9 9.6,129.4 9.6,70.6 44.2,23.1"
        fill="url(#srpGrad)" stroke="#7a5618" stroke-width="2"/>
      <polygon points="100,44 162,150 38,150"
        fill="none" stroke="#4a360e" stroke-width="1" opacity="0.55"/>
      <line x1="100" y1="44" x2="100" y2="6"   stroke="#3a2a0a" stroke-width="0.7" opacity="0.45"/>
      <line x1="162" y1="150" x2="189" y2="130" stroke="#3a2a0a" stroke-width="0.7" opacity="0.45"/>
      <line x1="38"  y1="150" x2="11"  y2="130" stroke="#3a2a0a" stroke-width="0.7" opacity="0.45"/>
      <text class="srp-d20-num" id="srp-num" x="100" y="113"
        text-anchor="middle" dominant-baseline="middle"
        font-family="Cinzel,serif" font-size="56" font-weight="700" fill="#c9961a">?</text>
    </svg>`;

    const popup = document.createElement('div');
    popup.id = 'skill-roll-popup';
    popup.className = 'skill-roll-overlay';
    popup.innerHTML = `
      <div class="srp-card">
        <div class="srp-head">
          <div class="srp-eyebrow">Próba Umiejętności</div>
          <div class="srp-name">${escapeHtml(name)}</div>
          <div class="srp-mods-line">${modsHTML} · Bonus <span>${sign}${total}</span></div>
        </div>
        <div class="srp-die-stage">
          <div class="srp-die-wrap" id="srp-die">${D20}</div>
          <div class="srp-result" id="srp-result">
            <span class="srp-res-val" id="srp-rd20">—</span>
            <span class="srp-res-sep">${sign}${total}</span>
            <span class="srp-res-sep">=</span>
            <span class="srp-res-total" id="srp-rtot">—</span>
            <span class="srp-res-label" id="srp-rlbl"></span>
          </div>
          <div class="srp-nat" id="srp-nat"></div>
        </div>
        <div class="srp-foot">
          <button class="srp-btn srp-btn-roll" id="srp-roll">⚄  Rzuć k20</button>
          <button class="srp-btn srp-btn-confirm" id="srp-confirm" style="display:none">Zatwierdź wynik</button>
        </div>
      </div>`;

    const _chatRoot = document.getElementById('chat-container') || document.body;
    _chatRoot.appendChild(popup);

    let rolled = null;
    const dieWrap = popup.querySelector('#srp-die');
    const dieNum  = popup.querySelector('#srp-num');
    const result  = popup.querySelector('#srp-result');
    const rd20    = popup.querySelector('#srp-rd20');
    const rtot    = popup.querySelector('#srp-rtot');
    const rlbl    = popup.querySelector('#srp-rlbl');
    const nat     = popup.querySelector('#srp-nat');
    const rollBtn = popup.querySelector('#srp-roll');
    const confBtn = popup.querySelector('#srp-confirm');

    rollBtn.addEventListener('click', () => {
        rollBtn.disabled = true;
        dieWrap.classList.add('srp-rolling');
        let ticks = 0;
        const iv = setInterval(() => {
            dieNum.textContent = Math.ceil(Math.random() * 20);
            if (++ticks >= 16) {
                clearInterval(iv);
                rolled = Math.ceil(Math.random() * 20);
                const sum   = rolled + total;
                const nat20 = rolled === 20;
                const nat1  = rolled === 1;

                dieWrap.classList.remove('srp-rolling');
                dieWrap.classList.add('srp-landed');
                dieNum.textContent = rolled;

                const outer = popup.querySelector('.srp-d20-outer');
                if (nat20) {
                    outer.style.stroke = '#f0c040';
                    dieNum.style.fill  = '#f0c040';
                    dieWrap.classList.add('srp-nat20');
                    nat.textContent = 'Naturalny 20';
                    nat.className = 'srp-nat nat20';
                } else if (nat1) {
                    outer.style.stroke = '#8b1a1a';
                    dieNum.style.fill  = '#c04040';
                    dieWrap.classList.add('srp-nat1');
                    nat.textContent = 'Naturalny 1';
                    nat.className = 'srp-nat nat1';
                }

                setTimeout(() => {
                    rd20.textContent = rolled;
                    rtot.textContent = sum;
                    rtot.className   = 'srp-res-total' + (nat20 ? ' nat20' : nat1 ? ' nat1' : '');
                    rlbl.textContent = nat20 ? '✦' : nat1 ? '✧' : '';
                    result.classList.add('visible');
                    confBtn.style.display = '';
                }, 220);
            }
        }, 65);
    });

    confBtn.addEventListener('click', async () => {
        if (rolled === null) return;
        confBtn.disabled = true;
        confBtn.textContent = 'Rozwiązuję…';
        await resolveSkillTest(pending.skill_test_id, rolled, popup);
    });
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
            const outcome = sr.nat20 ? ' — Naturalny 20!' : sr.nat1 ? ' — Naturalny 1' : sr.success ? ' — Sukces' : ' — Porażka';
            const rollLine = `🎲 ${skillName}: ${sr.d20_roll} +${sr.modifier} = ${sr.player_total}${outcome}`;
            appendMessage({ role: 'user', content: rollLine, created_at: new Date() });
            // Keep reference to roll bubble so we can scroll to it (not the very bottom)
            rollBubbleEl = elements.chatMessages.lastElementChild;
        }
        // Crit flash (T34) — skill-test path
        if (sr.nat20) triggerCritFlash('crit');
        else if (sr.nat1) triggerCritFlash('fumble');

        if (response.prose) {
            const { narrative: gmContent } = parseGmFull(response.prose);
            appendMessage({
                role: 'assistant',
                content: gmContent,
                created_at: new Date(),
                turn_number: response.turn_number,
            });
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

        // Re-enable input
        if (elements.btnSend) elements.btnSend.disabled = false;
    } catch (err) {
        popupEl?.remove();
        showToast(err.message || 'Błąd rozwiązania testu', 'error');
        if (elements.btnSend) elements.btnSend.disabled = false;
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

function updateHeaderStats() {
    if (!characterData) return;
    const sheet = characterData.sheet_json || characterData;
    const level = sheet.level || characterData.level || 1;
    const hp = sheet.current_hp ?? characterData.hp ?? 29;
    const maxHp = sheet.max_hp ?? characterData.max_hp ?? 29;
    elements.characterStatsDisplay.textContent = `Poziom ${level} • ${hp}/${maxHp} HP`;

    if (elements.headerHpBarFill && maxHp > 0) {
        const pct = Math.max(0, Math.min(100, (hp / maxHp) * 100));
        elements.headerHpBarFill.style.width = `${pct}%`;
        elements.headerHpBarFill.classList.toggle('header-hp-bar__fill--low', pct <= 40 && pct > 20);
        elements.headerHpBarFill.classList.toggle('header-hp-bar__fill--critical', pct <= 20);
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
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

// ============================================================================
// Combat
// ============================================================================
const COMBAT_ROLL_PREFIX = '__AI_GM_COMBAT_ROLL_V1__';
let combatPollTimer = null;
let combatActive = false;
let combatBusy = false;
let lastCombatState = null;
let enemyTurnInFlight = false;
let pendingLoot = null;
let pendingGold = 0;

function startCombatPolling() {
    stopCombatPolling();
    pollCombatState();
    combatPollTimer = setInterval(pollCombatState, 3500);
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
            if (combatActive) {
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
        }

        // Auto-trigger enemy turn when it's not the player's turn
        if (cs.current_turn !== 'player' && !enemyTurnInFlight && !combatBusy) {
            await handleEnemyTurn();
        }
    } catch (e) {
        window.clog?.warn('combat_poll_exception', { message: String(e?.message || e) });
    }
}

async function handleEnemyTurn() {
    if (enemyTurnInFlight || !currentCampaignId) return;
    enemyTurnInFlight = true;
    setCombatMsg('Tura wroga...');
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/enemy-turn`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
            setCombatMsg('Błąd tury wroga.', true);
            return;
        }
        const cs = data.combat_state;
        if (cs) {
            lastCombatState = cs;
            renderCombatUI(cs);
        }
        await fetchAndAppendNewCombatTurns();
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
        if (loot.length > 0 || gold > 0) {
            await showLootPopup(loot, gold);
        }
        showCombatEndOverlay('victory', loot, gold);
    } else if (reason === 'fled') {
        hideCombatUI();
        showCombatEndOverlay('fled', [], 0);
    } else if (reason === 'player_dead') {
        hideCombatUI();
        showDeathScreen(characterData?.name || 'Bohater');
    } else {
        hideCombatUI();
    }
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

function showLootPopup(loot, gold) {
    return new Promise(resolve => {
        const el = elements.combatLootOverlay;
        if (!el) { resolve([]); return; }
        const list = Array.isArray(loot) ? loot : [];
        const goldAmt = Math.max(0, Number(gold || 0));
        let html = list.length === 0
            ? '<p class="combat-loot-empty">Wróg nic nie miał.</p>'
            : '<ul>' + list.map((L, idx) => {
                const k = String(L?.label || L?.source_key || L?.key || '?').replace(/_/g, ' ');
                const qty = Number(L?.qty ?? L?.quantity ?? 1) || 1;
                return `<li><label><input type="checkbox" data-loot-idx="${idx}" checked> 📦 ${escapeHtml(k)} ×${qty}</label></li>`;
            }).join('') + '</ul>';
        if (goldAmt > 0) html += `<p>💰 +${goldAmt} GP (already added)</p>`;
        elements.combatLootList.innerHTML = html;
        el.hidden = false;
        const claim = async () => {
            el.hidden = true;
            const picks = Array.from(el.querySelectorAll('[data-loot-idx]:checked'))
                .map(x => Number(x.getAttribute('data-loot-idx')));
            if (picks.length > 0 && characterData?.id) {
                try {
                    await fetch(`/api/campaigns/${currentCampaignId}/combat/loot/claim`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ character_id: characterData.id, selected_indexes: picks })
                    });
                } catch (_e) {}
            }
            resolve(picks);
        };
        elements.combatLootClaimBtn.onclick = claim;
        elements.combatLootSkipBtn.onclick = () => { el.hidden = true; resolve([]); };
    });
}

function showCombatUI() {
    combatActive = true;
    lastRenderedCombatTurnId = 0;
    elements.combatBanner.hidden = false;
    elements.combatComposer.hidden = false;
    elements.composer?.classList.add('composer--hidden');
    // Show spell button for Scholar
    const sheet = characterData?.sheet_json || characterData || {};
    const parsedSheet = typeof sheet === 'string' ? JSON.parse(sheet) : sheet;
    const spellBtn = document.getElementById('combat-spell-btn');
    if (spellBtn) spellBtn.style.display = parsedSheet.archetype === 'scholar' ? '' : 'none';
    updateInputPlaceholder();
}

function hideCombatUI() {
    combatActive = false;
    lastCombatState = null;
    enemyTurnInFlight = false;
    pendingLoot = null;
    pendingGold = 0;
    elements.combatBanner.hidden = true;
    elements.combatComposer.hidden = true;
    elements.composer?.classList.remove('composer--hidden');
    if (elements.initiativeTrack) elements.initiativeTrack.innerHTML = '';
    _initActedThisRound = new Set();
    _initLastRound = 0;
    _initLastCurrentTurn = null;
    setCombatMsg('');
    updateInputPlaceholder();
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
    crit:   { title: 'Cios Krytyczny', sub: 'Naturalny 20 — podwójne obrażenia' },
    fumble: { title: 'Fatalne Pudło',  sub: 'Naturalny 1 — coś poszło nie tak' },
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

function _renderInitiativeTrack(cs) {
    const track = elements.initiativeTrack;
    if (!track) return;

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
        const tier = pct > 60 ? 'high' : (pct > 25 ? 'mid' : 'low');
        const portrait = isPlayer ? '🛡️' : (downed ? '💀' : '⚔️');
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
        return `
            <div class="${cls}" data-combatant-id="${escapeHtml(id)}" title="${escapeHtml(name)}${ini ? ' · ' + ini : ''} · ${zoneLabel}">
                <div class="init-chip__zone" aria-label="${zoneLabel}">${zoneGlyph}</div>
                <div class="init-chip__portrait">${portrait}</div>
                <div class="init-chip__name">${escapeHtml(name)}</div>
                <div class="init-chip__ini">${ini}</div>
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

function renderCombatUI(cs) {
    const round = Number(cs.round || 1);
    elements.combatRound.textContent = `Runda ${round}`;

    const combatants = Array.isArray(cs.combatants) ? cs.combatants : [];
    const player = combatants.find(c => c && c.type === 'player');
    const enemies = combatants.filter(c => c && c.type === 'enemy');
    const isPlayerTurn = cs.current_turn === 'player';

    _renderInitiativeTrack(cs);

    window.clog?.event('combat_render', {
        round, current_turn: String(cs.current_turn ?? 'null'), is_player_turn: isPlayerTurn, enemy_count: enemies.length,
    });

    elements.combatTurnLabel.textContent = isPlayerTurn ? 'Twoja tura' : 'Tura wroga';
    elements.combatTurnLabel.classList.toggle('combat-banner__turn--enemy', !isPlayerTurn);
    elements.combatTurnLabel.classList.toggle('combat-banner__turn--player', isPlayerTurn);

    const combatantRow = (c, isPlayer) => {
        const hpCur = Math.max(0, Number(c.hp_current ?? 0));
        const hpMax = Math.max(1, Number(c.hp_max ?? hpCur ?? 1));
        const pct = Math.max(0, Math.min(100, Math.round((hpCur / hpMax) * 100)));
        const dead = hpCur <= 0;
        const def = c.defense != null ? ` · DEF ${c.defense}` : '';
        const ini = c.initiative_roll != null ? `INI ${c.initiative_roll}` : '';
        if (isPlayer) {
            const hpPct = pct > 60 ? 'high' : (pct > 25 ? 'mid' : 'low');
            const woundHTML = renderWoundLabelHTML(hpCur, hpMax);
            return `
                <div class="combat-combatant combat-combatant--player">
                    <div class="combat-combatant__icon">🛡️</div>
                    <div class="combat-combatant__body">
                        <div class="combat-combatant__name">
                            <span class="combat-combatant__name-text">${escapeHtml(c.name || 'Bohater')}</span>
                            <span class="combat-combatant__meta">${ini}</span>
                        </div>
                        <div class="combat-combatant__hp-row">
                            <span>HP</span>
                            <span>${hpCur} / ${hpMax}${def}</span>
                        </div>
                        <div class="combat-enemy__bar">
                            <div class="combat-enemy__bar-fill combat-player__bar-fill--${hpPct}" style="width: ${pct}%"></div>
                        </div>
                        ${woundHTML}
                    </div>
                </div>`;
        }
        const tier = dead ? 'low' : (pct > 60 ? 'high' : (pct > 25 ? 'mid' : 'low'));
        const name = String(c.name || c.enemy_key || 'Wróg');
        return `
            <div class="combat-combatant combat-combatant--enemy ${dead ? 'combat-enemy--dead' : ''}">
                <div class="combat-combatant__icon">${dead ? '💀' : '⚔️'}</div>
                <div class="combat-combatant__body">
                    <div class="combat-combatant__name">
                        <span class="combat-combatant__name-text ${dead ? 'combat-enemy--dead' : ''}">${escapeHtml(name)}</span>
                        <span class="combat-combatant__meta">${ini}</span>
                    </div>
                    <div class="combat-combatant__hp-row">
                        <span>HP</span>
                        <span>${hpCur} / ${hpMax}${def}</span>
                    </div>
                    <div class="combat-enemy__bar">
                        <div class="combat-enemy__bar-fill combat-enemy__bar-fill--${tier}" style="width: ${pct}%"></div>
                    </div>
                </div>
            </div>`;
    };

    // ── Render combatants into zone columns (T34) ──
    const playerZone = String(player?.zone || 'engaged');
    const renderTo = (el, list) => { if (el) el.innerHTML = list.join(''); };
    const rangedItems = [];
    const engagedItems = [];
    if (player) {
        (playerZone === 'ranged' ? rangedItems : engagedItems).push(combatantRow(player, true));
    }
    enemies.forEach(e => {
        const z = String(e.zone || 'engaged');
        (z === 'ranged' ? rangedItems : engagedItems).push(combatantRow(e, false));
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

    const canAct = isPlayerTurn && !combatBusy;
    elements.btnCombatAttack.disabled = !canAct;
    elements.btnCombatFlee.disabled = !canAct;
    if (elements.btnCombatMove) elements.btnCombatMove.disabled = !canAct;
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
                return row && (et === 'attack' || et === 'death' || et === 'zone_change') &&
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

function appendCombatTurnCard(row) {
    const evt = String(row.event_type || '');
    const actor = String(row.actor || '');
    let html = '';

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
        const label = escapeHtml(String(meta.attack_label || 'ATAK'));
        const stat = meta.attack_stat ? ` · ${escapeHtml(String(meta.attack_stat).toUpperCase())}` : '';
        const ac = meta.target_ac != null ? ` vs AC ${meta.target_ac}` : '';
        const hitLine = hit
            ? `<span class="cturn__hit">✅ TRAFIENIE · ${dmg != null ? dmg : '?'} obrażeń</span>`
            : `<span class="cturn__miss">❌ PUDŁO</span>`;
        html = `<div class="cturn cturn--player">
            <div class="cturn__head">⚔️ <strong>${label}</strong>${stat} → ${tgt}</div>
            <div class="cturn__detail">Rzut: ${rv != null ? rv : '—'}${ac} → ${hitLine}</div>
        </div>`;
    } else if (evt === 'attack' && actor === 'enemy') {
        const hit = row.hit === 1 || row.hit === true;
        const rv = row.roll_value != null ? Number(row.roll_value) : null;
        const dmg = row.damage != null ? Number(row.damage) : null;
        let meta = {};
        try { meta = typeof row.narrative === 'string' ? JSON.parse(row.narrative) : {}; } catch (_e) {}
        const pac = meta.target_ac != null ? ` vs AC ${meta.target_ac}` : '';
        const rawD20 = meta.raw_d20 != null ? meta.raw_d20 : rv;
        const enemyName = escapeHtml(String(meta.enemy_name || row.target_name || 'Wróg'));
        const hitLine = hit
            ? `<span class="cturn__hit">✅ TRAFIENIE · ${dmg != null ? dmg : '?'} obrażeń</span>`
            : `<span class="cturn__miss">❌ PUDŁO</span>`;
        html = `<div class="cturn cturn--enemy">
            <div class="cturn__head">🗡️ <strong>ATAK WROGA</strong> — ${enemyName}</div>
            <div class="cturn__detail">Rzut: ${rawD20 != null ? rawD20 : '—'}${pac} → ${hitLine}</div>
        </div>`;
    }

    if (!html) return;
    const bubble = document.createElement('div');
    const side = actor === 'player' ? 'player' : (actor === 'enemy' ? 'enemy' : 'death');
    bubble.className = `chat-bubble chat-bubble--cturn-${side}`;
    bubble.innerHTML = html;
    elements.chatMessages.appendChild(bubble);
}

function pickEnemyTarget(cs) {
    const combatants = Array.isArray(cs?.combatants) ? cs.combatants : [];
    const living = combatants.filter(c => c && c.type === 'enemy' && Number(c.hp_current ?? 0) > 0);
    if (!living.length) return null;
    const order = Array.isArray(cs.turn_order) ? cs.turn_order : [];
    const livingSet = new Set(living.map(e => String(e.id)));
    for (const tid of order) {
        if (livingSet.has(String(tid))) {
            return living.find(e => String(e.id) === String(tid)) || null;
        }
    }
    return living[0] || null;
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
    combatBusy = true;
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

        window.clog?.event('combat_resolve_attack_request', { d20 });
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/resolve-attack`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await r.json().catch(() => ({}));
        window.clog?.event('combat_resolve_attack_response', { status: r.status, hit: !!data.hit, damage: data.damage ?? 0, enemy_dead: !!data.enemy_dead });
        if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);

        await _handleCombatAttackResult(data, d20, body.enemy_key, target);
    } catch (e) {
        window.clog?.error('combat_attack_exception', { message: String(e?.message || e) });
        setCombatMsg(`Błąd ataku: ${e.message || e}`, true);
    } finally {
        combatBusy = false;
        if (lastCombatState && elements.combatEndOverlay?.hidden !== false) renderCombatUI(lastCombatState);
        elements.btnCombatAttack.disabled = false;
        document.getElementById('combat-spell-btn').disabled = false;
        elements.btnCombatFlee.disabled = false;
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
    if (hit) { setCombatMsg(`Trafienie! ${dmg} obrażeń.`); }
    else if (data.player_nat1) { setCombatMsg('Fatalne pudło!', true); }
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

    if (cs) { lastCombatState = cs; renderCombatUI(cs); }

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
    const dbLine = `${COMBAT_ROLL_PREFIX}\n${JSON.stringify(payload)}`;
    await sendCombatNarration(dbLine);

    if (endedNow) {
        await handleCombatEnded(cs);
    } else {
        await refreshCharacterData();
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
    combatBusy = true;
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
        combatBusy = false;
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

    combatBusy = true;
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
        combatBusy = false;
        if (lastCombatState) renderCombatUI(lastCombatState);
    }
}

async function sendCombatNarration(dbLine) {
    if (!currentCampaignId || !characterData?.id) return;
    const typingIndicator = showTypingIndicator();
    try {
        const response = await apiRequest('POST', `/campaigns/${currentCampaignId}/turns`, {
            text: dbLine,
            character_id: characterData.id
        });
        typingIndicator.remove();
        let gmText = null;
        if (response.result) {
            gmText = typeof response.result === 'string' ? response.result : (response.result.message || response.result.narrative);
        }
        gmText = gmText || response.assistant_text || response.gm_response || response.content;
        if (gmText) {
            const { narrative: gmContent, ...gmMeta } = parseGmFull(gmText);
            if (gmContent && gmContent.trim()) {
                appendMessage({ role: 'assistant', content: gmContent, created_at: response.created_at || new Date(), debugMeta: gmMeta });
                scrollToBottom();
            }
        }
    } catch (e) {
        typingIndicator.remove();
        console.error('[Combat] narration error:', e);
    }
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

    let sheet = character.sheet_json || character;
    if (typeof sheet === 'string') { try { sheet = JSON.parse(sheet); } catch { sheet = {}; } }
    elements.sheetCharacterName.textContent = character.name || 'Bohater';

    // HP
    const hp = sheet.current_hp ?? character.hp ?? 29;
    const maxHp = Math.max(1, sheet.max_hp ?? character.max_hp ?? 29);
    elements.sheetHp.textContent = `${hp} / ${maxHp}`;
    elements.sheetHpBar.style.width = `${Math.max(0, Math.min(100, (hp / maxHp) * 100))}%`;

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

    // Level, XP
    elements.sheetLevel.textContent = sheet.level || character.level || 1;
    const xpEl = document.getElementById('sheet-xp');
    if (xpEl) xpEl.textContent = sheet.xp_available ?? 0;

    // Arcane Points (Scholar)
    const apCard = document.getElementById('sheet-ap-card');
    const apEl = document.getElementById('sheet-arcane-points');
    if (apCard && apEl) {
        const ap = sheet.arcane_points ?? 0;
        apCard.style.display = sheet.archetype === 'scholar' ? '' : 'none';
        apEl.textContent = ap;
    }

    // Stats grid with modifiers
    const stats = sheet.stats || character.stats || {};
    const mods = sheet.stat_modifiers || {};
    const STAT_LABELS = { STR:'Siła', DEX:'Zręczność', CON:'Kondycja', INT:'Inteligencja', WIS:'Mądrość', CHA:'Charyzma', LCK:'Szczęście' };
    const statNames = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA', 'LCK'];
    elements.sheetStats.innerHTML = statNames.map(stat => {
        const val = stats[stat] ?? stats[stat.toLowerCase()] ?? 10;
        const mod = mods[stat] ?? Math.floor((val - 10) / 2);
        const modStr = mod >= 0 ? `+${mod}` : `${mod}`;
        const modCls = mod > 0 ? 'mod--pos' : mod < 0 ? 'mod--neg' : 'mod--zero';
        return `<div class="stat-item">
            <span class="stat-item__label" title="${STAT_LABELS[stat] || stat}">${stat}</span>
            <span class="stat-item__value">${val}</span>
            <span class="stat-item__mod ${modCls}">${modStr}</span>
        </div>`;
    }).join('');

    // Conditions
    const conditions = sheet.conditions || [];
    const condSection = document.getElementById('sheet-conditions-section');
    const condEl = document.getElementById('sheet-conditions');
    if (condSection && condEl) {
        if (conditions.length > 0) {
            condSection.style.display = '';
            condEl.innerHTML = conditions.map(c => {
                const label = typeof c === 'string' ? c : (c.label || c.key || c);
                return `<span class="condition-chip">${escapeHtml(label)}</span>`;
            }).join('');
        } else {
            condSection.style.display = 'none';
        }
    }

    // Show/hide spells tab for Scholar
    const spellsTabBtn = document.getElementById('sheet-tab-spells');
    if (spellsTabBtn) {
        spellsTabBtn.style.display = sheet.archetype === 'scholar' ? '' : 'none';
    }

    renderSkillsTab(sheet);
    renderSpellsTab(character, sheet);
    renderInventoryTab(character);

    // Combined lore tab — data from GM-generated identity block
    const identity = sheet.identity || {};
    const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val || '—';
    };
    const bondText = (identity.bonds && identity.bonds[0]?.text) || identity.bond || sheet.bond || '';
    setText('sheet-backstory-text', sheet.backstory || identity.backstory);
    setText('sheet-appearance-text', identity.appearance || sheet.appearance);
    setText('sheet-personality-text', identity.personality || sheet.personality);
    setText('sheet-flaw-text', identity.flaw || sheet.flaw);
    setText('sheet-bond-text', bondText);
}

// ============================================================================
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

const INV_SLOT_DEFS = [
    { key: 'main_hand', label: 'Główna ręka',     icon: 'sword'  },
    { key: 'off_hand',  label: 'Pomocnicza ręka', icon: 'shield' },
    { key: 'armor',     label: 'Zbroja',          icon: 'armor'  }
];

const INV_ICONS = {
    sword: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 17.5L3 6V3h3l11.5 11.5"/><path d="M13 19l6-6"/><path d="M16 16l4 4"/><path d="M19 21l2-2"/></svg>`,
    shield: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
    armor: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20.4 7.4l-3.4-3a1 1 0 0 0-1.3.1l-1.7 2-1.5-1a1 1 0 0 0-1 0l-1.5 1-1.7-2a1 1 0 0 0-1.3-.1l-3.4 3a1 1 0 0 0-.3 1.1L5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6l1.7-4.5a1 1 0 0 0-.3-1.1z"/><path d="M12 6v15"/></svg>`,
    potion: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2h4"/><path d="M11 2v4.5L6 14a4 4 0 0 0 4 7h4a4 4 0 0 0 4-7L13 6.5V2"/></svg>`,
    scroll: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8a3 3 0 0 0 3-3V8H8"/><path d="M19 8V5a3 3 0 0 0-3-3H5v13a3 3 0 0 0 3 3"/><path d="M5 5h11"/></svg>`,
    pack: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h16v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8z"/><path d="M8 8V5a4 4 0 0 1 8 0v3"/><path d="M9 13h6"/></svg>`
};

// Map item_type → inventory section + icon glyph
function _invIconKind(item) {
    const t = String(item.item_type || '').toLowerCase();
    const k = String(item.key || item.label || '').toLowerCase();
    if (t === 'weapon')                                 return /bow|łuk/.test(k) ? 'sword' : 'sword';
    if (t === 'armor' && /shield|tarcz/.test(k))        return 'shield';
    if (t === 'armor')                                  return 'armor';
    if (t === 'consumable')                             return 'potion';
    return 'scroll';
}

// Same algorithm as legacy frontend's pickEquipSlot
function _invPickEquipSlot(item, occupied) {
    const t = String(item.item_type || '').toLowerCase();
    if (t === 'armor') {
        const k = String(item.key || item.label || '').toLowerCase();
        if (/shield|tarcz/.test(k)) return 'off_hand';
        return 'armor';
    }
    if (t === 'weapon') {
        if (!occupied.main_hand) return 'main_hand';
        if (!occupied.off_hand)  return 'off_hand';
        return 'main_hand';
    }
    return null;
}

function _invIsLore(item) {
    const t = String(item.item_type || '').toLowerCase();
    return t === 'misc' || t === 'quest' || t === 'narrative';
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
        const TYPE_ICONS = { attack:'⚔', heal:'💚', defense:'🛡', effect:'✨', attack_aoe:'💥' };
        listEl.innerHTML = spells.map(s => {
            const icon = TYPE_ICONS[s.spell_type] || '✨';
            const rankPips = Array.from({length: 3}, (_, i) =>
                `<span class="spell-rank-pip${i < (s.rank || 1) ? ' active' : ''}"></span>`
            ).join('');
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
            </div>`;
        }).join('');
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

    // Bucket items by equip status / type
    const equipped = {};   // slot → item
    const backpack = [];
    const lore = [];
    const occupied = { main_hand: false, off_hand: false, armor: false };

    for (const item of items) {
        if (Number(item.equipped) === 1 && item.slot) {
            equipped[item.slot] = item;
            occupied[item.slot] = true;
        } else if (_invIsLore(item)) {
            lore.push(item);
        } else {
            backpack.push(item);
        }
    }

    // Triptych
    const slotsEl = document.getElementById('sheet-equip-slots');
    if (slotsEl) {
        slotsEl.innerHTML = INV_SLOT_DEFS.map(def => _renderSlotCard(def, equipped[def.key])).join('');
    }

    // Backpack
    const bpCount = document.getElementById('inv-backpack-count');
    const bpList = document.getElementById('sheet-backpack');
    if (bpCount) bpCount.textContent = backpack.length;
    if (bpList) {
        bpList.innerHTML = backpack.length
            ? backpack.map(item => _renderBackpackRow(item, occupied)).join('')
            : `<div class="inv-empty">Plecak jest pusty</div>`;
    }

    // Lore
    const loreCount = document.getElementById('inv-lore-count');
    const loreList = document.getElementById('sheet-lore');
    if (loreCount) loreCount.textContent = lore.length;
    if (loreList) {
        loreList.innerHTML = lore.length
            ? lore.map(_renderLoreRow).join('')
            : `<div class="inv-empty">Brak przedmiotów fabularnych</div>`;
    }

    _wireInventoryActions();
}

function _renderSlotCard(def, item) {
    if (!item) {
        return `
            <div class="inv-slot inv-slot--empty" data-slot="${def.key}">
                <div class="inv-slot__icon">${INV_ICONS[def.icon]}</div>
                <div class="inv-slot__type">${def.label}</div>
                <div class="inv-slot__name inv-slot__name--empty">—</div>
            </div>`;
    }
    return `
        <div class="inv-slot inv-slot--filled" data-slot="${def.key}" data-inventory-id="${item.id}">
            <div class="inv-slot__icon">${INV_ICONS[def.icon]}</div>
            <div class="inv-slot__type">${def.label}</div>
            <div class="inv-slot__name">${escapeHtml(item.label || item.key || '?')}</div>
            <button type="button" class="inv-slot__unequip" data-action="unequip" data-inventory-id="${item.id}">Zdejmij</button>
        </div>`;
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

    return `
        <div class="inv-row" data-inventory-id="${item.id}">
            <div class="inv-row__icon">${INV_ICONS[kind]}</div>
            <div class="inv-row__info">
                <div class="inv-row__name">${escapeHtml(item.label || item.key || '?')}${qty}</div>
            </div>
            ${action}
        </div>`;
}

function _renderLoreRow(item) {
    const qty = item.quantity > 1 ? `<span class="inv-row__qty">×${item.quantity}</span>` : '';
    const desc = item.description ? ` data-tooltip="${escapeHtml(item.description)}"` : '';
    const isNarrative = item.is_narrative || item.item_type === 'narrative';
    const dropBtn = isNarrative
        ? `<button class="inv-row__drop-btn" data-action="drop" data-inventory-id="${item.id}" title="Wyrzuć przedmiot">✕</button>`
        : '';
    return `
        <div class="inv-row" data-inventory-id="${item.id}"${desc}>
            <div class="inv-row__icon">${INV_ICONS.scroll}</div>
            <div class="inv-row__info">
                <div class="inv-row__name">${escapeHtml(item.label || item.key || '?')}${qty}</div>
                ${item.description ? `<div class="inv-row__desc">${escapeHtml(item.description)}</div>` : ''}
            </div>
            ${dropBtn}
        </div>`;
}

function _wireInventoryActions() {
    document.querySelectorAll('#tab-inventory [data-action]').forEach(btn => {
        if (btn.__wired) return;
        btn.__wired = true;
        btn.addEventListener('click', async () => {
            const action = btn.dataset.action;
            const id = parseInt(btn.dataset.inventoryId, 10);
            if (!id || !characterData?.id) return;
            btn.disabled = true;
            try {
                if (action === 'drop') {
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

async function loadJournalContent(forceRegenerate) {
    const { journalBody, journalEmpty, journalLoading, journalBanner } = elements;
    const cid = currentCampaignId;

    console.log('[Journal] loadJournalContent', { cid, forceRegenerate, currentUser });

    if (!cid) {
        console.log('[Journal] no campaign id, showing empty');
        showJournalEmpty();
        return;
    }

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

// Wound label — mirrors backend get_wound_label() in economy_service.py.
// Returns { label, tier, color } or null when HP > 75% (no label).
// Tiers map to CSS classes so styling is decoupled from numbers.
function getWoundLabel(currentHp, maxHp) {
    const hp = Math.max(0, Number(currentHp) || 0);
    const max = Math.max(1, Number(maxHp) || 1);
    const pct = (hp / max) * 100;
    if (pct >= 76) return null;
    if (pct >= 51) return { label: 'Ranny',             tier: 'minor',    color: '#ffc107' };
    if (pct >= 26) return { label: 'Ciężko Ranny',      tier: 'impaired', color: '#ff9800' };
    if (pct >= 11) return { label: 'Poważnie Ranny',    tier: 'desperate',color: '#f44336' };
    return            { label: 'Na Skraju Śmierci', tier: 'near_death',color: '#7f0000' };
}

// Render markup for a wound label, or empty string when above threshold.
function renderWoundLabelHTML(currentHp, maxHp) {
    const w = getWoundLabel(currentHp, maxHp);
    if (!w) return '';
    return `<div class="wound-label wound-label--${w.tier}" aria-label="${w.label}"><span class="wound-label__orn">❦</span><span class="wound-label__text">${w.label}</span><span class="wound-label__orn">❦</span></div>`;
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

    panel.addEventListener('touchstart', (e) => {
        startY = e.touches[0].clientY;
        dragging = true;
        panel.style.transition = 'none';
    }, { passive: true });

    panel.addEventListener('touchmove', (e) => {
        if (!dragging) return;
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
        const diff = currentY - startY;
        if (diff > 80) {
            panel.style.transform = '';
            closeFn();
        } else {
            panel.style.transform = '';
        }
        startY = 0;
        currentY = 0;
    });
}

function initSheetTabSwipe(panel) {
    if (!panel) return;
    const content = panel.querySelector('.sheet-panel__content');
    if (!content) return;

    const TAB_ORDER = ['stats', 'skills', 'inventory', 'appearance'];
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

        const activeTab = panel.querySelector('.sheet-tab--active');
        const currentIdx = TAB_ORDER.indexOf(activeTab?.dataset?.tab);
        if (currentIdx === -1) return;

        const nextIdx = dx < 0
            ? Math.min(currentIdx + 1, TAB_ORDER.length - 1)
            : Math.max(currentIdx - 1, 0);
        if (nextIdx === currentIdx) return;

        const targetTab = panel.querySelector(`.sheet-tab[data-tab="${TAB_ORDER[nextIdx]}"]`);
        targetTab?.click();
    }, { passive: true });
}

function updateAdminSettingsVisibility() {
    const isAdmin = currentUser?.is_admin === 1 || currentUser?.is_admin === true;
    const adminSection = document.getElementById('admin-settings-section');
    const adminDivider = document.getElementById('admin-settings-divider');

    if (adminSection) adminSection.style.display = isAdmin ? 'block' : 'none';
    if (adminDivider) adminDivider.style.display = isAdmin ? 'flex' : 'none';

    if (isAdmin) pollServiceHealth();
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
function showDeathScreen(characterName) {
    const deathScreen = document.getElementById('death-screen');
    const nameElement = document.getElementById('death-character-name');

    if (nameElement && characterName) {
        nameElement.textContent = characterName;
    }

    if (deathScreen) {
        deathScreen.hidden = false;
        document.body.style.overflow = 'hidden';
    }
}

function hideDeathScreen() {
    const deathScreen = document.getElementById('death-screen');
    if (deathScreen) {
        deathScreen.hidden = true;
        document.body.style.overflow = '';
    }
}

async function handleResurrect() {
    hideDeathScreen();
    showToast('Bohater został wskrzeszony!', 'success');
    // TODO: Call resurrection API when available
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
// Campaign Actions (Admin only)
// ============================================================================
async function handleResetCampaign() {
    if (!currentCampaignId) {
        showToast('Brak aktywnej kampanii', 'error');
        return;
    }

    const confirmed = confirm(
        'Zresetować kampanię?\n\n' +
        'Usunięte: historia czatu, aktywna walka, podsumowania AI.\n' +
        'Kampania i postać zostają.'
    );

    if (!confirmed) return;

    try {
        await apiRequest('POST', `/campaigns/${currentCampaignId}/reset`);
        showToast('Kampania zresetowana', 'success');
        closeSettings();
        // Reload chat
        elements.chatMessages.innerHTML = '';
    } catch (error) {
        console.error('[Admin] Reset campaign error:', error);
        showToast(error.message || 'Błąd resetowania kampanii', 'error');
    }
}

async function handleResetCharacter() {
    if (!characterData?.id) {
        showToast('Brak aktywnej postaci', 'error');
        return;
    }

    const confirmed = confirm(
        'Zresetować postać?\n\n' +
        'Przywraca stan jak po kreatorze.\n' +
        'Zachowane: imię, archetyp, historia.'
    );

    if (!confirmed) return;

    try {
        const response = await apiRequest('POST', `/characters/${characterData.id}/reset-progress`);
        characterData = { ...characterData, sheet_json: response.sheet_json };
        populateCharacterSheet(characterData);
        updateHeaderStats();
        showToast('Postać zresetowana', 'success');
        closeSettings();
    } catch (error) {
        console.error('[Admin] Reset character error:', error);
        showToast(error.message || 'Błąd resetowania postaci', 'error');
    }
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

// ============================================================================
// Event Listeners
// ============================================================================
// ── Fast custom tooltip (replaces slow native title= delay) ──────────────────
(function _initFastTooltip() {
    const tip = document.createElement('div');
    tip.id = 'fast-tooltip';
    tip.style.cssText = 'position:fixed;z-index:99999;background:#1a1208;border:1px solid #5a3a10;color:#d4c09a;font-size:0.72rem;line-height:1.45;padding:6px 10px;border-radius:6px;max-width:220px;pointer-events:none;display:none;box-shadow:0 4px 16px rgba(0,0,0,0.7);';
    document.body.appendChild(tip);

    document.addEventListener('mouseover', e => {
        const el = e.target.closest('[data-tooltip]');
        if (!el) return;
        tip.textContent = el.dataset.tooltip;
        tip.style.display = 'block';
    });
    document.addEventListener('mousemove', e => {
        if (tip.style.display === 'none') return;
        const x = e.clientX + 12, y = e.clientY + 12;
        const { innerWidth: W, innerHeight: H } = window;
        tip.style.left = (x + 230 > W ? x - 242 : x) + 'px';
        tip.style.top  = (y + 80 > H ? y - 70 : y) + 'px';
    });
    document.addEventListener('mouseout', e => {
        if (!e.target.closest('[data-tooltip]')) return;
        tip.style.display = 'none';
    });
    // Also hide on touch
    document.addEventListener('touchstart', () => { tip.style.display = 'none'; }, { passive: true });
})();

function initEventListeners() {
    // Login
    elements.loginForm?.addEventListener('submit', handleLogin);

    // Heroes
    elements.btnNewHero?.addEventListener('click', () => {
        currentHero = null;
        currentCampaignId = null;
        currentCampaign = null;
        characterData = null;
        startCharacterWizard();
    });
    elements.btnHeroesLogout?.addEventListener('click', handleLogout);

    // Campaigns
    elements.btnNewCampaign?.addEventListener('click', showNewCampaignScreen);
    elements.btnLogout?.addEventListener('click', handleLogout);

    // New Campaign
    elements.newCampaignForm?.addEventListener('submit', handleCreateCampaign);
    elements.btnNewCampaignBack?.addEventListener('click', () => showScreen('campaigns'));
    elements.campaignNameInput?.addEventListener('input', (e) => {
        elements.campaignNameCount.textContent = e.target.value.length;
    });

    // Suggestion chips
    document.querySelectorAll('.chip[data-value]').forEach(chip => {
        chip.addEventListener('click', () => {
            elements.campaignNameInput.value = chip.dataset.value;
            elements.campaignNameCount.textContent = chip.dataset.value.length;
        });
    });

    // Character Wizard
    elements.btnWizardPrev?.addEventListener('click', handleWizardPrev);
    elements.btnWizardNext?.addEventListener('click', handleWizardNext);
    elements.btnWizardBack?.addEventListener('click', () => {
        if (currentCampaignId) {
            loadCampaigns();
            showScreen('campaigns');
        } else {
            loadHeroes();
            showScreen('heroes');
        }
    });

    // Game
    elements.btnOpenSheet?.addEventListener('click', toggleCharacterSheet);
    elements.btnOpenSettings?.addEventListener('click', toggleSettings);
    elements.btnOpenJournal?.addEventListener('click', toggleJournal);

    // Combat
    elements.btnCombatAttack?.addEventListener('click', handleCombatAttack);
    elements.btnCombatFlee?.addEventListener('click', handleCombatFlee);
    elements.btnCombatMove?.addEventListener('click', handleCombatMove);
    document.getElementById('combat-spell-btn')?.addEventListener('click', openSpellPicker);
    document.getElementById('spell-picker-close')?.addEventListener('click', closeSpellPicker);
    document.getElementById('spell-picker-overlay')?.addEventListener('click', e => {
        if (e.target === document.getElementById('spell-picker-overlay')) closeSpellPicker();
    });
    elements.combatEndBtn?.addEventListener('click', hideCombatEndOverlay);
    elements.btnSend?.addEventListener('click', handleSendMessage);
    elements.chatInput?.addEventListener('keypress', handleKeyPress);
    elements.chatInput?.addEventListener('input', updateCharCounter);
    initSlashAutocomplete(elements.chatInput);

    // Sheet tabs
    elements.sheetTabs.forEach(tab => {
        tab.addEventListener('click', handleSheetTabClick);
    });

    // Overlay
    elements.overlay?.addEventListener('click', handleOverlayClick);

    // Close settings panel
    document.getElementById('settings-close-btn')?.addEventListener('click', closeSettings);

    // Swipe down to close panels
    initPanelSwipeDown(elements.settingsPanel, closeSettings);
    initPanelSwipeDown(elements.sheetPanel, closeCharacterSheet);
    initPanelSwipeDown(elements.journalPanel, closeJournal);

    // Swipe left/right to switch sheet tabs
    initSheetTabSwipe(elements.sheetPanel);

    // World map panel
    initWorldMap();
    initDungeon();

    // Journal regen
    elements.btnJournalRegen?.addEventListener('click', () => loadJournalContent(true));

    // Go to campaigns from settings
    elements.btnGoToCampaigns?.addEventListener('click', handleGoToCampaigns);

    // Go to heroes (Postacie) from settings
    document.getElementById('go-to-heroes-btn')?.addEventListener('click', async () => {
        closeSettings();
        currentHero = null;
        try { sessionStorage.removeItem('aigm_active_session'); } catch {}
        await loadHeroes();
        showScreen('heroes');
    });

    // Admin actions (C04-C06)
    elements.btnResetCampaign?.addEventListener('click', handleResetCampaign);
    elements.btnResetCharacter?.addEventListener('click', handleResetCharacter);

    // Death screen test button
    document.getElementById('test-death-btn')?.addEventListener('click', () => {
        closeSettings();
        showDeathScreen(characterData?.name || 'Bohater');
    });

    // Death screen buttons
    document.getElementById('resurrect-btn')?.addEventListener('click', handleResurrect);
    document.getElementById('death-return-btn')?.addEventListener('click', handleDeathReturn);

    // Settings font controls
    initFontSettings();
    initBubblePrefs();
    initSettingsFolds();
    initVoiceSettings();
}

function initSettingsFolds() {
    document.querySelectorAll('.settings-group__header--toggle').forEach(header => {
        const foldId = header.dataset.fold;
        const fold = document.getElementById(foldId);
        if (!fold) return;

        const chevron = header.querySelector('.settings-group__chevron');
        const storageKey = `settings_fold_${foldId}`;
        const isOpen = localStorage.getItem(storageKey) === 'open';

        if (isOpen) {
            fold.removeAttribute('hidden');
            if (chevron) chevron.classList.add('settings-group__chevron--open');
        }

        header.addEventListener('click', () => {
            const open = fold.hasAttribute('hidden');
            fold.toggleAttribute('hidden', !open);
            if (chevron) chevron.classList.toggle('settings-group__chevron--open', open);
            localStorage.setItem(storageKey, open ? 'open' : 'closed');
        });
    });
}

function initFontSettings() {
    const fontSizeSlider = document.getElementById('font-size');
    const fontSizeValue = document.getElementById('font-size-value');
    const previewText = document.getElementById('settings-preview-text');
    const fontSelect = document.getElementById('font-select');

    const fontFamilies = {
        'system': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        'serif': 'Georgia, "Times New Roman", serif',
        'lora': '"Lora", Georgia, serif',
        'playfair': '"Playfair Display", Georgia, serif',
        'imfell': '"IM Fell English", Georgia, serif',
        'uncial': '"Uncial Antiqua", Georgia, serif',
        'cinzel': '"Cinzel", Georgia, serif'
    };

    // Load saved preferences
    const savedSize = localStorage.getItem('chatFontSize') || '16';
    const savedFont = localStorage.getItem('chatFontFamily') || 'system';

    if (fontSizeSlider) fontSizeSlider.value = savedSize;
    if (fontSizeValue) fontSizeValue.textContent = savedSize + 'px';
    if (fontSelect) fontSelect.value = savedFont;

    applyFontSettings(savedSize, fontFamilies[savedFont] || fontFamilies.system);

    fontSizeSlider?.addEventListener('input', (e) => {
        const size = e.target.value;
        if (fontSizeValue) fontSizeValue.textContent = size + 'px';
        applyFontSettings(size, fontFamilies[fontSelect?.value] || fontFamilies.system);
        localStorage.setItem('chatFontSize', size);
    });

    fontSelect?.addEventListener('change', (e) => {
        const family = fontFamilies[e.target.value] || fontFamilies.system;
        applyFontSettings(fontSizeSlider?.value || '16', family);
        localStorage.setItem('chatFontFamily', e.target.value);
    });

    function applyFontSettings(size, family) {
        if (previewText) {
            previewText.style.fontSize = size + 'px';
            previewText.style.fontFamily = family;
        }
        // Apply to chat messages
        document.querySelectorAll('.chat-bubble__content').forEach(el => {
            el.style.fontSize = size + 'px';
            el.style.fontFamily = family;
        });
        // Store for new messages
        document.documentElement.style.setProperty('--chat-font-size', size + 'px');
        document.documentElement.style.setProperty('--chat-font-family', family);
    }
}

function initBubblePrefs() {
    applyBubblePrefs();

    const toggleName = document.getElementById('bubble-toggle-name');
    const toggleTurn = document.getElementById('bubble-toggle-turn');
    const toggleDatetime = document.getElementById('bubble-toggle-datetime');

    if (toggleName) {
        toggleName.checked = bubblePrefs.showName;
        toggleName.addEventListener('change', e => {
            bubblePrefs.showName = e.target.checked;
            localStorage.setItem('bubble_name', String(e.target.checked));
            applyBubblePrefs();
        });
    }
    if (toggleTurn) {
        toggleTurn.checked = bubblePrefs.showTurn;
        toggleTurn.addEventListener('change', e => {
            bubblePrefs.showTurn = e.target.checked;
            localStorage.setItem('bubble_turn', String(e.target.checked));
            applyBubblePrefs();
        });
    }
    if (toggleDatetime) {
        toggleDatetime.checked = bubblePrefs.showDateTime;
        toggleDatetime.addEventListener('change', e => {
            bubblePrefs.showDateTime = e.target.checked;
            localStorage.setItem('bubble_datetime', String(e.target.checked));
            applyBubblePrefs();
        });
    }

    const toggleDebug = document.getElementById('debug-toggle');
    if (toggleDebug) {
        toggleDebug.checked = debugMode;
        toggleDebug.addEventListener('change', e => {
            debugMode = e.target.checked;
            localStorage.setItem('aigm_debug', debugMode ? '1' : '0');
            document.querySelectorAll('.debug-block').forEach(el => {
                el.style.display = debugMode ? 'block' : 'none';
            });
            // Re-render debug id chips (requires reload — hint user)
            if (debugMode) showToast('Debug mode ON — odśwież stronę aby zobaczyć ID tur', 'info', 3000);
        });
    }

    // Debug log copy
    let _debugTurnsN = 3;
    document.querySelectorAll('.debug-turns-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.debug-turns-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _debugTurnsN = parseInt(btn.dataset.n);
        });
    });

    document.getElementById('debug-copy-btn')?.addEventListener('click', async () => {
        if (!currentCampaignId) { showToast('Brak aktywnej kampanii', 'error'); return; }
        const btn = document.getElementById('debug-copy-btn');
        const preview = document.getElementById('debug-log-preview');
        btn.disabled = true; btn.textContent = 'Ładuję…';
        try {
            const resp = await apiRequest('GET', `/campaigns/${currentCampaignId}/turns/debug-log?limit=${_debugTurnsN}`);
            const humanText = resp.human_text || '';
            const jsonBlock = '\n\n```json\n' + JSON.stringify({campaign_id: resp.campaign_id, hero: resp.hero, turns: resp.turns}, null, 2) + '\n```';
            const full = humanText + jsonBlock;
            if (preview) preview.value = full.slice(0, 800) + (full.length > 800 ? '\n...[skrócono]' : '');
            await navigator.clipboard.writeText(full);
            showToast('Log skopiowany do schowka ✓', 'success', 2500);
        } catch (e) {
            showToast('Błąd: ' + (e.message || '?'), 'error');
        } finally {
            btn.disabled = false; btn.textContent = 'Kopiuj';
        }
    });
}

function initVoiceSettings() {
    const ttsToggle = document.getElementById('tts-toggle');
    const sttToggle = document.getElementById('stt-toggle');
    const statusHint = document.getElementById('voice-settings-status');
    const voiceStatusBar = document.getElementById('voice-status');

    window.addEventListener('voice-debug-status', (e) => {
        const text = e.detail?.text || '';
        if (voiceStatusBar) {
            voiceStatusBar.textContent = text;
            voiceStatusBar.hidden = !text;
        }
        if (statusHint) statusHint.textContent = text || 'Głos gotowy';
    });

    // Keep checkbox in sync whenever voice.js changes TTS state.
    window.addEventListener('voice-tts-state', (e) => {
        if (ttsToggle) ttsToggle.checked = !!e.detail?.enabled;
    });

    // Show/hide TTS reading overlay in the composer.
    const ttsReadingOverlay = document.getElementById('tts-reading-overlay');
    if (ttsReadingOverlay) {
        ttsReadingOverlay.addEventListener('click', () => window.voiceUI?.stopPlayback?.());
    }
    window.addEventListener('voice-tts-playing', (e) => {
        if (ttsReadingOverlay) ttsReadingOverlay.hidden = !e.detail?.playing;
    });

    // TTS checkbox — delegate to voice.js which owns the state machine.
    if (ttsToggle) {
        ttsToggle.addEventListener('change', () => {
            window.voiceUI?.setTtsEnabled?.(ttsToggle.checked, { unlock: ttsToggle.checked });
        });
    }

    // STT checkbox — use the shared toggleStt that voice.js exposes after init.
    if (sttToggle) {
        sttToggle.addEventListener('change', () => {
            if (typeof window.__voiceToggleStt === 'function') {
                void window.__voiceToggleStt();
            }
        });
    }

    // Sync initial checkbox state — voice.js init() already read localStorage.
    if (ttsToggle) ttsToggle.checked = window.voiceUI?.isTtsEnabled?.() ?? false;
}

function initSlashAutocomplete(inputEl) {
    if (!inputEl) return;
    const popup = document.createElement('div');
    popup.className = 'slash-popup';
    document.body.appendChild(popup);

    let active = false;
    let matches = [];
    let hi = 0;

    function hide() {
        active = false;
        matches = [];
        popup.classList.remove('slash-popup--open');
    }

    function getToken(val, pos) {
        const before = val.slice(0, pos);
        const idx = before.lastIndexOf('/');
        if (idx === -1) return null;
        const prev = idx === 0 ? ' ' : before[idx - 1];
        if (prev !== ' ' && prev !== '\n') return null;
        const token = before.slice(idx + 1);

        // /admin spans multiple words — treat the whole tail as the query
        if (/^admin(\s|$)/i.test(token)) {
            return { idx, query: token, isAdmin: true };
        }
        if (/\s/.test(token)) return null;
        return { idx, query: token, isAdmin: false };
    }

    function render() {
        popup.innerHTML = matches.map((c, i) =>
            `<div class="slash-popup-item${i === hi ? ' slash-popup-item--active' : ''}" data-i="${i}">` +
            `<span class="slash-popup-cmd">${escapeHtml(c.cmd)}</span>` +
            `<span class="slash-popup-desc">${escapeHtml(c.desc)}</span></div>`
        ).join('');
        popup.querySelectorAll('.slash-popup-item').forEach(el => {
            el.addEventListener('mousedown', e => e.preventDefault());
            el.addEventListener('click', () => pick(matches[+el.dataset.i]));
        });
    }

    function pick(cmd) {
        const val = inputEl.value;
        const pos = inputEl.selectionStart ?? val.length;
        const ctx = getToken(val, pos);
        if (!ctx) { hide(); return; }
        // If the admin command is a leaf (has placeholder hint in cmd.desc), keep the popup ready for arg
        const insert = cmd.cmd + ' ';
        inputEl.value = val.slice(0, ctx.idx) + insert + val.slice(pos);
        const caret = ctx.idx + insert.length;
        inputEl.setSelectionRange(caret, caret);
        inputEl.focus();
        // For /admin pick, re-sync to show subcommand suggestions
        if (cmd.cmd.startsWith('/admin')) {
            setTimeout(sync, 0);
        } else {
            hide();
        }
    }

    let _catalogSeq = 0;

    function sync() {
        const val = inputEl.value;
        const pos = inputEl.selectionStart ?? val.length;
        const ctx = getToken(val, pos);
        if (!ctx) { hide(); return; }
        const q = ctx.query.toLowerCase();

        let found;
        if (ctx.isAdmin) {
            if (!playerIsAdmin()) { hide(); return; }
            const afterAdmin = ctx.query.replace(/^admin\s*/i, '');

            // If we're in "add item|weapon ..." context, fetch catalog suggestions async
            const catalogCtx = _adminCatalogContext(afterAdmin);
            if (catalogCtx) {
                _catalogSeq += 1;
                const seq = _catalogSeq;
                fetchAdminCatalogSuggestions(afterAdmin).then(rows => {
                    if (seq !== _catalogSeq) return; // outdated
                    if (!rows || !rows.length) {
                        // fallback: tree suggestions
                        matches = getAdminSuggestions(afterAdmin);
                    } else {
                        matches = rows;
                    }
                    if (!matches.length) { hide(); return; }
                    hi = 0;
                    showPopup();
                });
                return;
            }

            found = getAdminSuggestions(afterAdmin);
        } else {
            found = SLASH_COMMANDS
                .filter(c => !c.adminOnly || playerIsAdmin())
                .filter(c => c.cmd.slice(1).startsWith(q) || (q.length > 1 && c.desc.toLowerCase().includes(q)));
        }
        if (!found.length) { hide(); return; }
        matches = found;
        hi = Math.min(hi, matches.length - 1);
        showPopup();
    }

    function showPopup() {
        if (!matches.length) { hide(); return; }
        const rect = inputEl.getBoundingClientRect();
        popup.style.left = rect.left + 'px';
        popup.style.width = rect.width + 'px';
        popup.style.bottom = (window.innerHeight - rect.top + 6) + 'px';
        render();
        popup.classList.add('slash-popup--open');
        active = true;
    }

    inputEl.addEventListener('input', () => { hi = 0; sync(); });
    inputEl.addEventListener('click', sync);
    inputEl.addEventListener('keyup', e => { if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') sync(); });
    inputEl.addEventListener('keydown', e => {
        if (!active || !matches.length) return;
        if (e.key === 'Escape') { e.preventDefault(); hide(); return; }
        if (e.key === 'ArrowDown') { e.preventDefault(); hi = (hi + 1) % matches.length; render(); return; }
        if (e.key === 'ArrowUp') { e.preventDefault(); hi = (hi - 1 + matches.length) % matches.length; render(); return; }
        if ((e.key === 'Enter' || e.key === 'Tab') && matches[hi]) { e.preventDefault(); pick(matches[hi]); }
    }, true);
    document.addEventListener('click', e => { if (!popup.contains(e.target) && e.target !== inputEl) hide(); });
}

// ============================================================================
// Initialization
// ============================================================================
// Returns true if session was restored (caller should return early)
async function tryRestoreSession() {
    try {
        const savedHeroId = localStorage.getItem('aigm_hero_id');
        const savedCampaignId = localStorage.getItem('aigm_campaign_id');
        if (!savedHeroId) return false;

        const heroResp = await apiRequest('GET', `/characters/${savedHeroId}`);
        const restored = heroResp.character || heroResp;
        if (!restored?.id || Number(restored.user_id) !== Number(currentUser?.id)) return false;

        currentHero = restored;
        if (elements.welcomeUser) elements.welcomeUser.textContent = `Bohater: ${restored.name}`;

        // Restore to game screen if hero had an active campaign
        const campId = savedCampaignId || restored.campaign_id;
        if (campId && (restored.status === 'in_campaign' || savedCampaignId)) {
            const chars = await apiRequest('GET', `/campaigns/${campId}/characters`);
            const myChar = (chars.characters || []).find(c => c.id === restored.id);
            if (myChar) {
                characterData = myChar;
                currentCampaignId = campId;
                const camp = await apiRequest('GET', `/campaigns/${campId}`);
                currentCampaign = camp;
                await enterGame(camp);
                // Restore dungeon HUD if dungeon campaign
                if (camp.mode === 'dungeon') {
                    try {
                        const runResp = await apiRequest('GET', `/campaigns/${campId}/dungeon-run`);
                        if (runResp.dungeon_run && !runResp.dungeon_run.completed && !runResp.dungeon_run.failed) {
                            _activeDungeonRun = runResp.dungeon_run;
                            _dungeonCampaignId = campId;
                            updateDungeonHUD();
                            showDungeonHUD(true);
                            renderCurrentRoom();
                        }
                    } catch {}
                }
                return true;
            }
        }

        // Hero found but no active campaign — go to campaign chooser
        await loadCampaigns();
        showScreen('campaigns');
        return true;
    } catch (e) {
        console.warn('[Restore] Failed:', e);
        return false;
    }
}

async function init() {
    initEventListeners();

    if (checkAuth()) {
        updateAdminSettingsVisibility();
        const displayName = currentUser.display_name || currentUser.username || '';
        if (elements.heroesWelcome) elements.heroesWelcome.textContent = `Witaj, ${displayName}`;
        if (elements.welcomeUser) elements.welcomeUser.textContent = `Witaj, ${displayName}`;
        await loadHeroes();
        if (await tryRestoreSession()) return;
        showScreen('heroes');
    } else {
        showScreen('login');
    }
}

async function loadBgSettings() {
    try {
        const resp = await fetch(`${API_BASE}/ui/backgrounds`);
        if (!resp.ok) return;
        const data = await resp.json();
        const bgs = data.backgrounds || {};
        for (const [screen, url] of Object.entries(bgs)) {
            if (url) {
                document.documentElement.style.setProperty(
                    `--bg-screen-${screen}`,
                    `url("${url}")`
                );
            }
        }
    } catch (_e) {}
}

document.addEventListener('DOMContentLoaded', () => {
    loadBgSettings();
    init();
});

// ── World Map Panel — Task 43 ─────────────────────────────────────────────────

const _wmap = {
  panel:   null,
  svg:     null,
  confirm: null,
  zoom: 1.4,
  pan:  { x: 180, y: 200 },
  hexTypes: {},
  hexes: [],
  teleports: [],
  currentHex: null,
  pendingTravel: null,   // { q, r, label }
  _ds: null,             // drag state
};

const _WH = 32; // hex size px

function _wmHexToPixel(q, r) {
  return { x: _WH * 1.5 * q, y: _WH * (Math.sqrt(3)/2 * q + Math.sqrt(3) * r) };
}

function _wmCorners(cx, cy, size) {
  return Array.from({length:6}, (_,i) => {
    const a = Math.PI / 180 * 60 * i;
    return `${cx + size * Math.cos(a)},${cy + size * Math.sin(a)}`;
  }).join(' ');
}

function _wmWorld(wx, wy) {
  return { x: wx * _wmap.zoom + _wmap.pan.x, y: wy * _wmap.zoom + _wmap.pan.y };
}

function _wmRender() {
  const svg = _wmap.svg;
  if (!svg) return;
  let html = '';
  const rz = _WH * _wmap.zoom;

  for (const hex of _wmap.hexes) {
    const {x, y} = _wmHexToPixel(hex.q, hex.r);
    const {x:sx, y:sy} = _wmWorld(x, y);
    const discovered = hex.status === 'discovered';
    const isCurrent = _wmap.currentHex && _wmap.currentHex.q === hex.q && _wmap.currentHex.r === hex.r;
    const cfg = _wmap.hexTypes[hex.hex_type] || {};

    if (discovered) {
      const fill = cfg.map_color || '#4a6a4a';
      const stroke = isCurrent ? '#f0c040' : '#1a1612';
      const sw = isCurrent ? 2.5 : 0.8;
      html += `<polygon class="wm-hex" data-q="${hex.q}" data-r="${hex.r}"
        points="${_wmCorners(sx, sy, rz-1)}"
        fill="${fill}" stroke="${stroke}" stroke-width="${sw}" style="cursor:pointer"/>`;
      if (_wmap.zoom >= 0.9 && cfg.map_icon)
        html += `<text x="${sx}" y="${sy-rz*0.05}" text-anchor="middle"
          font-size="${Math.max(10, 13*_wmap.zoom)}" style="pointer-events:none">${cfg.map_icon}</text>`;
      if (_wmap.zoom >= 1.0 && hex.label)
        html += `<text x="${sx}" y="${sy+rz*0.38}" text-anchor="middle"
          font-size="${Math.max(7, 9*_wmap.zoom)}" fill="#c8b87a" style="pointer-events:none">${escapeHtml(hex.label.slice(0,14))}</text>`;
      if (isCurrent)
        html += `<text x="${sx}" y="${sy-rz*0.52}" text-anchor="middle"
          font-size="${Math.max(11, 14*_wmap.zoom)}" style="pointer-events:none">📍</text>`;
    } else {
      // Outline: unvisited adjacent hex
      html += `<polygon class="wm-hex wm-hex--outline" data-q="${hex.q}" data-r="${hex.r}"
        points="${_wmCorners(sx, sy, rz-1)}"
        fill="transparent" stroke="#2a2218" stroke-width="0.6" stroke-dasharray="3,2"
        style="cursor:pointer"/>`;
    }
  }

  // Teleport connections
  for (const t of _wmap.teleports) {
    const p1 = _wmHexToPixel(t.from_q, t.from_r), p2 = _wmHexToPixel(t.to_q, t.to_r);
    const s1 = _wmWorld(p1.x, p1.y), s2 = _wmWorld(p2.x, p2.y);
    const mx = (s1.x+s2.x)/2, my = (s1.y+s2.y)/2 - 20*_wmap.zoom;
    const col = t.travel_type === 'boat' ? '#3a8aaa' : '#8a3aaa';
    html += `<path d="M${s1.x},${s1.y} Q${mx},${my} ${s2.x},${s2.y}"
      fill="none" stroke="${col}" stroke-width="${1.2*_wmap.zoom}" stroke-dasharray="4,2"
      style="pointer-events:none"/>`;
  }

  svg.innerHTML = html;
  svg.querySelectorAll('.wm-hex').forEach(el => {
    el.addEventListener('click', _wmOnHexClick);
  });
}

function _wmOnHexClick(e) {
  const q = parseInt(e.target.dataset.q), r = parseInt(e.target.dataset.r);
  const hex = _wmap.hexes.find(h => h.q === q && h.r === r);
  if (!hex) return;

  const label = hex.label || `(${q},${r})`;
  const cfg = _wmap.hexTypes[hex.hex_type] || {};
  const typeName = cfg.label || hex.hex_type || '';
  const info = hex.status === 'discovered'
    ? typeName
    : `${typeName} — nieznany teren`;

  _wmap.pendingTravel = { q, r, label };
  const confirm = _wmap.confirm;
  confirm.querySelector('#wmap-confirm-title').textContent = `Podróżujesz do ${label}`;
  confirm.querySelector('#wmap-confirm-info').textContent = info;
  confirm.removeAttribute('hidden');
}

async function _wmExecuteTravel() {
  const t = _wmap.pendingTravel;
  if (!t) return;
  _wmap.confirm.setAttribute('hidden', '');
  _wmClose();

  // Dispatch hex travel to turn pipeline
  if (!currentCampaignId || !characterData?.id) return;
  try {
    const response = await apiRequest('POST', `/campaigns/${currentCampaignId}/hex-travel`, {
      character_id: characterData.id,
      destination_q: t.q,
      destination_r: t.r,
    });

    // T2/T5 — backend advances clock during hex-travel and returns the new
    // state on `response.clock`. Re-render the header chip.
    if (response.clock) renderClock(response.clock);

    const enc = response.encounter;
    const hours = response.total_hours || 0;
    const arrivedHex = response.arrived_hex || {};
    const arrivedData = response.hex_data || {};

    // Build readable destination — never show coordinates
    const hexTypeName = (_wmap.hexTypes?.[arrivedData.hex_type]?.label) || arrivedData.hex_type || '';
    // Only use a name if it's a real label, not a fallback coord string
    const rawLabel = t.label && !t.label.match(/^\([-\d]+,[-\d]+\)$/) ? t.label : null;
    const destLabel = rawLabel || arrivedData.label || null;

    // Travel animation: brief walking indicator then message
    const travelAnim = document.createElement('div');
    travelAnim.className = 'chat-bubble chat-bubble--system';
    travelAnim.innerHTML = `<div class="chat-bubble__content" style="display:flex;align-items:center;gap:8px"><span style="animation:pulse 0.8s infinite">🚶</span> <em>Podróżujesz…</em></div>`;
    elements.chatMessages.appendChild(travelAnim);
    scrollToBottom();
    await new Promise(r => setTimeout(r, 900));
    travelAnim.remove();

    // Arrival message
    let prose;
    if (hours > 0) {
      const hStr = Number.isInteger(hours) ? `${hours}` : hours.toFixed(1);
      const hWord = hours === 1 ? 'godzinę' : (hours < 5 ? 'godziny' : 'godzin');
      if (destLabel) {
        prose = `Dotarłeś do <strong>${escapeHtml(destLabel)}</strong>. Droga zajęła ${hStr} ${hWord}.`;
      } else if (hexTypeName) {
        prose = `Wkraczasz na teren — ${escapeHtml(hexTypeName)}. Droga zajęła ${hStr} ${hWord}.`;
      } else {
        prose = `Dotarłeś do celu. Droga zajęła ${hStr} ${hWord}.`;
      }
    } else {
      prose = destLabel ? `Jesteś w ${escapeHtml(destLabel)}.` : 'Przybyłeś na miejsce.';
    }
    if (arrivedData.atmosphere) prose += ` <em>${escapeHtml(arrivedData.atmosphere)}</em>`;
    if (enc) prose += `<br><strong>Na drodze natykasz się na wroga!</strong>`;

    const travelBubble = document.createElement('div');
    travelBubble.className = 'chat-bubble chat-bubble--travel';
    travelBubble.innerHTML = prose;
    elements.chatMessages.appendChild(travelBubble);

    // Update current hex on map
    if (arrivedHex.q !== undefined) {
      _wmap.currentHex = arrivedHex;
      if (!_wmap.panel.hasAttribute('hidden')) _wmRender();
    }

    // If encounter → trigger combat via turn API (narrator will add [COMBAT_START:key])
    if (enc?.enemy_key) {
      setTimeout(async () => {
        try {
          const typingIndicator = showTypingIndicator();
          const combatResponse = await apiRequest('POST', `/campaigns/${currentCampaignId}/turns`, {
            text: `Spotykam ${enc.enemy_key} na drodze! Przygotowuję się do walki!`,
            character_id: characterData.id,
          });
          typingIndicator.remove();
          const gmText = combatResponse.prose
            || combatResponse.result?.message
            || combatResponse.assistant_text || '';
          if (gmText) {
            const { narrative: gmContent } = parseGmFull(gmText);
            if (gmContent) appendMessage({ role: 'assistant', content: gmContent, created_at: new Date() });
          }
          if (combatResponse.skill_test_pending) showSkillTestPopup(combatResponse.skill_test_pending);
          await pollCombatState();
          scrollToBottom();
        } catch (err) {
          console.warn('Encounter combat trigger failed:', err);
        }
      }, 600);
    }

    await refreshCharacterData();
    await pollCombatState();
    scrollToBottom();
  } catch (err) {
    showToast(err.message || 'Błąd podróży', 'error');
  }
}

async function _wmOpen() {
  if (!currentCampaignId || !characterData?.id) {
    showToast('Wybierz postać aby otworzyć mapę.', 'info'); return;
  }
  _wmap.panel.removeAttribute('hidden');
  _wmap.panel.style.transform = 'translateX(0)';

  try {
    const data = await apiRequest('GET', `/campaigns/${currentCampaignId}/world-map?character_id=${characterData.id}`);
    _wmap.hexes = data.hexes || [];
    _wmap.teleports = data.teleport_connections || [];
    _wmap.currentHex = data.current_hex;
    _wmap.hexTypes = data.hex_types || {};

    // Center on discovered hexes
    const disc = _wmap.hexes.filter(h => h.status === 'discovered');
    if (disc.length) {
      const pixels = disc.map(h => _wmHexToPixel(h.q, h.r));
      const cx = pixels.reduce((s,p)=>s+p.x,0)/pixels.length;
      const cy = pixels.reduce((s,p)=>s+p.y,0)/pixels.length;
      const rect = _wmap.svg.getBoundingClientRect();
      _wmap.pan = { x: (rect.width||360)/2 - cx*_wmap.zoom, y: (rect.height||500)/2 - cy*_wmap.zoom };
    }
    _wmRender();
  } catch (err) {
    showToast(err.message || 'Błąd ładowania mapy', 'error');
  }
}

function _wmClose() {
  _wmap.panel.style.transform = 'translateX(100%)';
  setTimeout(() => _wmap.panel.setAttribute('hidden', ''), 280);
  _wmap.confirm.setAttribute('hidden', '');
  _wmap.pendingTravel = null;
}

function initWorldMap() {
  _wmap.panel   = document.getElementById('world-map-panel');
  _wmap.svg     = document.getElementById('wmap-svg');
  _wmap.confirm = document.getElementById('wmap-confirm');
  if (!_wmap.panel) return;

  document.getElementById('open-map-btn')?.addEventListener('click', _wmOpen);
  document.getElementById('wmap-close-btn')?.addEventListener('click', _wmClose);

  // Swipe right on map panel to close (mobile)
  let _swipeStartX = 0;
  _wmap.panel.addEventListener('touchstart', e => { _swipeStartX = e.touches[0].clientX; }, { passive: true });
  _wmap.panel.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - _swipeStartX;
    if (dx > 60) _wmClose(); // swipe right 60px+ → close
  }, { passive: true });
  document.getElementById('wmap-btn-go')?.addEventListener('click', _wmExecuteTravel);
  document.getElementById('wmap-btn-cancel')?.addEventListener('click', () => {
    _wmap.confirm.setAttribute('hidden', '');
    _wmap.pendingTravel = null;
  });

  // Zoom
  _wmap.svg.addEventListener('wheel', e => {
    e.preventDefault();
    const r = _wmap.svg.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const f = e.deltaY < 0 ? 1.15 : 0.87;
    const nz = Math.max(0.4, Math.min(5, _wmap.zoom * f));
    _wmap.pan.x = mx - (mx - _wmap.pan.x) * (nz / _wmap.zoom);
    _wmap.pan.y = my - (my - _wmap.pan.y) * (nz / _wmap.zoom);
    _wmap.zoom = nz;
    _wmRender();
  }, { passive: false });

  // Pan (left-click drag)
  _wmap.svg.addEventListener('mousedown', e => {
    if (e.button === 0) _wmap._ds = { x: e.clientX - _wmap.pan.x, y: e.clientY - _wmap.pan.y };
  });
  window.addEventListener('mousemove', e => {
    if (_wmap._ds) { _wmap.pan = { x: e.clientX - _wmap._ds.x, y: e.clientY - _wmap._ds.y }; _wmRender(); }
  });
  window.addEventListener('mouseup', () => { _wmap._ds = null; });
}

// ── Spell Picker (Scholar combat) ─────────────────────────────────────────────

let _cachedSpells = null;

async function openSpellPicker() {
    if (!combatActive || lastCombatState?.current_turn !== 'player') {
        setCombatMsg('Nie twoja tura.', true); return;
    }
    const overlay = document.getElementById('spell-picker-overlay');
    const list = document.getElementById('spell-picker-list');
    const manaEl = document.getElementById('spell-picker-mana');
    if (!overlay) return;

    const sheet = (() => { const s = characterData?.sheet_json || characterData || {}; return typeof s === 'string' ? JSON.parse(s) : s; })();
    const mana = sheet.current_mana ?? 0;
    const maxMana = sheet.max_mana ?? 0;
    if (manaEl) manaEl.textContent = `🔮 ${mana} / ${maxMana}`;

    overlay.removeAttribute('hidden');
    list.innerHTML = '<div style="padding:12px;color:#888;font-size:0.8rem">Ładowanie zaklęć…</div>';

    try {
        if (!_cachedSpells || _cachedSpells._charId !== characterData?.id) {
            const resp = await apiRequest('GET', `/characters/${characterData.id}/spells`);
            _cachedSpells = resp.spells || [];
            _cachedSpells._charId = characterData.id;
        }
        const spells = _cachedSpells;
        if (!spells.length) {
            list.innerHTML = '<div style="padding:12px;color:#888;font-size:0.8rem">Brak wyuczonych zaklęć.</div>';
            return;
        }
        const TYPE_ICONS = { attack:'⚔', heal:'💚', defense:'🛡', effect:'✨', attack_aoe:'💥' };
        list.innerHTML = spells.map(s => {
            const canCast = mana >= (s.mana_cost || 2);
            return `<button class="spell-pick-btn${canCast ? '' : ' spell-pick-btn--nomana'}"
                data-spell-key="${s.spell_key}" ${canCast ? '' : 'disabled'}>
                <span class="spell-pick-icon">${TYPE_ICONS[s.spell_type] || '✨'}</span>
                <span class="spell-pick-name">${escapeHtml(s.label || s.spell_key)}</span>
                <span class="spell-pick-cost">🔮 ${s.mana_cost || 2}</span>
                ${s.damage_die ? `<span class="spell-pick-die">⚔ ${s.damage_die}</span>` : ''}
                ${s.heal_die ? `<span class="spell-pick-die heal">💚 ${s.heal_die}</span>` : ''}
            </button>`;
        }).join('');

        list.querySelectorAll('.spell-pick-btn:not(:disabled)').forEach(btn => {
            btn.addEventListener('click', () => {
                closeSpellPicker();
                handleCombatSpellAttack(btn.dataset.spellKey);
            });
        });
    } catch {
        list.innerHTML = '<div style="padding:12px;color:#f87171;font-size:0.8rem">Błąd ładowania zaklęć.</div>';
    }
}

function closeSpellPicker() {
    document.getElementById('spell-picker-overlay')?.setAttribute('hidden', '');
}

async function handleCombatSpellAttack(spellKey) {
    if (!combatActive || !currentCampaignId || combatBusy) return;
    combatBusy = true;
    elements.btnCombatAttack.disabled = true;
    document.getElementById('combat-spell-btn').disabled = true;
    elements.btnCombatFlee.disabled = true;
    setCombatMsg(`Rzucam zaklęcie…`);

    try {
        const diceResp = await fetch('/api/gm/dice', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dice: '1d20' })
        });
        const diceData = await diceResp.json();
        const d20 = Number(diceData.total ?? 0);

        const target = pickEnemyTarget(lastCombatState);
        const body = { raw_d20: d20, attacker: 'player', spell_key: spellKey };
        if (target?.enemy_key) body.enemy_key = String(target.enemy_key);
        if (target?.id) body.target_id = String(target.id);

        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/resolve-attack`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);

        _cachedSpells = null; // Invalidate cache (mana changed)
        await _handleCombatAttackResult(data);
    } catch (err) {
        setCombatMsg(err.message || 'Błąd zaklęcia.', true);
        combatBusy = false;
        elements.btnCombatAttack.disabled = false;
        document.getElementById('combat-spell-btn').disabled = false;
        elements.btnCombatFlee.disabled = false;
    }
}

// ── Dungeon System ────────────────────────────────────────────────────────────

let _activeDungeonRun = null;
let _dungeonCampaignId = null;

const ROOM_TYPE_ICONS = {
    combat: '⚔', boss: '💀', riddle: '🔮', trap: '⚙', chest: '🎁', rest: '🕯'
};

async function openDungeonPicker() {
    if (!currentHero?.id) { showToast('Wybierz bohatera aby wejść do lochu', 'error'); return; }
    const overlay = document.getElementById('dungeon-picker-overlay');
    const list = document.getElementById('dungeon-picker-list');
    overlay.removeAttribute('hidden');
    list.innerHTML = '<div class="dungeon-picker-loading">Ładowanie lochów…</div>';

    try {
        const data = await apiRequest('GET', `/dungeons?character_id=${currentHero.id}`);
        const dungeons = data.dungeons || [];
        if (!dungeons.length) {
            list.innerHTML = '<p class="dungeon-picker-empty">Brak dostępnych lochów.</p>';
            return;
        }
        list.innerHTML = '';
        dungeons.forEach(d => {
            const cd = d.cooldown || {};
            const onCooldown = cd.on_cooldown;
            const hoursLeft = cd.hours_remaining ? `${cd.hours_remaining}h` : '';
            const card = document.createElement('button');
            card.className = 'dungeon-card' + (onCooldown ? ' dungeon-card--cooldown' : '');
            card.disabled = !!onCooldown;
            card.innerHTML = `
                <div class="dungeon-card__icon">⛏</div>
                <div class="dungeon-card__body">
                    <div class="dungeon-card__name">${escapeHtml(d.label || d.key)}</div>
                    <div class="dungeon-card__meta">${d.rooms || '?'} komnat · Poz. ${d.min_level || 1}+</div>
                    <div class="dungeon-card__atm">${escapeHtml((d.atmosphere || '').slice(0, 80))}</div>
                </div>
                ${onCooldown
                    ? `<div class="dungeon-card__cooldown">⏳ ${hoursLeft}</div>`
                    : `<div class="dungeon-card__arrow">›</div>`
                }`;
            if (!onCooldown) {
                card.addEventListener('click', () => {
                    overlay.setAttribute('hidden', '');
                    enterDungeon(d.key);
                });
            }
            list.appendChild(card);
        });
    } catch (err) {
        list.innerHTML = `<p class="dungeon-picker-empty">Błąd: ${escapeHtml(err.message || '?')}</p>`;
    }
}

async function enterDungeon(dungeonKey) {
    if (!currentHero?.id || !currentUser?.id) return;
    showToast('Wkraczasz do lochu…', 'info', 2000);

    try {
        // Create disposable dungeon campaign
        const dungeonCampaign = await apiRequest('POST', '/campaigns', {
            title: `Ekspedycja: ${dungeonKey}`,
            system_id: 'fantasy',
            model_id: 'default',
            owner_user_id: currentUser.id,
            language: 'pl',
            mode: 'dungeon',
            status: 'active',
        });

        // Assign hero to dungeon campaign
        await apiRequest('POST', `/characters/${currentHero.id}/assign-campaign`, {
            campaign_id: dungeonCampaign.id,
            user_id: currentUser.id,
        });

        _dungeonCampaignId = dungeonCampaign.id;
        currentCampaignId = dungeonCampaign.id;
        currentCampaign = dungeonCampaign;

        // Reload hero data
        const heroResp = await apiRequest('GET', `/characters/${currentHero.id}`);
        currentHero = heroResp.character || heroResp;
        characterData = currentHero;

        // Enter the dungeon
        const resp = await apiRequest('POST', `/dungeons/${dungeonKey}/enter`, {
            character_id: currentHero.id,
            campaign_id: dungeonCampaign.id,
            previous_campaign_id: null,
        });

        _activeDungeonRun = resp.dungeon_run;
        await enterGame(dungeonCampaign);
        updateDungeonHUD();
        showDungeonHUD(true);

        if (resp.room_narrative) {
            appendMessage({ role: 'assistant', content: resp.room_narrative, created_at: new Date() });
            scrollToBottom();
        }
        renderCurrentRoom();
    } catch (err) {
        showToast(err.message || 'Błąd wejścia do lochu', 'error');
    }
}

function updateDungeonHUD() {
    const run = _activeDungeonRun;
    if (!run) return;
    const label = document.getElementById('dungeon-hud-label');
    const progress = document.getElementById('dungeon-hud-progress');
    const roomType = document.getElementById('dungeon-hud-room-type');
    const advBtn = document.getElementById('dungeon-advance-btn');

    if (label) label.textContent = `⛏ ${run.dungeon_label || 'Loch'}`;

    if (progress) {
        const total = run.total_rooms || 1;
        const cur = run.current_room || 1;
        const pips = Array.from({length: total}, (_, i) => {
            const room = run.rooms?.[i];
            const cleared = room?.cleared;
            const isCurrent = i + 1 === cur;
            const icon = ROOM_TYPE_ICONS[room?.room_type] || '●';
            return `<span class="dungeon-pip${cleared ? ' cleared' : ''}${isCurrent ? ' current' : ''}" title="${room?.room_type || ''}">${icon}</span>`;
        }).join('');
        progress.innerHTML = pips;
    }

    const currentRoom = run.rooms?.find(r => r.room_id === run.current_room);
    if (roomType && currentRoom) {
        const typeNames = {combat:'Walka', boss:'BOSS', riddle:'Zagadka', trap:'Pułapka', chest:'Skrzynia', rest:'Odpoczynek'};
        roomType.textContent = typeNames[currentRoom.room_type] || currentRoom.room_type;
    }

    // Show advance button only if current room is cleared and dungeon not complete
    const cleared = currentRoom?.cleared;
    if (advBtn) advBtn.hidden = !cleared || run.completed;

    // Refresh map if it's open
    if (!document.getElementById('dungeon-map-overlay')?.hidden) {
        renderDungeonMap(run);
    }
}

function _positionDungeonHUD() {
    const hud = document.getElementById('dungeon-hud');
    const gameScreen = document.getElementById('game-screen');
    if (!hud || !gameScreen) return;
    const gr = gameScreen.getBoundingClientRect();
    const header = gameScreen.querySelector('.header');
    const headerH = header ? header.getBoundingClientRect().height : 64;
    document.documentElement.style.setProperty('--dungeon-hud-top', `${headerH}px`);
    document.documentElement.style.setProperty('--dungeon-hud-left', `${gr.left}px`);
    document.documentElement.style.setProperty('--dungeon-hud-width', `${gr.width}px`);
    requestAnimationFrame(() => {
        const hudH = hud.getBoundingClientRect().height;
        document.documentElement.style.setProperty('--dungeon-hud-h', `${hudH}px`);
    });
}

function showDungeonHUD(show) {
    const hud = document.getElementById('dungeon-hud');
    if (!hud) return;
    hud.hidden = !show;
    const gameScreen = document.getElementById('game-screen');
    if (show) {
        _positionDungeonHUD();
        gameScreen?.classList.add('game-screen--dungeon');
    } else {
        gameScreen?.classList.remove('game-screen--dungeon');
    }
}

// Reposition HUD on window resize
window.addEventListener('resize', () => {
    if (!document.getElementById('dungeon-hud')?.hidden) _positionDungeonHUD();
});

function renderCurrentRoom() {
    const run = _activeDungeonRun;
    if (!run) return;
    const room = run.rooms?.find(r => r.room_id === run.current_room);
    if (!room) return;

    const riddlePanel = document.getElementById('dungeon-riddle-panel');

    if (room.room_type === 'riddle' && !room.cleared) {
        if (riddlePanel) {
            riddlePanel.removeAttribute('hidden');
            const txt = document.getElementById('dungeon-riddle-text');
            if (txt) txt.textContent = room.riddle_text || '…';
            const hint = document.getElementById('dungeon-riddle-hint');
            if (hint) { hint.textContent = ''; hint.setAttribute('hidden', ''); }
        }
    } else {
        riddlePanel?.setAttribute('hidden', '');
    }
}

async function _dungeonAdvance() {
    if (!_dungeonCampaignId || !characterData?.id) return;
    try {
        const resp = await apiRequest('POST', '/dungeons/advance-room', {
            campaign_id: _dungeonCampaignId,
            character_id: characterData.id,
        });
        _activeDungeonRun = resp.dungeon_run;

        if (resp.narrative) {
            appendMessage({ role: 'assistant', content: resp.narrative, created_at: new Date() });
            scrollToBottom();
        }

        if (resp.completed) {
            _showDungeonComplete(resp);
        } else {
            updateDungeonHUD();
            renderCurrentRoom();
            // Auto-open map on first advance (room 2) so player learns the layout exists
            const newRoom = _activeDungeonRun?.current_room;
            if (newRoom === 2) openDungeonMap(true);
        }
    } catch (err) {
        showToast(err.message || 'Błąd', 'error');
    }
}

async function _dungeonResolveRoom(playerInput) {
    if (!_dungeonCampaignId || !characterData?.id) return;
    try {
        const resp = await apiRequest('POST', '/dungeons/resolve-room', {
            campaign_id: _dungeonCampaignId,
            character_id: characterData.id,
            player_input: playerInput || null,
        });

        if (resp.narrative) {
            appendMessage({ role: 'assistant', content: resp.narrative, created_at: new Date() });
            scrollToBottom();
        }

        if (resp.hint) {
            const hintEl = document.getElementById('dungeon-riddle-hint');
            if (hintEl) { hintEl.textContent = `💡 ${resp.hint}`; hintEl.removeAttribute('hidden'); }
        }

        // Reload run state
        const runResp = await apiRequest('GET', `/campaigns/${_dungeonCampaignId}/dungeon-run`);
        if (runResp.dungeon_run) _activeDungeonRun = runResp.dungeon_run;
        updateDungeonHUD();
        renderCurrentRoom();

        if (resp.advance_available && resp.success !== false) {
            document.getElementById('dungeon-riddle-panel')?.setAttribute('hidden', '');
            document.getElementById('dungeon-advance-btn')?.removeAttribute('hidden');
        }

        // Heal on rest room
        if (resp.heal_pct && resp.heal_pct > 0) {
            await refreshCharacterData();
        }
    } catch (err) {
        showToast(err.message || 'Błąd', 'error');
    }
}

function _showDungeonComplete(resp) {
    const overlay = document.getElementById('dungeon-complete-overlay');
    if (!overlay) return;
    const icon = document.getElementById('dungeon-complete-icon');
    const title = document.getElementById('dungeon-complete-title');
    const lootEl = document.getElementById('dungeon-complete-loot');
    const cooldownEl = document.getElementById('dungeon-complete-cooldown');

    if (icon) icon.textContent = '⚔️';
    if (title) title.textContent = `Loch ukończony!`;

    const loot = resp.loot || [];
    if (lootEl) {
        lootEl.innerHTML = loot.length
            ? '<ul>' + loot.map(l => `<li>📦 ${escapeHtml(l.label || l.key || '?')} ×${l.quantity || 1}</li>`).join('') + '</ul>'
            : '<p>Brak łupów z bossa.</p>';
    }

    if (cooldownEl && _activeDungeonRun?.cooldown_hours) {
        cooldownEl.textContent = `Następna ekspedycja za ${_activeDungeonRun.cooldown_hours}h`;
    }

    overlay.removeAttribute('hidden');
    showDungeonHUD(false);
}

async function _exitDungeon() {
    if (!_dungeonCampaignId || !characterData?.id) { showScreen('campaigns'); return; }
    try {
        const resp = await apiRequest('POST', '/dungeons/exit', {
            campaign_id: _dungeonCampaignId,
            character_id: characterData.id,
        });
        // Delete the disposable dungeon campaign
        try { await apiRequest('DELETE', `/campaigns/${_dungeonCampaignId}`); } catch {}
        _activeDungeonRun = null;
        _dungeonCampaignId = null;
        currentCampaignId = null;
        characterData = null;
        try { localStorage.removeItem('aigm_campaign_id'); } catch {}
        showDungeonHUD(false);
        document.getElementById('dungeon-complete-overlay')?.setAttribute('hidden', '');
        document.getElementById('dungeon-riddle-panel')?.setAttribute('hidden', '');
        // Reload hero and go to campaign screen
        if (currentHero?.id) {
            const heroResp = await apiRequest('GET', `/characters/${currentHero.id}`);
            currentHero = heroResp.character || heroResp;
        }
        await loadCampaigns();
        showScreen('campaigns');
    } catch (err) {
        showToast(err.message || 'Błąd', 'error');
        showScreen('campaigns');
    }
}

// ── Dungeon Map (square tile grid) ───────────────────────────────────────────

const ROOM_TYPE_LABELS = {
    combat: 'Walka', boss: 'BOSS', riddle: 'Zagadka',
    trap: 'Pułapka', chest: 'Skrzynia', rest: 'Odpoczynek'
};

function renderDungeonMap(run) {
    const svg = document.getElementById('dmap-svg');
    if (!svg || !run) return;

    const rooms = run.rooms || [];
    const currentRoomId = run.current_room || 1;

    // Grid metrics
    const S = 52;          // tile size
    const GAP = 28;        // corridor length
    const PAD = 20;        // padding
    const R = 8;           // corner radius
    const STEP = S + GAP;

    // Ensure all rooms have coordinates (fallback: linear layout by room_id)
    rooms.forEach((r, i) => {
        if (r.map_col == null) r.map_col = i;
        if (r.map_row == null) r.map_row = 0;
    });

    // Determine grid bounds
    const maxCol = Math.max(...rooms.map(r => r.map_col));
    const maxRow = Math.max(...rooms.map(r => r.map_row));
    const svgW = (maxCol + 1) * STEP + GAP + PAD * 2;
    const svgH = (maxRow + 1) * STEP + GAP + PAD * 2;

    svg.setAttribute('viewBox', `0 0 ${svgW} ${svgH}`);
    svg.setAttribute('width', svgW);
    svg.setAttribute('height', svgH);

    const tileX = (col) => PAD + col * STEP;
    const tileY = (row) => PAD + row * STEP;
    const cx = (col) => tileX(col) + S / 2;
    const cy = (row) => tileY(row) + S / 2;

    let html = '';

    // Draw corridors first (behind tiles)
    for (let i = 0; i < rooms.length; i++) {
        const room = rooms[i];
        const next = rooms[i + 1];
        if (!next) continue;

        const x1 = tileX(room.map_col) + S;
        const y1 = cy(room.map_row);
        const x2 = tileX(next.map_col);
        const y2 = cy(next.map_row);

        const bothKnown = room.cleared || room.room_id === currentRoomId;
        const corridorOpacity = bothKnown ? 0.6 : 0.15;

        html += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"
            stroke="#4a3010" stroke-width="3" opacity="${corridorOpacity}"/>`;
    }

    // Draw tiles
    rooms.forEach(room => {
        const col = room.map_col || 0;
        const row = room.map_row || 0;
        const x = tileX(col);
        const y = tileY(row);
        const isCurrent = room.room_id === currentRoomId;
        const isCleared = room.cleared;
        const isRevealed = isCurrent || isCleared;
        const isBoss = room.room_type === 'boss';

        // Determine colors
        let fill, stroke, strokeW, textColor, opacity;
        if (!isRevealed) {
            fill = '#0d0904'; stroke = '#2a1a08'; strokeW = 1;
            textColor = '#4a3a20'; opacity = '0.7';
        } else if (isCurrent) {
            fill = '#1a1005'; stroke = '#c9751a'; strokeW = 2;
            textColor = '#d4a060'; opacity = '1';
        } else if (isCleared) {
            fill = '#100e08'; stroke = '#3a2808'; strokeW = 1;
            textColor = '#5a4a28'; opacity = '0.85';
        }

        if (isBoss && isRevealed) { stroke = '#8a2010'; fill = '#140802'; }

        // Tile background
        html += `<rect x="${x}" y="${y}" width="${S}" height="${S}" rx="${R}"
            fill="${fill}" stroke="${stroke}" stroke-width="${strokeW}" opacity="${opacity}"/>`;

        if (isCurrent) {
            // Subtle glow ring
            html += `<rect x="${x - 2}" y="${y - 2}" width="${S + 4}" height="${S + 4}" rx="${R + 2}"
                fill="none" stroke="#c9751a" stroke-width="1" opacity="0.25"/>`;
        }

        // Icon or ?
        const icon = isRevealed ? (ROOM_TYPE_ICONS[room.room_type] || '●') : '?';
        const iconSize = isRevealed ? 18 : 16;
        const iconY = y + S / 2 - (isRevealed ? 6 : 4);

        html += `<text x="${cx(col)}" y="${iconY}" text-anchor="middle"
            dominant-baseline="middle" font-size="${iconSize}"
            fill="${textColor}" style="pointer-events:none">${icon}</text>`;

        // Room label (revealed only)
        if (isRevealed) {
            const label = isBoss ? 'BOSS' : (ROOM_TYPE_LABELS[room.room_type] || room.room_type || '');
            const labelY = y + S - 10;
            html += `<text x="${cx(col)}" y="${labelY}" text-anchor="middle"
                font-size="7" fill="${textColor}" font-family="sans-serif"
                style="pointer-events:none;text-transform:uppercase;letter-spacing:0.08em">${label}</text>`;
        }

        // Cleared checkmark
        if (isCleared && !isCurrent) {
            html += `<text x="${x + S - 10}" y="${y + 12}" text-anchor="middle"
                font-size="9" fill="#5a8040" style="pointer-events:none">✓</text>`;
        }

        // Room number
        html += `<text x="${x + 8}" y="${y + 12}" text-anchor="middle"
            font-size="8" fill="${isRevealed ? '#6a5a30' : '#2a2010'}"
            style="pointer-events:none">${room.room_id}</text>`;
    });

    svg.innerHTML = html;
}

function openDungeonMap(autoClose = false) {
    const overlay = document.getElementById('dungeon-map-overlay');
    if (!overlay) return;
    renderDungeonMap(_activeDungeonRun);
    overlay.removeAttribute('hidden');
    if (autoClose) {
        setTimeout(() => overlay.setAttribute('hidden', ''), 3500);
    }
}

function closeDungeonMap() {
    document.getElementById('dungeon-map-overlay')?.setAttribute('hidden', '');
}

function initDungeon() {
    document.getElementById('dungeon-picker-btn')?.addEventListener('click', openDungeonPicker);
    document.getElementById('dungeon-picker-close')?.addEventListener('click', () => {
        document.getElementById('dungeon-picker-overlay')?.setAttribute('hidden', '');
    });
    document.getElementById('dungeon-advance-btn')?.addEventListener('click', _dungeonAdvance);
    document.getElementById('dungeon-exit-btn')?.addEventListener('click', _exitDungeon);
    document.getElementById('dungeon-complete-btn')?.addEventListener('click', _exitDungeon);
    document.getElementById('dungeon-map-btn')?.addEventListener('click', () => openDungeonMap());
    document.getElementById('dmap-close-btn')?.addEventListener('click', closeDungeonMap);
    document.getElementById('dungeon-map-overlay')?.addEventListener('click', (e) => {
        if (e.target === document.getElementById('dungeon-map-overlay')) closeDungeonMap();
    });

    // Riddle submit
    const riddleInput = document.getElementById('dungeon-riddle-input');
    document.getElementById('dungeon-riddle-submit')?.addEventListener('click', () => {
        const val = riddleInput?.value.trim();
        if (!val) return;
        if (riddleInput) riddleInput.value = '';
        _dungeonResolveRoom(val);
    });
    riddleInput?.addEventListener('keypress', e => {
        if (e.key === 'Enter') {
            const val = riddleInput.value.trim();
            if (!val) return;
            riddleInput.value = '';
            _dungeonResolveRoom(val);
        }
    });
    document.getElementById('dungeon-riddle-hint-btn')?.addEventListener('click', () => {
        _dungeonResolveRoom(null); // null = request hint
    });
}

// ── Custom DELETE hero confirmation modal ────────────────────────────────────

function showDeleteHeroModal(heroName) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'delete-modal-overlay';
    overlay.innerHTML = `
      <div class="delete-modal" role="dialog" aria-modal="true">
        <div class="delete-modal__header">
          <span class="delete-modal__icon">☠</span>
          <span class="delete-modal__title">Nieodwracalne usunięcie</span>
        </div>
        <div class="delete-modal__body">
          <div class="delete-modal__hero-name">${escapeHtml(heroName)}</div>
          <p class="delete-modal__desc">
            Bohater oraz wszystkie jego kampanie zostaną trwale usunięte.<br>
            Tej operacji nie można cofnąć.
          </p>
          <div class="delete-modal__label">Wpisz DELETE aby potwierdzić</div>
          <input type="text" class="delete-modal__input" id="del-confirm-input"
            placeholder="DELETE" autocomplete="off" spellcheck="false"/>
        </div>
        <div class="delete-modal__footer">
          <button class="delete-modal__btn delete-modal__btn--cancel" id="del-cancel">Anuluj</button>
          <button class="delete-modal__btn delete-modal__btn--confirm" id="del-confirm" disabled>Usuń na zawsze</button>
        </div>
      </div>`;

    document.body.appendChild(overlay);
    const input = overlay.querySelector('#del-confirm-input');
    const confirmBtn = overlay.querySelector('#del-confirm');
    const cancelBtn = overlay.querySelector('#del-cancel');

    setTimeout(() => input.focus(), 50);

    input.addEventListener('input', () => {
      const ok = input.value === 'DELETE';
      confirmBtn.disabled = !ok;
      input.classList.toggle('valid', ok);
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !confirmBtn.disabled) { overlay.remove(); resolve(true); }
      if (e.key === 'Escape') { overlay.remove(); resolve(false); }
    });
    confirmBtn.addEventListener('click', () => { overlay.remove(); resolve(true); });
    cancelBtn.addEventListener('click', () => { overlay.remove(); resolve(false); });
    overlay.addEventListener('click', e => { if (e.target === overlay) { overlay.remove(); resolve(false); } });
  });
}
