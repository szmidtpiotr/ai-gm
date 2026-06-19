/**
 * AI GM RPG - Mobile-First Frontend Application
 * Task T28.5 - Alternative frontend based on Figma designs v18-20
 */

const API_BASE = '/api';

// C6/U15 — wound tiers loaded from backend at startup (single source of truth);
// fallback mirrors wound_utils.WOUND_TIERS. `tiers` carries label+color+penalty.
const _WOUND_TIERS_FALLBACK = [
    { min_pct: 75, tier: 'healthy',    label: null,                 color: '#4caf50', penalty: 0 },
    { min_pct: 50, tier: 'minor',      label: 'Ranny',              color: '#ffc107', penalty: -1 },
    { min_pct: 25, tier: 'moderate',   label: 'Ciężko Ranny',       color: '#ff9800', penalty: -2 },
    { min_pct: 10, tier: 'serious',    label: 'Poważnie Ranny',     color: '#f44336', penalty: -4 },
    { min_pct: -1, tier: 'near_death', label: 'Na Skraju Śmierci',  color: '#7f0000', penalty: -4 },
];
let _woundThresholds = { healthy_pct: 75, moderate_pct: 50, critical_pct: 25, tiers: _WOUND_TIERS_FALLBACK };
(async () => {
    try {
        const r = await fetch('/api/config/wound-thresholds');
        if (r.ok) {
            const data = await r.json();
            if (!Array.isArray(data.tiers)) data.tiers = _WOUND_TIERS_FALLBACK;
            _woundThresholds = data;
        }
    } catch (_) {}
})();

const SLASH_COMMANDS = [
    { cmd: '/help',    desc: 'Pokaż listę dostępnych komend' },
    { cmd: '/sheet',   desc: 'Otwórz kartę postaci' },
    { cmd: '/mem',     desc: 'Pytanie o przeszłość z podsumowań (bez wpływu na narrację)' },
    { cmd: '/helpme',  desc: 'Doradca OOC — wskazówki poza fabułą' },
    { cmd: '/admin',   desc: 'Komendy admina: add | set | remove | clear | combat | quest | show', adminOnly: true },
    { cmd: '/debug',   desc: 'Debug: dump-state | set-hp N | set-state STATE | reset-cooldowns | roll SKILL', adminOnly: true },
    { cmd: '/roll',    desc: 'Admin: wymuś test umiejętności z animacją kostek (np. /roll skradanie)', adminOnly: true },
    { cmd: '/history', desc: 'Ostatnie 10 tur sesji' },
    { cmd: '/search',  desc: 'Przeszukaj lokację lub postać' },
    { cmd: '/atak',    desc: 'Synchronizuj panel walki lub zacznij walkę' },
    { cmd: '/czar',    desc: 'Rzuć zaklęcie poza walką (np. /czar mend_wounds)' },
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
    btnOpenCodex: document.getElementById('open-codex-btn'),
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
    combatYou: document.getElementById('combat-you'),
    btnCombatMove: document.getElementById('combat-move-btn'),
    combatMoveLabel: document.getElementById('combat-move-label'),
    btnCombatDodge: document.getElementById('combat-dodge-btn'),
    combatDodgeLabel: document.getElementById('combat-dodge-label'),
    btnCombatBlock: document.getElementById('combat-block-btn'),
    combatBlockLabel: document.getElementById('combat-block-label'),
    btnCombatWrestle: document.getElementById('combat-wrestle-btn'),
    combatWrestleLabel: document.getElementById('combat-wrestle-label'),
    combatMsg: document.getElementById('combat-msg'),
    combatComposer: document.getElementById('combat-composer'),
    btnCombatAttack: document.getElementById('combat-attack-btn'),
    btnCombatFlee: document.getElementById('combat-flee-btn'),
    // SF1 (#619): pasek 3-filarowy + bottom sheet z pozostałymi akcjami
    btnCombatAction: document.getElementById('combat-action-btn'),
    combatActionSheet: document.getElementById('combat-action-sheet'),
    combatActionSheetBackdrop: document.getElementById('combat-action-sheet-backdrop'),
    combatActionSheetList: document.getElementById('combat-action-sheet-list'),

    // Journal Panel
    journalPanel: document.getElementById('journal-panel'),
    btnOpenJournal: document.getElementById('open-journal-btn'),
    journalBody: document.getElementById('journal-body'),
    journalEmpty: document.getElementById('journal-empty'),
    journalLoading: document.getElementById('journal-loading'),
    journalBanner: document.getElementById('journal-banner'),
    journalSections: document.getElementById('journal-sections'),
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
    dropCelebrationOverlay: document.getElementById('drop-celebration-overlay'),
    dropCelebrationList: document.getElementById('drop-celebration-list'),
    dropCelebrationCloseBtn: document.getElementById('drop-celebration-close-btn'),

    // Header HP bar
    headerHpBarFill: document.getElementById('header-hp-bar-fill'),
    headerManaBar: document.getElementById('header-mana-bar'),
    headerManaBarFill: document.getElementById('header-mana-bar-fill'),

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
// Stage 10 A2 — auto-refresh state. _refreshInFlight prevents a stampede when
// multiple parallel requests get 401 simultaneously; they all await the same promise.
let _refreshInFlight = null;
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
        'Content-Type': 'application/json'
    };
    // Stage 10 A2 — attach JWT when we have one. Backend continues accepting
    // ?user_id= query param during 10-B; this header is additive.
    const accessToken = localStorage.getItem('aigm_access_token');
    if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
    }

    const options = { method, headers };
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
        // C15: unrecovered 401 → session expired, logout gracefully
        if (response.status === 401 && typeof handleSessionExpired === 'function') {
            handleSessionExpired();
            throw new Error('Sesja wygasła');
        }
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
                is_tester: response.is_tester || 0,
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
            if (response.game_mode_flags) {
                try {
                    const flags = typeof response.game_mode_flags === 'string'
                        ? JSON.parse(response.game_mode_flags) : response.game_mode_flags;
                    if (flags?.visual_theme) _applyTheme(flags.visual_theme);
                } catch (_) {}
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
        } else {
            showToast(error.message || 'Błąd logowania', 'error');
        }
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
    // Stage 10 A2 — clear JWT pair on logout.
    localStorage.removeItem('aigm_access_token');
    localStorage.removeItem('aigm_refresh_token');
    localStorage.removeItem('aigm_hero_id');
    localStorage.removeItem('aigm_campaign_id');
    try { sessionStorage.removeItem('aigm_hero_id'); sessionStorage.removeItem('aigm_active_session'); } catch {}
    // D10 E2 — reset theme on logout so next user gets theirs
    _selectedTheme = 'dark_fantasy';
    document.body.dataset.theme = '';
    showScreen('login');
}

function handleSessionExpired() {
    showToast('Sesja wygasła — zaloguj się ponownie.', 'error', 5000);
    // Clear auth credentials but KEEP aigm_hero_id / aigm_campaign_id so
    // tryRestoreSession() can resume the game after re-login.
    authToken = null;
    currentUser = null;
    currentHero = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('aigm_access_token');
    localStorage.removeItem('aigm_refresh_token');
    _selectedTheme = 'dark_fantasy';
    document.body.dataset.theme = '';
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
    const confirm  = document.getElementById('register-password-confirm')?.value ?? '';
    const errEl    = document.getElementById('register-error');
    errEl.hidden   = true;

    if (!email || !username || !password || !confirm) {
        errEl.textContent = 'Wypełnij wszystkie pola';
        errEl.hidden = false;
        return;
    }
    if (password !== confirm) {
        errEl.textContent = 'Hasła nie są zgodne';
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
                is_tester: resp.is_tester || 0,
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
                is_tester: resp.is_tester || 0,
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
    try {
        // Stage 6 H1: use the enriched /heroes endpoint.
        const response = await apiRequest('GET', `/heroes?user_id=${currentUser.id}`);
        const heroes = response.heroes || [];
        renderHeroes(heroes);
    } catch (error) {
        console.error('[Heroes] Failed to load:', error);
        showToast('Nie udało się załadować bohaterów', 'error');
    }
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

// Stage 6 H4: Hero history modal — past campaigns with outcome / XP / turns / date.
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
              <h3 id="hero-history-modal-title">Historia</h3>
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
    const title = document.getElementById('hero-history-modal-title');
    const body  = document.getElementById('hero-history-modal-body');
    if (title) title.textContent = `📜 ${hero.name} — historia`;
    if (body) body.innerHTML = `<p class="hero-history-modal__loading">Wczytywanie…</p>`;
    modal.classList.add('hero-history-modal--open');

    try {
        const r = await apiRequest('GET', `/characters/${hero.id}/history`);
        const rows = r.history || [];
        if (!body) return;
        if (!rows.length) {
            const isFirstActive = (hero.hero_status || hero.status) === 'in_campaign';
            body.innerHTML = `<p class="hero-history-modal__empty">${isFirstActive
                ? 'Aktualna przygoda jest pierwszą — historia zapełni się po jej zakończeniu.'
                : 'Ten bohater jeszcze nie skończył żadnej przygody.'}</p>`;
            return;
        }
        const outcomeIcon = { victory: '🏆', death: '💀', abandoned: '🚪' };
        const outcomeLabel = { victory: 'Zwycięstwo', death: 'Śmierć', abandoned: 'Porzucono' };
        body.innerHTML = `<ul class="hero-history-list">` + rows.map(h => {
            const icon  = outcomeIcon[h.outcome] || '•';
            const lbl   = outcomeLabel[h.outcome] || h.outcome || '—';
            const title = h.campaign_title || `Kampania #${h.campaign_id}`;
            const when  = _relativeTimePL(h.completed_at || h.created_at) || '—';
            return `
              <li class="hero-history-row hero-history-row--${_esc(h.outcome)}">
                <span class="hero-history-row__icon">${icon}</span>
                <div class="hero-history-row__main">
                  <div class="hero-history-row__title">${_esc(title)}</div>
                  <div class="hero-history-row__meta">${_esc(lbl)} · ${h.xp_earned ?? 0} PD · ${h.turns_count ?? 0} tur · ${_esc(when)}</div>
                  ${h.chapter_summary ? `<div class="hero-history-row__summary">${_esc(h.chapter_summary)}</div>` : ''}
                </div>
              </li>`;
        }).join('') + `</ul>`;
    } catch (err) {
        if (body) body.innerHTML = `<p class="hero-history-modal__empty">Nie udało się wczytać historii: ${_esc(err.message || err)}</p>`;
    }
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
    // E2 (#417) — load tooltip content (descriptions + mechanical examples) and
    // re-render once it arrives so the creator tooltips show roll examples.
    _loadCreatorHelp().then(() => { if (elements.characterWizard?.classList.contains('screen--active')) _wizardRender(); });
}

// E2 (#417) — Creator help cache: archetype/stat/skill examples for tooltips.
let _creatorHelp = null;
async function _loadCreatorHelp() {
    if (_creatorHelp) return _creatorHelp;
    try {
        const r = await fetch('/api/mechanics/creator-help');
        if (r.ok) {
            _creatorHelp = await r.json();
            _mergeSkillCatalog();
        }
    } catch (_e) { /* fall back to local hints */ }
    return _creatorHelp;
}
// FAZA S (#617) — the wizard's hardcoded ALL_SKILL_ROWS only listed the 16 legacy
// creation skills, so the new skill engine (gamble/haggling/lockpick/…) could never
// be picked at creation. Merge the full game_config_skills catalog (already returned
// by /creator-help) into the swap pool so new skills become selectable.
function _mergeSkillCatalog() {
    const cat = _creatorHelp?.skills;
    if (!Array.isArray(cat)) return;
    const have = new Set(ALL_SKILL_ROWS.map(r => r.key));
    for (const s of cat) {
        if (!s?.key || have.has(s.key)) continue;
        ALL_SKILL_ROWS.push({ key: s.key, label: s.label || s.key, stat: s.stat || '?', hint: s.description || '' });
        have.add(s.key);
    }
    ALL_SKILL_ROWS.sort((a, b) => a.key.localeCompare(b.key));
}
function _statExample(key) {
    return (_creatorHelp?.stats || []).find(s => s.key === key)?.example || '';
}
function _skillExample(key) {
    return (_creatorHelp?.skills || []).find(s => s.key === key)?.example || '';
}
function _archetypeExample(key) {
    return (_creatorHelp?.archetypes || []).find(a => a.key === key)?.example || '';
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
    else if (wizardStepNum === 1) _renderStep2(content, true);
    else if (wizardStepNum === 2) _renderStep3(content, true);
    else _renderStep4(content);
}

function _wizardRollAnimate(container, type) {
    const DICE = ['⚀','⚁','⚂','⚃','⚄','⚅'];
    if (type === 'stat') {
        container.querySelectorAll('.wizard-stat-row').forEach((row, i) => {
            row.classList.add('wiz-entering');
            row.style.setProperty('--wiz-i', i);
            const valEl = row.querySelector('.wizard-stat-val');
            if (!valEl) return;
            const finalVal = valEl.textContent.trim();
            const finalNum = parseInt(finalVal);
            if (isNaN(finalNum)) return;
            const rollStart = i * 52 + 90;
            const rollDuration = 320 + i * 35;
            valEl.classList.add('wiz-val-rolling');
            let t;
            setTimeout(() => {
                t = setInterval(() => {
                    valEl.textContent = WIZARD_STAT_MIN + Math.floor(Math.random() * (WIZARD_STAT_MAX - WIZARD_STAT_MIN + 1));
                }, 55);
                setTimeout(() => {
                    clearInterval(t);
                    valEl.textContent = finalVal;
                    valEl.classList.remove('wiz-val-rolling');
                    valEl.classList.add('wiz-val-landed');
                    setTimeout(() => valEl.classList.remove('wiz-val-landed'), 420);
                }, rollDuration);
            }, rollStart);
        });
    } else {
        container.querySelectorAll('.wizard-skill-row:not(.wizard-skill-row--swapping)').forEach((row, i) => {
            row.classList.add('wiz-entering');
            row.style.setProperty('--wiz-i', i);
            const rankEl = row.querySelector('.wizard-skill-rank');
            if (!rankEl) return;
            const finalRank = rankEl.textContent.trim();
            const flashStart = i * 52 + 80;
            const flashDuration = 220 + i * 25;
            rankEl.classList.add('wiz-rank-rolling');
            let t;
            setTimeout(() => {
                t = setInterval(() => { rankEl.textContent = DICE[Math.floor(Math.random() * 6)]; }, 50);
                setTimeout(() => {
                    clearInterval(t);
                    rankEl.textContent = finalRank;
                    rankEl.classList.remove('wiz-rank-rolling');
                    rankEl.classList.add('wiz-rank-landed');
                    setTimeout(() => rankEl.classList.remove('wiz-rank-landed'), 360);
                }, flashDuration);
            }, flashStart);
        });
    }
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
                        <span class="archetype-bonus">+2 STR · +1 KON · HP: 10</span>
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
let _step2FirstRender = false;
function _wizardCalcHP(archetype, con, level = 1) {
    const base = archetype === 'warrior' ? 10 : archetype === 'rogue' ? 8 : archetype === 'scholar' ? 6 : 8;
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

function _renderStep2(c, animate = false) {
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
        const ex = _statExample(stat);
        const hint = (STAT_HINTS[stat] || stat) + (ex ? ` — ${ex}` : '');
        rows += `
            <div class="wizard-stat-row" data-stat="${stat}">
                <div class="wizard-stat-label-wrap">
                    <span class="wizard-stat-label">${stat}</span>
                </div>
                <span class="wizard-stat-mod">${modStr}</span>
                <div class="wizard-stat-controls">
                    <button type="button" class="wizard-stat-btn" data-dir="-" ${canMinus ? '' : 'disabled'}>−</button>
                    <span class="wizard-stat-val">${v}</span>
                    <button type="button" class="wizard-stat-btn" data-dir="+" ${canPlus ? '' : 'disabled'}>+</button>
                </div>
                ${hint.trim() ? `<div class="wizard-stat-desc">${_esc(hint)}</div>` : ''}
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

    if (animate) _wizardRollAnimate(c, 'stat');

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
function _renderStep3(c, animate = false) {
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

        const skillEx = _skillExample(currentKey);
        const skillHint = (curRow.hint || '') + (skillEx ? ` — ${skillEx}` : '');
        return `
            <div class="wizard-skill-row${changed ? ' wizard-skill-row--changed' : ''}" data-orig="${origKey}">
                <span class="wizard-skill-name">
                    ${_esc(curRow.label)} <span class="wizard-skill-stat">— ${curRow.stat}</span>
                    ${swapBtn}
                </span>
                <div class="wizard-stat-controls wizard-skill-controls">
                    <button type="button" class="wizard-stat-btn" data-skill-dir="-" data-orig="${origKey}" ${canMinus ? '' : 'disabled'}>−</button>
                    <span class="wizard-skill-rank">${rank} · ${rankName}</span>
                    <button type="button" class="wizard-stat-btn" data-skill-dir="+" data-orig="${origKey}" ${canPlus ? '' : 'disabled'}>+</button>
                </div>
                ${skillHint.trim() ? `<div class="wizard-stat-desc">${_esc(skillHint)}</div>` : ''}
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

    if (animate) _wizardRollAnimate(c, 'skill');

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

async function enterGame(campaign, opts = {}) {
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
    // Visual overlay settings loaded in parallel; clock render also applies overlay
    Promise.all([loadVisualSettings(), Promise.resolve()]).then(() => {
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
                const fallback = opts.dungeonFallbackNarrative || 'Witaj, bohaterze. Twoja przygoda się zaczyna…';
                appendMessage({ role: 'assistant', content: fallback, created_at: new Date() });
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

    const resp = await fetch(`/api/campaigns/${currentCampaignId}/turns/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ text, character_id: characterData.id, input_type: inputType }),
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
            if (meta.current_location)         result.current_location         = meta.current_location;
            if (meta.suggested_actions)        result.suggested_actions        = meta.suggested_actions;
            if (meta.active_quests)            result.active_quests            = meta.active_quests;
            if (meta.travel_escalation_level != null) result.travel_escalation_level = meta.travel_escalation_level;
            if (meta.clock)              renderClock(meta.clock);
            if (meta.onboarding_cards)   result.onboarding_cards   = meta.onboarding_cards;
            if (meta.narrative_append)   result.narrative_append   = meta.narrative_append;
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
// #700: rozróżnij "realny POST walki w locie" od "zalegającej flagi". Reconciler ufa backendowi,
// gdy ŻADEN z tych fetchy nie trwa — wtedy zdejmuje zaciśnięty overlay/akcję (watchdog re-sync).
let enemyTurnFetchActive = false;     // true tylko między POST enemy-turn a jego odpowiedzią
let playerActionFetchActive = false;  // true tylko między POST akcji gracza a jego odpowiedzią
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
        if (goldAmt > 0) html += `<p>💰 +${goldAmt} GP (already added)</p>`;
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
    pendingLoot = null;
    pendingGold = 0;
    elements.combatBanner.hidden = true;
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

    const combatantRow = (c, isPlayer, isActive = false) => {
        const activeCls = isActive ? ' combat-combatant--active' : '';
        const activeArrow = isActive ? '<span class="combat-combatant__active-arrow" aria-hidden="true">▶</span>' : '';
        const hpCur = Math.max(0, Number(c.hp_current ?? 0));
        const hpMax = Math.max(1, Number(c.hp_max ?? hpCur ?? 1));
        const pct = Math.max(0, Math.min(100, Math.round((hpCur / hpMax) * 100)));
        const dead = hpCur <= 0;
        const def = c.defense != null ? ` · DEF ${c.defense}` : '';
        const ini = c.initiative_roll != null ? `INI ${c.initiative_roll}` : '';
        if (isPlayer) {
            const _absorb = Math.max(0, Number(c.absorb_hp ?? 0));  // B10 (#657): pula absorpcji tarczy
            const hpPct = pct > _woundThresholds.healthy_pct ? 'high' : (pct > _woundThresholds.critical_pct ? 'mid' : 'low');
            const woundHTML = renderWoundLabelHTML(hpCur, hpMax);
            const wpn = _equippedDurability.weapon;
            let duraWarn = '';
            if (wpn && wpn.broken) {
                duraWarn = `<div class="combat-dura-warn combat-dura-warn--broken">⚔ Twój oręż pęknięty — ciosy słabsze (−${wpn.penalty_pct}%)</div>`;
            } else if (wpn && Number(wpn.pct) <= 20) {
                duraWarn = `<div class="combat-dura-warn">⚔ Twój oręż ledwo trzyma się rękojeści (${wpn.pct}%)</div>`;
            }
            // #667: stan strefy gracza — wiąże z przyciskiem Zbliż się / Cofnij się.
            const _pz = String(c.zone || 'engaged');
            const _pzHint = _pz === 'ranged' ? '🏹 jesteś na dystansie' : '🗡 jesteś w zwarciu';
            return `
                <div class="combat-combatant combat-combatant--player${activeCls}">
                    ${activeArrow}
                    <div class="combat-combatant__icon">🛡️</div>
                    <div class="combat-combatant__body">
                        <div class="combat-combatant__name">
                            <span class="combat-you__tag">TY</span>
                            <span class="combat-combatant__name-text">${escapeHtml(c.name || 'Bohater')}</span>
                            <span class="combat-combatant__meta">${ini}</span>
                        </div>
                        <div class="combat-you__zone">${_pzHint}</div>
                        <div class="combat-combatant__hp-row">
                            <span>HP</span>
                            <span>${hpCur} / ${hpMax}${def}${_absorb > 0 ? ` · 🛡 ${_absorb}` : ''}</span>
                        </div>
                        <div class="combat-enemy__bar">
                            <div class="combat-enemy__bar-fill combat-player__bar-fill--${hpPct}" style="width: ${pct}%"></div>
                        </div>
                        ${woundHTML}
                        ${duraWarn}
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
        // #595: żywy wróg jest klikalnym celem; podświetl aktualnie wybrany + znacznik 🎯.
        const _isTarget = !dead && selectedTargetId != null && String(c.id) === String(selectedTargetId);
        const _targetable = !dead ? 'combat-combatant--targetable' : '';
        const _targetSel = _isTarget ? 'combat-combatant--target-selected' : '';
        const _targetAttr = !dead ? ` data-target-id="${escapeHtml(String(c.id))}" role="button" tabindex="0" title="Kliknij, aby celować w tego wroga"` : '';
        const _targetBadge = _isTarget ? `<span class="combat-combatant__target-badge" title="Wybrany cel">🎯</span>` : '';
        // #667: jawny znacznik strefy na żetonie (redundancja z kolumną) — czytelne
        // bez polegania na pozycji w kolumnie.
        const _ez = String(c.zone || 'engaged');
        const _ezGlyph = _ez === 'ranged' ? '🏹' : '🗡';
        const _ezTitle = _ez === 'ranged' ? 'Na dystans — daleko od ciebie' : 'W zwarciu — blisko ciebie';
        const _ezBadge = !dead ? `<span class="combat-combatant__zone" title="${_ezTitle}">${_ezGlyph}</span>` : '';
        // #660: po usunięciu chipów — rana + kondycje muszą żyć na wierszu, żeby nic nie zniknęło.
        const _enWound = !dead ? renderWoundLabelHTML(hpCur, hpMax) : '';
        const _enConds = !dead ? _renderConditionBadges(_rowConds) : '';
        return `
            <div class="combat-combatant combat-combatant--enemy${activeCls} ${dead ? 'combat-enemy--dead' : ''} ${_targetable} ${_targetSel}"${_targetAttr}>
                ${activeArrow}
                <div class="combat-combatant__icon">${dead ? '💀' : '⚔️'}</div>
                <div class="combat-combatant__body">
                    <div class="combat-combatant__name">
                        ${_ezBadge}
                        <span class="combat-combatant__name-text ${dead ? 'combat-enemy--dead' : ''}">${escapeHtml(name)}</span>
                        ${_targetBadge}
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
                    ${_enWound}
                    ${_enConds ? `<div class="combat-combatant__cond-row">${_enConds}</div>` : ''}
                </div>
            </div>`;
    };

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

function appendCombatTurnCard(row) {
    const evt = String(row.event_type || '');
    const actor = String(row.actor || '');
    let html = '';

    if (evt === 'reaction') {
        // S15 (#610) unik / S16 (#611) blok tarczą — wynik testu reakcji przeciw atakowi wroga.
        let meta = {};
        try { meta = typeof row.narrative === 'string' ? JSON.parse(row.narrative) : {}; } catch (_e) {}
        let txt;
        if (String(meta.reaction || '') === 'shield_block') {
            if (meta.full_block === true) {
                txt = `🛡 Blok pełny — atak całkowicie odparty (test ${meta.block_total ?? '?'} vs ${meta.dc ?? '?'})`;
            } else if (Number(meta.reduction || 0) > 0) {
                txt = `🛡 Blok — obrażenia zmniejszone o ${meta.reduction} (test ${meta.block_total ?? '?'} vs ${meta.dc ?? '?'})`;
            } else {
                txt = `🛡 Blok nieudany (test ${meta.block_total ?? '?'} vs ${meta.dc ?? '?'})${meta.durability_hit ? ' — tarcza uszkodzona' : ''}`;
            }
        } else {
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
        const label = escapeHtml(String(meta.attack_label || 'ATAK'));
        const stat = meta.attack_stat ? ` · ${escapeHtml(String(meta.attack_stat).toUpperCase())}` : '';
        const ac = meta.target_ac != null ? ` vs AC ${meta.target_ac}` : '';
        const hitLine = hit
            ? `<span class="cturn__hit">✅ TRAFIENIE · ${dmg != null ? dmg : '?'} obrażeń</span>`
            : `<span class="cturn__miss">❌ PUDŁO</span>`;
        // SF8 (#637) — rozbicie rzutu po nazwanym źródle (z live response, jednorazowo).
        let breakdownLine = '';
        const bd = window._pendingAttackBreakdown;
        window._pendingAttackBreakdown = null;
        if (bd && Array.isArray(bd.parts) && bd.parts.length) {
            breakdownLine = `<div class="cturn__breakdown">🎲 ${bd.d20} ${sf8BreakdownHtml(bd.parts)} = <strong>${bd.total}</strong></div>`;
        }
        html = `<div class="cturn cturn--player">
            <div class="cturn__head">⚔️ <strong>${label}</strong>${stat} → ${tgt}</div>
            <div class="cturn__detail">Rzut: ${rv != null ? rv : '—'}${ac} → ${hitLine}</div>
            ${breakdownLine}
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
            label: 'Obrażenia',
            kind: 'damage',
        };
    }
    return null;
}

// #569 / #661: visible 3D dice modal for combat rolls. Reuses the skill-test
// dice-overlay + DICE.dice_box. Stage 1 = the d20 attack (lands on pre-rolled
// forcedD20). Stage 2 (optional, `damageStage`) = the NdX damage/heal roll,
// landing on the backend's per-die results. Returns a Promise that resolves when
// the modal closes (auto-dwell or on click) so combat can continue.
function playCombatDiceRoll(forcedD20, label, breakdown = null, damageStage = null, outcome = null) {
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
        if (!overlay || !container || !resultCard || !resultNum) { resolve(); return; }

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
            if (skillCard) skillCard.hidden = false;
            if (skipBtn)   skipBtn.style.display = '';
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

        // Throw `notation` and land on `forced` (array of per-die results, or null
        // to let the lib roll freely). Calls onComplete after the dice settle.
        const throwDice = (notation, forced, onComplete) => {
            // #730: guard the settle phase. If the 3D dice library's settle callback
            // never fires (WebGL stalled/lost context), `onComplete` would never run →
            // the „Rzucam k20…" veil hangs forever, dimming the screen and blocking all
            // controls until reload. A one-shot `finish` + hard timeout guarantees the
            // roll always advances to the result card and the overlay can close.
            let _settled = false;
            const finish = () => { if (_settled) return; _settled = true; onComplete(); };
            requestAnimationFrame(() => {
                if (typeof DICE === 'undefined' || typeof DICE.dice_box !== 'function') {
                    finish(); return;
                }
                try {
                    if (!_diceBox) { _diceBox = new DICE.dice_box(container); }
                    else { _diceBox.clear(); _diceBox.rolling = false; _diceBox.reinit(container); }
                    _diceBox.setDice(notation);
                } catch (_e) { finish(); return; }
                // Backstop: force-advance if the dice never report settling.
                setTimeout(finish, 4000);
                _diceBox.start_throw(() => forced, () => setTimeout(finish, 400));
            });
        };

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
                    if (ds.multiplier && ds.multiplier > 1) line += ` ×${ds.multiplier}`;
                    resultTot.innerHTML = `${line}  =  <strong>${total}</strong> ${unit}`;
                }
                resultCard.hidden = false;
                armAdvance(1600, cleanup);  // wartość startowa — druga animacja wydłuża turę
            };
            throwDice(ds.notation, forced, showDmg);
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

        requestAnimationFrame(() => {
            // Fallback: brief number spin when the 3D dice library failed to load.
            if (typeof DICE === 'undefined' || typeof DICE.dice_box !== 'function') {
                resultCard.hidden = false;
                let ticks = 0;
                const iv = setInterval(() => {
                    resultNum.textContent = Math.ceil(Math.random() * 20);
                    if (++ticks >= 10) { clearInterval(iv); showAttack(d20); }
                }, 60);
                return;
            }
            throwDice('1d20', [d20], () => showAttack(d20));
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
        combatBusy = false; playerActionFetchActive = false;  // #700
        if (lastCombatState) renderCombatUI(lastCombatState);
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
    container.querySelector('#btn-long-rest')?.addEventListener('click', () => openLongRestModal(character, sheet));
    container.querySelector('#btn-awansuj')?.addEventListener('click', () => openAwansujPanel(character, sheet));
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
        // Stage 10-C — route through apiRequest so the JWT Bearer header is
        // attached automatically. Mechanics metadata is public, raw fetch ok.
        const [xpData, skillMeta] = await Promise.all([
            apiRequest('GET', `/characters/${character.id}/xp?user_id=${currentUser?.id}`),
            fetch('/api/mechanics/metadata').then(r => r.ok ? r.json() : {})
        ]);
        const xpAvail = xpData.xp_available ?? 0;
        const skills = sheet.skills || {};
        const stats = sheet.stats || {};
        const mods = sheet.stat_modifiers || {};
        const rankCosts = xpData.rank_up_costs || {};
        const statCosts = xpData.stat_point_costs || {};
        const skillRankCeiling = xpData.skill_rank_ceiling ?? 3;
        const statValueCeiling = xpData.stat_value_ceiling ?? 19;
        const isScholar = (sheet.archetype || '').toLowerCase() === 'scholar';

        // X6: skill rank-up cards
        const skillCards = Object.entries(skills).filter(([, rank]) => rank < skillRankCeiling).map(([key, rank]) => {
            const newRank = rank + 1;
            const cost = rankCosts[newRank] || rankCosts[String(newRank)] || '?';
            const canAfford = typeof cost === 'number' && xpAvail >= cost;
            const label = (skillMeta?.skills || []).find(s => s.key === key)?.label || key;
            return `<div class="awansuj-card ${canAfford ? '' : 'awansuj-card--locked'}">
                <div class="awansuj-card__title">${escapeHtml(label)}</div>
                <div class="awansuj-card__detail">Ranga ${rank} → ${newRank}</div>
                <button class="awansuj-card__btn" data-action="skill" data-key="${key}" data-cost="${cost}" ${canAfford ? '' : 'disabled'}>
                    ${cost} PD
                </button>
            </div>`;
        }).join('');

        // X7: stat point-up cards
        const STAT_LABELS = { STR:'Siła', DEX:'Zręczność', CON:'Kondycja', INT:'Inteligencja', WIS:'Mądrość', CHA:'Charyzma', LCK:'Szczęście' };
        const statCards = Object.entries(stats).map(([key, val]) => {
            const newVal = val + 1;
            const cost = statCosts[newVal] || statCosts[String(newVal)];
            if (!cost || newVal > statValueCeiling) return '';
            const canAfford = xpAvail >= cost;
            const mod = mods[key] ?? Math.floor((val - 10) / 2);
            const newMod = Math.floor((newVal - 10) / 2);
            return `<div class="awansuj-card ${canAfford ? '' : 'awansuj-card--locked'}">
                <div class="awansuj-card__title">${STAT_LABELS[key] || key}</div>
                <div class="awansuj-card__detail">${val} (${mod >= 0 ? '+' : ''}${mod}) → ${newVal} (${newMod >= 0 ? '+' : ''}${newMod})</div>
                <button class="awansuj-card__btn" data-action="stat" data-key="${key}" data-cost="${cost}" ${canAfford ? '' : 'disabled'}>
                    ${cost} PD
                </button>
            </div>`;
        }).filter(Boolean).join('');

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
                        <button class="awansuj-card__btn" data-action="spell-learn" data-key="${spell.key}" data-cost="75" ${canAfford ? '' : 'disabled'}>75 PD</button>
                    </div>`;
                } else if (currentRank < 3) {
                    const cost = currentRank === 1 ? 50 : 100;
                    const canAfford = xpAvail >= cost;
                    spellCards += `<div class="awansuj-card awansuj-card--spell ${canAfford ? '' : 'awansuj-card--locked'}">
                        <div class="awansuj-card__title">✨ ${escapeHtml(spell.label)}</div>
                        <div class="awansuj-card__detail">R${currentRank} → R${currentRank + 1}</div>
                        <button class="awansuj-card__btn" data-action="spell-upgrade" data-key="${spell.key}" data-cost="${cost}" ${canAfford ? '' : 'disabled'}>${cost} PD</button>
                    </div>`;
                }
            });
        }

        body.innerHTML = `
            <div class="awansuj-xp-badge">Dostępne PD: <strong>${xpAvail}</strong></div>
            ${skillCards || statCards ? `<div class="awansuj-section-label">Umiejętności</div><div class="awansuj-grid">${skillCards}</div>
            <div class="awansuj-section-label">Cechy</div><div class="awansuj-grid">${statCards}</div>` : ''}
            ${isScholar && spellCards ? `<div class="awansuj-section-label">Zaklęcia (Scholar)</div><div class="awansuj-grid">${spellCards}</div>` : ''}
            <div class="awansuj-section-label">Historia PD</div>
            <div id="awansuj-xp-log"><div class="camp-loading">Ładowanie…</div></div>`;

        loadXpLog(character, document.getElementById('awansuj-xp-log'));

        body.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const { action, key, cost } = btn.dataset;
                if (!confirm(`Wydać ${cost} PD?`)) return;
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
                    showToast(`Zakupiono! Pozostało: ${data.xp_available} PD`, 'success');
                    modal.style.display = 'none';
                    await refreshCharacterSheet();
                } catch (e) {
                    showToast('Błąd: ' + e.message, 'error');
                }
            });
        });
    } catch (e) {
        body.innerHTML = `<p style="color:var(--accent-red)">${escapeHtml(e.message)}</p>`;
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
            btn.addEventListener('click', () => castSpellOutOfCombat(btn.dataset.spellKey));
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

    // Lore
    const loreCount = document.getElementById('inv-lore-count');
    const loreList = document.getElementById('sheet-lore');
    if (loreCount) loreCount.textContent = lore.length;
    if (loreList) {
        loreList.innerHTML = lore.length
            ? lore.map(_renderLoreRow).join('')
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
    return `
        <div class="inv-row" data-inventory-id="${item.id}">
            <div class="inv-row__icon">${INV_ICONS[kind]}</div>
            <div class="inv-row__info">
                <div class="inv-row__name">${escapeHtml(item.label || item.key || '?')}${qty}</div>
                ${dura}
            </div>
            ${action}
        </div>`;
}

function _renderLoreRow(item) {
    const qty = item.quantity > 1 ? `<span class="inv-row__qty">×${item.quantity}</span>` : '';
    // D5 (#380): old hover tooltip removed — the click-to-open detail modal replaces it
    // (was duplicating the description with the new modal).
    const isNarrative = item.is_narrative || item.item_type === 'narrative';
    // Stage 4 S7: quest items can never be dropped — story-critical, no escape hatch.
    const isQuest = item.item_type === 'quest' || item.is_quest === true;
    const dropBtn = (isNarrative && !isQuest)
        ? `<button class="inv-row__drop-btn" data-action="drop" data-inventory-id="${item.id}" title="Wyrzuć przedmiot">✕</button>`
        : '';
    return `
        <div class="inv-row" data-inventory-id="${item.id}">
            <div class="inv-row__icon">${INV_ICONS.scroll}</div>
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
    overlay.innerHTML = `
        <div style="background:#14141c;border:1px solid rgba(245,158,11,.25);border-radius:12px;max-width:420px;width:100%;padding:18px;box-shadow:0 10px 40px rgba(0,0,0,.5)">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:8px">
                <div style="font-size:1.05rem;font-weight:700;color:#f5deb3">${escapeHtml(d.name || '?')}</div>
                <button id="item-view-close" style="background:none;border:none;color:#999;font-size:1.2rem;cursor:pointer;line-height:1">✕</button>
            </div>
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
            const aliveEnemies = enemies.filter(e => (e.hp || 0) > 0);
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
                <div style="color:#64748b;font-size:0.68rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">World State <span style="color:#334155;font-weight:400">${ws.scene_cleared?'✓ cleared':aliveEnemies.length+' alive'}</span></div>
                <div style="display:flex;flex-direction:column;gap:2px">
                  <div><span style="color:#334155">Enemies:</span> ${enemies.length ? enemies.map(e=>`<span style="color:${(e.hp||0)<=0?'#f87171':'#4ade80'}">${_esc(e.name||e.key||'?')}(${e.hp??'?'})</span>`).join(' ') : '<span style="color:#334155">—</span>'}</div>
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
let _selectedTheme = 'dark_fantasy';

function _applyTheme(theme) {
    document.body.dataset.theme = theme === 'classic' ? 'classic' : '';
}

async function showOnboardingCinematic() {
    showScreen('onboarding');

    // Reset theme selection to default
    _selectedTheme = 'dark_fantasy';
    document.querySelectorAll('.onboarding__theme-card').forEach(card => {
        const isDefault = card.dataset.theme === 'dark_fantasy';
        card.classList.toggle('onboarding__theme-card--selected', isDefault);
        card.setAttribute('aria-pressed', String(isDefault));
    });

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

async function completeOnboarding() {
    clearTimeout(_onboardingTimer);
    try {
        await apiRequest('PATCH', '/me/game-settings', { visual_theme: _selectedTheme });
    } catch (_) {}
    try {
        await apiRequest('PATCH', '/me/onboarding');
    } catch (_) {}
    _applyTheme(_selectedTheme);
    if (currentUser) {
        currentUser.game_mode_flags = JSON.stringify({ visual_theme: _selectedTheme });
        localStorage.setItem('user', JSON.stringify(currentUser));
    }
    showScreen('heroes');
}

// ── E25: Just-in-time onboarding card overlay ───────────────────────────────
// Shows cards one at a time with "Rozumiem" button, then POSTs mark-seen.
function showOnboardingCards(cards) {
    if (!cards || cards.length === 0) return;
    let idx = 0;

    const overlay = document.createElement('div');
    overlay.id = 'onboarding-card-overlay';
    overlay.className = 'onboarding-card-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');

    function renderCard() {
        const card = cards[idx];
        overlay.innerHTML = `
            <div class="onboarding-card">
                <div class="onboarding-card__progress">${idx + 1} / ${cards.length}</div>
                <h3 class="onboarding-card__title">${escapeHtml(card.title)}</h3>
                <p class="onboarding-card__content">${escapeHtml(card.content)}</p>
                <button type="button" class="btn btn--primary onboarding-card__btn-ok">Rozumiem</button>
            </div>`;
        overlay.querySelector('.onboarding-card__btn-ok').addEventListener('click', async () => {
            const key = card.mechanic_key;
            if (currentUser?.id) {
                apiRequest('POST', `/users/${currentUser.id}/seen-mechanics`, { mechanic_key: key })
                    .catch(() => {});
            }
            idx++;
            if (idx < cards.length) {
                renderCard();
            } else {
                overlay.remove();
            }
        });
    }

    renderCard();
    document.body.appendChild(overlay);
    overlay.querySelector('.onboarding-card__btn-ok')?.focus();
}

// ── E26: Kodeks — biblioteka przeczytanych kart mechanik ─────────────────────
async function showCodexLibrary() {
    if (!currentUser?.id) return;
    let cards = [];
    try {
        const data = await apiRequest('GET', `/users/${currentUser.id}/mechanic-cards`);
        cards = data.cards || [];
    } catch (_) {}

    const overlay = document.createElement('div');
    overlay.className = 'onboarding-card-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');

    if (cards.length === 0) {
        overlay.innerHTML = `
            <div class="onboarding-card">
                <h3 class="onboarding-card__title">Kodeks gracza</h3>
                <p class="onboarding-card__content">Nie odkryłeś jeszcze żadnych mechanik. Karty pojawiają się podczas rozgrywki.</p>
                <button type="button" class="btn btn--primary onboarding-card__btn-ok">Zamknij</button>
            </div>`;
        overlay.querySelector('.onboarding-card__btn-ok').addEventListener('click', () => overlay.remove());
    } else {
        let idx = 0;
        function renderCodexCard() {
            const card = cards[idx];
            overlay.innerHTML = `
                <div class="onboarding-card">
                    <div class="onboarding-card__progress">Kodeks: ${idx + 1} / ${cards.length}</div>
                    <h3 class="onboarding-card__title">${escapeHtml(card.title)}</h3>
                    <p class="onboarding-card__content">${escapeHtml(card.content)}</p>
                    <div class="onboarding-card__nav">
                        <button type="button" class="btn btn--secondary codex-prev" ${idx === 0 ? 'disabled' : ''}>← Poprzednia</button>
                        <button type="button" class="btn btn--primary codex-close">Zamknij</button>
                        <button type="button" class="btn btn--secondary codex-next" ${idx === cards.length - 1 ? 'disabled' : ''}>Następna →</button>
                    </div>
                </div>`;
            overlay.querySelector('.codex-prev')?.addEventListener('click', () => { if (idx > 0) { idx--; renderCodexCard(); } });
            overlay.querySelector('.codex-next')?.addEventListener('click', () => { if (idx < cards.length - 1) { idx++; renderCodexCard(); } });
            overlay.querySelector('.codex-close')?.addEventListener('click', () => overlay.remove());
        }
        renderCodexCard();
    }

    document.body.appendChild(overlay);
    overlay.querySelector('.onboarding-card__btn-ok, .codex-close')?.focus();
}

// ── E28: Tutorial offer for first-time players ───────────────────────────────
function _askTutorial() {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'onboarding-card-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.innerHTML = `
            <div class="onboarding-card">
                <h3 class="onboarding-card__title">Witaj, Wędrowcze!</h3>
                <p class="onboarding-card__content">
                    To Twoja pierwsza przygoda w AI-GM.<br>
                    Chcesz zacząć od samouczka <strong>"Moja Pierwsza Przygoda"</strong>,
                    który przeprowadzi Cię przez podstawy gry?
                </p>
                <div class="onboarding-card__nav">
                    <button type="button" class="btn btn--secondary tutorial-skip">Pomiń samouczek</button>
                    <button type="button" class="btn btn--primary tutorial-yes">Tak, samouczek!</button>
                </div>
            </div>`;
        overlay.querySelector('.tutorial-yes').addEventListener('click', () => { overlay.remove(); resolve(true); });
        overlay.querySelector('.tutorial-skip').addEventListener('click', () => { overlay.remove(); resolve(false); });
        document.body.appendChild(overlay);
        overlay.querySelector('.tutorial-yes')?.focus();
    });
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

    // D8 (#383) — znajomi + ustawienia modelu AI
    loadProfileFriends();
    loadProfileLlm();
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

    // ── E-mail (D8 #383) ──────────────────────────────────────────
    const emailEl = document.getElementById('profile-email-label');
    const emailEditBtn = document.getElementById('profile-email-edit-btn');
    const emailHint = document.getElementById('profile-email-hint');
    let _originalEmail = '';
    emailEditBtn?.addEventListener('click', () => {
        _originalEmail = emailEl.textContent.trim();
        emailEl.contentEditable = 'true';
        if (emailHint) emailHint.textContent = 'Enter aby zapisać · Esc aby anulować';
        _focusEnd(emailEl);
    });
    emailEl?.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const newEmail = emailEl.textContent.trim();
            emailEl.contentEditable = 'false';
            if (!newEmail || newEmail === _originalEmail) { emailEl.textContent = _originalEmail; if (emailHint) emailHint.textContent = ''; return; }
            const resp = await _saveProfile({ email: newEmail });
            if (resp && resp.email) { emailEl.textContent = resp.email; if (emailHint) emailHint.textContent = '✓ zapisano'; }
            else { emailEl.textContent = _originalEmail; }
        }
        if (e.key === 'Escape') { emailEl.textContent = _originalEmail; emailEl.contentEditable = 'false'; if (emailHint) emailHint.textContent = ''; }
    });
    emailEl?.addEventListener('blur', () => {
        if (emailEl.contentEditable === 'true') { emailEl.textContent = _originalEmail; emailEl.contentEditable = 'false'; }
    });

    // ── Model AI / LLM (D8 #383) ──────────────────────────────────
    const llmCustom = document.getElementById('profile-llm-custom');
    const llmFields = document.getElementById('profile-llm-fields');
    const llmSaveBtn = document.getElementById('profile-llm-save-btn');
    llmCustom?.addEventListener('change', () => { if (llmFields) llmFields.style.display = llmCustom.checked ? 'flex' : 'none'; });
    llmSaveBtn?.addEventListener('click', saveProfileLlm);
}

// ── D8 (#383): Profil — znajomi + ustawienia LLM ──────────────────────────
async function loadProfileFriends() {
    const el = document.getElementById('profile-friends-list');
    if (!el) return;
    try {
        const d = await apiRequest('GET', '/me/friends');
        const accepted = d.accepted || [], incoming = d.incoming || [], outgoing = d.outgoing || [];
        const parts = [];
        incoming.forEach(f => parts.push(`<div style="display:flex;align-items:center;gap:8px;justify-content:space-between">
            <span style="font-size:.85rem">${escapeHtml(f.display_name || f.username)} <span style="color:#888;font-size:.72rem">prosi o znajomość</span></span>
            <span style="display:flex;gap:6px">
              <button class="pf-action-btn" style="padding:4px 10px;font-size:.78rem" onclick="acceptFriendReq(${f.friendship_id})">✓</button>
              <button class="pf-action-btn" style="padding:4px 10px;font-size:.78rem" onclick="removeFriendReq(${f.friendship_id})">✕</button>
            </span></div>`));
        accepted.forEach(f => parts.push(`<div style="display:flex;align-items:center;gap:8px;justify-content:space-between">
            <span style="font-size:.85rem">${escapeHtml(f.display_name || f.username)}</span>
            <button class="pf-action-btn" style="padding:4px 10px;font-size:.78rem" onclick="removeFriendReq(${f.friendship_id})" title="Usuń">✕</button></div>`));
        outgoing.forEach(f => parts.push(`<div style="font-size:.82rem;color:#888">${escapeHtml(f.display_name || f.username)} — zaproszenie wysłane</div>`));
        el.innerHTML = parts.length ? parts.join('') : '<div style="color:#888;font-size:.82rem;text-align:center;padding:6px">Brak znajomych</div>';
    } catch (e) {
        el.innerHTML = '<div style="color:#888;font-size:.82rem;text-align:center;padding:6px">Brak znajomych</div>';
    }
}
async function acceptFriendReq(id) {
    try { await apiRequest('POST', `/me/friends/${id}/accept`, {}); showToast('Dodano do znajomych', 'success'); loadProfileFriends(); }
    catch (e) { showToast(e.message || 'Błąd', 'error'); }
}
async function removeFriendReq(id) {
    try { await apiRequest('DELETE', `/me/friends/${id}`); loadProfileFriends(); }
    catch (e) { showToast(e.message || 'Błąd', 'error'); }
}
async function loadProfileLlm() {
    if (!currentUser?.id) return;
    try {
        const s = await (await fetch(`/api/users/${currentUser.id}/llm-settings`)).json();
        const isCustom = (s.mode === 'custom');
        const c = document.getElementById('profile-llm-custom'); if (c) c.checked = isCustom;
        const f = document.getElementById('profile-llm-fields'); if (f) f.style.display = isCustom ? 'flex' : 'none';
        const m = document.getElementById('profile-llm-model'); if (m) m.value = s.model || '';
        const b = document.getElementById('profile-llm-baseurl'); if (b) b.value = s.base_url || '';
    } catch (e) { /* ignore */ }
}
async function saveProfileLlm() {
    if (!currentUser?.id) return;
    const hint = document.getElementById('profile-llm-hint');
    const custom = document.getElementById('profile-llm-custom')?.checked;
    const body = {
        mode: custom ? 'custom' : 'default',
        model: document.getElementById('profile-llm-model')?.value?.trim() || null,
        base_url: document.getElementById('profile-llm-baseurl')?.value?.trim() || null,
        api_key: document.getElementById('profile-llm-key')?.value?.trim() || null,
    };
    try {
        const r = await fetch(`/api/users/${currentUser.id}/llm-settings`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        if (hint) { hint.textContent = '✓ zapisano'; hint.style.color = '#4caf50'; }
    } catch (e) {
        if (hint) { hint.textContent = '✕ błąd zapisu'; hint.style.color = 'var(--red,#e88)'; }
    }
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

    // Onboarding cinematic
    document.getElementById('onboarding-cta')?.addEventListener('click', completeOnboarding);
    document.getElementById('onboarding-themes')?.addEventListener('click', e => {
        const card = e.target.closest('.onboarding__theme-card');
        if (!card) return;
        _selectedTheme = card.dataset.theme;
        document.querySelectorAll('.onboarding__theme-card').forEach(c => {
            const selected = c === card;
            c.classList.toggle('onboarding__theme-card--selected', selected);
            c.setAttribute('aria-pressed', String(selected));
        });
        _applyTheme(_selectedTheme);
    });

    // Profile page
    document.getElementById('profile-back-btn')?.addEventListener('click', () => showScreen(_profileReturnScreen || 'heroes'));
    _initProfileEditing();
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

    // D10 E2 — theme selector in profile
    document.querySelectorAll('.theme-selector-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const theme = this.dataset.theme || 'dark_fantasy';
            _selectedTheme = theme;
            _applyTheme(theme);
            document.querySelectorAll('.theme-selector-btn').forEach(b => {
                b.classList.toggle('theme-selector-btn--selected', b.dataset.theme === theme);
            });
            try {
                await apiRequest('PATCH', '/me/game-settings', { visual_theme: theme });
            } catch (e) {
                console.error('Failed to save theme:', e);
            }
        });
    });
    // Set initial state from current theme
    const currentTheme = document.body.dataset.theme === 'classic' ? 'classic' : 'dark_fantasy';
    document.querySelectorAll('.theme-selector-btn').forEach(btn => {
        btn.classList.toggle('theme-selector-btn--selected', btn.dataset.theme === currentTheme);
    });

    // Campaigns
    elements.btnNewCampaign?.addEventListener('click', showNewCampaignScreen);
    elements.btnLogout?.addEventListener('click', handleLogout);

    // New Campaign
    elements.newCampaignForm?.addEventListener('submit', handleCreateCampaign);
    elements.btnNewCampaignBack?.addEventListener('click', () => showScreen('campaigns'));

    // Stage 8 D3 — debug drawer toggle (admin only; visibility set by updateAdminSettingsVisibility)
    document.getElementById('debug-drawer-toggle')?.addEventListener('click', _toggleDebugDrawer);
    // B7 — DEV Inspector toggle
    document.getElementById('dev-inspector-toggle')?.addEventListener('click', _openInspectorModal);

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
    elements.btnOpenCodex?.addEventListener('click', showCodexLibrary);

    // Combat
    elements.btnCombatAttack?.addEventListener('click', onCombatAttackButton);  // B6c (#651): mag → menu ataku
    elements.btnCombatFlee?.addEventListener('click', handleCombatFlee);
    elements.btnCombatMove?.addEventListener('click', handleCombatMove);
    elements.btnCombatDodge?.addEventListener('click', handleCombatDodge);
    elements.btnCombatBlock?.addEventListener('click', handleCombatBlock);
    elements.btnCombatWrestle?.addEventListener('click', handleCombatWrestle);
    document.getElementById('combat-spell-btn')?.addEventListener('click', openSpellPicker);
    // SF1 (#619): pasek „Akcja" otwiera bottom sheet; tło/Esc/wybór pozycji zamyka.
    elements.btnCombatAction?.addEventListener('click', openCombatSheet);
    elements.combatActionSheetBackdrop?.addEventListener('click', closeCombatSheet);
    elements.combatActionSheetList?.addEventListener('click', (e) => {
        // klik w pozycję arkusza (nie w wyszarzony/disabled przycisk) → wykonaj handler i zamknij
        const btn = e.target.closest('.combat-btn');
        if (btn && !btn.disabled) closeCombatSheet();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && elements.combatActionSheet && !elements.combatActionSheet.hidden) closeCombatSheet();
    });
    // B6c (#651): arkusz „Atak" (mag) — tło/Esc zamyka; pozycje mają własne handlery.
    document.getElementById('combat-attack-sheet-backdrop')?.addEventListener('click', closeAttackSheet);
    document.addEventListener('keydown', (e) => {
        const sh = document.getElementById('combat-attack-sheet');
        if (e.key === 'Escape' && sh && !sh.hidden) closeAttackSheet();
    });
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

    // U19 (#571) — recap card controls
    document.getElementById('recap-continue-btn')?.addEventListener('click', closeRecapCard);
    document.getElementById('journal-recap-btn')?.addEventListener('click', openRecapManually);

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
        // /czar [spell_key] — autocomplete from known non-offensive spells
        if (/^czar(\s|$)/i.test(token)) {
            return { idx, query: token, isCzar: true };
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
        } else if (ctx.isCzar) {
            if (!characterData?.id) { hide(); return; }
            const afterCzar = ctx.query.replace(/^czar\s*/i, '');
            _fetchCzarSpells().then(spells => {
                const sugg = getCzarSuggestions(afterCzar, spells);
                if (!sugg.length) { hide(); return; }
                matches = sugg;
                hi = 0;
                showPopup();
            });
            return;
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

    if (checkUrlRouting()) return;

    if (checkAuth()) {
        updateAdminSettingsVisibility();
        const displayName = currentUser.display_name || currentUser.username || '';
        if (elements.heroesWelcome) elements.heroesWelcome.textContent = `Witaj, ${displayName}`;
        if (elements.welcomeUser) elements.welcomeUser.textContent = `Witaj, ${displayName}`;
        await loadHeroes();
        if (!authToken) return; // handleSessionExpired fired during loadHeroes
        if (await tryRestoreSession()) return;
        if (!authToken) return; // handleSessionExpired fired during tryRestoreSession
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

async function loadAppVersion() {
    try {
        const resp = await fetch('/api/version');
        if (!resp.ok) return;
        const { version } = await resp.json();
        const label = `v${version}`;
        const el = document.getElementById('app-version-badge');
        if (el) { el.textContent = label; el.style.cursor = 'pointer'; el.onclick = showChangelog; }
        const fixed = document.getElementById('app-version-fixed');
        if (fixed) { fixed.textContent = label; fixed.style.pointerEvents = 'auto'; fixed.style.cursor = 'pointer'; fixed.onclick = showChangelog; fixed.style.opacity = '0.6'; }
    } catch (_e) {}
}

function _renderChangelog(md) {
    return md
        .replace(/^# .+$/m, '')
        .replace(/^---$/gm, '<hr>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^\- \*\*(.+?)\*\* — (.+)$/gm, '<li><strong>$1</strong> — $2</li>')
        .replace(/^\- (.+)$/gm, '<li>$1</li>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/(<li>[\s\S]*?<\/li>)+/g, m => `<ul>${m}</ul>`)
        .replace(/\n{2,}/g, '\n')
        .trim();
}

async function showChangelog() {
    let modal = document.getElementById('changelog-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'changelog-modal';
        modal.style.cssText = 'position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.75);backdrop-filter:blur(3px)';
        modal.innerHTML = `
            <div style="background:#1a1a2e;border:1px solid #3a3a5c;border-radius:10px;width:min(640px,92vw);max-height:80vh;display:flex;flex-direction:column;box-shadow:0 8px 40px #000a">
                <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid #3a3a5c">
                    <span style="color:#c8b8ff;font-family:monospace;font-size:14px;font-weight:bold">📋 Release History</span>
                    <button onclick="document.getElementById('changelog-modal').remove()" style="background:none;border:none;color:#888;font-size:20px;cursor:pointer;line-height:1">×</button>
                </div>
                <div id="changelog-body" style="overflow-y:auto;padding:16px 20px;color:#ccc;font-size:13px;line-height:1.6">
                    <em style="color:#666">Ładowanie...</em>
                </div>
            </div>`;
        modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
        document.body.appendChild(modal);
        try {
            const r = await fetch('/api/changelog');
            const md = await r.text();
            const body = document.getElementById('changelog-body');
            if (body) {
                body.innerHTML = `<style>#changelog-body h2{color:#c8b8ff;margin:12px 0 4px;font-size:14px}#changelog-body h3{color:#88aacc;margin:8px 0 2px;font-size:12px;text-transform:uppercase;letter-spacing:.05em}#changelog-body ul{margin:4px 0 8px 16px;padding:0}#changelog-body li{margin:2px 0}#changelog-body hr{border:none;border-top:1px solid #333;margin:12px 0}#changelog-body strong{color:#e0d0ff}</style>` + _renderChangelog(md);
            }
        } catch (_e) {
            const body = document.getElementById('changelog-body');
            if (body) body.textContent = 'Nie można załadować changelogu.';
        }
    } else {
        modal.remove();
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    await loadBgSettings(); // await so login/heroes screen gets the correct background
    loadAppVersion();
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

  // E21: dungeon hex → skip travel, open dungeon picker directly
  if (hex.hex_type === 'dungeon') {
    _wmClose();
    openDungeonPicker();
    return;
  }

  _wmap.pendingTravel = { q, r, label };
  const confirm = _wmap.confirm;
  confirm.querySelector('#wmap-confirm-title').textContent = `Podróżujesz do ${label}`;
  confirm.querySelector('#wmap-confirm-info').textContent = info;
  confirm.removeAttribute('hidden');
}

const _TERRAIN_THEMES = {
  plains:    { g: 'linear-gradient(160deg,#3A2200 0%,#6B4400 35%,#9A6A18 65%,#5A3800 100%)', icon: '🌾' },
  forest:    { g: 'linear-gradient(160deg,#050E05 0%,#0F250F 35%,#1E421E 65%,#102010 100%)', icon: '🌲' },
  hills:     { g: 'linear-gradient(160deg,#1A1604 0%,#3A3210 35%,#5C5220 65%,#2E2808 100%)', icon: '⛰️' },
  mountains: { g: 'linear-gradient(160deg,#0A0E16 0%,#14202E 35%,#1E3044 65%,#0E1A28 100%)', icon: '🏔️' },
  swamp:     { g: 'linear-gradient(160deg,#060E06 0%,#0E2010 35%,#183A18 65%,#0A1A0C 100%)', icon: '🌿' },
  ruins:     { g: 'linear-gradient(160deg,#160806 0%,#2E1008 35%,#4A2214 65%,#2A1008 100%)', icon: '🏚️' },
  dungeon:   { g: 'linear-gradient(160deg,#050508 0%,#0C0C14 35%,#14141E 65%,#080812 100%)', icon: '🕯️' },
  road:      { g: 'linear-gradient(160deg,#180E04 0%,#2E1E08 35%,#4A3214 65%,#2A1C08 100%)', icon: '🛤️' },
  town:      { g: 'linear-gradient(160deg,#200A04 0%,#401808 35%,#6A3018 65%,#401808 100%)', icon: '🏘️' },
  castle:    { g: 'linear-gradient(160deg,#060610 0%,#10101C 35%,#1A1A2C 65%,#0C0C18 100%)', icon: '🏰' },
  cave:      { g: 'linear-gradient(160deg,#040404 0%,#0A0A0A 35%,#121210 65%,#060604 100%)', icon: '🪨' },
  river:     { g: 'linear-gradient(160deg,#060E18 0%,#0E1E2C 35%,#1C3040 65%,#0A1C2E 100%)', icon: '🌊' },
  water:     { g: 'linear-gradient(160deg,#060E18 0%,#0E1E2C 35%,#1C3040 65%,#0A1C2E 100%)', icon: '🏞️' },
  desert:    { g: 'linear-gradient(160deg,#2A1A04 0%,#4E3408 35%,#7A5618 65%,#3E2A08 100%)', icon: '🏜️' },
  tundra:    { g: 'linear-gradient(160deg,#0E1418 0%,#1E2A30 35%,#34464E 65%,#16242A 100%)', icon: '❄️' },
  coast:     { g: 'linear-gradient(160deg,#06121C 0%,#0E2434 35%,#1C3A50 65%,#0A1E30 100%)', icon: '🌅' },
  volcanic:  { g: 'linear-gradient(160deg,#140404 0%,#2E0A06 35%,#52160A 65%,#280806 100%)', icon: '🌋' },
};
const _TERRAIN_DEFAULT = { g: 'linear-gradient(160deg,#0A0810 0%,#16141E 50%,#201C2A 100%)', icon: '🗺️' };
let _travelCinematicTimer = null;

// #665: tip karty podróży. Priorytet: onboarding world_map (pierwsza podróż).
// Inaczej losowa odkryta karta Wiedzy/Kodeksu (cache na sesję, bez powtórki pod rząd).
let _codexTipsCache = null;
let _lastTravelTipKey = null;
async function _pickTravelTip(response) {
  const onboard = (response?.onboarding_cards || []).find(c => c.mechanic_key === 'world_map');
  if (onboard) return onboard;
  if (!currentUser?.id) return null;
  if (_codexTipsCache === null) {
    try {
      const data = await apiRequest('GET', `/users/${currentUser.id}/mechanic-cards`);
      _codexTipsCache = Array.isArray(data?.cards) ? data.cards : [];
    } catch { _codexTipsCache = []; }
  }
  const cards = _codexTipsCache;
  if (!cards.length) return null;
  const keyOf = c => String(c.mechanic_key || c.title || '');
  if (cards.length === 1) { _lastTravelTipKey = keyOf(cards[0]); return cards[0]; }
  let pick = cards[0];
  for (let i = 0; i < 8; i++) {
    pick = cards[Math.floor(Math.random() * cards.length)];
    if (keyOf(pick) !== _lastTravelTipKey) break;
  }
  _lastTravelTipKey = keyOf(pick);
  return pick;
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
      document.getElementById('travel-cin-tip-body').textContent = tip.content || tip.body || '';
      tipEl.removeAttribute('hidden');
    } else {
      tipEl.setAttribute('hidden', '');
    }

    overlay.removeAttribute('hidden');
    requestAnimationFrame(() => requestAnimationFrame(() => overlay.classList.add('travel-cin--visible')));

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
    // 400ms grace so lingering map-tap doesn't instantly dismiss
    setTimeout(() => overlay.addEventListener('click', done, { once: true }), 400);
  });
}

async function _wmExecuteTravel() {
  const t = _wmap.pendingTravel;
  if (!t) return;
  _wmap.confirm.setAttribute('hidden', '');
  _wmClose();

  // Dispatch hex travel to turn pipeline
  if (!currentCampaignId || !characterData?.id) return;
  try {
    const response = await apiRequest('POST', `/campaigns/${currentCampaignId}/travel`, {
      character_id: characterData.id,
      target_hex: { q: t.q, r: t.r },
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

    // Wait for map slide-out (280ms), then show full-screen travel cinematic
    await new Promise(r => setTimeout(r, 350));
    // #665: onboarding world_map (pierwsza podróż) lub losowa karta Kodeksu
    const cinTip = await _pickTravelTip(response);
    await _showTravelCinematic({
      hexType: arrivedData.hex_type,
      // Hex labels are usually empty — fall back to terrain name (Las/Rzeka/…)
      destLabel: destLabel || hexTypeName || null,
      atmo: arrivedData.atmosphere,
      tip: cinTip,
    });

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

// Re-fetch world map data from server. recenter=true centers on discovered hexes
// (used on open); recenter=false keeps current pan (used for live in-place refresh
// after a turn moved the player, so newly-discovered hexes appear without page reload).
async function _wmRefresh(recenter = false) {
  if (!currentCampaignId || !characterData?.id) return;
  const data = await apiRequest('GET', `/campaigns/${currentCampaignId}/world-map?character_id=${characterData.id}`);
  _wmap.hexes = data.hexes || [];
  _wmap.teleports = data.teleport_connections || [];
  _wmap.currentHex = data.current_hex;
  _wmap.hexTypes = data.hex_types || {};

  if (recenter) {
    const disc = _wmap.hexes.filter(h => h.status === 'discovered');
    if (disc.length) {
      const pixels = disc.map(h => _wmHexToPixel(h.q, h.r));
      const cx = pixels.reduce((s,p)=>s+p.x,0)/pixels.length;
      const cy = pixels.reduce((s,p)=>s+p.y,0)/pixels.length;
      const rect = _wmap.svg.getBoundingClientRect();
      _wmap.pan = { x: (rect.width||360)/2 - cx*_wmap.zoom, y: (rect.height||500)/2 - cy*_wmap.zoom };
    }
  }
  _wmRender();
}

async function _wmOpen() {
  if (!currentCampaignId || !characterData?.id) {
    showToast('Wybierz postać aby otworzyć mapę.', 'info'); return;
  }
  // L11: In active dungeon, show tile map instead of hex world map
  if (_activeDungeonRun && !_activeDungeonRun.completed && !_activeDungeonRun.failed) {
    openDungeonMap();
    return;
  }
  _wmap.panel.removeAttribute('hidden');
  _wmap.panel.style.transform = 'translateX(0)';

  try {
    await _wmRefresh(true);
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
        // B6c (#651): atakujące czary żyją pod „Atak" — tu zostają tylko nie-atakujące.
        const spells = (_cachedSpells || []).filter(s => s.spell_type !== 'attack' && s.spell_type !== 'attack_aoe');
        if (!spells.length) {
            list.innerHTML = '<div style="padding:12px;color:#888;font-size:0.8rem">Brak nie-atakujących zaklęć (atakujące są pod „Atak").</div>';
            return;
        }
        const TYPE_ICONS = { attack:'⚔', heal:'💚', defense:'🛡', effect:'✨', attack_aoe:'💥', narrative:'🕯' };
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

async function castSpellOutOfCombat(spellKey) {
    if (!currentCampaignId || !characterData?.id) {
        showToast('Brak aktywnej kampanii.', 'error');
        return;
    }
    const token = localStorage.getItem('aigm_access_token');
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/cast-spell`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({ spell_key: spellKey, character_id: characterData.id }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
            showToast(data?.detail || 'Błąd rzucania zaklęcia.', 'error');
            return;
        }
        _cachedSpells = null;
        _czarSpellCache = null;
        if (data.spell_type === 'narrative') {
            // Narrative spells go through the LLM so the GM narrates the effect
            const actionText = `Rzucam zaklęcie ${data.label || spellKey}. ${data.message || ''}`.trim();
            await sendTurn(actionText, 'free_text', `🕯 ${data.label || spellKey}`);
        } else {
            const msg = data.message || `Rzucono ${data.label || spellKey}.`;
            appendMessage({ role: 'system', content: `🔮 ${msg}`, created_at: new Date() });
            scrollToBottom();
            await refreshCharacterData();
        }
    } catch (e) {
        showToast(e.message || 'Błąd zaklęcia.', 'error');
    }
}

async function handleCombatSpellAttack(spellKey) {
    if (!combatActive || !currentCampaignId || combatBusy || enemyTurnInFlight) return;
    combatBusy = true; playerActionFetchActive = true;  // #700
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

        // #649 (B6a): animacja kości — parytet ze zwykłym atakiem (przedtem czar jej nie miał).
        const _atk = data.attack_roll || {};
        const _bdParts = _atk.attack_stat
            ? sf8AttackBreakdown(_atk, { surprise: data.surprise_atk_bonus, durability: data.durability_attack_penalty })
            : null;
        const _bdTotal = Number(data.attack_total ?? _atk.total ?? d20);
        // #661: czar atakujący → animacja obrażeń; heal → animacja leczenia (NdX).
        const _dodgeOutcomeSpell = data.dodge_roll
            ? { dodge: data.dodge_roll, dodged: !!data.dodged, hit: !!data.hit, attack_total: Number(data.attack_total ?? _bdTotal) }
            : null;
        await playCombatDiceRoll(d20, 'Czar', _bdParts ? { parts: _bdParts, total: _bdTotal } : null, buildDamageStage(data), _dodgeOutcomeSpell);

        await _handleCombatAttackResult(data, d20, body.enemy_key, target);
    } catch (err) {
        setCombatMsg(err.message || 'Błąd zaklęcia.', true);
    } finally {
        // #649 (B6a): reset NIEZALEŻNIE od wyniku. Bez tego po udanym czarze combatBusy
        // zostawało true i watcher tury wroga (warunek !combatBusy) nigdy nie odpalał →
        // tura wroga wisiała do F5. Lustro finally z handleCombatAttack.
        combatBusy = false; playerActionFetchActive = false;  // #700
        if (combatActive) {
            if (lastCombatState && elements.combatEndOverlay?.hidden !== false) renderCombatUI(lastCombatState);
            elements.btnCombatAttack.disabled = false;
            const _spellBtn = document.getElementById('combat-spell-btn');
            if (_spellBtn) _spellBtn.disabled = false;
            elements.btnCombatFlee.disabled = false;
        }
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
        // E22: check for active (incomplete) dungeon run first
        let activeRun = null;
        try {
            const runData = await apiRequest('GET', `/dungeons/active-run?character_id=${currentHero.id}`);
            activeRun = runData.active_run || null;
        } catch (_) { /* ignore — non-critical */ }

        const data = await apiRequest('GET', `/dungeons?character_id=${currentHero.id}`);
        const dungeons = data.dungeons || [];
        list.innerHTML = '';

        // L13/E22: active run → show resume modal (kontynuuj / porzuć) instead of silent card
        if (activeRun) {
            overlay.setAttribute('hidden', '');
            showDungeonResumeModal(activeRun);
            // Wire buttons (once per call; old listeners replaced each time modal shows)
            const continueBtn = document.getElementById('dungeon-resume-continue-btn');
            const abandonBtn = document.getElementById('dungeon-resume-abandon-btn');
            const resumeModal = document.getElementById('dungeon-resume-modal');
            if (continueBtn) {
                continueBtn.onclick = async () => {
                    resumeModal?.setAttribute('hidden', '');
                    await _resumeDungeonRun(activeRun.campaign_id);
                };
            }
            if (abandonBtn) {
                abandonBtn.onclick = () => {
                    resumeModal?.setAttribute('hidden', '');
                    // Set up context so abandon modal can call _doExitDungeon
                    _dungeonCampaignId = activeRun.campaign_id;
                    _activeDungeonRun = activeRun;
                    showDungeonAbandonModal();
                };
            }
            return; // don't show picker list while resume modal is showing
        }

        if (!dungeons.length && !activeRun) {
            list.innerHTML = '<p class="dungeon-picker-empty">Brak dostępnych lochów.</p>';
            return;
        }
        // #739: hero level for min_level gating — derive from lifetime XP (canonical),
        // matching the hero list + backend xp_service.
        const heroSheet = currentHero?.sheet_json || {};
        const heroLevel = (heroSheet.xp_lifetime_earned != null)
            ? Math.min(10, Math.floor(Number(heroSheet.xp_lifetime_earned) / 100) + 1)
            : (heroSheet.level || currentHero?.level || 1);

        dungeons.forEach(d => {
            const cd = d.cooldown || {};
            const onCooldown = cd.on_cooldown;
            const hoursLeft = cd.hours_remaining ? `${cd.hours_remaining}h` : '';
            const minLevel = d.min_level || 1;
            const locked = heroLevel < minLevel;            // #739: below required level
            const card = document.createElement('button');
            card.className = 'dungeon-card'
                + (onCooldown ? ' dungeon-card--cooldown' : '')
                + (locked ? ' dungeon-card--locked' : '');
            card.disabled = !!onCooldown || locked;
            card.innerHTML = `
                <div class="dungeon-card__icon">${locked ? '🔒' : '⛏'}</div>
                <div class="dungeon-card__body">
                    <div class="dungeon-card__name">${escapeHtml(d.label || d.key)}</div>
                    <div class="dungeon-card__meta">${d.rooms || '?'} komnat · Poz. ${minLevel}+</div>
                    <div class="dungeon-card__atm">${escapeHtml((d.atmosphere || '').slice(0, 80))}</div>
                </div>
                ${onCooldown
                    ? `<div class="dungeon-card__cooldown">⏳ ${hoursLeft}</div>`
                    : locked
                        ? `<div class="dungeon-card__cooldown">🔒 Wymagany Poz. ${minLevel}</div>`
                        : `<div class="dungeon-card__arrow">›</div>`
                }`;
            if (!onCooldown && !locked) {
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

    // #752: remember the campaign we came from so we can auto-return on exit.
    const _prevCampaignId = currentCampaignId || currentHero.campaign_id || null;

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
            previous_campaign_id: _prevCampaignId,
        });

        _activeDungeonRun = resp.dungeon_run;
        _dungeonSeenTiles = new Set();   // L12b: fresh run → tile popups show again
        await enterGame(dungeonCampaign, { dungeonFallbackNarrative: resp.room_narrative });
        updateDungeonHUD();
        showDungeonHUD(true);

        // #740: room_narrative is now fallback inside enterGame (used only if LLM fails).
        // Removed separate append — LLM __AI_GM_OPEN already has room context injected.
        // L12b: first-entry dungeon mechanics codex card (doors / chest / riddle / death)
        if (resp.onboarding_cards?.length) showOnboardingCards(resp.onboarding_cards);
        renderCurrentRoom();
    } catch (err) {
        showToast(err.message || 'Błąd wejścia do lochu', 'error');
    }
}

// E22: Resume an existing incomplete dungeon run
async function _resumeDungeonRun(campaignId) {
    try {
        showToast('Wznawiasz ekspedycję…', 'info', 2000);
        const campResp = await apiRequest('GET', `/campaigns/${campaignId}`);
        const camp = campResp.campaign || campResp;
        _dungeonCampaignId = campaignId;
        currentCampaignId = campaignId;
        currentCampaign = camp;

        const heroResp = await apiRequest('GET', `/characters/${currentHero.id}`);
        currentHero = heroResp.character || heroResp;
        characterData = currentHero;

        const runResp = await apiRequest('GET', `/campaigns/${campaignId}/dungeon-run`);
        if (runResp.dungeon_run && !runResp.dungeon_run.completed && !runResp.dungeon_run.failed) {
            _activeDungeonRun = runResp.dungeon_run;
        }

        await enterGame(camp);
        updateDungeonHUD();
        showDungeonHUD(true);
        renderCurrentRoom();
        _maybeShowDungeonCodexCard(runResp.onboarding_cards);
    } catch (err) {
        showToast(err.message || 'Błąd wznawiania lochu', 'error');
    }
}

// L12b: show the dungeon mechanics codex card once per page-load on resume/restore
// (fresh enter shows it directly). Guarded so moves/reloads don't re-stack it.
let _dungeonCardOffered = false;
function _maybeShowDungeonCodexCard(cards) {
    if (_dungeonCardOffered) return;
    if (!cards?.length) return;
    if (document.getElementById('onboarding-card-overlay')) return;
    _dungeonCardOffered = true;
    showOnboardingCards(cards);
}

function updateDungeonHUD() {
    const run = _activeDungeonRun;
    if (!run) return;
    const label = document.getElementById('dungeon-hud-label');
    const progress = document.getElementById('dungeon-hud-progress');
    const roomType = document.getElementById('dungeon-hud-room-type');
    const advBtn = document.getElementById('dungeon-advance-btn');

    if (label) label.textContent = `⛏ ${run.dungeon_label || 'Loch'}`;

    // v2: progress = visited nodes count / total nodes count
    if (progress) {
        const nodes = run.graph?.nodes || {};
        const total = Object.keys(nodes).length || 1;
        const visitedCount = Object.values(nodes).filter(n => n.visited).length;
        progress.textContent = `${visitedCount}/${total}`;
    }

    // v2: current node info
    const charId = characterData?.id;
    const positions = run.positions || {};
    const currentNodeId = (charId && positions[String(charId)]) || run.graph?.entry_node;
    const currentNode = run.graph?.nodes?.[currentNodeId];

    if (roomType && currentNode) {
        const content = currentNode.content || {};
        const typeName = currentNode.is_boss ? 'BOSS'
            : content.enemies?.length ? 'Walka'
            : content.riddle ? 'Zagadka'
            : content.chest ? 'Skrzynia'
            : 'Komnata';
        roomType.textContent = typeName;
    }

    // L12b: "show room view" icon — visible only when current tile has an image
    const roomViewBtn = document.getElementById('dungeon-room-view-btn');
    if (roomViewBtn) roomViewBtn.hidden = !currentNode?.content?.image_url;

    // v2: hide legacy advance-btn (movement via direction buttons)
    if (advBtn) advBtn.hidden = true;

    // Refresh nav + tile scene
    updateDungeonNav(run);
    renderTileScene(currentNode);

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
    // v2: delegate to updateDungeonHUD which handles v2 node state
    updateDungeonHUD();
}

// L12b (#694): node_ids whose tile-image popup was already auto-shown this run.
// Reset on enter/resume so a fresh run shows popups again.
let _dungeonSeenTiles = new Set();

// L12b: show the tile image as a popup modal (like the Dice Roll popup).
// `node` = a graph node ({tile_id, content:{image_url, room_description}, ...}).
function showTileImageModal(node) {
    const modal = document.getElementById('dungeon-tile-modal');
    if (!modal || !node) return;
    const content = node.content || {};
    const img = document.getElementById('dungeon-tile-modal-img');
    const name = document.getElementById('dungeon-tile-modal-name');

    // Image + name only — the room_description is narrator fuel (Decyzja 3),
    // the player reads the LLM-colorized version in chat, not the raw text.
    if (name) name.textContent = content.label || node.label || 'Komnata';
    if (img) {
        if (content.image_url) {
            img.src = content.image_url;
            img.removeAttribute('hidden');
        } else {
            img.src = '';
            img.setAttribute('hidden', '');
        }
    }
    modal.removeAttribute('hidden');
}

function closeTileImageModal() {
    document.getElementById('dungeon-tile-modal')?.setAttribute('hidden', '');
}

// L20b (#724): show full-screen portrait modal for enemies/NPCs.
// enemies = array of {name, image_url} objects. Auto-closes after 2 s or click.
// Returns a Promise that resolves when the modal closes.
function showEnemyPortraitModal(entities) {
    return new Promise((resolve) => {
        const modal = document.getElementById('portrait-modal');
        const box = document.getElementById('portrait-modal-box');
        if (!modal || !box) { resolve(); return; }

        const cards = entities.map(e => {
            const imgHtml = e.image_url
                ? `<img class="portrait-modal__card-img" src="${escapeHtml(e.image_url)}" alt="${escapeHtml(e.name || '')}">`
                : `<div class="portrait-modal__card-img-placeholder">⚔️</div>`;
            return `<div class="portrait-modal__card">${imgHtml}<div class="portrait-modal__card-name">${escapeHtml(e.name || 'Wróg')}</div></div>`;
        }).join('');
        box.innerHTML = cards + `<div class="portrait-modal__hint">Dotknij, aby kontynuować</div>`;

        modal.removeAttribute('hidden');
        let closed = false;
        const close = () => {
            if (closed) return;
            closed = true;
            modal.setAttribute('hidden', '');
            modal.removeEventListener('click', close);
            resolve();
        };
        modal.addEventListener('click', close);
        setTimeout(close, 2000);
    });
}

// L12b: reopen the popup for the room the player is currently standing in.
function showCurrentTileImageModal() {
    const run = _activeDungeonRun;
    if (!run) return;
    const charId = characterData?.id;
    const positions = run.positions || {};
    const nodeId = (charId && positions[String(charId)]) || run.graph?.entry_node;
    const node = run.graph?.nodes?.[nodeId];
    if (node?.content?.image_url) showTileImageModal(node);
    else showToast('Brak obrazu dla tej komnaty', 'info');
}

// L12b: called from updateDungeonHUD. Image is NO LONGER inline above chat —
// it pops up as a modal on the FIRST visit to each tile only.
function renderTileScene(node) {
    if (!node) return;
    const charId = characterData?.id;
    const positions = _activeDungeonRun?.positions || {};
    const nodeId = (charId && positions[String(charId)]) || _activeDungeonRun?.graph?.entry_node;
    if (!nodeId) return;
    const content = node.content || {};
    if (content.image_url && !_dungeonSeenTiles.has(nodeId)) {
        _dungeonSeenTiles.add(nodeId);
        showTileImageModal(node);
    }
}

function updateDungeonNav(run) {
    const nav = document.getElementById('dungeon-nav');
    if (!nav) return;

    const charId = characterData?.id;
    const positions = run?.positions || {};
    const currentNodeId = (charId && positions[String(charId)]) || run?.graph?.entry_node;
    const currentNode = run?.graph?.nodes?.[currentNodeId];
    const content = currentNode?.content || {};

    // Hide nav during combat (enemies present and not cleared)
    const inCombat = content.enemies?.length > 0 && !currentNode?.cleared;
    if (inCombat || !run || run.completed || run.failed) {
        nav.setAttribute('hidden', '');
        return;
    }
    nav.removeAttribute('hidden');

    // Show/hide direction buttons based on available exits
    const doorsOpen = currentNode?.doors_open || {};
    for (const dir of ['N', 'S', 'E', 'W']) {
        const btn = nav.querySelector(`[data-dungeon-dir="${dir}"]`);
        if (!btn) continue;
        if (doorsOpen[dir]) {
            btn.removeAttribute('hidden');
            const hint = currentNode.door_hints?.[dir];
            btn.title = hint ? `${dir}: ${hint}` : dir;
        } else {
            btn.setAttribute('hidden', '');
        }
    }

    // Tile action buttons
    const chestBtn = document.getElementById('dungeon-open-chest');
    const riddleBtn = document.getElementById('dungeon-answer-riddle');
    const hintBtn = nav.querySelector('[data-dungeon-action="riddle_hint"]');
    const riddlePanel = document.getElementById('dungeon-riddle-panel');

    // Chest lives in content.items as {type:'chest'} (backend never set content.chest → button never showed).
    const chestState = currentNode.chest_state || {};
    const hasChestItem = (content.items || []).some(i => String(i.type || '').toLowerCase() === 'chest');
    const hasChest = hasChestItem && !chestState.opened && !chestState.locked_forever;
    // #745: check riddle.solved (set by backend on correct answer) and riddle_state.failed_permanently
    // cleared is only set on room exit, not on riddle solve — cannot rely on it alone
    const riddleState = currentNode.riddle_state || {};
    const hasRiddle = content.riddle && !content.riddle?.solved && !riddleState.failed_permanently && !currentNode.cleared;

    if (chestBtn) chestBtn.hidden = !hasChest;
    if (riddleBtn) riddleBtn.hidden = !hasRiddle;
    if (hintBtn) hintBtn.hidden = !hasRiddle;

    // LB1 (#735): rest on a SAFE (cleared) combat tile — tile became safe after the
    // enemies were defeated. Backend gates the actual heal/charges per dungeon flag.
    const restBtn = document.getElementById('dungeon-rest');
    const restPill = document.getElementById('dungeon-rest-pill');
    const canRest = (content.enemies?.length > 0) && !!currentNode?.cleared;
    if (restBtn) restBtn.hidden = !canRest;
    if (restPill) restPill.hidden = !canRest;

    // Riddle panel (text input for answer)
    if (hasRiddle) {
        if (riddlePanel) {
            riddlePanel.removeAttribute('hidden');
            const txt = document.getElementById('dungeon-riddle-text');
            if (txt) txt.textContent = content.riddle?.text || content.riddle || '…';
            const hint = document.getElementById('dungeon-riddle-hint');
            if (hint) { hint.textContent = ''; hint.setAttribute('hidden', ''); }
        }
    } else {
        riddlePanel?.setAttribute('hidden', '');
    }
}

async function _dungeonMove(direction) {
    if (!_dungeonCampaignId || !characterData?.id) return;
    // Disable all dir buttons during request
    document.querySelectorAll('[data-dungeon-dir]').forEach(b => b.disabled = true);
    try {
        const resp = await apiRequest('POST', '/dungeons/move', {
            campaign_id: _dungeonCampaignId,
            character_id: characterData.id,
            direction,
        });

        if (!resp.ok) {
            showToast(resp.reason || `Brak drzwi ${direction}`, 'warning');
            return;
        }

        if (resp.dungeon_run) _activeDungeonRun = resp.dungeon_run;

        if (resp.narrative) {
            appendMessage({ role: 'assistant', content: resp.narrative, created_at: new Date() });
            scrollToBottom();
        }

        // The move endpoint returns the destination node but NOT the whole run, so
        // patch our local run so HUD/nav reflect the tile we just stepped onto.
        if (_activeDungeonRun?.graph?.nodes && resp.node_id && characterData?.id) {
            _activeDungeonRun.positions = _activeDungeonRun.positions || {};
            _activeDungeonRun.positions[String(characterData.id)] = resp.node_id;
            if (resp.node) _activeDungeonRun.graph.nodes[resp.node_id] = resp.node;
        }

        if (resp.completed || _activeDungeonRun?.completed) {
            _showDungeonComplete(resp);
        } else {
            updateDungeonHUD();
            // #687: refresh the D-pad/action cluster for the NEW tile — hides it when
            // the move lands on a combat tile (else it overlaps the combat controls)
            // and drops the stale chest/riddle button from the previous room.
            updateDungeonNav(_activeDungeonRun);
            // Auto-open map on first move
            const visitedCount = Object.values(_activeDungeonRun?.graph?.nodes || {}).filter(n => n.visited).length;
            if (visitedCount === 2) openDungeonMap(true);
        }

        // If combat started, refresh combat state
        if (resp.combat) {
            const campResp = await apiRequest('GET', `/campaigns/${_dungeonCampaignId}`);
            if (campResp?.campaign) {
                currentCampaignId = campResp.campaign.id;
                await loadCombatState();
            }
        }
    } catch (err) {
        showToast(err.message || 'Błąd ruchu', 'error');
    } finally {
        document.querySelectorAll('[data-dungeon-dir]').forEach(b => b.disabled = false);
    }
}

async function _dungeonResolveTile(action, payload) {
    if (!_dungeonCampaignId || !characterData?.id) return;
    try {
        const resp = await apiRequest('POST', '/dungeons/resolve-tile', {
            campaign_id: _dungeonCampaignId,
            character_id: characterData.id,
            action,
            payload: payload || null,
        });

        if (resp.narrative) {
            appendMessage({ role: 'assistant', content: resp.narrative, created_at: new Date() });
            scrollToBottom();
        }

        if (resp.hint) {
            const hintEl = document.getElementById('dungeon-riddle-hint');
            if (hintEl) { hintEl.textContent = `💡 ${resp.hint}`; hintEl.removeAttribute('hidden'); }
        }

        // #745: immediately hide riddle panel on solve/fail before reload to avoid flicker
        if (action === 'answer_riddle' && (resp.solved || resp.failed_permanently)) {
            document.getElementById('dungeon-riddle-panel')?.setAttribute('hidden', '');
        }

        // Reload run to get updated node state
        const runResp = await apiRequest('GET', `/campaigns/${_dungeonCampaignId}/dungeon-run`);
        if (runResp?.dungeon_run) _activeDungeonRun = runResp.dungeon_run;
        updateDungeonHUD();

        if (resp.heal_amount && resp.heal_amount > 0) {
            await refreshCharacterData();
        }
        if (resp.loot?.length) {
            await refreshCharacterData();
        }
        // LB1 (#735): rest on cleared tile — refresh HP, surface hp_after + onboarding note.
        if (action === 'rest') {
            if (resp.blocked) {
                showToast(resp.narrative || 'Najpierw pokonaj wrogów.', 'warning');
            } else if (resp.no_charges) {
                showToast('Brak sił na kolejny odpoczynek w tym lochu.', 'warning');
            } else {
                await refreshCharacterData();
                updateDungeonNav(_activeDungeonRun);
                const hpTxt = (typeof resp.hp_after === 'number') ? ` — HP: ${resp.hp_after}` : '';
                showToast(`🕯 Odpoczynek${hpTxt}`, 'success');
                if (resp.onboarding_note) {
                    showToast('Pełny odpoczynek to wyjątek lochu wprowadzającego — w głębszych lochach radzisz sobie sam.', 'info');
                }
            }
        }
        // L12b: chest → play the dice animation (like skill tests/combat), then result modal.
        if (action === 'open_chest') {
            if (typeof resp.roll === 'number' && typeof playCombatDiceRoll === 'function') {
                const dex = resp.dex_mod ?? 0;
                const parts = [{ label: 'k20', value: resp.roll }];
                if (dex) parts.push({ label: 'DEX', value: dex });
                try { await playCombatDiceRoll(resp.roll, 'Skrzynia (DEX)', { parts, total: resp.total }); } catch (_) {}
            }
            if (resp.trap?.triggered) await refreshCharacterData();  // trap dealt HP damage
            showChestResultModal(resp);
        }
    } catch (err) {
        showToast(err.message || 'Błąd akcji', 'error');
    }
}

// L12b (#696): chest open result — shows the DEX roll, granted loot and any trap.
function showChestResultModal(resp) {
    const overlay = document.createElement('div');
    overlay.className = 'dtile-modal';
    const loot = Array.isArray(resp.loot) ? resp.loot : [];
    const success = !!resp.success;
    const rollLine = (typeof resp.roll === 'number')
        ? `🎲 d20: ${resp.roll} ${(resp.dex_mod >= 0 ? '+' : '')}${resp.dex_mod ?? 0} = ${resp.total} vs DC ${resp.dc}`
        : '';
    let body;
    if (resp.chest_locked_forever && !success) {
        body = '<p class="dchest__fail">🔒 Mechanizm zablokował skrzynię na zawsze.</p>';
    } else if (success) {
        body = loot.length
            ? '<ul class="dchest__loot">' + loot.map(l =>
                `<li>📦 ${escapeHtml(l.label || l.key || '?')} ×${l.quantity || 1}</li>`).join('') + '</ul>'
            : '<p class="dchest__empty">Skrzynia była pusta.</p>';
    } else {
        const left = (resp.max_attempts ?? 3) - (resp.attempt ?? 0);
        body = `<p class="dchest__fail">Nie udało się otworzyć. Pozostało prób: ${Math.max(0, left)}.</p>`;
    }
    const trap = resp.trap?.triggered
        ? `<p class="dchest__trap">⚠️ Pułapka! ${escapeHtml(resp.trap.description || '')} (−${resp.trap.damage} HP)</p>`
        : '';
    overlay.innerHTML = `
        <div class="dtile-modal__box">
            <button type="button" class="dtile-modal__close">✕</button>
            <div class="dtile-modal__name">${success ? '🪙 Skrzynia otwarta' : '🪙 Skrzynia'}</div>
            ${rollLine ? `<div class="dchest__roll">${escapeHtml(rollLine)}</div>` : ''}
            ${body}
            ${trap}
        </div>`;
    const close = () => overlay.remove();
    overlay.querySelector('.dtile-modal__close').addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    document.body.appendChild(overlay);
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

    // L13: if mid-segment (not at checkpoint, not completed), show abandon confirmation modal
    const run = _activeDungeonRun;
    const atCheckpoint = run?.at_checkpoint || false;
    const isCompleted = run?.completed || false;
    if (run && !isCompleted && !atCheckpoint) {
        showDungeonAbandonModal();
        return;
    }

    await _doExitDungeon();
}

async function _doExitDungeon() {
    // #699: abandon from the resume modal never loads characterData (we are still
    // in the picker, hero not yet bound to the session). Prefer the run's own hero,
    // then the selected currentHero — characterData may be STALE from a previously
    // open campaign, which would apply restore+cooldown to the WRONG hero. Only
    // fall back to characterData last (the in-dungeon abandon path sets it correctly).
    const _runCharId = _activeDungeonRun?.character_id
        || Object.keys(_activeDungeonRun?.positions || {})[0]
        || null;
    const _exitCharId = _runCharId || currentHero?.id || characterData?.id || null;
    if (!_dungeonCampaignId || !_exitCharId) { showScreen('campaigns'); return; }
    try {
        const resp = await apiRequest('POST', '/dungeons/exit', {
            campaign_id: _dungeonCampaignId,
            character_id: _exitCharId,
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
        document.getElementById('dungeon-abandon-modal')?.setAttribute('hidden', '');
        document.getElementById('dungeon-riddle-panel')?.setAttribute('hidden', '');
        document.getElementById('dungeon-nav')?.setAttribute('hidden', '');
        document.getElementById('dungeon-tile-modal')?.setAttribute('hidden', '');
        _dungeonSeenTiles = new Set();
        // Reload hero and go to campaign screen
        if (currentHero?.id) {
            const heroResp = await apiRequest('GET', `/characters/${currentHero.id}`);
            currentHero = heroResp.character || heroResp;
        }
        await loadCampaigns();
        // #752: auto-return to the campaign we came from before the dungeon.
        // Backend re-links the hero to it (relinked_campaign_id); fall back to the
        // stored previous_campaign_id if the re-link was skipped.
        const _prevId = resp.relinked_campaign_id || resp.previous_campaign_id;
        if (_prevId) {
            try {
                const listResp = await apiRequest('GET', '/campaigns');
                const list = listResp.campaigns || (Array.isArray(listResp) ? listResp : []);
                const prevCamp = list.find(c => Number(c.id) === Number(_prevId));
                if (prevCamp) {
                    await selectCampaign(prevCamp);
                    return;
                }
            } catch (e) { console.warn('[Dungeon] auto-return failed', e); }
        }
        showScreen('campaigns');
    } catch (err) {
        showToast(err.message || 'Błąd', 'error');
        showScreen('campaigns');
    }
}

// ── L13 (#682): Dungeon Modals ────────────────────────────────────────────────

async function showDungeonDeathModal() {
    // Call backend to restore checkpoint and set cooldown
    let deathResult = { restored: false, cooldown_until: null };
    try {
        deathResult = await apiRequest('POST', '/dungeons/death', {
            campaign_id: _dungeonCampaignId,
            character_id: characterData?.id,
        });
        // Reload hero data after restore
        if (deathResult.restored && currentHero?.id) {
            const heroResp = await apiRequest('GET', `/characters/${currentHero.id}`);
            currentHero = heroResp.character || heroResp;
            characterData = currentHero;
        }
    } catch (_) { /* show modal anyway */ }

    const modal = document.getElementById('dungeon-death-modal');
    if (!modal) return;

    const checkpointMsg = document.getElementById('dungeon-death-checkpoint-msg');
    const xpMsg = document.getElementById('dungeon-death-xp-msg');
    const cooldownMsg = document.getElementById('dungeon-death-cooldown-msg');

    if (checkpointMsg) {
        const run = _activeDungeonRun;
        const hasCheckpoint = Array.isArray(run?.checkpoints) && run.checkpoints.length > 1;
        checkpointMsg.textContent = hasCheckpoint
            ? 'Stan przywrócony do ostatniego bossa (punkt kontrolny).'
            : 'Stan przywrócony do momentu wejścia do lochu.';
    }
    if (xpMsg) {
        xpMsg.textContent = 'XP i złoto zdobyte po punkcie kontrolnym utracone.';
    }
    if (cooldownMsg && deathResult.cooldown_until) {
        const until = new Date(deathResult.cooldown_until);
        const hours = Math.round((until - Date.now()) / 3600000);
        cooldownMsg.textContent = `Cooldown lochu: ${hours > 0 ? hours + 'h' : 'zakończony'}.`;
    } else if (cooldownMsg) {
        cooldownMsg.textContent = '';
    }

    modal.removeAttribute('hidden');
    document.getElementById('dungeon-death-exit-btn')?.focus();
}

function showDungeonAbandonModal() {
    const modal = document.getElementById('dungeon-abandon-modal');
    if (!modal) return;

    const run = _activeDungeonRun;
    const dungeon = run?.dungeon_label || run?.dungeon_key || 'lochu';
    const msg = document.getElementById('dungeon-abandon-msg');
    if (msg) msg.textContent = `Opuszczasz ${escapeHtml(dungeon)} w połowie segmentu.`;

    modal.removeAttribute('hidden');
    document.getElementById('dungeon-abandon-cancel-btn')?.focus();
}

function showDungeonResumeModal(activeRun) {
    const modal = document.getElementById('dungeon-resume-modal');
    if (!modal) return;

    const nameEl = document.getElementById('dungeon-resume-dungeon-name');
    const roomEl = document.getElementById('dungeon-resume-room-msg');

    if (nameEl) nameEl.textContent = activeRun.dungeon_label || activeRun.dungeon_key || 'Loch';
    if (roomEl) {
        const room = activeRun.current_room || 1;
        const total = Object.keys(activeRun.graph?.nodes || {}).length || '?';
        roomEl.textContent = `Komnata ${room} z ${total} — niedokończona wyprawa.`;
    }

    modal.removeAttribute('hidden');
    document.getElementById('dungeon-resume-continue-btn')?.focus();
}

function showDungeonBossChoiceModal(run) {
    const modal = document.getElementById('dungeon-boss-modal');
    if (!modal) return;

    const lootEl = document.getElementById('dungeon-boss-loot');
    const cycleEl = document.getElementById('dungeon-boss-cycle-msg');

    // Boss loot from last checkpoint
    const lastCheckpoint = (run?.checkpoints || []).slice(-1)[0];
    const loot = lastCheckpoint?.loot || [];
    if (lootEl) {
        lootEl.innerHTML = loot.length
            ? '<ul>' + loot.map(l => `<li>👑 ${escapeHtml(l.label || l.key || '?')} ×${l.quantity || 1}</li>`).join('') + '</ul>'
            : '<p>Łupy zostaną przyznane przy wyjściu.</p>';
    }

    const cycle = run?.current_cycle || 1;
    if (cycleEl) {
        cycleEl.textContent = `Możesz zejść głębiej — Cykl ${cycle + 1} (silniejsi wrogowie, lepsze łupy).`;
    }

    modal.removeAttribute('hidden');
    document.getElementById('dungeon-boss-exit-btn')?.focus();
}

function _closeDungeonModals() {
    ['dungeon-death-modal', 'dungeon-abandon-modal', 'dungeon-resume-modal', 'dungeon-boss-modal']
        .forEach(id => document.getElementById(id)?.setAttribute('hidden', ''));
}

// ── Dungeon Map v2 (tile graph) — L11 ────────────────────────────────────────

const ROOM_TYPE_LABELS = {
    combat: 'Walka', boss: 'BOSS', riddle: 'Zagadka',
    trap: 'Pułapka', chest: 'Skrzynia', rest: 'Odpoczynek'
};

// Direction offsets: N/S/E/W → [dcol, drow]
const _DIR_OFFSET = { N: [0, -1], S: [0, 1], E: [1, 0], W: [-1, 0] };

// Pan/zoom state for dungeon map overlay
const _dmap = { zoom: 1, pan: { x: 0, y: 0 }, dragging: false, lastX: 0, lastY: 0 };

function renderDungeonMap(run) {
    const svg = document.getElementById('dmap-svg');
    if (!svg || !run) return;

    // v2 graph format (L2)
    const graph = run.graph || {};
    const nodes = graph.nodes || {};
    const entryNode = graph.entry_node;

    // Current player node from positions dict (first value = solo player)
    const positions = run.positions || {};
    const currentNodeId = Object.values(positions)[0] || entryNode;

    if (!Object.keys(nodes).length) {
        svg.innerHTML = '<text x="50%" y="50%" text-anchor="middle" fill="#6a5a30" font-size="12">Brak danych mapy</text>';
        return;
    }

    // Grid metrics — Numbers Policy (L11 starting values, tuning after L19 playtest)
    const S = 52;           // tile size px
    const GAP = 28;         // corridor length px
    const PAD = 32;         // padding px
    const R = 8;            // corner radius px
    const STEP = S + GAP;

    // Determine which nodes to render:
    // - visited=true  → known tile (draw with image or colored box)
    // - fog           → unvisited node referenced by a visited node's doors_open
    const visitedIds = new Set(
        Object.entries(nodes).filter(([, n]) => n.visited).map(([id]) => id)
    );
    const fogIds = new Set();
    for (const [nid, node] of Object.entries(nodes)) {
        if (!node.visited) continue;
        for (const neighborId of Object.values(node.doors_open || {})) {
            if (neighborId && !visitedIds.has(neighborId)) fogIds.add(neighborId);
        }
    }

    const drawIds = new Set([...visitedIds, ...fogIds]);

    // Compute grid bounds
    let minCol = Infinity, maxCol = -Infinity, minRow = Infinity, maxRow = -Infinity;
    for (const nid of drawIds) {
        const pos = nodes[nid]?.position;
        if (!pos) continue;
        minCol = Math.min(minCol, pos[0]);
        maxCol = Math.max(maxCol, pos[0]);
        minRow = Math.min(minRow, pos[1]);
        maxRow = Math.max(maxRow, pos[1]);
    }
    if (!isFinite(minCol)) { minCol = 0; maxCol = 0; minRow = 0; maxRow = 0; }

    const svgW = (maxCol - minCol + 1) * STEP + GAP + PAD * 2;
    const svgH = (maxRow - minRow + 1) * STEP + GAP + PAD * 2;

    const tileX = (col) => PAD + (col - minCol) * STEP;
    const tileY = (row) => PAD + (maxRow - row) * STEP;
    const cxFn  = (col) => tileX(col) + S / 2;
    const cyFn  = (row) => tileY(row) + S / 2;

    let html = '';

    // ── Corridors (drawn first, behind tiles) ────────────────────────────────
    const drawnCorridors = new Set();
    for (const [nid, node] of Object.entries(nodes)) {
        if (!drawIds.has(nid) || !node.visited) continue;
        const pos = node.position;
        if (!pos) continue;
        for (const [dir, neighborId] of Object.entries(node.doors_open || {})) {
            if (!neighborId || !drawIds.has(neighborId)) continue;
            const key = [nid, neighborId].sort().join('|');
            if (drawnCorridors.has(key)) continue;
            drawnCorridors.add(key);

            const nPos = nodes[neighborId]?.position;
            if (!nPos) continue;

            const x1 = cxFn(pos[0]);
            const y1 = cyFn(pos[1]);
            const x2 = cxFn(nPos[0]);
            const y2 = cyFn(nPos[1]);
            const neighborVisited = visitedIds.has(neighborId);
            const opacity = neighborVisited ? 0.65 : 0.3;

            html += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"
                stroke="#5a3818" stroke-width="4" opacity="${opacity}"/>`;
        }
    }

    // ── Tiles ────────────────────────────────────────────────────────────────
    const imagesHtml = [];  // collect image elements (drawn after rects, before text)

    for (const nid of drawIds) {
        const node = nodes[nid];
        if (!node?.position) continue;

        const [col, row] = node.position;
        const x = tileX(col);
        const y = tileY(row);
        const isCurrent = nid === currentNodeId;
        const isVisited = visitedIds.has(nid);
        const isFog = fogIds.has(nid);
        const isCleared = node.cleared;
        const isBoss = node.is_boss;
        const content = node.content || {};
        const imageUrl = content.image_url;

        if (isVisited) {
            // ── Known room ───────────────────────────────────────────────────
            let fill, stroke, strokeW, textColor;
            if (isCurrent) {
                fill = '#1a1005'; stroke = '#c9751a'; strokeW = 2.5; textColor = '#d4a060';
            } else if (isCleared) {
                fill = '#100e08'; stroke = '#3a2808'; strokeW = 1; textColor = '#5a4a28';
            } else {
                fill = '#0f0c06'; stroke = '#3a2808'; strokeW = 1.5; textColor = '#b89050';
            }
            if (isBoss) { stroke = '#8a2010'; fill = '#140802'; }

            // Glow ring for current node
            if (isCurrent) {
                html += `<rect x="${x - 3}" y="${y - 3}" width="${S + 6}" height="${S + 6}" rx="${R + 3}"
                    fill="none" stroke="#c9751a" stroke-width="1" opacity="0.3"/>`;
            }

            // Background rect (always drawn; image renders on top if available)
            html += `<rect x="${x}" y="${y}" width="${S}" height="${S}" rx="${R}"
                fill="${fill}" stroke="${stroke}" stroke-width="${strokeW}"/>`;

            if (imageUrl) {
                // Clip image to rounded rect
                const clipId = `clip-${nid.replace(/[^a-zA-Z0-9]/g, '_')}`;
                html += `<defs><clipPath id="${clipId}"><rect x="${x}" y="${y}" width="${S}" height="${S}" rx="${R}"/></clipPath></defs>`;
                imagesHtml.push(`<image href="${escapeHtml(imageUrl)}" x="${x}" y="${y}" width="${S}" height="${S}"
                    clip-path="url(#${clipId})" preserveAspectRatio="xMidYMid slice" opacity="${isCleared ? 0.6 : 1}"/>`);
                // Dark overlay for cleared rooms so icon/text visible
                if (isCleared) {
                    imagesHtml.push(`<rect x="${x}" y="${y}" width="${S}" height="${S}" rx="${R}"
                        fill="rgba(0,0,0,0.35)" clip-path="url(#${clipId})"/>`);
                }
            } else {
                // Fallback: icon
                const icon = isBoss ? '💀' : (ROOM_TYPE_ICONS[content.enemies?.length ? 'combat' : (content.riddle ? 'riddle' : 'rest')] || '●');
                html += `<text x="${cxFn(col)}" y="${cyFn(row) - 4}" text-anchor="middle"
                    dominant-baseline="middle" font-size="18" style="pointer-events:none">${icon}</text>`;
            }

            // Label at bottom
            const labelStr = isBoss ? 'BOSS' : (ROOM_TYPE_LABELS[content.enemies?.length ? 'combat' : (content.riddle ? 'riddle' : 'rest')] || '');
            html += `<text x="${cxFn(col)}" y="${y + S - 9}" text-anchor="middle"
                font-size="7" fill="${textColor}" font-family="sans-serif"
                style="pointer-events:none;text-transform:uppercase;letter-spacing:0.06em">${escapeHtml(labelStr)}</text>`;

            // Cleared checkmark
            if (isCleared && !isCurrent) {
                html += `<text x="${x + S - 9}" y="${y + 13}" text-anchor="middle"
                    font-size="9" fill="#5a9040" style="pointer-events:none">✓</text>`;
            }

            // Player marker 📍
            if (isCurrent) {
                html += `<text x="${cxFn(col)}" y="${cyFn(row) + (imageUrl ? 8 : 4)}" text-anchor="middle"
                    font-size="16" style="pointer-events:none">📍</text>`;
            }

            // L12b (#694): transparent hit-rect on top → click opens tile image popup
            if (imageUrl) {
                imagesHtml.push(`<rect x="${x}" y="${y}" width="${S}" height="${S}" rx="${R}"
                    fill="transparent" data-node-id="${escapeHtml(nid)}" style="cursor:pointer"/>`);
            }

        } else if (isFog) {
            // ── Fog node: outline + "?" ──────────────────────────────────────
            // Find door hint from the visited neighbor
            let hint = '';
            for (const [vnid, vnode] of Object.entries(nodes)) {
                if (!visitedIds.has(vnid)) continue;
                for (const [dir, nbId] of Object.entries(vnode.doors_open || {})) {
                    if (nbId === nid) {
                        hint = vnode.door_hints?.[dir] || '';
                        break;
                    }
                }
                if (hint) break;
            }

            html += `<rect x="${x}" y="${y}" width="${S}" height="${S}" rx="${R}"
                fill="#0a0805" stroke="#2a2010" stroke-width="1" opacity="0.7"
                stroke-dasharray="4,3">
                ${hint ? `<title>${escapeHtml(hint)}</title>` : ''}
            </rect>`;
            html += `<text x="${cxFn(col)}" y="${cyFn(row)}" text-anchor="middle"
                dominant-baseline="middle" font-size="20" fill="#3a3020"
                style="pointer-events:none">?</text>`;
        }
    }

    // Compose SVG: lines → rects (html) → images → player
    html = html + imagesHtml.join('');

    // Wrap in pannable/zoomable <g>
    const tx = _dmap.pan.x;
    const ty = _dmap.pan.y;
    const z  = _dmap.zoom;
    svg.setAttribute('viewBox', `0 0 ${svgW} ${svgH}`);
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '100%');
    svg.setAttribute('data-map-w', svgW);
    svg.setAttribute('data-map-h', svgH);
    svg.innerHTML = `<g id="dmap-g" transform="translate(${tx},${ty}) scale(${z})">${html}</g>`;

    // Reset pan/zoom when freshly opened (map changed size)
    _dmap._lastSvgW = svgW;
}

function _dmapResetView() {
    _dmap.zoom = 1;
    _dmap.pan = { x: 0, y: 0 };
}

function openDungeonMap(autoClose = false) {
    const overlay = document.getElementById('dungeon-map-overlay');
    if (!overlay) return;
    _dmapResetView();
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
    // L12: direction buttons
    document.querySelectorAll('[data-dungeon-dir]').forEach(btn => {
        btn.addEventListener('click', () => {
            const dir = btn.dataset.dungeonDir;
            if (dir) _dungeonMove(dir);
        });
    });

    // L12: tile action buttons
    document.getElementById('dungeon-open-chest')?.addEventListener('click', () => {
        _dungeonResolveTile('open_chest');
    });
    document.getElementById('dungeon-answer-riddle')?.addEventListener('click', () => {
        const riddleInput = document.getElementById('dungeon-riddle-input');
        const answer = riddleInput?.value.trim();
        if (!answer) { showToast('Wpisz odpowiedź w polu poniżej', 'info'); return; }
        if (riddleInput) riddleInput.value = '';
        _dungeonResolveTile('answer_riddle', { answer });
    });
    document.querySelector('[data-dungeon-action="riddle_hint"]')?.addEventListener('click', () => {
        _dungeonResolveTile('riddle_hint');
    });
    // LB1 (#735): rest on cleared tile
    document.getElementById('dungeon-rest')?.addEventListener('click', () => {
        _dungeonResolveTile('rest');
    });

    document.getElementById('dungeon-advance-btn')?.addEventListener('click', () => {
        // Legacy: advance-btn no longer used in v2 but kept for safety
    });
    document.getElementById('dungeon-exit-btn')?.addEventListener('click', _exitDungeon);
    document.getElementById('dungeon-complete-btn')?.addEventListener('click', _exitDungeon);
    document.getElementById('dungeon-map-btn')?.addEventListener('click', () => openDungeonMap());
    document.getElementById('dmap-close-btn')?.addEventListener('click', closeDungeonMap);

    // L12b (#694): tile image popup — close on ✕ or tap outside box
    document.getElementById('dungeon-tile-modal-close')?.addEventListener('click', closeTileImageModal);
    document.getElementById('dungeon-tile-modal')?.addEventListener('click', (e) => {
        if (e.target === document.getElementById('dungeon-tile-modal')) closeTileImageModal();
    });
    document.getElementById('dungeon-room-view-btn')?.addEventListener('click', showCurrentTileImageModal);

    // L12b: click a visited tile on the map → open its image popup
    document.getElementById('dmap-svg')?.addEventListener('click', (e) => {
        const g = e.target.closest('[data-node-id]');
        if (!g) return;
        const nid = g.getAttribute('data-node-id');
        const node = _activeDungeonRun?.graph?.nodes?.[nid];
        if (node?.content?.image_url) showTileImageModal(node);
    });

    // L13 (#682): dungeon modal buttons
    document.getElementById('dungeon-death-exit-btn')?.addEventListener('click', async () => {
        document.getElementById('dungeon-death-modal')?.setAttribute('hidden', '');
        await _doExitDungeon();
    });
    document.getElementById('dungeon-abandon-confirm-btn')?.addEventListener('click', async () => {
        document.getElementById('dungeon-abandon-modal')?.setAttribute('hidden', '');
        await _doExitDungeon();
    });
    document.getElementById('dungeon-abandon-cancel-btn')?.addEventListener('click', () => {
        document.getElementById('dungeon-abandon-modal')?.setAttribute('hidden', '');
    });
    document.getElementById('dungeon-boss-exit-btn')?.addEventListener('click', async () => {
        document.getElementById('dungeon-boss-modal')?.setAttribute('hidden', '');
        if (!_dungeonCampaignId || !characterData?.id) return;
        try {
            await apiRequest('POST', '/dungeons/boss-choice', {
                campaign_id: _dungeonCampaignId,
                character_id: characterData.id,
                choice: 'exit',
            });
        } catch (_) { /* still exit */ }
        await _doExitDungeon();
    });
    document.getElementById('dungeon-boss-deeper-btn')?.addEventListener('click', async () => {
        document.getElementById('dungeon-boss-modal')?.setAttribute('hidden', '');
        if (!_dungeonCampaignId || !characterData?.id) return;
        try {
            const resp = await apiRequest('POST', '/dungeons/boss-choice', {
                campaign_id: _dungeonCampaignId,
                character_id: characterData.id,
                choice: 'go_deeper',
            });
            if (resp.ok) {
                showToast(`Schodzisz głębiej — Cykl ${resp.new_cycle}`, 'info', 3000);
                // Reload run and refresh HUD/map
                const runResp = await apiRequest('GET', `/campaigns/${_dungeonCampaignId}/dungeon-run`);
                if (runResp?.dungeon_run) _activeDungeonRun = runResp.dungeon_run;
                updateDungeonHUD();
                if (resp.narrative) {
                    appendMessage({ role: 'assistant', content: resp.narrative, created_at: new Date() });
                    scrollToBottom();
                }
            }
        } catch (err) {
            showToast(err.message || 'Błąd', 'error');
        }
    });
    document.getElementById('dungeon-map-overlay')?.addEventListener('click', (e) => {
        if (e.target === document.getElementById('dungeon-map-overlay')) closeDungeonMap();
    });

    // Pan/zoom on dmap-svg (L11)
    const dmapSvg = document.getElementById('dmap-svg');
    if (dmapSvg) {
        dmapSvg.addEventListener('wheel', (e) => {
            e.preventDefault();
            const factor = e.deltaY < 0 ? 1.15 : (1 / 1.15);
            _dmap.zoom = Math.min(4, Math.max(0.4, _dmap.zoom * factor));
            renderDungeonMap(_activeDungeonRun);
        }, { passive: false });

        dmapSvg.addEventListener('mousedown', (e) => {
            _dmap.dragging = true; _dmap.lastX = e.clientX; _dmap.lastY = e.clientY;
            dmapSvg.style.cursor = 'grabbing';
        });
        window.addEventListener('mouseup', () => {
            _dmap.dragging = false; dmapSvg.style.cursor = '';
        });
        window.addEventListener('mousemove', (e) => {
            if (!_dmap.dragging) return;
            _dmap.pan.x += (e.clientX - _dmap.lastX) / _dmap.zoom;
            _dmap.pan.y += (e.clientY - _dmap.lastY) / _dmap.zoom;
            _dmap.lastX = e.clientX; _dmap.lastY = e.clientY;
            renderDungeonMap(_activeDungeonRun);
        });

        // Touch pan (mobile)
        let _touchStart = null;
        dmapSvg.addEventListener('touchstart', (e) => {
            if (e.touches.length === 1) _touchStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        }, { passive: true });
        dmapSvg.addEventListener('touchmove', (e) => {
            if (e.touches.length === 1 && _touchStart) {
                const dx = e.touches[0].clientX - _touchStart.x;
                const dy = e.touches[0].clientY - _touchStart.y;
                _dmap.pan.x += dx / _dmap.zoom;
                _dmap.pan.y += dy / _dmap.zoom;
                _touchStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                renderDungeonMap(_activeDungeonRun);
            }
        }, { passive: true });
    }

    // L12: click-to-move on SVG map nodes — find closest direction from current node
    if (dmapSvg) {
        dmapSvg.addEventListener('click', (e) => {
            if (_dmap.dragging) return;
            const run = _activeDungeonRun;
            if (!run) return;
            const charId = characterData?.id;
            const positions = run.positions || {};
            const currentNodeId = (charId && positions[String(charId)]) || run.graph?.entry_node;
            const currentNode = run.graph?.nodes?.[currentNodeId];
            if (!currentNode) return;

            // Find which node was clicked by position proximity (SVG coordinate hit)
            const svgRect = dmapSvg.getBoundingClientRect();
            const svgW = parseFloat(dmapSvg.getAttribute('data-map-w') || 0);
            const svgH = parseFloat(dmapSvg.getAttribute('data-map-h') || 0);
            if (!svgW || !svgH) return;
            const scaleX = svgW / svgRect.width;
            const scaleY = svgH / svgRect.height;
            const clickSvgX = (e.clientX - svgRect.left) * scaleX / _dmap.zoom - _dmap.pan.x;
            const clickSvgY = (e.clientY - svgRect.top) * scaleY / _dmap.zoom - _dmap.pan.y;

            const S = 52; const GAP = 28; const PAD = 32; const STEP = S + GAP;
            const nodes = run.graph.nodes || {};
            const drawIds = Object.entries(nodes).filter(([, n]) => n.visited || Object.values(n.doors_open || {}).some(id => nodes[id]?.visited)).map(([id]) => id);
            const positions2 = Object.values(nodes).filter(n => n.position).map(n => n.position);
            const minCol = positions2.length ? Math.min(...positions2.map(p => p[0])) : 0;
            const minRow = positions2.length ? Math.min(...positions2.map(p => p[1])) : 0;
            const maxRow = positions2.length ? Math.max(...positions2.map(p => p[1])) : 0;

            let closestDir = null;
            let closestDist = 9999;
            for (const [dir, targetId] of Object.entries(currentNode.doors_open || {})) {
                const tn = nodes[targetId];
                if (!tn?.position) continue;
                const tx = PAD + (tn.position[0] - minCol) * STEP + S / 2;
                const ty = PAD + (maxRow - tn.position[1]) * STEP + S / 2;
                const dist = Math.hypot(clickSvgX - tx, clickSvgY - ty);
                if (dist < closestDist && dist < S) {
                    closestDist = dist; closestDir = dir;
                }
            }
            if (closestDir) {
                closeDungeonMap();
                _dungeonMove(closestDir);
            }
        });
    }

    // Riddle submit
    const riddleInput = document.getElementById('dungeon-riddle-input');
    document.getElementById('dungeon-riddle-submit')?.addEventListener('click', () => {
        const val = riddleInput?.value.trim();
        if (!val) return;
        if (riddleInput) riddleInput.value = '';
        _dungeonResolveTile('answer_riddle', { answer: val });
    });
    riddleInput?.addEventListener('keypress', e => {
        if (e.key === 'Enter') {
            const val = riddleInput.value.trim();
            if (!val) return;
            riddleInput.value = '';
            _dungeonResolveTile('answer_riddle', { answer: val });
        }
    });
    document.getElementById('dungeon-riddle-hint-btn')?.addEventListener('click', () => {
        _dungeonResolveTile('riddle_hint');
    });
}

// ── Custom DELETE hero confirmation modal ────────────────────────────────────

function showDeleteCampaignModal(campaignTitle) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'delete-modal-overlay';
    overlay.innerHTML = `
      <div class="delete-modal" role="dialog" aria-modal="true">
        <div class="delete-modal__header">
          <span class="delete-modal__icon">🗑</span>
          <span class="delete-modal__title">Usuń kampanię</span>
        </div>
        <div class="delete-modal__body">
          <div class="delete-modal__hero-name">${escapeHtml(campaignTitle)}</div>
          <p class="delete-modal__desc">
            Kampania zostanie trwale usunięta.<br>
            Bohater pozostanie — kampania jest tylko odłączana.<br>
            Tej operacji nie można cofnąć.
          </p>
        </div>
        <div class="delete-modal__footer">
          <button class="delete-modal__btn delete-modal__btn--cancel" id="del-campaign-cancel">Anuluj</button>
          <button class="delete-modal__btn delete-modal__btn--confirm" id="del-campaign-confirm">Usuń kampanię</button>
        </div>
      </div>`;

    document.body.appendChild(overlay);
    const confirmBtn = overlay.querySelector('#del-campaign-confirm');
    const cancelBtn = overlay.querySelector('#del-campaign-cancel');

    confirmBtn.addEventListener('click', () => { overlay.remove(); resolve(true); });
    cancelBtn.addEventListener('click', () => { overlay.remove(); resolve(false); });
    overlay.addEventListener('click', e => { if (e.target === overlay) { overlay.remove(); resolve(false); } });
    overlay.addEventListener('keydown', e => { if (e.key === 'Escape') { overlay.remove(); resolve(false); } });
  });
}

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

// ── #593 — Web Push: service worker + subscription flow ─────────────────────
function _urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
}

function _setPushStatus(msg) {
    const el = document.getElementById('push-status');
    if (el) el.textContent = msg || '';
}

async function _registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return null;
    try {
        return await navigator.serviceWorker.register('/sw.js');
    } catch (e) {
        console.warn('[push] SW register failed', e);
        return null;
    }
}

async function enablePushNotifications() {
    const btn = document.getElementById('enable-push-btn');
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
        _setPushStatus('Twoja przeglądarka nie obsługuje powiadomień push.');
        return;
    }

    // CRITICAL (#593): requestPermission() MUST run synchronously inside the click
    // gesture — BEFORE any `await`. An await first consumes the user-activation and
    // many browsers (esp. mobile Safari/Chrome) then silently suppress the prompt.
    let permPromise;
    if (Notification.permission === 'granted') {
        permPromise = Promise.resolve('granted');
    } else if (Notification.permission === 'denied') {
        _setPushStatus(
            '⛔ Powiadomienia są ZABLOKOWANE dla tej strony — przeglądarka nie pokaże już pytania. ' +
            'Odblokuj ręcznie: Desktop → kliknij 🔒/⚙ obok adresu → „Powiadomienia" → Zezwól (lub Resetuj), odśwież. ' +
            'Android Chrome → ⋮ → „Informacje o stronie"/🔒 → Uprawnienia → Powiadomienia → Zezwól, odśwież. Potem kliknij ponownie.'
        );
        return;
    } else {
        permPromise = Notification.requestPermission();  // fires prompt now, in-gesture
    }

    if (btn) btn.disabled = true;
    try {
        const perm = await permPromise;
        if (perm !== 'granted') {
            _setPushStatus('Nie udzielono zgody na powiadomienia.');
            return;
        }
        // VAPID public key from backend
        const vapid = await apiRequest('GET', '/push/vapid-public-key').catch(() => null);
        if (!vapid || !vapid.publicKey) {
            _setPushStatus('Zgoda udzielona, ale serwer nie ma kluczy VAPID (push nieskonfigurowany).');
            return;
        }
        // register SW + subscribe
        const reg = await _registerServiceWorker();
        if (!reg) { _setPushStatus('Nie udało się zarejestrować service workera.'); return; }
        await navigator.serviceWorker.ready;
        // A subscription created with a DIFFERENT applicationServerKey (e.g. an old/
        // broken VAPID key from a previous attempt) makes subscribe() throw
        // InvalidStateError. Drop any stale subscription first so the current key applies.
        const existing = await reg.pushManager.getSubscription();
        if (existing) { try { await existing.unsubscribe(); } catch (e) { /* ignore */ } }
        const sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: _urlBase64ToUint8Array(vapid.publicKey),
        });
        // persist subscription on backend
        const json = sub.toJSON();
        await apiRequest('POST', '/users/push-subscription', {
            endpoint: json.endpoint,
            keys: json.keys,
        });
        _setPushStatus('✓ Powiadomienia włączone na tym urządzeniu.');
        if (btn) btn.textContent = 'Powiadomienia włączone ✓';
        // Immediate local proof so the user sees a real notification right away.
        try { await reg.showNotification('AI-GM', { body: '🔔 Powiadomienia włączone — będziesz dostawać info o swojej turze.', icon: '/front/icon-192.png' }); } catch (e) { /* ignore */ }
    } catch (e) {
        console.error('[push] enable failed', e);
        _setPushStatus('Błąd włączania powiadomień: ' + (e.message || e));
    } finally {
        if (btn) btn.disabled = false;
    }
}

function initWebPush() {
    const btn = document.getElementById('enable-push-btn');
    if (btn && !btn._wired) {
        btn._wired = true;
        btn.addEventListener('click', enablePushNotifications);
    }
    // Pre-register the SW on load (non-gesture, allowed) so it's ready when the
    // user clicks — keeps the in-gesture path short.
    if ('serviceWorker' in navigator) {
        _registerServiceWorker();
    }
    // Reflect existing permission state in the label.
    if ('Notification' in window) {
        if (Notification.permission === 'granted') {
            _setPushStatus('Powiadomienia są dozwolone w przeglądarce.');
        } else if (Notification.permission === 'denied') {
            _setPushStatus('Powiadomienia zablokowane — odblokuj w ustawieniach strony.');
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWebPush);
} else {
    initWebPush();
}
