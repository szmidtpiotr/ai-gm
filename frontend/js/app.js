window.state = window.state || {};
window.state.characterSheet = window.state.characterSheet || null;
window.state.sheetPanelOpen = window.state.sheetPanelOpen ?? false;
window.API_BASE_URL = window.API_BASE_URL || "/api";
window.SHEET_PANEL_STORAGE_KEY = "ai-gm:sheetPanelOpen";

window.SHEET_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"];
window.state.lastApiCall = window.state.lastApiCall || null;
window.state.llmSettings = window.state.llmSettings || null;
window.state.showAllProviderModels = window.state.showAllProviderModels ?? false;

window.LLM_SETTINGS_COLLAPSE_PREF_KEY = "ai-gm:llmSettingsCollapsedPref";

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
  const model = (engineSelectEl?.value || 'gemma4:e4b').trim() || 'gemma4:e4b';

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
  if (engineSelectEl && settings.model) {
    engineSelectEl.value = settings.model;
    window.state.selectedEngine = settings.model;
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

window.closeHistorySummaryModal = function () {
  const overlay = document.getElementById("history-summary-overlay");
  if (!overlay) return;
  overlay.style.display = "none";
  overlay.setAttribute("aria-hidden", "true");
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

  try {
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
        const msg =
          typeof data.detail === "string" ? data.detail : `HTTP ${r.status}`;
        throw new Error(msg);
      }
    } else {
      const qs = new URLSearchParams({
        user_id: String(uid),
        stale_after_turns: "5",
      });
      let r = await fetch(
        `/api/campaigns/${cid}/history/summary/ensure?${qs}`,
        { method: "POST" }
      );
      data = await r.json().catch(() => ({}));
      if (!r.ok) {
        const r2 = await fetch(`/api/campaigns/${cid}/history/summary`);
        const d2 = await r2.json().catch(() => ({}));
        if (!r2.ok) {
          const msg =
            typeof data.detail === "string"
              ? data.detail
              : typeof d2.detail === "string"
                ? d2.detail
                : `HTTP ${r.status}`;
          throw new Error(msg);
        }
        data = d2;
      }
    }
    if (loadingEl) loadingEl.style.display = "none";
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
    if (bodyEl) {
      bodyEl.textContent =
        "Błąd wczytywania: " + (e && e.message ? e.message : String(e));
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

  await window.loadHistorySummaryModalContent({ forceRegenerate: false });
};

window.bindHistorySummaryButton = function () {
  const btn = document.getElementById("history-summary-btn");
  const regenBtn = document.getElementById("history-summary-regenerate-btn");
  const overlay = document.getElementById("history-summary-overlay");
  const closeBtn = document.getElementById("history-summary-close");
  if (btn) {
    btn.onclick = () => window.openHistorySummaryModal();
  }
  if (regenBtn) {
    regenBtn.onclick = () => window.loadHistorySummaryModalContent({ forceRegenerate: true });
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
  "death_save"
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
  "Initiative": "reflex_save"
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
    <div class="sheet-identity-block sheet-fluff">
      <h4 class="sheet-section-title">Postać</h4>
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

    <div>
      <h4 class="sheet-section-title">Statystyki</h4>
      <div class="sheet-stats-grid">${statsHtml}</div>
    </div>

    <div>
      <h4 class="sheet-section-title">Umiejętności</h4>
      <div class="sheet-skills-grid">${skillsHtml}</div>
    </div>

    ${identityHtml}
  `;
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
