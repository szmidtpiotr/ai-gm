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
const ARCHETYPE_BONUS = { warrior: { STR: 2, CON: 1 }, scholar: { INT: 2, WIS: 1 } };
const ALL_SKILL_ROWS = [
    { key: 'athletics',       label: 'Athletics',        stat: 'STR' },
    { key: 'endurance',       label: 'Endurance',        stat: 'CON' },
    { key: 'stealth',         label: 'Stealth',          stat: 'DEX' },
    { key: 'sleight_of_hand', label: 'Sleight of Hand',  stat: 'DEX' },
    { key: 'arcana',          label: 'Arcana',           stat: 'INT' },
    { key: 'investigation',   label: 'Investigation',    stat: 'INT' },
    { key: 'lore',            label: 'Lore',             stat: 'INT' },
    { key: 'awareness',       label: 'Awareness',        stat: 'WIS' },
    { key: 'survival',        label: 'Survival',         stat: 'WIS' },
    { key: 'medicine',        label: 'Medicine',         stat: 'WIS' },
    { key: 'persuasion',      label: 'Persuasion',       stat: 'CHA' },
    { key: 'intimidation',    label: 'Intimidation',     stat: 'CHA' },
    { key: 'melee_attack',    label: 'Melee Attack',     stat: 'STR' },
    { key: 'ranged_attack',   label: 'Ranged Attack',    stat: 'DEX' },
    { key: 'spell_attack',    label: 'Spell Attack',     stat: 'INT' },
    { key: 'alchemy',         label: 'Alchemy',          stat: 'INT' },
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

            console.log('[Login] Success, loading campaigns...');
            if (elements.welcomeUser) {
                elements.welcomeUser.textContent = `Witaj, ${currentUser.display_name || currentUser.username}`;
            }
            updateAdminSettingsVisibility();
            try {
                await loadCampaigns();
            } catch (e) {
                console.error('[Login] loadCampaigns failed:', e);
            }
            console.log('[Login] Calling showScreen(campaigns)...');
            showScreen('campaigns');
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
    localStorage.removeItem('token');
    localStorage.removeItem('user');
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
// Campaigns
// ============================================================================
async function loadCampaigns() {
    console.log('[Campaigns] Loading for user:', currentUser?.id);
    try {
        const response = await apiRequest('GET', '/campaigns');
        console.log('[Campaigns] Raw response:', response);
        const allCampaigns = response.campaigns || (Array.isArray(response) ? response : []);

        // Filter to show only current user's campaigns
        const campaigns = allCampaigns.filter(c => {
            const ownerId = c.owner_user_id ?? c.owneruserid;
            return Number(ownerId) === Number(currentUser?.id);
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

    if (!campaigns || campaigns.length === 0) {
        elements.campaignsEmpty.style.display = 'block';
        return;
    }

    elements.campaignsEmpty.style.display = 'none';

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
        } else {
            // No character for this user - start creation wizard
            startCharacterWizard();
        }
    } catch (error) {
        console.error('Error loading characters:', error);
        startCharacterWizard();
    }
}

function showNewCampaignScreen() {
    elements.campaignNameInput.value = '';
    elements.campaignNameCount.textContent = '0';
    showScreen('newCampaign');
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
                        <span class="archetype-title">Warrior</span>
                        <span class="archetype-desc">Frontowy wojownik: wytrzymały, pewny stali, silny w bezpośrednim starciu.</span>
                    </button>
                    <button type="button" class="archetype-card${savedArch === 'scholar' ? ' archetype-card--selected' : ''}" data-arch="scholar">
                        <span class="archetype-title">Scholar</span>
                        <span class="archetype-desc">Tkacz arkanów: kruchy, ale groźny dzięki zaklęciom i mistycznej wiedzy.</span>
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
function _renderStep2(c) {
    const archetype = wizardCreatedChar?.sheet_json?.archetype || 'warrior';
    const bonus = ARCHETYPE_BONUS[archetype] || {};
    const bonusStr = Object.entries(bonus).map(([k, v]) => `+${v} ${k}`).join(', ');

    let rows = '';
    for (const stat of ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']) {
        const v = wizardStatBases[stat] ?? 10;
        const mod = Math.floor((v - 10) / 2);
        const modStr = mod >= 0 ? `+${mod}` : `${mod}`;
        const canMinus = v > WIZARD_STAT_MIN;
        const canPlus = v < WIZARD_STAT_MAX && wizardStatUnassigned > 0;
        rows += `
            <div class="wizard-stat-row" data-stat="${stat}">
                <span class="wizard-stat-label">${stat}</span>
                <span class="wizard-stat-mod">${modStr}</span>
                <div class="wizard-stat-controls">
                    <button type="button" class="wizard-stat-btn" data-dir="-" ${canMinus ? '' : 'disabled'}>−</button>
                    <span class="wizard-stat-val">${v}</span>
                    <button type="button" class="wizard-stat-btn" data-dir="+" ${canPlus ? '' : 'disabled'}>+</button>
                </div>
            </div>`;
    }

    c.innerHTML = `
        <div class="wizard-form">
            <p class="wizard-hint">Przesuń punkty między statystykami. Zmniejsz stat (−) aby dodać do puli, wydaj pulę (+) na inne. Bonusy klasy dodawane automatycznie.</p>
            <div class="wizard-points">Niezapisane punkty: <strong>${wizardStatUnassigned}</strong></div>
            <p class="wizard-class-note">${bonusStr} dodawane automatycznie po potwierdzeniu</p>
            <div class="wizard-stat-grid">${rows}</div>
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
                `<option value="${cd.key}">${_esc(cd.label)} — ${cd.stat}</option>`
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
function _renderStep4(c) {
    const p = wizardIdentityPreview;
    if (!p) {
        c.innerHTML = `<div class="wizard-form"><p class="wizard-hint">Generowanie tożsamości...</p></div>`;
        return;
    }
    c.innerHTML = `
        <div class="wizard-form">
            <div class="form-field">
                <label>Wygląd</label>
                <textarea id="wiz-appearance" rows="3">${_esc(p.appearance)}</textarea>
            </div>
            <div class="form-field">
                <label>Osobowość</label>
                <textarea id="wiz-personality" rows="3">${_esc(p.personality)}</textarea>
            </div>
            <div class="form-field">
                <label>Słabość (zablokowane)</label>
                <input type="text" value="${_esc(p.flaw)}" disabled>
            </div>
            <div class="form-field">
                <label>Więź (zablokowane)</label>
                <input type="text" value="${_esc(p.bond)}" disabled>
            </div>
            <p class="wizard-hint">🔒 Twój sekret zostanie ujawniony, gdy historia tego zażąda.</p>
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
    } else {
        char = await apiRequest('POST', `/campaigns/${currentCampaignId}/characters`, {
            user_id: currentUser?.id,
            name,
            system_id: currentCampaign?.system_id || 'fantasy',
            sheet_json: { archetype, backstory: bg },
        });
    }

    wizardCreatedChar = char;
    const sheet = char.sheet_json || {};
    const archKey = sheet.archetype || 'warrior';
    const bonus = ARCHETYPE_BONUS[archKey] || {};
    const storedStats = sheet.stats || {};

    // Reverse-engineer pre-bonus base values
    for (const k of ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']) {
        const bonVal = bonus[k] || 0;
        wizardStatBases[k] = Math.max(WIZARD_STAT_MIN, (storedStats[k] || 10) - bonVal);
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

    // Identity overrides
    const appearance = document.getElementById('wiz-appearance')?.value?.trim() || wizardIdentityPreview?.appearance || '';
    const personality = document.getElementById('wiz-personality')?.value?.trim() || wizardIdentityPreview?.personality || '';
    const flaw = wizardIdentityPreview?.flaw || '';
    const bond = wizardIdentityPreview?.bond || '';
    const secret = wizardIdentityPreview?.secret || '';

    const result = await apiRequest('POST', `/characters/${charId}/finalize-sheet`, {
        stat_overrides: statOverrides,
        skills: finalSkills,
        skill_slot_current: Object.keys(skillSlotCurrent).length > 0 ? skillSlotCurrent : null,
        identity_overrides: { appearance, personality, flaw, bond, secret },
    });

    // Reload character with finalized sheet
    const chars = await apiRequest('GET', `/campaigns/${currentCampaignId}/characters`);
    const charList = chars.characters || (Array.isArray(chars) ? chars : []);
    characterData = charList.find(c => c.id === charId) || wizardCreatedChar;
    if (result?.sheet_json) characterData.sheet_json = result.sheet_json;

    await enterGame(currentCampaign);
}

// ============================================================================
// Game Screen
// ============================================================================
async function enterGame(campaign) {
    const sheet = characterData?.sheet_json || characterData || {};
    elements.characterNameDisplay.textContent = characterData?.name || 'Bohater';
    const level = sheet.level || characterData?.level || 1;
    const hp = sheet.current_hp ?? characterData?.hp ?? 29;
    const maxHp = sheet.max_hp ?? characterData?.max_hp ?? 29;
    elements.characterStatsDisplay.textContent = `Poziom ${level} • ${hp}/${maxHp} HP`;
    elements.chatMessages.innerHTML = '';

    try {
        const response = await apiRequest('GET', `/campaigns/${campaign.id}/turns`);
        const turns = response.turns || (Array.isArray(response) ? response : []);
        if (turns && turns.length > 0) {
            turns.forEach(turn => {
                if (turn.user_text && !turn.user_text.startsWith('__AI_GM')) {
                    appendMessage({ role: 'user', content: turn.user_text, created_at: turn.created_at, turn_number: turn.turn_number, route: turn.route }, { autoSpeak: false });
                }
                if (turn.assistant_text) {
                    const { narrative: gmContent, ...gmMeta } = parseGmFull(turn.assistant_text);
                    if (gmContent && gmContent.trim()) {
                        appendMessage({ role: 'assistant', content: gmContent, created_at: turn.created_at, turn_number: turn.turn_number, route: turn.route, debugMeta: gmMeta }, { autoSpeak: false });
                    }
                }
            });
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

        const rereadBtn = isGm ? `<button type="button" class="bubble-reread-btn" title="Przeczytaj ponownie">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
        </button>` : '';

        bubble.innerHTML = `
            <div class="chat-bubble__content">${formatMessageContent(msg.content || msg.text || '')}</div>
            <div class="chat-bubble__meta">
                <span class="bubble-meta__left">${namePart}${turnPart ? ' ' + turnPart : ''}</span>
                <span class="bubble-meta__right">${routePart}${dtPart}${rereadBtn}</span>
            </div>
        `;

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

async function handleSendMessage() {
    const content = elements.chatInput.value.trim();
    if (!content) return;

    if (!characterData?.id) {
        showToast('Brak postaci - odśwież stronę', 'error');
        return;
    }

    // Unlock audio from this user gesture (before any awaits lose gesture context)
    window.voiceUI?.unlockAudio?.();

    elements.chatInput.value = '';
    elements.btnSend.disabled = true;

    if (content.startsWith('/')) {
        const handled = await handleSlashCommand(content);
        if (handled) {
            elements.btnSend.disabled = false;
            return;
        }
    }

    const userMsgPlaceholder = { role: 'user', content, created_at: new Date() };
    appendMessage(userMsgPlaceholder);
    scrollToBottom();

    const typingIndicator = showTypingIndicator();

    try {
        const response = await apiRequest('POST', `/campaigns/${currentCampaignId}/turns`, {
            text: content,
            character_id: characterData.id
        });

        typingIndicator.remove();

        // Backend returns: { result: { message: "..." } } or { result: "..." }
        let gmText = null;
        if (response.result) {
            gmText = typeof response.result === 'string'
                ? response.result
                : (response.result.message || response.result.narrative);
        }
        // Fallback to other possible fields
        gmText = gmText || response.assistant_text || response.gm_response || response.content;

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
    } catch (error) {
        typingIndicator.remove();
        console.error('Send message error:', error);
        showToast(error.message || 'Nie udało się wysłać wiadomości', 'error');
    } finally {
        elements.btnSend.disabled = false;
        scrollToBottom();
    }
}

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
    setCombatMsg('');
}

function setCombatMsg(text, isError) {
    const el = elements.combatMsg;
    if (!el) return;
    if (!text) { el.hidden = true; el.textContent = ''; return; }
    el.textContent = text;
    el.hidden = false;
    el.classList.toggle('combat-banner__msg--error', !!isError);
}

function renderCombatUI(cs) {
    const round = Number(cs.round || 1);
    elements.combatRound.textContent = `Runda ${round}`;

    const combatants = Array.isArray(cs.combatants) ? cs.combatants : [];
    const player = combatants.find(c => c && c.type === 'player');
    const enemies = combatants.filter(c => c && c.type === 'enemy');
    const isPlayerTurn = cs.current_turn === 'player';

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

    const parts = [];
    if (player) parts.push(combatantRow(player, true));
    enemies.forEach(e => parts.push(combatantRow(e, false)));
    elements.combatEnemies.innerHTML = parts.join('');

    const canAct = isPlayerTurn && !combatBusy;
    elements.btnCombatAttack.disabled = !canAct;
    elements.btnCombatFlee.disabled = !canAct;
    window.clog?.event('combat_buttons_state', { attack_disabled: !canAct, is_player_turn: isPlayerTurn, busy: combatBusy });
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
            .filter(row =>
                row && (String(row.event_type) === 'attack' || String(row.event_type) === 'death') &&
                Number(row.id) > lastRenderedCombatTurnId
            )
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

        const atkRoll = data.attack_roll || {};
        const total = Number(atkRoll.total ?? data.total ?? d20);
        const mod = Number(atkRoll.modifier ?? 0);
        const dmg = data.damage ?? 0;
        const hit = !!data.hit;
        const targetName = data.target_name || target?.name || 'wróg';

        if (hit) { setCombatMsg(`Trafienie! ${dmg} obrażeń.`); }
        else if (data.player_nat1) { setCombatMsg('Fatalne pudło!', true); }
        else { setCombatMsg('Pudło.'); }

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
            total,
            hit,
            damage: dmg,
            target_name: targetName,
            enemy_key: body.enemy_key || '',
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
    } catch (e) {
        window.clog?.error('combat_attack_exception', { message: String(e?.message || e) });
        setCombatMsg(`Błąd ataku: ${e.message || e}`, true);
    } finally {
        combatBusy = false;
        if (lastCombatState && elements.combatEndOverlay?.hidden !== false) renderCombatUI(lastCombatState);
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

    const sheet = character.sheet_json || character;
    elements.sheetCharacterName.textContent = character.name || 'Bohater';

    const hp = sheet.current_hp ?? character.hp ?? 29;
    const maxHp = sheet.max_hp ?? character.max_hp ?? 29;
    elements.sheetHp.textContent = `${hp} / ${maxHp}`;
    elements.sheetHpBar.style.width = `${(hp / maxHp) * 100}%`;

    elements.sheetLevel.textContent = sheet.level || character.level || 1;

    const stats = sheet.stats || character.stats || {};
    const statNames = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];
    elements.sheetStats.innerHTML = statNames.map(stat => `
        <div class="stat-item">
            <span class="stat-item__label">${stat}</span>
            <span class="stat-item__value">${stats[stat] || stats[stat.toLowerCase()] || 10}</span>
        </div>
    `).join('');

    renderSkillsTab(sheet);

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
    return t === 'misc' || t === 'quest';
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
    return `
        <div class="inv-row" data-inventory-id="${item.id}">
            <div class="inv-row__icon">${INV_ICONS.scroll}</div>
            <div class="inv-row__info">
                <div class="inv-row__name">${escapeHtml(item.label || item.key || '?')}${qty}</div>
            </div>
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
                if (action === 'use') {
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
function initEventListeners() {
    // Login
    elements.loginForm?.addEventListener('submit', handleLogin);

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
        loadCampaigns();
        showScreen('campaigns');
    });

    // Game
    elements.btnOpenSheet?.addEventListener('click', toggleCharacterSheet);
    elements.btnOpenSettings?.addEventListener('click', toggleSettings);
    elements.btnOpenJournal?.addEventListener('click', toggleJournal);

    // Combat
    elements.btnCombatAttack?.addEventListener('click', handleCombatAttack);
    elements.btnCombatFlee?.addEventListener('click', handleCombatFlee);
    elements.combatEndBtn?.addEventListener('click', hideCombatEndOverlay);
    elements.btnSend?.addEventListener('click', handleSendMessage);
    elements.chatInput?.addEventListener('keypress', handleKeyPress);
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

    // Journal regen
    elements.btnJournalRegen?.addEventListener('click', () => loadJournalContent(true));

    // Go to campaigns from settings
    elements.btnGoToCampaigns?.addEventListener('click', handleGoToCampaigns);

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
async function init() {
    initEventListeners();

    if (checkAuth()) {
        updateAdminSettingsVisibility();
        await loadCampaigns();
        showScreen('campaigns');
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
