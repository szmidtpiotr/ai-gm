window.bootstrap = async function () {
  try {
    window.bindEvents();
    await window.loadTranslations('pl');
    await window.loadHealth();
    await window.loadModels();
    await window.loadCampaigns();

    if (window.state.selectedCampaignId) {
      const { systemSelectEl, engineSelectEl } = window.getEls();
      const campaign = window.currentCampaign();

      if (campaign?.system_id) {
        systemSelectEl.value = campaign.system_id;
      }

	const savedEngine = localStorage.getItem('ai-gm:selectedEngine');

	if (savedEngine) {
	  window.state.selectedEngine = savedEngine;
	} else if (campaign?.model_id) {
	  window.state.selectedEngine = campaign.model_id;
	} else {
	  window.state.selectedEngine = engineSelectEl.value;
	}

	if (window.state.selectedEngine) {
	  engineSelectEl.value = window.state.selectedEngine;
	}

      await window.loadCharacters(window.state.selectedCampaignId);
		  try {
	  await window.loadTurns(window.state.selectedCampaignId);
	} catch (e) {
	  console.warn('History load skipped:', e);
	}
    }

    window.updateUiState();

    if (!window.state.turns || window.state.turns.length === 0) {
      window.addMessage({
        speaker: 'System',
        text: window.t('system.ready'),
        role: 'system'
      });
    }
  } catch (e) {
    window.addMessage({
      speaker: 'Błąd',
      text: `Bootstrap failed: ${e.message}`,
      role: 'error'
    });
  }
};

document.addEventListener('DOMContentLoaded', () => {
  window.bootstrap();
  setInterval(window.loadHealth, 15000);
});