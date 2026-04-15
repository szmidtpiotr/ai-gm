window.getEls = function () {
  return {
    appTitleEl: document.getElementById('app-title'),
    campaignSelectEl: document.getElementById('campaign-select'),
    characterSelectEl: document.getElementById('character-select'),
    systemSelectEl: document.getElementById('system-select'),
    engineSelectEl: document.getElementById('engine-select'),
    ollamaUrlPresetEl: document.getElementById('ollama-url-preset'),
    testOllamaBtn: document.getElementById('test-ollama-btn'),
    chatEl: document.getElementById('chat'),
    historyPanelEl: document.getElementById('history-panel'),
    composerEl: document.querySelector('.composer'),
    inputEl: document.getElementById('input'),
    sendBtn: document.getElementById('send-btn'),
    diceBtn: document.getElementById('dice-btn'),
    contextualRollBtn: document.getElementById('contextual-roll-btn'),
    createCampaignBtn: document.getElementById('create-campaign-btn'),
    deleteCampaignBtn: document.getElementById('delete-campaign-btn'),
    createCharacterBtn: document.getElementById('create-character-btn'),
    statusBackendDotEl: document.getElementById('status-backend-dot'),
    statusOllamaDotEl: document.getElementById('status-ollama-dot'),
    labelCampaignEl: document.getElementById('label-campaign'),
    labelCharacterEl: document.getElementById('label-character'),
    labelSystemEl: document.getElementById('label-system'),
    labelEngineEl: document.getElementById('label-engine'),
    labelOllamaUrlEl: document.getElementById('label-ollama-url'),
    characterCreateOverlayEl: document.getElementById('character-create-overlay'),
    characterCreatePanelEl: document.getElementById('character-create-panel'),
    characterCreateCloseEl: document.getElementById('character-create-close'),
    characterCreateFormEl: document.getElementById('character-create-form'),
    characterCreateNameEl: document.getElementById('character-create-name'),
    characterCreateBackgroundEl: document.getElementById('character-create-background'),
    characterCreateSubmitEl: document.getElementById('character-create-submit'),
    campaignCreateOverlayEl: document.getElementById('campaign-create-overlay'),
    campaignCreatePanelEl: document.getElementById('campaign-create-panel'),
    campaignCreateCloseEl: document.getElementById('campaign-create-close'),
    campaignCreateFormEl: document.getElementById('campaign-create-form'),
    campaignCreateTitleInputEl: document.getElementById('campaign-create-title-input'),
    campaignCreateSubmitEl: document.getElementById('campaign-create-submit')
  };
};

window.characterModalOpen = window.characterModalOpen || false;
window.campaignModalOpen = window.campaignModalOpen || false;

window.setCharacterModalOpen = function (open) {
  window.characterModalOpen = !!open;
  const els = window.getEls();
  if (open && els.characterCreateNameEl) {
    setTimeout(() => els.characterCreateNameEl.focus(), 0);
  }
  window.updateUiState();
};

window.setCampaignModalOpen = function (open) {
  window.campaignModalOpen = !!open;
  const els = window.getEls();
  if (open && els.campaignCreateTitleInputEl) {
    setTimeout(() => els.campaignCreateTitleInputEl.focus(), 0);
  }
  window.updateUiState();
};

window.applyTranslations = function () {
  const els = window.getEls();

  if (els.appTitleEl) els.appTitleEl.textContent = window.t('app.title');
  if (els.labelCampaignEl) els.labelCampaignEl.textContent = window.t('campaign.label');
  if (els.labelCharacterEl) els.labelCharacterEl.textContent = window.t('character.label');
  if (els.labelSystemEl) els.labelSystemEl.textContent = window.t('system.label');
  if (els.labelEngineEl) els.labelEngineEl.textContent = window.t('engine.label');
  if (els.labelOllamaUrlEl) els.labelOllamaUrlEl.textContent = 'API URL';
  if (els.inputEl) els.inputEl.placeholder = window.t('input.placeholder');
  if (els.sendBtn) els.sendBtn.textContent = window.t('button.send');
};

// Scroll chat to bottom — immediate, no rAF (rAF per-token kills streaming paint)
window.scrollChatToBottom = function () {
  const { chatEl } = window.getEls();
  if (!chatEl) return;
  chatEl.scrollTop = chatEl.scrollHeight;
};

// Throttled scroll during streaming — max once per animation frame
window._scrollPending = false;
window.scrollChatToBottomThrottled = function () {
  if (window._scrollPending) return;
  window._scrollPending = true;
  requestAnimationFrame(() => {
    window._scrollPending = false;
    const { chatEl } = window.getEls();
    if (chatEl) chatEl.scrollTop = chatEl.scrollHeight;
  });
};

window.removeThinkingBubble = function () {
  const { chatEl } = window.getEls();
  if (!chatEl) return;
  const existing = chatEl.querySelector('#thinking-bubble');
  if (existing) existing.remove();
};

window.showThinkingBubble = function ({
  speaker = null,
  route = 'narrative',
  turn = null
} = {}) {
  const { chatEl } = window.getEls();
  if (!chatEl) return;

  // Only one thinking bubble at a time
  const existing = chatEl.querySelector('#thinking-bubble');
  if (existing) return;

  const wrap = document.createElement('div');
  wrap.className = 'message assistant thinking';
  wrap.id = 'thinking-bubble';

  const meta = document.createElement('div');
  meta.className = 'meta';

  const left = document.createElement('div');
  left.innerHTML =
    `<strong>${window.escapeHtml(speaker || window.t('chat.gm'))}</strong>` +
    `${turn ? ` \u2022 ${window.escapeHtml(window.t('chat.turn'))} ${turn}` : ''}`;

  const right = document.createElement('div');
  right.innerHTML = route
    ? `<span class="route-badge">${window.escapeHtml(route)}</span>`
    : '';

  meta.appendChild(left);
  meta.appendChild(right);

  const body = document.createElement('div');
  body.className = 'thinking-wrap';
  body.innerHTML =
    `<span class="thinking-text">${window.escapeHtml(speaker || window.t('chat.gm') || 'GM')} my\u015bli</span>` +
    `<span class="typing-dots" aria-hidden="true"><span></span><span></span><span></span></span>`;

  wrap.appendChild(meta);
  wrap.appendChild(body);
  chatEl.appendChild(wrap);

  // Force layout so browser actually paints this before continuing
  // eslint-disable-next-line no-unused-expressions
  wrap.offsetHeight;

  window.scrollChatToBottom();
};

// --- STREAMING BUBBLE FUNCTIONS ---

/**
 * Creates the live streaming bubble, replacing the thinking bubble.
 *
 * KEY FIX: The bubble is given a FIXED width (var(--bubble-max)) from the
 * very start so it never resizes as tokens arrive. This eliminates the
 * layout-jitter / reflow-on-every-token problem.
 *
 * animation:none is applied via CSS (.streaming class) so there is no
 * re-entrance flash when transitioning from the thinking bubble.
 */
window.createStreamingBubble = function ({
  speaker = null,
  route = 'narrative',
  turn = null
} = {}) {
  const { chatEl } = window.getEls();
  if (!chatEl) return null;

  window.removeThinkingBubble();

  const wrap = document.createElement('div');
  wrap.className = 'message assistant streaming';
  wrap.id = 'streaming-bubble';

  const meta = document.createElement('div');
  meta.className = 'meta';

  const left = document.createElement('div');
  left.innerHTML =
    `<strong>${window.escapeHtml(speaker || window.t('chat.gm'))}</strong>` +
    `${turn ? ` \u2022 ${window.escapeHtml(window.t('chat.turn'))} ${turn}` : ''}`;

  const right = document.createElement('div');
  right.innerHTML = route
    ? `<span class="route-badge">${window.escapeHtml(route)}</span>`
    : '';

  meta.appendChild(left);
  meta.appendChild(right);

  const body = document.createElement('div');
  body.className = 'message-body';

  const pre = document.createElement('pre');
  pre.className = 'streaming-text';
  // Inline style only sets min-height as safety net; width is controlled by CSS
  pre.style.cssText = 'display:block;min-height:1.4em;white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere;';
  pre.textContent = '';

  body.appendChild(pre);
  wrap.appendChild(meta);
  wrap.appendChild(body);
  chatEl.appendChild(wrap);

  // Force layout paint before first token arrives
  // eslint-disable-next-line no-unused-expressions
  wrap.offsetHeight;

  window.scrollChatToBottom();
  return wrap;
};

/**
 * Appends a token to the streaming bubble's <pre>.
 * Throttled scroll — at most one scroll per animation frame.
 */
window.appendToStreamingBubble = function (bubbleEl, token) {
  if (!bubbleEl) return;
  const pre = bubbleEl.querySelector('pre.streaming-text');
  if (!pre) return;
  pre.textContent += token;
  window.scrollChatToBottomThrottled();
};

/**
 * Finalizes the streaming bubble: removes .streaming class so the bubble
 * shrinks back to fit-content width (natural size), removes inline style
 * lock, and adds action buttons if the narrative contains dice expressions.
 */
window.finalizeStreamingBubble = function (bubbleEl, fullText) {
  if (!bubbleEl) return;

  bubbleEl.classList.remove('streaming');
  bubbleEl.removeAttribute('id');

  // Remove inline min-height lock — let the bubble size to its content
  const pre = bubbleEl.querySelector('pre.streaming-text');
  if (pre) pre.style.cssText = '';

  const route = bubbleEl.querySelector('.route-badge')?.textContent || '';
  let renderedText = fullText;
  if (route === 'narrative' && typeof window.parsePendingRoll === 'function') {
    renderedText = window.parsePendingRoll(fullText);
    if (pre) pre.textContent = renderedText;
  } else if (typeof window.parsePendingRoll === 'function') {
    window.parsePendingRoll('');
  }

  if (route === 'narrative') {
    const pending = window.state.pendingRoll;
    const diceList = window.extractDiceFromText(renderedText);
    if (pending) {
      const canonicalSkill = pending.canonical_skill || pending.skill;
      window.state.activeRollRequest = {
        skill: canonicalSkill,
        display_name: pending.skill,
        dice: pending.dice,
        label: `Roll ${canonicalSkill} ${pending.dice}`,
      };
      window.updateActionTriggerBtn(true);
    } else if (diceList && diceList.length > 0) {
      window.state.activeRollRequest = diceList[0];
      window.updateActionTriggerBtn(true);
    } else {
      window.state.activeRollRequest = null;
      window.updateActionTriggerBtn();
    }
  }

  window.scrollChatToBottom();
};

// --- END STREAMING BUBBLE FUNCTIONS ---

// Detect dice expressions in text, return array of unique dice types
window.extractDiceFromText = function (text) {
  const matches = text.match(/\d*d\d+(?:[+-]\d+)?/gi);
  if (!matches) return [];
  const seen = new Set();
  const result = [];
  matches.forEach(m => {
    const clean = m.replace(/^\d+/, '').replace(/[+-]\d+$/, '');
    if (!seen.has(clean)) {
      seen.add(clean);
      result.push({ full: m, dice: clean });
    }
  });
  return result;
};

// Show inline dice roll dialog
window.showDiceDialog = function (wrapEl) {
  const existing = wrapEl.querySelector('.dice-dialog');
  if (existing) { existing.remove(); return; }

  const dialog = document.createElement('div');
  dialog.className = 'dice-dialog';

  const commonDice = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100'];

  dialog.innerHTML = `
    <div class="dice-dialog-title">Wybierz ko\u015b\u0107 lub wpisz:</div>
    <div class="dice-quick-btns">
      ${commonDice.map(d => `<button type="button" class="secondary dice-quick" data-dice="${d}">${d}</button>`).join('')}
    </div>
    <div class="dice-custom-row">
      <input type="text" class="dice-custom-input" placeholder="np. 2d6+3" style="width:110px;padding:4px 8px;border-radius:6px;border:1px solid var(--color-border,#ccc);background:var(--color-surface,#fff);color:inherit;font-size:0.9em;">
      <button type="button" class="secondary dice-custom-roll">Rzu\u0107</button>
    </div>
  `;

  wrapEl.appendChild(dialog);

  dialog.querySelectorAll('.dice-quick').forEach(btn => {
    btn.addEventListener('click', async () => {
      const dice = btn.getAttribute('data-dice');
      await window.rollAndAppend(dice, wrapEl);
      dialog.remove();
    });
  });

  dialog.querySelector('.dice-custom-roll').addEventListener('click', async () => {
    const val = dialog.querySelector('.dice-custom-input').value.trim();
    if (!val) return;
    await window.rollAndAppend(val, wrapEl);
    dialog.remove();
  });
};

// Roll dice and append result to chat
window.rollAndAppend = async function (diceExpr, wrapEl) {
  try {
    const resp = await fetch('/api/gm/dice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dice: diceExpr })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    window.addMessage({
      speaker: '\uD83C\uDFB2',
      text: `${data.dice} = [${data.rolls.join(', ')}] = ${data.total}`,
      role: 'system'
    });
  } catch (e) {
    window.addMessage({ speaker: 'B\u0142\u0105d', text: `Ko\u015b\u0107: ${e.message}`, role: 'error' });
  }
};

window.addMessage = function ({
  speaker,
  text,
  role = 'assistant',
  route = '',
  turn = null,
  createdAt = null
}) {
  const { chatEl } = window.getEls();
  if (!chatEl) return;

  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;

  const meta = document.createElement('div');
  meta.className = 'meta';

  const left = document.createElement('div');
  left.innerHTML =
    `<strong>${window.escapeHtml(speaker)}</strong>` +
    `${turn ? ` \u2022 ${window.escapeHtml(window.t('chat.turn'))} ${turn}` : ''}`;

  const right = document.createElement('div');
  const parts = [];

  if (route) {
    parts.push(`<span class="route-badge">${window.escapeHtml(route)}</span>`);
  }

  if (createdAt) {
    parts.push(`<span>${window.escapeHtml(window.formatTimestamp(createdAt))}</span>`);
  }

  right.innerHTML = parts.join(' ');

  meta.appendChild(left);
  meta.appendChild(right);

  const body = document.createElement('div');
  body.className = 'message-body';
  body.innerHTML = `<pre>${window.escapeHtml(text)}</pre>`;

  wrap.appendChild(meta);
  wrap.appendChild(body);
  chatEl.appendChild(wrap);

  window.scrollChatToBottom();
};

window.replaceThinkingBubble = function ({
  speaker,
  text,
  role = 'assistant',
  route = '',
  turn = null,
  createdAt = null
}) {
  const { chatEl } = window.getEls();
  if (!chatEl) return;

  const existing = chatEl.querySelector('#thinking-bubble');
  if (!existing) {
    window.addMessage({ speaker, text, role, route, turn, createdAt });
    return;
  }

  let renderedText = text;
  if (route === 'narrative' && typeof window.parsePendingRoll === 'function') {
    renderedText = window.parsePendingRoll(text);
  } else if (typeof window.parsePendingRoll === 'function') {
    window.parsePendingRoll('');
  }

  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;

  const meta = document.createElement('div');
  meta.className = 'meta';

  const left = document.createElement('div');
  left.innerHTML =
    `<strong>${window.escapeHtml(speaker)}</strong>` +
    `${turn ? ` \u2022 ${window.escapeHtml(window.t('chat.turn'))} ${turn}` : ''}`;

  const right = document.createElement('div');
  const parts = [];

  if (route) {
    parts.push(`<span class="route-badge">${window.escapeHtml(route)}</span>`);
  }

  if (createdAt) {
    parts.push(`<span>${window.escapeHtml(window.formatTimestamp(createdAt))}</span>`);
  }

  right.innerHTML = parts.join(' ');

  meta.appendChild(left);
  meta.appendChild(right);

  const body = document.createElement('div');
  body.className = 'message-body';
  body.innerHTML = `<pre>${window.escapeHtml(renderedText)}</pre>`;

  wrap.appendChild(meta);
  wrap.appendChild(body);

  if (role === 'assistant' && route === 'narrative') {
    const pending = window.state.pendingRoll;
    const diceList = window.extractDiceFromText(renderedText);
    if (pending) {
      const canonicalSkill = pending.canonical_skill || pending.skill;
      window.state.activeRollRequest = {
        skill: canonicalSkill,
        display_name: pending.skill,
        dice: pending.dice,
        label: `Roll ${canonicalSkill} ${pending.dice}`,
      };
      window.updateActionTriggerBtn(true);
    } else if (diceList && diceList.length > 0) {
      window.state.activeRollRequest = diceList[0];
      window.updateActionTriggerBtn(true);
    } else {
      window.state.activeRollRequest = null;
      window.updateActionTriggerBtn();
    }
  }

  existing.replaceWith(wrap);
  window.scrollChatToBottom();
};

window.addJsonMessage = function (
  title,
  obj,
  role = 'assistant',
  route = 'command',
  turn = window.state.turnNumbers?.[window.state.selectedCampaignId] || 0,
  createdAt = null
) {
  window.addMessage({
    speaker: title,
    text: JSON.stringify(obj, null, 2),
    role,
    route,
    turn,
    createdAt
  });
};

window.updateUiState = function () {
  const els = window.getEls();
  const activeCampaign = window.currentCampaign ? window.currentCampaign() : null;
  const hasCampaign = !!activeCampaign;
  const hasCharacter = !!window.state.selectedCharacterId;
  const shouldForceCharacterModal = hasCampaign && !hasCharacter;
  const shouldShowCharacterModal = shouldForceCharacterModal || window.characterModalOpen;

  if (els.deleteCampaignBtn) els.deleteCampaignBtn.disabled = !hasCampaign;
  if (els.createCharacterBtn) els.createCharacterBtn.disabled = !hasCampaign;
  if (els.sendBtn) els.sendBtn.disabled = !(hasCampaign && hasCharacter);

  if (els.characterCreateCloseEl) {
    els.characterCreateCloseEl.style.display = shouldForceCharacterModal ? 'none' : 'inline-flex';
  }
  if (els.chatEl) {
    els.chatEl.style.display = shouldForceCharacterModal ? 'none' : 'flex';
  }
  if (els.composerEl) {
    els.composerEl.style.display = shouldForceCharacterModal ? 'none' : 'grid';
  }
  if (els.historyPanelEl) {
    els.historyPanelEl.style.display = shouldForceCharacterModal ? 'none' : els.historyPanelEl.style.display;
  }
  if (els.characterCreateOverlayEl) {
    els.characterCreateOverlayEl.style.display = shouldShowCharacterModal ? 'flex' : 'none';
    els.characterCreateOverlayEl.setAttribute('aria-hidden', shouldShowCharacterModal ? 'false' : 'true');
  }
  if (els.campaignCreateOverlayEl) {
    els.campaignCreateOverlayEl.style.display = window.campaignModalOpen ? 'flex' : 'none';
    els.campaignCreateOverlayEl.setAttribute('aria-hidden', window.campaignModalOpen ? 'false' : 'true');
  }
};

window.renderTurnResponse = function (data, turnNumber) {
  const createdAt = data?.created_at || null;

  if (!data || typeof data !== 'object') {
    window.removeThinkingBubble();
    window.addMessage({
      speaker: 'System',
      text: window.t('error.invalid_response'),
      role: 'error',
      turn: turnNumber,
      createdAt
    });
    return;
  }

  if (data.route === 'command') {
    const result = data.result || data;
    const renamedTo = result.character_name || result.name || null;

    if (result.command === '/name' && renamedTo) {
      const active = window.currentCharacter();
      if (active) active.name = renamedTo;

      const { characterSelectEl } = window.getEls();
      const option = characterSelectEl
        ? characterSelectEl.querySelector(
            `option[value="${window.state.selectedCharacterId}"]`
          )
        : null;

      if (option) option.textContent = renamedTo;

      window.removeThinkingBubble();
      window.addMessage({
        speaker: 'System',
        text: `${window.t('system.name_changed')} ${renamedTo}`,
        role: 'system',
        route: 'command',
        turn: turnNumber,
        createdAt
      });
      return;
    }

    if (result.command === '/sheet') {
      window.removeThinkingBubble();
      window.addJsonMessage(
        'Karta postaci',
        result.character || result,
        'assistant',
        'command',
        turnNumber,
        createdAt
      );
      return;
    }

    window.removeThinkingBubble();
    window.addJsonMessage(
      `Wynik ${result.command || 'komendy'}`,
      result,
      'assistant',
      'command',
      turnNumber,
      createdAt
    );
    return;
  }

  if (data.route === 'narrative') {
    const result = data.result || {};
    const message = result.message || result.content || 'Brak odpowiedzi';

    window.replaceThinkingBubble({
      speaker: window.t('chat.gm'),
      text: message,
      role: 'assistant',
      route: 'narrative',
      turn: turnNumber,
      createdAt
    });
    return;
  }

  window.removeThinkingBubble();
  window.addJsonMessage(
    'Odpowied\u017a',
    data,
    'assistant',
    'unknown',
    turnNumber,
    createdAt
  );
};

window.clearChat = function () {
  const { chatEl } = window.getEls();
  if (chatEl) chatEl.innerHTML = '';
};

window.clearHistoryPanel = function () {
  const historyPanelEl = document.getElementById('history-panel');
  if (historyPanelEl) {
    historyPanelEl.innerHTML = '<div class="muted">Brak historii.</div>';
  }
};

window.renderHistoryPanel = function () {
  const historyPanelEl = document.getElementById('history-panel');
  const turns = Array.isArray(window.state.turns) ? window.state.turns : [];

  if (!historyPanelEl) return;

  if (turns.length === 0) {
    historyPanelEl.innerHTML = '<div class="muted">Brak historii.</div>';
    return;
  }

  historyPanelEl.innerHTML = '';

  turns.forEach((turn) => {
    const item = document.createElement('div');
    item.className = 'message system';

    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.innerHTML = `
      <div>
        <strong>Tura ${window.escapeHtml(turn.turn_number || turn.id)}</strong>
        \u2022 ${window.escapeHtml(turn.character_name || 'Gracz')}
      </div>
      <div>${window.escapeHtml(window.formatTimestamp(turn.created_at))}</div>
    `;

    const body = document.createElement('div');
    body.className = 'message-body';
    body.innerHTML = `
      <pre>${window.escapeHtml(turn.user_text || '')}</pre>
      <div style="margin-top:8px;">
        <button type="button" class="secondary replay-turn-btn" data-text="${window.escapeHtml(turn.user_text || '')}">
          Wy\u015blij ponownie
        </button>
      </div>
    `;

    item.appendChild(meta);
    item.appendChild(body);
    historyPanelEl.appendChild(item);
  });

  historyPanelEl.querySelectorAll('.replay-turn-btn').forEach((btn) => {
    btn.onclick = () => {
      const { inputEl } = window.getEls();
      if (!inputEl) return;
      inputEl.value = btn.getAttribute('data-text') || '';
      inputEl.focus();
    };
  });
};

window.renderTurnsToChat = function () {
  window.clearChat();
  window.removeThinkingBubble();

  const turns = Array.isArray(window.state.turns) ? window.state.turns : [];
  let lastNarrativeRollRequest = null;

  turns.forEach((turn) => {
    if (turn.user_text) {
      window.addMessage({
        speaker: turn.character_name || 'Gracz',
        text: turn.user_text,
        role: 'user',
        route: 'input',
        turn: turn.turn_number || turn.id,
        createdAt: turn.created_at
      });
    }

    if (turn.assistant_text) {
      if (turn.route === 'narrative') {
        const assistantText = String(turn.assistant_text || '');
        if (!assistantText.trim()) return;

        const msgWrap = document.createElement('div');
        msgWrap.className = 'message assistant';
        const { chatEl } = window.getEls();

        const meta = document.createElement('div');
        meta.className = 'meta';
        const left = document.createElement('div');
        left.innerHTML =
          `<strong>${window.escapeHtml(window.t('chat.gm'))}</strong>` +
          ` \u2022 ${window.escapeHtml(window.t('chat.turn'))} ${turn.turn_number || turn.id}`;
        const right = document.createElement('div');
        right.innerHTML =
          `<span class="route-badge">narrative</span>` +
          ` <span>${window.escapeHtml(window.formatTimestamp(turn.created_at))}</span>`;
        meta.appendChild(left);
        meta.appendChild(right);

        const body = document.createElement('div');
        body.className = 'message-body';
        body.innerHTML = `<pre>${window.escapeHtml(assistantText)}</pre>`;

        msgWrap.appendChild(meta);
        msgWrap.appendChild(body);

        const lines = assistantText.split('\n');
        const lastLineRaw = (lines[lines.length - 1] || '').trim();
        const cueMatch = lastLineRaw.match(/^Roll (.+?) (d\d+)$/i);
        if (cueMatch) {
          const rawName = (cueMatch[1] || '').trim();
          const canonicalSkill = typeof window.resolveRollTestName === 'function'
            ? window.resolveRollTestName(rawName)
            : null;
          if (canonicalSkill) {
            const displayName = typeof window.formatRollTestDisplayName === 'function'
              ? window.formatRollTestDisplayName(canonicalSkill)
              : canonicalSkill;
            lastNarrativeRollRequest = {
              skill: canonicalSkill,
              display_name: displayName,
              dice: (cueMatch[2] || 'd20').toLowerCase(),
              label: `Roll ${canonicalSkill} ${(cueMatch[2] || 'd20').toLowerCase()}`,
            };
          } else {
            lastNarrativeRollRequest = null;
          }
        } else {
          const diceList = window.extractDiceFromText(assistantText);
          lastNarrativeRollRequest = (diceList && diceList.length > 0) ? diceList[0] : null;
        }

        if (chatEl) chatEl.appendChild(msgWrap);
      } else {
        window.addMessage({
          speaker: 'System',
          text: turn.assistant_text,
          role: 'system',
          route: turn.route || 'command',
          turn: turn.turn_number || turn.id,
          createdAt: turn.created_at
        });
      }
    }
  });

  window.state.activeRollRequest = lastNarrativeRollRequest;
  window.updateActionTriggerBtn(!!lastNarrativeRollRequest);
  window.scrollChatToBottom();
};

window.updateActionTriggerBtn = function (openPopup = false) {
  const hasActiveRoll = !!window.state.activeRollRequest;
  const popup = document.getElementById('action-popup');
  if (!popup) return;
  if (hasActiveRoll && openPopup) {
    popup.classList.remove('hidden');
    if (typeof window.positionActionPopup === 'function') {
      window.positionActionPopup();
    }
    if (typeof window.setActionInputLocked === 'function') {
      window.setActionInputLocked(true);
    }
  } else {
    popup.classList.add('hidden');
    if (typeof window.setActionInputLocked === 'function') {
      window.setActionInputLocked(false);
    }
  }
};

window.positionActionPopup = function () {
  const popup = document.getElementById('action-popup');
  const sheetPanel = document.getElementById('sheet-panel');
  const diceBtn = document.getElementById('dice-btn');
  if (!popup) return;

  const anchorEl = (sheetPanel && sheetPanel.offsetParent !== null) ? sheetPanel : diceBtn;
  if (!anchorEl) return;

  const anchorRect = anchorEl.getBoundingClientRect();
  const popupRect = popup.getBoundingClientRect();
  const gap = 12;

  let left = anchorRect.left + (anchorRect.width / 2) - (popupRect.width / 2);
  let top = anchorRect.bottom + gap;

  const minMargin = 12;
  const maxLeft = window.innerWidth - popupRect.width - minMargin;
  left = Math.max(minMargin, Math.min(left, maxLeft));
  const maxTop = window.innerHeight - popupRect.height - minMargin;
  top = Math.max(minMargin, Math.min(top, maxTop));

  popup.style.left = `${Math.round(left)}px`;
  popup.style.top = `${Math.round(top)}px`;
};

window.setActionInputLocked = function (locked) {
  const { inputEl } = window.getEls();
  if (!inputEl) return;
  inputEl.readOnly = !!locked;
  if (locked) {
    inputEl.value = '';
    inputEl.placeholder = 'Wybierz: 🎲 Rzuć kość lub ✍️ Akcja';
    inputEl.blur();
  } else if (inputEl.placeholder === 'Wybierz: 🎲 Rzuć kość lub ✍️ Akcja') {
    inputEl.placeholder = 'Wpisz /sheet albo opisz akcję...';
  }
};

window.initActionPopup = function () {
  const popup = document.getElementById('action-popup');
  const rollBtn = document.getElementById('popup-roll-btn');
  const actionBtn = document.getElementById('popup-action-btn');

  if (!popup || !rollBtn || !actionBtn) return;

  const repositionIfVisible = () => {
    if (!popup.classList.contains('hidden') && typeof window.positionActionPopup === 'function') {
      window.positionActionPopup();
    }
  };

  window.addEventListener('resize', repositionIfVisible);
  window.addEventListener('scroll', repositionIfVisible, true);

  // Keep popup visible while a roll decision is pending.
  // Do not close on outside click; close only via explicit action buttons.

  // Rzuć kość
  rollBtn.addEventListener('click', async () => {
    popup.classList.add('hidden');
    const req = window.state.activeRollRequest;
    if (!req) return;
    const { inputEl } = window.getEls();
    const rollSkill = (req.skill || 'melee_attack').trim() || 'melee_attack';
    const rollDice = (req.dice || 'd20').trim().toLowerCase() || 'd20';
    if (inputEl) {
      inputEl.value = `/roll ${rollSkill} ${rollDice}`;
    }
    await window.sendMessage();
    window.state.activeRollRequest = null;
    window.updateActionTriggerBtn();
  });

  // Akcja — fokus na input z hintami
  actionBtn.addEventListener('click', () => {
    popup.classList.add('hidden');
    const { inputEl } = window.getEls();
    window.setActionInputLocked(false);
    if (inputEl) {
      inputEl.placeholder = 'Opisz swoją akcję...';
      inputEl.focus();
    }
  });
};
