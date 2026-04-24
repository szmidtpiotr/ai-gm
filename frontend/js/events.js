window.bindEvents = function () {
  const els = window.getEls();
  const archetypeCards = Array.from(document.querySelectorAll('.archetype-card'));

  els.campaignSelectEl.onchange = async () => {
    const nextId = Number(els.campaignSelectEl.value);
    if (
      window.state.expectCharacterCreationForCampaignId != null &&
      Number(window.state.expectCharacterCreationForCampaignId) !== nextId
    ) {
      window.state.expectCharacterCreationForCampaignId = null;
    }
    window.state.selectedCampaignId = nextId;
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
  if (els.resetCampaignBtn) els.resetCampaignBtn.onclick = window.resetCampaignProgress;
  if (els.resetCharacterBtn) els.resetCharacterBtn.onclick = window.resetCharacterProgress;

  if (els.characterCreateFormEl) {
    els.characterCreateFormEl.onsubmit = async (e) => {
      e.preventDefault();
      if (window.state._characterCreationInFlight) return;
      await window.createCharacterFromForm();
    };
  }

  if (els.campaignCreateFormEl) {
    els.campaignCreateFormEl.onsubmit = async (e) => {
      e.preventDefault();
      if (window.state._campaignCreationInFlight) return;
      await window.createCampaignFromForm();
    };
  }

  if (els.campaignCreateCloseEl) {
    els.campaignCreateCloseEl.onclick = () => {
      if (window.state._campaignCreationInFlight) return;
      window.setCampaignModalOpen(false);
    };
  }

  if (els.campaignCreateOverlayEl) {
    els.campaignCreateOverlayEl.onclick = (e) => {
      if (e.target === els.campaignCreateOverlayEl) {
        if (window.state._campaignCreationInFlight) return;
        window.setCampaignModalOpen(false);
      }
    };
  }

  if (els.characterCreateCloseEl) {
    els.characterCreateCloseEl.onclick = async () => {
      if (window.state._characterCreationInFlight) return;
      if (typeof window.isCharacterCreationWizardBlockingClose === 'function' && window.isCharacterCreationWizardBlockingClose()) {
        return;
      }
      if (typeof window.abandonWizardCampaignIfNeeded === 'function') {
        await window.abandonWizardCampaignIfNeeded();
      }
      window.setCharacterModalOpen(false);
    };
  }

  if (els.characterCreateOverlayEl) {
    els.characterCreateOverlayEl.onclick = async (e) => {
      if (e.target !== els.characterCreateOverlayEl) return;
      if (window.state._characterCreationInFlight) return;
      if (typeof window.isCharacterCreationWizardBlockingClose === 'function' && window.isCharacterCreationWizardBlockingClose()) {
        return;
      }
      if (window.state.selectedCharacterId) {
        if (typeof window.abandonWizardCampaignIfNeeded === 'function') {
          await window.abandonWizardCampaignIfNeeded();
        }
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

  els.inputEl.onkeydown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (
        typeof window.combatInput?.triggerPlayerAttackFromEnter === 'function' &&
        window.combatInput.triggerPlayerAttackFromEnter()
      ) {
        return;
      }
      window.sendMessage();
    }
  };
};