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
    game: document.getElementById('game-screen'),
    'create-lobby': document.getElementById('create-lobby-screen'),
    'lobby-screen': document.getElementById('lobby-screen')
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
    btnCampaignsBack: document.getElementById('campaigns-back'),
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

// --- Wizard state (real 5-step flow) ---
let wizardRace = 'human';       // #976 R7 — chosen race (step 0)
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
    { title: 'Rasa', subtitle: 'Krok 1 z 5' },
    { title: 'Twój bohater', subtitle: 'Krok 2 z 5' },
    { title: 'Statystyki', subtitle: 'Krok 3 z 5' },
    { title: 'Umiejętności', subtitle: 'Krok 4 z 5' },
    { title: 'Tożsamość', subtitle: 'Krok 5 z 5' },
];
function _skillRow(key) { return ALL_SKILL_ROWS.find(r => r.key === key) || { key, label: key, stat: '?' }; }
function _skillBudgetUsed() {
    // Opcja A (#747) — model redystrybucji: budżet = suma podniesień MINUS suma obniżeń.
    // Bez Math.abs — obniżenie wylosowanego skilla (delta < 0) zwraca punkt do wydania gdzie indziej.
    return ALL_SKILL_ROWS.reduce((s, { key }) => {
        const o = Number(wizardSkillSnapshot[key] || 0);
        if (!o) return s;
        return s + ((wizardSkillLevels[key] ?? o) - o);
    }, 0);
}
function _canAdjSkill(origKey, delta) {
    const o = Number(wizardSkillSnapshot[origKey] || 0);
    if (!o) return false;
    const cur = wizardSkillLevels[origKey] ?? o;
    const next = cur + delta;
    if (next < 0 || next > 2) return false;
    const test = { ...wizardSkillLevels, [origKey]: next };
    // ta sama formuła netto co _skillBudgetUsed — inaczej licznik rozjedzie się z blokowaniem przycisków
    const budget = ALL_SKILL_ROWS.reduce((s, { key }) => {
        const oo = Number(wizardSkillSnapshot[key] || 0);
        if (!oo) return s;
        return s + ((test[key] ?? oo) - oo);
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


// ── #901 — Księga Zasad — otwiera w nowej zakładce
function showRulesBook() {
    window.open('/rules/', '_blank', 'noopener');
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

// #900: confirmation modal before overwriting an active campaign
function _confirmNewCampaignOverwrite(heroName, campaignTitle, turnCount) {
    return new Promise((resolve) => {
        const pluralTury = (n) => n === 1 ? 'tura' : n < 5 ? 'tury' : 'tur';
        const turns = (turnCount != null && turnCount > 0)
            ? ` (${turnCount} ${pluralTury(turnCount)})`
            : '';
        const overlay = document.createElement('div');
        overlay.id = 'confirm-new-campaign-overlay';
        overlay.className = 'onboarding-card-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.innerHTML = `
            <div class="onboarding-card">
                <h3 class="onboarding-card__title">Nowa kampania?</h3>
                <p class="onboarding-card__content">
                    Bohater <strong>${escapeHtml(heroName)}</strong> jest już
                    w kampanii <strong>${escapeHtml(campaignTitle)}</strong>${escapeHtml(turns)}.<br><br>
                    Bohater niesie swój los do przodu — nie można grać tej samej postacią
                    (z obecnym ekwipunkiem i doświadczeniem) w dwóch kampaniach jednocześnie.<br><br>
                    Stara kampania zostanie <strong>zamknięta na zawsze</strong>.
                    Zobaczysz ją w historii jako zapis przeszłości, ale nie wrócisz do niej.
                </p>
                <div class="onboarding-card__nav">
                    <button type="button" class="btn btn--secondary" id="cnc-cancel">Anuluj</button>
                    <button type="button" class="btn btn--primary" id="cnc-confirm">Rozpocznij nową</button>
                </div>
            </div>`;
        overlay.querySelector('#cnc-confirm').addEventListener('click', () => { overlay.remove(); resolve(true); });
        overlay.querySelector('#cnc-cancel').addEventListener('click', () => { overlay.remove(); resolve(false); });
        document.body.appendChild(overlay);
        overlay.querySelector('#cnc-cancel')?.focus();
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
    document.getElementById('open-kodeks-gracza-btn')?.addEventListener('click', () => {
        closeSettings();
        showCodexLibrary();
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

    // Campaigns → back to heroes
    elements.btnCampaignsBack?.addEventListener('click', () => { loadHeroes(); showScreen('heroes'); });

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
    elements.btnOpenCodex?.addEventListener('click', showRulesBook);

    // #952 — hamburger ☰ dropdown menu (akcje drugorzędne + wyjście z lochu)
    setupGameMenu();
    // #952 — auto-hide paska przygody przy czytaniu narracji
    setupHeaderAutoHide();

    // Combat
    elements.btnCombatAttack?.addEventListener('click', onCombatAttackButton);  // B6c (#651): mag → menu ataku
    elements.btnCombatFlee?.addEventListener('click', handleCombatFlee);
    elements.btnCombatMove?.addEventListener('click', handleCombatMove);
    elements.btnCombatDodge?.addEventListener('click', handleCombatDodge);
    elements.btnCombatBlock?.addEventListener('click', handleCombatBlock);
    elements.btnCombatWrestle?.addEventListener('click', handleCombatWrestle);
    document.getElementById('combat-spell-btn')?.addEventListener('click', openSpellPicker);
    document.getElementById('combat-item-btn')?.addEventListener('click', openConsumablePicker);  // #859
    document.getElementById('consumable-picker-close')?.addEventListener('click', closeConsumablePicker);  // #859
    document.getElementById('consumable-picker-overlay')?.addEventListener('click', e => {
        if (e.target === document.getElementById('consumable-picker-overlay')) closeConsumablePicker();
    });
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

    // World map panel + local map panel
    initWorldMap();
    initLocalMap();
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

    const skipCombatNarrToggle = document.getElementById('skip-combat-narr-toggle');
    if (skipCombatNarrToggle) {
        skipCombatNarrToggle.checked = localStorage.getItem('aigm_skip_combat_narrative') === '1';
        skipCombatNarrToggle.addEventListener('change', e => {
            localStorage.setItem('aigm_skip_combat_narrative', e.target.checked ? '1' : '0');
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
        if (await consumePendingJoin()) return;
        if (await tryRestoreSession()) return;
        if (!authToken) return; // handleSessionExpired fired during tryRestoreSession
        showScreen('heroes');
    } else {
        showScreen('login');
    }
}

async function loadBgSettings() {
    try {
        // cache-bust so players see bg changes without hard-refresh (#896)
        const resp = await fetch(`${API_BASE}/ui/backgrounds?t=${Date.now()}`);
        if (!resp.ok) return;
        const data = await resp.json();
        const bgs = data.backgrounds || {};
        const cache = {};
        for (const [screen, url] of Object.entries(bgs)) {
            if (url) {
                document.documentElement.style.setProperty(
                    `--bg-screen-${screen}`,
                    `url("${url}")`
                );
                cache[screen] = url;
            }
        }
        // save to localStorage so preload script in <head> can apply on next visit (#896)
        try { localStorage.setItem('ai-gm-bg-cache', JSON.stringify(cache)); } catch (_) {}
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
  // #998: In settlement with sub-map, show local map instead of world map
  if (_lmap.panel) {
    try {
      const localData = await _lmRefresh();
      if (localData?.has_local_map) {
        _lmap.panel.removeAttribute('hidden');
        _lmap.panel.style.transform = 'translateX(0)';
        requestAnimationFrame(() => { _lmCenter(); _lmRender(); });
        return;
      }
    } catch (_) { /* no local map — fall through to world map */ }
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

// ── Local Map Panel — #998 FAZA ML ───────────────────────────────────────────

const _lmap = {
  panel:   null,
  svg:     null,
  confirm: null,
  title:   null,
  zoom: 1.6,
  pan:  { x: 0, y: 0 },
  hexes: [],
  currentHex: null,   // { hex_id, q, r, location_key }
  hubLabel: null,
  pendingTravel: null, // { hex_id, label, encounter_chance }
};

function _lmHexFill(hex) {
  if (hex.encounter_chance > 0) return '#2a1208'; // risky — dark red-brown
  return '#082014';                                // safe  — dark green
}
function _lmHexStroke(hex, isCurrent) {
  if (isCurrent) return { color: '#f0c040', width: 2.5 };
  if (hex.encounter_chance > 0) return { color: '#7a3a18', width: 0.8 };
  return { color: '#1a3020', width: 0.8 };
}

function _lmRender() {
  const svg = _lmap.svg;
  if (!svg) return;
  const rz = _WH * _lmap.zoom;
  let html = '';

  for (const hex of _lmap.hexes) {
    const { x, y } = _wmHexToPixel(hex.q, hex.r);
    const sx = x * _lmap.zoom + _lmap.pan.x;
    const sy = y * _lmap.zoom + _lmap.pan.y;
    const isCurrent = _lmap.currentHex && _lmap.currentHex.hex_id === hex.id;
    const fill = _lmHexFill(hex);
    const { color: stroke, width: sw } = _lmHexStroke(hex, isCurrent);
    const risky = hex.encounter_chance > 0;

    html += `<polygon class="lmap-hex" data-hex-id="${hex.id}"
      points="${_wmCorners(sx, sy, rz - 1)}"
      fill="${fill}" stroke="${stroke}" stroke-width="${sw}" style="cursor:pointer"/>`;

    if (risky)
      html += `<text x="${sx}" y="${sy - rz * 0.25}" text-anchor="middle"
        font-size="${Math.max(9, 11 * _lmap.zoom)}" style="pointer-events:none" fill="#cc6a3a">⚠</text>`;

    if (hex.label)
      html += `<text x="${sx}" y="${sy + rz * 0.38}" text-anchor="middle"
        font-size="${Math.max(7, 7.5 * _lmap.zoom)}" fill="#8ac8a8" style="pointer-events:none"
        >${escapeHtml((hex.label.includes(': ') ? hex.label.split(': ').slice(1).join(': ') : hex.label).slice(0, 12))}</text>`;

    if (isCurrent)
      html += `<text x="${sx}" y="${sy - rz * 0.52}" text-anchor="middle"
        font-size="${Math.max(11, 14 * _lmap.zoom)}" style="pointer-events:none">📍</text>`;
  }

  svg.innerHTML = html;
  svg.querySelectorAll('.lmap-hex').forEach(el => {
    el.addEventListener('click', _lmOnHexClick);
  });
}

function _lmCenter() {
  if (!_lmap.hexes.length || !_lmap.svg) return;
  const pixels = _lmap.hexes.map(h => _wmHexToPixel(h.q, h.r));
  const rz = _WH * _lmap.zoom;
  // Use bounding box of hex centers to determine content extent
  const minX = Math.min(...pixels.map(p => p.x)) - rz;
  const maxX = Math.max(...pixels.map(p => p.x)) + rz;
  const minY = Math.min(...pixels.map(p => p.y)) - rz;
  const maxY = Math.max(...pixels.map(p => p.y)) + rz;
  const contentW = (maxX - minX) * _lmap.zoom;
  const contentH = (maxY - minY) * _lmap.zoom;
  // Try real SVG rect first, fallback to viewport estimate
  const rect = _lmap.svg.getBoundingClientRect();
  const w = rect.width  > 10 ? rect.width  : Math.min(window.innerWidth  || 390, 420) * 0.95;
  const h = rect.height > 10 ? rect.height : (window.innerHeight || 700) - 120;
  // Center content in available space
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  _lmap.pan = {
    x: w / 2 - cx * _lmap.zoom,
    y: Math.max(rz, Math.min(h / 2 - cy * _lmap.zoom, h - contentH - rz)),
  };
}

function _lmOnHexClick(e) {
  const hexId = parseInt(e.currentTarget.dataset.hexId);
  const hex = _lmap.hexes.find(h => h.id === hexId);
  if (!hex) return;

  const label = hex.label || `(${hex.q},${hex.r})`;
  const riskInfo = hex.encounter_chance > 0 ? '⚠ Ryzykowna lokacja — możliwe spotkanie' : '✓ Bezpieczna lokacja';

  _lmap.pendingTravel = { hex_id: hexId, label, encounter_chance: hex.encounter_chance };
  _lmap.confirm.querySelector('#lmap-confirm-title').textContent = `Idziesz do ${label}`;
  _lmap.confirm.querySelector('#lmap-confirm-info').textContent = riskInfo;
  _lmap.confirm.removeAttribute('hidden');
}

async function _lmExecuteTravel() {
  const t = _lmap.pendingTravel;
  if (!t || !currentCampaignId) return;
  _lmap.confirm.setAttribute('hidden', '');

  try {
    const response = await apiRequest('POST', `/campaigns/${currentCampaignId}/local-travel`, {
      hex_id: t.hex_id,
    });

    if (response.clock) renderClock(response.clock);

    _lmap.currentHex = response.local_hex;
    _lmRender();

    const prose = `Przemieszczasz się do <strong>${escapeHtml(t.label)}</strong>. (+15 min)`;
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble chat-bubble--travel';
    bubble.innerHTML = prose;
    elements.chatMessages.appendChild(bubble);
    scrollToBottom();

    await refreshCharacterData();
  } catch (err) {
    showToast(err.message || 'Błąd ruchu lokalnego', 'error');
  }
}

async function _lmRefresh() {
  if (!currentCampaignId) return;
  const data = await apiRequest('GET', `/campaigns/${currentCampaignId}/local-map`);
  _lmap.hexes = data.hexes || [];
  _lmap.currentHex = data.current_local_hex || null;
  _lmap.hubLabel = data.hub_label || 'Osada';
  if (_lmap.title) _lmap.title.textContent = `🏘 ${_lmap.hubLabel}`;
  return data;
}

async function _lmOpen() {
  if (!currentCampaignId) return;
  try {
    const data = await _lmRefresh();
    if (!data?.has_local_map) {
      // Fallthrough to world map if no local map
      _wmOpen();
      return;
    }
    _lmap.panel.removeAttribute('hidden');
    _lmap.panel.style.transform = 'translateX(0)';
    // Defer centering until after layout is applied
    requestAnimationFrame(() => { _lmCenter(); _lmRender(); });
  } catch (err) {
    showToast(err.message || 'Błąd ładowania mapy osady', 'error');
    _wmOpen(); // fallback to world map
  }
}

function _lmClose() {
  _lmap.panel.style.transform = 'translateX(100%)';
  setTimeout(() => _lmap.panel.setAttribute('hidden', ''), 280);
  if (_lmap.confirm) _lmap.confirm.setAttribute('hidden', '');
  _lmap.pendingTravel = null;
}

function initLocalMap() {
  _lmap.panel   = document.getElementById('local-map-panel');
  _lmap.svg     = document.getElementById('lmap-svg');
  _lmap.confirm = document.getElementById('lmap-confirm');
  _lmap.title   = document.getElementById('lmap-title');
  if (!_lmap.panel) return;

  document.getElementById('lmap-close-btn')?.addEventListener('click', _lmClose);
  document.getElementById('lmap-back-btn')?.addEventListener('click', () => {
    _lmClose();
    setTimeout(_wmOpen, 300);
  });
  document.getElementById('lmap-btn-go')?.addEventListener('click', _lmExecuteTravel);
  document.getElementById('lmap-btn-cancel')?.addEventListener('click', () => {
    _lmap.confirm.setAttribute('hidden', '');
    _lmap.pendingTravel = null;
  });

  // Swipe right to close (mobile)
  let _swipeStartX = 0;
  _lmap.panel.addEventListener('touchstart', e => { _swipeStartX = e.touches[0].clientX; }, { passive: true });
  _lmap.panel.addEventListener('touchend', e => {
    if (e.changedTouches[0].clientX - _swipeStartX > 60) _lmClose();
  }, { passive: true });
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

// ── #859/#734: użyj mikstury/przedmiotu w walce — quick-picker konsumpcyjnych z plecaka ──
// #734: użycie to AKCJA — handleCombatUseItem woła /combat/use-consumable (leczy + KONSUMUJE turę).
// Domyka pętlę sustain #732: drop → wypij w groźnej walce kosztem tury (taktyczna decyzja).
async function openConsumablePicker() {
    if (!combatActive || lastCombatState?.current_turn !== 'player') {
        setCombatMsg('Nie twoja tura.', true); return;
    }
    if (combatBusy || enemyTurnInFlight) return;
    const overlay = document.getElementById('consumable-picker-overlay');
    const list = document.getElementById('consumable-picker-list');
    if (!overlay || !list || !characterData?.id) return;

    overlay.removeAttribute('hidden');
    list.innerHTML = '<div style="padding:12px;color:#888;font-size:0.8rem">Ładowanie plecaka…</div>';

    try {
        const resp = await fetch(`/api/inventory/${characterData.id}`).then(r => r.json());
        const items = Array.isArray(resp?.data) ? resp.data : [];
        // ta sama reguła co w plecaku (#764): konsumpcyjne z flagą can_use
        const usable = items.filter(it => String(it.item_type || '').toLowerCase() === 'consumable' && it.can_use === true);
        if (!usable.length) {
            list.innerHTML = '<div style="padding:12px;color:#888;font-size:0.8rem">Brak przedmiotów do użycia w plecaku.</div>';
            return;
        }
        list.innerHTML = usable.map(it => {
            const qty = (it.quantity || 1) > 1 ? `<span class="spell-pick-cost">×${it.quantity}</span>` : '';
            return `<button class="spell-pick-btn" data-inventory-id="${it.id}">
                <span class="spell-pick-icon">🧪</span>
                <span class="spell-pick-name">${escapeHtml(it.label || it.key || '?')}</span>
                ${qty}
            </button>`;
        }).join('');

        list.querySelectorAll('.spell-pick-btn:not(:disabled)').forEach(btn => {
            btn.addEventListener('click', () => {
                closeConsumablePicker();
                handleCombatUseItem(parseInt(btn.dataset.inventoryId, 10));
            });
        });
    } catch {
        list.innerHTML = '<div style="padding:12px;color:#f87171;font-size:0.8rem">Błąd ładowania plecaka.</div>';
    }
}

function closeConsumablePicker() {
    document.getElementById('consumable-picker-overlay')?.setAttribute('hidden', '');
}

async function handleCombatUseItem(inventoryId) {
    // #734: użycie mikstury w walce to AKCJA — konsumuje turę (endpoint /combat/use-consumable).
    // Backend leczy sheet, syncuje PŻ do active_combat i przesuwa turę → po akcji może ruszyć wróg.
    if (!inventoryId || !characterData?.id || !currentCampaignId) return;
    if (!combatActive || combatBusy || enemyTurnInFlight) return;
    if (lastCombatState?.current_turn !== 'player') { setCombatMsg('Nie twoja tura.', true); return; }
    combatBusy = true; playerActionFetchActive = true;  // #700
    setCombatMsg('Używam przedmiotu…');
    try {
        const r = await fetch(`/api/campaigns/${currentCampaignId}/combat/use-consumable`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ inventory_id: inventoryId }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.detail || 'błąd użycia');

        const cs = data.combat_state;
        const use = data.use_result || {};
        const st = use.character_state || {};
        const label = use.item?.label || 'przedmiot';
        const hpLine = (st.current_hp != null) ? ` — HP ${st.current_hp}/${st.max_hp ?? '?'}` : '';
        appendMessage({ role: 'system', content: `🧪 Użyto: ${label}${hpLine}.`, created_at: new Date() });
        scrollToBottom();
        showToast(`Użyto: ${label}`, 'success');

        if (cs) { lastCombatState = cs; renderCombatUI(cs); }
        await refreshCharacterData();
        // Tura zużyta — jeśli teraz ruch wroga, dopnij turę przeciwnika.
        if (cs && cs.current_turn !== 'player' && cs.status === 'active') {
            await pollCombatState();
        }
    } catch (err) {
        console.error('[combat] use item failed:', err);
        showToast(err?.message || 'Nie udało się użyć przedmiotu', 'error');
    } finally {
        combatBusy = false; playerActionFetchActive = false;  // #700
        setCombatMsg('');
        if (lastCombatState) renderCombatUI(lastCombatState);
    }
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
            // #653: heal spells OOC show dice animation (heal_die/heal_rolls/heal_modifier
            // already in the response); Stage 1 (d20) skipped via null forcedD20.
            if (data.spell_type === 'heal') {
                const healStage = buildDamageStage(data);
                // null label: Stage 1 (d20) is skipped so label param is never rendered.
                if (healStage) await playCombatDiceRoll(null, null, null, healStage);
            }
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

// #952 — hamburger ☰ dropdown: akcje drugorzędne + (w lochu) wyjście z krypty.
function setupGameMenu() {
    const btn = document.getElementById('game-menu-btn');
    const menu = document.getElementById('game-menu');
    if (!btn || !menu) return;

    const closeMenu = () => {
        menu.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
    };
    const openMenu = () => {
        // Zakotw menu pod przyciskiem ☰ przez viewport coords — menu jest poza <header> (position:fixed).
        const r = btn.getBoundingClientRect();
        menu.style.top  = `${r.bottom + 4}px`;
        menu.style.right = `${window.innerWidth - r.right}px`;
        menu.style.left = '';
        menu.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
    };

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (menu.hidden) openMenu(); else closeMenu();
    });
    // Klik pozycji menu → wykonaj akcję (handler już podpięty pod ID) i zamknij.
    menu.querySelectorAll('.game-menu__item').forEach((item) => {
        item.addEventListener('click', () => closeMenu());
    });
    // Klik poza menu / Escape → zamknij.
    document.addEventListener('click', (e) => {
        if (menu.hidden) return;
        if (!menu.contains(e.target) && e.target !== btn && !btn.contains(e.target)) closeMenu();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !menu.hidden) closeMenu();
    });
}

// #952 — auto-hide paska przygody: scroll w dół narracji chowa pasek, scroll w górę go przywraca.
// Ustawiany przez scrollToBottom() żeby programmatyczny scroll nie chował belki.
let _suppressAutoHide = false;

function setupHeaderAutoHide() {
    const scroller = document.getElementById('chat-messages');
    const header = document.querySelector('.header--game');
    if (!scroller || !header) return;
    let lastY = 0;
    const THRESHOLD = 8;

    scroller.addEventListener('scroll', () => {
        const y = scroller.scrollTop;
        if (_suppressAutoHide) {
            // Programmatyczny scroll — tylko aktualizuj pozycję, nie ruszaj paska
            lastY = y;
            return;
        }
        // #967: combat blokuje uciekanie paska przez body.combat-active (CSS !important).
        // Scroll handler może spokojnie dodawać/zdejmować header--hidden — CSS go overriduje.
        const delta = y - lastY;
        if (y < 40) {
            header.classList.remove('header--hidden');
        } else if (delta > THRESHOLD) {
            header.classList.add('header--hidden');
        } else if (delta < -THRESHOLD) {
            header.classList.remove('header--hidden');
        }
        lastY = y;
    }, { passive: true });

    // Tap w górnej strefie (~60px) przywraca schowany pasek — działa nawet gdy jesteś na dole.
    document.getElementById('game-screen')?.addEventListener('click', (e) => {
        if (e.clientY < 64 && header.classList.contains('header--hidden')) {
            header.classList.remove('header--hidden');
        }
    });
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

// #952 — pasek lochu scalony z górną belką. Riddle panel pozycjonowany tuż pod paskiem.
function _positionDungeonHUD() {
    const gameScreen = document.getElementById('game-screen');
    if (!gameScreen) return;
    const header = gameScreen.querySelector('.header');
    const headerH = header ? header.getBoundingClientRect().height : 50;
    document.documentElement.style.setProperty('--dungeon-hud-top', `${headerH}px`);
    document.documentElement.style.setProperty('--dungeon-hud-h', '0px');
}

function showDungeonHUD(show) {
    const hud = document.getElementById('dungeon-hud');           // inline klaster w pasku
    const clock = document.getElementById('header-clock');        // chip czasu — ustępuje w lochu
    const exitItem = document.getElementById('dungeon-exit-btn'); // pozycja "Wyjdź z krypty" w menu ☰
    if (hud) hud.hidden = !show;
    if (exitItem) exitItem.hidden = !show;
    if (clock && show) clock.hidden = true; // w lochu klaster zastępuje chip czasu
    if (clock && !show && clock.textContent) clock.hidden = false; // po wyjściu z lochu chip wraca
    const gameScreen = document.getElementById('game-screen');
    if (show) {
        _positionDungeonHUD();
        gameScreen?.classList.add('game-screen--dungeon');
    } else {
        gameScreen?.classList.remove('game-screen--dungeon');
    }
}

// Reposition riddle-panel anchor on window resize
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

// #869: `opts.silent` suppresses intermediate narrative/auto-map during a multi-step
// auto-walk. Returns { ok, stop, reason } so the walker knows when to hand control back.
async function _dungeonMove(direction, opts = {}) {
    if (!_dungeonCampaignId || !characterData?.id) return { ok: false, stop: true };
    const silent = !!opts.silent;
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
            return { ok: false, stop: true, reason: resp.reason };
        }

        if (resp.dungeon_run) _activeDungeonRun = resp.dungeon_run;

        // #869: during auto-walk, intermediate (cleared) tiles render no narrative —
        // only the final tile shows its full description (set below when !silent).
        if (resp.narrative && !silent) {
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

        const completed = !!(resp.completed || _activeDungeonRun?.completed);
        if (completed) {
            _showDungeonComplete(resp);
        } else {
            updateDungeonHUD();
            // #687: refresh the D-pad/action cluster for the NEW tile — hides it when
            // the move lands on a combat tile (else it overlaps the combat controls)
            // and drops the stale chest/riddle button from the previous room.
            updateDungeonNav(_activeDungeonRun);
            // Auto-open map on first move (#869: not mid auto-walk — map stays closed)
            if (!silent) {
                const visitedCount = Object.values(_activeDungeonRun?.graph?.nodes || {}).filter(n => n.visited).length;
                if (visitedCount === 2) openDungeonMap(true);
            }
        }

        // If combat started, refresh combat state
        const combatStarted = !!(resp.combat && !resp.combat.error);
        if (resp.combat) {
            const campResp = await apiRequest('GET', `/campaigns/${_dungeonCampaignId}`);
            if (campResp?.campaign) {
                currentCampaignId = campResp.campaign.id;
                await pollCombatState();
            }
        }

        // #869: hand control back to the player when the tile holds an unresolved event
        // (combat / riddle / dungeon complete) — auto-walk must never barrel through danger.
        const content = resp.content || {};
        const pendingRiddle = !resp.is_cleared && !!content.riddle;
        const stop = combatStarted || pendingRiddle || completed;
        return { ok: true, stop, reason: resp.reason };
    } catch (err) {
        showToast(err.message || 'Błąd ruchu', 'error');
        return { ok: false, stop: true, reason: err.message };
    } finally {
        document.querySelectorAll('[data-dungeon-dir]').forEach(b => b.disabled = false);
    }
}

// #869: walk a BFS-computed direction sequence one tile at a time. Awaits each step
// (each may trigger combat/riddle/content) and STOPS the moment a step reports `stop`
// (blocked door, combat, riddle, or run complete) — control returns to the player.
async function _dungeonAutoWalk(directions) {
    if (!Array.isArray(directions) || !directions.length) return;
    for (let i = 0; i < directions.length; i++) {
        const isLast = i === directions.length - 1;
        const res = await _dungeonMove(directions[i], { silent: !isLast });
        if (!res || res.stop) break;
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

// #869: BFS over OPEN doors → shortest list of directions (N|S|E|W) from `fromNodeId`
// to `toNodeId`. INTERMEDIATE hops only through ODKRYTE (visited) tiles; the DESTINATION
// may be a first-layer fog tile (border of known area) — its final hop is the discovering
// step (mirrors a manual d-pad press into fog). Deep fog (route would pass THROUGH an
// unknown tile) stays unreachable → null. Returns [] when from===to. Exposed on window
// so the click-to-move handler (and regression test #869) can reuse it.
function dungeonBfsPath(nodes, fromNodeId, toNodeId) {
    if (!nodes || !fromNodeId || !toNodeId) return null;
    if (fromNodeId === toNodeId) return [];
    if (!nodes[toNodeId]) return null;
    const prev = { [fromNodeId]: null };            // nodeId -> { from, dir } | null (start)
    const queue = [fromNodeId];
    while (queue.length) {
        const cur = queue.shift();
        const node = nodes[cur];
        if (!node) continue;
        for (const [dir, nbId] of Object.entries(node.doors_open || {})) {
            if (!nbId || nbId in prev) continue;
            const nb = nodes[nbId];
            if (!nb) continue;
            // intermediate hops must be known; only the destination may be the target
            if (nbId !== toNodeId && !nb.visited) continue;
            prev[nbId] = { from: cur, dir };
            if (nbId === toNodeId) {
                const path = [];
                let n = toNodeId;
                while (prev[n]) { path.unshift(prev[n].dir); n = prev[n].from; }
                return path;
            }
            queue.push(nbId);
        }
    }
    return null;
}
if (typeof window !== 'undefined') window.dungeonBfsPath = dungeonBfsPath;

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

// #741: przeciąganie D-pada lochu + zapamiętanie pozycji.
// Klucz localStorage: 'dungeonNavPos' = {left, top} w px (lewy-górny róg navu).
const _DPAD_POS_KEY = 'dungeonNavPos';
const _DPAD_DRAG_THRESHOLD = 6; // px — poniżej to tap (mapa/kierunek), powyżej to przeciąganie

function _clampDpadPos(left, top, w, h) {
    const m = 4; // margines od krawędzi
    const maxL = Math.max(m, window.innerWidth - w - m);
    const maxT = Math.max(m, window.innerHeight - h - m);
    return { left: Math.min(Math.max(m, left), maxL), top: Math.min(Math.max(m, top), maxT) };
}

function _applyDpadPos(nav, left, top) {
    // Przejście z right/bottom na left/top — sterujemy lewym-górnym rogiem.
    nav.style.left = left + 'px';
    nav.style.top = top + 'px';
    nav.style.right = 'auto';
    nav.style.bottom = 'auto';
}

function _restoreDpadPos(nav) {
    let saved;
    try { saved = JSON.parse(localStorage.getItem(_DPAD_POS_KEY) || 'null'); } catch (_) { saved = null; }
    if (!saved || typeof saved.left !== 'number' || typeof saved.top !== 'number') return;
    const r = nav.getBoundingClientRect();
    const w = r.width || 80, h = r.height || 200;
    const { left, top } = _clampDpadPos(saved.left, saved.top, w, h);
    _applyDpadPos(nav, left, top);
}

function initDpadDrag() {
    const nav = document.getElementById('dungeon-nav');
    if (!nav || nav._dpadDragInit) return;
    nav._dpadDragInit = true;
    const handle = nav.querySelector('.dungeon-nav__dirs');
    if (!handle) return;

    // Odtwórz zapisaną pozycję, gdy nav staje się widoczny (jest hidden poza lochem).
    _restoreDpadPos(nav);

    let startX = 0, startY = 0, baseLeft = 0, baseTop = 0, dragging = false, suppressClick = false;

    handle.addEventListener('pointerdown', (e) => {
        // Tylko główny przycisk/dotyk; ignoruj jeśli nav ukryty.
        if (e.button != null && e.button !== 0) return;
        const r = nav.getBoundingClientRect();
        baseLeft = r.left; baseTop = r.top;
        startX = e.clientX; startY = e.clientY;
        dragging = false;
        // #957: NIE chwytaj wskaźnika przy tapie — capture na kontenerze tłumiłby click
        // przycisków-dzieci (kierunki + ⊕). Capture dopiero gdy ruch przekroczy próg dragu.

        const onMove = (ev) => {
            const dx = ev.clientX - startX, dy = ev.clientY - startY;
            if (!dragging && Math.hypot(dx, dy) < _DPAD_DRAG_THRESHOLD) return; // jeszcze tap
            if (!dragging) {
                dragging = true;
                nav.classList.add('is-dragging');
                try { handle.setPointerCapture(ev.pointerId); } catch (_) {}  // #957: dopiero przy realnym dragu
            }
            const r2 = nav.getBoundingClientRect();
            const { left, top } = _clampDpadPos(baseLeft + dx, baseTop + dy, r2.width, r2.height);
            _applyDpadPos(nav, left, top);
        };
        const onUp = () => {
            handle.removeEventListener('pointermove', onMove);
            handle.removeEventListener('pointerup', onUp);
            handle.removeEventListener('pointercancel', onUp);
            try { handle.releasePointerCapture(e.pointerId); } catch (_) {}
            nav.classList.remove('is-dragging');
            if (dragging) {
                // Zapisz pozycję; zablokuj kliknięcie, które inaczej odpaliłoby kierunek/mapę.
                const r2 = nav.getBoundingClientRect();
                try { localStorage.setItem(_DPAD_POS_KEY, JSON.stringify({ left: r2.left, top: r2.top })); } catch (_) {}
                suppressClick = true;
                setTimeout(() => { suppressClick = false; }, 0);
            }
        };
        handle.addEventListener('pointermove', onMove);
        handle.addEventListener('pointerup', onUp);
        handle.addEventListener('pointercancel', onUp);
    });

    // Po przeciągnięciu połknij kliknięcie (tap vs drag) — w fazie capture, przed handlerami przycisków.
    nav.addEventListener('click', (e) => {
        if (suppressClick) { e.stopPropagation(); e.preventDefault(); suppressClick = false; }
    }, true);

    // Po zmianie rozmiaru okna utrzymaj nav w widoku.
    window.addEventListener('resize', () => {
        if (nav.style.left) _restoreDpadPos(nav);
    });
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

    // #741: środkowy ⊕ D-pada otwiera mapę lochu (skrót pod kciukiem, jak ikona 🗺 w HUD).
    document.getElementById('dungeon-nav-center')?.addEventListener('click', () => openDungeonMap());

    // #741: D-pad lochu da się przeciągnąć po ekranie; pozycja zapamiętana w localStorage.
    initDpadDrag();

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

            // #869: identify the clicked TILE (closest tile center within S px), then
            // pathfind to it — not just the closest adjacent door.
            let clickedId = null;
            let closestDist = 9999;
            for (const nid of drawIds) {
                const tn = nodes[nid];
                if (!tn?.position) continue;
                const tx = PAD + (tn.position[0] - minCol) * STEP + S / 2;
                const ty = PAD + (maxRow - tn.position[1]) * STEP + S / 2;
                const dist = Math.hypot(clickSvgX - tx, clickSvgY - ty);
                if (dist < closestDist && dist < S) {
                    closestDist = dist; clickedId = nid;
                }
            }
            if (!clickedId || clickedId === currentNodeId) return;

            // Multi-step: BFS through KNOWN (visited) tiles to the clicked destination.
            const path = dungeonBfsPath(nodes, currentNodeId, clickedId);
            if (path && path.length) {
                closeDungeonMap();
                _dungeonAutoWalk(path);
                return;
            }

            // Not reachable via known tiles. If the clicked tile is a direct fog
            // neighbour, allow the single discovering step (legacy 1-step behaviour).
            let directDir = null;
            for (const [dir, targetId] of Object.entries(currentNode.doors_open || {})) {
                if (targetId === clickedId) { directDir = dir; break; }
            }
            if (directDir) {
                closeDungeonMap();
                _dungeonMove(directDir);
                return;
            }

            // Unknown / unreachable tile (fog beyond reach) → no-op with hint.
            showToast('Nieodkryte — kliknij sąsiedni kafel, aby zbadać', 'info');
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

// #593 round 4 — every enable attempt records a step trail so a failure is
// VISIBLE on screen (and in window.__pushDiag) instead of needing a remote
// debugging round. _pushDiagPush(step, ok, detail).
window.__pushDiag = [];
function _pushDiagReset() { window.__pushDiag = []; _pushDiagRender(); }
function _pushDiagPush(step, ok, detail) {
    window.__pushDiag.push({ step, ok, detail: detail || '' });
    _pushDiagRender();
}
function _pushDiagRender() {
    const el = document.getElementById('push-diag');
    if (!el) return;
    el.innerHTML = window.__pushDiag.map(d =>
        `<li>${d.ok === true ? '✅' : d.ok === false ? '❌' : '⏳'} ${d.step}` +
        (d.detail ? ` — <span style="color:var(--t3)">${String(d.detail).replace(/</g, '&lt;')}</span>` : '') +
        `</li>`
    ).join('');
}

async function enablePushNotifications() {
    const btn = document.getElementById('enable-push-btn');
    _pushDiagReset();
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
        _pushDiagPush('Wsparcie przeglądarki', false, 'brak serviceWorker/PushManager/Notification');
        _setPushStatus('Twoja przeglądarka nie obsługuje powiadomień push.');
        return;
    }
    _pushDiagPush('Wsparcie przeglądarki', true, '');

    // Must be logged in — the subscription is saved against the player's account.
    // Without a JWT the browser would subscribe but the POST 401s → silent 0 rows.
    if (!localStorage.getItem('aigm_access_token')) {
        _pushDiagPush('Zalogowany', false, 'brak tokenu — zaloguj się i spróbuj ponownie');
        _setPushStatus('Musisz być zalogowany, aby włączyć powiadomienia.');
        return;
    }
    _pushDiagPush('Zalogowany', true, '');

    // CRITICAL (#593): requestPermission() MUST run synchronously inside the click
    // gesture — BEFORE any `await`. An await first consumes the user-activation and
    // many browsers (esp. mobile Safari/Chrome) then silently suppress the prompt.
    let permPromise;
    if (Notification.permission === 'granted') {
        permPromise = Promise.resolve('granted');
        _pushDiagPush('Zgoda przeglądarki', true, 'już przyznana');
    } else if (Notification.permission === 'denied') {
        _pushDiagPush('Zgoda przeglądarki', false, 'ZABLOKOWANA — odblokuj w 🔒 obok adresu, odśwież');
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
            _pushDiagPush('Zgoda przeglądarki', false, 'odpowiedź: ' + perm);
            _setPushStatus('Nie udzielono zgody na powiadomienia.');
            return;
        }
        if (Notification.permission === 'granted') _pushDiagPush('Zgoda przeglądarki', true, 'przyznana');
        // Server readiness — surfaces a misconfigured server half on screen.
        const diag = await apiRequest('GET', '/push/diagnostics').catch(() => null);
        if (diag) _pushDiagPush('Serwer gotowy', !!diag.configured && !!diag.pywebpush_installed && !!diag.private_key_loadable,
            `configured=${diag.configured}, pywebpush=${diag.pywebpush_installed}, klucz_ok=${diag.private_key_loadable}`);
        // VAPID public key from backend
        const vapid = await apiRequest('GET', '/push/vapid-public-key').catch(() => null);
        if (!vapid || !vapid.publicKey) {
            _pushDiagPush('Klucz VAPID', false, 'serwer nie zwrócił klucza');
            _setPushStatus('Zgoda udzielona, ale serwer nie ma kluczy VAPID (push nieskonfigurowany).');
            return;
        }
        _pushDiagPush('Klucz VAPID', true, vapid.publicKey.slice(0, 12) + '…');
        // register SW + subscribe
        const reg = await _registerServiceWorker();
        if (!reg) { _pushDiagPush('Service worker', false, 'rejestracja nieudana'); _setPushStatus('Nie udało się zarejestrować service workera.'); return; }
        await navigator.serviceWorker.ready;
        _pushDiagPush('Service worker', true, 'scope ' + reg.scope);
        // A subscription created with a DIFFERENT applicationServerKey (e.g. an old/
        // broken VAPID key from a previous attempt) makes subscribe() throw
        // InvalidStateError. Drop any stale subscription first so the current key applies.
        const existing = await reg.pushManager.getSubscription();
        if (existing) { try { await existing.unsubscribe(); } catch (e) { /* ignore */ } }
        let sub;
        try {
            sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: _urlBase64ToUint8Array(vapid.publicKey),
            });
        } catch (e) {
            _pushDiagPush('Subskrypcja push', false, (e && e.name ? e.name + ': ' : '') + (e && e.message || e));
            throw e;
        }
        _pushDiagPush('Subskrypcja push', true, sub.endpoint.slice(0, 40) + '…');
        // persist subscription on backend
        const json = sub.toJSON();
        try {
            await apiRequest('POST', '/users/push-subscription', {
                endpoint: json.endpoint,
                keys: json.keys,
            });
        } catch (e) {
            _pushDiagPush('Zapis na serwer', false, (e && e.status ? 'HTTP ' + e.status + ': ' : '') + (e && e.message || e));
            throw e;
        }
        _pushDiagPush('Zapis na serwer', true, 'zapisano — urządzenie widoczne w admin → Push');
        _setPushStatus('✓ Powiadomienia włączone na tym urządzeniu.');
        if (btn) btn.textContent = 'Powiadomienia włączone ✓';
        // Immediate local proof so the user sees a real notification right away.
        try { await reg.showNotification('AI-GM', { body: '🔔 Powiadomienia włączone — będziesz dostawać info o swojej turze.', icon: '/front/icon-192.png' }); } catch (e) { /* ignore */ }
    } catch (e) {
        console.error('[push] enable failed', e);
        _setPushStatus('Błąd włączania powiadomień: ' + (e.message || e) + ' — patrz 🩺 Diagnostyka poniżej.');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// Read-only diagnostics: inspects current state WITHOUT requesting permission or
// subscribing — so the user can run it any time and report exactly what's wrong.
async function runPushDiagnostics() {
    _pushDiagReset();
    const sw = 'serviceWorker' in navigator, pm = 'PushManager' in window, nt = 'Notification' in window;
    _pushDiagPush('Wsparcie przeglądarki', sw && pm && nt, `SW=${sw} Push=${pm} Notif=${nt}`);
    _pushDiagPush('Bezpieczny kontekst (HTTPS)', window.isSecureContext, location.origin);
    _pushDiagPush('Zalogowany', !!localStorage.getItem('aigm_access_token'), '');
    if (nt) _pushDiagPush('Zgoda przeglądarki', Notification.permission === 'granted',
        Notification.permission + (Notification.permission === 'denied' ? ' — odblokuj w 🔒 obok adresu' : ''));
    const diag = await apiRequest('GET', '/push/diagnostics').catch(() => null);
    if (diag) _pushDiagPush('Serwer gotowy', !!diag.configured && !!diag.pywebpush_installed && !!diag.private_key_loadable,
        `configured=${diag.configured}, pywebpush=${diag.pywebpush_installed}, klucz_ok=${diag.private_key_loadable}, pub_len=${diag.public_key_len}`);
    else _pushDiagPush('Serwer gotowy', false, '/api/push/diagnostics nieosiągalny');
    if (sw) {
        try {
            const reg = await navigator.serviceWorker.getRegistration();
            const ex = reg ? await reg.pushManager.getSubscription() : null;
            _pushDiagPush('Istniejąca subskrypcja', !!ex, ex ? ex.endpoint.slice(0, 40) + '…' : 'brak (kliknij „Włącz")');
        } catch (e) { _pushDiagPush('Istniejąca subskrypcja', false, e && e.message || e); }
    }
}

function initWebPush() {
    const btn = document.getElementById('enable-push-btn');
    if (btn && !btn._wired) {
        btn._wired = true;
        btn.addEventListener('click', enablePushNotifications);
    }
    const diagBtn = document.getElementById('push-diag-btn');
    if (diagBtn && !diagBtn._wired) {
        diagBtn._wired = true;
        diagBtn.addEventListener('click', runPushDiagnostics);
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
