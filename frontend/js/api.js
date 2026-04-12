window.loadTranslations = async function (lang) {
  const resp = await fetch(`/i18n/${lang}.json`);
  if (!resp.ok) throw new Error(`Translation load failed: ${resp.status}`);
  window.state.translations = await resp.json();
  window.state.lang = lang;
  window.applyTranslations();
};

window.loadHealth = async function () {
  const {
    statusBackendEl,
    statusOllamaEl,
    statusModelsEl,
    statusHostEl
  } = window.getEls();

  try {
    const resp = await fetch(window.API_HEALTH, {
  headers: { 'X-Ollama-Base-Url': window.getOllamaBaseUrl() }
});
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    statusBackendEl.textContent = `${window.t('status.backend')}: OK`;
    statusOllamaEl.textContent =
      `${window.t('status.ollama')}: ${data.ollama?.reachable ? 'OK' : window.t('status.disconnected')}`;
    statusModelsEl.textContent =
      `${window.t('status.models')}: ${data.ollama?.model_count ?? 0}`;
    statusHostEl.textContent =
      `${window.t('health.host')}: ${data.ollama?.base_url || '-'}`;
  } catch (e) {
    statusBackendEl.textContent = `${window.t('status.backend')}: ${window.t('health.fail')}`;
    statusOllamaEl.textContent = `${window.t('status.ollama')}: ${window.t('status.disconnected')}`;
    statusModelsEl.textContent = `${window.t('status.models')}: 0`;
    statusHostEl.textContent = `${window.t('health.host')}: -`;
  }
};

window.loadModels = async function () {
  const { engineSelectEl } = window.getEls();

const resp = await fetch(window.API_MODELS, {
  headers: { 'X-Ollama-Base-Url': window.getOllamaBaseUrl() }
});
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

  const data = await resp.json();

  window.state.models = Array.isArray(data.models)
    ? data.models
    : Array.isArray(data)
      ? data
      : [];

  engineSelectEl.innerHTML = '';

  if (window.state.models.length === 0) {
    engineSelectEl.innerHTML = '<option value="" disabled selected>Brak modeli</option>';
    engineSelectEl.disabled = true;
    window.state.selectedEngine = null;
    return;
  }

  engineSelectEl.disabled = false;

  window.state.models.forEach(model => {
    const name = typeof model === 'string' ? model : model.name;
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    engineSelectEl.appendChild(option);
  });

  const savedEngine = localStorage.getItem('ai-gm:selectedEngine');
  const preferredEngine =
    savedEngine ||
    window.state.selectedEngine ||
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

window.getOllamaBaseUrl = function () {
  const saved = localStorage.getItem('ai-gm:ollamaBaseUrl') || '';
  return saved.trim() || 'http://ollama:11434';
};

window.getApiHeaders = function () {
  return {
    'Content-Type': 'application/json',
    'X-Ollama-Base-Url': window.getOllamaBaseUrl()
  };
};