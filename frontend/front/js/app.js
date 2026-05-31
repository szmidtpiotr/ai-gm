/**
 * AI GM RPG - Mobile-First Frontend Application
 * Task T28.5 - Alternative frontend based on Figma designs v18-20
 */

// ── Theme system ──────────────────────────────────────────────────────────
const VALID_THEMES = ['dark', 'amber', 'sepia', 'light'];

function applyTheme(theme) {
    const t = VALID_THEMES.includes(theme) ? theme : 'dark';
    document.documentElement.dataset.theme = t;
    localStorage.setItem('aigm_theme', t);
}

// Apply saved theme immediately on load (before any rendering)
applyTheme(localStorage.getItem('aigm_theme') || 'dark');

const API_BASE = '/api';

const SLASH_COMMANDS = [
    { cmd: '/help',    desc: 'Pokaż listę dostępnych komend' },
    { cmd: '/sheet',   desc: 'Otwórz kartę postaci' },
    { cmd: '/mem',     desc: 'Pytanie o przeszłość z podsumowań (bez wpływu na narrację)' },
    { cmd: '/helpme',  desc: 'Doradca OOC — wskazówki poza fabułą' },
    { cmd: '/whisper', desc: 'Wyślij szept do gracza: /whisper Imię wiadomość', multiplayerOnly: true },
    { cmd: '/admin',   desc: 'Komendy admina: add | set | remove | clear | combat | quest | show', adminOnly: true },
    { cmd: '/debug',   desc: 'Debug: dump-state | set-hp N | set-state STATE | reset-cooldowns | roll SKILL', adminOnly: true },
    { cmd: '/roll',    desc: 'Admin: wymuś test umiejętności. /roll skradanie → kostek; /roll skradanie 18 → wstrzyknij wartość 18', adminOnly: true },
    { cmd: '/history', desc: 'Ostatnie 10 tur sesji' },
    { cmd: '/search',  desc: 'Przeszukaj lokację lub postać' },
    { cmd: '/atak',    desc: 'Synchronizuj panel walki lub zacznij walkę' },
];

// ============================================================================
// DOM Elements
// ============================================================================
const screens = {
    login: document.getElementById('login-screen'),
    register: document.getElementById('register-screen'),
    verifyEmail: document.getElementById('verify-email-screen'),
    forgotPassword: document.getElementById('forgot-password-screen'),
    resetPassword: document.getElementById('reset-password-screen'),
    onboarding: document.getElementById('onboarding-screen'),
    profile: document.getElementById('profile-screen'),
    heroes: document.getElementById('heroes-screen'),
    campaigns: document.getElementById('campaigns-screen'),
    newCampaign: document.getElementById('new-campaign-screen'),
    campaignStyle: document.getElementById('campaign-style-screen'),
    prebuiltCampaign: document.getElementById('prebuilt-campaign-screen'),
    characterWizard: document.getElementById('character-wizard-screen'),
    game: document.getElementById('game-screen'),
    'create-lobby-screen': document.getElementById('create-lobby-screen'),
    'lobby-screen': document.getElementById('lobby-screen'),
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
    btnHeroesLogout: document.getElementById('heroes-profile-btn'),

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
    btnHome: document.getElementById('home-btn'),
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
let _onboardingTimer = null;
let _inviteCode = null;
let _resetToken = null;
let _verifyEmailAddress = null;
let _resendCountdownInterval = null;
let _canResendVerify = false;
let _profileReturnScreen = 'heroes';
let currentCampaignId = null;
let currentCampaign = null;

// T33: Suggested actions state
let _suggestedActions = [];

// T47a: Turn cancel — AbortController for the active LLM streaming fetch
let _activeTurnAbort = null;   // AbortController | null — set while a turn is in-flight
let _activeTurnText  = '';     // the raw text submitted, restored on cancel
let wizardStepNum = 0;
let isSheetOpen = false;
let isSettingsOpen = false;
let isJournalOpen = false;
let _journalBadgeTurns = 0;  // narrative turns since last journal open; badge fires at 10
let characterData = null;
let authToken = null;
let currentUser = null;
let debugMode = localStorage.getItem('aigm_debug') === '1';

// --- Campaign style screen state ---
let _pendingCampaignTitle = '';
let _campaignStyleMode = 'solo';
let _selectedHookIds = [];
let _selectedTemplateId = null;
let _hookPoolAll = [];
let _hookTypeFilter = '';

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
let wizardStatsRevealed = false;   // true after dice animation has played for this session
let wizardSkillsRevealed = false;  // true after skill dice animation has played for this session
const WIZARD_MAX_SWAPS = 4;
const WIZARD_LOCKED_COUNT = 3;   // first N skill slots cannot be swapped to a different skill
const WIZARD_STAT_MIN = 8;
const WIZARD_STAT_MAX = 18;
const ARCHETYPE_BONUS = { warrior: { STR: 2, CON: 1 }, scholar: { INT: 2, WIS: 1 }, rogue: { DEX: 2, LCK: 1 } };
// Archetype-specific skill pools — swap candidates must come from here
const ARCHETYPE_SKILL_POOL = {
    warrior: new Set(['melee_attack','athletics','endurance','intimidation','survival','ranged_attack','stealth','persuasion']),
    scholar:  new Set(['arcana','spell_attack','lore','investigation','medicine','awareness','alchemy','persuasion']),
    rogue:    new Set(['stealth','ranged_attack','sleight_of_hand','persuasion','survival','intimidation','athletics','awareness']),
};
// Preferred skills per archetype (for sorting locked vs swappable slots)
const ARCHETYPE_PREFERRED = {
    warrior: ['melee_attack','athletics','endurance'],
    scholar:  ['arcana','spell_attack','lore'],
    rogue:    ['stealth','ranged_attack','sleight_of_hand'],
};
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
// Stage 10 A2 — auto-refresh state. _refreshInFlight prevents a stampede when
// multiple parallel requests get 401 simultaneously; they all await the same promise.
let _refreshInFlight = null;
let _mpInviteInterval = null;
async function _tryRefreshAccessToken() {
    const refresh = localStorage.getItem('aigm_refresh_token');
    if (!refresh) return null;
    if (_refreshInFlight) return _refreshInFlight;
    _refreshInFlight = (async () => {
        try {
            const r = await fetch(`${API_BASE}/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refresh }),
            });
            if (!r.ok) {
                console.warn('[JWT] refresh failed:', r.status);
                return null;
            }
            const data = await r.json();
            if (data?.access_token) {
                localStorage.setItem('aigm_access_token', data.access_token);
                return data.access_token;
            }
        } catch (e) {
            console.warn('[JWT] refresh exception:', e);
        }
        return null;
    })();
    try {
        return await _refreshInFlight;
    } finally {
        _refreshInFlight = null;
    }
}

async function apiRequest(method, endpoint, body = null) {
    const headers = {
        'Content-Type': 'application/json',
        // Prevent browser caching of API responses — turn lists across campaigns
        // can otherwise resolve from cache and skip the intro-turn trigger.
        'Cache-Control': 'no-cache',
    };
    // Stage 10 A2 — attach JWT when we have one. Backend continues accepting
    // ?user_id= query param during 10-B; this header is additive.
    const accessToken = localStorage.getItem('aigm_access_token');
    if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
    }

    const options = { method, headers, cache: 'no-store' };
    if (body) {
        options.body = JSON.stringify(body);
    }

    console.log(`[API] ${method} ${API_BASE}${endpoint}`, body || '');

    let response = await fetch(`${API_BASE}${endpoint}`, options);

    // Stage 10 A2 — on 401 with a stored refresh token AND we sent an access
    // token, try refreshing once and retry the request.
    if (response.status === 401 && accessToken && localStorage.getItem('aigm_refresh_token')) {
        const refreshed = await _tryRefreshAccessToken();
        if (refreshed) {
            headers['Authorization'] = `Bearer ${refreshed}`;
            response = await fetch(`${API_BASE}${endpoint}`, options);
        }
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error(`[API] Error ${response.status}:`, errorData);
        // Surface structured `detail` objects (e.g. historia_cooldown) — string
        // detail goes into the Error message, full body attached as `err.body`.
        const detail = errorData?.detail;
        const msg = typeof detail === 'string'
            ? detail
            : (typeof detail === 'object' && detail?.message)
                ? detail.message
                : (errorData.message || `API Error: ${response.status}`);
        const err = new Error(msg);
        err.status = response.status;
        err.body = errorData;
        throw err;
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
        // S12 follow-up: bottom bar is a game-screen affordance only.
        // Toggle a body class so CSS can both gate the bar's display AND
        // make room at the bottom of #game-screen so the composer isn't covered.
        document.body.classList.toggle('bottom-bar-visible', screenName === 'game');
        window.clog?.setContext({ screen: screenName });
        window.clog?.event('screen_change', { screen: screenName });
        if (screenName !== 'game' && typeof stopCombatPolling === 'function') {
            stopCombatPolling();
            if (typeof hideCombatUI === 'function') hideCombatUI();
        }
        if (screenName === 'campaigns') {
            if (!_mpInviteInterval) _mpInviteInterval = setInterval(loadPendingMpInvites, 10000);
            applyGameModeFlags();
        } else {
            clearInterval(_mpInviteInterval); _mpInviteInterval = null;
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
                is_admin: response.is_admin,
                is_tester: !!response.is_tester,
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
            registerPushNotifications().catch(() => {});

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
            if (window._pendingJoinToken) {
                const token = window._pendingJoinToken;
                delete window._pendingJoinToken;
                showScreen('campaigns');
                const tokenInput = document.getElementById('lobby-join-token-input');
                if (tokenInput) tokenInput.value = token;
                joinViaToken();
                return;
            }
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
        } else if (error.status === 423 && error.body?.detail?.error === 'pending_deletion') {
            // F1.2 — account is soft-deleted; offer the undo path
            _showUndeleteModal(error.body.detail.undo_deadline, username, password);
        } else {
            showToast(error.message || 'Błąd logowania', 'error');
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span class="btn__icon">✨</span> Zaloguj się';
    }
}

// F1.2 — undo modal shown when login hits 423 / pending_deletion
function _showUndeleteModal(undoDeadlineIso, username, password) {
    const modal = document.getElementById('undelete-modal');
    if (!modal) return;
    const deadlineEl = document.getElementById('undelete-deadline');
    if (deadlineEl) deadlineEl.textContent = _formatDeadline(undoDeadlineIso);
    modal.hidden = false;
    const confirmBtn = document.getElementById('undelete-confirm-btn');
    const cancelBtn  = document.getElementById('undelete-cancel-btn');
    const backdrop   = document.getElementById('undelete-modal-backdrop');

    const close = () => { modal.hidden = true; };
    const onCancel = () => close();
    const onBackdrop = () => close();
    const onConfirm = async () => {
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Przywracanie…';
        try {
            const resp = await apiRequest('POST', '/auth/undelete', { username, password });
            close();
            // Mirror the login-success flow
            currentUser = {
                id: resp.user_id,
                username: resp.username || username,
                display_name: resp.display_name,
                is_admin: resp.is_admin,
                role: resp.role || (resp.is_admin ? 'admin' : 'player'),
            };
            if (resp.access_token)  localStorage.setItem('aigm_access_token', resp.access_token);
            if (resp.refresh_token) localStorage.setItem('aigm_refresh_token', resp.refresh_token);
            authToken = resp.access_token || `user:${currentUser.id}`;
            localStorage.setItem('token', authToken);
            localStorage.setItem('user', JSON.stringify(currentUser));
            showToast('Konto przywrócone. Witaj z powrotem!', 'success');
            await loadHeroes();
            if (await tryRestoreSession()) return;
            if (!resp.onboarded_at) showOnboardingCinematic();
            else showScreen('heroes');
        } catch (e) {
            showToast(e.message || 'Błąd przywracania konta', 'error');
            confirmBtn.disabled = false;
            confirmBtn.textContent = '🔄 Cofnij usunięcie i zaloguj się';
        }
    };

    // Re-bind cleanly (these handlers may be re-attached on each modal open)
    confirmBtn.onclick = onConfirm;
    cancelBtn.onclick  = onCancel;
    backdrop.onclick   = onBackdrop;
}

function handleLogout() {
    window.multiplayerUI?.deactivate();
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
    const errEl    = document.getElementById('register-error');
    errEl.hidden   = true;

    if (!email || !username || !password) {
        errEl.textContent = 'Wypełnij wszystkie pola';
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
                role: resp.role || 'player'
            };
            localStorage.setItem('user', JSON.stringify(currentUser));
            updateAdminSettingsVisibility();
        }
        showToast('Email potwierdzony! Witaj w AI-GM.', 'success');
        await loadHeroes();
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
    return false;
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
    // Stage 6 H1: use the enriched /heroes endpoint.
    const response = await apiRequest('GET', `/heroes?user_id=${currentUser.id}`);
    const heroes = response.heroes || [];
    renderHeroes(heroes);
}

// Stage 6 H3: status chip mapping (label + CSS modifier class).
const HERO_STATUS_META = {
    idle:         { label: 'Wolny',      cls: 'hero-status--idle' },
    in_campaign:  { label: 'W kampanii', cls: 'hero-status--campaign' },
    in_dungeon:   { label: 'W lochu',    cls: 'hero-status--dungeon' },
};

// Human-friendly relative time: <1h → "Dzisiaj", <1d → "Wczoraj", <7d → "X dni temu", else date.
function _relativeTimePL(iso) {
    if (!iso) return '';
    const t = new Date(iso.replace(' ', 'T') + (iso.includes('Z') ? '' : 'Z'));
    if (isNaN(t)) return '';
    const diffMs = Date.now() - t.getTime();
    const dayMs = 86_400_000;
    if (diffMs < 60_000) return 'przed chwilą';
    if (diffMs < dayMs) return 'dzisiaj';
    if (diffMs < 2 * dayMs) return 'wczoraj';
    if (diffMs < 7 * dayMs) return `${Math.floor(diffMs / dayMs)} dni temu`;
    return t.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
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

    // Sort: in_campaign first, then in_dungeon, then idle. Newest within each group.
    const sortRank = { in_campaign: 0, in_dungeon: 1, idle: 2 };
    const sorted = [...heroes].sort((a, b) => {
        const ra = sortRank[a.hero_status || a.status || 'idle'] ?? 9;
        const rb = sortRank[b.hero_status || b.status || 'idle'] ?? 9;
        if (ra !== rb) return ra - rb;
        return String(b.created_at || '').localeCompare(String(a.created_at || ''));
    });

    sorted.forEach(hero => {
        const sheet = hero.sheet_json || {};
        const archetype = sheet.archetype || hero.system_id || '?';
        const level = (sheet.xp_lifetime_earned != null)
            ? Math.min(10, Math.floor(Number(sheet.xp_lifetime_earned) / 100) + 1)
            : (sheet.level || 1);
        const hp = sheet.current_hp ?? sheet.max_hp ?? '?';
        const maxHp = sheet.max_hp ?? '?';
        const status = hero.hero_status || hero.status || 'idle';
        const statusMeta = HERO_STATUS_META[status] || HERO_STATUS_META.idle;
        const campaignTitle = hero.campaign_title || '';
        const completed = Number(hero.campaigns_completed ?? 0);
        const xpLifetime = Number(hero.total_xp_lifetime ?? 0);
        const xpAvail = Number(sheet.xp_available || 0);
        const lastSeen = _relativeTimePL(hero.last_activity_at);

        const wrapper = document.createElement('div');
        wrapper.className = 'hero-card-wrapper';

        const card = document.createElement('div');
        card.className = 'hero-card';
        card.dataset.heroId = String(hero.id);
        card.innerHTML = `
            <div class="hero-card__main">
              <div class="hero-card__icon">⚔</div>
              <div class="hero-card__body">
                <div class="hero-card__title-row">
                  <h3 class="hero-card__name">${_esc(hero.name)}</h3>
                  <span class="hero-status-chip ${statusMeta.cls}">${_esc(statusMeta.label)}</span>
                </div>
                <p class="hero-card__sub">${_esc(archetype)} · Poz. ${level} · ${hp}/${maxHp} HP${lastSeen ? ` · <span class="hero-card__lastseen">${_esc(lastSeen)}</span>` : ''}</p>
                ${campaignTitle ? `<p class="hero-card__campaign">📖 ${_esc(campaignTitle)}</p>` : ''}
                <div class="hero-card__trophy">
                  <span title="Zakończone przygody">⚔ ${completed}</span>
                  <span title="Łączna ilość zdobytych PD">🏆 ${xpLifetime} PD</span>
                  <button type="button" class="hero-card__history-btn" data-hero-id="${hero.id}" title="Historia bohatera">📜 Historia</button>
                  ${status === 'idle' && xpAvail > 0 ? `<button type="button" class="hero-card__awansuj-btn" data-hero-id="${hero.id}" title="Wydaj PD na rozwój">⬆ Awansuj (${xpAvail} PD)</button>` : ''}
                </div>
              </div>
            </div>
        `;
        card.addEventListener('click', (e) => {
            // Don't trigger card-select when clicking the inline buttons.
            if (e.target.closest('.hero-card__history-btn, .hero-card__awansuj-btn')) return;
            selectHero(hero);
        });

        // Inline button wiring
        card.querySelector('.hero-card__history-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            openHeroHistoryModal(hero);
        });
        card.querySelector('.hero-card__awansuj-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            // Open the existing Awansuj panel — works on idle heroes (no campaign required).
            currentHero = hero;
            characterData = hero;
            openAwansujPanel(hero, sheet);
        });

        const delBtn = document.createElement('button');
        delBtn.className = 'hero-card__delete';
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
        list.appendChild(wrapper);
    });
}

function _toRoman(n) {
    if (!n || n < 1) return '?';
    const v = [1000,900,500,400,100,90,50,40,10,9,5,4,1];
    const r = ['M','CM','D','CD','C','XC','L','XL','X','IX','V','IV','I'];
    let out = '';
    for (let i = 0; i < v.length; i++) {
        while (n >= v[i]) { out += r[i]; n -= v[i]; }
    }
    return out;
}

// Stage 12 J1: Hero Journal — chapter list, one per completed campaign.
async function openHeroHistoryModal(hero) {
    let modal = document.getElementById('hero-history-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'hero-history-modal';
        modal.className = 'hero-history-modal';
        modal.innerHTML = `
          <div class="hero-history-modal__backdrop" data-action="close"></div>
          <div class="hero-history-modal__card">
            <header class="hero-history-modal__header">
              <div class="hero-history-modal__header-inner">
                <span class="hero-history-modal__crest">📜</span>
                <div>
                  <div class="hero-history-modal__hero-name" id="hero-history-modal-hero"></div>
                  <h3 id="hero-history-modal-title">Kronika przygód</h3>
                </div>
              </div>
              <button type="button" class="hero-history-modal__close" data-action="close" aria-label="Zamknij">✕</button>
            </header>
            <div class="hero-history-modal__body" id="hero-history-modal-body">
              <p class="hero-history-modal__loading">Wczytywanie…</p>
            </div>
          </div>`;
        document.body.appendChild(modal);
        modal.addEventListener('click', (e) => {
            if (e.target.dataset.action === 'close') {
                modal.classList.remove('hero-history-modal--open');
            }
        });
    }
    const heroNameEl = document.getElementById('hero-history-modal-hero');
    const body = document.getElementById('hero-history-modal-body');
    if (heroNameEl) heroNameEl.textContent = hero.name;
    if (body) body.innerHTML = `<p class="hero-history-modal__loading">Wczytywanie…</p>`;
    modal.classList.add('hero-history-modal--open');

    try {
        const r = await apiRequest('GET', `/characters/${hero.id}/history`);
        const rows = r.history || [];
        if (!body) return;
        if (!rows.length) {
            const isFirstActive = (hero.hero_status || hero.status) === 'in_campaign';
            body.innerHTML = `
              <div class="journal-empty">
                <div class="journal-empty__glyph">📜</div>
                <p class="journal-empty__text">${isFirstActive
                    ? 'Pierwsza przygoda trwa — jej rozdział pojawi się tu po zakończeniu.'
                    : 'Kronika jest pusta. Żadna przygoda nie dobiegła jeszcze końca.'}</p>
              </div>`;
            return;
        }
        const outcomeIcon  = { victory: '🏆', death: '💀', abandoned: '🚪' };
        const outcomeLabel = { victory: 'Zwycięstwo', death: 'Śmierć', abandoned: 'Porzucono' };
        body.innerHTML = `<ol class="journal-list">` + rows.map((h, idx) => {
            const chapterN  = rows.length - idx;
            const icon      = outcomeIcon[h.outcome]  || '•';
            const lbl       = outcomeLabel[h.outcome] || h.outcome || '—';
            const chTitle   = _esc(h.campaign_title   || `Kampania #${h.campaign_id}`);
            const when      = _relativeTimePL(h.completed_at || h.created_at) || '—';
            const outcomeClass = _esc(h.outcome || 'abandoned');
            const summaryHtml = h.chapter_summary
                ? `<p class="journal-chapter__summary">${_esc(h.chapter_summary)}</p>`
                : `<p class="journal-chapter__summary journal-chapter__summary--pending">Podsumowanie rozdziału zostanie wygenerowane wkrótce…</p>`;
            return `
              <li class="journal-chapter journal-chapter--${outcomeClass}">
                <div class="journal-chapter__eyebrow">Rozdział ${_toRoman(chapterN)}</div>
                <div class="journal-chapter__title">${chTitle}</div>
                <div class="journal-chapter__outcome-row">
                  <span class="journal-chapter__outcome-badge journal-chapter__outcome-badge--${outcomeClass}">
                    ${icon} ${_esc(lbl)}
                  </span>
                  <span class="journal-chapter__stats">
                    ${h.xp_earned ?? 0} PD &middot; ${h.turns_count ?? 0} tur &middot; ${_esc(when)}
                  </span>
                </div>
                ${summaryHtml}
              </li>`;
        }).join('') + `</ol>`;
        // J6 — append cross-campaign minimap after chapter list
        _appendJournalMinimap(body, hero.id);
    } catch (err) {
        if (body) body.innerHTML = `<p class="hero-history-modal__empty">Nie udało się wczytać kroniki: ${_esc(err.message || err)}</p>`;
    }
}

async function _appendJournalMinimap(body, characterId) {
    const wrap = document.createElement('div');
    wrap.className = 'journal-minimap';
    wrap.innerHTML = `<div class="journal-minimap__title">Odwiedzone miejsca</div><div class="journal-minimap__svg-wrap" id="journal-minimap-svg-wrap"><span class="journal-minimap__empty">Wczytywanie…</span></div>`;
    body.appendChild(wrap);

    try {
        const data = await apiRequest('GET', `/characters/${characterId}/hex-map`);
        const hexes = data.hexes || [];
        const svgWrap = document.getElementById('journal-minimap-svg-wrap');
        if (!svgWrap) return;
        if (!hexes.length) {
            svgWrap.innerHTML = `<span class="journal-minimap__empty">Żadne miejsce nie zostało jeszcze odkryte.</span>`;
            return;
        }
        svgWrap.innerHTML = _renderHexMinimap(hexes);
    } catch (_e) {
        const svgWrap = document.getElementById('journal-minimap-svg-wrap');
        if (svgWrap) svgWrap.innerHTML = '';
    }
}

function _renderHexMinimap(hexes) {
    const S = 12;
    const H = Math.sqrt(3) * S;
    const toPixel = (q, r) => ({ x: S * 1.5 * q, y: H * (r + q * 0.5) });
    const TYPE_COLORS = {
        plains: '#3d5a2a', forest: '#1a3a1a', mountain: '#4a3c2e',
        water: '#102a42', desert: '#5a4a1a', swamp: '#1e3228',
        dungeon: '#2a1a3a', ruins: '#3a2a2a', town: '#4a4a2e', road: '#3a3a1a',
    };
    const pixels = hexes.map(h => toPixel(h.q, h.r));
    const minX = Math.min(...pixels.map(p => p.x)) - S;
    const minY = Math.min(...pixels.map(p => p.y)) - H / 2;
    const maxX = Math.max(...pixels.map(p => p.x)) + S;
    const maxY = Math.max(...pixels.map(p => p.y)) + H / 2;
    const svgW = Math.ceil(maxX - minX + 16);
    const svgH = Math.ceil(maxY - minY + 16);
    const hexPath = (cx, cy) => {
        const pts = [];
        for (let i = 0; i < 6; i++) {
            const a = Math.PI / 180 * (60 * i);
            pts.push(`${(cx + S * Math.cos(a)).toFixed(1)},${(cy + S * Math.sin(a)).toFixed(1)}`);
        }
        return `M${pts.join('L')}Z`;
    };
    const paths = hexes.map((h, i) => {
        const { x, y } = pixels[i];
        const cx = x - minX + 8, cy = y - minY + 8;
        const col = TYPE_COLORS[h.hex_type] || '#2a2420';
        const lbl = (h.label || '').slice(0, 8);
        return `<g>
          <path d="${hexPath(cx, cy)}" fill="${col}" stroke="#c9a54a44" stroke-width="0.8"/>
          ${lbl ? `<text x="${cx.toFixed(1)}" y="${(cy + 3).toFixed(1)}" text-anchor="middle" font-size="4.5" fill="#c8b87a88" style="pointer-events:none">${_esc(lbl)}</text>` : ''}
        </g>`;
    }).join('');
    return `<svg width="${svgW}" height="${svgH}" style="display:block">${paths}</svg>`;
}

async function selectHero(hero) {
    currentHero = hero;
    if (elements.welcomeUser) {
        elements.welcomeUser.textContent = `Bohater: ${hero.name}`;
    }
    try { localStorage.setItem('aigm_hero_id', hero.id); localStorage.removeItem('aigm_campaign_id'); } catch {}

    const status = hero.hero_status || hero.status || 'idle';
    if (status === 'idle') {
        _showIdleHeroPanel(hero);
        return;
    }
    await loadCampaigns();
    showScreen('campaigns');
}

function _showIdleHeroPanel(hero) {
    const panel = document.getElementById('idle-hero-panel');
    if (!panel) { _proceedFromIdlePanel(); return; }
    const sheet = (typeof hero.sheet_json === 'string' ? JSON.parse(hero.sheet_json || '{}') : hero.sheet_json) || {};

    // Identity
    const initial = (hero.name || '?')[0].toUpperCase();
    document.getElementById('idle-hero-panel-avatar').textContent = initial;
    document.getElementById('idle-hero-panel-name').textContent = hero.name || '—';
    const archetype = sheet.archetype || hero.archetype || '—';
    const level = sheet.level || 1;
    const hp = sheet.current_hp ?? sheet.max_hp ?? '?';
    const maxHp = sheet.max_hp ?? hp;
    document.getElementById('idle-hero-panel-meta').textContent = `${archetype} · Poziom ${level}`;

    // Stats row
    const xpAvail = sheet.xp_available || 0;
    const campaigns = hero.campaigns_completed ?? 0;
    document.getElementById('idle-hero-panel-stats').innerHTML = `
        <div class="idle-hero-stat"><span class="idle-hero-stat__val">${hp}/${maxHp}</span><span class="idle-hero-stat__label">HP</span></div>
        <div class="idle-hero-stat"><span class="idle-hero-stat__val">${xpAvail > 0 ? `+${xpAvail}` : (sheet.xp_lifetime || 0)}</span><span class="idle-hero-stat__label">${xpAvail > 0 ? 'PD dostępne' : 'PD ogółem'}</span></div>
        <div class="idle-hero-stat"><span class="idle-hero-stat__val">${campaigns}</span><span class="idle-hero-stat__label">Przygód</span></div>
    `;

    // Awansuj button
    const awansujBtn = document.getElementById('idle-hero-panel-awansuj');
    if (awansujBtn) {
        awansujBtn.hidden = xpAvail <= 0;
        awansujBtn.textContent = `⬆ Awansuj (${xpAvail} PD)`;
    }

    panel.hidden = false;
}

function _hideIdleHeroPanel() {
    const panel = document.getElementById('idle-hero-panel');
    if (panel) panel.hidden = true;
}

async function _proceedFromIdlePanel() {
    _hideIdleHeroPanel();
    await loadCampaigns();
    showScreen('campaigns');
}

// ============================================================================
// Campaigns
// ============================================================================
async function loadPendingMpInvites() {
    const section = document.getElementById('mp-invites-section');
    const list = document.getElementById('mp-invites-list');
    if (!section || !list) return;
    try {
        const [invData, lobbyData, activeData] = await Promise.all([
            apiRequest('GET', '/multiplayer/my-invites'),
            apiRequest('GET', '/multiplayer/my-lobbies'),
            apiRequest('GET', '/multiplayer/my-active-games'),
        ]);
        const invites = invData.invites || [];
        const lobbies = lobbyData.lobbies || [];
        const activeGames = activeData.games || [];
        if (invites.length === 0 && lobbies.length === 0 && activeGames.length === 0) { section.style.display = 'none'; return; }
        section.style.display = '';

        const lobbyHtml = lobbies.map(l => `
          <div class="mp-list-card mp-list-card--lobby">
            <div class="mp-list-card__icon">👥</div>
            <div class="mp-list-card__body">
              <div class="mp-list-card__title">${l.title}</div>
              <div class="mp-list-card__meta">${l.host_username} · ${l.accepted_count}/${l.max_players} graczy · lobby</div>
            </div>
            <div class="mp-list-card__actions">
              <button class="lf-invite-btn" onclick="_showLobbyScreen(${l.campaign_id})">Wejdź</button>
              ${l.role !== 'owner' ? `<button class="lf-invite-btn lf-invite-btn--muted" onclick="leaveMpLobby(${l.campaign_id})">Opuść</button>` : ''}
            </div>
          </div>`).join('');

        const inviteHtml = invites.map(inv => `
          <div class="mp-list-card mp-list-card--invite">
            <div class="mp-list-card__icon">⚔</div>
            <div class="mp-list-card__body">
              <div class="mp-list-card__title">${inv.title}</div>
              <div class="mp-list-card__meta">od @${inv.host_username} · ${inv.max_players} graczy</div>
            </div>
            <div class="mp-list-card__badge">zaproszenie</div>
            <div class="mp-list-card__actions">
              <button class="lf-invite-btn" onclick="acceptMpInvite(${inv.campaign_id})">Dołącz</button>
              <button class="lf-invite-btn lf-invite-btn--muted" onclick="declineMpInvite(${inv.campaign_id})">✕</button>
            </div>
          </div>`).join('');

        const activeHtml = activeGames.map(g => {
            const leaveLabel = g.role === 'owner' ? 'Zakończ' : 'Opuść';
            const leaveConfirm = g.role === 'owner'
                ? `Zakończyć sesję multiplayer dla wszystkich?`
                : `Opuścić sesję multiplayer?`;
            return `
          <div class="mp-list-card mp-list-card--active">
            <div class="mp-list-card__icon">⚔</div>
            <div class="mp-list-card__body">
              <div class="mp-list-card__title">${g.title}</div>
              <div class="mp-list-card__meta">${g.host_username} · ${g.player_count} graczy · w trakcie</div>
            </div>
            <div class="mp-list-card__actions">
              <button class="lf-invite-btn" onclick="enterMpGame(${g.campaign_id})">Graj</button>
              <button class="lf-invite-btn lf-invite-btn--muted" onclick="confirmLeaveMpGame(${g.campaign_id}, '${leaveConfirm}')">${leaveLabel}</button>
            </div>
          </div>`;
        }).join('');

        list.innerHTML = activeHtml + lobbyHtml + inviteHtml;
    } catch (e) {
        section.style.display = 'none';
    }
}

async function acceptMpInvite(campaignId) {
    try {
        await apiRequest('POST', `/multiplayer/campaigns/${campaignId}/accept`);
        await _showLobbyScreen(campaignId);
    } catch (e) {
        showToast('Nie udało się dołączyć: ' + e.message, 'error');
    }
}

async function declineMpInvite(campaignId) {
    try {
        await apiRequest('POST', `/multiplayer/campaigns/${campaignId}/decline`);
        await loadPendingMpInvites();
    } catch (e) {
        showToast('Błąd: ' + e.message, 'error');
    }
}

async function enterMpGame(campaignId) {
    if (!currentHero) { showToast('Wybierz bohatera przed wejściem do gry', 'error'); return; }
    try {
        const camp = await apiRequest('GET', `/campaigns/${campaignId}`);
        currentCampaignId = campaignId;
        currentCampaign = camp;
        characterData = {
            id: currentHero.id,
            name: currentHero.name,
            character_name: currentHero.name,
            user_id: currentHero.user_id ?? currentUser?.id,
            ...currentHero,
        };
        await enterGame(camp);
    } catch (e) {
        showToast('Błąd wejścia do gry: ' + e.message, 'error');
    }
}

async function confirmLeaveMpGame(campaignId, message) {
    if (!confirm(message || 'Opuścić sesję multiplayer?')) return;
    await leaveMpLobby(campaignId);
}

async function leaveMpLobby(campaignId) {
    try {
        await apiRequest('POST', `/multiplayer/campaigns/${campaignId}/decline`);
        localStorage.removeItem('aigm_lobby_id');
        await loadPendingMpInvites();
    } catch (e) {
        showToast('Błąd: ' + e.message, 'error');
    }
}

async function loadCampaigns() {
    console.log('[Campaigns] Loading for user:', currentUser?.id);
    loadPendingMpInvites();
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
    if (currentHero && currentHero.id) {
        // Hero already selected — create campaign immediately
        handleNewCampaignWithHero();
        return;
    }
    // No hero selected — send to heroes screen so the player picks one first.
    // The old new-campaign wizard (character creation) must not appear if heroes exist.
    showToast('Najpierw wybierz bohatera, aby stworzyć nową kampanię.', 'info', 3000);
    loadHeroes().then(() => showScreen('heroes'));
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
    if (!name) { showToast('Wprowadź nazwę kampanii', 'error'); return; }
    if (!currentUser?.id) { showToast('Nie jesteś zalogowany', 'error'); return; }

    _pendingCampaignTitle = name;
    _campaignStyleMode = 'solo';
    _selectedHookIds = [];
    _selectedTemplateId = null;
    _hookPoolAll = [];
    _hookTypeFilter = '';

    _selectCampaignStyle('solo');
    showScreen('campaignStyle');
    _initCampaignStyleScreen();
}

async function _initCampaignStyleScreen() {
    // Load hook pool and templates in parallel
    try {
        const [hooksRes, tplRes] = await Promise.allSettled([
            apiRequest('GET', '/campaign-templates/hooks/pool'),
            apiRequest('GET', '/campaign-templates'),
        ]);
        _hookPoolAll = hooksRes.status === 'fulfilled' ? (hooksRes.value?.items || []) : [];
        const templates = tplRes.status === 'fulfilled' ? (tplRes.value?.items || []) : [];
        _renderHookPool();
        _renderTemplateGrid(templates);
    } catch (_) {}
}

function _selectCampaignStyle(mode) {
    _campaignStyleMode = mode;
    const soloBtnEl = document.getElementById('style-btn-solo');
    const prebuiltBtnEl = document.getElementById('style-btn-prebuilt');
    const soloCheck = document.getElementById('style-check-solo');
    const prebuiltCheck = document.getElementById('style-check-prebuilt');
    const hookSection = document.getElementById('hook-picker-section');
    const tplSection = document.getElementById('template-picker-section');

    if (mode === 'solo') {
        soloBtnEl?.classList.add('adv-card--primary');
        prebuiltBtnEl?.classList.remove('adv-card--primary');
        if (soloCheck) soloCheck.style.display = '';
        if (prebuiltCheck) prebuiltCheck.style.display = 'none';
        if (hookSection) hookSection.style.display = '';
        if (tplSection) tplSection.style.display = 'none';
        _selectedTemplateId = null;
    } else {
        prebuiltBtnEl?.classList.add('adv-card--primary');
        soloBtnEl?.classList.remove('adv-card--primary');
        if (prebuiltCheck) prebuiltCheck.style.display = '';
        if (soloCheck) soloCheck.style.display = 'none';
        if (tplSection) tplSection.style.display = '';
        if (hookSection) hookSection.style.display = 'none';
        _selectedHookIds = [];
    }
}

function _renderHookPool() {
    const typeFilters = document.getElementById('hook-type-filters');
    const grid = document.getElementById('hook-pool-grid');
    if (!typeFilters || !grid) return;

    const types = [...new Set(_hookPoolAll.map(h => h.hook_type))];
    const typeLabels = { weapon:'⚔ Broń', enemy:'💀 Wrogowie', npc:'👤 NPC', location:'🗺 Lokacje', item:'🎒 Przedmioty', consumable:'🧪 Konsumpcja', armor:'🛡 Zbroja', event:'⚡ Zdarzenia', theme:'💡 Tematy' };

    typeFilters.innerHTML = `<button class="chip${_hookTypeFilter==='' ? ' chip--active':''}" onclick="_filterHookPool('')">Wszystkie</button>`
        + types.map(t => `<button class="chip${_hookTypeFilter===t?' chip--active':''}" onclick="_filterHookPool('${t}')">${typeLabels[t]||t}</button>`).join('');

    const visible = _hookTypeFilter ? _hookPoolAll.filter(h => h.hook_type === _hookTypeFilter) : _hookPoolAll;

    if (!visible.length) {
        grid.innerHTML = '<p style="font-size:0.78rem;color:var(--text-secondary);text-align:center;padding:12px 0">Brak dostępnych wątków.</p>';
        return;
    }

    grid.innerHTML = visible.map(h => {
        const sel = _selectedHookIds.includes(h.id);
        return `<button type="button" class="adv-card${sel?' adv-card--primary':''}" onclick="_toggleHook(${h.id})" style="opacity:${!sel && _selectedHookIds.length>=5?0.45:1}">
          <span class="adv-card__icon">${typeLabels[h.hook_type]?.split(' ')[0]||'📌'}</span>
          <div class="adv-card__body"><h3>${h.title}</h3><p>${(h.description||'').substring(0,100)}</p></div>
          ${sel ? '<span style="color:var(--accent)">✓</span>' : ''}
        </button>`;
    }).join('');
}

function _filterHookPool(type) {
    _hookTypeFilter = type;
    _renderHookPool();
}

function _toggleHook(id) {
    if (_selectedHookIds.includes(id)) {
        _selectedHookIds = _selectedHookIds.filter(x => x !== id);
    } else if (_selectedHookIds.length < 5) {
        _selectedHookIds.push(id);
    }
    _renderHookPool();
}

function _renderTemplateGrid(templates) {
    const grid = document.getElementById('template-pool-grid');
    if (!grid) return;
    if (!templates.length) {
        grid.innerHTML = '<p style="font-size:0.78rem;color:var(--text-secondary);text-align:center;padding:12px 0">Brak gotowych przygód.</p>';
        return;
    }
    const diffLabels = ['','★','★★','★★★','★★★★','★★★★★'];
    grid.innerHTML = templates.map(t => {
        const sel = _selectedTemplateId === t.id;
        return `<button type="button" class="adv-card${sel?' adv-card--primary':''}" onclick="_selectTemplate(${t.id})">
          <span class="adv-card__icon">📖</span>
          <div class="adv-card__body">
            <h3>${t.title}</h3>
            <p>${(t.description||'').substring(0,120)}</p>
            <p style="font-size:0.72rem;margin-top:4px;color:var(--text-secondary)">${diffLabels[t.difficulty_rating]||''} ${t.atmosphere||''}</p>
          </div>
          ${sel ? '<span style="color:var(--accent)">✓</span>' : ''}
        </button>`;
    }).join('');
}

function _selectTemplate(id) {
    _selectedTemplateId = _selectedTemplateId === id ? null : id;
    const grid = document.getElementById('template-pool-grid');
    if (!grid) return;
    grid.querySelectorAll('.adv-card').forEach((btn, i) => {
        const isSelected = parseInt(btn.getAttribute('onclick')?.match(/\d+/)?.[0]) === _selectedTemplateId;
        btn.classList.toggle('adv-card--primary', isSelected);
        const check = btn.querySelector('span:last-child');
        if (check && check !== btn.querySelector('.adv-card__icon') && check !== btn.querySelector('.adv-card__body')) {
            check.remove();
        }
        if (isSelected) btn.insertAdjacentHTML('beforeend', '<span style="color:var(--accent)">✓</span>');
    });
}

async function _finalCreateCampaign() {
    if (!currentUser?.id) { showToast('Nie jesteś zalogowany', 'error'); return; }
    if (_campaignStyleMode === 'pre_built' && !_selectedTemplateId) {
        showToast('Wybierz gotową przygodę lub wróć do poprzedniej opcji', 'error');
        return;
    }

    const btn = document.getElementById('campaign-style-submit');
    if (btn) btn.disabled = true;
    const loadingToast = showToast('Tworzę kampanię…', 'info', 0);
    try {
        const payload = {
            title: _pendingCampaignTitle,
            system_id: 'fantasy',
            model_id: 'default',
            owner_user_id: currentUser.id,
            language: 'pl',
            mode: _campaignStyleMode === 'pre_built' ? 'pre_built' : 'solo',
            status: 'active',
        };
        if (_campaignStyleMode === 'solo' && _selectedHookIds.length) {
            payload.selected_hook_ids = _selectedHookIds;
        }
        if (_campaignStyleMode === 'pre_built' && _selectedTemplateId) {
            payload.template_id = _selectedTemplateId;
        }

        const campaign = await apiRequest('POST', '/campaigns', payload);
        currentCampaignId = campaign.id;
        currentCampaign = campaign;
        loadingToast?.remove?.();
        startCharacterWizard();
    } catch (error) {
        loadingToast?.remove?.();
        showToast(error.message || 'Nie udało się utworzyć kampanii', 'error');
        if (btn) btn.disabled = false;
    }
}

// ============================================================================
// Prebuilt Campaign Screen — "Gotowa Kampania" flow
// ============================================================================
let _prebuiltTemplates = [];
let _selectedPrebuiltId = null;

async function openPrebuiltCampaignScreen() {
    if (!currentUser?.id) { showToast('Nie jesteś zalogowany', 'error'); return; }
    _selectedPrebuiltId = null;
    showScreen('prebuiltCampaign');
    const grid = document.getElementById('prebuilt-grid');
    const loading = document.getElementById('prebuilt-loading');
    const confirm = document.getElementById('prebuilt-confirm');
    if (confirm) confirm.style.transform = 'translateY(100%)';
    if (loading) loading.style.display = '';
    if (grid) grid.innerHTML = '';
    try {
        const d = await apiRequest('GET', '/campaign-templates');
        _prebuiltTemplates = d.items || [];
        if (loading) loading.style.display = 'none';
        if (!_prebuiltTemplates.length) {
            if (grid) grid.innerHTML = '<p style="text-align:center;color:var(--text-secondary);padding:40px 0;font-size:0.85rem">Brak gotowych kampanii.<br>Administrator nie opublikował jeszcze żadnego scenariusza.</p>';
            return;
        }
        _renderPrebuiltGrid();
    } catch(e) {
        if (loading) loading.style.display = 'none';
        if (grid) grid.innerHTML = `<p style="text-align:center;color:var(--text-secondary);padding:40px 0;font-size:0.85rem">Błąd ładowania: ${e.message}</p>`;
    }
}

function _renderPrebuiltGrid() {
    const grid = document.getElementById('prebuilt-grid');
    if (!grid) return;
    const diffLabels = ['','★','★★','★★★','★★★★','★★★★★'];
    // Rarity border color by level
    const RARITY_COLOR = ['','#4a4540','#3a7a4a','#3a5a8a','#b8902a','#7a3a9a'];
    const RARITY_LABEL = ['','Pospolity','Niepospolity','Rzadki','Epicki','Legendarny'];
    const TYPE_EMOJI = { weapon:'⚔', consumable:'🧪', item:'🛡', armor:'🛡' };
    const TYPE_LABEL = { weapon:'Broń', consumable:'Mikstura', item:'Przedmiot', armor:'Zbroja' };

    grid.innerHTML = _prebuiltTemplates.map(t => {
        const actCount = t.gm_plan_json?.acts?.length || 0;
        const items = t.campaign_items || [];

        const itemChips = items.length ? `
          <div class="prebuilt-items-row">
            <span class="prebuilt-items-label">Przedmioty kampanii:</span>
            <div class="prebuilt-chips">
              ${items.map(it => {
                  const emoji = TYPE_EMOJI[it.entry_type] || '📦';
                  const rc = RARITY_COLOR[it.rarity] || RARITY_COLOR[1];
                  const safeData = JSON.stringify(it).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'&quot;');
                  return `<button class="item-chip" style="--chip-border:${rc}" onclick="showItemPopup(this,event)" data-item="${safeData}" title="${_esc(it.label)}">
                    <span>${emoji}</span>
                    <span class="item-chip__name">${_esc(it.label)}</span>
                  </button>`;
              }).join('')}
            </div>
          </div>` : '';

        return `<div class="adv-card prebuilt-campaign-card" style="align-items:flex-start;padding:14px 16px;gap:10px;display:flex;flex-direction:column;cursor:default">
          <div style="display:flex;gap:12px;width:100%">
            <span class="adv-card__icon" style="font-size:1.5rem;flex-shrink:0">📖</span>
            <div class="adv-card__body" style="flex:1;min-width:0">
              <h3 style="margin-bottom:4px">${_esc(t.title)}</h3>
              <p style="margin-bottom:6px">${_esc((t.description||'').substring(0,140))}${(t.description||'').length>140?'…':''}</p>
              <div style="display:flex;gap:8px;flex-wrap:wrap;font-size:0.7rem;color:var(--text-secondary)">
                ${diffLabels[t.difficulty_rating] ? `<span>${diffLabels[t.difficulty_rating]}</span>` : ''}
                ${t.atmosphere ? `<span>· ${_esc(t.atmosphere)}</span>` : ''}
                ${actCount ? `<span>· ${actCount} aktów</span>` : ''}
                ${t.play_count ? `<span>· 🎮 ${t.play_count}×</span>` : ''}
              </div>
            </div>
          </div>
          ${itemChips}
          <button type="button" class="btn btn--primary" style="width:100%;margin-top:2px" onclick="_launchPrebuiltById(${t.id})">
            🚀 Zagraj
          </button>
        </div>`;
    }).join('');
}

const _RARITY_LABEL = ['','Pospolity','Niepospolity','Rzadki','Epicki','Legendarny'];
const _RARITY_GLOW  = ['','rgba(74,69,64,.6)','rgba(58,122,74,.5)','rgba(58,90,138,.5)','rgba(184,144,42,.5)','rgba(122,58,154,.5)'];
const _RARITY_COLOR = ['','#6b665e','#4a9a5a','#5a80c0','#c9a54a','#b06adc'];
const _TYPE_LABEL_PL = { weapon:'Broń', consumable:'Mikstura', item:'Przedmiot', armor:'Zbroja' };

function showItemPopup(chip, event) {
    event.stopPropagation();
    _closeItemPopup();
    const item = JSON.parse(chip.dataset.item.replace(/&quot;/g,'"'));
    const rColor = _RARITY_COLOR[item.rarity] || _RARITY_COLOR[1];
    const rGlow  = _RARITY_GLOW[item.rarity]  || _RARITY_GLOW[1];
    const rLabel = _RARITY_LABEL[item.rarity]  || '';
    const typePL = _TYPE_LABEL_PL[item.entry_type] || item.entry_type;
    const statLine = [
        item.damage_die ? `<span class="ip-stat">⚡ ${_esc(item.damage_die)}</span>` : '',
        item.effect_type ? `<span class="ip-stat">✦ ${_esc(item.effect_type)}</span>` : '',
    ].filter(Boolean).join('');

    const popup = document.createElement('div');
    popup.id = 'item-popup';
    popup._chip = chip;
    popup.innerHTML = `
      <div class="ip-glow" style="--ip-glow:${rGlow}"></div>
      <div class="ip-accent-line" style="background:${rColor}"></div>
      <div class="ip-header">
        <span class="ip-type" style="color:${rColor}">${typePL}</span>
        <button class="ip-close" onclick="_closeItemPopup()">✕</button>
      </div>
      <div class="ip-name">${_esc(item.label)}</div>
      ${statLine ? `<div class="ip-stats">${statLine}</div>` : ''}
      <div class="ip-rarity" style="color:${rColor}">◆ ${rLabel}</div>
      ${item.description ? `<div class="ip-desc">${_esc(item.description)}</div>` : ''}
    `;
    document.body.appendChild(popup);

    // Position: on mobile (< 600px) — bottom sheet; on desktop — near chip
    const isMobile = window.innerWidth < 600;
    if (!isMobile) {
        const rect = chip.getBoundingClientRect();
        const popupW = 260;
        let left = rect.left;
        if (left + popupW > window.innerWidth - 12) left = window.innerWidth - popupW - 12;
        popup.style.position = 'fixed';
        popup.style.left = left + 'px';
        popup.style.top = (rect.top - 8) + 'px';
        popup.style.transform = 'translateY(-100%)';
        popup.classList.add('ip--desktop');
    } else {
        popup.classList.add('ip--sheet');
        requestAnimationFrame(() => popup.classList.add('ip--sheet-open'));
    }
    chip.classList.add('item-chip--active');

    // Close on outside click
    setTimeout(() => {
        document.addEventListener('click', _closeItemPopup, { once: true });
    }, 0);
}

function _closeItemPopup() {
    const p = document.getElementById('item-popup');
    if (p) {
        document.querySelectorAll('.item-chip--active').forEach(c => c.classList.remove('item-chip--active'));
        if (p.classList.contains('ip--sheet')) {
            p.classList.remove('ip--sheet-open');
            setTimeout(() => p.remove(), 280);
        } else {
            p.remove();
        }
    }
}

function _pickPrebuilt(id) {
    _selectedPrebuiltId = id;
}

async function _launchPrebuiltById(id) {
    _selectedPrebuiltId = id;
    const tpl = _prebuiltTemplates.find(t => t.id === id);
    await _launchPrebuiltCampaign(tpl?.title || 'Kampania');
}

async function _launchPrebuiltCampaign(title) {
    if (!currentUser?.id || !_selectedPrebuiltId) return;
    title = title || _prebuiltTemplates.find(t => t.id === _selectedPrebuiltId)?.title || 'Kampania';
    const btn = document.querySelector(`#prebuilt-grid button[onclick="_launchPrebuiltById(${_selectedPrebuiltId})"]`);
    if (btn) { btn.disabled = true; btn.innerHTML = '⏳'; }
    const loadingToast = showToast('Tworzę kampanię…', 'info', 0);
    try {
        const campaign = await apiRequest('POST', '/campaigns', {
            title,
            system_id: 'fantasy',
            model_id: 'default',
            owner_user_id: currentUser.id,
            language: 'pl',
            mode: 'pre_built',
            status: 'active',
            template_id: _selectedPrebuiltId,
            selected_hook_ids: []
        });
        loadingToast?.remove?.();
        // Use existing hero if selected — assign & enter game directly, no wizard
        await selectCampaign(campaign);
    } catch(e) {
        loadingToast?.remove?.();
        showToast(e.message || 'Nie udało się utworzyć kampanii', 'error');
        if (btn) { btn.disabled = false; btn.innerHTML = '🚀 Zagraj'; }
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
    wizardStatsRevealed = false;
    wizardSkillsRevealed = false;
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
    // Show dice animation the first time stats are revealed this session
    if (!wizardStatsRevealed) { _renderStep2Dice(c); return; }

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
        <div class="wizard-form wiz-stats-reveal">
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

function _renderStep2Dice(c) {
    const STATS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA', 'LCK'];
    const STAT_PL = { STR:'Siła', DEX:'Zręczność', CON:'Kondycja', INT:'Intelekt', WIS:'Mądrość', CHA:'Charyzma', LCK:'Szczęście' };

    c.innerHTML = `
        <div class="wiz-dice-stage">
            <div class="wiz-dice-header">
                <div class="wiz-dice-header-icon">🎲</div>
                <h3>Kości rzucone…</h3>
                <p>Los decyduje o losie bohatera</p>
            </div>
            <div class="wiz-dice-grid">
                ${STATS.map(s => `
                    <div class="wiz-dice-item">
                        <div class="wiz-dice-face" id="wdice-${s}">?</div>
                        <span class="wiz-dice-stat-abbr">${s}</span>
                        <span class="wiz-dice-stat-name">${STAT_PL[s]}</span>
                    </div>`).join('')}
            </div>
        </div>`;

    // Cycle random numbers on each die face
    const timers = {};
    STATS.forEach(s => {
        const face = document.getElementById(`wdice-${s}`);
        if (face) timers[s] = setInterval(() => { face.textContent = Math.floor(Math.random() * 18) + 1; }, 75);
    });

    // Settle each die staggered (800ms initial delay, 180ms apart)
    STATS.forEach((s, i) => {
        setTimeout(() => {
            const face = document.getElementById(`wdice-${s}`);
            if (!face) return;
            clearInterval(timers[s]);
            face.textContent = wizardStatBases[s] ?? (s === 'LCK' ? 8 : 10);
            face.classList.add('settled');
        }, 800 + i * 180);
    });

    // After all settled + brief pause, switch to stat grid
    setTimeout(() => {
        wizardStatsRevealed = true;
        _renderStep2(c);
    }, 800 + STATS.length * 180 + 650);
}

// Step 3 — dice reveal + card-based skill layout with pool drawer
function _rankDots(rank) {
    const on = '<span class="wiz-rdot wiz-rdot--on">●</span>';
    const off = '<span class="wiz-rdot">○</span>';
    return rank >= 2 ? on+on : rank >= 1 ? on+off : off+off;
}

function _getSlotRows() {
    const archetype = wizardCreatedChar?.sheet_json?.archetype || 'warrior';
    const preferred = new Set(ARCHETYPE_PREFERRED[archetype] || []);
    return ALL_SKILL_ROWS
        .filter(r => Number(wizardSkillSnapshot[r.key] || 0) > 0)
        .sort((a, b) => {
            const dr = Number(wizardSkillSnapshot[b.key] || 0) - Number(wizardSkillSnapshot[a.key] || 0);
            if (dr !== 0) return dr;
            return (preferred.has(b.key) ? 1 : 0) - (preferred.has(a.key) ? 1 : 0);
        })
        .slice(0, 7);
}

function _renderStep3Reveal(c) {
    const slotRows = _getSlotRows();
    c.innerHTML = `
        <div class="wiz-dice-stage">
            <div class="wiz-dice-header">
                <div class="wiz-dice-header-icon">🎯</div>
                <h3>Los wyznacza twoje talenty…</h3>
                <p>Kości decydują o umiejętnościach bohatera</p>
            </div>
            <div class="wiz-dice-grid">
                ${slotRows.map((r, i) => `
                    <div class="wiz-dice-item">
                        <div class="wiz-dice-face${i < WIZARD_LOCKED_COUNT ? ' wiz-dice-face--gold' : ''}" id="sdice-${r.key}">?</div>
                        <span class="wiz-dice-stat-abbr">${r.stat}</span>
                        <span class="wiz-dice-stat-name">${i < WIZARD_LOCKED_COUNT ? '🔒' : '↔'}</span>
                    </div>`).join('')}
            </div>
        </div>`;

    const timers = {};
    slotRows.forEach(r => {
        const face = document.getElementById(`sdice-${r.key}`);
        if (face) timers[r.key] = setInterval(() => { face.textContent = Math.floor(Math.random() * 6) + 1; }, 75);
    });
    slotRows.forEach((r, i) => {
        setTimeout(() => {
            const face = document.getElementById(`sdice-${r.key}`);
            if (!face) return;
            clearInterval(timers[r.key]);
            face.textContent = Number(wizardSkillSnapshot[r.key] || 1);
            face.classList.add('settled');
        }, 700 + i * 160);
    });
    setTimeout(() => {
        wizardSkillsRevealed = true;
        _renderStep3(c);
    }, 700 + slotRows.length * 160 + 600);
}

function _renderStep3(c) {
    if (!wizardSkillsRevealed) { _renderStep3Reveal(c); return; }

    const archetype = wizardCreatedChar?.sheet_json?.archetype || 'warrior';
    const archPool  = ARCHETYPE_SKILL_POOL[archetype] || ARCHETYPE_SKILL_POOL.warrior;
    const budgetUsed = _skillBudgetUsed();
    const slotRows = _getSlotRows();

    const visibleKeys = new Set(slotRows.map(r => wizardSkillSwapMap[r.key] || r.key));
    const candidates = ALL_SKILL_ROWS
        .filter(r => archPool.has(r.key) && !visibleKeys.has(r.key))
        .sort((a, b) => a.label.localeCompare(b.label));

    const buildCard = ({ key: origKey }, slotIndex) => {
        const isLocked  = slotIndex < WIZARD_LOCKED_COUNT;
        const isSwapped = origKey in wizardSkillSwapMap;
        const currentKey = isSwapped ? wizardSkillSwapMap[origKey] : origKey;
        const curRow = _skillRow(currentKey);
        const inPool  = !isLocked && wizardSwapModeSlot === origKey;
        const rank    = wizardSkillLevels[origKey] ?? Number(wizardSkillSnapshot[origKey] || 0);
        const changed = isSwapped || rank !== Number(wizardSkillSnapshot[origKey] || 0);
        const canPlus  = _canAdjSkill(origKey, 1);
        const canMinus = _canAdjSkill(origKey, -1);

        const rankCtrl = `
            <div class="wiz-scard-rank-ctrl">
                <button class="wiz-scard-rank-btn" data-skill-dir="-" data-orig="${origKey}" ${canMinus?'':'disabled'}>−</button>
                <span class="wiz-scard-rank-num">${rank}</span>
                <button class="wiz-scard-rank-btn" data-skill-dir="+" data-orig="${origKey}" ${canPlus?'':'disabled'}>+</button>
            </div>`;

        let actionEl;
        if (isLocked)       actionEl = `<span class="wiz-scard-lock" title="Umiejętność podstawowa">🔒</span>`;
        else if (isSwapped) actionEl = `<button class="wiz-scard-revert-btn" data-revert="${origKey}" title="Cofnij zamianę">↩</button>`;
        else                actionEl = `<button class="wiz-scard-swap-btn" data-swap="${origKey}" title="Wymień umiejętność z puli">↔</button>`;

        const poolHtml = inPool ? `
            <div class="wiz-scard-pool">
                <span class="wiz-scard-pool-label">Wybierz z puli archetypu:</span>
                <div class="wiz-scard-pool-chips">
                    ${candidates.map(cd => `
                        <button class="wiz-pool-chip" data-replace="${origKey}" data-new="${cd.key}">
                            ${_esc(cd.label)}<span class="wiz-pool-chip-stat">${cd.stat}</span>
                        </button>`).join('')}
                    ${!candidates.length ? '<span class="wiz-pool-empty">Brak dostępnych umiejętności</span>' : ''}
                </div>
                <button class="wiz-scard-pool-cancel" data-cancel-swap="${origKey}">✕ Anuluj</button>
            </div>` : '';

        return `
            <div class="wiz-scard${isLocked?' wiz-scard--locked':' wiz-scard--swap'}${changed?' wiz-scard--changed':''}${inPool?' wiz-scard--open':''}"
                 data-orig="${origKey}" style="--deal-i:${slotIndex}">
                <div class="wiz-scard-body">
                    <div class="wiz-scard-main">
                        <span class="wiz-scard-name">${_esc(curRow.label)}</span>
                        <span class="wiz-scard-stat">${curRow.stat}</span>
                    </div>
                    <div class="wiz-scard-foot">
                        <span class="wiz-scard-dots">${_rankDots(rank)}</span>
                        ${rankCtrl}
                        ${actionEl}
                    </div>
                </div>
                ${poolHtml}
            </div>`;
    };

    const lockedCards = slotRows.slice(0, WIZARD_LOCKED_COUNT).map(buildCard).join('');
    const swapCards   = slotRows.slice(WIZARD_LOCKED_COUNT).map((r, i) => buildCard(r, i + WIZARD_LOCKED_COUNT)).join('');

    c.innerHTML = `
        <div class="wiz-skill-deck wiz-stats-reveal">
            <div class="wiz-sdeck-hdr wiz-sdeck-hdr--locked">
                <span>🔒 Podstawowe</span>
                <span class="wiz-sdeck-count">${WIZARD_LOCKED_COUNT} sloty</span>
            </div>
            ${lockedCards}
            <div class="wiz-sdeck-hdr wiz-sdeck-hdr--swap">
                <span>↔ Wymienne</span>
                <span class="wiz-sdeck-count">${slotRows.length - WIZARD_LOCKED_COUNT} sloty · Poziomy: ${budgetUsed}/${WIZARD_MAX_SWAPS}</span>
            </div>
            ${swapCards}
            <button type="button" class="btn btn--secondary wizard-reset-btn" id="wiz-skill-reset" style="margin-top:10px">Reset</button>
        </div>
    `;

    c.querySelectorAll('[data-swap]').forEach(btn =>
        btn.addEventListener('click', () => { wizardSwapModeSlot = btn.dataset.swap; _renderStep3(c); }));
    c.querySelectorAll('[data-cancel-swap]').forEach(btn =>
        btn.addEventListener('click', () => { wizardSwapModeSlot = null; _renderStep3(c); }));
    c.querySelectorAll('[data-replace]').forEach(btn =>
        btn.addEventListener('click', () => {
            if (!btn.dataset.new) return;
            wizardSkillSwapMap[btn.dataset.replace] = btn.dataset.new;
            wizardSwapModeSlot = null;
            _renderStep3(c);
        }));
    c.querySelectorAll('[data-revert]').forEach(btn =>
        btn.addEventListener('click', () => {
            delete wizardSkillSwapMap[btn.dataset.revert];
            wizardSwapModeSlot = null;
            _renderStep3(c);
        }));
    c.querySelectorAll('[data-skill-dir]').forEach(btn =>
        btn.addEventListener('click', () => {
            const origKey = btn.dataset.orig;
            const delta = btn.dataset.skillDir === '+' ? 1 : -1;
            if (!_canAdjSkill(origKey, delta)) return;
            const cur = wizardSkillLevels[origKey] ?? Number(wizardSkillSnapshot[origKey] || 0);
            wizardSkillLevels[origKey] = cur + delta;
            _renderStep3(c);
        }));
    document.getElementById('wiz-skill-reset')?.addEventListener('click', () => {
        wizardSkillLevels = {};
        wizardSkillSwapMap = {};
        wizardSwapModeSlot = null;
        _renderStep3(c);
    });
}

// Step 4 — Identity review — old-book visual, auto-resize textareas, no type dropdowns
const BOND_TYPE_LABELS   = {person:'Osoba',place:'Miejsce',object:'Przedmiot',ideal:'Ideał'};
const WEAKNESS_TYPE_LABELS = {fear:'Strach',flaw:'Wada',addiction:'Nałóg',trauma:'Trauma'};

function _renderStep4(c) {
    const p = wizardIdentityPreview;
    if (!p) {
        c.innerHTML = `<div class="wiz-tome-loading">
            <div class="wiz-tome-quill">🪶</div>
            <p>GM konsultuje starsze, mroczniejsze księgi…</p>
        </div>`;
        return;
    }
    const bonds     = p.bonds     || [{description:p.bond||'',type:'person'},{description:'',type:'ideal'}];
    const weaknesses= p.weaknesses|| [{description:p.flaw||'',type:'flaw'}, {description:'',type:'fear'}];

    const bondsHtml = bonds.slice(0,2).map((b,i) => {
        const typeLabel = BOND_TYPE_LABELS[b.type] || 'Więź';
        return `
        <div class="wiz-tome-entry">
            <span class="wiz-tome-entry-badge wiz-tome-entry-badge--bond">${typeLabel}</span>
            <textarea id="wiz-bond-${i}" class="wiz-tome-textarea" data-bond-type="${b.type||'ideal'}"
                placeholder="Opisz więź…">${_esc(b.description||'')}</textarea>
        </div>`;
    }).join('');

    const weakHtml = weaknesses.slice(0,2).map((w,i) => {
        const typeLabel = WEAKNESS_TYPE_LABELS[w.type] || 'Słabość';
        return `
        <div class="wiz-tome-entry">
            <span class="wiz-tome-entry-badge wiz-tome-entry-badge--flaw">${typeLabel}</span>
            <textarea id="wiz-weak-${i}" class="wiz-tome-textarea" data-weak-type="${w.type||'flaw'}"
                placeholder="Opisz słabość…">${_esc(w.description||'')}</textarea>
        </div>`;
    }).join('');

    c.innerHTML = `
        <div class="wiz-tome-page">
            <div class="wiz-tome-section">
                <h4 class="wiz-tome-label">Wygląd</h4>
                <textarea id="wiz-appearance" class="wiz-tome-textarea"
                    placeholder="Jak wygląda twój bohater?">${_esc(p.appearance||'')}</textarea>
            </div>
            <div class="wiz-tome-divider">✦</div>
            <div class="wiz-tome-section">
                <h4 class="wiz-tome-label">Osobowość</h4>
                <textarea id="wiz-personality" class="wiz-tome-textarea"
                    placeholder="Jak zachowuje się twój bohater?">${_esc(p.personality||'')}</textarea>
            </div>
            <div class="wiz-tome-divider">✦</div>
            <div class="wiz-tome-section">
                <h4 class="wiz-tome-label">Więzi</h4>
                ${bondsHtml}
            </div>
            <div class="wiz-tome-divider">✦</div>
            <div class="wiz-tome-section">
                <h4 class="wiz-tome-label">Słabości</h4>
                ${weakHtml}
            </div>
            <p class="wiz-tome-secret">🔒 GM zna też to, o czym sam nie wiesz. Objawi się w swoim czasie.</p>
        </div>
    `;

    // Auto-resize all textareas to fit content
    c.querySelectorAll('.wiz-tome-textarea').forEach(ta => {
        const resize = () => { ta.style.height = 'auto'; ta.style.height = (ta.scrollHeight + 2) + 'px'; };
        resize();
        ta.addEventListener('input', resize);
    });
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
    wizardStepNum = 3;
    elements.wizardStep.textContent = WIZARD_STEPS[3].subtitle;
    elements.wizardTitle.textContent = WIZARD_STEPS[3].title;
    elements.btnWizardPrev.style.display = 'block';
    elements.btnWizardNext.innerHTML = 'Rozpocznij przygodę <span class="btn__icon">✨</span>';
    elements.btnWizardNext.disabled = true;

    // Immersive loading state — GM is writing the identity
    elements.wizardContent.innerHTML = `
        <div class="wiz-tome-loading">
            <div class="wiz-tome-quill">🪶</div>
            <h3>Mistrz Gry kreuje twą historię</h3>
            <p>Starożytne karty zapisują przeznaczenie…</p>
            <div class="wiz-tome-loading-dots"><span></span><span></span><span></span></div>
        </div>`;

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

    const bonds = [0,1].map(i => {
        const el = document.getElementById(`wiz-bond-${i}`);
        return { description: el?.value?.trim() || '', type: el?.dataset?.bondType || 'ideal' };
    }).filter(b => b.description);

    const weaknesses = [0,1].map(i => {
        const el = document.getElementById(`wiz-weak-${i}`);
        return { description: el?.value?.trim() || '', type: el?.dataset?.weakType || 'flaw' };
    }).filter(w => w.description);

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
    if (el) {
        if (!state || typeof state.display !== 'string') {
            el.textContent = '';
            el.hidden = true;
        } else {
            el.textContent = state.display;
            el.hidden = false;
            el.dataset.period = state.period || '';
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

async function enterGame(campaign) {
    // Persist session so F5 restores to this exact state
    try {
        if (currentHero?.id) localStorage.setItem('aigm_hero_id', currentHero.id);
        if (campaign?.id) localStorage.setItem('aigm_campaign_id', campaign.id);
    } catch {}

    window.multiplayerUI?.deactivate();

    const sheet = characterData?.sheet_json || characterData || {};
    elements.characterNameDisplay.textContent = characterData?.name || 'Bohater';
    const level = sheet.level || characterData?.level || 1;
    const hp = sheet.current_hp ?? characterData?.hp ?? 29;
    const maxHp = sheet.max_hp ?? characterData?.max_hp ?? 29;
    elements.characterStatsDisplay.textContent = `${hp}/${maxHp} HP`;
    elements.chatMessages.innerHTML = '';
    document.getElementById('skill-roll-popup')?.remove();
    const _diceOverlayEl = document.getElementById('dice-overlay');
    if (_diceOverlayEl) _diceOverlayEl.hidden = true;

    // T5 — fetch initial clock state and render in header
    // Visual overlay settings loaded in parallel; clock render also applies overlay
    Promise.all([loadVisualSettings(), Promise.resolve()]).then(() => {
        fetchAndRenderClock(campaign.id);
    });

    let turns = [];
    let combatRows = [];
    try {
        const [response, combatHist] = await Promise.all([
            apiRequest('GET', `/campaigns/${campaign.id}/turns`),
            fetch(`/api/campaigns/${campaign.id}/combat/turns/history`, { cache: 'no-store' }).then(r => r.ok ? r.json() : { turns: [] }).catch(() => ({ turns: [] })),
        ]);
        turns = response.turns || (Array.isArray(response) ? response : []);
        combatRows = Array.isArray(combatHist.turns) ? combatHist.turns : [];
    } catch (error) {
        console.error('Failed to load chat history:', error);
        // Leave turns/combatRows empty — empty-timeline branch will trigger __AI_GM_OPEN
    }

    try {
        // J3 — init badge counter from existing narrative turn count mod 10
        _journalBadgeTurns = turns.filter(t => t.route === 'narrative').length % 10;

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
                    // Skill test rich format: "[Rzut: Skill — d20 +mod = total[ vs key: d20 +mod = total] — Outcome]"
                    let displayText = utext;
                    // Group 6 optionally captures " vs perception: 5 +2 = 7" for opposed checks
                    const richM = utext.match(/^\[Rzut:\s*(.+?)\s*[—-]\s*(\d+)\s*([+\-−])\s*(\d+)\s*=\s*(\d+)((?:\s+vs\s+[^—-]+)?)\s*[—-]\s*(.+?)\]$/);
                    const simpleM = !richM && utext.match(/^\[Rzut:\s*(.+?)\s*[—-]\s*(\d+)\]$/);
                    if (richM) {
                        const sign = richM[3] === '−' ? '−' : richM[3];
                        const oppSuffix = richM[6] ? richM[6].trim() : '';
                        displayText = `🎲 ${richM[1]}: ${richM[2]} ${sign}${richM[4]} = ${richM[5]}${oppSuffix ? ' ' + oppSuffix : ''} — ${richM[7]}`;
                    } else if (simpleM) {
                        displayText = `🎲 ${simpleM[1]}: rzut ${simpleM[2]}`;
                    }
                    const rollRole = (richM || simpleM) ? 'roll' : 'user';
                    appendMessage({ role: rollRole, content: displayText, created_at: turn.created_at, turn_number: turn.turn_number, route: turn.route, turn_id: turn.id }, { autoSpeak: false });
                }
                if (turn.assistant_text) {
                    const { narrative: gmContent, ...gmMeta } = parseGmFull(turn.assistant_text);
                    if (gmContent && gmContent.trim()) {
                        appendMessage({ role: 'assistant', content: gmContent, created_at: turn.created_at, turn_number: turn.turn_number, route: turn.route, debugMeta: gmMeta, turn_id: turn.id }, { autoSpeak: false });
                    }
                }
            }
        } else if (campaign?.mode === 'multiplayer') {
            // MP campaign — no solo turns, skip __AI_GM_OPEN, just show game screen
            showScreen('game');
            updateAdminSettingsVisibility();
            if (characterData) populateCharacterSheet(characterData);
            scrollToBottom();
            if (characterData?.id) {
                const isHost = campaign.host_user_id === (currentUser?.id);
                const timerMin = campaign.round_timer_minutes || ((campaign.round_timer_hours || 24) * 60);
                window.multiplayerUI?.activate(campaign.id, characterData.id, characterData.name || 'Bohater', isHost, timerMin);
            }
            return;
        } else {
            // No turns yet — new solo campaign. Send an empty opening turn to trigger plan gen + opening scene
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
    if (campaign?.mode === 'multiplayer' && characterData?.id) {
        const isHost = campaign.host_user_id === (currentUser?.id);
        const timerMin = campaign.round_timer_minutes || ((campaign.round_timer_hours || 24) * 60);
        window.multiplayerUI?.activate(campaign.id, characterData.id, characterData.name || 'Bohater', isHost, timerMin);
    }
    startCombatPolling();

    // Stage 10-C+ Bug 1 fix — on F5 / resume, the campaign GET payload carries
    // any pending_skill_test. Re-mount the roll popup so the player can't
    // walk away from a bad roll by refreshing.
    if (campaign?.pending_skill_test) {
        try { showSkillTestPopup(campaign.pending_skill_test); } catch (e) {
            console.warn('[skill-roll] could not restore pending popup on resume:', e);
        }
    }
}

function appendMessage(msg, opts = {}) {
    const bubble = document.createElement('div');
    const isGm = msg.role === 'assistant' || msg.actor === 'gm';

    // KW4 — process triggered tips from GM narrative
    if (isGm && msg.debugMeta?.triggeredTips?.length) {
        _handleTriggeredTips(msg.debugMeta.triggeredTips);
    }
    const isSystem = msg.role === 'system';
    const isRoll = msg.role === 'roll';
    const variant = isSystem ? 'system' : isRoll ? 'roll' : (isGm ? 'gm' : 'user');
    bubble.className = `chat-bubble chat-bubble--${variant}`;

    if (!isSystem && !isRoll) {
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
    bubble._isChatBubble = true;  // sentinel for cancel removal

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
        if (m.debugRoll) {
            const dr = m.debugRoll;
            const rollLine = `▼ ROLL: action=${dr.action_type || '?'} d20=${dr.roll ?? '?'} total=${dr.total ?? '?'} dc=${dr.dc ?? '?'} → ${dr.outcome || '?'}`;
            dbg.innerHTML += `<span class="debug-block__roll">${escapeHtml(rollLine)}</span>`;
        }
        dbg.innerHTML += `<span class="debug-block__loc">${escapeHtml(locLine)}${locJson ? '\n' + escapeHtml(locJson) : ''}</span>`;
        elements.chatMessages.appendChild(dbg);
    }
    return bubble;
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
    if (!text) return { narrative: '', locationIntent: null, debugRoll: null };
    let raw = String(text).trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim();
    const _tipKeys = [];
    const stripInternalTags = s => String(s || '')
        .replace(/\s*\[LOCATION_BLOCKED:[^\]]*\]/g, '')
        .replace(/\s*\[APPLY_CONDITION:[^\]]*\]/g, '')
        .replace(/\s*\[TIP:([^\]]+)\]/gi, (_, k) => { _tipKeys.push(k.trim()); return ''; })
        .trim();
    try {
        const data = JSON.parse(raw);
        if (data && typeof data === 'object') {
            const narrative = stripInternalTags(typeof data.narrative === 'string' ? data.narrative : '');
            return {
                narrative,
                locationIntent: data.location_intent || null,
                debugRoll: data._debug || null,
                raw: data,
                triggeredTips: _tipKeys.length ? [..._tipKeys] : undefined,
            };
        }
    } catch (_e) {}
    return { narrative: parseGmResponse(text), locationIntent: null, debugRoll: null };
}

function parseGmResponse(text) {
    const stripExtra = s => String(s || '')
        .replace(/\s*\[LOCATION_BLOCKED:[^\]]*\]/g, '')
        .replace(/\s*\[APPLY_CONDITION:[^\]]*\]/g, '')
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
    // Keep the user's original text for display in the bubble; use expanded
    // form only for matching/extracting args. So '/pytanie gdzie jestem' stays
    // '/pytanie ...' on screen but matches the /mem handler.
    const original = text.trim();
    const t = _expandSlashAlias(original);

    if (/^\/help(\s|$)/i.test(t)) {
        const mpActive = !!window.multiplayerUI?.isActive();
        const lines = SLASH_COMMANDS
            .filter(c => !c.adminOnly || playerIsAdmin())
            .filter(c => !c.multiplayerOnly || mpActive)
            .map(c => `\`${c.cmd}\` — ${c.desc}`)
            .join('\n');
        appendMessage({ role: 'system', content: `**Komendy:**\n${lines}`, created_at: new Date() });
        // KW6 — inject Wskazówki shortcut chip into the help bubble
        const helpBubble = elements.chatMessages.lastElementChild;
        if (helpBubble) {
            const chip = document.createElement('button');
            chip.className = 'help-wskazowki-chip';
            chip.textContent = '📖 Pokaż wskazówki';
            chip.addEventListener('click', () => {
                if (!isSheetOpen) toggleCharacterSheet();
                _switchSheetTab('knowledge');
                renderKnowledgeTab();
            });
            helpBubble.querySelector('.chat-bubble__content').appendChild(chip);
        }
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
                if (sub?.startsWith('xp ')) {
                    const lvlMsg = result.level_up ? ` ⬆ LEVEL UP! Poz. ${result.level_up.old_level} → ${result.level_up.new_level}` : '';
                    return `PD ${result.op === 'add' ? '+' : '='}${result.amount} → dostępne: ${result.xp_available} | lifetime: ${result.xp_lifetime_earned} | Poz. ${result.level}${lvlMsg}`;
                }
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

    // /roll [skill_key] [value|intent] — admin-only
    // /roll stealth        → dice popup (random committed roll)
    // /roll stealth 18     → forced value 18, skip popup, resolve immediately
    if (/^\/roll(\s|$)/i.test(t)) {
        if (!playerIsAdmin()) {
            showToast('Brak uprawnień — /roll wymaga konta admina.', 'error');
            return true;
        }
        if (!characterData?.id) {
            showToast('Brak aktywnego bohatera — wejdź do kampanii.', 'error');
            return true;
        }
        const rollArgs = t.replace(/^\/roll\s*/i, '').trim();
        const parts = rollArgs.split(/\s+/);
        const skillArg = parts[0] || 'athletics';

        // Detect forced value: second token is a number 1-20
        const maybeVal = parts[1];
        const forcedVal = (maybeVal && /^\d+$/.test(maybeVal) && +maybeVal >= 1 && +maybeVal <= 20)
            ? +maybeVal : null;
        const intent = forcedVal !== null ? parts.slice(2).join(' ').trim()
                                         : parts.slice(1).join(' ').trim();

        try {
            const body = {
                character_id: characterData.id,
                text: `/roll ${skillArg}`,
                user_id: currentUser?.id,
            };
            if (forcedVal !== null) body.forced_d20 = forcedVal;
            if (intent) body.intent = intent;

            const r = await fetch('/api/debug/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) {
                showToast(`/roll: ${data?.detail || 'błąd'}`, 'error');
                return true;
            }

            const stp = data?.skill_test_pending;
            if (!stp) {
                const res = data?.result || {};
                const _ctr = (data?.skill_test_pending || {}).counter || {};
                const _dcLabel = _ctr.counter_type === 'opposed'
                    ? `vs ${(_ctr.counter_key || 'przeciwnik').toUpperCase()}`
                    : `DC ${res.dc}`;
                appendMessage({ role: 'system', content: `🎲 /roll ${res.skill_label || skillArg} — ${_dcLabel}, mod ${res.modifier >= 0 ? '+' : ''}${res.modifier}`, created_at: new Date() });
                return true;
            }

            if (forcedVal !== null) {
                // Forced value path: skip popup, resolve immediately with the committed value
                if (elements.btnSend) elements.btnSend.disabled = true;
                await resolveSkillTest(stp.skill_test_id, forcedVal, null);
            } else {
                // Normal path: show 3D dice popup
                if (intent) stp._admin_intent = intent;
                showSkillTestPopup(stp);
            }
        } catch (e) {
            showToast(`/roll: ${e.message || e}`, 'error');
            if (elements.btnSend) elements.btnSend.disabled = false;
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
            appendMessage({ role: 'system', content: 'Użyj: <code>/mem [pytanie]</code> — pytanie o przeszłość ze wszystkich kampanii bohatera.', created_at: new Date() });
            scrollToBottom();
            return true;
        }
        await handleMemCommand(question, original);
        return true;
    }

    if (/^\/helpme(\s|$)/i.test(t)) {
        const topic = t.replace(/^\/helpme\s*/i, '').trim();
        await handleHelpmeCommand(topic, original);
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

// Stage 8 follow-up — /debug subcommand tree for autocomplete.
// Mirrors ADMIN_CMD_TREE shape so we can reuse the same suggestion-popup plumbing.
const DEBUG_CMD_TREE = {
    'dump-state':       {},
    'set-hp':           {},
    'set-state':        { 'NARRATIVE': {}, 'COMBAT': {}, 'SKILL_TEST_PENDING': {} },
    'reset-cooldowns':  {},
    'xp':               { 'add': {}, 'set': {} },
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
    'xp':              { hint: 'Zarządzaj PD', placeholder: '<add|set> <N>' },
    'xp add':          { hint: 'Dodaj N PD do xp_available (+ lifetime)', placeholder: '<N>' },
    'xp set':          { hint: 'Ustaw xp_available na N', placeholder: '<N>' },
    'preview-death':   { hint: '👁 Podgląd ekranu śmierci (bez zmian w DB)' },
    'preview-victory': { hint: '👁 Podgląd ekranu zwycięstwa (bez zmian w DB)' },
};

// /roll [skill] [intent] autocomplete — skill list seeded from game_config_skills
// Populated at page load / first use and cached for the session.
let _rollSkillCache = null;
let _publicSlashCache = null;
let _publicSlashFetchInflight = null;
let _aliasToCanonical = {};  // {'/pytanie': '/mem', ...}

// Fetch player-visible slash commands from server (alias-aware).
// Server returns [{command: '/szukaj', canonical: '/search', description: '...'}].
async function _fetchPublicSlashCommands(force = false) {
    if (_publicSlashCache && !force) return _publicSlashCache;
    if (_publicSlashFetchInflight) return _publicSlashFetchInflight;
    _publicSlashFetchInflight = (async () => {
        try {
            const r = await fetch(`${API_BASE}/mechanics/slash-commands`);
            if (!r.ok) throw new Error('HTTP ' + r.status);
            const d = await r.json();
            const rows = Array.isArray(d.commands) ? d.commands : [];
            // Convert to the same shape as SLASH_COMMANDS for the autocomplete code path
            _publicSlashCache = rows.map(c => ({
                cmd: String(c.command || '').split(/\s+/)[0],   // strip placeholder suffix
                desc: String(c.description || ''),
            }));
            // Build alias→canonical map for client-side substitution
            _aliasToCanonical = {};
            for (const c of rows) {
                const visible = String(c.command || '').split(/\s+/)[0].toLowerCase();
                const canon   = String(c.canonical || '').toLowerCase();
                if (visible && canon && visible !== canon) {
                    _aliasToCanonical[visible] = canon;
                }
            }
            return _publicSlashCache;
        } catch (e) {
            console.warn('[slash] failed to fetch server commands, using hardcoded fallback', e);
            _publicSlashCache = null;
            return null;
        } finally {
            _publicSlashFetchInflight = null;
        }
    })();
    return _publicSlashFetchInflight;
}

// Replace alias prefix with canonical so client-side regex handlers (handleMemCommand,
// handleHelpmeCommand, /admin, etc.) still match. Keep rest of text intact.
function _expandSlashAlias(text) {
    if (!text || !text.startsWith('/')) return text;
    const first = text.split(/\s+/, 1)[0].toLowerCase();
    const canon = _aliasToCanonical[first];
    if (!canon || canon === first) return text;
    return canon + text.slice(first.length);
}

// Effective list: server (alias-aware) + admin-only + multiplayerOnly commands merged in.
function _effectiveSlashCommands() {
    const base = (_publicSlashCache || SLASH_COMMANDS).slice();
    const seen = new Set(base.map(c => c.cmd));
    for (const c of SLASH_COMMANDS) {
        if (c.adminOnly && !seen.has(c.cmd) && playerIsAdmin()) base.push(c);
        if (c.multiplayerOnly && !seen.has(c.cmd)) base.push(c);
    }
    // Tag commands known as multiplayerOnly regardless of source (server doesn't carry this flag)
    const mpOnly = new Set(SLASH_COMMANDS.filter(c => c.multiplayerOnly).map(c => c.cmd));
    return base.map(c => mpOnly.has(c.cmd) ? { ...c, multiplayerOnly: true } : c);
}

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

function getRollSuggestions(afterRoll, cachedSkills) {
    const parts = afterRoll.trimStart().split(/\s+/);
    const typed = (parts[0] || '').toLowerCase();
    const hasSkill = afterRoll.trimStart().includes(' ');

    // Skill already picked — hide popup so Enter submits the full command normally
    if (hasSkill) return [];

    // Still typing the skill name — match by key OR Polish label prefix;
    // insert the Polish label (backend resolves label → key).
    return (cachedSkills || [])
        .filter(s => {
            const key = (s.key || '').toLowerCase();
            const lbl = (s.label || '').toLowerCase();
            return key.startsWith(typed) || lbl.startsWith(typed);
        })
        .map(s => ({ cmd: `/roll ${s.label}`, desc: s.key }));
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
        _hideTravelHintModal();
        return;
    }
    // Show travel modal if travel hint present
    const travelAction = actions.find(a => a.action === 'OPEN_MAP' && a.highlight);
    if (travelAction) {
        _showTravelHintModal(travelAction.label.replace(/^[🗺️\s]*Podróżuj → /, '').replace(/^[🗺️\s]*/, ''));
    } else {
        _hideTravelHintModal();
    }
    container.style.display = 'flex';
    actions.forEach((a, i) => {
        const btn = document.createElement('button');
        let btnClass = 'suggested-action-btn' + (a.enabled ? '' : ' disabled');
        if (a.highlight) btnClass += ' suggested-action-btn--travel';
        btn.className = btnClass;
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

    // Stage 2B R4: BUILD_CAMP goes through a dedicated endpoint, not the narrator.
    if (actionStr === 'BUILD_CAMP') {
        await handleBuildCamp();
        return;
    }

    if (actionStr === 'OPEN_MAP') {
        _wmOpen();
        return;
    }

    await sendTurn(actionStr, 'structured', displayLabel);
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
        const clockStr = data?.current_clock ? ` Zegar: ${data.current_clock}.` : '';
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

    // Keep button enabled so mobile tap can reach the cancel handler.
    // Double-send is blocked by the _activeTurnAbort guard in the click listener.
    elements.btnSend.disabled = false;
    renderSuggestedActions([]);
    _activeTurnText = text;

    const displayText = displayLabel || text;
    const userBubble = appendMessage({ role: 'user', content: displayText, created_at: new Date() });
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

        // Auto-update hex map pin when GM narration changed current_hex
        if (result.hex_changed) {
            const { from: hFrom, to: hTo } = result.hex_changed;
            if (_wmap.hexes && _wmap.hexes.length) {
                _wmap.currentHex = hTo;
                _wmRender();
            }
            // Pulse the map button to signal location changed
            const mapBtn = document.getElementById('open-map-btn');
            if (mapBtn) {
                mapBtn.classList.add('map-btn--pulse');
                setTimeout(() => mapBtn.classList.remove('map-btn--pulse'), 2000);
            }
        }

        await refreshCharacterData();
        await pollCombatState();

        // Show initiative roll results when combat just started
        if (result.combat_started) {
            const combatants = result.combat_started.combatants || [];
            const sorted = [...combatants].sort((a, b) => (b.initiative_roll || 0) - (a.initiative_roll || 0));
            if (sorted.length && sorted.some(c => c.initiative_roll != null)) {
                const lines = sorted.map(c => {
                    const name = c.name || (c.type === 'player' ? (characterData?.name || 'Gracz') : c.id);
                    const roll = c.initiative_roll != null ? c.initiative_roll : '?';
                    return `• ${name}: **${roll}**`;
                });
                const firstTurn = result.combat_started.current_turn;
                const firstCombatant = sorted[0];
                const firstLabel = firstCombatant?.type === 'player'
                    ? (characterData?.name || 'Gracz')
                    : (firstCombatant?.name || 'Wróg');
                appendMessage({
                    role: 'system',
                    content: `⚔ **Inicjatywa:**\n${lines.join('\n')}\n\n${firstLabel} zaczyna!`,
                    created_at: new Date(),
                });
                scrollToBottom();
            }
        }

        // BUG-02: clock now ticks every turn — refresh header display.
        fetchAndRenderClock(currentCampaignId);
        _refreshDebugBlocks();
        updateInputPlaceholder();

        if (result.npc_interaction?.image_url) {
            showNpcReveal(result.npc_interaction);
        }

        // T38: victory auto-trigger when [CAMPAIGN_END] tag fired this turn
        if (result.campaign_ended) {
            showVictoryScreen();
            return;
        }

        // J3 — count narrative turns; show journal badge every 10
        if (inputType !== 'combat') {
            _journalBadgeTurns++;
            if (_journalBadgeTurns >= 10) {
                _journalBadgeTurns = 0;
                if (!isJournalOpen) {
                    document.getElementById('open-journal-btn')?.classList.add('journal-btn--badge');
                }
            }
        }
    } catch (error) {
        typingIndicator.remove();
        _activeTurnAbort = null;
        _hideCancelButton();
        if (error.name === 'AbortError') {
            // User-initiated cancel — restore their text to the input
            userBubble?.remove();
            elements.chatInput.value = _activeTurnText;
            elements.chatInput.dispatchEvent(new Event('input'));
            elements.chatInput.focus();
            showToast('Wiadomość cofnięta — możesz poprawić', 'info');
            return;
        }
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
        // Unescape JSON string content (basic: \" → ", \n → newline)
        return m[1].replace(/\\"/g, '"').replace(/\\n/g, '\n').replace(/\\t/g, '\t');
    }
    // Not yet past the JSON prefix — hide it (show nothing until narrative starts)
    if (raw.startsWith('{') && !raw.includes('"narrative"')) return '';
    return raw;
}

// Streaming implementation — returns {skill_test_pending, suggested_actions} on completion
async function _sendTurnStream(text, inputType, typingIndicator) {
    const headers = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('aigm_access_token');
    if (token) headers['Authorization'] = `Bearer ${token}`;

    _activeTurnAbort = new AbortController();
    _showCancelButton();

    const resp = await fetch(`/api/campaigns/${currentCampaignId}/turns/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ text, character_id: characterData.id, input_type: inputType }),
        signal: _activeTurnAbort.signal,
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
            if (meta.skill_test_pending) result.skill_test_pending = meta.skill_test_pending;
            if (meta.current_location)   result.current_location   = meta.current_location;
            if (meta.campaign_ended)     result.campaign_ended     = true;
            // BUG-02: clock is included in [DONE] — update header immediately, no extra request
            if (meta.clock) renderClock(meta.clock);
            return;
        }

        if (payload.startsWith('[NPC_INTERACTION]')) {
            result.npc_interaction = JSON.parse(payload.slice(17));
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
        if (payload.startsWith('[CMD_JSON]')) {
            try {
                const cmdResult = JSON.parse(payload.slice(10));
                result.command_result = cmdResult;
                typingIndicator.remove();
                const msg = cmdResult?.result?.message;
                if (msg) {
                    appendMessage({
                        role: 'system',
                        content: msg,
                        created_at: cmdResult.created_at || new Date(),
                        route: 'command',
                    });
                    scrollToBottom();
                }
            } catch (e) {
                console.warn('[stream] CMD_JSON parse failed', e);
            }
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

    _activeTurnAbort = null;
    _hideCancelButton();

    // Finalize streaming bubble — apply full GM formatting
    if (streamBubble && contentEl && rawTokens) {
        const { narrative: gmContent } = parseGmFull(rawTokens);
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
    if (window.multiplayerUI?.isActive() && !content.startsWith('/')) {
        await window.multiplayerUI.handleSubmit();
        return;
    }
    // Redirect /whisper to party chat when multiplayer is active
    if (window.multiplayerUI?.isActive() && /^\/whisper\s+\S+\s+.+$/i.test(content)) {
        elements.chatInput.value = '';
        hideCharCounter();
        await window.multiplayerUI._sendChat?.(content);
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

// ── Shake-to-roll on mobile (F3 / issue #66, upgrade #113) ──────────────────
// onShake is invoked with ({x, y} normalized direction, intensity ratio).
// Returns { active, cleanup, error, requestPermission? }.
// active: true means listener is attached now.
// error: 'unsupported' | 'needs_permission' | 'denied' | null.
function _initShakeToRoll(onShake) {
    if (typeof window === 'undefined' || typeof window.DeviceMotionEvent === 'undefined') {
        return { active: false, cleanup: null, error: 'unsupported' };
    }
    // Threshold tuned for an intentional shake; phones idle near ~0 m/s² on .acceleration
    // and ~9.8 m/s² on .accelerationIncludingGravity. We compute magnitude minus gravity baseline.
    const THRESHOLD = 18; // m/s²
    let triggered = false;
    const motionHandler = (e) => {
        if (triggered) return;
        const usePure = !!(e.acceleration && e.acceleration.x !== null);
        const a = usePure ? e.acceleration : e.accelerationIncludingGravity;
        if (!a) return;
        const ax = a.x || 0, ay = a.y || 0, az = a.z || 0;
        const mag = Math.sqrt(ax * ax + ay * ay + az * az);
        const effective = usePure ? mag : Math.abs(mag - 9.8);
        if (effective > THRESHOLD) {
            triggered = true;
            window.removeEventListener('devicemotion', motionHandler);
            // Haptic confirmation — Android supports navigator.vibrate; iOS Safari is a silent no-op.
            try { navigator.vibrate?.(60); } catch (_e) {}
            // Direction vector from horizontal acceleration; ignore Z (toward/away from face).
            // accel.y is positive toward the top of the phone — matches dice "up" axis, no flip needed.
            const horizMag = Math.sqrt(ax * ax + ay * ay);
            const dirVec = horizMag > 0.5
                ? { x: ax / horizMag, y: ay / horizMag }
                : null; // axial / pure-Z shake → let caller use random vector
            const intensity = Math.min(3, effective / THRESHOLD);
            onShake(dirVec, intensity);
        }
    };
    const cleanup = () => window.removeEventListener('devicemotion', motionHandler);

    const needsPermission = typeof window.DeviceMotionEvent.requestPermission === 'function';
    const stored = localStorage.getItem('aigm_motion_permission');
    if (needsPermission && stored !== 'granted') {
        return {
            active: false,
            cleanup,
            error: stored === 'denied' ? 'denied' : 'needs_permission',
            requestPermission: async () => {
                try {
                    const result = await window.DeviceMotionEvent.requestPermission();
                    localStorage.setItem('aigm_motion_permission', result);
                    // Bundle DeviceOrientation permission in the same user gesture so
                    // tilt-aim works without a second prompt.
                    try {
                        if (typeof window.DeviceOrientationEvent?.requestPermission === 'function') {
                            const oresult = await window.DeviceOrientationEvent.requestPermission();
                            localStorage.setItem('aigm_orientation_permission', oresult);
                        }
                    } catch (_oe) { /* orientation refusal is non-fatal */ }
                    if (result === 'granted') {
                        window.addEventListener('devicemotion', motionHandler);
                        return true;
                    }
                } catch (_e) {
                    localStorage.setItem('aigm_motion_permission', 'denied');
                }
                return false;
            },
        };
    }
    window.addEventListener('devicemotion', motionHandler);
    return { active: true, cleanup, error: null };
}

function _showShakeHint(text, onTap) {
    const hint = document.getElementById('dice-shake-hint');
    if (!hint) return;
    const textEl = hint.querySelector('.shake-hint-text');
    if (textEl && text) textEl.textContent = text;
    hint.hidden = false;
    hint.onclick = onTap || null;
}
function _hideShakeHint() {
    const hint = document.getElementById('dice-shake-hint');
    if (!hint) return;
    hint.hidden = true;
    hint.onclick = null;
}

// ── Tilt-to-aim (F3 #3) ─────────────────────────────────────────────────────
// Reads DeviceOrientationEvent; captures a baseline on the first sample so any
// hold-angle (vertical, lap, etc.) feels neutral. Caller passes onTilt(vec)
// receiving {x, y} ∈ [-1, 1] suitable for start_throw_with_vector.
function _initTiltAim(onTilt) {
    if (typeof window === 'undefined' || typeof window.DeviceOrientationEvent === 'undefined') {
        return { active: false, cleanup: null, getCurrent: () => null };
    }
    const needsPermission = typeof window.DeviceOrientationEvent.requestPermission === 'function';
    const stored = localStorage.getItem('aigm_orientation_permission');
    if (needsPermission && stored !== 'granted') {
        return { active: false, cleanup: null, getCurrent: () => null, error: stored === 'denied' ? 'denied' : 'needs_permission' };
    }
    const RANGE_DEG = 30; // ±30° tilt from baseline = full vector range
    let baselineBeta = null, baselineGamma = null;
    let current = { x: 0, y: 0 };
    const handler = (e) => {
        if (e.beta == null || e.gamma == null) return;
        if (baselineBeta == null) { baselineBeta = e.beta; baselineGamma = e.gamma; }
        const dGamma = e.gamma - baselineGamma;      // +ve = right side down
        const dBeta  = e.beta  - baselineBeta;        // +ve = top of phone away
        const vx = Math.max(-1, Math.min(1, dGamma / RANGE_DEG));
        // Dice "up" axis is positive Y; tilting the top of the phone away from you (beta +)
        // should throw the dice up the screen → negate dBeta.
        const vy = Math.max(-1, Math.min(1, -dBeta / RANGE_DEG));
        current = { x: vx, y: vy };
        if (onTilt) onTilt(current);
    };
    window.addEventListener('deviceorientation', handler);
    return {
        active: true,
        cleanup: () => window.removeEventListener('deviceorientation', handler),
        getCurrent: () => current,
    };
}

function _showManualBtn(onClick) {
    const b = document.getElementById('dice-manual-roll-btn');
    if (!b) return;
    b.hidden = false;
    b.onclick = onClick;
}
function _hideManualBtn() {
    const b = document.getElementById('dice-manual-roll-btn');
    if (!b) return;
    b.hidden = true;
    b.onclick = null;
}

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
    window.multiplayerUI?.deactivate();
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

    // Pre-populate result card header (shown after roll)
    if (resultSkill)  resultSkill.textContent  = name;
    if (resultIntent) { resultIntent.textContent = intent; resultIntent.hidden = !intent; }

    const modParts = [
        mod.skill_rank  ? `Ranga +${mod.skill_rank}`  : '',
        mod.stat_mod != null ? `Mod.${mod.governing_stat||'STAT'} ${mod.stat_mod>=0?'+':''}${mod.stat_mod}` : '',
        mod.proficiency ? `Biegłość +${mod.proficiency}` : '',
    ].filter(Boolean);
    if (resultTot) resultTot.textContent = (modParts.length ? modParts.join(' · ') + ' · ' : '') + `Bonus ${sign}${total}`;

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

        // Overwrite the mod line with the final sum
        if (resultTot) resultTot.textContent =
            (modParts.length ? modParts.join(' · ') + ' · ' : '') + `Bonus ${sign}${total}  =  ${sum}`;

        if (nat20) {
            resultVerd.textContent = '✦ Naturalny 20!';
            resultVerd.className   = 'nat20';
        } else if (nat1) {
            resultVerd.textContent = '✧ Naturalny 1';
            resultVerd.className   = 'nat1';
        } else {
            const counter = pending.counter || {};
            if (counter.counter_type === 'opposed') {
                // Opponent rolls server-side — we don't know the outcome yet
                const oppKey = (counter.counter_key || 'przeciwnik').toUpperCase();
                resultVerd.textContent = `vs ${oppKey} — wynik po chwili`;
                resultVerd.className   = '';
            } else {
                const dc = pending.dc || 12;
                resultVerd.textContent = sum >= dc ? 'Sukces' : 'Porażka';
                resultVerd.className   = sum >= dc ? 'success' : 'failure';
            }
        }
        resultCard.hidden = false;

        // Close after 5.5 s, or immediately on tap/click anywhere on the overlay
        let _closed = false;
        const _savedDismiss = window.dismissDiceRoll;
        async function _closeResult() {
            if (_closed) return;
            _closed = true;
            overlay.removeEventListener('click', _closeResult);
            window.dismissDiceRoll = _savedDismiss;
            overlay.hidden = true;
            if (skillCard) skillCard.hidden = false;
            await resolveSkillTest(pending.skill_test_id, rolled, null);
        }
        // Override ✕ button so it resolves-and-stays rather than navigate-away
        window.dismissDiceRoll = _closeResult;
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

        const beforeRoll = committedD20 !== null ? () => [committedD20] : null;
        const afterRoll = (notation) => {
            // Brief settle pause before revealing result card
            setTimeout(() => _showResult(notation.result[0]), 600);
        };

        // Shake-to-roll + tilt-aim + manual fallback (F3 / issue #66, upgrades #113)
        let _shake = null;
        let _tilt = null;
        const triggerThrow = (dirVec, intensity) => {
            if (_shake?.cleanup) _shake.cleanup();
            if (_tilt?.cleanup)  _tilt.cleanup();
            _hideShakeHint();
            _hideManualBtn();
            if (dirVec && typeof _diceBox.start_throw_with_vector === 'function') {
                _diceBox.start_throw_with_vector(dirVec, intensity ?? 1, beforeRoll, afterRoll);
            } else {
                _diceBox.start_throw(beforeRoll, afterRoll);
            }
        };
        // Patch dismissDiceRoll so the ✕ button also tears down all listeners
        const _origDismiss = window.dismissDiceRoll;
        window.dismissDiceRoll = async function() {
            if (_shake?.cleanup) _shake.cleanup();
            if (_tilt?.cleanup)  _tilt.cleanup();
            _hideShakeHint();
            _hideManualBtn();
            window.dismissDiceRoll = _origDismiss;
            if (_origDismiss) await _origDismiss();
        };

        // Shake handler — prefers the live tilt vector when the player has aimed,
        // otherwise uses the shake's own direction.
        const onShake = (shakeVec, intensity) => {
            const tiltVec = _tilt?.getCurrent?.();
            const aimed = tiltVec && (Math.abs(tiltVec.x) > 0.1 || Math.abs(tiltVec.y) > 0.1);
            triggerThrow(aimed ? tiltVec : shakeVec, intensity);
        };

        const startTilt = () => {
            // Silent tilt — no visual reticle; tilt still influences throw direction at shake time
            _tilt = _initTiltAim(null);
        };

        const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
        if (isTouch) {
            _shake = _initShakeToRoll(onShake);
            // Manual fallback is always available on touch — fires a random-vector throw
            _showManualBtn(() => triggerThrow());
            if (_shake.error === 'needs_permission') {
                _showShakeHint('Przechyl by celować, potrząśnij by rzucić — dotknij aby zezwolić', async () => {
                    const ok = await _shake.requestPermission();
                    if (ok) {
                        startTilt();
                        _showShakeHint('Przechyl by celować, potrząśnij by rzucić', null);
                    }
                    // If denied, leave manual button visible as the way out
                });
            } else if (_shake.active) {
                startTilt();
                const hint = _tilt?.active
                    ? 'Przechyl by celować, potrząśnij by rzucić'
                    : 'Potrząśnij telefonem aby rzucić kością';
                _showShakeHint(hint, null);
            } else {
                // Motion unsupported / denied — manual button is the only way; no auto-throw
                _showShakeHint('Dotknij "Rzuć ręcznie" aby rzucić', null);
            }
        } else {
            triggerThrow(); // desktop: auto-roll, no shake
        }
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

        // Show the roll result as a centered yellow roll bubble in chat history
        const sr = response.skill_test_result || {};
        let rollBubbleEl = null;
        if (sr.skill_label || sr.skill_key) {
            const skillName = sr.skill_label || sr.skill_key || 'Test';
            const outcome = sr.nat20 ? ' — Naturalny 20!' : sr.nat1 ? ' — Naturalny 1' : sr.success ? ' — Sukces' : ' — Porażka';
            const rollLine = `🎲 ${skillName}: ${sr.d20_roll} +${sr.modifier} = ${sr.player_total}${outcome}`;
            appendMessage({ role: 'roll', content: rollLine, created_at: new Date() });
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
// T47a — Turn cancel helpers
function _cancelActiveTurn() {
    if (!_activeTurnAbort) return;
    _activeTurnAbort.abort();
    // State cleanup happens in sendTurn's catch(AbortError) block
}

function _showCancelButton() {
    if (!elements.btnSend) return;
    elements.btnSend.classList.add('composer__send--stopping');
    elements.btnSend.title = 'Zatrzymaj odpowiedź (ESC)';
}

function _hideCancelButton() {
    if (!elements.btnSend) return;
    elements.btnSend.classList.remove('composer__send--stopping');
    elements.btnSend.title = '';
}

document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const popup = document.getElementById('skill-roll-popup');
    if (popup) { popup.remove(); _resetInputState(); return; }
    // T47a — cancel in-flight turn
    if (_activeTurnAbort) { _cancelActiveTurn(); return; }
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
    elements.characterStatsDisplay.textContent = `${hp}/${maxHp} HP`;

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
let _encounterRevealShown = false;

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
            _encounterRevealShown = false;
            window.clog?.event('combat_started', { round: cs.round, current_turn: cs.current_turn });
            showCombatUI();
            const _firstEnemy = (Array.isArray(cs.combatants) ? cs.combatants : []).find(c => c?.type === 'enemy');
            if (_firstEnemy?.enemy_key && !_encounterRevealShown) {
                _encounterRevealShown = true;
                showEncounterReveal(_firstEnemy.enemy_key, _firstEnemy.name);
            }
        }

        // Auto-trigger enemy turn when it's not the player's turn
        if (cs.current_turn !== 'player' && !enemyTurnInFlight && !combatBusy) {
            await handleEnemyTurn();
        }
    } catch (e) {
        window.clog?.warn('combat_poll_exception', { message: String(e?.message || e) });
    }
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
    const sub = document.getElementById('combat-status-overlay-sub');
    if (sub) sub.textContent = enemyName ? `Działa: ${enemyName}` : '';
    overlay.classList.add('combat-status-overlay--visible');
}

async function showEncounterReveal(enemyKey, enemyName) {
    try {
        const label = enemyName || 'Wróg';
        const overlay = document.createElement('div');
        overlay.className = 'encounter-reveal';
        overlay.innerHTML = `
            <div class="encounter-reveal__card">
                <img class="encounter-reveal__img" id="er-img-${enemyKey}" src="" alt="${label}" style="display:none">
                <div class="encounter-reveal__footer">
                    <div class="encounter-reveal__name">${label}</div>
                    <div class="encounter-reveal__hint">Dotknij aby zamknąć</div>
                </div>
            </div>`;
        document.body.appendChild(overlay);

        const dismiss = () => {
            overlay.classList.add('encounter-reveal--out');
            setTimeout(() => overlay.remove(), 350);
        };
        overlay.addEventListener('click', dismiss);
        const autoTimer = setTimeout(dismiss, 4000);

        requestAnimationFrame(() => overlay.classList.add('encounter-reveal--in'));

        // Load image async — show overlay immediately, image appears when ready
        const data = await fetch(`/api/enemies/${encodeURIComponent(enemyKey)}`).then(r => r.ok ? r.json() : null);
        const imageUrl = data?.enemy?.image_url;
        if (!imageUrl) {
            clearTimeout(autoTimer);
            dismiss();
            return;
        }
        const img = overlay.querySelector(`#er-img-${enemyKey}`);
        if (img && overlay.isConnected) {
            img.src = `${imageUrl}?t=${Date.now()}`;
            img.style.display = '';
        }
    } catch (_) {}
}

function showNpcReveal(npc) {
    if (!npc?.image_url) return;
    const overlay = document.createElement('div');
    overlay.className = 'encounter-reveal encounter-reveal--npc';
    overlay.innerHTML = `
        <div class="encounter-reveal__card">
            <img class="encounter-reveal__img" src="${npc.image_url}?t=${Date.now()}" alt="${npc.label || 'NPC'}">
            <div class="encounter-reveal__footer">
                <div class="encounter-reveal__name">${npc.label || 'NPC'}</div>
                <div class="encounter-reveal__hint">Dotknij aby zamknąć</div>
            </div>
        </div>`;
    document.body.appendChild(overlay);
    const dismiss = () => {
        overlay.classList.add('encounter-reveal--out');
        setTimeout(() => overlay.remove(), 350);
    };
    overlay.addEventListener('click', dismiss);
    setTimeout(dismiss, 4000);
    requestAnimationFrame(() => overlay.classList.add('encounter-reveal--in'));
}

async function handleEnemyTurn() {
    if (enemyTurnInFlight || !currentCampaignId) return;
    enemyTurnInFlight = true;
    setCombatMsg('Tura wroga...');
    // Show the overlay eagerly — `renderCombatUI` will keep it on until the next
    // state poll proves the player has control back. Avoids a flicker window
    // between POST request and the next render.
    _showEnemyTurnOverlay(true);
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
    _encounterRevealShown = false;
    elements.combatBanner.hidden = true;
    elements.combatComposer.hidden = true;
    elements.composer?.classList.remove('composer--hidden');
    if (elements.initiativeTrack) elements.initiativeTrack.innerHTML = '';
    _showEnemyTurnOverlay(false);  // C2: clear overlay on combat end
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
// T25V2 — Level-up notification overlay
function showLevelUpNotification(lu) {
    if (!lu || !lu.new_level) return;
    const existing = document.getElementById('levelup-overlay');
    if (existing) existing.remove();

    const el = document.createElement('div');
    el.id = 'levelup-overlay';
    el.className = 'levelup-overlay';
    el.innerHTML = `
        <div class="levelup-overlay__inner">
            <div class="levelup-overlay__badge">AWANS</div>
            <div class="levelup-overlay__level">Poziom ${lu.new_level}</div>
            <div class="levelup-overlay__gains">
                ${lu.hp_gain > 0 ? `<span>+${lu.hp_gain} HP</span>` : ''}
                ${lu.mana_gain > 0 ? `<span>+${lu.mana_gain} Mana</span>` : ''}
            </div>
            <div class="levelup-overlay__tap">Dotknij aby zamknąć</div>
        </div>`;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('levelup-overlay--active'));

    const close = () => {
        el.classList.remove('levelup-overlay--active');
        setTimeout(() => el.remove(), 400);
    };
    el.addEventListener('click', close);
    setTimeout(close, 5000);
}

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
};

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
        return `
            <div class="${cls}" data-combatant-id="${escapeHtml(id)}" title="${escapeHtml(name)}${ini ? ' · ' + ini : ''} · ${zoneLabel}${_condTitleSuffix}">
                <div class="init-chip__zone" aria-label="${zoneLabel}">${zoneGlyph}</div>
                ${_badges ? `<div class="init-chip__cond-row">${_badges}</div>` : ''}
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
    // Stage 7 C1 — warm the condition meta cache so chip tooltips have descriptions.
    // First call hits the network; subsequent calls are cached (5-min TTL).
    _ensureConditionMeta().catch(() => {});

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

    // Stage 7 C2 — "Tura wroga…" overlay during enemy turns.
    // Names the currently-acting enemy if combat_state pins one.
    const _currentTurnId = String(cs.current_turn ?? '');
    const _actingEnemy = !isPlayerTurn
        ? enemies.find(e => String(e?.id ?? e?.combatant_id ?? '') === _currentTurnId) || enemies[0]
        : null;
    _showEnemyTurnOverlay(!isPlayerTurn && cs.status !== 'ended', _actingEnemy?.name);

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
        // Stage 3 Z5 — surprise badge on combatant row
        const _rowConds = Array.isArray(c.conditions) ? c.conditions : [];
        const _rowSurprised = _rowConds.some(cc => cc && String(cc.key || '').toLowerCase() === 'zaskoczony');
        const _rowSurpriseBadge = _rowSurprised
            ? `<span class="combat-combatant__surprise" title="Zaskoczony — atak +2, pierwsze trafienie podwaja obrażenia">⚡</span>`
            : '';
        return `
            <div class="combat-combatant combat-combatant--enemy ${dead ? 'combat-enemy--dead' : ''}">
                <div class="combat-combatant__icon">${dead ? '💀' : '⚔️'}</div>
                <div class="combat-combatant__body">
                    <div class="combat-combatant__name">
                        <span class="combat-combatant__name-text ${dead ? 'combat-enemy--dead' : ''}">${escapeHtml(name)}</span>
                        ${_rowSurpriseBadge}
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
            appendCombatTurnCard(row, true);
            lastRenderedCombatTurnId = Math.max(lastRenderedCombatTurnId, Number(row.id));
        }
        if (newRows.length > 0 && !_combatRollBusy && _combatRollQueue.length === 0) scrollToBottom();
    } catch (_e) {}
}

// ── Combat dice roll animation queue ─────────────────────────────────────────
const _combatRollQueue = [];
let _combatRollBusy = false;

function _buildCombatBubble(row) {
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
        const side = actor === 'player' ? 'player' : 'enemy';
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble chat-bubble--cturn-${side}`;
        bubble.innerHTML = html;
        return bubble;
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

    if (!html) return null;
    const side = actor === 'player' ? 'player' : (actor === 'enemy' ? 'enemy' : 'death');
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble chat-bubble--cturn-${side}`;
    bubble.innerHTML = html;
    return bubble;
}

function _showCombatDiceRoll(row, onDone) {
    const actor = String(row.actor || '');
    const hit = row.hit === 1 || row.hit === true;
    const rv = row.roll_value != null ? Number(row.roll_value) : null;
    const dmg = row.damage != null ? Number(row.damage) : null;
    const nat20 = rv === 20;
    const nat1 = rv === 1;

    let meta = {};
    try { meta = typeof row.narrative === 'string' ? JSON.parse(row.narrative) : {}; } catch (_e) {}

    const overlay    = document.getElementById('dice-overlay');
    const container  = document.getElementById('dice-container');
    const combatCard = document.getElementById('dice-combat-card');
    const skillCard  = document.getElementById('dice-skill-card');
    const resultCard = document.getElementById('dice-result-card');
    const headerEl   = document.getElementById('dice-combat-header');
    const numEl      = document.getElementById('dice-combat-num');
    const detailEl   = document.getElementById('dice-combat-detail');
    const verdictEl  = document.getElementById('dice-combat-verdict');

    // Header
    if (actor === 'player') {
        const label = String(meta.attack_label || 'ATAK').toUpperCase();
        const tgt = String(row.target_name || 'Wróg');
        headerEl.textContent = `⚔️ ${label} → ${tgt}`;
    } else {
        const enemyName = String(meta.enemy_name || row.target_name || 'Wróg');
        headerEl.textContent = `🗡️ ATAK WROGA — ${enemyName}`;
    }

    // Hide other cards, show overlay
    if (skillCard) skillCard.hidden = true;
    if (resultCard) resultCard.hidden = true;
    combatCard.hidden = true;
    numEl.textContent = '';
    numEl.className = '';
    verdictEl.textContent = '';
    verdictEl.className = '';
    detailEl.textContent = '';
    overlay.hidden = false;

    function _showCombatResult(rolled) {
        numEl.textContent = rolled;
        numEl.className = nat20 ? 'nat20' : nat1 ? 'nat1' : '';

        const ac = meta.target_ac != null ? ` vs AC ${meta.target_ac}` : (meta.target_ac != null ? '' : '');
        const rawD20 = actor === 'enemy' && meta.raw_d20 != null ? meta.raw_d20 : rolled;
        const acNote = meta.target_ac != null ? ` vs AC ${meta.target_ac}` : '';
        detailEl.textContent = `Rzut: ${rawD20}${acNote}`;

        if (nat20) {
            verdictEl.textContent = '✦ Naturalny 20!';
            verdictEl.className = 'nat20';
        } else if (nat1) {
            verdictEl.textContent = '✧ Naturalny 1';
            verdictEl.className = 'nat1';
        } else if (hit) {
            verdictEl.textContent = `✅ TRAFIENIE · ${dmg != null ? dmg : '?'} obrażeń`;
            verdictEl.className = 'hit';
        } else {
            verdictEl.textContent = '❌ PUDŁO';
            verdictEl.className = 'miss';
        }
        combatCard.hidden = false;

        let _combatClosed = false;
        const _closeCombat = () => {
            if (_combatClosed) return;
            _combatClosed = true;
            overlay.removeEventListener('click', _closeCombat);
            window.dismissDiceRoll = _savedCombatDismiss;
            overlay.hidden = true;
            combatCard.hidden = true;
            if (skillCard) skillCard.hidden = false;
            onDone();
        };
        const _savedCombatDismiss = window.dismissDiceRoll;
        window.dismissDiceRoll = _closeCombat;
        overlay.addEventListener('click', _closeCombat, { once: true });
        setTimeout(_closeCombat, 2500);
    }

    const committedD20 = rv !== null ? Math.max(1, Math.min(20, rv)) : null;

    requestAnimationFrame(() => {
        if (typeof DICE === 'undefined' || typeof DICE.dice_box !== 'function') {
            // Fallback: number spin
            let ticks = 0;
            const iv = setInterval(() => {
                numEl.textContent = Math.ceil(Math.random() * 20);
                if (++ticks >= 14) {
                    clearInterval(iv);
                    _showCombatResult(committedD20 !== null ? committedD20 : Math.ceil(Math.random() * 20));
                }
            }, 55);
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
            let ticks = 0;
            const iv = setInterval(() => {
                numEl.textContent = Math.ceil(Math.random() * 20);
                if (++ticks >= 14) { clearInterval(iv); _showCombatResult(committedD20 !== null ? committedD20 : Math.ceil(Math.random() * 20)); }
            }, 55);
            return;
        }
        const beforeRoll = committedD20 !== null ? () => [committedD20] : null;
        _diceBox.start_throw(beforeRoll, (notation) => {
            setTimeout(() => _showCombatResult(notation.result[0]), 600);
        });
    });
}

function _processCombatRollQueue() {
    if (_combatRollBusy || _combatRollQueue.length === 0) return;
    _combatRollBusy = true;
    const { row, animate } = _combatRollQueue.shift();
    const bubble = _buildCombatBubble(row);

    if (!animate || String(row.event_type) !== 'attack') {
        if (bubble) elements.chatMessages.appendChild(bubble);
        _combatRollBusy = false;
        _processCombatRollQueue();
        return;
    }

    _showCombatDiceRoll(row, () => {
        if (bubble) {
            elements.chatMessages.appendChild(bubble);
            scrollToBottom();
        }
        _combatRollBusy = false;
        _processCombatRollQueue();
    });
}

function appendCombatTurnCard(row, animate = false) {
    const evt = String(row.event_type || '');
    // Non-attack events bypass queue — append immediately
    if (evt !== 'attack' || !animate) {
        const bubble = _buildCombatBubble(row);
        if (bubble) elements.chatMessages.appendChild(bubble);
        return;
    }
    _combatRollQueue.push({ row, animate });
    _processCombatRollQueue();
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

    // KW3 — lazy-render knowledge tab on first open
    if (tabId === 'knowledge') renderKnowledgeTab();
}

function populateCharacterSheet(character) {
    if (!character) return;

    let sheet = character.sheet_json || character;
    if (typeof sheet === 'string') { try { sheet = JSON.parse(sheet); } catch { sheet = {}; } }
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

    // J5: XP timeline — full 10-level progression
    renderXpTimeline(sheet);

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

function renderXpTimeline(sheet) {
    const container = document.getElementById('xp-timeline-card');
    if (!container) return;
    const MAX_XP = 1000;
    const xpLifetime = Math.max(0, parseInt(sheet.xp_lifetime_earned ?? 0));
    const level = Math.min(10, Math.max(1, Math.floor(xpLifetime / 100) + 1));
    const fillPct = Math.min(100, (xpLifetime / MAX_XP) * 100);

    // 9 dividers at 10%, 20% ... 90%
    let divsHtml = '';
    for (let i = 1; i < 10; i++) {
        divsHtml += `<span class="xp-timeline__div" style="left:${i * 10}%"></span>`;
    }

    // 10 level labels, each spanning 10% of the bar
    let labelsHtml = '';
    for (let lvl = 1; lvl <= 10; lvl++) {
        const cls = lvl === level ? 'xp-timeline__label xp-timeline__label--current' : 'xp-timeline__label';
        labelsHtml += `<span class="${cls}">L${lvl}</span>`;
    }

    const toNext = level < 10 ? (level * 100 - xpLifetime) : 0;
    const metaText = level < 10
        ? `${xpLifetime} PD · Poz. ${level} · ${toNext} PD do Poz. ${level + 1}`
        : `${xpLifetime} PD · Poz. 10 · MAX`;

    container.innerHTML = `
      <div class="xp-timeline__track-wrap">
        <div class="xp-timeline__fill" style="width:${fillPct}%"></div>
        <div class="xp-timeline__dividers">${divsHtml}</div>
        <div class="xp-timeline__cursor" style="left:${fillPct}%"></div>
      </div>
      <div class="xp-timeline__labels">${labelsHtml}</div>
      <div class="xp-timeline__meta">${metaText}</div>
    `;
}

// ── Knowledge Tips Tab (KW3–KW5) ─────────────────────────────────────────────

let _knowledgeTipsCache = null;

async function _loadKnowledgeTips() {
    if (_knowledgeTipsCache) return _knowledgeTipsCache;
    try {
        const data = await fetch('/api/knowledge-tips').then(r => r.json());
        _knowledgeTipsCache = data.tips || [];
    } catch (_e) {
        _knowledgeTipsCache = [];
    }
    return _knowledgeTipsCache;
}

const KNOWLEDGE_CAT_LABELS = {
    combat: 'Walka', magic: 'Magia', exploration: 'Eksploracja',
    mechanics: 'Mechaniki', general: 'Postać i świat'
};
const KNOWLEDGE_CAT_ORDER = ['combat', 'magic', 'exploration', 'mechanics', 'general'];

async function renderKnowledgeTab() {
    const container = document.getElementById('knowledge-tips-content');
    if (!container) return;
    const tips = await _loadKnowledgeTips();
    if (!tips.length) {
        container.innerHTML = '<p class="sheet-empty-hint">Brak dostępnych wskazówek.</p>';
        return;
    }
    const grouped = {};
    for (const t of tips) {
        const cat = t.category || 'general';
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(t);
    }
    const seenTips = _getSeenTips();
    let html = '';
    for (const cat of KNOWLEDGE_CAT_ORDER) {
        if (!grouped[cat]?.length) continue;
        html += `<div class="knowledge-category">
          <div class="knowledge-category__label">${KNOWLEDGE_CAT_LABELS[cat] || cat}</div>
          ${grouped[cat].map(t => `
            <div class="knowledge-tip${seenTips.has(t.tip_key) ? ' knowledge-tip--highlight' : ''}" id="tip-${t.tip_key}">
              <div class="knowledge-tip__title">${_esc(t.title)}</div>
              <div class="knowledge-tip__body">${_esc(t.body)}</div>
              ${t.related_command ? `<span class="knowledge-tip__cmd">${_esc(t.related_command)}</span>` : ''}
            </div>`).join('')}
        </div>`;
    }
    // other categories not in ORDER
    for (const cat of Object.keys(grouped)) {
        if (KNOWLEDGE_CAT_ORDER.includes(cat)) continue;
        html += `<div class="knowledge-category">
          <div class="knowledge-category__label">${cat}</div>
          ${grouped[cat].map(t => `
            <div class="knowledge-tip" id="tip-${t.tip_key}">
              <div class="knowledge-tip__title">${_esc(t.title)}</div>
              <div class="knowledge-tip__body">${_esc(t.body)}</div>
            </div>`).join('')}
        </div>`;
    }
    container.innerHTML = html;
}

function _getSeenTips() {
    try { return new Set(JSON.parse(localStorage.getItem('aigm_seen_tips') || '[]')); } catch { return new Set(); }
}
function _markTipSeen(key) {
    try {
        const s = _getSeenTips();
        s.add(key);
        localStorage.setItem('aigm_seen_tips', JSON.stringify([...s]));
    } catch {}
}

async function _handleTriggeredTips(keys) {
    const tips = await _loadKnowledgeTips();
    const tipMap = Object.fromEntries(tips.map(t => [t.tip_key, t]));
    const seen = _getSeenTips();
    for (const key of keys) {
        if (seen.has(key)) continue;
        _markTipSeen(key);
        const tip = tipMap[key];
        if (tip) {
            showToast(`Nowa wskazówka: ${tip.title}`, 'info', 4000);
        }
    }
}

// ── Rest Buttons ──────────────────────────────────────────────────────────────

function renderRestButtons(character, sheet) {
    const container = document.getElementById('sheet-rest-actions');
    if (!container) return;
    const shortUsed = parseInt(sheet.short_rests_used ?? 0);
    const shortLeft = Math.max(0, 2 - shortUsed);
    const safeForRest = !!character.safe_for_rest;

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
            </div>
            ${!safeForRest ? '<div class="rest-actions__note">Musisz być w bezpiecznym miejscu</div>' : ''}
        </div>`;

    container.querySelector('#btn-short-rest')?.addEventListener('click', () => doRest('short', character, sheet));
    container.querySelector('#btn-long-rest')?.addEventListener('click', () => doRest('long', character, sheet));
    container.querySelector('#btn-awansuj')?.addEventListener('click', () => openAwansujPanel(character, sheet));
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
            showToast(`Długi odpoczynek. HP: ${data.hp_after}/${data.new_max_hp || sheet.max_hp}. +8h.${xpMsg}`, 'success');
            if (data.level_up) showLevelUpNotification(data.level_up);
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

    await _renderAwansujBody(character, sheet);
}

async function _renderAwansujBody(character, sheet) {
    const body = document.getElementById('awansuj-body');
    if (!body) return;
    body.innerHTML = '<div class="camp-loading">Ładowanie…</div>';

    const STAT_LABELS = { STR:'Siła', DEX:'Zręczność', CON:'Kondycja', INT:'Inteligencja', WIS:'Mądrość', CHA:'Charyzma', LCK:'Szczęście' };

    try {
        const [xpData, skillMeta] = await Promise.all([
            apiRequest('GET', `/characters/${character.id}/xp?user_id=${currentUser?.id}`),
            fetch('/api/mechanics/skills').then(r => r.ok ? r.json() : { skills: [] })
        ]);
        const xpAvail = xpData.xp_available ?? 0;
        const pendingXp = xpData.pending_xp ?? 0;
        const skills = sheet.skills || {};
        const stats = sheet.stats || {};
        const mods = sheet.stat_modifiers || {};
        const rankCosts = xpData.rank_up_costs || {};
        const statCosts = xpData.stat_point_costs || {};
        const isScholar = (sheet.archetype || '').toLowerCase() === 'scholar';
        const skillLabelMap = Object.fromEntries((skillMeta?.skills || []).map(s => [s.key, s.label]));

        // X6: skill rank-up cards — sorted: affordable first, then by rank desc
        const skillEntries = Object.entries(skills).filter(([, rank]) => rank < 5);
        skillEntries.sort(([, ra], [, rb]) => {
            const ca = rankCosts[ra + 1] ?? rankCosts[String(ra + 1)] ?? Infinity;
            const cb = rankCosts[rb + 1] ?? rankCosts[String(rb + 1)] ?? Infinity;
            const aAfford = typeof ca === 'number' && xpAvail >= ca ? 0 : 1;
            const bAfford = typeof cb === 'number' && xpAvail >= cb ? 0 : 1;
            if (aAfford !== bAfford) return aAfford - bAfford;
            return rb - ra; // higher rank first within same affordability
        });
        const skillCards = skillEntries.map(([key, rank]) => {
            const newRank = rank + 1;
            const cost = rankCosts[newRank] ?? rankCosts[String(newRank)] ?? '?';
            const canAfford = typeof cost === 'number' && xpAvail >= cost;
            const label = skillLabelMap[key] || key;
            return `<div class="awansuj-card ${canAfford ? '' : 'awansuj-card--locked'}">
                <div class="awansuj-card__title">${escapeHtml(label)}</div>
                <div class="awansuj-card__detail">Ranga ${rank} → ${newRank}</div>
                <button class="awansuj-card__btn awansuj-card__btn--confirm" data-action="skill" data-key="${key}" data-cost="${cost}" ${canAfford ? '' : 'disabled'}>
                    ${cost} PD
                </button>
            </div>`;
        }).join('');

        // X7: stat point-up cards — sorted affordable first
        const statEntries = Object.entries(stats).map(([key, val]) => {
            const newVal = val + 1;
            const cost = statCosts[newVal] ?? statCosts[String(newVal)];
            if (!cost || newVal > 20) return null;
            return { key, val, cost, canAfford: xpAvail >= cost };
        }).filter(Boolean);
        statEntries.sort((a, b) => (a.canAfford ? 0 : 1) - (b.canAfford ? 0 : 1));
        const statCards = statEntries.map(({ key, val, cost, canAfford }) => {
            const newVal = val + 1;
            const mod = mods[key] ?? Math.floor((val - 10) / 2);
            const newMod = Math.floor((newVal - 10) / 2);
            return `<div class="awansuj-card ${canAfford ? '' : 'awansuj-card--locked'}">
                <div class="awansuj-card__title">${STAT_LABELS[key] || key}</div>
                <div class="awansuj-card__detail">${val} (${mod >= 0 ? '+' : ''}${mod}) → ${newVal} (${newMod >= 0 ? '+' : ''}${newMod})</div>
                <button class="awansuj-card__btn awansuj-card__btn--confirm" data-action="stat" data-key="${key}" data-cost="${cost}" ${canAfford ? '' : 'disabled'}>
                    ${cost} PD
                </button>
            </div>`;
        }).join('');

        // X8: Scholar spell cards
        let spellCards = '';
        if (isScholar) {
            const [knownSpells, allSpells] = await Promise.all([
                fetch(`/api/characters/${character.id}/spells`).then(r => r.json()),
                fetch('/api/spells').then(r => r.ok ? r.json() : { spells: [] })
            ]);
            const knownMap = {};
            (knownSpells.spells || []).forEach(s => { knownMap[s.spell_key] = s.rank; });
            (allSpells.spells || []).forEach(spell => {
                const currentRank = knownMap[spell.key] ?? 0;
                if (currentRank === 0) {
                    const canAfford = xpAvail >= 75;
                    spellCards += `<div class="awansuj-card awansuj-card--spell ${canAfford ? '' : 'awansuj-card--locked'}">
                        <div class="awansuj-card__title">✨ ${escapeHtml(spell.label)}</div>
                        <div class="awansuj-card__detail">Naucz (R1)</div>
                        <button class="awansuj-card__btn awansuj-card__btn--confirm" data-action="spell-learn" data-key="${spell.key}" data-cost="75" ${canAfford ? '' : 'disabled'}>75 PD</button>
                    </div>`;
                } else if (currentRank < 3) {
                    const cost = currentRank === 1 ? 50 : 100;
                    const canAfford = xpAvail >= cost;
                    spellCards += `<div class="awansuj-card awansuj-card--spell ${canAfford ? '' : 'awansuj-card--locked'}">
                        <div class="awansuj-card__title">✨ ${escapeHtml(spell.label)}</div>
                        <div class="awansuj-card__detail">R${currentRank} → R${currentRank + 1}</div>
                        <button class="awansuj-card__btn awansuj-card__btn--confirm" data-action="spell-upgrade" data-key="${spell.key}" data-cost="${cost}" ${canAfford ? '' : 'disabled'}>${cost} PD</button>
                    </div>`;
                }
            });
        }

        const pendingNote = pendingXp > 0
            ? `<div class="awansuj-pending-note">⏳ ${pendingXp} PD oczekuje — dostępne po długim odpoczynku</div>`
            : '';

        body.innerHTML = `
            <div class="awansuj-xp-badge">Dostępne PD: <strong>${xpAvail}</strong></div>
            ${pendingNote}
            ${skillCards ? `<div class="awansuj-section-label">Umiejętności</div><div class="awansuj-grid">${skillCards}</div>` : ''}
            ${statCards ? `<div class="awansuj-section-label">Cechy</div><div class="awansuj-grid">${statCards}</div>` : ''}
            ${isScholar && spellCards ? `<div class="awansuj-section-label">Zaklęcia</div><div class="awansuj-grid">${spellCards}</div>` : ''}
            <div class="awansuj-section-label">Historia PD</div>
            <div id="awansuj-xp-log"><div class="camp-loading">Ładowanie…</div></div>`;

        loadXpLog(character, document.getElementById('awansuj-xp-log'));

        // Inline double-confirm: first click arms the button, second click spends.
        // Clicking anywhere else disarms. No browser confirm() modal.
        let _armed = null;
        const disarm = () => {
            if (_armed) {
                _armed.textContent = _armed.dataset.origLabel;
                _armed.classList.remove('awansuj-card__btn--armed');
                _armed = null;
            }
        };
        body.addEventListener('click', e => {
            const btn = e.target.closest('.awansuj-card__btn--confirm');
            if (!btn) { disarm(); return; }
            if (btn.disabled) return;

            if (_armed === btn) {
                // Second click — execute
                disarm();
                _doSpend(character, sheet, btn);
            } else {
                // First click — arm
                disarm();
                _armed = btn;
                btn.dataset.origLabel = btn.textContent.trim();
                btn.textContent = '✓ Potwierdź';
                btn.classList.add('awansuj-card__btn--armed');
            }
        }, true);
    } catch (e) {
        body.innerHTML = `<p style="color:var(--accent-red)">${escapeHtml(e.message)}</p>`;
    }
}

async function _doSpend(character, sheet, btn) {
    const { action, key, cost } = btn.dataset;
    let url, payload;
    if (action === 'skill') {
        url = `/api/characters/${character.id}/xp/spend-skill`;
        payload = { skill_key: key };
    } else if (action === 'stat') {
        url = `/api/characters/${character.id}/xp/spend-stat`;
        payload = { stat_key: key };
    } else if (action === 'spell-learn') {
        url = `/api/characters/${character.id}/xp/spend-spell-learn`;
        payload = { spell_key: key };
    } else if (action === 'spell-upgrade') {
        url = `/api/characters/${character.id}/xp/spend-spell-upgrade`;
        payload = { spell_key: key };
    } else return;

    btn.disabled = true;
    btn.textContent = '…';
    try {
        const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || 'Błąd');
        showToast(`Zakupiono! Pozostało: ${data.xp_available} PD`, 'success');
        // Reload the panel in-place with fresh character data
        const updated = await apiRequest('GET', `/characters/${character.id}`);
        characterData = updated;
        const updatedSheet = updated.sheet_json || {};
        await _renderAwansujBody(updated, updatedSheet);
        updateHeaderStats();
    } catch (e) {
        showToast('Błąd: ' + e.message, 'error');
        btn.disabled = false;
        btn.textContent = cost + ' PD';
    }
}

// X9: XP grant log (loaded into awansuj-xp-log div)
async function loadXpLog(character, container) {
    if (!container) return;
    try {
        // Stage 10-C — apiRequest attaches the Bearer header.
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

// Stage 5 E4/E6: pick the right equip slot for a backpack item.
// Armor → driven by item.armor_coverage; weapons → driven by item.weapon_slot.
function _invPickEquipSlot(item, occupied) {
    const t = String(item.item_type || '').toLowerCase();
    if (t === 'armor') {
        const k = String(item.key || item.label || '').toLowerCase();
        if (/shield|tarcz/.test(k)) return 'off_hand';
        const cov = String(item.armor_coverage || '').toLowerCase();
        if (cov === 'head') return 'head';
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
        if (ws === 'either')        return occupied.main_hand ? 'off_hand' : 'main_hand';
        return 'main_hand';
    }
    return null;
}

// Stage 5 E6: only show weapons in the right slot when filtering.
function _itemFitsSlot__weapon(item, slot) {
    const ws = String(item.weapon_slot || 'main_hand').toLowerCase();
    if (slot === 'main_hand') return ws === 'main_hand' || ws === 'two_handed' || ws === 'either';
    if (slot === 'off_hand')  return ws === 'off_hand_only' || ws === 'either';
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
    pulseGoldOnChange(goldGp);  // S9

    // Stage 5 E4-E7: bucket items + compute synthetic slot coverage for full-armor anchors.
    const equipped = {};   // slot → item (real slot OR synthetic locked-by-full)
    const lockedByFull = {}; // slot → anchor item (so the UI shows a chain)
    const backpack = [];
    const lore = [];
    const occupied = { head: false, torso: false, l_arm: false, r_arm: false,
                       l_leg: false, r_leg: false, main_hand: false, off_hand: false };

    for (const item of items) {
        if (Number(item.equipped) === 1 && item.slot) {
            equipped[item.slot] = item;
            occupied[item.slot] = true;
            // Full-coverage armor: stamp the limb slots as locked.
            for (const cs of (item.covered_slots || [])) {
                if (cs !== item.slot) {
                    lockedByFull[cs] = item;
                    occupied[cs] = true;
                }
            }
        } else if (_invIsLore(item)) {
            lore.push(item);
        } else {
            backpack.push(item);
        }
    }

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
        body = `<div class="anatomy-slot__name">${escapeHtml(item.label || item.key || '?')}</div>`;
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
    // Stage 4 S7: quest items can never be dropped — story-critical, no escape hatch.
    const isQuest = item.item_type === 'quest' || item.is_quest === true;
    const dropBtn = (isNarrative && !isQuest)
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
        document.getElementById('open-journal-btn')?.classList.remove('journal-btn--badge');
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
    // mechEffect mirrors backend wound_penalty() in vitality_service.py (issue #26 Option A).
    if (pct >= 76) return null;
    if (pct >= 51) return { label: 'Ranny',             tier: 'minor',    color: '#ffc107', mechEffect: '' };
    if (pct >= 26) return { label: 'Ciężko Ranny',      tier: 'impaired', color: '#ff9800', mechEffect: '' };
    if (pct >= 11) return { label: 'Poważnie Ranny',    tier: 'desperate',color: '#f44336', mechEffect: '-1 ATK' };
    return            { label: 'Na Skraju Śmierci', tier: 'near_death',color: '#7f0000', mechEffect: '-2 ATK, -1 DEX' };
}

// Render markup for a wound label, or empty string when above threshold.
function renderWoundLabelHTML(currentHp, maxHp) {
    const w = getWoundLabel(currentHp, maxHp);
    if (!w) return '';
    const tip = w.mechEffect ? `${w.label}: ${w.mechEffect}` : w.label;
    return `<div class="wound-label wound-label--${w.tier}" aria-label="${tip}" title="${tip}"><span class="wound-label__orn">❦</span><span class="wound-label__text">${w.label}</span><span class="wound-label__orn">❦</span></div>`;
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

    const TAB_ORDER = ['stats', 'skills', 'inventory', 'appearance', 'knowledge'];
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

    const mpMultiplayerSection = document.getElementById('mp-multiplayer-section');
    if (mpMultiplayerSection) mpMultiplayerSection.style.display = currentCampaign?.mode === 'multiplayer' ? '' : 'none';

    // Stage 8 D3 — show the 🐛 toggle only when (admin) AND (debugMode on
    // via Settings → "🐛 Pokaż debug pod wiadomościami GM"). Hidden otherwise
    // to keep the production view clean.
    _refreshDebugToggleVisibility();

    // Bug report button — visible only for is_tester users
    _refreshBugReportButton();

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
}

// Stage 9 P4 — Command palette modal.
// Single source of truth: SLASH_COMMANDS for top-level commands + DEBUG_CMD_TREE
// for /debug subcommands (admin only) + a curated /admin example subset.
// Opens via ⌘ button in composer OR Ctrl+/ keybinding. Closes on Esc / backdrop.
const _PALETTE_STATE = { items: [], filtered: [], highlighted: 0 };

function _buildPaletteItems() {
    const items = [];
    // Top-level slash commands — alias-aware from server when available
    const source = _effectiveSlashCommands();
    for (const c of source) {
        if (c.adminOnly && !playerIsAdmin()) continue;
        if (c.multiplayerOnly && !window.multiplayerUI?.isActive()) continue;
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
                        if (data.xp_unlocked > 0) {
                            showToast(`✦ ${data.xp_unlocked} PD odblokowano — dostępne w następnej przygodzie`, 'info', 4000);
                        }
                    }
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
        const xpUnlocked = data.xp_unlocked > 0 ? ` · ✦ ${data.xp_unlocked} PD odblokowano` : '';
        if (metaEl)  metaEl.textContent  = `${data.character_class || ''} · Poz. ${data.level || 1} · ${data.xp_lifetime_earned ?? 0} PD${xpUnlocked}`;
        if (titleEl) titleEl.textContent = data.ending_title || '';
        if (sumEl)   sumEl.textContent   = data.ending_summary || '';
    } catch (_e) {}
}

function hideVictoryScreen() {
    const screen = document.getElementById('victory-screen');
    if (screen) {
        screen.hidden = true;
        document.body.style.overflow = '';
    }
}
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
        showToast('Wskrzeszenie nie jest dostępne dla tego konta.', 'error');
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

// ── Onboarding cinematic ──────────────────────────────────────────────────
async function showOnboardingCinematic() {
    showScreen('onboarding');

    // Fetch inviter info
    try {
        const stats = await apiRequest('GET', '/me/stats');
        if (stats.inviter_name) {
            document.getElementById('onboarding-inviter-name').textContent = stats.inviter_name;
            document.getElementById('onboarding-inviter').hidden = false;
        }
    } catch (_) {}

    // Progress bar animation over 6s
    const bar = document.getElementById('onboarding-progress-bar');
    if (bar) {
        bar.style.transition = 'width 6s linear';
        requestAnimationFrame(() => {
            requestAnimationFrame(() => { bar.style.width = '100%'; });
        });
    }

    // CTA is shown by CSS animation at 5s — nothing else needed
}

function _advanceOnboardingToThemePicker() {
    document.getElementById('onboarding-step-1')?.classList.add('onboarding__content--hidden');
    const step2 = document.getElementById('onboarding-step-2');
    if (!step2) return;
    step2.classList.remove('onboarding__content--hidden');

    // Mark active swatch based on current saved theme
    const current = localStorage.getItem('aigm_theme') || 'dark';
    step2.querySelectorAll('.onboarding__theme-swatch').forEach(btn => {
        btn.classList.toggle('onboarding__theme-swatch--active', btn.dataset.theme === current);
    });
}

async function completeOnboarding() {
    clearTimeout(_onboardingTimer);
    try {
        await apiRequest('PATCH', '/me/onboarding');
    } catch (_) {}
    showScreen('heroes');
}

// ── Profile page ────────────────────────────────────────────────────────
function _renderProfileAvatar(avatarUrl, fallbackLetter) {
    const el = document.getElementById('profile-avatar');
    if (!el) return;
    if (avatarUrl) {
        el.innerHTML = `<img src="${avatarUrl}" alt="Avatar">`;
    } else {
        el.textContent = fallbackLetter;
    }
}

async function loadProfilePage() {
    _profileReturnScreen = currentScreen;
    showScreen('profile');
    const user = currentUser;
    if (!user) return;

    const fallbackLetter = (user.display_name || user.username || '?').charAt(0).toUpperCase();
    const nameEl = document.getElementById('profile-username');
    if (nameEl) nameEl.textContent = user.display_name || user.username;
    _renderProfileAvatar(null, fallbackLetter);

    // Show login immediately from cached user (without @, the row adds it)
    const loginEl = document.getElementById('profile-login-label');
    if (loginEl) loginEl.textContent = user.username || '';

    try {
        const stats = await apiRequest('GET', '/me/stats');
        const displayName = stats.display_name || user.display_name || user.username;
        if (nameEl) nameEl.textContent = displayName;
        _renderProfileAvatar(stats.avatar_url || null,
            (displayName || '?').charAt(0).toUpperCase());

        // Email
        const emailEl = document.getElementById('profile-email-label');
        if (emailEl) emailEl.textContent = stats.email || '';

        document.getElementById('ps-heroes').textContent = stats.heroes ?? '—';
        document.getElementById('ps-campaigns').textContent = stats.campaigns_completed ?? '—';
        document.getElementById('ps-xp').textContent = stats.lifetime_xp?.toLocaleString('pl') ?? '—';
        document.getElementById('ps-turns').textContent = stats.turns_total ?? '—';

        const sent = stats.invite_weekly_sent ?? 0;
        const limit = stats.invite_weekly_limit ?? 3;
        const quotaEl = document.getElementById('profile-invite-quota');
        if (quotaEl) quotaEl.textContent =
            sent >= limit
                ? `Limit tygodniowy wyczerpany (${limit} zaproszeń)`
                : `${sent} z ${limit} zaproszeń wysłanych w tym tygodniu`;
        const inviteBtn = document.getElementById('profile-invite-btn');
        if (inviteBtn) inviteBtn.disabled = sent >= limit;
    } catch (e) {
        console.error('[Profile] stats failed:', e);
    }
    // F1.3 — load friends list every time the profile opens
    _loadFriends();
}

async function _saveProfile(patch) {
    try {
        const resp = await apiRequest('PATCH', '/me/profile', patch);
        if (resp.display_name !== undefined && currentUser) {
            currentUser.display_name = resp.display_name;
            localStorage.setItem('user', JSON.stringify(currentUser));
        }
        return resp;
    } catch (e) {
        showToast(e.message || 'Błąd zapisu', 'error');
        return null;
    }
}

function _initProfileEditing() {
    // Contenteditable inline name edit — no separate input element
    const nameEl    = document.getElementById('profile-username');
    const editBtn   = document.getElementById('profile-name-edit-btn');
    const saveBtn   = document.getElementById('profile-name-save');
    const cancelBtn = document.getElementById('profile-name-cancel');
    let _originalName = '';

    const _focusEnd = (el) => {
        el.focus();
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    };

    // ── Display name ──────────────────────────────────────────────
    editBtn?.addEventListener('click', () => {
        _originalName = nameEl.textContent.trim();
        nameEl.contentEditable = 'true';
        _focusEnd(nameEl);
    });

    nameEl?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const newName = nameEl.textContent.trim();
            if (!newName) { nameEl.textContent = _originalName; nameEl.contentEditable = 'false'; return; }
            _saveProfile({ display_name: newName }).then(resp => {
                if (resp) {
                    nameEl.textContent = resp.display_name || newName;
                    showToast('Nazwa zaktualizowana', 'success');
                    // update localStorage
                    if (currentUser) currentUser.display_name = resp.display_name || newName;
                }
            });
            nameEl.contentEditable = 'false';
        }
        if (e.key === 'Escape') {
            nameEl.textContent = _originalName;
            nameEl.contentEditable = 'false';
        }
    });

    nameEl?.addEventListener('blur', () => {
        // Revert on blur-without-Enter
        if (nameEl.contentEditable === 'true') {
            nameEl.textContent = _originalName;
            nameEl.contentEditable = 'false';
        }
    });

    // ── @username ─────────────────────────────────────────────────
    const loginEl       = document.getElementById('profile-login-label');
    const loginEditBtn  = document.getElementById('profile-login-edit-btn');
    const loginHint     = document.getElementById('profile-login-hint');
    let _originalLogin  = '';

    const _setLoginHint = (msg, ok) => {
        if (!loginHint) return;
        loginHint.textContent = msg;
        loginHint.className = 'pf-login-hint' + (ok === true ? ' pf-login-hint--ok' : ok === false ? ' pf-login-hint--err' : '');
    };

    loginEditBtn?.addEventListener('click', () => {
        _originalLogin = loginEl.textContent.trim();
        loginEl.contentEditable = 'true';
        _setLoginHint('Enter aby zapisać · Esc aby anulować', null);
        _focusEnd(loginEl);
    });

    loginEl?.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const newLogin = loginEl.textContent.trim().toLowerCase();
            if (!newLogin) { loginEl.textContent = _originalLogin; loginEl.contentEditable = 'false'; _setLoginHint('', null); return; }
            _setLoginHint('Sprawdzanie…', null);
            try {
                const resp = await _saveProfile({ username: newLogin });
                if (resp) {
                    loginEl.textContent = resp.username || newLogin;
                    if (currentUser) { currentUser.username = resp.username || newLogin; localStorage.setItem('user', JSON.stringify(currentUser)); }
                    loginEl.contentEditable = 'false';
                    _setLoginHint('Zapisano', true);
                    setTimeout(() => _setLoginHint('', null), 2000);
                    showToast('Login zaktualizowany', 'success');
                }
            } catch (err) {
                _setLoginHint(err.message || 'Błąd', false);
            }
        }
        if (e.key === 'Escape') {
            loginEl.textContent = _originalLogin;
            loginEl.contentEditable = 'false';
            _setLoginHint('', null);
        }
    });

    loginEl?.addEventListener('blur', () => {
        if (loginEl.contentEditable === 'true') {
            loginEl.textContent = _originalLogin;
            loginEl.contentEditable = 'false';
            _setLoginHint('', null);
        }
    });

    // Avatar upload
    const avatarBtn   = document.getElementById('profile-avatar-btn');
    const avatarInput = document.getElementById('profile-avatar-input');

    avatarBtn?.addEventListener('click', () => avatarInput?.click());

    avatarInput?.addEventListener('change', async () => {
        const file = avatarInput.files?.[0];
        if (!file) return;
        if (file.size > 2 * 1024 * 1024) {
            showToast('Plik za duży (max 2 MB)', 'error');
            return;
        }
        const reader = new FileReader();
        reader.onload = async (ev) => {
            const dataUrl = ev.target.result;
            _renderProfileAvatar(dataUrl,
                (currentUser?.display_name || currentUser?.username || '?').charAt(0).toUpperCase());
            const resp = await _saveProfile({ avatar_url: dataUrl });
            if (!resp) {
                // revert on failure
                _renderProfileAvatar(null,
                    (currentUser?.display_name || currentUser?.username || '?').charAt(0).toUpperCase());
            } else {
                showToast('Zdjęcie zaktualizowane', 'success');
            }
        };
        reader.readAsDataURL(file);
        avatarInput.value = '';
    });

    // ── Inline change-password form ─────────────────────────────────────────
    const changePwBtn     = document.getElementById('profile-change-password-btn');
    const pwFields        = document.getElementById('pf-password-fields');
    const pwSaveBtn       = document.getElementById('pf-password-save-btn');
    const pwCancelBtn     = document.getElementById('pf-password-cancel-btn');
    const pwErrorEl       = document.getElementById('pf-password-error');
    const currentPwInput  = document.getElementById('pf-current-password');
    const newPwInput      = document.getElementById('pf-new-password');
    const confirmPwInput  = document.getElementById('pf-confirm-password');

    changePwBtn?.addEventListener('click', () => {
        const open = pwFields && !pwFields.hidden;
        if (pwFields) pwFields.hidden = open;
        changePwBtn.classList.toggle('pf-row-btn--open', !open);
        if (!open && currentPwInput) currentPwInput.focus();
    });

    pwCancelBtn?.addEventListener('click', () => {
        if (pwFields) pwFields.hidden = true;
        changePwBtn?.classList.remove('pf-row-btn--open');
        [currentPwInput, newPwInput, confirmPwInput].forEach(el => { if (el) el.value = ''; });
        if (pwErrorEl) pwErrorEl.hidden = true;
    });

    pwSaveBtn?.addEventListener('click', async () => {
        if (pwErrorEl) pwErrorEl.hidden = true;
        const current = currentPwInput?.value || '';
        const newPw   = newPwInput?.value || '';
        const confirm = confirmPwInput?.value || '';

        if (!current) { _showPwError('Wprowadź obecne hasło'); return; }
        if (newPw.length < 8) { _showPwError('Nowe hasło musi mieć min. 8 znaków'); return; }
        if (newPw !== confirm) { _showPwError('Hasła nie są identyczne'); return; }

        pwSaveBtn.disabled = true;
        pwSaveBtn.textContent = 'Zapisywanie…';
        try {
            await apiRequest('POST', '/auth/change-password', {
                current_password: current,
                new_password: newPw,
            });
            showToast('Hasło zmienione', 'success');
            pwCancelBtn?.click();
        } catch (e) {
            _showPwError(e.message || 'Błąd zmiany hasła');
        } finally {
            pwSaveBtn.disabled = false;
            pwSaveBtn.textContent = 'Zapisz hasło';
        }
    });

    function _showPwError(msg) {
        if (!pwErrorEl) return;
        pwErrorEl.textContent = msg;
        pwErrorEl.hidden = false;
    }

    // ── F1.2 — Delete account (soft-delete with 7-day grace) ─────────────────
    const delBtn       = document.getElementById('profile-delete-account-btn');
    const delFields    = document.getElementById('pf-delete-fields');
    const delConfirm   = document.getElementById('pf-delete-confirm-btn');
    const delCancel    = document.getElementById('pf-delete-cancel-btn');
    const delPwInput   = document.getElementById('pf-delete-password');
    const delErrorEl   = document.getElementById('pf-delete-error');

    delBtn?.addEventListener('click', () => {
        const open = delFields && !delFields.hidden;
        if (delFields) delFields.hidden = open;
        delBtn.classList.toggle('pf-row-btn--open', !open);
        if (!open && delPwInput) delPwInput.focus();
    });

    delCancel?.addEventListener('click', () => {
        if (delFields) delFields.hidden = true;
        delBtn?.classList.remove('pf-row-btn--open');
        if (delPwInput) delPwInput.value = '';
        if (delErrorEl) delErrorEl.hidden = true;
    });

    delConfirm?.addEventListener('click', async () => {
        if (delErrorEl) delErrorEl.hidden = true;
        const pw = delPwInput?.value || '';
        if (!pw) { _showDelError('Wprowadź hasło, aby potwierdzić'); return; }

        delConfirm.disabled = true;
        delConfirm.textContent = 'Usuwanie…';
        try {
            const resp = await apiRequest('POST', '/auth/delete-account', { current_password: pw });
            const deadline = resp?.undo_deadline ? _formatDeadline(resp.undo_deadline) : '';
            showToast(
                `Konto zaplanowane do usunięcia. Możesz cofnąć logując się do ${deadline}.`,
                'success',
            );
            // Force logout
            handleLogout();
        } catch (e) {
            _showDelError(e.message || 'Błąd usuwania konta');
            delConfirm.disabled = false;
            delConfirm.textContent = 'Tak, usuń moje konto';
        }
    });

    function _showDelError(msg) {
        if (!delErrorEl) return;
        delErrorEl.textContent = msg;
        delErrorEl.hidden = false;
    }
}

// Helper: format an ISO timestamp as DD.MM.YYYY HH:MM
function _formatDeadline(iso) {
    try {
        const d = new Date(iso);
        return d.toLocaleString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (_e) { return iso; }
}

// ── F1.3 — Friends panel ────────────────────────────────────────────────────
let _friendsSearchTimer = null;

function _friendInitial(u) {
    const s = (u.display_name || u.username || '?').trim();
    return s ? s.charAt(0).toUpperCase() : '?';
}

function _friendRowHtml(user, ctx /* 'search' | 'incoming' | 'outgoing' | 'accepted' */) {
    const avatarBg = user.avatar_url
        ? `style="background-image:url('${user.avatar_url.replace(/'/g, "&apos;")}'); color:transparent"`
        : '';
    let actions = '';
    if (ctx === 'search') {
        if (user.status === 'none')
            actions = `<button class="pf-friend-btn pf-friend-btn--accent" data-act="request" data-uid="${user.id}">+ Dodaj</button>`;
        else if (user.status === 'pending_outgoing')
            actions = `<span class="pf-friend-status-chip">Wysłano</span>`;
        else if (user.status === 'pending_incoming')
            actions = `<button class="pf-friend-btn pf-friend-btn--accent" data-act="accept" data-fid="${user.friendship_id}">Akceptuj</button>`;
        else if (user.status === 'accepted')
            actions = `<span class="pf-friend-status-chip">Znajomy</span>`;
    } else if (ctx === 'incoming') {
        actions = `
            <button class="pf-friend-btn pf-friend-btn--accent" data-act="accept" data-fid="${user.friendship_id}">Akceptuj</button>
            <button class="pf-friend-btn pf-friend-btn--danger" data-act="delete" data-fid="${user.friendship_id}">Odrzuć</button>`;
    } else if (ctx === 'outgoing') {
        actions = `<button class="pf-friend-btn pf-friend-btn--danger" data-act="delete" data-fid="${user.friendship_id}">Anuluj</button>`;
    } else if (ctx === 'accepted') {
        actions = `<button class="pf-friend-btn pf-friend-btn--danger" data-act="delete" data-fid="${user.friendship_id}">Usuń</button>`;
    }
    return `
        <div class="pf-friend-row" data-uid="${user.id}">
            <div class="pf-friend-avatar" ${avatarBg}>${_friendInitial(user)}</div>
            <div class="pf-friend-meta">
                <div class="pf-friend-name">${(user.display_name || user.username || '').replace(/</g, '&lt;')}</div>
                <div class="pf-friend-login">@${(user.username || '').replace(/</g, '&lt;')}</div>
            </div>
            <div class="pf-friend-actions">${actions}</div>
        </div>`;
}

async function _loadFriends() {
    try {
        const data = await apiRequest('GET', '/me/friends');
        const accepted = data.accepted || [];
        const incoming = data.incoming || [];
        const outgoing = data.outgoing || [];

        const renderList = (id, items, ctx, emptyHtml) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.innerHTML = items.length
                ? items.map(u => _friendRowHtml(u, ctx)).join('')
                : (emptyHtml || '');
        };
        renderList('pf-friends-accepted', accepted, 'accepted',
            '<p class="pf-friends-empty">Jeszcze nikogo nie dodałeś. Wyszukaj kogoś powyżej.</p>');
        renderList('pf-friends-incoming', incoming, 'incoming');
        renderList('pf-friends-outgoing', outgoing, 'outgoing');
        document.getElementById('pf-friends-incoming-wrap').hidden = incoming.length === 0;
        document.getElementById('pf-friends-outgoing-wrap').hidden = outgoing.length === 0;
    } catch (e) {
        console.error('[Friends] load failed:', e);
    }
}

async function _searchFriends(q) {
    const resultsEl = document.getElementById('pf-friends-search-results');
    if (!resultsEl) return;
    if (!q || q.length < 2) {
        resultsEl.innerHTML = '';
        return;
    }
    try {
        const data = await apiRequest('GET', `/me/friends/search?q=${encodeURIComponent(q)}`);
        const items = data.results || [];
        resultsEl.innerHTML = items.length
            ? items.map(u => _friendRowHtml(u, 'search')).join('')
            : '<p class="pf-friends-empty">Brak wyników</p>';
    } catch (e) {
        console.error('[Friends] search failed:', e);
        resultsEl.innerHTML = '<p class="pf-friends-empty">Błąd wyszukiwania</p>';
    }
}

async function _handleFriendAction(act, target) {
    try {
        if (act === 'request') {
            const uid = parseInt(target.dataset.uid, 10);
            await apiRequest('POST', '/me/friends/request', { target_user_id: uid });
            showToast('Zaproszenie wysłane', 'success');
        } else if (act === 'accept') {
            const fid = parseInt(target.dataset.fid, 10);
            await apiRequest('POST', `/me/friends/${fid}/accept`);
            showToast('Dodano do drużyny', 'success');
        } else if (act === 'delete') {
            const fid = parseInt(target.dataset.fid, 10);
            await apiRequest('DELETE', `/me/friends/${fid}`);
        }
        // Refresh both list and any open search results
        await _loadFriends();
        const searchInput = document.getElementById('pf-friends-search-input');
        if (searchInput && searchInput.value.trim().length >= 2) {
            await _searchFriends(searchInput.value.trim());
        }
    } catch (e) {
        showToast(e.message || 'Błąd operacji', 'error');
    }
}

function _initFriendsPanel() {
    const input = document.getElementById('pf-friends-search-input');
    input?.addEventListener('input', () => {
        clearTimeout(_friendsSearchTimer);
        const q = input.value.trim();
        _friendsSearchTimer = setTimeout(() => _searchFriends(q), 250);
    });

    // Event delegation for all friend-row buttons (search results + section lists)
    document.getElementById('profile-screen')?.addEventListener('click', (e) => {
        const btn = e.target.closest('.pf-friend-btn[data-act]');
        if (!btn) return;
        _handleFriendAction(btn.dataset.act, btn);
    });
}

// ── Invite modal ─────────────────────────────────────────────────────────
function openInviteModal() {
    const form = document.getElementById('invite-form');
    const result = document.getElementById('invite-result');
    const btn = document.getElementById('invite-submit-btn');
    if (form) { form.reset(); form.hidden = false; }
    if (result) result.hidden = true;
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn__icon">📨</span> Wyślij zaproszenie';
    }
    document.getElementById('invite-modal').hidden = false;
}

function closeInviteModal() {
    document.getElementById('invite-modal').hidden = true;
}

async function handleSendInvite(e) {
    e.preventDefault();
    const email   = document.getElementById('invite-email').value.trim();
    const message = document.getElementById('invite-message').value.trim();
    if (!email) { showToast('Podaj adres email', 'error'); return; }

    const btn = document.getElementById('invite-submit-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn__icon">⏳</span> Wysyłanie...';

    try {
        const resp = await apiRequest('POST', '/me/invites', { email, message: message || null });
        const linkEl = document.getElementById('invite-link-display');
        if (linkEl) linkEl.value = resp.invite_link || '';
        document.getElementById('invite-form').hidden = true;
        document.getElementById('invite-result').hidden = false;
        showToast('Zaproszenie wysłane!', 'success');
    } catch (err) {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn__icon">📨</span> Wyślij zaproszenie';
        showToast(err.message || 'Błąd wysyłania zaproszenia', 'error');
    }
}

function initEventListeners() {
    // Login
    elements.loginForm?.addEventListener('submit', handleLogin);

    // Auth screens
    document.getElementById('register-form')?.addEventListener('submit', handleRegister);
    document.getElementById('forgot-form')?.addEventListener('submit', handleForgotPassword);
    document.getElementById('reset-form')?.addEventListener('submit', handleResetPassword);
    document.getElementById('resend-verify-btn')?.addEventListener('click', handleResendVerification);

    document.getElementById('forgot-password-link')?.addEventListener('click', () => {
        const successEl = document.getElementById('forgot-success');
        if (successEl) successEl.hidden = true;
        const submitBtn = document.getElementById('forgot-submit-btn');
        if (submitBtn) submitBtn.hidden = false;
        showScreen('forgotPassword');
    });
    document.getElementById('register-link')?.addEventListener('click', () => showScreen('register'));
    document.getElementById('register-back-link')?.addEventListener('click', () => showScreen('login'));
    document.getElementById('verify-back-link')?.addEventListener('click', () => showScreen('login'));
    document.getElementById('forgot-back-link')?.addEventListener('click', () => showScreen('login'));
    document.getElementById('reset-back-link')?.addEventListener('click', () => showScreen('login'));

    // Onboarding — step 1 CTA advances to theme picker
    document.getElementById('onboarding-cta')?.addEventListener('click', _advanceOnboardingToThemePicker);
    // Onboarding — theme swatches
    document.getElementById('onboarding-themes')?.addEventListener('click', e => {
        const btn = e.target.closest('.onboarding__theme-swatch');
        if (!btn) return;
        document.querySelectorAll('.onboarding__theme-swatch').forEach(b => b.classList.remove('onboarding__theme-swatch--active'));
        btn.classList.add('onboarding__theme-swatch--active');
        applyTheme(btn.dataset.theme);
    });
    // Onboarding — final "Zaczynam przygodę" button
    document.getElementById('onboarding-start')?.addEventListener('click', completeOnboarding);

    // Profile page
    document.getElementById('profile-back-btn')?.addEventListener('click', () => showScreen(_profileReturnScreen || 'heroes'));
    _initProfileEditing();
    _initFriendsPanel();
    document.getElementById('go-to-profile-btn')?.addEventListener('click', () => {
        closeSettings();
        loadProfilePage();
    });
    document.getElementById('profile-invite-btn')?.addEventListener('click', openInviteModal);
    // Invite modal
    document.getElementById('invite-modal-backdrop')?.addEventListener('click', closeInviteModal);
    document.getElementById('invite-modal-close')?.addEventListener('click', closeInviteModal);
    document.getElementById('invite-form')?.addEventListener('submit', handleSendInvite);
    document.getElementById('invite-copy-btn')?.addEventListener('click', () => {
        const linkEl = document.getElementById('invite-link-display');
        if (!linkEl) return;
        navigator.clipboard?.writeText(linkEl.value).then(() => {
            showToast('Link skopiowany!', 'success');
        }).catch(() => {
            linkEl.select();
            document.execCommand('copy');
            showToast('Link skopiowany!', 'success');
        });
    });
    document.getElementById('invite-another-btn')?.addEventListener('click', () => {
        const form = document.getElementById('invite-form');
        const result = document.getElementById('invite-result');
        const btn = document.getElementById('invite-submit-btn');
        if (form) { form.reset(); form.hidden = false; }
        if (result) result.hidden = true;
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span class="btn__icon">📨</span> Wyślij zaproszenie';
        }
    });
    document.getElementById('heroes-invite-btn')?.addEventListener('click', openInviteModal);

    // Heroes
    elements.btnNewHero?.addEventListener('click', () => {
        currentHero = null;
        currentCampaignId = null;
        currentCampaign = null;
        characterData = null;
        startCharacterWizard();
    });
    elements.btnHeroesLogout?.addEventListener('click', () => loadProfilePage());
    document.getElementById('profile-logout-btn')?.addEventListener('click', handleLogout);

    // Campaigns
    elements.btnNewCampaign?.addEventListener('click', showNewCampaignScreen);
    elements.btnLogout?.addEventListener('click', () => { loadHeroes().then(() => showScreen('heroes')); });

    // New Campaign
    elements.newCampaignForm?.addEventListener('submit', handleCreateCampaign);
    elements.btnNewCampaignBack?.addEventListener('click', () => showScreen('campaigns'));

    // Campaign Style Screen
    document.getElementById('campaign-style-back')?.addEventListener('click', () => showScreen('newCampaign'));
    document.getElementById('campaign-style-submit')?.addEventListener('click', _finalCreateCampaign);

    // Prebuilt Campaign Screen
    document.getElementById('prebuilt-back')?.addEventListener('click', () => showScreen('campaigns'));


    // Idle hero panel
    document.getElementById('idle-hero-panel-backdrop')?.addEventListener('click', _hideIdleHeroPanel);
    document.getElementById('idle-hero-panel-close')?.addEventListener('click', _hideIdleHeroPanel);
    document.getElementById('idle-hero-panel-proceed')?.addEventListener('click', _proceedFromIdlePanel);
    document.getElementById('idle-hero-panel-history')?.addEventListener('click', () => {
        _hideIdleHeroPanel();
        if (currentHero) openHeroHistoryModal(currentHero);
    });
    document.getElementById('idle-hero-panel-awansuj')?.addEventListener('click', () => {
        _hideIdleHeroPanel();
        if (currentHero) {
            const sheet = (typeof currentHero.sheet_json === 'string' ? JSON.parse(currentHero.sheet_json || '{}') : currentHero.sheet_json) || {};
            characterData = currentHero;
            openAwansujPanel(currentHero, sheet);
        }
    });

    // Stage 8 D3 — debug drawer toggle (admin only; visibility set by updateAdminSettingsVisibility)
    document.getElementById('debug-drawer-toggle')?.addEventListener('click', _toggleDebugDrawer);

    // Stage 9 P4 — command palette modal
    _wirePaletteEvents();
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
    // Stage 4 follow-up: header home icon → main heroes screen (was: open sheet).
    // Sheet access now lives in the mobile bottom bar's "Postać" button.
    elements.btnHome?.addEventListener('click', () => {
        if (isSheetOpen) closeCharacterSheet();
        showScreen('heroes');
    });
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
    elements.btnSend?.addEventListener('click', (e) => {
        if (_activeTurnAbort) { _cancelActiveTurn(); return; }
        handleSendMessage();
    });
    elements.chatInput?.addEventListener('keypress', handleKeyPress);
    elements.chatInput?.addEventListener('input', updateCharCounter);
    initSlashAutocomplete(elements.chatInput);

    // Sheet tabs
    elements.sheetTabs.forEach(tab => {
        tab.addEventListener('click', handleSheetTabClick);
    });

    // Stage 4 S12: mobile bottom bar
    document.getElementById('mobile-bottom-bar')?.addEventListener('click', handleMobileBarClick);

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

    // Death screen buttons
    document.getElementById('resurrect-btn')?.addEventListener('click', handleResurrect);
    document.getElementById('death-return-btn')?.addEventListener('click', handleDeathReturn);

    // Stage 9 P7 — post-end option buttons, shared between death + victory screens.
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-end-action]');
        if (!btn) return;
        handleEndAction(btn.dataset.endAction);
    });

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
            header.classList.add('is-open');
        }

        header.addEventListener('click', () => {
            const open = fold.hasAttribute('hidden');
            fold.toggleAttribute('hidden', !open);
            if (chevron) chevron.classList.toggle('settings-group__chevron--open', open);
            header.classList.toggle('is-open', open);
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
            // Stage 8 follow-up: 🐛 drawer toggle visibility follows this same setting.
            _refreshDebugToggleVisibility();
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
        // /debug also spans multiple words — same treatment.
        if (/^debug(\s|$)/i.test(token)) {
            return { idx, query: token, isDebug: true };
        }
        // /roll [skill] [intent] — spans up to two words (skill + free-text intent)
        if (/^roll(\s|$)/i.test(token)) {
            return { idx, query: token, isRoll: true };
        }
        // /whisper [name] — suggests session player names
        if (/^whisper(\s|$)/i.test(token)) {
            return { idx, query: token, isWhisper: true };
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
        // Scroll the highlighted item into view (popup has overflow-y:auto + max-height)
        const activeEl = popup.querySelector('.slash-popup-item--active');
        if (activeEl) activeEl.scrollIntoView({ block: 'nearest' });
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
        // /admin: re-sync to show subcommand suggestions after picking a top-level verb
        // /roll: hide popup — skill is now in input, user types free-text intent then Enter
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
        } else if (ctx.isDebug) {
            // Stage 8 follow-up — /debug subcommand autocomplete (admin only).
            if (!playerIsAdmin()) { hide(); return; }
            const afterDebug = ctx.query.replace(/^debug\s*/i, '');
            found = getDebugSuggestions(afterDebug);
        } else if (ctx.isRoll) {
            // /roll [skill] [intent] — admin-only skill picker with free-text intent
            if (!playerIsAdmin()) { hide(); return; }
            const afterRoll = ctx.query.replace(/^roll\s*/i, '');
            // Fetch skill list async (cached after first call)
            _fetchRollSkills().then(skills => {
                const sugg = getRollSuggestions(afterRoll, skills);
                if (!sugg.length) { hide(); return; }
                matches = sugg;
                hi = 0;
                showPopup();
            });
            return; // async path — skip synchronous found assignment
        } else if (ctx.isWhisper) {
            if (!window.multiplayerUI?.isActive()) { hide(); return; }
            const partial = ctx.query.replace(/^whisper\s*/i, '').toLowerCase();
            const players = window.multiplayerUI.getSessionPlayers();
            found = players
                .filter(name => !partial || name.toLowerCase().startsWith(partial))
                .map(name => ({ cmd: '/whisper ' + name, desc: 'szept prywatny' }));
        } else {
            // Use alias-aware list from server; kick off async fetch if not cached
            if (!_publicSlashCache) {
                _fetchPublicSlashCommands().then(rows => {
                    if (rows) sync();  // re-render once data lands
                });
            }
            const list = _effectiveSlashCommands();
            found = list
                .filter(c => !c.adminOnly || playerIsAdmin())
                .filter(c => !c.multiplayerOnly || !!window.multiplayerUI?.isActive())
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

        // Hero found but no active campaign — check for pending lobby restore
        if (typeof tryRestoreLobbySession === 'function' && await tryRestoreLobbySession()) {
            return true;
        }
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

    // Warm the alias-aware slash-command cache (non-blocking)
    _fetchPublicSlashCommands();

    if (checkUrlRouting()) return;

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
        const ts = Date.now();
        for (const [screen, url] of Object.entries(bgs)) {
            if (url) {
                document.documentElement.style.setProperty(
                    `--bg-screen-${screen}`,
                    `url("${url}?t=${ts}")`
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
  travelPath: [],        // [{q,r}] active travel path from backend
  travelHead: -1,        // index of currently animated hex (-1 = none)
  journal: null,         // #wmap-travel-journal element
  level: 0,             // 0 = world, 1 = local
  parentHex: null,       // {q, r, label} when in local mode
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

  // Build path lookup for animation highlighting
  const _pathIdx = (q, r) => _wmap.travelPath.findIndex(p => p.q === q && p.r === r);

  for (const hex of _wmap.hexes) {
    const {x, y} = _wmHexToPixel(hex.q, hex.r);
    const {x:sx, y:sy} = _wmWorld(x, y);
    const discovered = hex.status === 'discovered';
    const isCurrent = _wmap.currentHex && _wmap.currentHex.q === hex.q && _wmap.currentHex.r === hex.r;
    const cfg = _wmap.hexTypes[hex.hex_type] || {};

    // Travel path highlighting
    const pi = _pathIdx(hex.q, hex.r);
    const isOnPath = pi >= 0;
    const isPassed = isOnPath && pi <= _wmap.travelHead;
    const isHead = pi === _wmap.travelHead && pi >= 0;

    if (discovered) {
      let fill = cfg.map_color || '#4a6a4a';
      let stroke = isCurrent ? '#f0c040' : '#1a1612';
      let sw = isCurrent ? 2.5 : 0.8;
      if (isHead) { stroke = '#f0c040'; sw = 3; fill = `color-mix(in srgb, ${fill} 70%, #c9961a 30%)`; }
      else if (isPassed) { stroke = 'rgba(240,192,64,0.55)'; sw = 1.8; }
      html += `<polygon class="wm-hex" data-q="${hex.q}" data-r="${hex.r}"
        points="${_wmCorners(sx, sy, rz-1)}"
        fill="${fill}" stroke="${stroke}" stroke-width="${sw}" style="cursor:pointer"/>`;
      if (_wmap.zoom >= 0.9 && cfg.map_icon)
        html += `<text x="${sx}" y="${sy-rz*0.05}" text-anchor="middle"
          font-size="${Math.max(10, 13*_wmap.zoom)}" style="pointer-events:none">${cfg.map_icon}</text>`;
      if (_wmap.zoom >= 1.0 && hex.label)
        html += `<text x="${sx}" y="${sy+rz*0.38}" text-anchor="middle"
          font-size="${Math.max(7, 9*_wmap.zoom)}" fill="#c8b87a" style="pointer-events:none">${escapeHtml(hex.label.slice(0,14))}</text>`;
      if (isCurrent && !isHead)
        html += `<text x="${sx}" y="${sy-rz*0.52}" text-anchor="middle"
          font-size="${Math.max(11, 14*_wmap.zoom)}" style="pointer-events:none">📍</text>`;
    } else if (hex.status === 'unexplored') {
      // Phantom hex — not in world_hexes yet, will be generated on travel
      html += `<polygon class="wm-hex wm-hex--unexplored" data-q="${hex.q}" data-r="${hex.r}"
        points="${_wmCorners(sx, sy, rz-1)}"
        fill="transparent" stroke="rgba(180,160,100,0.18)" stroke-width="0.5" stroke-dasharray="2,4"
        style="cursor:pointer"/>`;
    } else {
      // Outline: unvisited but mapped adjacent hex
      const outlineStroke = isPassed ? 'rgba(240,192,64,0.4)' : '#2a2218';
      const outlineSw = isPassed ? 1.5 : 0.6;
      html += `<polygon class="wm-hex wm-hex--outline" data-q="${hex.q}" data-r="${hex.r}"
        points="${_wmCorners(sx, sy, rz-1)}"
        fill="${isPassed ? 'rgba(240,192,64,0.04)' : 'transparent'}" stroke="${outlineStroke}" stroke-width="${outlineSw}" stroke-dasharray="3,2"
        style="cursor:pointer"/>`;
    }
  }

  // Travel path connector polyline (drawn after hexes so it's on top)
  if (_wmap.travelHead >= 0 && _wmap.travelPath.length > 1) {
    const visPath = _wmap.travelPath.slice(0, _wmap.travelHead + 1);
    const pts = visPath.map(({q,r}) => {
      const {x,y} = _wmHexToPixel(q,r);
      const {x:sx,y:sy} = _wmWorld(x,y);
      return `${sx},${sy}`;
    }).join(' ');
    html += `<polyline class="wmap-path-line" points="${pts}"
      fill="none" stroke="rgba(240,192,64,0.38)" stroke-width="${1.4*_wmap.zoom}"
      stroke-dasharray="${4*_wmap.zoom},${3*_wmap.zoom}" style="pointer-events:none"/>`;
    // Animated cursor dot at head
    const head = _wmap.travelPath[_wmap.travelHead];
    const {x:hx,y:hy} = _wmHexToPixel(head.q, head.r);
    const {x:hsx,y:hsy} = _wmWorld(hx,hy);
    const cr = Math.max(4, 5 * _wmap.zoom);
    html += `<circle class="wmap-travel-cursor" cx="${hsx}" cy="${hsy}" r="${cr}"
      fill="rgba(240,192,64,0.85)" style="pointer-events:none"/>`;
    html += `<circle class="wmap-travel-cursor-ring" cx="${hsx}" cy="${hsy}" r="${cr*1.9}"
      fill="none" stroke="rgba(240,192,64,0.35)" stroke-width="1" style="pointer-events:none"/>`;
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

  // For the current hex, prefer the live location badge label if the hex has no own label
  const isCurrent = _wmap.currentHex && _wmap.currentHex.q === q && _wmap.currentHex.r === r;
  const locationLabel = isCurrent ? (characterData?.current_location_label || null) : null;
  const label = hex.label || locationLabel || `(${q},${r})`;
  const cfg = _wmap.hexTypes[hex.hex_type] || {};
  const typeName = cfg.label || hex.hex_type || '';
  const info = hex.status === 'discovered'
    ? typeName
    : `${typeName} — nieznany teren`;

  _wmap.pendingTravel = { q, r, label };
  const confirm = _wmap.confirm;
  const isSameHex = isCurrent;
  confirm.querySelector('#wmap-confirm-title').textContent = isSameHex
    ? `Jesteś tutaj: ${label}`
    : `Podróżujesz do ${label}`;
  confirm.querySelector('#wmap-confirm-info').textContent = info;
  // Zoom-in button for town/castle hexes (world mode only)
  const zoomBtn = confirm.querySelector('#wmap-btn-zoom');
  if (zoomBtn) {
    const canZoom = _wmap.level === 0 && (hex.hex_type === 'town' || hex.hex_type === 'castle') && hex.status === 'discovered';
    zoomBtn.style.display = canZoom ? '' : 'none';
    if (canZoom) {
      zoomBtn.onclick = () => _wmZoomIn(q, r, label);
    }
  }
  confirm.removeAttribute('hidden');
}

// ── Travel journal helpers ────────────────────────────────────────────────────

function _wmJournalShow(state) {
  const el = _wmap.journal;
  if (!el) return;
  // Removing [hidden] triggers :not([hidden]) → transform:translateY(0) transition
  el.removeAttribute('hidden');
  if (state === 'loading') {
    el.querySelector('#wmap-tj-title').textContent = 'WYRUSZASZ';
    const sp = el.querySelector('#wmap-tj-spinner');
    sp.className = 'wmap-tj-spinner';
    el.querySelector('#wmap-tj-route').innerHTML = '';
    el.querySelector('#wmap-tj-meta').textContent = '';
    el.querySelector('#wmap-tj-atmo').textContent = '';
    el.querySelector('#wmap-tj-atmo').classList.remove('wmap-tj-atmo--visible');
    el.querySelector('#wmap-tj-encounter').setAttribute('hidden', '');
  }
}

function _wmJournalBuildStops(path) {
  const route = _wmap.journal?.querySelector('#wmap-tj-route');
  if (!route || !path.length) return;
  // Sample: show all if ≤ 8 stops, else pick evenly
  const n = path.length;
  let indices = [];
  if (n <= 8) { indices = path.map((_, i) => i); }
  else {
    indices = [0];
    const step = (n - 2) / 5;
    for (let k = 1; k <= 5; k++) indices.push(Math.round(step * k));
    indices.push(n - 1);
    indices = [...new Set(indices)].sort((a, b) => a - b);
  }
  let html = '';
  indices.forEach((pi, i) => {
    const { q, r } = path[pi];
    const hex = _wmap.hexes.find(h => h.q === q && h.r === r);
    const cfg = hex ? (_wmap.hexTypes[hex.hex_type] || {}) : {};
    const icon = cfg.map_icon || '·';
    if (i > 0) html += `<span class="wmap-tj-arrow">›</span>`;
    html += `<div class="wmap-tj-stop" id="wmap-tj-stop-pi${pi}" data-path-idx="${pi}">
      <div class="wmap-tj-stop-icon">${icon}</div>
    </div>`;
  });
  route.innerHTML = html;
  // Reveal first stop immediately
  requestAnimationFrame(() => route.querySelector('.wmap-tj-stop')?.classList.add('wmap-tj-stop--visible'));
  return indices;
}

function _wmJournalUpdateStop(pathIdx, mode, sampledIndices) {
  const route = _wmap.journal?.querySelector('#wmap-tj-route');
  if (!route) return;
  // Find the closest sampled stop for this path index
  if (!sampledIndices) return;
  const closest = sampledIndices.reduce((best, si) =>
    Math.abs(si - pathIdx) < Math.abs(best - pathIdx) ? si : best, sampledIndices[0]);
  const stopEl = route.querySelector(`#wmap-tj-stop-pi${closest}`);
  if (!stopEl) return;
  stopEl.classList.add('wmap-tj-stop--visible');
  const icon = stopEl.querySelector('.wmap-tj-stop-icon');
  if (!icon) return;
  icon.className = 'wmap-tj-stop-icon';
  if (mode === 'encounter') icon.classList.add('wmap-tj-stop-icon--encounter');
  else if (mode === 'arrived') icon.classList.add('wmap-tj-stop-icon--arrived');
  else icon.classList.add('wmap-tj-stop-icon--active');
}

function _wmJournalArrived(response, destLabel) {
  const el = _wmap.journal;
  if (!el) return;
  el.querySelector('#wmap-tj-title').textContent = 'DOTARŁEŚ';
  const sp = el.querySelector('#wmap-tj-spinner');
  sp.className = 'wmap-tj-spinner wmap-tj-spinner--done';
  const hours = response.total_hours || 0;
  if (hours > 0) {
    const hStr = Number.isInteger(hours) ? `${hours}` : hours.toFixed(1);
    const hWord = hours === 1 ? 'godzina' : (hours < 5 ? 'godziny' : 'godzin');
    el.querySelector('#wmap-tj-meta').textContent = `${hStr} ${hWord} w drodze`;
  }
  const atmo = response.hex_data?.atmosphere;
  if (atmo) {
    const atmoEl = el.querySelector('#wmap-tj-atmo');
    atmoEl.textContent = atmo;
    requestAnimationFrame(() => atmoEl.classList.add('wmap-tj-atmo--visible'));
  }
  if (response.encounter?.enemy_key) {
    el.querySelector('#wmap-tj-encounter').removeAttribute('hidden');
  }
}

function _wmJournalHide() {
  const el = _wmap.journal;
  if (!el) return;
  // Adding [hidden] triggers transform:translateY(100%) transition (slide-down)
  el.setAttribute('hidden', '');
  _wmap.travelPath = [];
  _wmap.travelHead = -1;
}

async function _wmAnimateTravelPath(path, encounterHex, sampledIndices) {
  if (!path.length) { _wmap.travelHead = -1; return; }
  _wmap.travelPath = path;
  const steps = path.length;
  const stepDelay = Math.max(120, Math.min(320, 1600 / steps));

  for (let i = 0; i < steps; i++) {
    _wmap.travelHead = i;
    _wmRender();
    _wmJournalUpdateStop(i, i === steps - 1 ? 'arrived' : 'active', sampledIndices);

    const isEncHex = encounterHex && encounterHex.q === path[i].q && encounterHex.r === path[i].r;
    if (isEncHex) {
      _wmJournalUpdateStop(i, 'encounter', sampledIndices);
      await new Promise(r => setTimeout(r, 500));
      break;
    }
    await new Promise(r => setTimeout(r, stepDelay));
  }
}

async function _wmExecuteTravel() {
  const t = _wmap.pendingTravel;
  if (!t) return;
  _wmap.confirm.setAttribute('hidden', '');

  if (!currentCampaignId || !characterData?.id) return;

  _wmJournalShow('loading');

  // Preload tips cache in parallel so cinematic has no tip-fetch delay
  const tipsPreload = _loadKnowledgeTips();

  try {
    const response = await apiRequest('POST', `/campaigns/${currentCampaignId}/hex-travel`, {
      character_id: characterData.id,
      destination_q: t.q,
      destination_r: t.r,
    });

    if (response.ok === false) {
      _wmJournalHide();
      showToast(response.error || 'Nie można podróżować do tego miejsca.', 'error');
      return;
    }

    if (response.clock) renderClock(response.clock);

    const enc = response.encounter;
    const hours = response.total_hours || 0;
    const arrivedHex = response.arrived_hex || {};
    const arrivedData = response.hex_data || {};
    const path = response.path || [];

    const sampledIndices = _wmJournalBuildStops(path);
    const encounterHex = enc ? response.encounter_hex : null;
    await _wmAnimateTravelPath(path, encounterHex, sampledIndices);

    if (arrivedHex.q !== undefined) {
      _wmap.currentHex = arrivedHex;
      _wmap.travelHead = -1;
      _wmRender();
    }

    const hexTypeName = (_wmap.hexTypes?.[arrivedData.hex_type]?.label) || arrivedData.hex_type || '';
    const rawLabel = t.label && !t.label.match(/^\([-\d]+,[-\d]+\)$/) ? t.label : null;
    const destLabel = rawLabel || arrivedData.label || null;

    _wmJournalArrived(response, destLabel);

    // Short pause so journal DOTARŁEŚ is readable, then close map
    await new Promise(r => setTimeout(r, 1000));
    _wmClose();
    // Wait for map slide-out before overlay covers the screen
    await new Promise(r => setTimeout(r, 360));

    // Pick a tip from the cycling pool (round-robin through all knowledge tips)
    let cinTip = null;
    try {
      const tips = await tipsPreload;
      if (tips.length) {
        const idx = parseInt(localStorage.getItem('aigm_travel_tip_idx') || '0', 10);
        cinTip = tips[idx % tips.length];
        localStorage.setItem('aigm_travel_tip_idx', String((idx + 1) % tips.length));
      }
    } catch (_) {}

    // Full-screen cinematic — waits for player tap or 15 s countdown
    await _showTravelCinematic({
      hexType: arrivedData.hex_type,
      destLabel,
      atmo: arrivedData.atmosphere,
      tip: cinTip,
    });

    // Build arrival chat bubble
    let prose;
    if (hours > 0) {
      const hStr = Number.isInteger(hours) ? `${hours}` : hours.toFixed(1);
      const hWord = hours === 1 ? 'godzinę' : (hours < 5 ? 'godziny' : 'godzin');
      if (destLabel) prose = `Dotarłeś do <strong>${escapeHtml(destLabel)}</strong>. Droga zajęła ${hStr} ${hWord}.`;
      else if (hexTypeName) prose = `Wkraczasz na teren — ${escapeHtml(hexTypeName)}. Droga zajęła ${hStr} ${hWord}.`;
      else prose = `Dotarłeś do celu. Droga zajęła ${hStr} ${hWord}.`;
    } else {
      prose = destLabel ? `Jesteś w ${escapeHtml(destLabel)}.` : 'Przybyłeś na miejsce.';
    }
    if (arrivedData.atmosphere) prose += ` <em>${escapeHtml(arrivedData.atmosphere)}</em>`;
    if (enc) prose += `<br><strong>Na drodze natykasz się na wroga!</strong>`;

    const travelBubble = document.createElement('div');
    travelBubble.className = 'chat-bubble chat-bubble--travel';
    travelBubble.innerHTML = prose;
    elements.chatMessages.appendChild(travelBubble);
    scrollToBottom();

    // Mark shown tip as seen in the knowledge tab (highlights it there)
    if (cinTip) _markTipSeen(cinTip.tip_key);
    // KW7 — first hex travel flag (used by GM tip system)
    if (!localStorage.getItem('aigm_first_hex_travel')) {
      localStorage.setItem('aigm_first_hex_travel', '1');
    }

    // GM arrival narration — brief location intro. Skipped if encounter combat fires instead.
    if (!enc?.enemy_key) {
      try {
        const triggerText = destLabel
          ? `Przybyłem do: ${destLabel}.`
          : `Przybyłem w nowe miejsce.`;
        const typingEl = showTypingIndicator();
        const narration = await apiRequest('POST', `/campaigns/${currentCampaignId}/turns`, {
          text: triggerText,
          character_id: characterData.id,
        });
        typingEl.remove();
        const gmText = narration.prose || narration.result?.message || narration.assistant_text || '';
        if (gmText) {
          const { narrative: gmContent } = parseGmFull(gmText);
          if (gmContent) appendMessage({ role: 'assistant', content: gmContent, created_at: new Date() });
        }
        if (narration.skill_test_pending) showSkillTestPopup(narration.skill_test_pending);
        scrollToBottom();
      } catch (err) {
        console.warn('Arrival narration failed:', err);
      }
    }

    // Encounter → trigger combat after a short delay
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
    _wmJournalHide();
    showToast(err.message || 'Błąd podróży', 'error');
  }
}

// ── Full-screen travel cinematic ──────────────────────────────────────────────

// Keys match hex_type_config.hex_type in the DB exactly
const _TERRAIN_THEMES = {
  plains:    { g: 'linear-gradient(160deg,#3A2200 0%,#6B4400 35%,#9A6A18 65%,#5A3800 100%)', icon: '🌾' },
  forest:    { g: 'linear-gradient(160deg,#050E05 0%,#0F250F 35%,#1E421E 65%,#102010 100%)', icon: '🌲' },
  hills:     { g: 'linear-gradient(160deg,#2A1E08 0%,#4A3A18 35%,#6A5A2A 65%,#4A3A18 100%)', icon: '⛰️' },
  mountains: { g: 'linear-gradient(160deg,#0A0E16 0%,#14202E 35%,#1E3044 65%,#0E1A28 100%)', icon: '🏔️' },
  swamp:     { g: 'linear-gradient(160deg,#060E06 0%,#0E2010 35%,#183A18 65%,#0A1A0C 100%)', icon: '🌿' },
  ruins:     { g: 'linear-gradient(160deg,#160806 0%,#2E1008 35%,#4A2214 65%,#2A1008 100%)', icon: '🏚️' },
  dungeon:   { g: 'linear-gradient(160deg,#050508 0%,#0C0C14 35%,#14141E 65%,#080812 100%)', icon: '⚔️' },
  road:      { g: 'linear-gradient(160deg,#180E04 0%,#2E1E08 35%,#4A3214 65%,#2A1C08 100%)', icon: '🛤️' },
  town:      { g: 'linear-gradient(160deg,#200A04 0%,#401808 35%,#6A3018 65%,#401808 100%)', icon: '🏘️' },
  castle:    { g: 'linear-gradient(160deg,#060610 0%,#10101C 35%,#1A1A2C 65%,#0C0C18 100%)', icon: '🏰' },
  cave:      { g: 'linear-gradient(160deg,#040404 0%,#0A0A0A 35%,#121210 65%,#060604 100%)', icon: '🕳️' },
  river:     { g: 'linear-gradient(160deg,#060E18 0%,#0E1E2C 35%,#1C3040 65%,#0A1C2E 100%)', icon: '🌊' },
};
const _TERRAIN_DEFAULT = { g: 'linear-gradient(160deg,#0A0810 0%,#16141E 50%,#201C2A 100%)', icon: '🗺️' };

let _travelCinematicTimer = null;

function _showTravelHintModal(label) {
  const modal = document.getElementById('travel-hint-modal');
  if (!modal) return;
  const titleEl = document.getElementById('travel-hint-modal-title');
  if (titleEl) titleEl.textContent = 'Podróżuj → ' + label;
  modal.removeAttribute('hidden');
  document.getElementById('travel-hint-go')?.addEventListener('click', () => {
    _hideTravelHintModal();
    _wmOpen();
  }, { once: true });
  document.getElementById('travel-hint-stay')?.addEventListener('click', () => {
    _hideTravelHintModal();
    renderSuggestedActions([]);
  }, { once: true });
}

function _hideTravelHintModal() {
  const modal = document.getElementById('travel-hint-modal');
  if (modal) modal.setAttribute('hidden', '');
}

function _showTravelCinematic({ hexType, destLabel, atmo, tip }) {
  return new Promise(resolve => {
    const overlay = document.getElementById('travel-cinematic');
    if (!overlay) { resolve(); return; }

    const theme = _TERRAIN_THEMES[hexType] || _TERRAIN_DEFAULT;
    document.getElementById('travel-cin-bg').style.background = theme.g;
    document.getElementById('travel-cin-icon').textContent = theme.icon;
    document.getElementById('travel-cin-title').textContent = destLabel || 'Nieznane miejsce';

    const atmoEl = document.getElementById('travel-cin-atmo');
    atmoEl.textContent = atmo || '';
    atmoEl.style.display = atmo ? '' : 'none';

    const tipEl = document.getElementById('travel-cin-tip');
    if (tip) {
      document.getElementById('travel-cin-tip-title').textContent = tip.title || '';
      document.getElementById('travel-cin-tip-body').textContent = tip.body || '';
      tipEl.removeAttribute('hidden');
    } else {
      tipEl.setAttribute('hidden', '');
    }

    overlay.removeAttribute('hidden');
    // Double rAF ensures transition fires after display is restored
    requestAnimationFrame(() => requestAnimationFrame(() => overlay.classList.add('travel-cin--visible')));

    // Progress bar
    const bar = document.getElementById('travel-cin-bar');
    bar.style.transition = 'none';
    bar.style.width = '0%';
    requestAnimationFrame(() => requestAnimationFrame(() => {
      bar.style.transition = 'width 15s linear';
      bar.style.width = '100%';
    }));

    const done = () => {
      clearTimeout(_travelCinematicTimer);
      overlay.removeEventListener('click', done);
      overlay.classList.remove('travel-cin--visible');
      setTimeout(() => { overlay.setAttribute('hidden', ''); resolve(); }, 500);
    };

    _travelCinematicTimer = setTimeout(done, 15000);
    // 400ms grace period prevents lingering touch events from the map interaction from
    // immediately dismissing the overlay before the player has a chance to read it.
    setTimeout(() => overlay.addEventListener('click', done, { once: true }), 400);
  });
}

async function _wmOpen() {
  _hideTravelHintModal();
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
    _wmap.level = 0;
    _wmap.parentHex = null;
    const backBtn = document.getElementById('wmap-back-btn');
    if (backBtn) backBtn.setAttribute('hidden', '');

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
  _wmJournalHide();   // slide journal down first, then panel slides right
  _wmap.panel.style.transform = 'translateX(100%)';
  setTimeout(() => _wmap.panel.setAttribute('hidden', ''), 280);
  _wmap.confirm.setAttribute('hidden', '');
  _wmap.pendingTravel = null;
}

async function _wmZoomIn(q, r, label) {
  if (!currentCampaignId) return;
  try {
    const data = await apiRequest('GET', `/campaigns/${currentCampaignId}/world-map?character_id=${characterData?.id||0}&parent_q=${q}&parent_r=${r}`);
    if (!data.hexes || !data.hexes.length) {
      showToast('Brak mapy lokalnej dla tego miejsca.', 'info'); return;
    }
    _wmap.hexes = data.hexes;
    _wmap.teleports = [];
    _wmap.currentHex = null;
    _wmap.hexTypes = data.hex_types || {};
    _wmap.level = 1;
    _wmap.parentHex = { q, r, label: data.parent_label || label };
    _wmap.zoom = 1.4;
    _wmap.pan = { x: 0, y: 0 };
    _wmap.confirm.setAttribute('hidden', '');
    _wmap.pendingTravel = null;
    // Center on local hexes
    const pixels = _wmap.hexes.map(h => _wmHexToPixel(h.q, h.r));
    if (pixels.length) {
      const cx = pixels.reduce((s,p)=>s+p.x,0)/pixels.length;
      const cy = pixels.reduce((s,p)=>s+p.y,0)/pixels.length;
      const rect = _wmap.svg.getBoundingClientRect();
      _wmap.pan = { x: (rect.width||360)/2 - cx*_wmap.zoom, y: (rect.height||500)/2 - cy*_wmap.zoom };
    }
    _wmRender();
    // Show back button
    const backBtn = document.getElementById('wmap-back-btn');
    if (backBtn) { backBtn.textContent = `← ${_wmap.parentHex.label}`; backBtn.removeAttribute('hidden'); }
  } catch (err) {
    showToast(err.message || 'Błąd ładowania mapy lokalnej', 'error');
  }
}

async function _wmBack() {
  _wmap.level = 0;
  _wmap.parentHex = null;
  const backBtn = document.getElementById('wmap-back-btn');
  if (backBtn) backBtn.setAttribute('hidden', '');
  await _wmOpen();
}

function initWorldMap() {
  _wmap.panel   = document.getElementById('world-map-panel');
  _wmap.svg     = document.getElementById('wmap-svg');
  _wmap.confirm = document.getElementById('wmap-confirm');
  _wmap.journal = document.getElementById('wmap-travel-journal');
  if (!_wmap.panel) return;

  document.getElementById('open-map-btn')?.addEventListener('click', _wmOpen);
  // composer-map-btn removed from HTML
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
  document.getElementById('wmap-back-btn')?.addEventListener('click', _wmBack);

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

// ── Bug Report System ─────────────────────────────────────────
const _capturedJsErrors = [];
(function _installErrorCapture() {
    const _orig = window.onerror;
    window.onerror = function(message, filename, lineno, colno, error) {
        _capturedJsErrors.push({ message: String(message), filename, lineno, colno, ts: Date.now() });
        if (_capturedJsErrors.length > 30) _capturedJsErrors.shift();
        if (_orig) return _orig.apply(this, arguments);
    };
})();

function _makeDraggable(el) {
    let startX, startY, startLeft, startTop, dragging = false;
    const STORAGE_KEY = 'aigm_bugreport_pos';

    function applyStoredPos() {
        try {
            const p = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
            if (p) { el.style.left = p.left; el.style.top = p.top; el.style.right = 'auto'; el.style.bottom = 'auto'; }
        } catch {}
    }
    applyStoredPos();

    function onStart(cx, cy) {
        dragging = true;
        startX = cx; startY = cy;
        const rect = el.getBoundingClientRect();
        startLeft = rect.left; startTop = rect.top;
        el.style.left = startLeft + 'px'; el.style.top = startTop + 'px';
        el.style.right = 'auto'; el.style.bottom = 'auto';
    }
    function onMove(cx, cy) {
        if (!dragging) return;
        el.style.left = Math.max(0, Math.min(window.innerWidth - 50, startLeft + cx - startX)) + 'px';
        el.style.top = Math.max(0, Math.min(window.innerHeight - 50, startTop + cy - startY)) + 'px';
    }
    function onEnd(wasTap) {
        if (!dragging) return;
        dragging = false;
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ left: el.style.left, top: el.style.top })); } catch {}
        if (wasTap) openBugReportModal();
    }

    el.addEventListener('mousedown', e => { e.preventDefault(); const moved = { v: false }; onStart(e.clientX, e.clientY);
        const mm = e2 => { if (Math.abs(e2.clientX - startX) > 4 || Math.abs(e2.clientY - startY) > 4) moved.v = true; onMove(e2.clientX, e2.clientY); };
        const mu = () => { document.removeEventListener('mousemove', mm); document.removeEventListener('mouseup', mu); onEnd(!moved.v); };
        document.addEventListener('mousemove', mm); document.addEventListener('mouseup', mu); });

    el.addEventListener('touchstart', e => { const t = e.touches[0]; const moved = { v: false }; onStart(t.clientX, t.clientY);
        const tm = e2 => { const t2 = e2.touches[0]; if (Math.abs(t2.clientX - startX) > 4 || Math.abs(t2.clientY - startY) > 4) moved.v = true; onMove(t2.clientX, t2.clientY); };
        const te = () => { el.removeEventListener('touchmove', tm); el.removeEventListener('touchend', te); onEnd(!moved.v); };
        el.addEventListener('touchmove', tm, { passive: true }); el.addEventListener('touchend', te); }, { passive: true });
}

function _refreshBugReportButton() {
    const isTester = currentUser?.is_tester === true || currentUser?.is_tester === 1;
    let btn = document.getElementById('bug-report-btn');
    if (!btn) {
        btn = document.createElement('button');
        btn.id = 'bug-report-btn';
        btn.title = 'Zgłoś błąd (przeciągnij, żeby przenieść)';
        btn.innerHTML = '🐞';
        _makeDraggable(btn);
        document.body.appendChild(btn);

        const overlay = document.createElement('div');
        overlay.id = 'bug-report-overlay';
        overlay.hidden = true;
        overlay.innerHTML = `
          <div class="bug-modal" role="dialog" aria-modal="true" aria-label="Zgłoszenie błędu">
            <div class="bug-modal__header">
              <span class="bug-modal__title" id="bug-modal-title">Zgłoś błąd</span>
              <button class="bug-modal__close" onclick="closeBugReportModal()" aria-label="Zamknij">✕</button>
            </div>
            <div style="display:flex;gap:8px;margin-bottom:14px">
              <button id="bug-type-bug" onclick="_setBugType('bug')" style="flex:1;padding:7px 0;border-radius:6px;border:2px solid #e55;background:rgba(220,50,50,0.18);color:#ff8080;font-size:0.82rem;cursor:pointer;font-weight:600">🐛 Błąd</button>
              <button id="bug-type-feature" onclick="_setBugType('feature')" style="flex:1;padding:7px 0;border-radius:6px;border:2px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.45);font-size:0.82rem;cursor:pointer">💡 Sugestia</button>
            </div>
            <div>
              <label for="bug-observation" id="bug-obs-label">Co zaobserwowałeś?</label>
              <textarea id="bug-observation" rows="4" placeholder="Opisz co się stało..."></textarea>
            </div>
            <div id="bug-repro-row">
              <label for="bug-reproduction">Jak to odtworzyć?</label>
              <textarea id="bug-reproduction" rows="3" placeholder="Kroki które doprowadziły do błędu..."></textarea>
            </div>
            <div class="bug-modal__actions">
              <button class="bug-modal__cancel" onclick="closeBugReportModal()">Anuluj</button>
              <button class="bug-modal__submit" id="bug-submit-btn" onclick="submitBugReport()">Wyślij zgłoszenie</button>
            </div>
            <div class="bug-modal__note">Szczegóły techniczne (stan gry, ostatnie ruchy) są dołączane automatycznie.</div>
          </div>`;
        overlay.addEventListener('click', e => { if (e.target === overlay) closeBugReportModal(); });
        document.body.appendChild(overlay);
    }
    btn.hidden = !isTester;
}

let _bugReportType = 'bug';

function _setBugType(type) {
    _bugReportType = type;
    const isBug = type === 'bug';
    const btnBug = document.getElementById('bug-type-bug');
    const btnFeat = document.getElementById('bug-type-feature');
    const title = document.getElementById('bug-modal-title');
    const obsLabel = document.getElementById('bug-obs-label');
    const reproRow = document.getElementById('bug-repro-row');
    const obs = document.getElementById('bug-observation');

    if (isBug) {
        btnBug.style.borderColor = '#e55';
        btnBug.style.background = 'rgba(220,50,50,0.18)';
        btnBug.style.color = '#ff8080';
        btnFeat.style.borderColor = 'rgba(255,255,255,0.15)';
        btnFeat.style.background = 'rgba(255,255,255,0.06)';
        btnFeat.style.color = 'rgba(255,255,255,0.45)';
        title.textContent = 'Zgłoś błąd';
        obsLabel.textContent = 'Co zaobserwowałeś?';
        obs.placeholder = 'Opisz co się stało...';
        reproRow.style.display = '';
    } else {
        btnFeat.style.borderColor = '#7c5';
        btnFeat.style.background = 'rgba(80,200,80,0.15)';
        btnFeat.style.color = '#9f9';
        btnBug.style.borderColor = 'rgba(255,255,255,0.15)';
        btnBug.style.background = 'rgba(255,255,255,0.06)';
        btnBug.style.color = 'rgba(255,255,255,0.45)';
        title.textContent = 'Zgłoś sugestię';
        obsLabel.textContent = 'Co chciałbyś zmienić lub dodać?';
        obs.placeholder = 'Opisz pomysł lub sugestię...';
        reproRow.style.display = 'none';
    }
}

function openBugReportModal() {
    document.getElementById('bug-report-overlay').hidden = false;
    document.getElementById('bug-observation').value = '';
    document.getElementById('bug-reproduction').value = '';
    document.getElementById('bug-submit-btn').disabled = false;
    document.getElementById('bug-submit-btn').textContent = 'Wyślij zgłoszenie';
    _setBugType('bug');
    document.getElementById('bug-observation').focus();
}

function closeBugReportModal() {
    document.getElementById('bug-report-overlay').hidden = true;
}

async function submitBugReport() {
    const observation = (document.getElementById('bug-observation').value || '').trim();
    const reproduction = (document.getElementById('bug-reproduction').value || '').trim();

    if (!observation) {
        document.getElementById('bug-observation').focus();
        return;
    }

    const btn = document.getElementById('bug-submit-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Wysyłanie...';

    try {
        const payload = {
            observation,
            reproduction,
            report_type: _bugReportType,
            campaign_id: currentCampaignId || null,
            js_errors: _capturedJsErrors.slice(-10),
        };

        const resp = await apiRequest('POST', '/bug-report', payload);

        if (resp.ok) {
            closeBugReportModal();
            showToast('Zgłoszenie wysłane! Dziękujemy.', 'success');
        } else {
            throw new Error('Nieoczekiwana odpowiedź serwera');
        }
    } catch (e) {
        btn.disabled = false;
        btn.textContent = 'Wyślij zgłoszenie';
        showToast('Błąd wysyłania zgłoszenia: ' + (e.message || 'nieznany błąd'), 'error');
    }
}

// ============================================================================
// Web Push Notifications
// ============================================================================
async function registerPushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        console.warn('[Push] Not supported in this browser');
        return;
    }

    let vapidPublicKey;
    try {
        const resp = await fetch('/api/push/vapid-public-key');
        if (!resp.ok) { console.warn('[Push] VAPID key fetch failed:', resp.status); return; }
        const data = await resp.json();
        vapidPublicKey = data.publicKey;
    } catch (e) {
        console.warn('[Push] VAPID key fetch error:', e);
        return;
    }
    if (!vapidPublicKey) { console.warn('[Push] No VAPID key returned'); return; }

    let reg;
    try {
        reg = await navigator.serviceWorker.register('/sw.js');
        await navigator.serviceWorker.ready;
        console.log('[Push] SW registered, scope:', reg.scope);
    } catch (e) {
        console.warn('[Push] SW registration failed:', e);
        return;
    }

    let existingSub;
    try {
        existingSub = await reg.pushManager.getSubscription();
    } catch (e) {
        console.warn('[Push] getSubscription error:', e);
        return;
    }
    if (existingSub) {
        console.log('[Push] Already subscribed, re-sending to backend');
        await _sendSubscriptionToBackend(existingSub);
        return;
    }

    const permission = await Notification.requestPermission();
    console.log('[Push] Permission:', permission);
    if (permission !== 'granted') return;

    try {
        const sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: _urlBase64ToUint8Array(vapidPublicKey),
        });
        console.log('[Push] Subscribed, sending to backend');
        await _sendSubscriptionToBackend(sub);
    } catch (e) {
        console.warn('[Push] Subscribe failed:', e);
    }
}

async function _sendSubscriptionToBackend(sub) {
    const token = localStorage.getItem('aigm_access_token') || localStorage.getItem('token');
    if (!token) return;
    try {
        await fetch('/api/users/push-subscription', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify(sub.toJSON()),
        });
    } catch (e) {
        console.warn('[Push] Failed to register subscription:', e);
    }
}

async function applyGameModeFlags() {
    try {
        const res = await fetch('/api/game-modes');
        if (!res.ok) return;
        const { flags = {} } = await res.json();

        const hide = (id) => { const el = document.getElementById(id); if (el) el.style.display = 'none'; };
        const show = (id) => { const el = document.getElementById(id); if (el) el.style.display = ''; };

        // Solo campaign buttons
        flags.ai_campaign_enabled === false ? hide('new-campaign-btn') : show('new-campaign-btn');
        flags.prebuilt_enabled    === false ? hide('prebuilt-btn')     : show('prebuilt-btn');
        flags.dungeon_enabled     === false ? hide('dungeon-picker-btn') : show('dungeon-picker-btn');

        // Multiplayer lobby mode tiles
        const aiTile  = document.getElementById('lobby-mode-ai');
        const preTile = document.getElementById('lobby-mode-prebuilt');
        if (aiTile)  aiTile.style.display  = flags.ai_campaign_enabled  === false ? 'none' : '';
        if (preTile) preTile.style.display = flags.prebuilt_enabled      === false ? 'none' : '';
    } catch (e) {
        console.warn('[GameModes] fetch failed, defaults apply', e.message);
    }
}

function _urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = atob(base64);
    return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
}
