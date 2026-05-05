window.state = window.state || {};
window.state.characterSheet = window.state.characterSheet || null;
window.state.sheetPanelOpen = window.state.sheetPanelOpen ?? false;
/** `null` = unknown (legacy session without flag): keep LLM controls visible. `false` = non-admin. */
window.state.playerIsAdmin = window.state.playerIsAdmin ?? null;
window.API_BASE_URL = window.API_BASE_URL || "/api";
window.SHEET_PANEL_STORAGE_KEY = "ai-gm:sheetPanelOpen";

window.SHEET_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"];
window.state.lastApiCall = window.state.lastApiCall || null;
window.state.llmSettings = window.state.llmSettings || null;
window.state.showAllProviderModels = window.state.showAllProviderModels ?? false;

window.LLM_SETTINGS_COLLAPSE_PREF_KEY = "ai-gm:llmSettingsCollapsedPref";

/** Phase 8E-2 — server defaults for sheet fold (from GET /api/settings/ui). */
window._uiPanelDefaults = window._uiPanelDefaults || null;

window.loadUiPanelDefaults = async function () {
  try {
    const base = (window.API_BASE_URL || "/api").replace(/\/+$/, "");
    const r = await fetch(`${base}/settings/ui`);
    if (!r.ok) return;
    const data = await r.json();
    if (data && data.ok && data.data && data.data.panels && typeof data.data.panels === "object") {
      window._uiPanelDefaults = data.data.panels;
    }
  } catch (_e) {
    /* applyFoldState uses mobile / expanded fallback */
  }
};

window.applyFoldState = function () {
  const sections = ["stats", "skills", "inventory", "identity"];
  const isMobile = typeof window.innerWidth === "number" && window.innerWidth < 768;

  sections.forEach((section) => {
    const el = document.querySelector(`[data-section="${section}"]`);
    if (!el) return;

    const stored = localStorage.getItem(`ui_fold_${section}`);
    let state;
    if (stored) {
      state = stored;
    } else if (window._uiPanelDefaults && typeof window._uiPanelDefaults === "object") {
      state = window._uiPanelDefaults[section] || "expanded";
    } else if (isMobile && section !== "stats") {
      state = "collapsed";
    } else {
      state = "expanded";
    }

    const collapsed = state === "collapsed";
    el.classList.toggle("fold-collapsed", collapsed);
    const icon = el.querySelector(".fold-icon");
    if (icon) icon.textContent = collapsed ? "\u25b8" : "\u25be";
  });
};

(function initSheetFoldClickDelegation() {
  if (window.__sheetFoldClickDelegationWired) return;
  window.__sheetFoldClickDelegationWired = true;
  document.addEventListener("click", (e) => {
    const toggle = e.target.closest("[data-fold-toggle]");
    if (!toggle) return;
    const section = toggle.getAttribute("data-fold-toggle");
    if (!section) return;
    const wrapper = document.querySelector(`[data-section="${section}"]`);
    if (!wrapper) return;
    const isCollapsed = wrapper.classList.toggle("fold-collapsed");
    const icon = wrapper.querySelector(".fold-icon");
    if (icon) icon.textContent = isCollapsed ? "\u25b8" : "\u25be";
    localStorage.setItem(`ui_fold_${section}`, isCollapsed ? "collapsed" : "expanded");
  });
})();

window.playerMayEditLlmConnectionUi = function () {
  if (window.state.playerIsAdmin === false) return false;
  return true;
};

window.applyPlayerLlmSettingsAccessUi = function () {
  const wrap = document.getElementById("llm-player-admin-only");
  if (!wrap) return;
  const show = window.playerMayEditLlmConnectionUi();
  wrap.hidden = !show;
  wrap.style.display = show ? "" : "none";
  wrap.setAttribute("aria-hidden", show ? "false" : "true");
};

window.state.mechanicMetadata = window.state.mechanicMetadata || null;

window.getTestDescription = function (canonicalKey) {
  const meta = window.state?.mechanicMetadata;
  const map = meta?.test_descriptions || {};
  const key = String(canonicalKey || "").trim();
  return map[key] || "";
};

window.loadMechanicMetadata = async function () {
  try {
    const resp = await fetch('/api/mechanics/metadata');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    window.state.mechanicMetadata = data || null;
    try {
      const mod = await import("./slash_commands.js");
      if (typeof mod.loadSlashCommandCatalog === "function") {
        await mod.loadSlashCommandCatalog();
      }
    } catch (_e) {
      /* module optional */
    }
    return window.state.mechanicMetadata;
  } catch (_err) {
    // Keep metadata optional — game can still function without descriptions.
    window.state.mechanicMetadata = window.state.mechanicMetadata || { test_descriptions: {} };
    return window.state.mechanicMetadata;
  }
};

/** LLM provider/model/API key: backend (`GET/POST /api/settings/llm`, per-user PUT) is source of truth — not localStorage (iframes may block it). */
window.persistLlmSettingsToStorage = function (_settings) {};

window.restoreLlmSettingsFromStorage = function () {
  return null;
};

window.setLlmControlsCollapsed = function (collapsed) {
  const llmControlsEl = document.getElementById("llm-controls");
  if (!llmControlsEl) return;
  llmControlsEl.classList.toggle("llm-controls--collapsed", !!collapsed);

  const hintEl = document.getElementById("llm-settings-toggle-hint");
  if (!hintEl) return;
  const settings = window.state?.llmSettings;
  const provider = String(settings?.provider || "").toLowerCase() || "unknown";
  const apiKeySet = !!settings?.api_key_set;
  const connected = provider === "ollama" || apiKeySet;
  hintEl.textContent = connected ? "Saved" : "Connect";
};

window.getLlmControlsCollapsedPref = function () {
  const raw = localStorage.getItem(window.LLM_SETTINGS_COLLAPSE_PREF_KEY);
  if (raw === "1") return true;
  if (raw === "0") return false;
  return null;
};

window.computeDefaultLlmControlsCollapsed = function () {
  // Default UX: hide the panel to maximize chat space.
  // Users can always expand via the toggle.
  return true;
};

window.initLlmSettingsCollapse = function () {
  const toggleBtn = document.getElementById("llm-settings-toggle-btn");
  if (!toggleBtn) return;

  const pref = window.getLlmControlsCollapsedPref();
  const collapsed = pref !== null ? pref : window.computeDefaultLlmControlsCollapsed();
  window.setLlmControlsCollapsed(collapsed);

  toggleBtn.addEventListener("click", () => {
    const llmControlsEl = document.getElementById("llm-controls");
    const isCollapsed = !!llmControlsEl?.classList?.contains("llm-controls--collapsed");
    const next = !isCollapsed;
    localStorage.setItem(window.LLM_SETTINGS_COLLAPSE_PREF_KEY, next ? "1" : "0");
    window.setLlmControlsCollapsed(next);
  });
};

/** Gdy włączone: nie pokazuj mechanic walki w głównym czacie (panel Walki bez zmian). */
window.HIDE_COMBAT_CHAT_BUBBLES_KEY = "ai-gm:hideCombatChatBubbles";

window.isCombatChatBubbleHidden = function () {
  try {
    return localStorage.getItem(window.HIDE_COMBAT_CHAT_BUBBLES_KEY) === "1";
  } catch (_e) {
    return false;
  }
};

window.initCombatChatBubblePref = function () {
  const el = document.getElementById("hide-combat-chat-bubbles-toggle");
  if (!el) return;
  el.checked = window.isCombatChatBubbleHidden();
  el.addEventListener("change", () => {
    try {
      localStorage.setItem(
        window.HIDE_COMBAT_CHAT_BUBBLES_KEY,
        el.checked ? "1" : "0"
      );
    } catch (_e) {}
    if (typeof window.renderTurnsToChat === "function" && window.state?.selectedCampaignId) {
      try {
        window.renderTurnsToChat();
      } catch (err) {
        console.warn("renderTurnsToChat after combat chat pref failed:", err);
      }
    }
  });
};

/** Preferencje automatycznego TTS wg „rodzaju” dymku (localStorage). */
window.TTS_PREF_KEYS = {
  narrative: "ai-gm:tts:narrative",
  memory: "ai-gm:tts:memory",
  helpme: "ai-gm:tts:helpme",
  dice: "ai-gm:tts:dice",
  combat: "ai-gm:tts:combat",
};

window.getTtsBubblePrefs = function () {
  function read(key, defaultBool) {
    try {
      const v = localStorage.getItem(key);
      if (v === null) return defaultBool;
      return v === "1";
    } catch (_e) {
      return defaultBool;
    }
  }
  const k = window.TTS_PREF_KEYS;
  return {
    narrative: read(k.narrative, true),
    memory: read(k.memory, false),
    helpme: read(k.helpme, false),
    dice: read(k.dice, false),
    combat: read(k.combat, false),
  };
};

/**
 * Czy automatycznie czytać ten dymek przez TTS (addMessage + strumień narracji).
 * Domyślnie tylko narracja fabularna; /mem, helpme, dice, combat wyłączone.
 */
window.shouldAutoSpeakTtsForBubble = function (msg) {
  const role = String(msg?.role || "").toLowerCase();
  if (role !== "assistant" && role !== "gm") return false;
  const routeRaw = String(msg?.route || "").toLowerCase();
  const memoryTurn = !!msg?.memoryTurn;
  const helpmeTurn = !!msg?.helpmeTurn;
  const prefs = window.getTtsBubblePrefs?.() || {};

  if (memoryTurn) return !!prefs.memory;
  if (helpmeTurn) return !!prefs.helpme;

  if (
    routeRaw === "command" ||
    routeRaw === "unknown" ||
    routeRaw === "system" ||
    routeRaw === "error"
  ) {
    return false;
  }

  if (!routeRaw || routeRaw === "narrative") return prefs.narrative !== false;
  if (routeRaw === "memory") return !!prefs.memory;
  if (routeRaw === "helpme") return !!prefs.helpme;
  if (routeRaw === "dice") return !!prefs.dice;
  if (routeRaw === "combat") return !!prefs.combat;
  return false;
};

window.syncLlmControlsCollapseToCurrentState = function () {
  const pref = window.getLlmControlsCollapsedPref();
  if (pref !== null) {
    window.setLlmControlsCollapsed(pref);
    return;
  }
  const collapsed = window.computeDefaultLlmControlsCollapsed();
  window.setLlmControlsCollapsed(collapsed);
};

window.prettyLlmErrorMessage = function (rawMessage) {
  const msg = String(rawMessage || '').trim();
  const lower = msg.toLowerCase();
  if (!msg) return 'Unknown LLM error.';
  if (lower.includes('invalid_api_key') || lower.includes('invalid api key')) {
    return 'LLM auth failed: invalid API key. Paste the token without "Bearer".';
  }
  if (lower.includes('connection refused') || lower.includes('connecterror')) {
    return 'LLM connection failed: provider host refused connection. Check URL/port.';
  }
  if (lower.includes('timeout')) {
    return 'LLM request timed out. Try again or use a smaller/faster model.';
  }
  if (lower.includes('unknown llm provider')) {
    return 'LLM provider config is invalid. Reconnect with a supported provider.';
  }
  if (lower.startsWith('{') && lower.includes('"error"')) {
    return `LLM provider error: ${msg}`;
  }
  return `LLM error: ${msg}`;
};

window.normalizeLlmBaseUrlInput = function (rawBaseUrl, provider) {
  let value = String(rawBaseUrl || '').trim().replace(/\/+$/, '');
  const lower = value.toLowerCase();
  if (provider === 'openai') {
    if (lower.endsWith('/v1/chat/completions')) {
      value = value.slice(0, -'/v1/chat/completions'.length);
    } else if (lower.endsWith('/chat/completions')) {
      value = value.slice(0, -'/chat/completions'.length);
    } else if (lower.endsWith('/v1/models')) {
      value = value.slice(0, -'/v1/models'.length);
    } else if (lower.endsWith('/v1')) {
      value = value.slice(0, -'/v1'.length);
    }
  } else if (provider === 'ollama') {
    if (lower.endsWith('/api/chat')) {
      value = value.slice(0, -'/api/chat'.length);
    } else if (lower.endsWith('/api/tags')) {
      value = value.slice(0, -'/api/tags'.length);
    } else if (lower.endsWith('/api')) {
      value = value.slice(0, -'/api'.length);
    }
  }
  return value.replace(/\/+$/, '');
};

window.getLlmProviderPayloadFromForm = function () {
  const { llmProviderSelectEl, llmBaseUrlInputEl, llmApiKeyInputEl, engineSelectEl } = window.getEls();
  const selected = (llmProviderSelectEl?.value || 'ollama-local').trim();
  const campaign = typeof window.currentCampaign === 'function' ? window.currentCampaign() : null;
  const campaignModel =
    String(campaign?.model_id || campaign?.modelid || '').trim();
  const model =
    String(window.state.selectedEngine || '').trim() ||
    String(engineSelectEl?.value || '').trim() ||
    campaignModel;

  if (selected === 'ollama-local') {
    return {
      provider: 'ollama',
      base_url: 'http://localhost:11434',
      model,
      api_key: '',
    };
  }
  if (selected === 'ollama-remote') {
    const base = window.normalizeLlmBaseUrlInput((llmBaseUrlInputEl?.value || '').trim(), 'ollama');
    return {
      provider: 'ollama',
      base_url: base || 'http://host:11434',
      model,
      api_key: (llmApiKeyInputEl?.value || '').trim(),
    };
  }
  const openaiBase = window.normalizeLlmBaseUrlInput((llmBaseUrlInputEl?.value || '').trim(), 'openai');
  return {
    provider: 'openai',
    base_url: openaiBase || 'https://api.llmapi.ai',
    model,
    api_key: (llmApiKeyInputEl?.value || '').trim(),
  };
};

window.updateLlmProviderFormVisibility = function () {
  const {
    llmProviderSelectEl,
    llmBaseUrlInputEl,
    llmApiKeyInputEl,
    llmBaseUrlFieldEl,
    llmApiKeyFieldEl,
    openaiModelsToggleWrapEl,
  } = window.getEls();
  if (!llmProviderSelectEl || !llmBaseUrlInputEl || !llmApiKeyInputEl) return;
  const selected = llmProviderSelectEl.value;
  const hideExtra = selected === 'ollama-local';
  if (llmBaseUrlFieldEl) llmBaseUrlFieldEl.style.display = hideExtra ? 'none' : 'flex';
  if (llmApiKeyFieldEl) llmApiKeyFieldEl.style.display = hideExtra ? 'none' : 'flex';
  if (openaiModelsToggleWrapEl) {
    openaiModelsToggleWrapEl.style.display = selected === 'openai' ? 'block' : 'none';
  }
  if (selected === 'ollama-remote') {
    llmBaseUrlInputEl.placeholder = 'http://host:port';
    llmApiKeyInputEl.placeholder = 'API key (optional)';
  } else if (selected === 'openai') {
    llmBaseUrlInputEl.placeholder = 'https://api.llmapi.ai';
    llmApiKeyInputEl.placeholder = 'Bearer token';
  }
};

window.applyLlmSettingsToForm = function (settings) {
  const { llmProviderSelectEl, llmBaseUrlInputEl, llmApiKeyInputEl, engineSelectEl } = window.getEls();
  if (!settings) return;
  const provider = (settings.provider || 'ollama').toLowerCase();
  const baseUrl = settings.base_url || '';
  const campaign = typeof window.currentCampaign === 'function' ? window.currentCampaign() : null;
  const campaignModel =
    String(campaign?.model_id || campaign?.modelid || '').trim();
  const preferredModel =
    campaignModel ||
    String(window.state.selectedEngine || '').trim() ||
    String(settings.model || '').trim();
  if (llmProviderSelectEl) {
    if (provider === 'openai') {
      llmProviderSelectEl.value = 'openai';
    } else if (baseUrl && baseUrl !== 'http://localhost:11434') {
      llmProviderSelectEl.value = 'ollama-remote';
    } else {
      llmProviderSelectEl.value = 'ollama-local';
    }
  }
  if (llmBaseUrlInputEl) llmBaseUrlInputEl.value = baseUrl || 'http://localhost:11434';
  if (llmApiKeyInputEl) llmApiKeyInputEl.value = '';
  if (preferredModel) {
    window.state.selectedEngine = preferredModel;
    if (engineSelectEl) {
      engineSelectEl.value = preferredModel;
    }
  }
  window.updateLlmProviderFormVisibility();
  if (llmApiKeyInputEl) {
    const masked = String(settings.api_key || '').trim();
    const keySet = !!settings.api_key_set;
    if (keySet && masked) {
      llmApiKeyInputEl.placeholder = masked;
    } else if (keySet) {
      llmApiKeyInputEl.placeholder = 'Klucz API zapisany (wklej nowy, aby zamienić)';
    }
  }
};

window.computeLlmGate = function () {
  const s = window.state.llmSettings;
  const { llmProviderSelectEl, llmApiKeyInputEl, engineSelectEl } = window.getEls();
  const providerUi = (llmProviderSelectEl?.value || 'ollama-local').toLowerCase();
  const model =
    String(s?.model || '').trim() ||
    String(window.state.selectedEngine || '').trim() ||
    String(engineSelectEl?.value || '').trim();

  const keyInForm = (llmApiKeyInputEl?.value || '').trim();
  const hasStoredKey = !!s?.api_key_set;

  if (!model) {
    return {
      ok: false,
      reason: 'Wybierz model LLM w panelu połączenia i zapisz (Connect).',
    };
  }

  if (providerUi === 'ollama-local') {
    return { ok: true };
  }

  if (!hasStoredKey && !keyInForm) {
    return {
      ok: false,
      reason:
        'Dla OpenAI / zdalnego Ollama potrzebny jest klucz API: wklej go w ustawieniach LLM i zapisz (Connect).',
    };
  }
  return { ok: true };
};

window.connectLlmSettings = async function () {
  if (typeof window.playerMayEditLlmConnectionUi === "function" && !window.playerMayEditLlmConnectionUi()) {
    throw new Error("Brak uprawnień do zmiany ustawień LLM.");
  }
  const userId = window.state?.playerUserId || 1;
  const raw = window.getLlmProviderPayloadFromForm();
  const keyTrim = String(raw.api_key || '').trim();
  const preserveKey = !keyTrim && !!(window.state.llmSettings && window.state.llmSettings.api_key_set);
  const payload = {
    provider: raw.provider,
    base_url: raw.base_url,
    model: raw.model,
    api_key: preserveKey ? null : keyTrim || '',
  };
  const resp = await fetch('/api/settings/llm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  const data = await resp.json();
  let newSettings = data?.settings || null;

  // Persist per-user settings (including api_key) so that refresh/another device works.
  try {
    const userResp = await fetch(`/api/users/${userId}/llm-settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (userResp.ok) {
      const userData = await userResp.json();
      newSettings = userData?.settings || newSettings;
    }
  } catch (_err) {
    // Keep runtime settings in memory.
  }

  window.state.llmSettings = newSettings;
  window.state.selectedEngine = payload.model;
  window.syncLlmControlsCollapseToCurrentState();
  try {
    await window.loadUserLlmSettings(userId);
  } catch (_e) {
    /* runtime settings already applied */
  }
  if (typeof window.updateUiState === 'function') window.updateUiState();
  return data;
};

window.loadLlmSettings = async function () {
  const resp = await fetch('/api/settings/llm');
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  const settings = await resp.json();
  window.state.llmSettings = settings;
  window.applyLlmSettingsToForm(settings);
  if (typeof window.updateUiState === 'function') window.updateUiState();
  return settings;
};

window.loadUserLlmSettings = async function (userId) {
  const uid = userId || (window.currentUserId ? window.currentUserId() : 1);
  const resp = await fetch(`/api/users/${uid}/llm-settings`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const settings = await resp.json();
  window.state.llmSettings = settings || null;
  window.applyLlmSettingsToForm(window.state.llmSettings);
  if (typeof window.updateUiState === 'function') window.updateUiState();
  return window.state.llmSettings;
};

window.initLlmProviderControls = async function () {
  const { llmProviderSelectEl, showAllModelsToggleEl } = window.getEls();
  if (llmProviderSelectEl) {
    llmProviderSelectEl.addEventListener('change', async () => {
      window.updateLlmProviderFormVisibility();
      const userId = window.state?.playerUserId || 1;
      await window.loadModels(userId);
    });
  }
  if (showAllModelsToggleEl) {
    showAllModelsToggleEl.checked = !!window.state.showAllProviderModels;
    showAllModelsToggleEl.addEventListener('change', async () => {
      window.state.showAllProviderModels = !!showAllModelsToggleEl.checked;
      const userId = window.state?.playerUserId || 1;
      await window.loadModels(userId);
    });
  }
  window.updateLlmProviderFormVisibility();

  try {
    await window.loadLlmSettings();
  } catch (e) {
    console.warn('GET /api/settings/llm failed:', e);
  }
};

window._debugFormatTs = function (date = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

window._debugRoleFromMessageEl = function (msgEl) {
  if (!msgEl || !msgEl.classList) return "unknown";
  if (msgEl.classList.contains("user")) return "player";
  if (msgEl.classList.contains("assistant")) return "gm";
  if (msgEl.classList.contains("error")) return "error";
  if (msgEl.classList.contains("system")) return "system";
  return "unknown";
};

window._debugCollectLastMessages = function (count) {
  const chatEl = document.getElementById("chat");
  if (!chatEl) return [];
  const all = Array.from(chatEl.querySelectorAll(".message"));
  const selected = all.slice(Math.max(0, all.length - count));
  return selected.map((msgEl) => {
    const role = window._debugRoleFromMessageEl(msgEl);
    const content = (msgEl.querySelector("pre")?.textContent || "").trim();
    return { role, content };
  }).filter((item) => item.content.length > 0);
};

window._debugCollectErrors = function () {
  const chatEl = document.getElementById("chat");
  if (!chatEl) return [];
  return Array.from(chatEl.querySelectorAll(".message.error pre"))
    .map((el) => (el.textContent || "").trim())
    .filter(Boolean);
};

window._debugCharacterLine = function () {
  const character = window.currentCharacter ? window.currentCharacter() : null;
  const sheet = window.state.characterSheet && typeof window.state.characterSheet === "object"
    ? window.state.characterSheet
    : {};
  const stats = sheet.stats && typeof sheet.stats === "object" ? sheet.stats : {};
  const hp = `${Number(sheet.current_hp || 0)}/${Number(sheet.max_hp || 0)}`;
  const str = Number(stats.STR ?? stats.str ?? 0);
  const dex = Number(stats.DEX ?? stats.dex ?? 0);
  const con = Number(stats.CON ?? stats.con ?? 0);
  return `CHARACTER: ${character?.name || "Unknown"} | HP: ${hp} | STR:${str} DEX:${dex} CON:${con}`;
};

window._debugBuildSnapshotText = function (messageCount) {
  const ts = window._debugFormatTs();
  const lines = [`--- DEBUG SNAPSHOT [${ts}] ---`];
  lines.push(window._debugCharacterLine());
  lines.push("LAST TURNS:");

  const turns = window._debugCollectLastMessages(messageCount);
  if (turns.length === 0) {
    lines.push("  [system] none");
  } else {
    turns.forEach((m) => lines.push(`  [${m.role}] ${m.content}`));
  }

  const lastApi = window.state.lastApiCall;
  if (lastApi && lastApi.url) {
    lines.push(`LAST API: ${lastApi.method || "GET"} ${lastApi.url} → ${lastApi.status ?? "?"}`);
  } else {
    lines.push("LAST API: none");
  }

  const errors = window._debugCollectErrors();
  lines.push(`ERROR: ${errors.length ? errors.join(" | ") : "none"}`);
  lines.push("-----------------------------------------");
  return lines.join("\n");
};

window._debugShowManualCopyPopup = function (text) {
  const wrap = document.createElement("div");
  wrap.style.cssText = [
    "position:fixed",
    "inset:0",
    "background:rgba(0,0,0,0.35)",
    "display:flex",
    "align-items:center",
    "justify-content:center",
    "z-index:2000",
    "padding:16px"
  ].join(";");

  const panel = document.createElement("div");
  panel.style.cssText = [
    "background:var(--panel,#fff)",
    "border:1px solid var(--border,#ccc)",
    "border-radius:10px",
    "width:min(900px,95vw)",
    "padding:12px",
    "display:flex",
    "flex-direction:column",
    "gap:10px"
  ].join(";");

  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.cssText = "width:100%;min-height:300px;font-family:monospace;font-size:12px;";

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "secondary";
  closeBtn.textContent = "Zamknij";
  closeBtn.onclick = () => wrap.remove();

  panel.appendChild(ta);
  panel.appendChild(closeBtn);
  wrap.appendChild(panel);
  document.body.appendChild(wrap);
  ta.focus();
  ta.select();
};

window.copyDebugSnapshot = async function () {
  const rawCount = prompt("Ile ostatnich wiadomości skopiować?", "8");
  if (rawCount === null) return;
  const messageCount = Math.max(1, Math.min(100, Number.parseInt(rawCount, 10) || 8));
  const text = window._debugBuildSnapshotText(messageCount);

  try {
    await navigator.clipboard.writeText(text);
    window.addMessage?.({
      speaker: "System",
      text: "Snapshot debug skopiowany do schowka.",
      role: "system",
    });
  } catch (_err) {
    window._debugShowManualCopyPopup(text);
  }
};

window.bindDebugSnapshotButton = function () {
  const btn = document.getElementById("copy-debug-btn");
  if (!btn) return;
  btn.onclick = window.copyDebugSnapshot;
};

/**
 * Tymczasowy podgląd stanu walki pod przyciskiem Copy Debug.
 * @param {null|object} payload — `null`, obiekt stanu walki z syncu, albo odpowiedź GET `{ active, combat }`.
 */
window.updateCombatDebugStatusLabel = function (payload) {
  const el = document.getElementById("combat-debug-status");
  if (!el) return;

  const hint =
    window.state && String(window.state._combatDebugEnemyHint || "").trim()
      ? String(window.state._combatDebugEnemyHint).trim()
      : "";

  let cs = null;
  let via = "sync ";

  if (payload && typeof payload === "object" && "active" in payload && "combat" in payload) {
    via = "GET ";
    if (!payload.active || payload.combat == null) {
      let line = "COMBAT: " + via + "(brak — active=false)";
      if (hint) line += "\nWróg: " + hint;
      el.textContent = line;
      return;
    }
    cs = payload.combat;
  } else {
    cs = payload || null;
    if (cs && typeof cs === "object" && Object.keys(cs).length === 0) {
      cs = null;
    }
  }

  if (!cs) {
    let line = "COMBAT: " + via + "brak aktywnej walki";
    if (hint) line += "\nWróg: " + hint;
    el.textContent = line;
    return;
  }

  const combatants = Array.isArray(cs.combatants) ? cs.combatants : [];
  const enemies = combatants.filter((c) => c && c.type === "enemy");
  if (window.state && enemies.length) {
    window.state._combatDebugEnemyHint = enemies
      .map((e) => {
        const k = String(e.enemy_key || e.id || "?").trim() || "?";
        const lab = String(e.name || e.label || k).trim() || k;
        return `${k} — ${lab}`;
      })
      .join("; ");
  }

  const st = String(cs.status ?? "?");
  const cur = cs.current_turn != null ? String(cs.current_turn) : "—";
  const er = cs.ended_reason != null ? String(cs.ended_reason) : "";
  const id = cs.id != null ? String(cs.id) : "";
  const parts = ["status=" + st, "tura=" + cur];
  if (er) parts.push("reason=" + er);
  if (id) parts.push("#" + id);

  let targetLine = "";
  if (st === "active" && cur && cur !== "player") {
    const e = combatants.find((c) => c && String(c.id) === cur);
    if (e && e.type === "enemy") {
      const k = String(e.enemy_key || e.id || "?");
      const nm = String(e.name || e.label || k);
      const hp = Number(e.hp_current ?? 0);
      const mx = Math.max(1, Number(e.hp_max ?? 1));
      targetLine = `Przeciwnik: ${k} — ${nm} HP ${hp}/${mx}`;
    }
  }

  let main = "COMBAT: " + via + parts.join(" · ");
  if (targetLine) main += "\n" + targetLine;
  el.textContent = main;
};

function _extractBalancedJsonObject(text, startIndex) {
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let i = startIndex; i < text.length; i += 1) {
    const ch = text[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (ch === '\\') {
      escaped = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (ch === '{') depth += 1;
    if (ch === '}') {
      depth -= 1;
      if (depth === 0) {
        return text.slice(startIndex, i + 1);
      }
    }
  }
  return null;
}

window.extractLocationIntentDebug = function (text) {
  const raw = String(text || '').trim();
  if (!raw) return null;

  const unwrapped = raw
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim();

  try {
    const parsed = JSON.parse(unwrapped);
    if (parsed && typeof parsed === 'object' && parsed.location_intent) {
      return parsed.location_intent;
    }
  } catch (_e) {
    /* fall back to extracting the location_intent object only */
  }

  const keyIndex = unwrapped.indexOf('"location_intent"');
  if (keyIndex < 0) return null;
  const colonIndex = unwrapped.indexOf(':', keyIndex);
  if (colonIndex < 0) return null;
  const after = unwrapped.slice(colonIndex + 1).trimStart();
  if (after.startsWith('null')) return null;
  const objectStart = unwrapped.indexOf('{', colonIndex);
  if (objectStart < 0) return null;
  const objectText = _extractBalancedJsonObject(unwrapped, objectStart);
  if (!objectText) return null;
  try {
    return JSON.parse(objectText);
  } catch (_e) {
    return null;
  }
};

window.renderLocationIntentDebug = function () {
  const panel = document.getElementById('location-debug-panel');
  const pre = document.getElementById('location-debug-json');
  if (!panel || !pre) return;

  const intent = window.state?._locationIntentDebug || null;
  if (!intent) {
    panel.querySelector('summary').textContent = 'LOCATION: brak intencji';
    pre.textContent = '—';
    return;
  }

  const action = String(intent.action || '?');
  const label = String(intent.target_label || intent.target_key || '?');
  panel.querySelector('summary').textContent = `LOCATION: ${action} → ${label}`;
  pre.textContent = JSON.stringify(intent, null, 2);
};

window.updateLocationIntentDebugFromText = function (assistantText, source = 'gm') {
  const intent = window.extractLocationIntentDebug(assistantText);
  void source;
  if (!window.state) window.state = {};
  window.state._locationIntentDebug = intent || null;
  window.renderLocationIntentDebug();
  return intent;
};

window.closeHistorySummaryModal = function () {
  const overlay = document.getElementById("history-summary-overlay");
  if (!overlay) return;
  overlay.style.display = "none";
  overlay.setAttribute("aria-hidden", "true");
};

/**
 * T09: Tekst błędu z body JSON (FastAPI: detail string | object | walidacja).
 * @param {any} data
 * @returns {string}
 */
window._parseHistorySummaryDetail = function (data) {
  const d = data && data.detail;
  if (typeof d === "string" && d.trim()) return d.trim();
  if (Array.isArray(d) && d.length) {
    const parts = d.map((x) => (x && x.msg) || JSON.stringify(x)).filter(Boolean);
    if (parts.length) return parts.join(" ");
  }
  if (d && typeof d === "object") {
    if (typeof d.message === "string" && d.message.trim()) return d.message.trim();
    if (d.error === "summary_rollup_cooldown" && typeof d.message === "string") {
      return d.message.trim();
    }
  }
  return "";
};

/**
 * T09: Czytelny komunikat dla użytkownika wg kodu HTTP + JSON ([S11b], T08 429).
 * @param {number} status
 * @param {any} data
 * @returns {string}
 */
window.formatHistorySummaryApiError = function (status, data) {
  const parsed = window._parseHistorySummaryDetail(data);
  if (parsed) return parsed;
  if (status === 429) {
    return (
      "Zbyt częste odświeżanie skrótu fabularnego dla tej kampanii (cooldown). " +
      "Poczekaj na kolejne tury narracyjne lub użyj zapisanego skrótu poniżej."
    );
  }
  if (status === 502) {
    return (
      "Model LLM nie wygenerował podsumowania (błąd lub timeout). " +
      "Możesz spróbować ponownie później — poniżej ewentualnie ostatni zapisany skrót."
    );
  }
  if (status === 403) return "Brak uprawnień do wygenerowania podsumowania (tylko właściciel kampanii).";
  if (status === 404) return "Nie znaleziono kampanii lub podsumowania.";
  if (status >= 500) return "Błąd serwera przy podsumowaniu. Spróbuj ponownie później.";
  return `Żądanie nie powiodło się (HTTP ${status}).`;
};

/**
 * Odczyt ostatniego zapisanego skrótu (player) — fallback przy błędzie LLM / ensure.
 * @param {string|number} campaignId
 * @returns {Promise<{ summary: string | null, ok: boolean }>}
 */
window.fetchLatestSavedHistorySummary = async function (campaignId) {
  const cid = String(campaignId || "").trim();
  if (!cid) return { summary: null, ok: false };
  try {
    const qs = new URLSearchParams({ audience: "player" });
    const r = await fetch(`/api/campaigns/${cid}/history/summary?${qs}`);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { summary: null, ok: false };
    const s = data.summary;
    if (s != null && String(s).trim() !== "") return { summary: String(s), ok: true };
    return { summary: null, ok: true };
  } catch (_e) {
    return { summary: null, ok: false };
  }
};

/**
 * @param {{ forceRegenerate?: boolean }} opts
 */
window.loadHistorySummaryModalContent = async function (opts) {
  const forceRegenerate = !!(opts && opts.forceRegenerate);
  const bodyEl = document.getElementById("history-summary-body");
  const emptyEl = document.getElementById("history-summary-empty");
  const loadingEl = document.getElementById("history-summary-loading");
  const cid = window.state?.selectedCampaignId;
  if (!cid) {
    window.addMessage?.({
      speaker: "System",
      text: "Wybierz kampanię, żeby zobaczyć podsumowanie.",
      role: "system",
    });
    return;
  }
  const uid = window.state?.playerUserId || 1;

  if (forceRegenerate) {
    const camp = typeof window.currentCampaign === "function" ? window.currentCampaign() : null;
    const ownerId = Number(camp?.owner_user_id ?? camp?.owneruserid ?? 0);
    if (!camp || ownerId !== Number(uid)) {
      window.addMessage?.({
        speaker: "System",
        text: "Tylko właściciel kampanii może ponownie wygenerować podsumowanie.",
        role: "system",
      });
      return;
    }
    const ok = window.confirm(
      "Wygenerować ponownie podsumowanie narracji? Wywoła model LLM i nadpisze zapisane podsumowanie."
    );
    if (!ok) return;
  }

  const dualWrap = document.getElementById("history-summary-dual-wrap");
  if (dualWrap) dualWrap.style.display = "none";

  if (loadingEl) loadingEl.style.display = "block";
  if (bodyEl) {
    bodyEl.style.display = "none";
    bodyEl.textContent = "";
  }
  if (emptyEl) {
    emptyEl.style.display = "none";
    emptyEl.textContent =
      "Brak podsumowania — pojawi się po turach narracyjnych, gdy właściciel kampanii otworzy to okno (automatyczne odświeżanie co 5 nowych tur).";
  }

  const bannerEl = document.getElementById("history-summary-banner");
  if (bannerEl) {
    bannerEl.style.display = "none";
    bannerEl.textContent = "";
    bannerEl.style.borderLeftColor = "#888";
    bannerEl.style.background = "";
  }

  try {
    const showBanner = (text, kind) => {
      if (!bannerEl) return;
      if (!text) {
        bannerEl.style.display = "none";
        return;
      }
      bannerEl.textContent = text;
      bannerEl.style.display = "block";
      if (kind === "error") {
        bannerEl.style.borderLeftColor = "#c62828";
        bannerEl.style.background = "rgba(198, 40, 40, 0.08)";
      } else if (kind === "warn") {
        bannerEl.style.borderLeftColor = "#f57c00";
        bannerEl.style.background = "rgba(245, 124, 0, 0.08)";
      } else {
        bannerEl.style.borderLeftColor = "#1565c0";
        bannerEl.style.background = "rgba(21, 101, 192, 0.06)";
      }
    };

    let data;
    if (forceRegenerate) {
      const qs = new URLSearchParams({
        user_id: String(uid),
        persist: "true",
        max_turns: "200",
      });
      const r = await fetch(`/api/campaigns/${cid}/history/summary?${qs}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      data = await r.json().catch(() => ({}));
      if (!r.ok) {
        const errMsg = window.formatHistorySummaryApiError(r.status, data);
        const fb = await window.fetchLatestSavedHistorySummary(cid);
        if (loadingEl) loadingEl.style.display = "none";
        if (fb.summary && bodyEl) {
          bodyEl.textContent = fb.summary;
          bodyEl.style.display = "block";
          showBanner(
            "Nie udało się wygenerować nowego podsumowania. " +
              errMsg +
              " Poniżej ostatni zapisany skrót — odśwież ponownie, gdy LLM zadziała.",
            "error"
          );
        } else if (emptyEl) {
          emptyEl.style.display = "block";
          showBanner(errMsg, "error");
        }
        return;
      }
    } else {
      const qs = new URLSearchParams({
        user_id: String(uid),
        stale_after_turns: "5",
      });
      const r = await fetch(`/api/campaigns/${cid}/history/summary/ensure?${qs}`, {
        method: "POST",
      });
      data = await r.json().catch(() => ({}));
      if (!r.ok) {
        const errMsg = window.formatHistorySummaryApiError(r.status, data);
        const fb = await window.fetchLatestSavedHistorySummary(cid);
        if (loadingEl) loadingEl.style.display = "none";
        if (fb.summary && bodyEl) {
          bodyEl.textContent = fb.summary;
          bodyEl.style.display = "block";
          showBanner(
            "Automatyczne odświeżenie się nie powiodło. " +
              errMsg +
              " Poniżej ostatni zapisany skrót.",
            "error"
          );
        } else if (emptyEl) {
          emptyEl.style.display = "block";
          showBanner(errMsg, "error");
        }
        return;
      }
    }

    if (loadingEl) loadingEl.style.display = "none";

    if (!forceRegenerate && data && data.cooldown_active) {
      const need = data.turns_until_summary_rollup_allowed;
      const parts = [
        "Pełne odświeżenie przez LLM jest tymczasowo ograniczone (cooldown). Wyświetlono ostatni zapisany skrót.",
        need != null && Number(need) > 0
          ? `Kolejne odświeżenie LLM po ok. ${need} turach narracyjnych.`
          : "",
      ].filter(Boolean);
      showBanner(parts.join(" "), "warn");
    } else if (data && data.warning && String(data.warning).trim()) {
      showBanner(String(data.warning).trim(), "warn");
    }

    const s = data.summary;
    if (s != null && String(s).trim() !== "") {
      if (bodyEl) {
        bodyEl.textContent = String(s);
        bodyEl.style.display = "block";
      }
    } else if (emptyEl) {
      emptyEl.style.display = "block";
    }
  } catch (e) {
    if (loadingEl) loadingEl.style.display = "none";
    const errText =
      e && e.message
        ? String(e.message)
        : "Nieznany błąd wczytywania podsumowania.";
    const fb = await window.fetchLatestSavedHistorySummary(cid);
    const bannerElCatch = document.getElementById("history-summary-banner");
    if (bannerElCatch && fb.summary && bodyEl) {
      bodyEl.textContent = fb.summary;
      bodyEl.style.display = "block";
      bannerElCatch.textContent =
        "Błąd wczytywania: " +
        errText +
        " Poniżej ostatni zapisany skrót (jeśli był w bazie).";
      bannerElCatch.style.display = "block";
      bannerElCatch.style.borderLeftColor = "#c62828";
      bannerElCatch.style.background = "rgba(198, 40, 40, 0.08)";
    } else if (bodyEl) {
      bodyEl.textContent = "Błąd wczytywania: " + errText;
      bodyEl.style.display = "block";
    }
  }
};

window.openHistorySummaryModal = async function () {
  const overlay = document.getElementById("history-summary-overlay");
  const regenBtn = document.getElementById("history-summary-regenerate-btn");
  if (!overlay) return;
  const cid = window.state?.selectedCampaignId;
  if (!cid) {
    window.addMessage?.({
      speaker: "System",
      text: "Wybierz kampanię, żeby zobaczyć podsumowanie.",
      role: "system",
    });
    return;
  }
  overlay.style.display = "flex";
  overlay.setAttribute("aria-hidden", "false");

  if (regenBtn) {
    const camp = typeof window.currentCampaign === "function" ? window.currentCampaign() : null;
    const ownerId = Number(camp?.owner_user_id ?? camp?.owneruserid ?? 0);
    const uid = Number(window.state?.playerUserId || 0);
    const isOwner = !!(camp && ownerId === uid);
    regenBtn.style.display = isOwner ? "inline-flex" : "none";
    regenBtn.disabled = !isOwner;
  }
  const dualBtn = document.getElementById("history-summary-dual-preview-btn");
  if (dualBtn) {
    const settings = await window.getSummarySettingsForUi();
    const camp = typeof window.currentCampaign === "function" ? window.currentCampaign() : null;
    const ownerId = Number(camp?.owner_user_id ?? camp?.owneruserid ?? 0);
    const uid = Number(window.state?.playerUserId || 0);
    const isAdmin = !!window.state?.playerIsAdmin;
    const isOwner = !!(camp && ownerId === uid);
    const mode = String(settings?.dual_summary_preview_mode || "owner_admin");
    const allowed =
      mode !== "off" && isOwner && (mode === "owner" || (mode === "owner_admin" && isAdmin));
    dualBtn.style.display = allowed ? "inline-flex" : "none";
    dualBtn.disabled = !allowed;
  }

  await window.loadHistorySummaryModalContent({ forceRegenerate: false });
};

window.getSummarySettingsForUi = async function () {
  if (window.__summarySettingsUiCache) return window.__summarySettingsUiCache;
  try {
    const r = await fetch("/api/settings/summary");
    const data = await r.json().catch(() => ({}));
    const payload = data?.data && typeof data.data === "object" ? data.data : {};
    const out = {
      summary_rollup_cooldown_turns: Number(payload.summary_rollup_cooldown_turns || 20),
      dual_summary_preview_mode: String(payload.dual_summary_preview_mode || "owner_admin"),
    };
    window.__summarySettingsUiCache = out;
    return out;
  } catch (_err) {
    return {
      summary_rollup_cooldown_turns: 20,
      dual_summary_preview_mode: "owner_admin",
    };
  }
};

window.runHistorySummaryDualPreview = async function () {
  const cid = window.state?.selectedCampaignId;
  const uid = window.state?.playerUserId || 1;
  const settings = await window.getSummarySettingsForUi();
  const camp = typeof window.currentCampaign === "function" ? window.currentCampaign() : null;
  const ownerId = Number(camp?.owner_user_id ?? camp?.owneruserid ?? 0);
  const isAdmin = !!window.state?.playerIsAdmin;
  const mode = String(settings?.dual_summary_preview_mode || "owner_admin");
  const allowed =
    !!cid &&
    Number(uid) === ownerId &&
    mode !== "off" &&
    (mode === "owner" || (mode === "owner_admin" && isAdmin));
  if (!allowed) {
    let msg = "Podgląd dual (T01) jest obecnie niedostępny.";
    if (!cid || Number(uid) !== ownerId) {
      msg = "Podgląd dual (T01) wymaga właściciela kampanii.";
    } else if (mode === "owner_admin") {
      msg = "Podgląd dual (T01) wymaga właściciela kampanii z rolą global admin.";
    } else if (mode === "off") {
      msg = "Podgląd dual (T01) jest wyłączony w ustawieniach admin.";
    }
    window.addMessage?.({
      speaker: "System",
      text: msg,
      role: "system",
    });
    return;
  }
  const ok = window.confirm(
    "Podgląd dual (T01): jedno wywołanie LLM zwróci tekst dla gracza i notatkę MG. Nie zapisuje nic w bazie. Kontynuować?"
  );
  if (!ok) return;

  const dualWrap = document.getElementById("history-summary-dual-wrap");
  const dualMeta = document.getElementById("history-summary-dual-meta");
  const dualPl = document.getElementById("history-summary-dual-player");
  const dualGm = document.getElementById("history-summary-dual-gm");
  const loadingEl = document.getElementById("history-summary-loading");
  if (dualWrap) dualWrap.style.display = "block";
  if (dualMeta) dualMeta.textContent = "Wywołanie modelu…";
  if (dualPl) dualPl.textContent = "";
  if (dualGm) dualGm.textContent = "";
  if (loadingEl) loadingEl.style.display = "block";

  try {
    const qs = new URLSearchParams({
      user_id: String(uid),
      max_turns: "200",
    });
    const url = `/api/campaigns/${cid}/dual-summary-preview?${qs}`;
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      let msg =
        typeof data.detail === "string" ? data.detail : `HTTP ${r.status}`;
      if (r.status === 404) {
        const d = typeof data.detail === "string" ? data.detail : "";
        if (d === "Campaign not found") {
          msg +=
            " — w tej bazie nie ma kampanii o tym ID (np. inne środowisko). Odśwież listę kampanii lub użyj instancji z właściwą bazą.";
        } else if (d === "Not Found" || !d) {
          msg +=
            " — backend nie ma endpointu (zbyt stary obraz dev/prod?). Na serwerze dev: `docker compose -f docker-compose.dev.yml build backend && docker compose -f docker-compose.dev.yml up -d backend`.";
        }
      }
      throw new Error(msg);
    }
    if (dualPl) dualPl.textContent = String(data.player_summary ?? "");
    if (dualGm) dualGm.textContent = String(data.gm_notes ?? "");
    const leaks = Array.isArray(data.leaked_plan_tokens)
      ? data.leaked_plan_tokens.join(", ")
      : "";
    const pe = data.parse_error ? `Błąd parsowania JSON: ${data.parse_error}` : "";
    const warn = data.warning ? String(data.warning) : "";
    if (dualMeta) {
      dualMeta.textContent = [
        `Model: ${data.model_used ?? "—"}`,
        `Tury w podglądzie: ${data.included_turn_count ?? "—"}`,
        leaks ? `Heurystyka „token z planu w tekście gracza”: ${leaks}` : "Brak trafień heurystyki wycieku (albo pusty plan).",
        pe,
        warn,
      ]
        .filter(Boolean)
        .join(" · ");
    }
  } catch (e) {
    if (dualMeta) {
      dualMeta.textContent =
        "Błąd: " + (e && e.message ? e.message : String(e));
    }
  } finally {
    if (loadingEl) loadingEl.style.display = "none";
  }
};

window.bindHistorySummaryButton = function () {
  const btn = document.getElementById("history-summary-btn");
  const regenBtn = document.getElementById("history-summary-regenerate-btn");
  const dualBtn = document.getElementById("history-summary-dual-preview-btn");
  const overlay = document.getElementById("history-summary-overlay");
  const closeBtn = document.getElementById("history-summary-close");
  if (btn) {
    btn.onclick = () => window.openHistorySummaryModal();
  }
  if (regenBtn) {
    regenBtn.onclick = () => window.loadHistorySummaryModalContent({ forceRegenerate: true });
  }
  if (dualBtn) {
    dualBtn.onclick = () => window.runHistorySummaryDualPreview();
  }
  if (closeBtn) {
    closeBtn.onclick = () => window.closeHistorySummaryModal();
  }
  if (overlay) {
    overlay.onclick = (e) => {
      if (e.target === overlay) window.closeHistorySummaryModal();
    };
  }
};

window.installApiDebugTracker = function () {
  if (window.__apiDebugTrackerInstalled) return;
  if (typeof window.fetch !== "function") return;
  window.__apiDebugTrackerInstalled = true;
  const originalFetch = window.fetch.bind(window);

  window.fetch = async function (input, init) {
    const method = (init?.method || "GET").toUpperCase();
    const url = typeof input === "string" ? input : (input?.url || "");
    try {
      const response = await originalFetch(input, init);
      window.state.lastApiCall = { method, url, status: response.status };
      return response;
    } catch (error) {
      window.state.lastApiCall = { method, url, status: "ERR" };
      throw error;
    }
  };
};

window.ROLL_VALID_TESTS = new Set([
  "athletics", "stealth", "awareness", "survival", "lore", "investigation",
  "arcana", "alchemy", "medicine", "persuasion", "intimidation",
  "melee_attack", "ranged_attack", "spell_attack",
  "fortitude_save", "reflex_save", "willpower_save", "arcane_save",
  "death_save",
  "initiative",
]);

window.ROLL_TEST_ALIASES = {
  "Str Save": "fortitude_save",
  "Con Save": "fortitude_save",
  "Dex Save": "reflex_save",
  "Wis Save": "willpower_save",
  "Int Save": "arcane_save",
  "Cha Save": "willpower_save",
  "Athletics": "athletics",
  "Stealth": "stealth",
  "Awareness": "awareness",
  "Perception": "awareness",
  "Survival": "survival",
  "Lore": "lore",
  "Investigation": "investigation",
  "Arcana": "arcana",
  "Alchemy": "alchemy",
  "Death Save": "death_save",
  "Medicine": "medicine",
  "Persuasion": "persuasion",
  "Intimidation": "intimidation",
  "Attack": "melee_attack",
  "Melee Attack": "melee_attack",
  "Ranged Attack": "ranged_attack",
  "Spell Attack": "spell_attack",
  Initiative: "initiative",
};

window.resolveRollTestName = function (raw) {
  const source = String(raw || "").trim();
  if (!source) return null;
  const titleKey = source
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
  if (window.ROLL_TEST_ALIASES[titleKey]) {
    return window.ROLL_TEST_ALIASES[titleKey];
  }
  const normalized = source.toLowerCase().replace(/-/g, "_").replace(/\s+/g, "_");
  return window.ROLL_VALID_TESTS.has(normalized) ? normalized : null;
};

/** Dozwolone skill z cue GM gdy postać ma HP > 0 (death_save tylko przy HP <= 0). */
window.ALLOWED_ROLL_SKILLS_ALIVE = new Set([
  "melee_attack",
  "ranged_attack",
  "spell_attack",
  "athletics",
  "stealth",
  "awareness",
  "survival",
  "lore",
  "investigation",
  "arcana",
  "alchemy",
  "medicine",
  "persuasion",
  "intimidation",
  "fortitude_save",
  "reflex_save",
  "willpower_save",
  "arcane_save",
  "initiative",
]);

window.getCharacterHpForRollRules = function () {
  const sheet = window.state?.characterSheet;
  if (!sheet) return null;
  const v = window.getSheetValue(sheet, ["current_hp", "hp", "health"], null);
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

/**
 * Czy wolno pokazać przycisk „Rzuć kość” / wysłać /roll dla tego cue.
 * Brak jawnego skill w obiekcie (tylko wyciągnięta kość z tekstu) → false.
 */
window.isActiveRollRequestAllowed = function (req) {
  if (!req) return false;
  const skill = String(req.skill || "")
    .trim()
    .toLowerCase();
  if (!skill) {
    return false;
  }
  const hp = window.getCharacterHpForRollRules();

  if (skill === "death_save") {
    if (hp === null) {
      console.warn("[roll] death_save: brak HP na arkuszu — cue zignorowany");
      return false;
    }
    if (hp > 0) {
      console.warn("[roll] death_save przy HP > 0 — cue zignorowany");
      return false;
    }
    return true;
  }

  if (hp !== null && hp <= 0) {
    console.warn("[roll] skill", skill, "przy HP <= 0 — oczekiwany death_save z GM");
    return false;
  }

  return window.ALLOWED_ROLL_SKILLS_ALIVE.has(skill);
};

window.formatRollTestDisplayName = function (canonicalName) {
  const normalized = String(canonicalName || "").trim().toLowerCase();
  const labels = {
    athletics: "Athletics",
    stealth: "Stealth",
    sleight_of_hand: "Sleight of Hand",
    endurance: "Endurance",
    awareness: "Awareness",
    survival: "Survival",
    lore: "Lore",
    investigation: "Investigation",
    arcana: "Arcana",
    alchemy: "Alchemy",
    medicine: "Medicine",
    persuasion: "Persuasion",
    intimidation: "Intimidation",
    melee_attack: "Melee Attack",
    ranged_attack: "Ranged Attack",
    spell_attack: "Spell Attack",
    death_save: "Death Save",
    fortitude_save: "Fortitude Save",
    reflex_save: "Reflex Save",
    willpower_save: "Willpower Save",
    arcane_save: "Arcane Save",
    initiative: "Initiative",
  };
  return labels[normalized] || canonicalName;
};

window.formatSheetSkillKeyLabel = function (key) {
  const k = String(key || "").trim().toLowerCase();
  const map = {
    sleight_of_hand: "Sleight of Hand",
    melee_attack: "Melee Attack",
    ranged_attack: "Ranged Attack",
    spell_attack: "Spell Attack",
    alchemy: "Alchemy",
  };
  if (map[k]) return map[k];
  return k
    .split("_")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
};

window.getSheetEls = function () {
  return {
    playAreaEl: document.querySelector(".play-area"),
    sheetPanelEl: document.getElementById("sheet-panel"),
    sheetPanelBodyEl: document.getElementById("sheet-panel-body")
  };
};

window.getSheetValue = function (obj, keys, fallback = 0) {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      return obj[key];
    }
  }
  return fallback;
};

window.getStatModifier = function (value) {
  return Math.floor((Number(value) - 10) / 2);
};

window.getArchetypeFromSheet = function (sheet) {
  const value = String(sheet?.archetype || "").trim();
  if (!value) return "Unknown";
  const normalized = value.toLowerCase();
  if (normalized === "scholar") return "Scholar";
  if (normalized === "warrior") return "Warrior";
  return value;
};

window.setSheetPanelOpen = function (open) {
  window.state.sheetPanelOpen = !!open;
  localStorage.setItem(window.SHEET_PANEL_STORAGE_KEY, window.state.sheetPanelOpen ? "1" : "0");
  const { playAreaEl, sheetPanelEl } = window.getSheetEls();
  if (!sheetPanelEl || !playAreaEl) return;

  playAreaEl.classList.toggle("sheet-open", window.state.sheetPanelOpen);
  sheetPanelEl.setAttribute("aria-hidden", window.state.sheetPanelOpen ? "false" : "true");
  if (window.state.sheetPanelOpen) {
    window.renderCharacterSheetPanel();
  }
};

window.renderCharacterSheetPanel = function () {
  const { sheetPanelBodyEl } = window.getSheetEls();
  if (!sheetPanelBodyEl) return;

  const character = window.currentCharacter ? window.currentCharacter() : null;
  const sheet = window.state.characterSheet;

  if (!character || !sheet) {
    sheetPanelBodyEl.innerHTML = '<div class="muted">Wybierz postać</div>';
    return;
  }

  const archetype = window.getArchetypeFromSheet(sheet);
  const currentHp = Number(window.getSheetValue(sheet, ["current_hp", "hp", "health"], 0));
  const maxHp = Number(window.getSheetValue(sheet, ["max_hp", "hp_max", "maxHealth"], currentHp || 1));
  const hpPercent = Math.max(0, Math.min(100, (currentHp / Math.max(1, maxHp)) * 100));

  const currentMana = Number(window.getSheetValue(sheet, ["current_mana", "mana"], 0));
  const maxMana = Number(window.getSheetValue(sheet, ["max_mana", "mana_max"], currentMana || 1));
  const manaPercent = Math.max(0, Math.min(100, (currentMana / Math.max(1, maxMana)) * 100));

  const statsObj = sheet.stats && typeof sheet.stats === "object" ? sheet.stats : {};
  const skillsObj = sheet.skills && typeof sheet.skills === "object" ? sheet.skills : {};

  const statsHtml = window.SHEET_STATS.map((key) => {
    const raw = window.getSheetValue(statsObj, [key, key.toLowerCase()], 10);
    const value = Number(raw);
    const mod = window.getStatModifier(value);
    const modLabel = mod >= 0 ? `+${mod}` : String(mod);
    return `
      <div class="sheet-stat">
        <span class="sheet-stat-key">${window.escapeHtml(key)}</span>
        <span class="sheet-stat-val">${window.escapeHtml(value)}</span>
        <span class="sheet-stat-mod">${window.escapeHtml(modLabel)}</span>
      </div>
    `;
  }).join("");

  const skillKeys = Object.keys(skillsObj || {}).sort((a, b) => a.localeCompare(b));
  const skillsHtml =
    skillKeys.length === 0
      ? '<div class="muted">—</div>'
      : skillKeys
          .map((sk) => {
            const raw = window.getSheetValue(skillsObj, [sk, sk.toLowerCase()], 0);
            const value = Number(raw);
            const clamped = Math.max(0, Math.min(5, Number.isFinite(value) ? value : 0));
            const label = window.formatSheetSkillKeyLabel(sk);
            return `
      <div class="sheet-skill">
        <span>${window.escapeHtml(label)}</span>
        <strong>${window.escapeHtml(clamped)}/5</strong>
      </div>
    `;
          })
          .join("");

  const ident = sheet.identity && typeof sheet.identity === "object" ? sheet.identity : {};
  const appearance = String(ident.appearance || "").trim();
  const personality = String(ident.personality || "").trim();
  const flaw = String(ident.flaw || "").trim();

  const identityHtml =
    appearance || personality || flaw
      ? `
    <div class="sheet-foldable-section" data-section="identity">
      <div class="sheet-section-header" data-fold-toggle="identity" role="button" tabindex="0">
        <h4 class="sheet-section-title">Postać</h4>
        <span class="fold-icon" aria-hidden="true">▾</span>
      </div>
      <div class="sheet-section-body">
        <div class="sheet-identity-block sheet-fluff">
      ${
        appearance
          ? `<div class="sheet-identity-field"><span class="sheet-identity-label">Wygląd</span><p class="sheet-identity-text">${window.escapeHtml(appearance)}</p></div>`
          : ""
      }
      ${
        personality
          ? `<div class="sheet-identity-field"><span class="sheet-identity-label">Osobowość</span><p class="sheet-identity-text">${window.escapeHtml(personality)}</p></div>`
          : ""
      }
      ${
        flaw
          ? `<div class="sheet-identity-field"><span class="sheet-identity-label">Wada</span><p class="sheet-identity-text">${window.escapeHtml(flaw)}</p></div>`
          : ""
      }
        </div>
      </div>
    </div>`
      : "";

  sheetPanelBodyEl.innerHTML = `
    <div class="sheet-heading">
      <div class="sheet-name">${window.escapeHtml(character.name || "Bohater")}</div>
      <div class="sheet-archetype">${window.escapeHtml(archetype)}</div>
    </div>

    <div class="sheet-resource">
      <div class="sheet-resource-top">
        <span>HP</span>
        <span>${window.escapeHtml(currentHp)} / ${window.escapeHtml(maxHp)}</span>
      </div>
      <div class="sheet-bar"><div class="sheet-bar-fill hp" style="width:${hpPercent}%"></div></div>
    </div>

    ${archetype.toLowerCase() === "scholar" ? `
      <div class="sheet-resource">
        <div class="sheet-resource-top">
          <span>Mana</span>
          <span>${window.escapeHtml(currentMana)} / ${window.escapeHtml(maxMana)}</span>
        </div>
        <div class="sheet-bar"><div class="sheet-bar-fill mana" style="width:${manaPercent}%"></div></div>
      </div>
    ` : ""}

    <div class="sheet-foldable-section" data-section="stats">
      <div class="sheet-section-header" data-fold-toggle="stats" role="button" tabindex="0">
        <h4 class="sheet-section-title">Statystyki</h4>
        <span class="fold-icon" aria-hidden="true">▾</span>
      </div>
      <div class="sheet-section-body">
        <div class="sheet-stats-grid">${statsHtml}</div>
      </div>
    </div>

    <div class="sheet-foldable-section" data-section="skills">
      <div class="sheet-section-header" data-fold-toggle="skills" role="button" tabindex="0">
        <h4 class="sheet-section-title">Umiejętności</h4>
        <span class="fold-icon" aria-hidden="true">▾</span>
      </div>
      <div class="sheet-section-body">
        <div class="sheet-skills-grid">${skillsHtml}</div>
      </div>
    </div>

    <div class="sheet-foldable-section" data-section="inventory">
      <div class="sheet-section-header" data-fold-toggle="inventory" role="button" tabindex="0">
        <h4 class="sheet-section-title">Ekwipunek</h4>
        <span class="fold-icon" aria-hidden="true">▾</span>
      </div>
      <div class="sheet-section-body">
        <div class="gold-display">
          💰 <span id="gold-amount">—</span> GP
        </div>
        <div class="equipment-slots">
          <div class="equip-slot" data-slot="main_hand">
            <span class="slot-label">Główna ręka</span>
            <div class="slot-item" id="slot-main_hand">—</div>
          </div>
          <div class="equip-slot" data-slot="off_hand">
            <span class="slot-label">Pomocnicza ręka</span>
            <div class="slot-item" id="slot-off_hand">—</div>
          </div>
          <div class="equip-slot" data-slot="armor">
            <span class="slot-label">Zbroja</span>
            <div class="slot-item" id="slot-armor">—</div>
          </div>
        </div>
        <div class="backpack">
          <div class="sheet-backpack-heading">Plecak</div>
          <ul id="backpack-list" class="backpack-list"></ul>
        </div>
        <div class="narrative-items hidden" id="narrative-items-section">
          <div class="sheet-backpack-heading">Przedmioty fabularne</div>
          <ul id="narrative-items-list" class="narrative-items-list"></ul>
        </div>
      </div>
    </div>

    ${identityHtml}
  `;

  window.applyFoldState();

  const cid = character && character.id != null ? Number(character.id) : 0;
  if (cid && typeof window.loadInventory === "function") {
    void window.loadInventory(cid);
  }
};

window.loadCharacterSheet = async function (characterId) {
  if (!characterId) {
    window.state.characterSheet = null;
    window.renderCharacterSheetPanel();
    return;
  }

  try {
    let resp = await fetch(`${window.API_BASE_URL}/characters/${characterId}/sheet`);
    if (!resp.ok) {
      resp = await fetch(`/characters/${characterId}/sheet`);
    }
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    window.state.characterSheet =
      data?.sheet_json && typeof data.sheet_json === "object" ? data.sheet_json : {};
  } catch (_err) {
    window.state.characterSheet = {};
  }

  window.renderCharacterSheetPanel();
};

window.bindCharacterSheetPanel = function () {
  /* Sheet refreshes when loadCharacters runs (see wrapper below) after campaign/character state updates. */
};

window.initCharacterSheetPanel = async function () {
  window.installApiDebugTracker();
  window.bindHistorySummaryButton();
  window.bindDebugSnapshotButton();

  const savedState = localStorage.getItem(window.SHEET_PANEL_STORAGE_KEY);
  if (savedState === "1") window.state.sheetPanelOpen = true;
  if (savedState === "0") window.state.sheetPanelOpen = false;

  window.setSheetPanelOpen(window.state.sheetPanelOpen);
  window.bindCharacterSheetPanel();

  const selectedId = Number(window.state.selectedCharacterId || 0);
  if (selectedId) {
    await window.loadCharacterSheet(selectedId);
  } else {
    window.renderCharacterSheetPanel();
  }
};

if (typeof window.loadCharacters === "function") {
  const originalLoadCharacters = window.loadCharacters;
  window.loadCharacters = async function (...args) {
    const result = await originalLoadCharacters.apply(this, args);
    await window.loadCharacterSheet(Number(window.state.selectedCharacterId || 0));
    return result;
  };
}

document.addEventListener("DOMContentLoaded", () => {
  setTimeout(() => {
    window.initCharacterSheetPanel();
  }, 0);
});
