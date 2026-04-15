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
window.state.pendingRoll = window.state.pendingRoll || null;

window._updateRollButtonsState = function () {
  const { contextualRollBtn } = window.getEls();
  const pending = window.state.pendingRoll;
  if (!contextualRollBtn) return;

  if (pending) {
    contextualRollBtn.textContent = `🎲 Rzuć ${pending.dice} — ${pending.skill}`;
    contextualRollBtn.style.display = 'block';
    return;
  }

  contextualRollBtn.style.display = 'none';
};

window.parsePendingRoll = function (text) {
  const sourceText = String(text || '');
  const lines = sourceText.split('\n');
  const lastLineRaw = (lines[lines.length - 1] || '').trim();
  const match = lastLineRaw.match(/^Roll (.+?) (d\d+)$/i);

  if (!match) {
    window.state.pendingRoll = null;
    window._updateRollButtonsState();
    return sourceText;
  }

  const skillLabel = (match[1] || '').trim();
  const canonicalSkill = typeof window.resolveRollTestName === 'function'
    ? window.resolveRollTestName(skillLabel)
    : null;
  const diceExpr = (match[2] || 'd20').toLowerCase();

  if (!canonicalSkill) {
    console.warn('Ignoring unknown roll cue test name:', skillLabel);
    window.state.pendingRoll = null;
    window._updateRollButtonsState();
    return sourceText;
  }

  const displaySkill = typeof window.formatRollTestDisplayName === 'function'
    ? window.formatRollTestDisplayName(canonicalSkill)
    : canonicalSkill;
  window.state.pendingRoll = {
    skill: displaySkill,
    canonical_skill: canonicalSkill,
    dice: diceExpr
  };

  window._updateRollButtonsState();

  lines.pop();
  return lines.join('\n').trimEnd();
};

window.performPendingRoll = function () {
  const pending = window.state.pendingRoll;
  if (!pending) return;

  const diceMatch = pending.dice.match(/^d(\d+)$/i);
  const sides = diceMatch ? Number(diceMatch[1]) : 20;
  const roll = Math.floor(Math.random() * sides) + 1;

  window.addMessage({
    speaker: 'System',
    text: `🎲 Roll ${pending.skill} ${pending.dice} → ${roll}`,
    role: 'system'
  });

  window.state.pendingRoll = null;
  window._updateRollButtonsState();
};

window.nextTurnNumber = function () {
  const id = window.state.selectedCampaignId;
  if (!id) return 1;

  const current = window.state.turnNumbers[id] || 0;
  window.state.turnNumbers[id] = current + 1;
  return window.state.turnNumbers[id];
};

window.createCampaign = async function () {
  window.setCampaignModalOpen(true);
};

window.createCampaignFromForm = async function () {
  const { systemSelectEl, engineSelectEl } = window.getEls();
  const {
    campaignCreateTitleInputEl,
    campaignCreateFormEl,
    campaignCreateSubmitEl
  } = window.getEls();

  const title = (campaignCreateTitleInputEl?.value || '').trim();
  if (!title) return;

  const payload = {
    title,
    system_id: systemSelectEl.value,
    model_id: engineSelectEl.value || (window.state.models[0]?.name ?? 'gemma3:1b'),
    owner_user_id: 1,
    language: window.state.lang || 'pl',
    mode: 'solo',
    status: 'active'
  };

  if (campaignCreateSubmitEl) campaignCreateSubmitEl.disabled = true;

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
    window.setCampaignModalOpen(false);

    if (campaignCreateFormEl) {
      campaignCreateFormEl.reset();
    }

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
  } finally {
    if (campaignCreateSubmitEl) campaignCreateSubmitEl.disabled = false;
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
    campaignSelectEl,
    characterCreateNameEl,
    characterCreateBackgroundEl,
    characterCreateFormEl,
    characterCreateSubmitEl
  } = window.getEls();

  if (!window.state.selectedCampaignId) {
    alert('Najpierw wybierz kampanię');
    return;
  }

  // Guard against stale local campaign id after refresh/deletions.
  await window.loadCampaigns(window.state.selectedCampaignId);
  let selectedCampaignId = Number(
    campaignSelectEl?.value || window.state.selectedCampaignId || 0
  );
  if (!selectedCampaignId) {
    alert('Najpierw wybierz kampanię');
    return;
  }

  // Preflight campaign validation against backend to avoid hidden stale state.
  try {
    const checkResp = await fetch(`/api/campaigns/${selectedCampaignId}`);
    if (checkResp.status === 404) {
      const listResp = await fetch(window.API_CAMPAIGNS);
      if (listResp.ok) {
        const listData = await listResp.json();
        const campaigns = Array.isArray(listData.campaigns) ? listData.campaigns : [];
        if (campaigns.length > 0) {
          selectedCampaignId = Number(campaigns[0].id);
          window.state.selectedCampaignId = selectedCampaignId;
          if (campaignSelectEl) {
            campaignSelectEl.value = String(selectedCampaignId);
          }
          localStorage.setItem('ai-gm:selectedCampaignId', String(selectedCampaignId));
        } else {
          alert('Brak kampanii. Utwórz najpierw kampanię.');
          return;
        }
      }
    }
  } catch (_) {
    // Continue with currently selected id; submit may still provide concrete backend error.
  }

  const name = (characterCreateNameEl?.value || '').trim();
  const background = (characterCreateBackgroundEl?.value || '').trim();
  const archetype = characterCreateFormEl?.dataset?.archetype || '';
  const campaign = window.currentCampaign ? window.currentCampaign() : null;
  const campaignSystem = campaign?.system_id || campaign?.systemid || 'fantasy';

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
    system_id: campaignSystem,
    sheet_json: {
      archetype,
      background,
      level: 1,
      current_hp: archetype === 'Warrior' ? 24 : 16,
      max_hp: archetype === 'Warrior' ? 24 : 16,
      current_mana: archetype === 'Mage' ? 24 : 6,
      max_mana: archetype === 'Mage' ? 24 : 6,
      stats: {
        STR: archetype === 'Warrior' ? 14 : 10,
        DEX: 12,
        CON: archetype === 'Warrior' ? 13 : 10,
        INT: archetype === 'Mage' ? 14 : 10,
        WIS: 11,
        CHA: 10,
        LCK: 10
      },
      skills: {
        Athletics: archetype === 'Warrior' ? 2 : 1,
        Swordsmanship: archetype === 'Warrior' ? 2 : 0,
        Archery: 1,
        Stealth: 1,
        Survival: 1,
        Persuasion: 1,
        Insight: 1,
        Arcana: archetype === 'Mage' ? 2 : 0,
        Alchemy: archetype === 'Mage' ? 1 : 0,
        Lore: 1
      },
      inventory: []
    },
    location: 'Start',
    is_active: 1
  };

  if (characterCreateSubmitEl) characterCreateSubmitEl.disabled = true;

  try {
    const resp = await fetch(`/api/campaigns/${selectedCampaignId}/characters`, {
      method: 'POST',
      headers: window.getApiHeaders(),
      body: JSON.stringify(payload)
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    await window.loadCharacters(selectedCampaignId, data.id);
    await window.loadTurns(selectedCampaignId);
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
    alert(`Tworzenie postaci nie powiodło się: ${e.message}`);
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
    const resp = await fetch('/api/gm/dice', {
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
