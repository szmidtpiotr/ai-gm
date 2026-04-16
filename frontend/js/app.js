window.state = window.state || {};
window.state.characterSheet = window.state.characterSheet || null;
window.state.sheetPanelOpen = window.state.sheetPanelOpen ?? false;
window.API_BASE_URL = window.API_BASE_URL || "/api";
window.SHEET_PANEL_STORAGE_KEY = "ai-gm:sheetPanelOpen";

window.SHEET_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"];
window.SHEET_SKILLS = [
  "Athletics",
  "Swordsmanship",
  "Archery",
  "Stealth",
  "Survival",
  "Persuasion",
  "Insight",
  "Arcana",
  "Alchemy",
  "Lore"
];
window.state.lastApiCall = window.state.lastApiCall || null;
window.state.llmSettings = window.state.llmSettings || null;
window.state.showAllProviderModels = window.state.showAllProviderModels ?? false;

window.LLM_SETTINGS_STORAGE_KEY = "ai-gm:llmSettings";

window._safeLlmSettingsForStorage = function (settings) {
  if (!settings || typeof settings !== "object") return null;
  return {
    provider: String(settings.provider || ""),
    base_url: String(settings.base_url || ""),
    model: String(settings.model || ""),
  };
};

window.persistLlmSettingsToStorage = function (settings) {
  const safe = window._safeLlmSettingsForStorage(settings);
  if (!safe) return;
  localStorage.setItem(window.LLM_SETTINGS_STORAGE_KEY, JSON.stringify(safe));
};

window.restoreLlmSettingsFromStorage = function () {
  try {
    const raw = localStorage.getItem(window.LLM_SETTINGS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const safe = window._safeLlmSettingsForStorage(parsed);
    if (!safe) return null;
    // Need at least provider+model to make sense for model list loading.
    if (!safe.provider || !safe.model) return null;
    return safe;
  } catch (_err) {
    return null;
  }
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
};

window.connectLlmSettings = async function () {
  const payload = window.getLlmProviderPayloadFromForm();
  const resp = await fetch('/api/settings/llm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  const data = await resp.json();
  window.state.llmSettings = data?.settings || null;
  window.state.selectedEngine = payload.model;
  // Persist provider/base_url/model across browser refresh.
  // Intentionally do NOT persist api_key (frontend could expose it via localStorage).
  window.persistLlmSettingsToStorage(window.state.llmSettings);
  localStorage.setItem('ai-gm:selectedEngine', payload.model);
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
  return settings;
};

window.initLlmProviderControls = async function () {
  const { llmProviderSelectEl, showAllModelsToggleEl } = window.getEls();
  if (llmProviderSelectEl) {
    llmProviderSelectEl.addEventListener('change', async () => {
      window.updateLlmProviderFormVisibility();
      await window.loadModels();
    });
  }
  if (showAllModelsToggleEl) {
    showAllModelsToggleEl.checked = !!window.state.showAllProviderModels;
    showAllModelsToggleEl.addEventListener('change', async () => {
      window.state.showAllProviderModels = !!showAllModelsToggleEl.checked;
      await window.loadModels();
    });
  }
  window.updateLlmProviderFormVisibility();

  // Fallback: if backend runtime config returns empty strings, restore the last
  // connected provider/base_url/model from localStorage.
  const saved = window.restoreLlmSettingsFromStorage();
  if (saved) {
    window.state.llmSettings = saved;
    window.applyLlmSettingsToForm(saved);
  }

  try {
    const live = await window.loadLlmSettings();
    // If backend didn't have runtime config persisted, keep the localStorage values.
    if (saved && (!live?.provider || !live?.model)) {
      window.state.llmSettings = saved;
      window.applyLlmSettingsToForm(saved);
    }
  } catch (_err) {
    // Keep defaults if settings endpoint is unavailable.
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
  "arcana", "medicine", "persuasion", "intimidation",
  "melee_attack", "ranged_attack", "spell_attack",
  "fortitude_save", "reflex_save", "willpower_save", "arcane_save"
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
    awareness: "Awareness",
    survival: "Survival",
    lore: "Lore",
    investigation: "Investigation",
    arcana: "Arcana",
    medicine: "Medicine",
    persuasion: "Persuasion",
    intimidation: "Intimidation",
    melee_attack: "Melee Attack",
    ranged_attack: "Ranged Attack",
    spell_attack: "Spell Attack",
    fortitude_save: "Fortitude Save",
    reflex_save: "Reflex Save",
    willpower_save: "Willpower Save",
    arcane_save: "Arcane Save",
  };
  return labels[normalized] || canonicalName;
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
  if (normalized === "mage") return "Mage";
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

  const skillsHtml = window.SHEET_SKILLS.map((skill) => {
    const value = Number(window.getSheetValue(skillsObj, [skill, skill.toLowerCase()], 0));
    const clamped = Math.max(0, Math.min(5, value));
    return `
      <div class="sheet-skill">
        <span>${window.escapeHtml(skill)}</span>
        <strong>${window.escapeHtml(clamped)}/5</strong>
      </div>
    `;
  }).join("");

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

    ${archetype.toLowerCase() === "mage" ? `
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
  const characterSelect = document.getElementById("character-select");
  if (characterSelect) {
    characterSelect.addEventListener("change", async () => {
      const id = Number(characterSelect.value);
      await window.loadCharacterSheet(id);
    });
  }

  const campaignSelect = document.getElementById("campaign-select");
  if (campaignSelect) {
    campaignSelect.addEventListener("change", async () => {
      const selectedId = Number(document.getElementById("character-select")?.value || 0);
      await window.loadCharacterSheet(selectedId);
    });
  }
};

window.initCharacterSheetPanel = async function () {
  window.installApiDebugTracker();
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
