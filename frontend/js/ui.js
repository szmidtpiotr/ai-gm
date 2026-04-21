window.getEls = function () {
  return {
    appTitleEl: document.getElementById('app-title'),
    campaignSelectEl: document.getElementById('campaign-select'),
    systemSelectEl: document.getElementById('system-select'),
    engineSelectEl: document.getElementById('engine-select'),
    llmProviderSelectEl: document.getElementById('llm-provider-select'),
    llmBaseUrlInputEl: document.getElementById('llm-base-url-input'),
    llmApiKeyInputEl: document.getElementById('llm-api-key-input'),
    llmBaseUrlFieldEl: document.getElementById('llm-base-url-field'),
    llmApiKeyFieldEl: document.getElementById('llm-api-key-field'),
    showAllModelsToggleEl: document.getElementById('show-all-models-toggle'),
    openaiModelsToggleWrapEl: document.getElementById('openai-models-toggle-wrap'),
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
    statusBackendDotEl: document.getElementById('status-backend-dot'),
    statusOllamaDotEl: document.getElementById('status-ollama-dot'),
    statusLokiDotEl: document.getElementById('status-loki-dot'),
    labelCampaignEl: document.getElementById('label-campaign'),
    labelSystemEl: document.getElementById('label-system'),
    labelEngineEl: document.getElementById('label-engine'),
    labelLlmProviderEl: document.getElementById('label-llm-provider'),
    labelLlmBaseUrlEl: document.getElementById('label-llm-base-url'),
    labelLlmApiKeyEl: document.getElementById('label-llm-api-key'),
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
  if (open) {
    if (!window.state.charCreationWizard && typeof window.resetCharacterCreationWizardUi === 'function') {
      window.resetCharacterCreationWizardUi();
    }
    if (els.characterCreateNameEl) {
      setTimeout(() => els.characterCreateNameEl.focus(), 0);
    }
  } else if (typeof window.resetCharacterCreationWizardUi === 'function') {
    window.resetCharacterCreationWizardUi();
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
  if (els.labelSystemEl) els.labelSystemEl.textContent = window.t('system.label');
  if (els.labelEngineEl) els.labelEngineEl.textContent = 'Model';
  if (els.labelLlmProviderEl) els.labelLlmProviderEl.textContent = 'Provider';
  if (els.labelLlmBaseUrlEl) els.labelLlmBaseUrlEl.textContent = 'URL';
  if (els.labelLlmApiKeyEl) els.labelLlmApiKeyEl.textContent = 'API Key';
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
  if (route === 'memory') {
    wrap.classList.add('memory-turn');
  }
  if (route === 'helpme') {
    wrap.classList.add('helpme-turn');
  }
  if (route && route !== 'narrative') {
    wrap.classList.add('is-archived-bubble');
    wrap.setAttribute('data-archived', '1');
  }
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
          description: pending.description || '',
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

window.addBackInGameSeparator = function () {
  const { chatEl } = window.getEls();
  if (!chatEl) return;
  const row = document.createElement('div');
  row.className = 'chat-back-in-game';
  row.textContent = '\u2014 wracamy do gry \u2014';
  chatEl.appendChild(row);
  window.scrollChatToBottom();
  window.updateArchiveToggleUi?.();
};

// Decyduje, czy dany dymek ma być "archiwalny" (ukrywany domyślnie).
// Widoczne są tylko: input gracza (narracyjny) oraz narracja GM.
window.isArchiveBubble = function ({ role, route, memoryTurn, helpmeTurn } = {}) {
  if (memoryTurn || helpmeTurn) return true;
  if (role === 'system' || role === 'error') return true;
  if (role === 'assistant') {
    if (!route || route === 'narrative') return false;
    return true;
  }
  if (role === 'user') {
    if (!route || route === 'input' || route === 'dice') return false;
    return true;
  }
  return false;
};

window.ROLL_CARD_PREFIX = '__AI_GM_ROLL_V1__';

window.tryParseRollCardFromText = function (text) {
  const s = String(text || '').trim();
  const p = window.ROLL_CARD_PREFIX;
  if (!s.startsWith(p + '\n')) return null;
  try {
    return JSON.parse(s.slice(p.length).trim());
  } catch (_e) {
    return null;
  }
};

/** Rich combat attack / enemy attack bubble — must match backend COMBAT_ROLL_CTX_PREFIX. */
window.COMBAT_ROLL_PREFIX = '__AI_GM_COMBAT_ROLL_V1__';

window.tryParseCombatRollCardFromText = function (text) {
  const s = String(text || '').trim();
  const p = window.COMBAT_ROLL_PREFIX;
  if (!s.startsWith(p + '\n')) return null;
  try {
    return JSON.parse(s.slice(p.length).trim());
  } catch (_e) {
    return null;
  }
};

window.formatCombatRollNum = function (n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return '—';
  if (v === 0) return '0';
  return v > 0 ? String(v) : '\u2212' + String(Math.abs(v));
};

window.buildCombatRollCardHtml = function (data) {
  if (!data || typeof data !== 'object') return '';
  const kind = String(data.kind || 'player_attack');
  const intent = String(data.intent || '').trim();
  const name = window.escapeHtml(String(data.character_name || data.enemy_name || '?'));
  const label = window.escapeHtml(String(data.attack_label || 'ATAK (STR)'));
  const d20 = Number(data.d20);
  const mods = Array.isArray(data.modifiers) ? data.modifiers : [];
  const modSegs = mods
    .map((m) => {
      const nm = window.escapeHtml(String(m.name || '?'));
      const vl = window.formatCombatRollNum(Number(m.value));
      return `${nm}: ${vl}`;
    })
    .join('&nbsp;&nbsp;|&nbsp;&nbsp;');
  const total = window.formatCombatRollNum(Number(data.total));
  const hit = !!data.hit;
  const dmg = data.damage != null ? String(data.damage) : '?';
  const ac = data.target_ac != null ? window.formatCombatRollNum(Number(data.target_ac)) : null;

  let cardMod = 'roll-card--neutral';
  if (kind === 'enemy_attack') {
    cardMod = hit ? 'roll-card--success' : 'roll-card--fail';
  } else {
    cardMod = hit ? 'roll-card--success' : 'roll-card--fail';
  }

  let line5 = '';
  if (kind === 'enemy_attack') {
    line5 = hit
      ? `Cel: obrona ${ac != null ? ac : '—'} — ✅ TRAFIENIE — ${dmg} obrażeń!`
      : `Cel: obrona ${ac != null ? ac : '—'} — ❌ PUDŁO`;
  } else {
    line5 = hit
      ? `Atakuję z wynikiem ${total} — ✅ SUKCES — trafiam za ${dmg} obrażeń!`
      : `Atakuję z wynikiem ${total} — ❌ PUDŁO`;
  }

  const intentBlock = intent
    ? `<div class="combat-roll-card__intent">${window.escapeHtml(intent)}</div><div class="roll-card__sep" role="separator"></div>`
    : '';

  return (
    `<div class="roll-card roll-card--light combat-roll-card ${cardMod}">` +
    `${intentBlock}` +
    `<div class="roll-card__line roll-card__line--head">🎲 ${name} \u2014 ${label}</div>` +
    `<div class="roll-card__line roll-card__line--detail">` +
    `1d20:&nbsp;&nbsp;<span class="roll-card__die">${Number.isFinite(d20) ? d20 : '?'}</span>` +
    (modSegs
      ? `&nbsp;&nbsp;|&nbsp;&nbsp; ${modSegs} &nbsp;&nbsp;|&nbsp;&nbsp; Wynik: <strong>${total}</strong>`
      : `&nbsp;&nbsp;|&nbsp;&nbsp; Wynik: <strong>${total}</strong>`) +
    `</div>` +
    `<div class="roll-card__line roll-card__line--wynik">${window.escapeHtml(line5)}</div>` +
    `</div>`
  );
};

window.formatRollModifier = function (mod) {
  const n = Number(mod);
  if (!Number.isFinite(n)) return '±0';
  if (n === 0) return '±0';
  return n > 0 ? `+${n}` : `${n}`;
};

window.dcLabelPl = function (dc) {
  if (dc == null || dc === '') return '—';
  const n = Number(dc);
  if (!Number.isFinite(n)) return '—';
  const DC_LABELS = { 8: 'Łatwe', 12: 'Średnie', 16: 'Trudne', 20: 'Ekstremalne', 25: 'Legendarne' };
  const keys = Object.keys(DC_LABELS)
    .map(Number)
    .filter((k) => k <= n);
  const best = keys.length ? Math.max(...keys) : null;
  return best != null ? DC_LABELS[best] : String(n);
};

window.rollSkillDisplayNamePl = function (skill) {
  const k = String(skill || '').trim();
  const SKILL_NAMES = {
    attack: 'Atak (STR)',
    athletics: 'Atletyka (STR)',
    stealth: 'Skradanie (DEX)',
    sleight_of_hand: 'Zręczność rąk (DEX)',
    endurance: 'Wytrzymałość (CON)',
    arcana: 'Arkana (INT)',
    investigation: 'Śledztwo (INT)',
    lore: 'Wiedza (INT)',
    awareness: 'Spostrzegawczość (WIS)',
    survival: 'Przetrwanie (WIS)',
    medicine: 'Medycyna (WIS)',
    persuasion: 'Perswazja (CHA)',
    intimidation: 'Zastraszanie (CHA)',
    melee_attack: 'Atak (STR)',
    ranged_attack: 'Atak dystansowy (DEX)',
    spell_attack: 'Atak magiczny (INT)',
    death_save: 'Rzut przeciw śmierci',
    fortitude_save: 'Rzut obronny: Tężyzna (CON)',
    reflex_save: 'Rzut obronny: Refleks (DEX)',
    willpower_save: 'Rzut obronny: Wola (WIS)',
    arcane_save: 'Rzut obronny: Intelekt (INT)',
    dex_save: 'Rzut obronny: Refleks (DEX)',
    con_save: 'Rzut obronny: Tężyzna (CON)',
    wis_save: 'Rzut obronny: Wola (WIS)',
    str_save: 'Rzut obronny: Siła (STR)',
    int_save: 'Rzut obronny: Intelekt (INT)',
    cha_save: 'Rzut obronny: Charyzma (CHA)',
    alchemy: 'Alchemia (INT)'
  };
  return SKILL_NAMES[k] || k;
};

window.buildRollCardHtml = function (data) {
  const rolled = Number(data.rolled);
  const mod = Number(data.modifier);
  const total = Number(data.total);
  const dc = data.dc != null && data.dc !== '' ? Number(data.dc) : null;
  const success = data.success;
  const isNat20 = !!data.is_nat20;
  const isNat1 = !!data.is_nat1;
  const rt = String(data.roll_type || '');

  let dieCls = 'roll-card__die';
  if (rolled === 20) dieCls += ' roll-card__die--nat20';

  let cardMod = 'roll-card--neutral';
  if (rt === 'attack' && isNat20) {
    cardMod = 'roll-card--success';
  } else if (rt === 'attack' && isNat1) {
    cardMod = 'roll-card--fail';
  } else if (success === true) {
    cardMod = 'roll-card--success';
  } else if (success === false) {
    cardMod = 'roll-card--fail';
  }

  const skillLabel = window.rollSkillDisplayNamePl(String(data.skill || ''));
  const modStr = window.formatRollModifier(mod);
  const dcLabel = dc != null ? window.dcLabelPl(dc) : '';

  let wynikTail = '';
  if (rt === 'attack' && isNat20) {
    wynikTail = ` \u2014 ${window.escapeHtml('⚡ TRAFIENIE KRYTYCZNE')}`;
  } else if (rt === 'attack' && isNat1) {
    wynikTail = ` \u2014 ${window.escapeHtml('💀 KRYTYCZNA PORAŻKA')}`;
  } else {
    if (success === true) {
      wynikTail += ` <span class="roll-card__sf">(sukces)</span>`;
    } else if (success === false) {
      wynikTail += ` <span class="roll-card__sf">(porażka)</span>`;
    }
    if (dc != null && (success === true || success === false)) {
      wynikTail += ` \u00b7 DC ${dc} (${window.escapeHtml(dcLabel)})`;
    }
  }

  return (
    `<div class="roll-card roll-card--light ${cardMod}">
      <div class="roll-card__line roll-card__line--head">🎲 Rzut: ${window.escapeHtml(skillLabel)}</div>
      <div class="roll-card__line roll-card__line--detail">
        1d20:&nbsp;&nbsp;<span class="${dieCls}">${rolled}</span>
        &nbsp;&nbsp;|&nbsp;&nbsp; Modyfikator (ranga + biegłość): ${window.escapeHtml(modStr)}
      </div>
      <div class="roll-card__line roll-card__line--wynik">Wynik: <strong>${total}</strong>${wynikTail}</div>
    </div>`
  );
};

// Odświeża etykietę/licznik przycisku "archiwum" oraz klasę na #chat.
window.updateArchiveToggleUi = function () {
  const { chatEl } = window.getEls();
  const btn = document.getElementById('archive-toggle-btn');
  const countEl = document.getElementById('archive-toggle-count');
  const labelEl = btn ? btn.querySelector('.archive-toggle-label') : null;
  if (!chatEl || !btn) return;

  const show = !!(window.state && window.state.showArchiveBubbles);
  chatEl.classList.toggle('archive-hidden', !show);

  const archivedNodes = chatEl.querySelectorAll(
    '.is-archived-bubble, .chat-back-in-game'
  );
  const n = archivedNodes.length;

  btn.setAttribute('aria-pressed', show ? 'true' : 'false');
  btn.setAttribute('data-count', String(n));
  if (countEl) countEl.textContent = String(n);
  if (labelEl) labelEl.textContent = show ? 'Ukryj archiwum' : 'Pokaż archiwum';
};

window.setShowArchiveBubbles = function (show) {
  window.state = window.state || {};
  window.state.showArchiveBubbles = !!show;
  window.updateArchiveToggleUi();
};

window.addMessage = function ({
  speaker,
  text,
  role = 'assistant',
  route = '',
  turn = null,
  createdAt = null,
  memoryTurn = false,
  helpmeTurn = false,
  oocTurn = false
}) {
  const { chatEl } = window.getEls();
  if (!chatEl) return;

  const combatRollPayload =
    text && typeof window.tryParseCombatRollCardFromText === 'function'
      ? window.tryParseCombatRollCardFromText(text)
      : null;
  const rollPayload =
    role === 'user' && text && typeof window.tryParseRollCardFromText === 'function'
      ? window.tryParseRollCardFromText(text)
      : null;
  const effRoute = combatRollPayload || rollPayload ? 'dice' : route;

  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;
  if (
    combatRollPayload &&
    String(combatRollPayload.kind || '') === 'enemy_attack' &&
    role === 'assistant'
  ) {
    wrap.classList.add('enemy-roll-bubble');
  }
  if (memoryTurn) {
    wrap.classList.add('memory-turn');
  }
  if (helpmeTurn) {
    wrap.classList.add('helpme-turn');
  }
  if (oocTurn || helpmeTurn) {
    wrap.classList.add('message-ooc-helpme');
  }
  if (window.isArchiveBubble({ role, route: effRoute, memoryTurn, helpmeTurn })) {
    wrap.classList.add('is-archived-bubble');
    wrap.setAttribute('data-archived', '1');
  }

  const meta = document.createElement('div');
  meta.className = 'meta';

  const left = document.createElement('div');
  left.innerHTML =
    `<strong>${window.escapeHtml(speaker)}</strong>` +
    `${turn ? ` \u2022 ${window.escapeHtml(window.t('chat.turn'))} ${turn}` : ''}`;

  const right = document.createElement('div');
  const parts = [];

  if (effRoute) {
    parts.push(`<span class="route-badge">${window.escapeHtml(effRoute)}</span>`);
  }

  if (createdAt) {
    parts.push(`<span>${window.escapeHtml(window.formatTimestamp(createdAt))}</span>`);
  }

  right.innerHTML = parts.join(' ');

  meta.appendChild(left);
  meta.appendChild(right);

  const body = document.createElement('div');
  body.className = 'message-body';
  if (
    combatRollPayload &&
    typeof window.buildCombatRollCardHtml === 'function' &&
    (role === 'user' || (role === 'assistant' && String(combatRollPayload.kind || '') === 'enemy_attack'))
  ) {
    body.innerHTML = window.buildCombatRollCardHtml(combatRollPayload);
  } else if (rollPayload && typeof window.buildRollCardHtml === 'function') {
    body.innerHTML = window.buildRollCardHtml(rollPayload);
  } else if (
    role === 'user' &&
    text &&
    !rollPayload &&
    !combatRollPayload &&
    /^\s*(\/roll\b|roll\s+\S+\s+d\d+)/i.test(String(text).trim())
  ) {
    body.innerHTML =
      '<div class="roll-card roll-card--light roll-card--neutral roll-card--pending">' +
      '<div class="roll-card__line roll-card__line--detail">🎲 Rzut w toku…</div>' +
      '</div>';
  } else {
    body.innerHTML = `<pre>${window.escapeHtml(text)}</pre>`;
  }

  wrap.appendChild(meta);
  if (oocTurn || helpmeTurn) {
    const lab = document.createElement('div');
    lab.className = 'ooc-helpme-label';
    lab.textContent = '[POMOC — poza fabułą]';
    wrap.appendChild(lab);
  }
  wrap.appendChild(body);
  chatEl.appendChild(wrap);

  window.scrollChatToBottom();
  window.updateArchiveToggleUi?.();
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

  const combatRollPayload =
    text && typeof window.tryParseCombatRollCardFromText === 'function'
      ? window.tryParseCombatRollCardFromText(text)
      : null;
  const rollPayload =
    role === 'user' && text && typeof window.tryParseRollCardFromText === 'function'
      ? window.tryParseRollCardFromText(text)
      : null;
  const effRoute = combatRollPayload || rollPayload ? 'dice' : route;

  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;
  if (
    combatRollPayload &&
    String(combatRollPayload.kind || '') === 'enemy_attack' &&
    role === 'assistant'
  ) {
    wrap.classList.add('enemy-roll-bubble');
  }
  if (window.isArchiveBubble({ role, route: effRoute })) {
    wrap.classList.add('is-archived-bubble');
    wrap.setAttribute('data-archived', '1');
  }

  const meta = document.createElement('div');
  meta.className = 'meta';

  const left = document.createElement('div');
  left.innerHTML =
    `<strong>${window.escapeHtml(speaker)}</strong>` +
    `${turn ? ` \u2022 ${window.escapeHtml(window.t('chat.turn'))} ${turn}` : ''}`;

  const right = document.createElement('div');
  const parts = [];

  if (effRoute) {
    parts.push(`<span class="route-badge">${window.escapeHtml(effRoute)}</span>`);
  }

  if (createdAt) {
    parts.push(`<span>${window.escapeHtml(window.formatTimestamp(createdAt))}</span>`);
  }

  right.innerHTML = parts.join(' ');

  meta.appendChild(left);
  meta.appendChild(right);

  const body = document.createElement('div');
  body.className = 'message-body';
  if (
    combatRollPayload &&
    typeof window.buildCombatRollCardHtml === 'function' &&
    (role === 'user' || (role === 'assistant' && String(combatRollPayload.kind || '') === 'enemy_attack'))
  ) {
    body.innerHTML = window.buildCombatRollCardHtml(combatRollPayload);
  } else if (rollPayload && typeof window.buildRollCardHtml === 'function') {
    body.innerHTML = window.buildRollCardHtml(rollPayload);
  } else {
    body.innerHTML = `<pre>${window.escapeHtml(renderedText)}</pre>`;
  }

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
  window.updateArchiveToggleUi?.();
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
  const expectId = window.state.expectCharacterCreationForCampaignId;
  const shouldForceCharacterModal =
    hasCampaign &&
    !hasCharacter &&
    expectId != null &&
    Number(expectId) === Number(window.state.selectedCampaignId);
  const shouldShowCharacterModal = shouldForceCharacterModal || window.characterModalOpen;

  const llmGate = typeof window.computeLlmGate === 'function' ? window.computeLlmGate() : { ok: true };
  const llmBlocked = !llmGate.ok;
  const campaignCreationBusy = !!window.state._campaignCreationInFlight;
  const characterCreationBusy = !!window.state._characterCreationInFlight;

  if (els.deleteCampaignBtn) els.deleteCampaignBtn.disabled = !hasCampaign;
  if (els.createCampaignBtn) els.createCampaignBtn.disabled = llmBlocked || campaignCreationBusy;
  if (els.campaignCreateSubmitEl) els.campaignCreateSubmitEl.disabled = llmBlocked || campaignCreationBusy;
  if (els.characterCreateSubmitEl) els.characterCreateSubmitEl.disabled = llmBlocked || characterCreationBusy;
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

      if (typeof window.loadCharacterSheet === 'function' && window.state.selectedCharacterId) {
        window.loadCharacterSheet(Number(window.state.selectedCharacterId)).catch(() => {});
      }

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
  window.updateArchiveToggleUi?.();
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

    const ut = turn.user_text || '';
    const rollP =
      typeof window.tryParseRollCardFromText === 'function'
        ? window.tryParseRollCardFromText(ut)
        : null;
    const replayText =
      rollP && rollP.replay_command ? String(rollP.replay_command) : ut;
    const bodyHtml =
      rollP && typeof window.buildRollCardHtml === 'function'
        ? window.buildRollCardHtml(rollP)
        : `<pre>${window.escapeHtml(ut)}</pre>`;

    const body = document.createElement('div');
    body.className = 'message-body';
    body.innerHTML = `
      ${bodyHtml}
      <div style="margin-top:8px;">
        <button type="button" class="secondary replay-turn-btn" data-text="${window.escapeHtml(replayText)}">
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
    const isMemory = turn.route === 'memory';
    const isHelpme = turn.route === 'helpme';
    if (turn.user_text) {
      const cpMsg =
        typeof window.tryParseCombatRollCardFromText === 'function'
          ? window.tryParseCombatRollCardFromText(turn.user_text)
          : null;
      const isEnemyCard = !!(cpMsg && String(cpMsg.kind || '') === 'enemy_attack');
      window.addMessage({
        speaker: isEnemyCard
          ? String(cpMsg.enemy_name || 'Wróg')
          : turn.character_name || 'Gracz',
        text: turn.user_text,
        role: isEnemyCard ? 'assistant' : 'user',
        route: isMemory ? 'memory' : isHelpme ? 'helpme' : isEnemyCard ? 'combat' : 'input',
        turn: turn.turn_number || turn.id,
        createdAt: turn.created_at,
        memoryTurn: isMemory,
        helpmeTurn: isHelpme
      });
    }

    if (turn.assistant_text) {
      if (turn.route === 'memory') {
        window.addMessage({
          speaker: window.t('chat.gm'),
          text: turn.assistant_text,
          role: 'assistant',
          route: 'memory',
          turn: turn.turn_number || turn.id,
          createdAt: turn.created_at,
          memoryTurn: true
        });
      } else if (turn.route === 'helpme') {
        window.addMessage({
          speaker: window.t('chat.gm'),
          text: turn.assistant_text,
          role: 'assistant',
          route: 'helpme',
          turn: turn.turn_number || turn.id,
          createdAt: turn.created_at,
          helpmeTurn: true,
          oocTurn: !!turn.ooc
        });
        window.addBackInGameSeparator();
      } else if (turn.route === 'narrative') {
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
              description: typeof window.getTestDescription === 'function'
                ? window.getTestDescription(canonicalSkill)
                : '',
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
  window.updateArchiveToggleUi?.();
};

window.updateActionTriggerBtn = function (openPopup = false) {
  const hasActiveRoll = !!window.state.activeRollRequest;
  const popup = document.getElementById('action-popup');
  if (!popup) return;

  const hint = document.getElementById('action-popup-roll-hint');
  if (hint) {
    const desc = window.state.activeRollRequest?.description || '';
    hint.textContent = hasActiveRoll && desc ? `Opis: ${desc}` : '';
  }

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

// Obsługa przycisku "Pokaż/Ukryj archiwum" — jednorazowe podpięcie eventów
// i ustawienie widoczności zgodnie ze stanem (domyślnie: ukryte po starcie
// i po odświeżeniu strony).
window.initArchiveToggle = function () {
  const btn = document.getElementById('archive-toggle-btn');
  if (!btn || btn.__wired) return;
  btn.__wired = true;
  btn.addEventListener('click', () => {
    const show = !(window.state && window.state.showArchiveBubbles);
    window.setShowArchiveBubbles(show);
  });
  window.updateArchiveToggleUi();
};
