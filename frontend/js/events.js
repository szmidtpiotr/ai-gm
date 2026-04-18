window.bindEvents = function () {
  const els = window.getEls();
  const historyBtn = document.getElementById('history-btn');
  const historyPanelEl = document.getElementById('history-panel');
  const archetypeCards = Array.from(document.querySelectorAll('.archetype-card'));

  els.campaignSelectEl.onchange = async () => {
    window.state.selectedCampaignId = Number(els.campaignSelectEl.value);
    localStorage.setItem(
      'ai-gm:selectedCampaignId',
      String(window.state.selectedCampaignId)
    );
    window.state.helpmeLog = [];

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
    }

    await window.loadCharacters(window.state.selectedCampaignId);

    // Apply per-user LLM settings after character list refresh.
    const userId = window.state?.playerUserId || 1;
    try {
      await window.loadUserLlmSettings(userId);
      await window.loadHealth(userId);
      await window.loadModels(userId);
      window.syncLlmControlsCollapseToCurrentState?.();
    } catch (_err) {
      // Keep UI operational with existing in-memory/lclocal values.
    }
    await window.loadTurns(window.state.selectedCampaignId);
    window.updateUiState();
  };

  els.characterSelectEl.onchange = async () => {
    window.state.selectedCharacterId = Number(els.characterSelectEl.value);
    localStorage.setItem(
      'ai-gm:selectedCharacterId',
      String(window.state.selectedCharacterId)
    );
    const userId = window.state?.playerUserId || 1;
    try {
      await window.loadUserLlmSettings(userId);
      await window.loadHealth(userId);
      await window.loadModels(userId);
      window.syncLlmControlsCollapseToCurrentState?.();
    } catch (_err) {
      // ignore
    }
    window.updateUiState();
  };

  els.engineSelectEl.onchange = () => {
    window.state.selectedEngine = els.engineSelectEl.value;
  };

  if (els.testOllamaBtn) {
    els.testOllamaBtn.onclick = async () => {
      try {
        const userId = window.state?.playerUserId || 1;
        if (typeof window.connectLlmSettings === 'function') {
          await window.connectLlmSettings();
        }
        await window.loadHealth(userId);
        await window.loadModels(userId);

        if (window.state.selectedEngine) {
          els.engineSelectEl.value = window.state.selectedEngine;
        }

        window.addMessage({
          speaker: 'System',
          text: `Połączenie LLM zapisane (provider: ${window.state.llmSettings?.provider || 'unknown'})`,
          role: 'system',
          route: 'config'
        });
      } catch (e) {
        const pretty = typeof window.prettyLlmErrorMessage === 'function'
          ? window.prettyLlmErrorMessage(e.message)
          : e.message;
        window.addMessage({
          speaker: 'Błąd',
          text: `Połączenie LLM nie powiodło się: ${pretty}`,
          role: 'error'
        });
      }
    };
  }

  els.sendBtn.onclick = window.sendMessage;
  if (els.diceBtn) {
    els.diceBtn.onclick = () => {
      const isOpen = !!window.state.sheetPanelOpen;
      if (typeof window.setSheetPanelOpen === 'function') {
        window.setSheetPanelOpen(!isOpen);
      }
    };
  }
  if (els.contextualRollBtn) {
    els.contextualRollBtn.onclick = window.performPendingRoll;
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
    els.characterCreateCloseEl.onclick = () => {
      if (typeof window.isCharacterCreationWizardBlockingClose === 'function' && window.isCharacterCreationWizardBlockingClose()) {
        return;
      }
      window.setCharacterModalOpen(false);
    };
  }

  if (els.characterCreateOverlayEl) {
    els.characterCreateOverlayEl.onclick = (e) => {
      if (e.target !== els.characterCreateOverlayEl) return;
      if (typeof window.isCharacterCreationWizardBlockingClose === 'function' && window.isCharacterCreationWizardBlockingClose()) {
        return;
      }
      if (window.state.selectedCharacterId) {
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