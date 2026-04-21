window.loadTranslations = async function (lang) {
  const resp = await fetch(`/i18n/${lang}.json`);
  if (!resp.ok) throw new Error(`Translation load failed: ${resp.status}`);
  window.state.translations = await resp.json();
  window.state.lang = lang;
  window.applyTranslations();
};

window.loadHealth = async function (userId = null) {
  const {
    statusBackendDotEl,
    statusOllamaDotEl,
    statusLokiDotEl
  } = window.getEls();

  const setDotState = (dotEl, state, title) => {
    if (!dotEl) return;
    dotEl.classList.remove('ok', 'warn', 'error', 'unknown');
    dotEl.classList.add(state);
    if (title) dotEl.title = title;
  };

  const prevBackendOk = window.__backendHealthOk;

  try {
    const url = userId ? `${window.API_HEALTH}?user_id=${encodeURIComponent(String(userId))}` : window.API_HEALTH;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    setDotState(statusBackendDotEl, 'ok', 'Backend: OK');
    setDotState(
      statusOllamaDotEl,
      data.llm?.reachable ? 'ok' : 'warn',
      `LLM: ${data.llm?.reachable ? 'OK' : window.t('status.disconnected')}`
    );

    const loki = data.loki;
    if (!loki || loki.configured === false) {
      setDotState(
        statusLokiDotEl,
        'unknown',
        'Loki: ' + (window.t ? window.t('status.loki_na') : 'not configured (set LOKI_URL on backend)')
      );
    } else if (loki.reachable) {
      setDotState(statusLokiDotEl, 'ok', 'Loki: OK');
    } else {
      let detail = loki.error ? String(loki.error) : window.t ? window.t('status.disconnected') : 'unreachable';
      if (!loki.error && loki.http_status != null) {
        detail = `HTTP ${loki.http_status}`;
      }
      setDotState(statusLokiDotEl, 'warn', `Loki: ${detail}`);
    }

    window.__backendHealthOk = true;

    // After Docker / backend restart the UI still shows old chat; reload turns when health recovers.
    if (prevBackendOk === false && typeof window.loadTurns === 'function') {
      const cid = window.state?.selectedCampaignId;
      if (cid) {
        try {
          await window.loadTurns(cid);
        } catch (_err) {
          /* keep green dot; next poll can retry */
        }
      }
    }
  } catch (e) {
    window.__backendHealthOk = false;
    setDotState(statusBackendDotEl, 'error', `Backend: ${window.t('health.fail')}`);
    setDotState(statusOllamaDotEl, 'error', `Ollama: ${window.t('status.disconnected')}`);
    setDotState(
      statusLokiDotEl,
      'unknown',
      'Loki: ' + (window.t ? window.t('status.loki_unknown') : 'unknown (backend unreachable)')
    );
  }
};

window.loadModels = async function (userId = null) {
  const { engineSelectEl } = window.getEls();
  const provider = String(window.state.llmSettings?.provider || '').toLowerCase();
  const wantAll = provider === 'openai' && !!window.state.showAllProviderModels;

  let modelsUrl = wantAll ? `${window.API_MODELS}?show_all=1` : window.API_MODELS;
  if (userId) {
    modelsUrl += wantAll ? `&user_id=${encodeURIComponent(String(userId))}` : `?user_id=${encodeURIComponent(String(userId))}`;
  }

  const resp = await fetch(modelsUrl);
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const data = await resp.json();
      detail = data.detail || detail;
    } catch (_err) {}
    throw new Error(window.prettyLlmErrorMessage(detail));
  }

  const data = await resp.json();

  window.state.models = Array.isArray(data.models)
    ? data.models
    : Array.isArray(data)
      ? data
      : [];

  engineSelectEl.innerHTML = '';

  if (window.state.models.length === 0) {
    const fallbackOption = document.createElement('option');
    fallbackOption.value = 'gemma4:e4b';
    fallbackOption.textContent = 'gemma4:e4b';
    engineSelectEl.appendChild(fallbackOption);
    engineSelectEl.value = 'gemma4:e4b';
    window.state.selectedEngine = 'gemma4:e4b';
    return;
  }

  window.state.models.forEach(model => {
    const name = typeof model === 'string' ? model : model.name;
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    engineSelectEl.appendChild(option);
  });

  const preferredFromRuntime = (window.state.llmSettings && window.state.llmSettings.model) || '';
  const preferredEngine =
    window.state.selectedEngine ||
    preferredFromRuntime ||
    window.state.models[0].name ||
    window.state.models[0];

  const exists = window.state.models.some(model => {
    const name = typeof model === 'string' ? model : model.name;
    return name === preferredEngine;
  });

  window.state.selectedEngine = exists
    ? preferredEngine
    : (typeof window.state.models[0] === 'string'
        ? window.state.models[0]
        : window.state.models[0].name);

  engineSelectEl.value = window.state.selectedEngine;
};

window.loadCampaigns = async function (preferredCampaignId = null) {
  const { campaignSelectEl } = window.getEls();
  const uid = window.state?.playerUserId || null;

const resp = await fetch(window.API_CAMPAIGNS);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

  const data = await resp.json();
  const rawCampaigns = Array.isArray(data.campaigns) ? data.campaigns : [];
  const visibleCampaigns = uid
    ? rawCampaigns.filter((c) => Number(c.owner_user_id ?? c.owneruserid) === Number(uid))
    : rawCampaigns;

  window.state.campaigns = visibleCampaigns.map(c => ({
    ...c,
    systemid: c.systemid ?? c.system_id,
    modelid: c.modelid ?? c.model_id,
    owneruserid: c.owneruserid ?? c.owner_user_id,
    createdat: c.createdat ?? c.created_at,
    character_count: Number(c.character_count ?? 0)
  }));

  campaignSelectEl.innerHTML = '';

  if (window.state.campaigns.length === 0) {
    campaignSelectEl.innerHTML = '<option value="" disabled selected>Brak kampanii</option>';
    campaignSelectEl.disabled = true;

    window.state.expectCharacterCreationForCampaignId = null;
    window.state.selectedCampaignId = null;
    window.state.characters = [];
    window.state.selectedCharacterId = null;
    localStorage.removeItem('ai-gm:selectedCharacterId');

    window.updateUiState();
    return;
  }

  campaignSelectEl.disabled = false;

  const campaignPlayable = (c) => {
    const st = String(c.status || '').toLowerCase();
    const n = Number(c.character_count ?? 0);
    return st === 'ended' || n >= 1;
  };

  window.state.campaigns.forEach(campaign => {
    const option = document.createElement('option');
    option.value = String(campaign.id);
    const broken = !campaignPlayable(campaign);
    option.textContent = broken ? `${campaign.title} (brak bohatera)` : campaign.title;
    campaignSelectEl.appendChild(option);
  });

  const savedCampaignId = Number(localStorage.getItem('ai-gm:selectedCampaignId'));
  const prefOk =
    preferredCampaignId &&
    window.state.campaigns.some((c) => Number(c.id) === Number(preferredCampaignId));
  const savedOk =
    savedCampaignId &&
    window.state.campaigns.some((c) => Number(c.id) === Number(savedCampaignId));

  let selectedId = null;
  if (prefOk) {
    selectedId = Number(preferredCampaignId);
  } else if (savedOk && campaignPlayable(window.state.campaigns.find((c) => Number(c.id) === Number(savedCampaignId)))) {
    selectedId = Number(savedCampaignId);
  } else {
    const firstPlayable = window.state.campaigns.find((c) => campaignPlayable(c));
    selectedId = firstPlayable
      ? Number(firstPlayable.id)
      : Number(window.state.campaigns[0].id);
  }

  window.state.selectedCampaignId = selectedId;
  campaignSelectEl.value = String(selectedId);

  window.updateUiState();
};


window.loadCharacters = async function (campaignId, preferredCharacterId = null) {
  if (!campaignId) {
    window.state.characters = [];
    window.state.selectedCharacterId = null;
    localStorage.removeItem('ai-gm:selectedCharacterId');
    window.updateUiState();
    return;
  }

  const resp = await fetch(`/api/campaigns/${campaignId}/characters`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

  const data = await resp.json();
  const uid = window.state?.playerUserId || null;
  const rawChars = Array.isArray(data.characters) ? data.characters : [];
  window.state.characters = uid
    ? rawChars.filter((ch) => Number(ch.user_id ?? ch.userid) === Number(uid))
    : rawChars;

  if (window.state.characters.length === 0) {
    window.state.selectedCharacterId = null;
    localStorage.removeItem('ai-gm:selectedCharacterId');
    window.updateUiState();
    return;
  }

  if (
    window.state.expectCharacterCreationForCampaignId != null &&
    Number(window.state.expectCharacterCreationForCampaignId) === Number(campaignId)
  ) {
    window.state.expectCharacterCreationForCampaignId = null;
  }

  const savedCharacterId = Number(localStorage.getItem('ai-gm:selectedCharacterId'));
  const candidateId = preferredCharacterId || savedCharacterId;

  const selectedId = candidateId && window.state.characters.some(
    c => Number(c.id) === Number(candidateId)
  )
    ? Number(candidateId)
    : Number(window.state.characters[0].id);

  window.state.selectedCharacterId = selectedId;
  localStorage.setItem('ai-gm:selectedCharacterId', String(selectedId));

  window.updateUiState();
};

/**
 * Scal tury z serwera z lokalnymi wpisami walki (np. karta rzutu wroga), posortuj po turze i czasie.
 */
window.mergeTurnsForChat = function () {
  const s = Array.isArray(window.state.serverTurns) ? [...window.state.serverTurns] : [];
  const logt = Array.isArray(window.state.combatLogTurns) ? [...window.state.combatLogTurns] : [];
  const c = Array.isArray(window.state.combatClientTurns)
    ? [...window.state.combatClientTurns]
    : [];
  const merged = s.concat(logt).concat(c);
  merged.sort((a, b) => {
    const ta = Date.parse(String(a.created_at || '')) || 0;
    const tb = Date.parse(String(b.created_at || '')) || 0;
    if (ta !== tb) return ta - tb;
    const na = Number(a.turn_number || 0);
    const nb = Number(b.turn_number || 0);
    if (na !== nb) return na - nb;
    return String(a.id || '').localeCompare(String(b.id || ''));
  });
  return merged;
};

/**
 * Mapuje wiersze `combat_turns` (atak wroga) na syntetyczne tury czatu z kartą rzutu.
 */
window.buildCombatLogChatTurnsFromRows = function (rows) {
  const p = window.COMBAT_ROLL_PREFIX || '__AI_GM_COMBAT_ROLL_V1__';
  const out = [];
  if (!Array.isArray(rows)) return out;
  for (const row of rows) {
    if (String(row.actor) !== 'enemy' || String(row.event_type) !== 'attack') continue;
    let meta = {};
    try {
      meta =
        typeof row.narrative === 'string' && row.narrative.trim()
          ? JSON.parse(row.narrative)
          : {};
    } catch (_e) {
      meta = {};
    }
    const enemyName = String(meta.enemy_name || 'Wróg');
    const raw = Number(meta.raw_d20);
    const atkRoll = Number(row.roll_value);
    const bonus =
      Number.isFinite(raw) && Number.isFinite(atkRoll) ? atkRoll - raw : null;
    const mods = [];
    if (bonus != null && Number.isFinite(bonus)) {
      mods.push({ name: 'Bonus do trafienia', value: bonus });
    }
    const pac = meta.target_ac != null ? Number(meta.target_ac) : null;
    const hit = row.hit === 1;
    const dmg = row.damage != null ? Number(row.damage) : null;
    const summary = hit
      ? `Atak wroga: wynik ${atkRoll} — trafienie za ${dmg != null ? dmg : '?'} HP`
      : `Atak wroga: wynik ${atkRoll} — pudło.`;
    const enemyPayload = {
      kind: 'enemy_attack',
      intent: '',
      summary_line: summary,
      enemy_name: enemyName,
      attack_label: 'ATAK (wróg)',
      d20: Number.isFinite(raw) ? raw : atkRoll,
      modifiers: mods,
      total: Number.isFinite(atkRoll) ? atkRoll : raw,
      hit,
      damage: dmg != null ? dmg : 0,
      target_ac: pac != null && Number.isFinite(pac) ? pac : null,
    };
    out.push({
      id: `combatlog-${row.id}`,
      user_text: `${p}\n${JSON.stringify(enemyPayload)}`,
      assistant_text: null,
      character_name: enemyName,
      character_user_id: null,
      route: 'narrative',
      turn_number: Number(row.turn_number),
      created_at: row.created_at,
      _fromCombatLog: true,
    });
  }
  return out;
};

window.loadCombatLogTurns = async function (campaignId) {
  if (!campaignId) {
    window.state.combatLogTurns = [];
    return [];
  }
  try {
    const res = await fetch(`/api/campaigns/${campaignId}/combat/turns`, {
      headers: window.getApiHeaders ? window.getApiHeaders() : {},
    });
    if (!res.ok) {
      window.state.combatLogTurns = [];
      return [];
    }
    const data = await res.json();
    const rows = Array.isArray(data.turns) ? data.turns : [];
    window.state.combatLogTurns =
      typeof window.buildCombatLogChatTurnsFromRows === 'function'
        ? window.buildCombatLogChatTurnsFromRows(rows)
        : [];
    return window.state.combatLogTurns;
  } catch (_e) {
    window.state.combatLogTurns = [];
    return [];
  }
};

window.refreshCombatLogTurns = async function (campaignId) {
  await window.loadCombatLogTurns(campaignId);
  window.state.combatClientTurns = [];
  if (typeof window.mergeTurnsForChat === 'function') {
    window.state.turns = window.mergeTurnsForChat();
  }
  if (typeof window.renderTurnsToChat === 'function') {
    window.renderTurnsToChat();
  }
};

window.loadTurns = async function (campaignId, limit = 30, userId = null) {
  if (!campaignId) {
    window.state.serverTurns = [];
    window.state.combatClientTurns = [];
    window.state.combatLogTurns = [];
    window.state.turns = [];
    window.clearChat();
    window.clearHistoryPanel();
    return;
  }

  const uid = userId || window.state?.playerUserId || null;

  const resp = await fetch(`/api/campaigns/${campaignId}/turns?limit=${limit}`);
  if (resp.status === 410) {
    window.state.serverTurns = [];
    window.state.combatClientTurns = [];
    window.state.combatLogTurns = [];
    window.state.turns = [];
    if (typeof window.showCampaignDeathScreen === 'function') {
      await window.showCampaignDeathScreen(campaignId);
    }
    window.clearChat?.();
    window.renderHistoryPanel?.();
    return;
  }
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

  if (typeof window.dismissCampaignDeathScreen === 'function') {
    window.dismissCampaignDeathScreen();
  }

  const data = await resp.json();
  const turns = Array.isArray(data.turns) ? data.turns : [];
  const serverList = uid
    ? turns.filter((t) => {
        const cuid = t?.character_user_id ?? null;
        // Keep command/system turns even if character_user_id is missing.
        if (!cuid) return true;
        return Number(cuid) === Number(uid);
      })
    : turns;

  window.state.serverTurns = serverList;
  window.state.combatClientTurns = [];
  if (typeof window.loadCombatLogTurns === 'function') {
    await window.loadCombatLogTurns(campaignId);
  }
  window.state.turns = window.mergeTurnsForChat();

  if (window.state.serverTurns.length > 0) {
    const lastTurn = window.state.serverTurns[window.state.serverTurns.length - 1];
    window.state.turnNumber = Number(lastTurn.turn_number || lastTurn.id || 0);
  } else {
    window.state.turnNumber = 0;
  }

  window.renderTurnsToChat();
  window.renderHistoryPanel();

  try {
    const cr = await fetch(`/api/campaigns/${campaignId}/combat`, {
      headers: window.getApiHeaders ? window.getApiHeaders() : {}
    });
    if (!cr.ok) {
      if (typeof window.updateCombatDebugStatusLabel === 'function') {
        const el = document.getElementById('combat-debug-status');
        if (el) el.textContent = 'COMBAT: GET failed HTTP ' + cr.status;
      }
      if (typeof window.combatInput?.syncWithCombat === 'function') {
        window.combatInput.syncWithCombat(null);
      }
    } else {
      const cd = await cr.json().catch(() => ({}));
      if (typeof window.updateCombatDebugStatusLabel === 'function') {
        window.updateCombatDebugStatusLabel(cd);
      }
      const cs = cd.combat;
      const hasActiveCombat = cd.active === true && cs != null;

      const clearCombatUi = () => {
        window.state.combatClientTurns = [];
        window.state.combatLogTurns = [];
        window.state.turns = window.mergeTurnsForChat();
        if (typeof window.renderTurnsToChat === 'function') {
          window.renderTurnsToChat();
        }
        if (typeof window.combatPanel?.hide === 'function') {
          window.combatPanel.hide();
        }
        if (typeof window.combatInput?.syncWithCombat === 'function') {
          window.combatInput.syncWithCombat(null);
        }
      };

      if (!hasActiveCombat) {
        clearCombatUi();
      } else if (cs.status === 'ended') {
        if (typeof window.combatPanel?.hide === 'function') {
          window.combatPanel.hide();
        }
        if (typeof window.combatInput?.syncWithCombat === 'function') {
          window.combatInput.syncWithCombat(null);
        }
        window.state.combatClientTurns = [];
        if (typeof window.loadCombatLogTurns === 'function') {
          await window.loadCombatLogTurns(campaignId);
        }
        window.state.turns = window.mergeTurnsForChat();
        if (typeof window.renderTurnsToChat === 'function') {
          window.renderTurnsToChat();
        }
        if (typeof window.addMessage === 'function') {
          window.addMessage({
            speaker: 'System',
            text: 'Walka zakończona!',
            role: 'system'
          });
        }
      } else {
        if (typeof window.combatPanel?.render === 'function') {
          window.combatPanel.render(cs);
        }
        if (typeof window.combatInput?.syncWithCombat === 'function') {
          window.combatInput.syncWithCombat(cs);
        }
        if (cs.status === 'active' && typeof window.combatPanel?.show === 'function') {
          window.combatPanel.show();
        }
      }
    }
  } catch (_e) {
    /* ignore */
  }

  if (typeof window.afterTurnsLoaded === 'function') {
    try {
      await window.afterTurnsLoaded(campaignId);
    } catch (_err) {
      /* optional combat / hooks */
    }
  }
};

window.getApiHeaders = function () {
  return {
    'Content-Type': 'application/json'
  };
};