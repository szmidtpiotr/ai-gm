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
  body.innerHTML = `<pre>${window.escapeHtml(text)}</pre>`;

  wrap.appendChild(meta);
  wrap.appendChild(body);
  chatEl.appendChild(wrap);
  chatEl.scrollTop = chatEl.scrollHeight;
};

window.addJsonMessage = function (
  title,
  obj,
  role = 'assistant',
  route = 'command',
  turn = window.state.turnNumber,
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

    window.addMessage({
      speaker: window.t('chat.gm'),
      text: message,
      role: 'assistant',
      route: 'narrative',
      turn: turnNumber,
      createdAt
    });
    return;
  }

  window.addJsonMessage('Odpowiedź', data, 'assistant', 'unknown', turnNumber, createdAt);
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
        window.addMessage({
          speaker: window.t('chat.gm'),
          text: turn.assistant_text,
          role: 'assistant',
          route: 'narrative',
          turn: turn.turn_number || turn.id,
          createdAt: turn.created_at
        });
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

  const chatEl = document.getElementById('chat');
  if (chatEl) {
    requestAnimationFrame(() => {
      chatEl.scrollTop = chatEl.scrollHeight;
    });
  }
};