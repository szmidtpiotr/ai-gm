window.bindEvents = function () {
  const els = window.getEls();
  const historyBtn = document.getElementById('history-btn');
  const historyPanelEl = document.getElementById('history-panel');
  const archetypeCards = Array.from(document.querySelectorAll('.archetype-card'));
  const defaultOllamaUrl = 'http://ollama:11434';
  const customStorageKey = 'ai-gm:ollamaCustomUrl';
  const ollamaOptionsEl = document.getElementById('ollama-url-options');
  const customOptionId = 'ollama-custom-option';

  const syncOllamaPreset = () => {
    if (!els.ollamaUrlPresetEl) return;
    const value = (window.getOllamaBaseUrl() || '').trim() || defaultOllamaUrl;
    els.ollamaUrlPresetEl.value = value;

    if (!ollamaOptionsEl) return;
    let customOption = document.getElementById(customOptionId);

    if (value === defaultOllamaUrl) {
      if (customOption) customOption.remove();
      return;
    }

    if (!customOption) {
      customOption = document.createElement('option');
      customOption.id = customOptionId;
      ollamaOptionsEl.appendChild(customOption);
    }
    customOption.value = value;
    customOption.label = `Custom: ${value}`;
  };
  syncOllamaPreset();

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

  if (els.ollamaUrlPresetEl) {
    const applyOllamaFieldValue = () => {
      const value = (els.ollamaUrlPresetEl.value || '').trim() || defaultOllamaUrl;
      localStorage.setItem('ai-gm:ollamaBaseUrl', value);
      if (value !== defaultOllamaUrl) {
        localStorage.setItem(customStorageKey, value);
      }
      syncOllamaPreset();
    };

    els.ollamaUrlPresetEl.onchange = applyOllamaFieldValue;
    els.ollamaUrlPresetEl.onblur = applyOllamaFieldValue;
  }

  if (els.testOllamaBtn) {
    els.testOllamaBtn.onclick = async () => {
      const value = (els.ollamaUrlPresetEl?.value || '').trim() || defaultOllamaUrl;
      localStorage.setItem('ai-gm:ollamaBaseUrl', value);
      if (value !== defaultOllamaUrl) {
        localStorage.setItem(customStorageKey, value);
      }
      syncOllamaPreset();

      try {
        await window.loadHealth();
        await window.loadModels();

        if (window.state.selectedEngine) {
          els.engineSelectEl.value = window.state.selectedEngine;
        }

        window.addMessage({
          speaker: 'System',
          text: `API URL ustawiony na ${value}`,
          role: 'system',
          route: 'config'
        });
        window.location.reload();
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
  if (els.diceBtn) {
    els.diceBtn.onclick = () => window.setSheetPanelOpen(!window.state.sheetPanelOpen);
  }
  els.createCampaignBtn.onclick = window.createCampaign;
  els.deleteCampaignBtn.onclick = window.deleteCampaign;
  els.createCharacterBtn.onclick = window.createCharacter;

  if (els.characterCreateFormEl) {
    els.characterCreateFormEl.onsubmit = async (e) => {
      e.preventDefault();
      await window.createCharacterFromForm();
    };
  }

  if (els.campaignCreateFormEl) {
    els.campaignCreateFormEl.onsubmit = async (e) => {
      e.preventDefault();
      await window.createCampaignFromForm();
    };
  }

  if (els.campaignCreateCloseEl) {
    els.campaignCreateCloseEl.onclick = () => window.setCampaignModalOpen(false);
  }

  if (els.campaignCreateOverlayEl) {
    els.campaignCreateOverlayEl.onclick = (e) => {
      if (e.target === els.campaignCreateOverlayEl) {
        window.setCampaignModalOpen(false);
      }
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