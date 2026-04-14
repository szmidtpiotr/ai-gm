window.getEls = function () {
  return {
    appTitleEl: document.getElementById('app-title'),
    campaignSelectEl: document.getElementById('campaign-select'),
    characterSelectEl: document.getElementById('character-select'),
    systemSelectEl: document.getElementById('system-select'),
    engineSelectEl: document.getElementById('engine-select'),
    ollamaUrlEl: document.getElementById('ollama-url'),
    testOllamaBtn: document.getElementById('test-ollama-btn'),
    chatEl: document.getElementById('chat'),
    inputEl: document.getElementById('input'),
    sendBtn: document.getElementById('send-btn'),
    diceBtn: document.getElementById('dice-btn'),
    createCampaignBtn: document.getElementById('create-campaign-btn'),
    deleteCampaignBtn: document.getElementById('delete-campaign-btn'),
    createCharacterBtn: document.getElementById('create-character-btn'),
    statusBackendEl: document.getElementById('status-backend'),
    statusOllamaEl: document.getElementById('status-ollama'),
    statusModelsEl: document.getElementById('status-models'),
    statusHostEl: document.getElementById('status-host'),
    labelCampaignEl: document.getElementById('label-campaign'),
    labelCharacterEl: document.getElementById('label-character'),
    labelSystemEl: document.getElementById('label-system'),
    labelEngineEl: document.getElementById('label-engine'),
    labelOllamaUrlEl: document.getElementById('label-ollama-url')
  };
};

window.applyTranslations = function () {
  const els = window.getEls();

  if (els.appTitleEl) els.appTitleEl.textContent = window.t('app.title');
  if (els.labelCampaignEl) els.labelCampaignEl.textContent = window.t('campaign.label');
  if (els.labelCharacterEl) els.labelCharacterEl.textContent = window.t('character.label');
  if (els.labelSystemEl) els.labelSystemEl.textContent = window.t('system.label');
  if (els.labelEngineEl) els.labelEngineEl.textContent = window.t('engine.label');
  if (els.labelOllamaUrlEl) els.labelOllamaUrlEl.textContent = 'Ollama Host';
  if (els.inputEl) els.inputEl.placeholder = window.t('input.placeholder');
  if (els.sendBtn) els.sendBtn.textContent = window.t('button.send');
};

window.scrollChatToBottom = function () {
  const { chatEl } = window.getEls();
  if (!chatEl) return;

  requestAnimationFrame(() => {
    chatEl.scrollTop = chatEl.scrollHeight;
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
    `${turn ? ` • ${window.escapeHtml(window.t('chat.turn'))} ${turn}` : ''}`;

  const right = document.createElement('div');
  right.innerHTML = route
    ? `<span class="route-badge">${window.escapeHtml(route)}</span>`
    : '';

  meta.appendChild(left);
  meta.appendChild(right);

  const body = document.createElement('div');
  body.className = 'thinking-wrap';
  body.innerHTML = `
    <span class="thinking-text">${window.escapeHtml(speaker || window.t('chat.gm') || 'GM')} myśli</span>
    <span class="typing-dots" aria-hidden="true">
      <span></span>
      <span></span>
      <span></span>
    </span>
  `;

  wrap.appendChild(meta);
  wrap.appendChild(body);
  chatEl.appendChild(wrap);

  window.scrollChatToBottom();
};

// Detect dice expressions in a string and return array of unique dice types found (e.g. ["d20","d6"])
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
  // Remove existing dialog if any
  const existing = wrapEl.querySelector('.dice-dialog');
  if (existing) { existing.remove(); return; }

  const dialog = document.createElement('div');
  dialog.className = 'dice-dialog';

  const commonDice = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100'];

  dialog.innerHTML = `
    <div class="dice-dialog-title">Wybierz kość lub wpisz:</div>
    <div class="dice-quick-btns">
      ${commonDice.map(d => `<button type="button" class="secondary dice-quick" data-dice="${d}">${d}</button>`).join('')}
    </div>
    <div class="dice-custom-row">
      <input type="text" class="dice-custom-input" placeholder="np. 2d6+3" style="width:110px;padding:4px 8px;border-radius:6px;border:1px solid var(--color-border,#ccc);background:var(--color-surface,#fff);color:inherit;font-size:0.9em;">
      <button type="button" class="secondary dice-custom-roll">Rzuć</button>
    </div>
  `;

  wrapEl.appendChild(dialog);

  // Quick dice buttons
  dialog.querySelectorAll('.dice-quick').forEach(btn => {
    btn.addEventListener('click', async () => {
      const dice = btn.getAttribute('data-dice');
      await window.rollAndAppend(dice, wrapEl);
      dialog.remove();
    });
  });

  // Custom input roll
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
    const resp = await fetch('/gm/dice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dice: diceExpr })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    window.addMessage({
      speaker: '🎲',
      text: `${data.dice} = [${data.rolls.join(', ')}] = ${data.total}`,
      role: 'system'
    });
  } catch (e) {
    window.addMessage({ speaker: 'Błąd', text: `Kość: ${e.message}`, role: 'error' });
  }
};

// Append action bar to a GM narrative message element
// Roll buttons only shown when GM text contains dice expressions
window.appendActionButtons = function (wrapEl, diceList) {
  const hasDice = diceList && diceList.length > 0;

  // Only show action bar when there are dice to roll
  if (!hasDice) return;

  const bar = document.createElement('div');
  bar.className = 'action-bar';

  // Add specific dice buttons detected from GM text
  diceList.forEach(({ full, dice }) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'secondary action-dice-btn';
    btn.textContent = `🎲 Rzuć ${dice}`;
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      await window.rollAndAppend(full, wrapEl);
      btn.disabled = false;
    });
    bar.appendChild(btn);
  });

  // Dice chooser button (custom roll)
  const diceChooseBtn = document.createElement('button');
  diceChooseBtn.type = 'button';
  diceChooseBtn.className = 'secondary action-dice-choose-btn';
  diceChooseBtn.textContent = '🎲 Rzuć kość';
  diceChooseBtn.addEventListener('click', () => {
    window.showDiceDialog(wrapEl);
  });
  bar.appendChild(diceChooseBtn);

  // Focus input button
  const focusBtn = document.createElement('button');
  focusBtn.type = 'button';
  focusBtn.className = 'secondary';
  focusBtn.textContent = '✍️ Inna akcja';
  focusBtn.addEventListener('click', () => {
    const { inputEl } = window.getEls();
    if (inputEl) inputEl.focus();
  });
  bar.appendChild(focusBtn);

  wrapEl.appendChild(bar);
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
    `${turn ? ` • ${window.escapeHtml(window.t('chat.turn'))} ${turn}` : ''}`;

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

  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;

  const meta = document.createElement('div');
  meta.className = 'meta';

  const left = document.createElement('div');
  left.innerHTML =
    `<strong>${window.escapeHtml(speaker)}</strong>` +
    `${turn ? ` • ${window.escapeHtml(window.t('chat.turn'))} ${turn}` : ''}`;

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

  // Add action bar only when GM narrative contains dice expressions
  if (role === 'assistant' && route === 'narrative') {
    const diceList = window.extractDiceFromText(text);
    window.appendActionButtons(wrap, diceList);
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
  const hasCampaign = !!window.state.selectedCampaignId;
  const hasCharacter = !!window.state.selectedCharacterId;

  if (els.deleteCampaignBtn) els.deleteCampaignBtn.disabled = !hasCampaign;
  if (els.createCharacterBtn) els.createCharacterBtn.disabled = !hasCampaign;
  if (els.sendBtn) els.sendBtn.disabled = !(hasCampaign && hasCharacter);
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
    'Odpowiedź',
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
        • ${window.escapeHtml(turn.character_name || 'Gracz')}
      </div>
      <div>${window.escapeHtml(window.formatTimestamp(turn.created_at))}</div>
    `;

    const body = document.createElement('div');
    body.className = 'message-body';
    body.innerHTML = `
      <pre>${window.escapeHtml(turn.user_text || '')}</pre>
      <div style="margin-top:8px;">
        <button type="button" class="secondary replay-turn-btn" data-text="${window.escapeHtml(turn.user_text || '')}">
          Wyślij ponownie
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
        const msgWrap = document.createElement('div');
        msgWrap.className = 'message assistant';
        const { chatEl } = window.getEls();

        const meta = document.createElement('div');
        meta.className = 'meta';
        const left = document.createElement('div');
        left.innerHTML = `<strong>${window.escapeHtml(window.t('chat.gm'))}</strong> • ${window.escapeHtml(window.t('chat.turn'))} ${turn.turn_number || turn.id}`;
        const right = document.createElement('div');
        right.innerHTML = `<span class="route-badge">narrative</span> <span>${window.escapeHtml(window.formatTimestamp(turn.created_at))}</span>`;
        meta.appendChild(left);
        meta.appendChild(right);

        const body = document.createElement('div');
        body.className = 'message-body';
        body.innerHTML = `<pre>${window.escapeHtml(turn.assistant_text)}</pre>`;

        msgWrap.appendChild(meta);
        msgWrap.appendChild(body);

        // Add action bar only when GM text contains dice expressions
        const diceList = window.extractDiceFromText(turn.assistant_text);
        window.appendActionButtons(msgWrap, diceList);

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

  window.scrollChatToBottom();
};
