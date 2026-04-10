window.bindEvents = function () {
  const els = window.getEls();
  const historyBtn = document.getElementById('history-btn');
  const historyPanelEl = document.getElementById('history-panel');

  els.campaignSelectEl.onchange = async () => {
    window.state.selectedCampaignId = Number(els.campaignSelectEl.value);
    localStorage.setItem(
      'ai-gm:selectedCampaignId',
      String(window.state.selectedCampaignId)
    );

    const campaign = window.currentCampaign();

    if (campaign?.language && campaign.language !== window.state.lang) {
      await window.loadTranslations(campaign.language);
    }

    if (campaign?.system_id) {
      els.systemSelectEl.value = campaign.system_id;
    }

    if (campaign?.model_id) {
      window.state.selectedEngine = campaign.model_id;
    } else if (!window.state.selectedEngine) {
      window.state.selectedEngine = els.engineSelectEl.value;
    }

    if (window.state.selectedEngine) {
      els.engineSelectEl.value = window.state.selectedEngine;
      localStorage.setItem('ai-gm:selectedEngine', window.state.selectedEngine);
    }

    await window.loadCharacters(window.state.selectedCampaignId);
    await window.loadTurns(window.state.selectedCampaignId);
    window.updateUiState();
  };

  els.characterSelectEl.onchange = () => {
    window.state.selectedCharacterId = Number(els.characterSelectEl.value);
    localStorage.setItem(
      'ai-gm:selectedCharacterId',
      String(window.state.selectedCharacterId)
    );
    window.updateUiState();
  };

  els.engineSelectEl.onchange = () => {
    window.state.selectedEngine = els.engineSelectEl.value;
    localStorage.setItem('ai-gm:selectedEngine', window.state.selectedEngine);
  };

  els.sendBtn.onclick = window.sendMessage;
  els.diceBtn.onclick = window.rollDice;
  els.createCampaignBtn.onclick = window.createCampaign;
  els.deleteCampaignBtn.onclick = window.deleteCampaign;
  els.createCharacterBtn.onclick = window.createCharacter;

  if (historyBtn && historyPanelEl) {
    historyBtn.onclick = async () => {
      if (!window.state.selectedCampaignId) return;

      await window.loadTurns(window.state.selectedCampaignId);

      historyPanelEl.style.display =
        historyPanelEl.style.display === 'none' ? 'block' : 'none';
    };
  }

  els.inputEl.onkeydown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      window.sendMessage();
    }
  };
};