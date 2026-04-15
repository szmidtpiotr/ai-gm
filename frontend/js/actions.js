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
  turnNumbers: {}
};

window.chatRequestState = window.chatRequestState || {
  inFlight: false,
  requestId: 0
};

window.nextTurnNumber = function () {
  const id = window.state.selectedCampaignId;
  if (!id) return 1;

  const current = window.state.turnNumbers[id] || 0;
  window.state.turnNumbers[id] = current + 1;
  return window.state.turnNumbers[id];
};

window.createCampaign = async function () {
  const { systemSelectEl, engineSelectEl } = window.getEls();

  const title = prompt(
    'Tytuł kampanii:',
    `Kampania ${new Date().toISOString().slice(0, 10)}`
  );
  if (!title) return;

  const payload = {
    title: title.trim(),
    system_id: systemSelectEl.value,
    model_id: engineSelectEl.value || (window.state.models[0]?.name ?? 'gemma3:1b'),
    owner_user_id: 1,
    language: window.state.lang || 'pl',
    mode: 'solo',
    status: 'active'
  };

  try {
    const resp = await fetch(window.API_CAMPAIGNS, {
      method: 'POST',
      headers: window.getApiHeaders(),
      body: JSON.stringify(payload)
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    await window.loadCampaigns(data.id);
    await window.loadCharacters(data.id);

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

window.createCharacter = async function () {
  if (!window.state.selectedCampaignId) {
    alert('Najpierw wybierz kampanię');
    return;
  }

  window.setCharacterModalOpen(true);
};

window.createCharacterFromForm = async function () {
  const {
    characterCreateNameEl,
    characterCreateBackgroundEl,
    characterCreateFormEl,
    characterCreateSubmitEl
  } = window.getEls();

  if (!window.state.selectedCampaignId) {
    alert('Najpierw wybierz kampanię');
    return;
  }

  const name = (characterCreateNameEl?.value || '').trim();
  const background = (characterCreateBackgroundEl?.value || '').trim();
  const archetype = characterCreateFormEl?.dataset?.archetype || '';

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
  if (!archetype) {
    alert('Wybierz archetyp postaci');
    return;
  }

  const payload = {
    user_id: 1,
    name,
    system_id: 'fantasy',
    sheet_json: {
      archetype,
      background,
      level: 1,
      hp: archetype === 'Warrior' ? 24 : 16,
      mana: archetype === 'Mage' ? 24 : 6,
      stats: {},
      inventory: []
    },
    location: 'Start',
    is_active: 1
  };

  if (characterCreateSubmitEl) characterCreateSubmitEl.disabled = true;

  try {
    const resp = await fetch(`/api/campaigns/${window.state.selectedCampaignId}/characters`, {
      method: 'POST',
      headers: window.getApiHeaders(),
      body: JSON.stringify(payload)
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    await window.loadCharacters(window.state.selectedCampaignId, data.id);
    await window.loadTurns(window.state.selectedCampaignId);
    window.setCharacterModalOpen(false);
    window.updateUiState();

    if (characterCreateFormEl) {
      characterCreateFormEl.reset();
      characterCreateFormEl.dataset.archetype = '';
    }
    document.querySelectorAll('.archetype-card').forEach((card) => {
      card.classList.remove('selected');
    });

    window.addMessage({
      speaker: 'System',
      text: `Utworzono postać: ${data.name}`,
      role: 'system',
      route: 'character'
    });
  } catch (e) {
    window.addMessage({
      speaker: 'Błąd',
      text: `Tworzenie postaci: ${e.message}`,
      role: 'error'
    });
  } finally {
    if (characterCreateSubmitEl) characterCreateSubmitEl.disabled = false;
  }
};

window.sendMessage = async function () {
  const { inputEl, systemSelectEl, engineSelectEl, sendBtnEl } = window.getEls();
  const text = inputEl.value.trim();
  if (!text) return;

  if (window.chatRequestState?.inFlight) {
    return;
  }

  const clientCreatedAt = new Date().toISOString();

  if (!window.state.selectedCampaignId) {
    window.addMessage({
      speaker: 'System',
      text: window.t('error.no_campaign'),
      role: 'error',
      createdAt: clientCreatedAt
    });
    return;
  }

  if (!window.state.selectedCharacterId) {
    window.addMessage({
      speaker: 'System',
      text: window.t('error.no_character'),
      role: 'error',
      createdAt: clientCreatedAt
    });
    return;
  }

  const selectedEngine = window.state.selectedEngine || engineSelectEl.value || '';

  if (!selectedEngine) {
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

  let turnNumber = window.nextTurnNumber();

  // Show user message
  window.addMessage({
    speaker: window.currentCharacterName(),
    text,
    role: 'user',
    route: 'input',
    turn: turnNumber,
    createdAt: clientCreatedAt
  });

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
      text,
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

    while (!streamDone) {
      const { done, value } = await reader.read();

      if (done) {
        // Flush any remaining data in buffer
        if (buffer.trim()) {
          const remaining = buffer.trim();
          if (remaining.startsWith('data: ')) {
            const token = remaining.slice(6);
            if (token !== '[DONE]' && !token.startsWith('[ERROR]')) {
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

        if (token === '[DONE]') {
          if (streamBubble) {
            window.finalizeStreamingBubble(streamBubble, fullText);
          } else {
            window.removeThinkingBubble();
          }
          await window.loadTurns(window.state.selectedCampaignId);
          streamDone = true;
          break;
        }

        if (token.startsWith('[ERROR]')) {
          const errMsg = token.slice(8) || 'Nieznany błąd';
          if (streamBubble) {
            window.finalizeStreamingBubble(streamBubble, `⚠️ ${errMsg}`);
          } else {
            window.removeThinkingBubble();
            window.addMessage({
              speaker: 'Błąd',
              text: `⚠️ ${errMsg}`,
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
        window.finalizeStreamingBubble(streamBubble, fullText);
        await window.loadTurns(window.state.selectedCampaignId);
      } else {
        window.removeThinkingBubble();
      }
    }

  } catch (e) {
    if (requestId !== window.chatRequestState.requestId) return;

    window.removeThinkingBubble();
    window.addMessage({
      speaker: 'Błąd',
      text: `Serwer: ${e.message}`,
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

window.rollDice = async function () {
  const dice = prompt('Kość (d20, 2d6+3, d100):', '1d20');
  if (!dice) return;

  try {
    const resp = await fetch('/gm/dice', {
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
