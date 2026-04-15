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
  const { systemSelectEl } = window.getEls();

  if (!window.state.selectedCampaignId) {
    alert('Najpierw wybierz kampanię');
    return;
  }

  const name = prompt('Imię postaci:', 'Nowy Bohater');
  if (!name) return;

  const payload = {
    user_id: 1,
    name: name.trim(),
    system_id: systemSelectEl.value,
    sheet_json: {
      level: 1,
      hp: 20,
      stats: {},
      inventory: []
    },
    location: 'Start',
    is_active: 1
  };

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

  // Show thinking bubble with animated dots immediately — before fetch even starts
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

    // --- STREAMING via SSE ---
    // NOTE: fetch() itself returns only after the response headers arrive.
    // The thinking bubble stays visible during this entire wait. Only when
    // the first token chunk arrives do we swap to the streaming bubble.
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
    // Strategy:
    //   - Keep thinking bubble visible until first real token arrives
    //   - On first token: swap thinking -> streaming bubble (createStreamingBubble
    //     removes thinking bubble internally)
    //   - Stream tokens directly into <pre> via textContent append
    //   - On [DONE]: finalize bubble (remove .streaming class, show dice buttons)
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';
    let streamBubble = null; // created lazily on first real token
    let streamDone = false;

    while (!streamDone) {
      const { done, value } = await reader.read();

      // On stream close, flush remaining buffer
      if (done) {
        if (buffer.trim()) {
          const remaining = buffer.trim();
          if (remaining.startsWith('data: ')) {
            const token = remaining.slice(6);
            if (token !== '[DONE]' && !token.startsWith('[ERROR]')) {
              const realToken = token.replace(/\\n/g, '\n');
              fullText += realToken;
              if (!streamBubble) {
                // First token — swap thinking bubble to streaming bubble
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
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete last line in buffer

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const token = line.slice(6);

        if (token === '[DONE]') {
          if (streamBubble) {
            window.finalizeStreamingBubble(streamBubble, fullText);
          } else {
            // [DONE] arrived with no tokens at all — remove thinking bubble
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

        // Normal token — unescape \n sequences back to real newlines
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

    // Stream ended without [DONE] (server closed early) — finalize gracefully
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
