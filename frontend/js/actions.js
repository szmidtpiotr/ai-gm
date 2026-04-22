window.state = window.state || {
  lang: 'pl',
  translations: {},
  campaigns: [],
  characters: [],
  models: [],
  turns: [],
  selectedCampaignId: null,
  selectedCharacterId: null,
  selectedEngine: null,
  turnNumbers: {},
  expectCharacterCreationForCampaignId: null
};

window.state._campaignCreationInFlight = window.state._campaignCreationInFlight || false;
window.state._characterCreationInFlight = window.state._characterCreationInFlight || false;
/**
 * After a character is successfully created (POST .../characters), store a reference here
 * so that if the player goes Back to step 1 and re-submits the form we skip the duplicate
 * POST and re-enter the wizard with the same character.
 * Cleared on: finalize success (finalized=true), or abandon cleanup (null).
 */
window.state._wizardPendingCharacter = window.state._wizardPendingCharacter || null;

window.state._combatJustEnded = window.state._combatJustEnded || false;
window.state._lastKilledEnemy = window.state._lastKilledEnemy || null;
window.state._combatVictoryUiPending = window.state._combatVictoryUiPending || false;
window.state.gmRollClientTurns = window.state.gmRollClientTurns || [];

/**
 * Registry keys enabled for players (`GET /api/mechanics/slash-commands`). Filled by `loadSlashCommandCatalog`.
 * When empty or unset, the client does not pre-block (the server still enforces).
 * @type {Set<string> | null}
 */
window.__slashCommandsEnabledKeys = window.__slashCommandsEnabledKeys || null;

/** @param {string} registryCommand e.g. "/atak", "/mem [pytanie]", "/search" */
window.isPublicSlashCommandEnabled = function (registryCommand) {
  const keys = window.__slashCommandsEnabledKeys;
  if (!keys || !(keys instanceof Set) || keys.size === 0) return true;
  return keys.has(String(registryCommand || '').trim());
};

/**
 * Maps a user line to a registry key when it is handled by the main narrative stream (not /mem, /search, …).
 * @param {string} line
 * @returns {string | null}
 */
window.slashRegistryKeyForChatClient = function (line) {
  const t = String(line || '').trim();
  if (!t.startsWith('/')) return null;
  if (/^\/roll\b/i.test(t)) return '/roll';
  if (/^\/help\b/i.test(t)) return '/help';
  if (/^\/sheet\b/i.test(t)) return '/sheet';
  if (/^\/history\b/i.test(t)) return '/history';
  if (/^\/export\b/i.test(t)) return '/export';
  if (/^\/name\b/i.test(t)) return '/name <new name>';
  if (/^\/(?:walka|atak)\s*$/i.test(t)) return '/atak';
  return null;
};

/** Survives refresh: used to DELETE abandoned campaign on next load or via pagehide keepalive. */
window.WIZARD_PENDING_SESSION_KEY = 'ai-gm:wizardPendingCharacter';

window._persistWizardPendingSession = function () {
  try {
    const p = window.state._wizardPendingCharacter;
    if (!p || p.finalized) {
      sessionStorage.removeItem(window.WIZARD_PENDING_SESSION_KEY);
      return;
    }
    sessionStorage.setItem(
      window.WIZARD_PENDING_SESSION_KEY,
      JSON.stringify({
        campaignId: p.campaignId,
        characterId: p.characterId,
        characterName: p.characterName || '',
        finalized: false
      })
    );
  } catch (_e) {
    /* optional */
  }
};

window._clearWizardPendingSession = function () {
  try {
    sessionStorage.removeItem(window.WIZARD_PENDING_SESSION_KEY);
  } catch (_e) {
    /* optional */
  }
};

/**
 * After refresh / crash: remove campaign+character created for an unfinished wizard
 * (sessionStorage still holds campaign id; in-memory _wizardPendingCharacter is gone).
 */
window.cleanupAbandonedWizardFromSession = async function () {
  let raw = null;
  try {
    raw = sessionStorage.getItem(window.WIZARD_PENDING_SESSION_KEY);
  } catch (_e) {
    return;
  }
  if (!raw) return;
  let p = null;
  try {
    p = JSON.parse(raw);
  } catch (_e) {
    window._clearWizardPendingSession();
    return;
  }
  if (!p || p.finalized || !p.campaignId) {
    window._clearWizardPendingSession();
    return;
  }
  try {
    const resp = await fetch(`/api/campaigns/${p.campaignId}`, {
      method: 'DELETE',
      headers: window.getApiHeaders ? window.getApiHeaders() : {}
    });
    if (!resp.ok && resp.status !== 404) {
      console.warn('[wizard] session startup cleanup failed', resp.status);
    }
  } catch (e) {
    console.warn('[wizard] session startup cleanup error', e);
  }
  window._clearWizardPendingSession();
  window.state._wizardPendingCharacter = null;
  window.state.expectCharacterCreationForCampaignId = null;
};

if (!window.__wizardPageHideCleanupRegistered) {
  window.__wizardPageHideCleanupRegistered = true;
  window.addEventListener('pagehide', () => {
    const p = window.state._wizardPendingCharacter;
    if (!p || p.finalized || !p.campaignId) return;
    try {
      fetch(`/api/campaigns/${p.campaignId}`, {
        method: 'DELETE',
        headers: window.getApiHeaders ? window.getApiHeaders() : {},
        keepalive: true
      }).catch(() => {});
    } catch (_e) {
      /* optional */
    }
  });
}

/** Disable campaign create UI while POST /campaigns is in flight (prevents double submit). */
window._setCampaignCreationBusy = function (busy) {
  window.state._campaignCreationInFlight = !!busy;
  const els = window.getEls();
  const on = !!busy;
  if (els.campaignCreateSubmitEl) els.campaignCreateSubmitEl.disabled = on;
  if (els.campaignCreateCloseEl) els.campaignCreateCloseEl.disabled = on;
  if (els.campaignCreateTitleInputEl) els.campaignCreateTitleInputEl.readOnly = on;
  if (els.createCampaignBtn) els.createCampaignBtn.disabled = on;
  if (els.campaignCreateOverlayEl) {
    if (on) els.campaignCreateOverlayEl.setAttribute('data-creation-busy', '1');
    else els.campaignCreateOverlayEl.removeAttribute('data-creation-busy');
  }
  if (typeof window.updateUiState === 'function') window.updateUiState();
};

/** Disable character create form while POST .../characters is in flight. */
window._setCharacterCreationBusy = function (busy) {
  window.state._characterCreationInFlight = !!busy;
  const els = window.getEls();
  const on = !!busy;
  if (els.characterCreateSubmitEl) {
    els.characterCreateSubmitEl.disabled = on;
    if (on) {
      if (!els.characterCreateSubmitEl.dataset.origText) {
        els.characterCreateSubmitEl.dataset.origText = els.characterCreateSubmitEl.textContent;
      }
      els.characterCreateSubmitEl.innerHTML =
        'GM przygotowuje świat\u2026 <span class="typing-dots" aria-hidden="true"><span></span><span></span><span></span></span>';
    } else {
      const orig = els.characterCreateSubmitEl.dataset.origText;
      if (orig) {
        els.characterCreateSubmitEl.textContent = orig;
        delete els.characterCreateSubmitEl.dataset.origText;
      }
    }
  }
  if (els.characterCreateCloseEl) els.characterCreateCloseEl.disabled = on;
  if (els.characterCreateNameEl) els.characterCreateNameEl.readOnly = on;
  if (els.characterCreateBackgroundEl) els.characterCreateBackgroundEl.readOnly = on;
  document.querySelectorAll('.archetype-card').forEach((c) => {
    c.style.pointerEvents = on ? 'none' : '';
  });
  if (els.characterCreateOverlayEl) {
    if (on) els.characterCreateOverlayEl.setAttribute('data-creation-busy', '1');
    else els.characterCreateOverlayEl.removeAttribute('data-creation-busy');
  }
  if (typeof window.updateUiState === 'function') window.updateUiState();
};

window.chatRequestState = window.chatRequestState || {
  inFlight: false,
  requestId: 0
};
window.state.pendingRoll = window.state.pendingRoll || null;

window._updateRollButtonsState = function () {
  const { contextualRollBtn } = window.getEls();
  if (!contextualRollBtn) return;
  // Legacy inline roll button is disabled; use popup actions only.
  contextualRollBtn.style.display = 'none';
};

window.parsePendingRoll = function (text) {
  const sourceText = String(text || '');
  const lines = sourceText.split('\n');
  const lastLineRaw = (lines[lines.length - 1] || '').trim();
  const match = lastLineRaw.match(/^Roll (.+?) (d\d+)$/i);

  if (!match) {
    window.state.pendingRoll = null;
    window._updateRollButtonsState();
    return sourceText;
  }

  const skillLabel = (match[1] || '').trim();
  const canonicalSkill = typeof window.resolveRollTestName === 'function'
    ? window.resolveRollTestName(skillLabel)
    : null;
  const diceExpr = (match[2] || 'd20').toLowerCase();

  if (!canonicalSkill) {
    console.warn('Ignoring unknown roll cue test name:', skillLabel);
    window.state.pendingRoll = null;
    window._updateRollButtonsState();
    return sourceText;
  }

  const dcMatches = [...sourceText.matchAll(/\bDC\s*[:=]?\s*(\d+)/gi)];
  let dcFromNarrative = null;
  if (dcMatches.length) {
    dcFromNarrative = parseInt(dcMatches[dcMatches.length - 1][1], 10);
    if (Number.isNaN(dcFromNarrative)) dcFromNarrative = null;
  }

  const displaySkill = typeof window.formatRollTestDisplayName === 'function'
    ? window.formatRollTestDisplayName(canonicalSkill)
    : canonicalSkill;
  window.state.pendingRoll = {
    skill: displaySkill,
    canonical_skill: canonicalSkill,
    dice: diceExpr,
    dc: dcFromNarrative,
    description: typeof window.getTestDescription === 'function'
      ? window.getTestDescription(canonicalSkill)
      : '',
  };

  window._updateRollButtonsState();

  lines.pop();
  return lines.join('\n').trimEnd();
};

window.performPendingRoll = function () {
  const pending = window.state.pendingRoll;
  if (!pending) return;

  const diceMatch = pending.dice.match(/^d(\d+)$/i);
  const sides = diceMatch ? Number(diceMatch[1]) : 20;
  const roll = Math.floor(Math.random() * sides) + 1;

  window.addMessage({
    speaker: 'System',
    text: `🎲 Roll ${pending.skill} ${pending.dice} → ${roll}`,
    role: 'system'
  });

  window.state.pendingRoll = null;
  window._updateRollButtonsState();
};

window.nextTurnNumber = function () {
  const id = window.state.selectedCampaignId;
  if (!id) return 1;

  const current = window.state.turnNumbers[id] || 0;
  window.state.turnNumbers[id] = current + 1;
  return window.state.turnNumbers[id];
};

/**
 * Bug 4: if the player opened the character creation modal, a character was created
 * (POST .../characters), but they closed/cancelled before completing finalize-sheet,
 * delete the campaign (and its orphaned character + turns) to avoid leftover junk data.
 */
window.abandonWizardCampaignIfNeeded = async function () {
  const p = window.state._wizardPendingCharacter;
  if (!p || p.finalized) return;
  // Clear immediately to prevent re-entry.
  window.state._wizardPendingCharacter = null;
  window.state.expectCharacterCreationForCampaignId = null;
  window._clearWizardPendingSession();
  try {
    const resp = await fetch(`/api/campaigns/${p.campaignId}`, {
      method: 'DELETE',
      headers: window.getApiHeaders ? window.getApiHeaders() : {}
    });
    if (!resp.ok && resp.status !== 404) {
      console.warn('[wizard] campaign cleanup failed', resp.status);
    }
  } catch (e) {
    console.warn('[wizard] campaign cleanup error', e);
  }
  try {
    if (typeof window.loadCampaigns === 'function') {
      await window.loadCampaigns();
    }
    if (typeof window.loadCharacters === 'function' && window.state.selectedCampaignId) {
      await window.loadCharacters(window.state.selectedCampaignId);
    }
  } catch (_e) {}
  if (typeof window.updateUiState === 'function') window.updateUiState();
};

window.createCampaign = async function () {
  if (window.state._campaignCreationInFlight) return;
  window.setCampaignModalOpen(true);
};

window.createCampaignFromForm = async function () {
  const { systemSelectEl, engineSelectEl } = window.getEls();
  const {
    campaignCreateTitleInputEl,
    campaignCreateFormEl,
    campaignCreateSubmitEl
  } = window.getEls();

  const title = (campaignCreateTitleInputEl?.value || '').trim();
  if (!title) return;

  const payload = {
    title,
    system_id: systemSelectEl.value,
    model_id: engineSelectEl.value || (window.state.models[0]?.name ?? 'gemma3:1b'),
    owner_user_id: window.state?.playerUserId || 1,
    language: window.state.lang || 'pl',
    mode: 'solo',
    status: 'active'
  };

  window._setCampaignCreationBusy(true);
  const userIdPre = window.state?.playerUserId || 1;
  try {
    try {
      if (typeof window.loadUserLlmSettings === 'function') {
        await window.loadUserLlmSettings(userIdPre);
      }
    } catch (_e) {}

    if (typeof window.computeLlmGate === 'function') {
      const g = window.computeLlmGate();
      if (!g.ok) {
        const llmControlsEl = document.getElementById('llm-controls');
        if (llmControlsEl) llmControlsEl.classList.remove('llm-controls--collapsed');
        if (typeof window.setLlmControlsCollapsed === 'function') {
          window.setLlmControlsCollapsed(false);
        }
        window.addMessage({
          speaker: 'System',
          text: g.reason,
          role: 'error',
          route: 'config',
        });
        throw new Error(g.reason);
      }
    }

    if (typeof window.connectLlmSettings === 'function') {
      try {
        await window.connectLlmSettings();
        if (typeof window.loadHealth === 'function') await window.loadHealth(userIdPre);
        if (typeof window.loadModels === 'function') await window.loadModels(userIdPre);
      } catch (llmErr) {
        throw new Error(`Połączenie LLM nieaktywne: ${llmErr.message}`);
      }
    }

    const resp = await fetch(window.API_CAMPAIGNS, {
      method: 'POST',
      headers: window.getApiHeaders(),
      body: JSON.stringify(payload)
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    window.state.expectCharacterCreationForCampaignId = data.id;
    await window.loadCampaigns(data.id);
    await window.loadCharacters(data.id);
    window.setCampaignModalOpen(false);

    if (campaignCreateFormEl) {
      campaignCreateFormEl.reset();
    }

    window.addMessage({
      speaker: 'System',
      text: `Utworzono kampanię: ${data.title}`,
      role: 'system',
      route: 'campaign'
    });
  } catch (e) {
    window.addMessage({
      speaker: 'Błąd',
      text: `Tworzenie kampanii: ${e.message}`,
      role: 'error'
    });
  } finally {
    window._setCampaignCreationBusy(false);
  }
};

window.deleteCampaign = async function () {
  if (!window.state.selectedCampaignId) {
    alert('Najpierw wybierz kampanię');
    return;
  }

  const campaign = window.currentCampaign();
  const label = campaign?.title || `#${window.state.selectedCampaignId}`;
  const confirmed = confirm(`Usunąć kampanię "${label}"?`);
  if (!confirmed) return;

  const deletingId = window.state.selectedCampaignId;
  try {
    const resp = await fetch(`/api/campaigns/${window.state.selectedCampaignId}`, {
      method: 'DELETE'
    });

    if (!resp.ok) {
      let detail = `HTTP ${resp.status}`;
      try {
        const data = await resp.json();
        detail = data.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }

    window.addMessage({
      speaker: 'System',
      text: `Usunięto kampanię: ${label}`,
      role: 'system',
      route: 'campaign'
    });

    if (
      window.state.expectCharacterCreationForCampaignId != null &&
      Number(window.state.expectCharacterCreationForCampaignId) === Number(deletingId)
    ) {
      window.state.expectCharacterCreationForCampaignId = null;
    }

    await window.loadCampaigns();
    if (window.state.selectedCampaignId) {
      await window.loadCharacters(window.state.selectedCampaignId);
    }
  } catch (e) {
    window.addMessage({
      speaker: 'Błąd',
      text: `Usuwanie kampanii: ${e.message}`,
      role: 'error'
    });
  }
};

window.createCharacterFromForm = async function () {
  const {
    campaignSelectEl,
    characterCreateNameEl,
    characterCreateBackgroundEl,
    characterCreateFormEl,
    characterCreateSubmitEl
  } = window.getEls();

  if (!window.state.selectedCampaignId) {
    alert('Najpierw wybierz kampanię');
    return;
  }

  // Guard against stale local campaign id after refresh/deletions.
  await window.loadCampaigns(window.state.selectedCampaignId);
  let selectedCampaignId = Number(
    campaignSelectEl?.value || window.state.selectedCampaignId || 0
  );
  if (!selectedCampaignId) {
    alert('Najpierw wybierz kampanię');
    return;
  }

  // Preflight campaign validation against backend to avoid hidden stale state.
  try {
    const checkResp = await fetch(`/api/campaigns/${selectedCampaignId}`);
    if (checkResp.status === 404) {
      const listResp = await fetch(window.API_CAMPAIGNS);
      if (listResp.ok) {
        const listData = await listResp.json();
        const campaigns = Array.isArray(listData.campaigns) ? listData.campaigns : [];
        if (campaigns.length > 0) {
          selectedCampaignId = Number(campaigns[0].id);
          window.state.selectedCampaignId = selectedCampaignId;
          if (campaignSelectEl) {
            campaignSelectEl.value = String(selectedCampaignId);
          }
          localStorage.setItem('ai-gm:selectedCampaignId', String(selectedCampaignId));
        } else {
          alert('Brak kampanii. Utwórz najpierw kampanię.');
          return;
        }
      }
    }
  } catch (_) {
    // Continue with currently selected id; submit may still provide concrete backend error.
  }

  const name = (characterCreateNameEl?.value || '').trim();
  const background = (characterCreateBackgroundEl?.value || '').trim();
  const archetypeRaw = characterCreateFormEl?.dataset?.archetype || '';
  const archetype = String(archetypeRaw).toLowerCase();
  const campaign = window.currentCampaign ? window.currentCampaign() : null;
  const campaignSystem = campaign?.system_id || campaign?.systemid || 'fantasy';

  if (!name) {
    alert('Podaj imię postaci');
    characterCreateNameEl?.focus();
    return;
  }
  if (!background) {
    alert('Podaj historię postaci');
    characterCreateBackgroundEl?.focus();
    return;
  }
  if (!archetype || (archetype !== 'warrior' && archetype !== 'scholar')) {
    alert('Wybierz archetyp postaci');
    return;
  }

  const statsBases =
    archetype === 'warrior'
      ? { STR: 12, DEX: 12, CON: 12, INT: 10, WIS: 11, CHA: 10, LCK: 10 }
      : { STR: 10, DEX: 11, CON: 10, INT: 12, WIS: 11, CHA: 10, LCK: 10 };

  const skillsLocked = {
    athletics: archetype === 'warrior' ? 2 : 1,
    stealth: 1,
    sleight_of_hand: 0,
    endurance: 1,
    arcana: archetype === 'scholar' ? 2 : 0,
    investigation: 0,
    lore: archetype === 'scholar' ? 1 : 0,
    awareness: 1,
    survival: 1,
    medicine: 0,
    persuasion: 1,
    intimidation: archetype === 'warrior' ? 1 : 0
  };

  const payload = {
    user_id: window.state?.playerUserId || 1,
    name,
    system_id: campaignSystem,
    sheet_json: {
      archetype,
      background,
      level: 1,
      current_hp: 10,
      max_hp: 10,
      current_mana: 0,
      max_mana: 0,
      stats: statsBases,
      skills: skillsLocked,
      inventory: []
    },
    location: 'Start',
    is_active: 1
  };

  // Bug 3: if we already created a character for this campaign (e.g. player went Back
  // from step 2 to step 1 and hit Create again), reuse that character instead of POSTing again.
  const pendingChar = window.state._wizardPendingCharacter;
  if (
    pendingChar &&
    !pendingChar.finalized &&
    Number(pendingChar.campaignId) === Number(selectedCampaignId)
  ) {
    if (typeof window.enterCharacterCreationWizard === 'function') {
      window.enterCharacterCreationWizard({
        characterId: pendingChar.characterId,
        campaignId: pendingChar.campaignId,
        sheetJson: pendingChar.sheetJson || {},
        characterName: pendingChar.characterName || name
      });
    }
    return;
  }

  window._setCharacterCreationBusy(true);
  const userIdPre = window.state?.playerUserId || 1;
  try {
    try {
      if (typeof window.loadUserLlmSettings === 'function') {
        await window.loadUserLlmSettings(userIdPre);
      }
    } catch (_e) {}

    if (typeof window.computeLlmGate === 'function') {
      const g = window.computeLlmGate();
      if (!g.ok) {
        const llmControlsEl = document.getElementById('llm-controls');
        if (llmControlsEl) llmControlsEl.classList.remove('llm-controls--collapsed');
        if (typeof window.setLlmControlsCollapsed === 'function') {
          window.setLlmControlsCollapsed(false);
        }
        window.addMessage({
          speaker: 'System',
          text: g.reason,
          role: 'error',
          route: 'config',
        });
        throw new Error(g.reason);
      }
    }

    if (typeof window.connectLlmSettings === 'function') {
      try {
        await window.connectLlmSettings();
        if (typeof window.loadHealth === 'function') await window.loadHealth(userIdPre);
        if (typeof window.loadModels === 'function') await window.loadModels(userIdPre);
      } catch (llmErr) {
        throw new Error(`Połączenie LLM nieaktywne: ${llmErr.message}`);
      }
    }

    const resp = await fetch(`/api/campaigns/${selectedCampaignId}/characters`, {
      method: 'POST',
      headers: window.getApiHeaders(),
      body: JSON.stringify(payload)
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    await window.loadCharacters(selectedCampaignId, data.id);
    window.updateUiState();

    window.addMessage({
      speaker: 'System',
      text: `Utworzono postać: ${data.name}`,
      role: 'system',
      route: 'character'
    });

    if (typeof window.enterCharacterCreationWizard === 'function') {
      // Bug 3: store pending character so Back → re-submit reuses this character
      window.state._wizardPendingCharacter = {
        characterId: data.id,
        campaignId: selectedCampaignId,
        sheetJson: data.sheet_json || {},
        characterName: data.name || name,
        finalized: false
      };
      window._persistWizardPendingSession();
      window.enterCharacterCreationWizard({
        characterId: data.id,
        campaignId: selectedCampaignId,
        sheetJson: data.sheet_json || {},
        openingMessage: data.opening_message || null,
        characterName: data.name || name
      });
    } else {
      await window.loadTurns(selectedCampaignId);
      window.setCharacterModalOpen(false);
      window.updateUiState();
      if (characterCreateFormEl) {
        characterCreateFormEl.reset();
        characterCreateFormEl.dataset.archetype = '';
      }
      document.querySelectorAll('.archetype-card').forEach((card) => {
        card.classList.remove('selected');
      });
      const hasOpeningInTurns =
        Array.isArray(window.state.turns) &&
        window.state.turns.some(
          (turn) => String(turn.assistant_text || '').trim() === String(data.opening_message || '').trim()
        );
      if (data.opening_message && !hasOpeningInTurns) {
        window.addMessage({
          speaker: window.t('chat.gm'),
          text: data.opening_message,
          role: 'assistant',
          route: 'narrative'
        });
      } else if (data.opening_message) {
        window.renderTurnsToChat();
      }
    }

    const { inputEl } = window.getEls();
    if (inputEl && !window.state.charCreationWizard) {
      inputEl.focus();
    }
  } catch (e) {
    alert(`Tworzenie postaci nie powiodło się: ${e.message}`);
    window.addMessage({
      speaker: 'Błąd',
      text: `Tworzenie postaci: ${e.message}`,
      role: 'error'
    });
  } finally {
    window._setCharacterCreationBusy(false);
  }
};

/**
 * When no narrative GM turn exists yet (e.g. opening generation failed at creation),
 * send one minimal user line to start the story. Skips if history already has GM text.
 */
window.requestGmOpeningIfQuiet = async function (campaignId, characterId) {
  if (!campaignId || !characterId) return;
  if (window.chatRequestState?.inFlight) return;
  const turns = window.state.turns || [];
  if (
    turns.some(
      (t) =>
        t.route === 'narrative' && String(t.assistant_text || '').trim().length > 0
    )
  ) {
    return;
  }
  const { inputEl } = window.getEls();
  const lang = window.state?.lang === 'en' ? 'en' : 'pl';
  const starter =
    lang === 'en'
      ? 'I take in my surroundings and decide how to act.'
      : 'Patrzę wokół i rozważam, co zrobić dalej.';
  if (inputEl) inputEl.value = starter;
  await window.sendMessage();
};

window.sendMessage = async function () {
  const { inputEl, systemSelectEl, engineSelectEl, sendBtnEl } = window.getEls();

  if (window.chatRequestState?.inFlight) {
    return;
  }

  const suppressUserBubble = !!window.__suppressNextUserBubbleForGm;
  if (window.__suppressNextUserBubbleForGm) {
    window.__suppressNextUserBubbleForGm = false;
  }

  const pendingLine = window.__pendingNarrativeUserTextForApi;
  if (pendingLine != null) {
    window.__pendingNarrativeUserTextForApi = null;
  }

  let text = (inputEl.value || "").trim();
  if (pendingLine != null) {
    text = String(pendingLine);
  }
  if (!text) return;

  const clientCreatedAt = new Date().toISOString();

  const restorePendingLine = () => {
    if (pendingLine != null) {
      window.__pendingNarrativeUserTextForApi = pendingLine;
    }
  };

  if (!window.state.selectedCampaignId) {
    restorePendingLine();
    window.addMessage({
      speaker: 'System',
      text: window.t('error.no_campaign'),
      role: 'error',
      createdAt: clientCreatedAt
    });
    return;
  }

  if (!window.state.selectedCharacterId) {
    restorePendingLine();
    window.addMessage({
      speaker: 'System',
      text: window.t('error.no_character'),
      role: 'error',
      createdAt: clientCreatedAt
    });
    return;
  }

  const combatStartMatch = text.trim().match(/^\/(?:walka|atak)\s+(.+)$/i);
  if (combatStartMatch) {
    if (!window.isPublicSlashCommandEnabled('/atak')) {
      window.addMessage({
        speaker: 'System',
        text: 'Ta komenda czatu jest wyłączona przez administratora.',
        role: 'error',
        createdAt: clientCreatedAt
      });
      inputEl.value = '';
      return;
    }
    const rawKeys = String(combatStartMatch[1] || '')
      .split(/[,\s]+/)
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
    if (!rawKeys.length) {
      window.addMessage({
        speaker: 'System',
        text:
          'Aby rozpocząć walkę w silniku, podaj klucze wrogów: np. /atak bandit lub /walka bandit,wolf. ' +
          'Samo /atak lub /walka (bez argumentów) pobiera stan aktywnej walki.',
        role: 'error',
        createdAt: clientCreatedAt
      });
      inputEl.value = '';
      return;
    }
    try {
      const resp = await fetch(
        `/api/campaigns/${window.state.selectedCampaignId}/combat/start`,
        {
          method: 'POST',
          headers: window.getApiHeaders(),
          body: JSON.stringify({
            enemy_keys: rawKeys,
            character_id: window.state.selectedCharacterId
          })
        }
      );
      const data = await resp.json().catch(() => ({}));
      if (resp.status === 409) {
        const d = typeof data.detail === 'string' ? data.detail : 'Walka już trwa.';
        window.addMessage({
          speaker: 'System',
          text: d,
          role: 'error',
          createdAt: clientCreatedAt
        });
        inputEl.value = '';
        return;
      }
      if (!resp.ok) {
        const detail = data.detail || data.message || `HTTP ${resp.status}`;
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }
      window.addMessage({
        speaker: 'System',
        text:
          `Walka w silniku: START vs ${rawKeys.join(', ')}. ` +
          (data.current_turn === 'player'
            ? 'Twoja tura — użyj przycisku Atak lub narracji zgodnej z panelem walki.'
            : 'Sesja aktywna — sprawdź panel „Walka”.'),
        role: 'system',
        createdAt: clientCreatedAt
      });
      inputEl.value = '';
      await window.loadTurns(window.state.selectedCampaignId);
    } catch (e) {
      window.addMessage({
        speaker: 'Błąd',
        text: `Rozpoczęcie walki: ${e.message || e}`,
        role: 'error',
        createdAt: clientCreatedAt
      });
      inputEl.value = '';
    }
    return;
  }

  if (/^\/search(\s|$)/i.test(text.trim())) {
    if (!window.isPublicSlashCommandEnabled('/search')) {
      window.addMessage({
        speaker: 'System',
        text: 'Ta komenda czatu jest wyłączona przez administratora.',
        role: 'error',
        createdAt: clientCreatedAt
      });
      inputEl.value = '';
      return;
    }
    const combatState = window.combatPanel?._state || null;
    if (combatState && String(combatState.status || '') === 'active') {
      window.addMessage({
        speaker: 'System',
        text: 'Nie możesz użyć /search w trakcie aktywnej walki.',
        role: 'error',
        createdAt: clientCreatedAt
      });
      return;
    }

    const target = text.replace(/^\/search\s*/i, '').trim() || null;

    inputEl.value = '';
    window.chatRequestState.inFlight = true;
    const requestId = ++window.chatRequestState.requestId;
    const turnNumber = window.nextTurnNumber?.() ?? Date.now();
    if (sendBtnEl) sendBtnEl.disabled = true;
    inputEl.disabled = true;

    const speakerName =
      typeof window.currentCharacterName === 'function'
        ? window.currentCharacterName()
        : 'Gracz';

    window.addMessage({
      speaker: speakerName,
      text: text.trim(),
      role: 'user',
      route: 'narrative',
      turn: turnNumber,
      createdAt: clientCreatedAt
    });

    window.removeThinkingBubble?.();
    window.showThinkingBubble?.({
      speaker: window.t?.('chat.gm') ?? 'GM',
      route: 'narrative',
      turn: turnNumber
    });

    try {
      const resp = await fetch(
        `/api/campaigns/${window.state.selectedCampaignId}/search`,
        {
          method: 'POST',
          headers: window.getApiHeaders(),
          body: JSON.stringify({
            character_id: window.state.selectedCharacterId,
            target: target,
            context: window.state._lastKilledEnemy || null
          })
        }
      );
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail ?? data.message ?? `HTTP ${resp.status}`);
      if (requestId !== window.chatRequestState.requestId) return;

      window.removeThinkingBubble?.();
      window.state._lastKilledEnemy = null;

      window.addMessage({
        speaker: window.t?.('chat.gm') ?? 'GM',
        text: data.answer || data.message || '',
        role: 'assistant',
        route: 'narrative',
        turn: data.turn_number || turnNumber,
        createdAt: data.created_at || null
      });

      await window.loadTurns?.(window.state.selectedCampaignId);
    } catch (e) {
      if (requestId !== window.chatRequestState.requestId) return;
      window.removeThinkingBubble?.();
      window.addMessage({
        speaker: window.t?.('chat.gm') ?? 'GM',
        text: `❌ Błąd przeszukiwania: ${e.message}`,
        role: 'assistant',
        route: 'narrative',
        turn: turnNumber
      });
    } finally {
      if (requestId === window.chatRequestState.requestId) {
        window.chatRequestState.inFlight = false;
        if (sendBtnEl) sendBtnEl.disabled = false;
        if (inputEl) {
          inputEl.disabled = false;
          inputEl.focus();
        }
      }
    }
    return;
  }

  if (/^\/mem(\s|$)/i.test(text.trim())) {
    if (!window.isPublicSlashCommandEnabled('/mem [pytanie]')) {
      window.addMessage({
        speaker: 'System',
        text: 'Ta komenda czatu jest wyłączona przez administratora.',
        role: 'error',
        createdAt: clientCreatedAt
      });
      inputEl.value = '';
      return;
    }
    const question = text.replace(/^\/mem\s*/i, '').trim();
    if (!question) {
      window.addMessage({
        speaker: 'System',
        text: 'Użyj: /mem [pytanie] — odpowiedź bazuje na zapisanym podsumowaniu (nie zmienia fabuły).',
        role: 'error',
        createdAt: clientCreatedAt
      });
      inputEl.value = '';
      return;
    }

    window.chatRequestState.inFlight = true;
    const requestId = ++window.chatRequestState.requestId;
    const turnNumber = window.nextTurnNumber();
    inputEl.value = '';

    if (sendBtnEl) sendBtnEl.disabled = true;
    inputEl.disabled = true;

    window.addMessage({
      speaker: window.currentCharacterName(),
      text: text.trim(),
      role: 'user',
      route: 'memory',
      turn: turnNumber,
      createdAt: clientCreatedAt,
      memoryTurn: true
    });

    window.removeThinkingBubble();
    window.showThinkingBubble({
      speaker: window.t('chat.gm'),
      route: 'memory',
      turn: turnNumber
    });

    try {
      const uid = window.state?.playerUserId || 1;
      const resp = await fetch(
        `/api/campaigns/${window.state.selectedCampaignId}/memory/ask?user_id=${encodeURIComponent(uid)}`,
        {
          method: 'POST',
          headers: window.getApiHeaders(),
          body: JSON.stringify({
            character_id: window.state.selectedCharacterId,
            question: question,
            user_line: text.trim()
          })
        }
      );
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const detail = data.detail || data.message || `HTTP ${resp.status}`;
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }
      if (requestId !== window.chatRequestState.requestId) return;

      window.removeThinkingBubble();
      window.addMessage({
        speaker: window.t('chat.gm'),
        text: data.answer || '',
        role: 'assistant',
        route: 'memory',
        turn: data.turn_number || turnNumber,
        createdAt: data.created_at || null,
        memoryTurn: true
      });
      await window.loadTurns(window.state.selectedCampaignId);
    } catch (e) {
      if (requestId !== window.chatRequestState.requestId) return;
      window.removeThinkingBubble();
      const pretty = typeof window.prettyLlmErrorMessage === 'function'
        ? window.prettyLlmErrorMessage(e.message)
        : e.message;
      window.addMessage({
        speaker: 'Błąd',
        text: pretty,
        role: 'error',
        turn: turnNumber
      });
    } finally {
      if (requestId === window.chatRequestState.requestId) {
        window.chatRequestState.inFlight = false;
      }
      if (sendBtnEl) sendBtnEl.disabled = false;
      if (inputEl) {
        inputEl.disabled = false;
        inputEl.focus();
      }
    }
    return;
  }

  if (/^\/helpme(\s|$)/i.test(text.trim())) {
    if (!window.isPublicSlashCommandEnabled('/helpme [pytanie]')) {
      window.addMessage({
        speaker: 'System',
        text: 'Ta komenda czatu jest wyłączona przez administratora.',
        role: 'error',
        createdAt: clientCreatedAt
      });
      inputEl.value = '';
      return;
    }
    const topic = text.replace(/^\/helpme\s*/i, '').trim();

    window.chatRequestState.inFlight = true;
    const requestId = ++window.chatRequestState.requestId;
    const turnNumber = window.nextTurnNumber();
    inputEl.value = '';

    if (sendBtnEl) sendBtnEl.disabled = true;
    inputEl.disabled = true;

    window.addMessage({
      speaker: window.currentCharacterName(),
      text: text.trim(),
      role: 'user',
      route: 'helpme',
      turn: turnNumber,
      createdAt: clientCreatedAt,
      helpmeTurn: true
    });

    window.removeThinkingBubble();
    window.showThinkingBubble({
      speaker: window.t('chat.gm'),
      route: 'helpme',
      turn: turnNumber
    });

    try {
      const uid = window.state?.playerUserId || 1;
      const resp = await fetch(
        `/api/campaigns/${window.state.selectedCampaignId}/helpme?user_id=${encodeURIComponent(uid)}`,
        {
          method: 'POST',
          headers: window.getApiHeaders(),
          body: JSON.stringify({
            character_id: window.state.selectedCharacterId,
            topic: topic,
            user_line: text.trim()
          })
        }
      );
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const detail = data.detail || data.message || `HTTP ${resp.status}`;
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }
      if (requestId !== window.chatRequestState.requestId) return;

      window.removeThinkingBubble();
      window.addMessage({
        speaker: window.t('chat.gm'),
        text: data.answer || '',
        role: 'assistant',
        route: 'helpme',
        turn: data.turn_number || turnNumber,
        createdAt: data.created_at || null,
        helpmeTurn: true,
        oocTurn: !!data.ooc
      });
      if (!Array.isArray(window.state.helpmeLog)) window.state.helpmeLog = [];
      window.state.helpmeLog.push({
        turn_number: data.turn_number || turnNumber,
        user_text: text.trim(),
        assistant_text: data.answer || '',
        created_at: data.created_at || clientCreatedAt
      });
      await window.loadTurns(window.state.selectedCampaignId);
    } catch (e) {
      if (requestId !== window.chatRequestState.requestId) return;
      window.removeThinkingBubble();
      const pretty = typeof window.prettyLlmErrorMessage === 'function'
        ? window.prettyLlmErrorMessage(e.message)
        : e.message;
      window.addMessage({
        speaker: 'Błąd',
        text: pretty,
        role: 'error',
        turn: turnNumber
      });
    } finally {
      if (requestId === window.chatRequestState.requestId) {
        window.chatRequestState.inFlight = false;
      }
      if (sendBtnEl) sendBtnEl.disabled = false;
      if (inputEl) {
        inputEl.disabled = false;
        inputEl.focus();
      }
    }
    return;
  }

  const streamSlashKey =
    typeof window.slashRegistryKeyForChatClient === 'function'
      ? window.slashRegistryKeyForChatClient(text)
      : null;
  if (streamSlashKey && !window.isPublicSlashCommandEnabled(streamSlashKey)) {
    restorePendingLine();
    window.addMessage({
      speaker: 'System',
      text: 'Ta komenda czatu jest wyłączona przez administratora.',
      role: 'error',
      createdAt: clientCreatedAt
    });
    return;
  }

  const selectedEngine =
    String(window.state.selectedEngine || '').trim() ||
    String(engineSelectEl?.value || '').trim() ||
    String(window.state.models?.[0]?.name || '').trim() ||
    '';

  if (!selectedEngine) {
    restorePendingLine();
    window.addMessage({
      speaker: 'System',
      text: 'Nie wybrano modelu.',
      role: 'error',
      createdAt: clientCreatedAt
    });
    return;
  }

  window.chatRequestState.inFlight = true;
  const requestId = ++window.chatRequestState.requestId;

  if (sendBtnEl) sendBtnEl.disabled = true;
  inputEl.disabled = true;

  // Powrót do narracji — chowamy wszystkie dymki archiwalne (OOC / mem / system / błędy / separator).
  if (typeof window.setShowArchiveBubbles === 'function') {
    window.setShowArchiveBubbles(false);
  }

  let turnNumber = window.nextTurnNumber();

  let textToSend = text;
  if (/^\/roll\b/i.test(textToSend)) {
    const hasExplicitDc = /\bdc\s+\d+\s*$/i.test(textToSend);
    const pending = window.state.pendingRoll;
    if (
      !hasExplicitDc &&
      pending &&
      pending.dc != null &&
      Number.isFinite(Number(pending.dc))
    ) {
      textToSend = `${textToSend} dc ${pending.dc}`;
    }
  }

  // Show user message (skipped when combat attack card was already inserted in UI)
  if (!suppressUserBubble) {
    window.addMessage({
      speaker: window.currentCharacterName(),
      text,
      role: 'user',
      route: 'input',
      turn: turnNumber,
      createdAt: clientCreatedAt
    });
  }

  inputEl.value = '';

  // Show thinking bubble immediately — before fetch even starts
  window.removeThinkingBubble();
  window.showThinkingBubble({
    speaker: window.t('chat.gm'),
    route: 'narrative',
    turn: turnNumber
  });

  try {
    const payload = {
      character_id: window.state.selectedCharacterId,
      text: textToSend,
      system: systemSelectEl.value,
      engine: selectedEngine,
      game_id: window.state.selectedCampaignId
    };

    // Thinking bubble stays visible while waiting for response headers.
    // On first real token it swaps to the streaming bubble.
    const resp = await fetch(
      `/api/campaigns/${window.state.selectedCampaignId}/turns/stream`,
      {
        method: 'POST',
        headers: window.getApiHeaders(),
        body: JSON.stringify(payload)
      }
    );

    if (resp.status === 410) {
      window.removeThinkingBubble();
      if (typeof window.showCampaignDeathScreen === 'function') {
        await window.showCampaignDeathScreen(window.state.selectedCampaignId);
      }
      return;
    }

    if (!resp.ok) {
      let detail = `HTTP ${resp.status}`;
      try {
        const errData = await resp.json();
        detail = errData.detail || errData.error || detail;
      } catch (_) {}
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }

    if (requestId !== window.chatRequestState.requestId) return;

    // Read SSE stream.
    // IMPORTANT: SSE lines are separated by real newline characters (\n).
    // We must split on the actual newline char — NOT the two-char sequence \\n.
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';
    let streamBubble = null; // created lazily on first real token
    let streamDone = false;

    const applyCombatStartedSseToken = (token) => {
      if (!token || !token.startsWith('[COMBAT_STARTED]')) return false;
      const raw = token.slice('[COMBAT_STARTED]'.length);
      try {
        const cs = JSON.parse(raw);
        if (typeof window.combatPanel?.render === 'function') {
          window.combatPanel.render(cs);
        }
        if (typeof window.combatInput?.syncWithCombat === 'function') {
          window.combatInput.syncWithCombat(cs);
        }
        if (typeof window.combatPanel?.show === 'function') {
          window.combatPanel.show();
        }
        if (typeof window.addMessage === 'function') {
          const enemies = (cs.combatants || [])
            .filter((c) => c.type === 'enemy')
            .map((c) => c.name)
            .join(', ');
          window.addMessage({
            speaker: 'System',
            text: `⚔ Walka rozpoczęta! Przeciwnicy: ${enemies}. Twoja tura.`,
            role: 'system',
            turn: turnNumber
          });
        }
      } catch (_e) {
        /* ignore malformed payload */
      }
      return true;
    };

    const applyCombatSseToken = (token) => {
      if (!token || !token.startsWith('[COMBAT]')) return false;
      if (token.startsWith('[COMBAT_STARTED]')) return false;
      const raw = token.slice('[COMBAT]'.length);
      try {
        const comb = JSON.parse(raw);
        if (
          comb.new_combat_turn &&
          comb.new_combat_turn !== 'ended' &&
          typeof window.combatInput?.syncWithCombat === 'function'
        ) {
          window.combatInput.syncWithCombat({
            status: 'active',
            current_turn: comb.new_combat_turn,
          });
        }
      } catch (_e) {
        /* ignore malformed combat payload */
      }
      return true;
    };

    const applyGmRollSseToken = (token) => {
      if (!token || !token.startsWith('[GM_ROLL]')) return false;
      try {
        const rollData = JSON.parse(token.slice('[GM_ROLL]'.length));
        if (typeof window.addGmRollBubble === 'function') {
          window.addGmRollBubble(rollData, turnNumber);
        }
      } catch (e) {
        console.warn('GM_ROLL parse error', e);
      }
      return true;
    };

    const applyCombatEndedSseToken = (token) => {
      if (!token || !token.startsWith('[COMBAT_ENDED]')) return false;
      try {
        const data = JSON.parse(token.slice('[COMBAT_ENDED]'.length));
        window.state._combatJustEnded = true;
        window.state._lastKilledEnemy = data;
        window.state._combatVictoryUiPending = true;
      } catch (_e) {
        /* ignore */
      }
      return true;
    };

    const applyCmdJsonToken = (token) => {
      if (!token || !token.startsWith('[CMD_JSON]')) return false;
      try {
        const payload = JSON.parse(token.slice('[CMD_JSON]'.length));
        const res = payload.result || {};
        window.removeThinkingBubble();
        if (res.command === 'atak') {
          if (res.combat_active && res.combat_state) {
            if (typeof window.combatPanel?.render === 'function') {
              window.combatPanel.render(res.combat_state);
            }
            if (typeof window.combatInput?.syncWithCombat === 'function') {
              window.combatInput.syncWithCombat(res.combat_state);
            }
            if (typeof window.combatPanel?.show === 'function') {
              window.combatPanel.show();
            }
          }
          const msg = res.feature_disabled
            ? (res.message || 'Ta funkcja jest wyłączona przez administratora.')
            : res.combat_active
              ? 'Stan walki zsynchronizowany z silnikiem.'
              : (res.message || 'Nie trwa żadna walka.');
          window.addMessage({
            speaker: 'System',
            text: msg,
            role: 'system',
            turn: turnNumber
          });
        }
        void window.loadTurns(window.state.selectedCampaignId);
      } catch (_e) {
        /* ignore malformed payload */
      }
      return true;
    };

    while (!streamDone) {
      const { done, value } = await reader.read();

      if (done) {
        // Flush any remaining data in buffer
        if (buffer.trim()) {
          const remaining = buffer.trim();
          if (remaining.startsWith('data: ')) {
            const token = remaining.slice(6);
            if (applyCombatStartedSseToken(token)) {
              /* skip */
            } else if (applyCombatSseToken(token)) {
              /* skip */
            } else if (applyGmRollSseToken(token)) {
              /* skip */
            } else if (applyCombatEndedSseToken(token)) {
              /* skip */
            } else if (applyCmdJsonToken(token)) {
              /* skip */
            } else if (token !== '[DONE]' && !token.startsWith('[ERROR]')) {
              // Unescape literal \n sequences the server may have encoded
              const realToken = token.replace(/\\n/g, '\n');
              fullText += realToken;
              if (!streamBubble) {
                streamBubble = window.createStreamingBubble({
                  speaker: window.t('chat.gm'),
                  route: 'narrative',
                  turn: turnNumber
                });
              }
              window.appendToStreamingBubble(streamBubble, realToken);
            }
          }
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // Split on REAL newline characters — SSE protocol uses \n as line separator.
      // Using a string literal '\n' (one char) is correct here.
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete last line in buffer

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const token = line.slice(6);

        if (applyCombatStartedSseToken(token)) {
          continue;
        }

        if (applyCombatSseToken(token)) {
          continue;
        }

        if (applyGmRollSseToken(token)) {
          continue;
        }

        if (applyCombatEndedSseToken(token)) {
          continue;
        }

        if (applyCmdJsonToken(token)) {
          continue;
        }

        if (token === '[DONE]') {
          const cleanedGm = fullText.replace(/\[COMBAT_START:[^\]]*\]/gi, '').trimEnd();
          if (streamBubble) {
            window.finalizeStreamingBubble(streamBubble, cleanedGm);
          } else {
            window.removeThinkingBubble();
          }
          if (
            window.state._combatVictoryUiPending &&
            window.state._lastKilledEnemy &&
            typeof window.combatPanel?.showVictoryAfterNarration === 'function'
          ) {
            window.state._combatVictoryUiPending = false;
            if (
              typeof window.consumeCombatJustEndedGuard === 'function' &&
              window.consumeCombatJustEndedGuard()
            ) {
              if (typeof window.combatPanel?.cancelDeferredVictoryUi === 'function') {
                window.combatPanel.cancelDeferredVictoryUi();
              }
            } else {
              window.combatPanel.showVictoryAfterNarration(window.state._lastKilledEnemy);
            }
          }
          await window.loadTurns(window.state.selectedCampaignId);
          streamDone = true;
          break;
        }

        if (token.startsWith('[ERROR]')) {
          const errMsg = token.slice(8) || 'Nieznany błąd';
          const pretty = typeof window.prettyLlmErrorMessage === 'function'
            ? window.prettyLlmErrorMessage(errMsg)
            : errMsg;
          if (streamBubble) {
            window.finalizeStreamingBubble(streamBubble, `⚠️ ${pretty}`);
          } else {
            window.removeThinkingBubble();
            window.addMessage({
              speaker: 'Błąd',
              text: `⚠️ ${pretty}`,
              role: 'error',
              turn: turnNumber
            });
          }
          streamDone = true;
          break;
        }

        // Normal token — unescape literal \n sequences the server may encode
        const realToken = token.replace(/\\n/g, '\n');
        fullText += realToken;

        // Lazy bubble creation: thinking stays until first real token
        if (!streamBubble) {
          streamBubble = window.createStreamingBubble({
            speaker: window.t('chat.gm'),
            route: 'narrative',
            turn: turnNumber
          });
        }

        window.appendToStreamingBubble(streamBubble, realToken);
      }
    }

    // Stream ended without [DONE] — finalize gracefully
    if (!streamDone) {
      if (streamBubble) {
        const cleanedGm = fullText.replace(/\[COMBAT_START:[^\]]*\]/gi, '').trimEnd();
        window.finalizeStreamingBubble(streamBubble, cleanedGm);
        if (
          window.state._combatVictoryUiPending &&
          window.state._lastKilledEnemy &&
          typeof window.combatPanel?.showVictoryAfterNarration === 'function'
        ) {
          window.state._combatVictoryUiPending = false;
          if (
            typeof window.consumeCombatJustEndedGuard === 'function' &&
            window.consumeCombatJustEndedGuard()
          ) {
            if (typeof window.combatPanel?.cancelDeferredVictoryUi === 'function') {
              window.combatPanel.cancelDeferredVictoryUi();
            }
          } else {
            window.combatPanel.showVictoryAfterNarration(window.state._lastKilledEnemy);
          }
        }
        await window.loadTurns(window.state.selectedCampaignId);
      } else {
        window.removeThinkingBubble();
      }
    }

  } catch (e) {
    if (requestId !== window.chatRequestState.requestId) return;

    window.removeThinkingBubble();
    const pretty = typeof window.prettyLlmErrorMessage === 'function'
      ? window.prettyLlmErrorMessage(e.message)
      : e.message;
    window.addMessage({
      speaker: 'Błąd',
      text: `Serwer: ${pretty}`,
      role: 'error',
      turn: turnNumber
    });
  } finally {
    if (requestId === window.chatRequestState.requestId) {
      window.chatRequestState.inFlight = false;
    }

    const { sendBtn, inputEl: inp } = window.getEls();
    if (sendBtn) sendBtn.disabled = false;
    if (inp) { inp.disabled = false; inp.focus(); }
  }
};

/**
 * Narracja GM przez SSE z gotowym user_text (np. JSON pod COMBAT_ROLL prefix),
 * bez dymku gracza — ten sam mechanizm co po ataku / ucieczce z panelu walki.
 */
window.triggerCombatNarration = async function (userText) {
  if (typeof window.sendMessage !== 'function') return;
  const s = typeof userText === 'string' ? userText.trim() : '';
  if (!s) return;
  const { inputEl } = window.getEls();
  if (inputEl) inputEl.value = '';
  window.__pendingNarrativeUserTextForApi = s;
  window.__suppressNextUserBubbleForGm = true;
  await window.sendMessage();
};

window.rollDice = async function () {
  const dice = prompt('Kość (d20, 2d6+3, d100):', '1d20');
  if (!dice) return;

  try {
    const resp = await fetch('/api/gm/dice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dice })
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    window.addMessage({
      speaker: '🎲',
      text: `${data.dice} = [${data.rolls.join(', ')}] = ${data.total}`,
      role: 'system'
    });
  } catch (e) {
    window.addMessage({
      speaker: 'Błąd',
      text: `Kość: ${e.message}`,
      role: 'error'
    });
  }
};
