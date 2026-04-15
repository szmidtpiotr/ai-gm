window.bindEvents = function () {
  const els = window.getEls();
  const historyBtn = document.getElementById('history-btn');
  const historyPanelEl = document.getElementById('history-panel');
  const archetypeCards = Array.from(document.querySelectorAll('.archetype-card'));

  if (els.ollamaUrlEl) {
    els.ollamaUrlEl.value = window.getOllamaBaseUrl();
  }

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

    if (campaign?.system_id || campaign?.systemid) {
      els.systemSelectEl.value = campaign.system_id || campaign.systemid;
    }

    if (campaign?.model_id || campaign?.modelid) {
      window.state.selectedEngine = campaign.model_id || campaign.modelid;
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

  if (els.ollamaUrlEl) {
    els.ollamaUrlEl.onchange = () => {
      const value = (els.ollamaUrlEl.value || '').trim() || 'http://ollama:11434';
      localStorage.setItem('ai-gm:ollamaBaseUrl', value);
      els.ollamaUrlEl.value = value;
    };
  }

  if (els.testOllamaBtn && els.ollamaUrlEl) {
    els.testOllamaBtn.onclick = async () => {
      const value = (els.ollamaUrlEl.value || '').trim() || 'http://ollama:11434';
      localStorage.setItem('ai-gm:ollamaBaseUrl', value);
      els.ollamaUrlEl.value = value;

      try {
        await window.loadHealth();
        await window.loadModels();

        if (window.state.selectedEngine) {
          els.engineSelectEl.value = window.state.selectedEngine;
        }

        window.addMessage({
          speaker: 'System',
          text: `Ollama Host ustawiony na ${value}`,
          role: 'system',
          route: 'config'
        });
      } catch (e) {
        window.addMessage({
          speaker: 'Błąd',
          text: `Test Ollama Host nie powiódł się: ${e.message}`,
          role: 'error'
        });
      }
    };
  }

  els.sendBtn.onclick = window.sendMessage;
  els.diceBtn.onclick = window.rollDice;
  els.createCampaignBtn.onclick = window.createCampaign;
  els.deleteCampaignBtn.onclick = window.deleteCampaign;
  els.createCharacterBtn.onclick = window.createCharacter;

  if (els.characterCreateFormEl) {
    els.characterCreateFormEl.onsubmit = async (e) => {
      e.preventDefault();
      await window.createCharacterFromForm();
    };
  }

  if (els.characterCreateCloseEl) {
    els.characterCreateCloseEl.onclick = () => window.setCharacterModalOpen(false);
  }

  if (els.characterCreateOverlayEl) {
    els.characterCreateOverlayEl.onclick = (e) => {
      if (e.target === els.characterCreateOverlayEl && window.state.selectedCharacterId) {
        window.setCharacterModalOpen(false);
      }
    };
  }

  archetypeCards.forEach((card) => {
    card.onclick = () => {
      const archetype = card.getAttribute('data-archetype');
      if (els.characterCreateFormEl) {
        els.characterCreateFormEl.dataset.archetype = archetype || '';
      }
      archetypeCards.forEach((item) => item.classList.remove('selected'));
      card.classList.add('selected');
    };
  });

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