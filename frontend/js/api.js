window.loadTranslations = async function (lang) {
  const resp = await fetch(`/i18n/${lang}.json`);
  if (!resp.ok) throw new Error(`Translation load failed: ${resp.status}`);
  window.state.translations = await resp.json();
  window.state.lang = lang;
  window.applyTranslations();
};

window.loadHealth = async function () {
  const {
    statusBackendDotEl,
    statusOllamaDotEl
  } = window.getEls();

  const setDotState = (dotEl, state, title) => {
    if (!dotEl) return;
    dotEl.classList.remove('ok', 'warn', 'error', 'unknown');
    dotEl.classList.add(state);
    if (title) dotEl.title = title;
  };

  try {
    const resp = await fetch(window.API_HEALTH);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    setDotState(statusBackendDotEl, 'ok', 'Backend: OK');
    setDotState(
      statusOllamaDotEl,
      data.llm?.reachable ? 'ok' : 'warn',
      `LLM: ${data.llm?.reachable ? 'OK' : window.t('status.disconnected')}`
    );
  } catch (e) {
    setDotState(statusBackendDotEl, 'error', `Backend: ${window.t('health.fail')}`);
    setDotState(statusOllamaDotEl, 'error', `Ollama: ${window.t('status.disconnected')}`);
  }
};

window.loadModels = async function () {
  const { engineSelectEl } = window.getEls();
  const provider = String(window.state.llmSettings?.provider || '').toLowerCase();
  const wantAll = provider === 'openai' && !!window.state.showAllProviderModels;
  const modelsUrl = wantAll ? `${window.API_MODELS}?show_all=1` : window.API_MODELS;

const resp = await fetch(modelsUrl);
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const data = await resp.json();
      detail = data.detail || detail;
    } catch (_err) {}
    throw new Error(window.prettyLlmErrorMessage(detail));
  }

  const data = await resp.json();

  window.state.models = Array.isArray(data.models)
    ? data.models
    : Array.isArray(data)
      ? data
      : [];

  engineSelectEl.innerHTML = '';

  if (window.state.models.length === 0) {
    const fallbackOption = document.createElement('option');
    fallbackOption.value = 'gemma4:e4b';
    fallbackOption.textContent = 'gemma4:e4b';
    engineSelectEl.appendChild(fallbackOption);
    engineSelectEl.value = 'gemma4:e4b';
    window.state.selectedEngine = 'gemma4:e4b';
    return;
  }

  window.state.models.forEach(model => {
    const name = typeof model === 'string' ? model : model.name;
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    engineSelectEl.appendChild(option);
  });

  const savedEngine = localStorage.getItem('ai-gm:selectedEngine');
  const preferredFromRuntime = (window.state.llmSettings && window.state.llmSettings.model) || '';
  const preferredEngine =
    window.state.selectedEngine ||
    preferredFromRuntime ||
    savedEngine ||
    window.state.models[0].name ||
    window.state.models[0];

  const exists = window.state.models.some(model => {
    const name = typeof model === 'string' ? model : model.name;
    return name === preferredEngine;
  });

  window.state.selectedEngine = exists
    ? preferredEngine
    : (typeof window.state.models[0] === 'string'
        ? window.state.models[0]
        : window.state.models[0].name);

  engineSelectEl.value = window.state.selectedEngine;
};

window.loadCampaigns = async function (preferredCampaignId = null) {
  const { campaignSelectEl, characterSelectEl } = window.getEls();

const resp = await fetch(window.API_CAMPAIGNS);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

  const data = await resp.json();
  window.state.campaigns = Array.isArray(data.campaigns)
  ? data.campaigns.map(c => ({
      ...c,
      systemid: c.systemid ?? c.system_id,
      modelid: c.modelid ?? c.model_id,
      owneruserid: c.owneruserid ?? c.owner_user_id,
      createdat: c.createdat ?? c.created_at
    }))
  : [];

  campaignSelectEl.innerHTML = '';

  if (window.state.campaigns.length === 0) {
    campaignSelectEl.innerHTML = '<option value="" disabled selected>Brak kampanii</option>';
    campaignSelectEl.disabled = true;

    window.state.selectedCampaignId = null;
    window.state.characters = [];
    window.state.selectedCharacterId = null;

    characterSelectEl.innerHTML = '<option value="" disabled selected>Brak postaci</option>';
    characterSelectEl.disabled = true;

    window.updateUiState();
    return;
  }

  campaignSelectEl.disabled = false;

  window.state.campaigns.forEach(campaign => {
    const option = document.createElement('option');
    option.value = String(campaign.id);
    option.textContent = campaign.title;
    campaignSelectEl.appendChild(option);
  });

  const savedCampaignId = Number(localStorage.getItem('ai-gm:selectedCampaignId'));
  const candidateId = preferredCampaignId || savedCampaignId;

  const selectedId = candidateId && window.state.campaigns.some(
    c => Number(c.id) === Number(candidateId)
  )
    ? Number(candidateId)
    : Number(window.state.campaigns[0].id);

  window.state.selectedCampaignId = selectedId;
  campaignSelectEl.value = String(selectedId);

  window.updateUiState();
};


window.loadCharacters = async function (campaignId, preferredCharacterId = null) {
  const { characterSelectEl } = window.getEls();

  if (!campaignId) {
    window.state.characters = [];
    window.state.selectedCharacterId = null;
    characterSelectEl.innerHTML = '<option value="" disabled selected>Brak postaci</option>';
    characterSelectEl.disabled = true;
    window.updateUiState();
    return;
  }

  const resp = await fetch(`/api/campaigns/${campaignId}/characters`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

  const data = await resp.json();
  window.state.characters = Array.isArray(data.characters) ? data.characters : [];
  characterSelectEl.innerHTML = '';

  if (window.state.characters.length === 0) {
    characterSelectEl.innerHTML =
      `<option value="" disabled selected>${window.escapeHtml(window.t('empty.characters'))}</option>`;
    characterSelectEl.disabled = true;
    window.state.selectedCharacterId = null;
    window.updateUiState();
    return;
  }

  characterSelectEl.disabled = false;

  window.state.characters.forEach(character => {
    const option = document.createElement('option');
    option.value = String(character.id);
    option.textContent = character.name;
    characterSelectEl.appendChild(option);
  });

  const savedCharacterId = Number(localStorage.getItem('ai-gm:selectedCharacterId'));
  const candidateId = preferredCharacterId || savedCharacterId;

  const selectedId = candidateId && window.state.characters.some(
    c => Number(c.id) === Number(candidateId)
  )
    ? Number(candidateId)
    : Number(window.state.characters[0].id);

  window.state.selectedCharacterId = selectedId;
  characterSelectEl.value = String(selectedId);

  window.updateUiState();
};

window.loadTurns = async function (campaignId, limit = 30) {
  if (!campaignId) {
    window.state.turns = [];
    window.clearChat();
    window.clearHistoryPanel();
    return;
  }

  const resp = await fetch(`/api/campaigns/${campaignId}/turns?limit=${limit}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

  const data = await resp.json();
  window.state.turns = Array.isArray(data.turns) ? data.turns : [];

  if (window.state.turns.length > 0) {
    const lastTurn = window.state.turns[window.state.turns.length - 1];
    window.state.turnNumber = Number(lastTurn.turn_number || lastTurn.id || 0);
  } else {
    window.state.turnNumber = 0;
  }

  window.renderTurnsToChat();
  window.renderHistoryPanel();
};

window.getApiHeaders = function () {
  return {
    'Content-Type': 'application/json'
  };
};