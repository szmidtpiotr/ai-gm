import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=21";
import { getBaseUrl, getToken } from "/admin_panel/shared/auth.js?v=19";
import { showToast } from "/admin_panel/shared/toast.js?v=18";

const LLM_LS_KEY = "aigm_admin_test_runner_llm_v1";

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = text;
  return n;
}

function normApiRoot() {
  const b = String(getBaseUrl() || "").replace(/\/+$/, "");
  if (b) return b;
  try {
    return String(window.location.origin || "").replace(/\/+$/, "");
  } catch (_e) {
    return "";
  }
}

function errText(err, fallback) {
  if (err instanceof APIError && err.body && typeof err.body === "object" && err.body.detail) {
    const d = err.body.detail;
    return Array.isArray(d) ? d.join("; ") : String(d);
  }
  return fallback;
}

const DEFAULT_YAML = `{
  "name": "my_test",
  "goal": "Przykładowy test",
  "max_steps": 10,
  "total_timeout_ms": 120000
}`;

/**
 * @param {string} rawBaseUrl
 * @param {"ollama" | "openai"} provider
 */
function normalizeLlmBaseUrlInput(rawBaseUrl, provider) {
  let value = String(rawBaseUrl || "")
    .trim()
    .replace(/\/+$/, "");
  const lower = value.toLowerCase();
  if (provider === "openai") {
    if (lower.endsWith("/v1/chat/completions")) {
      value = value.slice(0, -"/v1/chat/completions".length);
    } else if (lower.endsWith("/chat/completions")) {
      value = value.slice(0, -"/chat/completions".length);
    } else if (lower.endsWith("/v1/models")) {
      value = value.slice(0, -"/v1/models".length);
    } else if (lower.endsWith("/v1")) {
      value = value.slice(0, -"/v1".length);
    }
  } else if (provider === "ollama") {
    if (lower.endsWith("/api/chat")) {
      value = value.slice(0, -"/api/chat".length);
    } else if (lower.endsWith("/api/tags")) {
      value = value.slice(0, -"/api/tags".length);
    } else if (lower.endsWith("/api")) {
      value = value.slice(0, -"/api".length);
    }
  }
  return value.replace(/\/+$/, "");
}

/**
 * @param {string} mode
 * @param {string} baseUrlInp
 * @param {string} apiKeyInp
 * @param {string} modelVal
 */
function buildLlmPayload(mode, baseUrlInp, apiKeyInp, modelVal) {
  const model = (modelVal || "").trim() || "gemma4:e4b";
  if (mode === "ollama-local") {
    return { provider: "ollama", base_url: "http://127.0.0.1:11434", model, api_key: "" };
  }
  if (mode === "ollama-remote") {
    const base = normalizeLlmBaseUrlInput(baseUrlInp, "ollama");
    return {
      provider: "ollama",
      base_url: base || "http://host.docker.internal:11434",
      model,
      api_key: (apiKeyInp || "").trim(),
    };
  }
  const openaiBase = normalizeLlmBaseUrlInput(baseUrlInp, "openai");
  return {
    provider: "openai",
    base_url: openaiBase || "https://api.openai.com/v1",
    model,
    api_key: (apiKeyInp || "").trim(),
  };
}

/**
 * @param {HTMLElement} container
 */
export async function init(container) {
  container.setAttribute("aria-busy", "false");
  container.classList.add("test-runner-root");

  const layout = el("div", "test-runner-layout");
  const left = el("div", "test-runner-left");
  const right = el("div", "test-runner-right");

  const llmCard = el("div", "test-runner-llm-card");
  const useRow = el("div", "test-runner-llm-use-row");
  const useCustomLlm = el("input", "test-runner-llm-check");
  useCustomLlm.type = "checkbox";
  const useLab = el("label", "test-runner-llm-check-label", "");
  useLab.appendChild(useCustomLlm);
  useLab.appendChild(
    document.createTextNode(
      " Własne połączenie LLM w czacie (Ollama / OpenAI-compatible; nadpisuje env / skrypt testowy)",
    ),
  );
  useRow.appendChild(useLab);
  llmCard.appendChild(el("h2", "test-runner-heading", "Połączenie z AI"));
  llmCard.appendChild(useRow);

  const provSelect = el("select", "test-runner-llm-provider");
  provSelect.innerHTML =
    '<option value="ollama-local">Ollama (127.0.0.1:11434)</option><option value="ollama-remote">Ollama (własny URL / host Docker)</option><option value="openai">OpenAI-compatible</option>';

  const fieldUrl = el("div", "test-runner-llm-field test-runner-llm-field-url");
  fieldUrl.appendChild(el("label", "", "Base URL"));
  const baseInp = el("input", "test-runner-llm-input");
  baseInp.type = "text";
  baseInp.placeholder = "np. http://host.docker.internal:11434";
  fieldUrl.appendChild(baseInp);

  const fieldKey = el("div", "test-runner-llm-field test-runner-llm-field-key");
  fieldKey.appendChild(el("label", "", "Klucz API"));
  const keyInp = el("input", "test-runner-llm-input");
  keyInp.type = "password";
  keyInp.autocomplete = "off";
  keyInp.placeholder = "opcjonalnie (Ollama) / wymagany u wielu dostawców OpenAI-compatible";
  fieldKey.appendChild(keyInp);

  const showAllRow = el("div", "test-runner-llm-showall");
  const showAllOpenai = el("input", "test-runner-llm-check");
  showAllOpenai.type = "checkbox";
  const showAllLab = el("label", "test-runner-llm-check-label", "");
  showAllLab.appendChild(showAllOpenai);
  showAllLab.appendChild(document.createTextNode(" Pokaż wszystkie modele (OpenAI-compatible)"));
  showAllRow.appendChild(showAllLab);

  const modelSelect = el("select", "test-runner-llm-model-select");
  const refreshModelsBtn = el("button", "secondary-btn", "Odśwież listę modeli");
  refreshModelsBtn.type = "button";
  const modelRow = el("div", "test-runner-llm-model-row");
  modelRow.appendChild(modelSelect);
  modelRow.appendChild(refreshModelsBtn);

  const fieldMode = el("div", "test-runner-llm-field");
  fieldMode.appendChild(el("label", "", "Tryb"));
  fieldMode.appendChild(provSelect);

  const fieldModel = el("div", "test-runner-llm-field");
  fieldModel.appendChild(el("label", "", "Model"));
  fieldModel.appendChild(modelRow);

  const syncRow = el("div", "test-runner-llm-sync-row");
  const syncBtn = el("button", "secondary-btn", "Zsynchronizuj z kontem podglądu");
  syncBtn.type = "button";
  syncBtn.title =
    "Zapisuje te ustawienia LLM w bazie dla player_id z ai_test_config.json (to samo konto, na które loguje się podgląd gry).";
  syncRow.appendChild(syncBtn);

  const llmHint = el("p", "test-runner-llm-hint");
  llmHint.textContent =
    "Zaznacz «Własne połączenie», wybierz tryb i model. W kontenerze Docker do Ollamy na hoście użyj trybu «własny URL»: http://host.docker.internal:11434. Ustawienia zapisują się lokalnie w przeglądarce (w tym klucz). Podgląd gry (iframe) korzysta z LLM zapisanych dla konta użytkownika (`/api/health?user_id=…`) — po zmianie powyżej kliknij «Zsynchronizuj…», żeby kropka LLM w podglądzie była spójna z planerem.";

  const llmFieldsInner = el("div", "test-runner-llm-fields-inner");
  llmFieldsInner.appendChild(fieldMode);
  llmFieldsInner.appendChild(fieldUrl);
  llmFieldsInner.appendChild(fieldKey);
  llmFieldsInner.appendChild(showAllRow);
  llmFieldsInner.appendChild(fieldModel);
  llmFieldsInner.appendChild(syncRow);
  llmFieldsInner.appendChild(llmHint);
  llmCard.appendChild(llmFieldsInner);

  function getCurrentModelValue() {
    return String(modelSelect.value || "").trim();
  }

  function updateLlmFieldsVisibility() {
    const on = useCustomLlm.checked;
    const mode = provSelect.value;
    llmFieldsInner.classList.toggle("test-runner-llm-inactive", !on);
    syncBtn.disabled = !on;
    if (!on) return;
    const showUrlKey = mode !== "ollama-local";
    fieldUrl.style.display = showUrlKey ? "" : "none";
    fieldKey.style.display = showUrlKey ? "" : "none";
    showAllRow.style.display = mode === "openai" ? "" : "none";
    if (mode === "ollama-remote") {
      baseInp.placeholder = "http://host:11434";
    } else if (mode === "openai") {
      baseInp.placeholder = "https://api.openai.com/v1 lub inny /v1";
    } else {
      baseInp.placeholder = "— tylko przy trybach z własnym URL —";
    }
  }

  function persistLlmToStorage() {
    try {
      localStorage.setItem(
        LLM_LS_KEY,
        JSON.stringify({
          useCustom: useCustomLlm.checked,
          mode: provSelect.value,
          base: baseInp.value,
          apiKey: keyInp.value,
          showAll: showAllOpenai.checked,
          model: getCurrentModelValue(),
        }),
      );
    } catch (_e) {
      /* ignore */
    }
  }

  function getLlmPayloadForRequest() {
    if (!useCustomLlm.checked) {
      return null;
    }
    return buildLlmPayload(provSelect.value, baseInp.value, keyInp.value, getCurrentModelValue());
  }

  /**
   * Payload dla planera kroków agenta (jak GM: zewn. API / ten sam host).
   * Bez api_key w body, jeśli pole puste → agent bierze LLM_API_KEY z env na serwerze.
   * @returns {{ provider: string, base_url: string, model: string, api_key?: string } | null}
   */
  function buildAgentPlannerLlBodyForApi() {
    if (!useCustomLlm.checked) return null;
    const pl = buildLlmPayload(provSelect.value, baseInp.value, keyInp.value, getCurrentModelValue());
    const body = {
      provider: pl.provider,
      base_url: pl.base_url,
      model: pl.model,
    };
    const keyTrim = String(keyInp.value || "").trim();
    if (keyTrim) {
      body.api_key = keyTrim;
    }
    return body;
  }

  function shortenUrlHint(u, max) {
    const m = max != null ? max : 96;
    const s = String(u || "");
    if (s.length <= m) return s;
    return `${s.slice(0, m)}…`;
  }

  /**
   * @param {boolean} [silent] — true: bez toastu przy sukcesie (np. start panelu)
   */
  async function loadLlmModelList(silent) {
    if (!useCustomLlm.checked) {
      return;
    }
    const pl = buildLlmPayload(provSelect.value, baseInp.value, keyInp.value, getCurrentModelValue());
    const prev = getCurrentModelValue();
    const savedModel = (() => {
      try {
        const s = JSON.parse(localStorage.getItem(LLM_LS_KEY) || "{}");
        return String(s.model || "").trim();
      } catch {
        return "";
      }
    })();
    const want = prev || savedModel;
    try {
      const data = await adminFetch("/api/test_runner/llm_models", {
        method: "POST",
        body: JSON.stringify({
          provider: pl.provider,
          base_url: pl.base_url,
          api_key: pl.api_key,
          show_all: provSelect.value === "openai" && showAllOpenai.checked,
        }),
      });
      const list = Array.isArray(data.models) ? data.models : [];
      const names = new Set();
      modelSelect.innerHTML = "";
      const addOpt = (name) => {
        const n = String(name || "").trim();
        if (!n || names.has(n)) {
          return;
        }
        names.add(n);
        const o = el("option", "", n);
        o.value = n;
        modelSelect.appendChild(o);
      };
      for (const m of list) {
        addOpt(m);
      }
      if (want && !names.has(want)) {
        addOpt(want);
      }
      if (!names.size) {
        addOpt(want || "gemma4:e4b");
      }
      if (want && names.has(want)) {
        modelSelect.value = want;
      } else if (modelSelect.options[0]) {
        modelSelect.value = modelSelect.options[0].value;
      }
      if (data && data.reachable === false && data.error) {
        showToast(String(data.error).slice(0, 200), "error");
      } else if (!silent) {
        showToast(
          `Modele: ${data.models?.length ?? 0} (${data.reachable ? "OK" : "niedostępny host"})`,
          data.reachable ? "success" : "error",
        );
      }
    } catch (e) {
      showToast(errText(e, e.message) || String(e), "error");
    }
    persistLlmToStorage();
  }

  function applyLlmFromStorage() {
    try {
      const s = JSON.parse(localStorage.getItem(LLM_LS_KEY) || "{}");
      if (typeof s.useCustom === "boolean") {
        useCustomLlm.checked = s.useCustom;
      }
      if (s.mode && ["ollama-local", "ollama-remote", "openai"].includes(s.mode)) {
        provSelect.value = s.mode;
      }
      if (typeof s.base === "string") {
        baseInp.value = s.base;
      }
      if (typeof s.apiKey === "string") {
        keyInp.value = s.apiKey;
      }
      if (typeof s.showAll === "boolean") {
        showAllOpenai.checked = s.showAll;
      }
    } catch (_e) {
      /* ignore */
    }
  }

  applyLlmFromStorage();
  updateLlmFieldsVisibility();

  useCustomLlm.addEventListener("change", () => {
    updateLlmFieldsVisibility();
    persistLlmToStorage();
    void loadLlmModelList(false);
  });
  provSelect.addEventListener("change", () => {
    updateLlmFieldsVisibility();
    persistLlmToStorage();
    void loadLlmModelList(false);
  });
  [baseInp, keyInp].forEach((inp) => {
    inp.addEventListener("input", () => {
      persistLlmToStorage();
    });
  });
  showAllOpenai.addEventListener("change", () => {
    persistLlmToStorage();
    void loadLlmModelList(false);
  });
  modelSelect.addEventListener("change", () => {
    persistLlmToStorage();
  });

  async function syncLlmToPreviewUser() {
    if (!useCustomLlm.checked) {
      showToast("Włącz «Własne połączenie LLM» i uzupełnij pola, potem zsynchronizuj.", "error");
      return;
    }
    let cfg;
    try {
      cfg = await adminFetch("/api/test_runner/ai_test_config");
    } catch (e) {
      if (e instanceof APIError && e.status === 404) {
        showToast(
          "Brak pliku ai_test_config (seed środowiska). W Dockerze: volumen /data lub ustaw AI_TEST_CONFIG_PATH.",
          "error",
        );
      } else {
        showToast(errText(e, e.message) || String(e), "error");
      }
      return;
    }
    const uid = Number(cfg.player_id);
    if (!Number.isFinite(uid) || uid < 1) {
      showToast("ai_test_config: nieprawidłowe player_id.", "error");
      return;
    }
    const pl = buildLlmPayload(provSelect.value, baseInp.value, keyInp.value, getCurrentModelValue());
    const keyTrim = String(keyInp.value || "").trim();
    try {
      await adminFetch(`/api/admin/users/${encodeURIComponent(String(uid))}/llm-settings`, {
        method: "PUT",
        body: JSON.stringify({
          provider: pl.provider,
          base_url: pl.base_url,
          model: pl.model,
          api_key: keyTrim || null,
        }),
      });
    } catch (e) {
      showToast(errText(e, e.message) || String(e), "error");
      return;
    }
    const name = cfg.player_username ? ` (${cfg.player_username})` : "";
    showToast(
      `Zsynchronizowano LLM z kontem użytkownika ${uid}${name}. Podgląd: odśwież stronę w iframe lub poczekaj na health (poll).`,
      "success",
    );
  }

  syncBtn.addEventListener("click", () => {
    void syncLlmToPreviewUser();
  });

  refreshModelsBtn.addEventListener("click", () => {
    void loadLlmModelList(false);
  });

  const chatLog = el("div", "test-runner-chat-log");
  const chatForm = el("form", "test-runner-chat-form");
  const chatInput = el("textarea", "test-runner-chat-input");
  chatInput.rows = 3;
  chatInput.placeholder = "Opisz test (persona, cel, oczekiwany wynik)…";
  const chatSend = el("button", "primary-btn", "Wyślij");
  chatSend.type = "submit";
  chatForm.appendChild(chatInput);
  chatForm.appendChild(chatSend);
  left.appendChild(llmCard);
  left.appendChild(el("h2", "test-runner-heading", "Czat z AI (plan scenariusza)"));
  left.appendChild(chatLog);
  left.appendChild(chatForm);

  const agentRow = el("div", "test-runner-agent-row");
  const agentLinesWrap = el("div", "test-runner-agent-lines");
  const agentStatusNode = el("p", "test-runner-agent-hint test-runner-agent-line", "Agent (Node / Playwright): …");
  const agentStatusPlanner = el(
    "p",
    "test-runner-agent-hint test-runner-agent-line test-runner-planer-line",
    "Planer LLM agenta: —",
  );
  const agentRefreshBtn = el("button", "secondary-btn", "Sprawdź agenta");
  agentRefreshBtn.type = "button";
  agentRefreshBtn.title =
    "Node (GET /agent/scenarios) oraz reachability planera (GET /api/tags Ollamy lub /v1/models OpenAI). Zaznacz «Własne połączenie LLM», żeby sprawdzić ten sam URL co dla GM.";
  agentLinesWrap.appendChild(agentStatusNode);
  agentLinesWrap.appendChild(agentStatusPlanner);
  agentRow.appendChild(agentLinesWrap);
  agentRow.appendChild(agentRefreshBtn);

  const yamlLabel = el("h2", "test-runner-heading", "Scenariusz (JSON / YAML) — edycja przed startem");
  const yamlTa = el("textarea", "test-runner-yaml");
  yamlTa.value = DEFAULT_YAML;
  const actions = el("div", "test-runner-actions");
  const runBtn = el("button", "primary-btn", "Uruchom ▶");
  const stopBtn = el("button", "danger-btn", "Zatrzymaj ⏹");
  stopBtn.disabled = true;
  stopBtn.title = "Zatrzymaj aktualnie działający test";
  const saveBtn = el("button", "secondary-btn", "Zapisz");
  const filenameInp = el("input", "test-runner-filename");
  filenameInp.type = "text";
  filenameInp.placeholder = "nazwa_pliku.json";
  const scenarioSelect = el("select", "test-runner-scenario-select");
  const refreshListBtn = el("button", "secondary-btn", "Odśwież listę");
  actions.appendChild(runBtn);
  actions.appendChild(stopBtn);
  actions.appendChild(saveBtn);
  actions.appendChild(filenameInp);
  actions.appendChild(scenarioSelect);
  actions.appendChild(refreshListBtn);

  const shotWrap = el("div", "test-runner-screenshot-wrap");
  const shot = el("img", "test-runner-screenshot");
  shot.alt = "Podgląd przeglądarki testu";
  shot.setAttribute("width", "100%");
  const shotStatus = el("p", "test-runner-shot-status", "—");
  shotWrap.appendChild(shot);
  shotWrap.appendChild(shotStatus);

  const stepLog = el("div", "test-runner-step-log");
  const runMeta = el("p", "test-runner-run-meta", "Status: —");

  right.appendChild(agentRow);
  right.appendChild(yamlLabel);
  right.appendChild(yamlTa);
  right.appendChild(actions);
  right.appendChild(el("h2", "test-runner-heading", "Podgląd (ok. 1,5 s)"));
  right.appendChild(shotWrap);
  right.appendChild(el("h2", "test-runner-heading", "Dziennik kroków (SSE)"));
  right.appendChild(runMeta);
  right.appendChild(stepLog);

  layout.appendChild(left);
  layout.appendChild(right);
  container.appendChild(layout);

  /** @type {Array<{role: string, content: string}>} */
  let planningHistory = [];
  let pollTimer = null;
  let runEs = null;
  let currentRunId = null;
  let shotPopupTimer = null;

  // Popup powiększenia obrazu z auto-odświeżaniem.
  const shotPopup = el("div", "test-runner-shot-popup");
  shotPopup.setAttribute("role", "dialog");
  shotPopup.setAttribute("aria-modal", "true");
  shotPopup.style.display = "none";
  const shotPopupInner = el("div", "test-runner-shot-popup-inner");
  const shotPopupHeader = el("div", "test-runner-shot-popup-header");
  const shotPopupTitle = el("div", "test-runner-shot-popup-title", "Podgląd (powiększenie)");
  const shotPopupClose = el("button", "test-runner-shot-popup-close", "Zamknij");
  shotPopupClose.type = "button";
  shotPopupHeader.appendChild(shotPopupTitle);
  shotPopupHeader.appendChild(shotPopupClose);
  const shotPopupImg = el("img", "test-runner-shot-popup-img");
  shotPopupImg.alt = "Podgląd powiększony";
  shotPopupInner.appendChild(shotPopupHeader);
  shotPopupInner.appendChild(shotPopupImg);
  shotPopup.appendChild(shotPopupInner);
  document.body.appendChild(shotPopup);

  function hideShotPopup() {
    shotPopup.style.display = "none";
    if (shotPopupTimer) {
      clearInterval(shotPopupTimer);
      shotPopupTimer = null;
    }
  }

  async function refreshShotPopupOnce() {
    if (!currentRunId) return;
    try {
      const sh = await adminFetch(`/api/test_runner/screenshot/${currentRunId}`);
      if (sh && sh.base64) {
        shotPopupImg.src = `data:image/jpeg;base64,${sh.base64}`;
      }
    } catch (_e) {
      /* ignore */
    }
  }

  function showShotPopup() {
    if (!currentRunId) {
      showToast("Najpierw uruchom test, potem kliknij podgląd obrazu.", "error");
      return;
    }
    shotPopup.style.display = "";
    void refreshShotPopupOnce();
    if (shotPopupTimer) clearInterval(shotPopupTimer);
    shotPopupTimer = setInterval(() => {
      void refreshShotPopupOnce();
    }, 1200);
  }

  shot.addEventListener("click", () => showShotPopup());
  shotPopupClose.addEventListener("click", () => hideShotPopup());
  shotPopup.addEventListener("click", (e) => {
    if (e.target === shotPopup) hideShotPopup();
  });

  function setRunningState(isRunning, runId = null) {
    currentRunId = runId;
    runBtn.disabled = isRunning;
    stopBtn.disabled = !isRunning;
    container.setAttribute("aria-busy", String(isRunning));
    if (isRunning) {
      runMeta.textContent = `Status: STARTING… (run_id: ${runId || "?"})`;
    }
  }

  function clearTimers() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    if (runEs) {
      try {
        runEs.close();
      } catch (_e) {
        /* ignore */
      }
      runEs = null;
    }
  }

  async function stopRunningTest() {
    if (!currentRunId) {
      showToast("Brak aktywnego testu do zatrzymania", "error");
      return;
    }
    try {
      stopBtn.disabled = true;
      appendLogLine("Wysyłanie sygnału zatrzymania…", "info");
      const result = await adminFetch(`/api/test_runner/stop/${encodeURIComponent(currentRunId)}`, {
        method: "POST",
      });
      appendLogLine(`Zatrzymano: ${result.message || "ok"}`, "ok");
      showToast(`Test zatrzymany: ${result.message || "ok"}`, "success");
    } catch (e) {
      stopBtn.disabled = false;
      const msg = errText(e, e.message) || String(e);
      appendLogLine(`Błąd zatrzymania: ${msg}`, "err");
      showToast(`Błąd zatrzymania: ${msg}`, "error");
    }
  }

  function appendLogLine(msg, kind = "info") {
    const line = el("div", `test-runner-log-line test-runner-log-${kind}`);
    line.textContent = msg;
    stepLog.appendChild(line);
    stepLog.scrollTop = stepLog.scrollHeight;
  }

  function resetStepLog() {
    stepLog.innerHTML = "";
  }

  async function refreshAgentHealth() {
    agentStatusNode.classList.remove("test-runner-agent-ok", "test-runner-agent-err");
    agentStatusPlanner.classList.remove("test-runner-agent-ok", "test-runner-agent-err");
    agentStatusNode.textContent = "Agent (Node / Playwright): sprawdzam…";
    agentStatusPlanner.textContent = "Planer LLM agenta: …";
    try {
      const h = await adminFetch("/api/test_runner/agent_health");
      if (!(h && h.reachable)) {
        agentStatusNode.classList.add("test-runner-agent-err");
        agentStatusNode.textContent = `Agent (Node): NIEDOSTĘPNY — ${String(h && h.error ? h.error : "unknown").slice(0, 360)}`;
        agentStatusPlanner.textContent =
          "Planer LLM: — (najpierw musi działać proces agenta AI_TEST_AGENT_URL → test-agent:4000)";
        agentStatusPlanner.classList.add("test-runner-agent-err");
        return h;
      }
      agentStatusNode.classList.add("test-runner-agent-ok");
      const n = h.scenario_count != null ? `, scenariusze: ${h.scenario_count}` : "";
      agentStatusNode.textContent = `Agent (Node): OK (${h.agent_url || "?"})${n}`;

      const pingBody = { agent_planner_llm: buildAgentPlannerLlBodyForApi() };
      let ping;
      try {
        ping = await adminFetch("/api/test_runner/agent_planner_ping", {
          method: "POST",
          body: JSON.stringify(pingBody),
        });
      } catch (pe) {
        agentStatusPlanner.classList.add("test-runner-agent-err");
        agentStatusPlanner.textContent = `Planer LLM: brak endpointu (zaktualizuj agenta) — ${errText(pe, pe.message)}`;
        return { ...h, planner: { reachable: false, error: String(pe) } };
      }
      const p = ping && ping.planner;
      if (p && p.reachable) {
        agentStatusPlanner.classList.add("test-runner-agent-ok");
        const hint = p.api_url_hint ? shortenUrlHint(p.api_url_hint) : "";
        agentStatusPlanner.textContent = hint
          ? `Planer LLM: OK — ${hint}`
          : "Planer LLM: OK (probe /api/tags lub /v1/models)";
      } else {
        agentStatusPlanner.classList.add("test-runner-agent-err");
        const detail = (p && p.error) || (ping && ping.error) || "unknown";
        agentStatusPlanner.textContent = `Planer LLM: BŁĄD — ${String(detail).slice(0, 420)} (sprawdź URL/klucz lub env LLM_* w kontenerze test-agent)`;
      }
      return { ...h, planner: p, planner_ping: ping };
    } catch (e) {
      agentStatusNode.classList.add("test-runner-agent-err");
      agentStatusPlanner.classList.add("test-runner-agent-err");
      agentStatusPlanner.textContent = "Planer LLM: —";
      if (e instanceof APIError && e.status === 404) {
        agentStatusNode.textContent =
          "Agent: brak /agent_health w backendzie (zaktualizuj). Przed ▶ uruchom ai_test_agent (port 4000).";
        return { skipHealth: true };
      }
      agentStatusNode.textContent = `Agent: błąd — ${errText(e, e.message) || e.message || String(e)}`;
      return { reachable: false, error: agentStatusNode.textContent };
    }
  }

  agentRefreshBtn.addEventListener("click", () => {
    void refreshAgentHealth();
  });

  chatForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const text = chatInput.value.trim();
    if (!text) {
      showToast("Wpisz treść wiadomości.", "error");
      return;
    }
    const userLine = el("div", "test-runner-chat-bubble test-runner-chat-user");
    userLine.textContent = text;
    chatLog.appendChild(userLine);
    chatInput.value = "";
    try {
      const payload = { message: text, history: planningHistory };
      const llm = getLlmPayloadForRequest();
      if (llm) {
        payload.llm = llm;
      }
      const data = await adminFetch("/api/test_runner/generate_scenario", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      planningHistory.push({ role: "user", content: text });
      const reply = String(data.reply || "");
      const aiLine = el("div", "test-runner-chat-bubble test-runner-chat-ai");
      aiLine.textContent = reply;
      chatLog.appendChild(aiLine);
      planningHistory.push({ role: "assistant", content: reply });
      chatLog.scrollTop = chatLog.scrollHeight;
      if (data.yaml) {
        yamlTa.value = String(data.yaml);
        if (data.ready) {
          showToast("Scenariusz uznany za gotowy (ready).", "success");
        }
      }
    } catch (e) {
      if (e instanceof APIError && e.status === 404) {
        showToast(
          "Test Runner (404): /api/test_runner niedostępny. Zrestartuj backend z AI_TEST_MODE=1 (w Docker: docker compose -f docker-compose.dev.yml up -d --build backend; plik env.test musi być w /app/env.test w kontenerze lub w zmiennej środowiskowej).",
          "error",
        );
        return;
      }
      if (e instanceof APIError && e.status === 401) {
        showToast("Brak uprawnień (401) — w panelu kliknij Connect / Dev login (token admin).", "error");
        return;
      }
      showToast(errText(e, e.message) || e.message, "error");
    }
  });

  async function loadScenarioList() {
    try {
      const data = await adminFetch("/api/test_runner/scenarios");
      const list = data.scenarios || [];
      scenarioSelect.innerHTML = "";
      const opt0 = el("option", "", "— wybierz plik —");
      opt0.value = "";
      scenarioSelect.appendChild(opt0);
      list.forEach((name) => {
        const o = el("option", "", name);
        o.value = name;
        scenarioSelect.appendChild(o);
      });
    } catch (e) {
      if (e instanceof APIError && e.status === 404) {
        showToast(
          "Test Runner (404). Backend bez montowanego /api/test_runner. Docker: wykonaj `docker compose -f docker-compose.dev.yml up -d --build backend` (env.test -> /app/env.test; AI_TEST_MODE=1 w compose). Bez Docker: export AI_TEST_MODE=1 i zrestartuj uvicorn.",
          "error",
        );
        return;
      }
      if (e instanceof APIError && e.status === 401) {
        showToast("Brak uprawnień (401) — w panelu zaloguj się (Connect / token).", "error");
        return;
      }
      showToast(errText(e, e.message), "error");
    }
  }

  scenarioSelect.addEventListener("change", async () => {
    const name = scenarioSelect.value;
    if (!name) return;
    try {
      const data = await adminFetch(`/api/test_runner/scenario/${encodeURIComponent(name)}`);
      if (data && data.content) {
        yamlTa.value = data.content;
        showToast(`Wczytano: ${name}`, "success");
      }
    } catch (e) {
      showToast(errText(e, e.message), "error");
    }
  });

  refreshListBtn.addEventListener("click", () => {
    void loadScenarioList();
  });

  runBtn.addEventListener("click", async () => {
    clearTimers();
    resetStepLog();
    const yaml = yamlTa.value;
    if (!yaml.trim()) {
      showToast("Pusty scenariusz.", "error");
      return;
    }
    const ah = await refreshAgentHealth();
    if (ah && !ah.skipHealth && ah.reachable === false) {
      runMeta.textContent = "Status: —";
      const msg = String(ah.error || "").trim() || "Uruchom na hoście: cd ai_test_agent && npm run agent:server (port 4000).";
      showToast(msg.slice(0, 500), "error");
      appendLogLine(
        "KONIEC: agent testowy niedostępny. Docker: `docker compose -f docker-compose.dev.yml up -d --build test-agent`. Planer LLM: env LLM_API_URL/LLM_API_KEY w test-agent albo «Własne połączenie LLM» w panelu (jak dla GM).",
        "err",
      );
      return;
    }
    setRunningState(true);
    try {
      const startBody = { yaml };
      const apl = buildAgentPlannerLlBodyForApi();
      if (apl) {
        startBody.agent_planner_llm = apl;
      }
      const { run_id: runId } = await adminFetch("/api/test_runner/start", {
        method: "POST",
        body: JSON.stringify(startBody),
      });
      setRunningState(true, runId);
      appendLogLine(`Uruchomiono agenta… run_id: ${runId}`, "info");

      const root = normApiRoot();
      const tok = encodeURIComponent(getToken() || "");
      const streamUrl = `${root}/api/test_runner/stream/${runId}?token=${tok}`;
      const es = new EventSource(streamUrl);
      runEs = es;
      es.onmessage = (event) => {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }
        if (data.done) {
          setRunningState(false);
          const fail = data.error || data.reason === "error" || data.success === false;
          if (data.reason === "cancelled") {
            appendLogLine("KONIEC: zatrzymano przez użytkownika", "info");
            runMeta.textContent = "Status: CANCELLED";
          } else if (fail) {
            appendLogLine(`KONIEC: błąd  ${data.error || data.reason || ""}`, "err");
            runMeta.textContent = "Status: ERROR (SSE)";
          } else {
            const ok = data.success === true;
            appendLogLine(
              `KONIEC: ${ok ? "PASS" : "FAIL"}  steps=${data.steps != null ? data.steps : "?"}`,
              ok ? "ok" : "err",
            );
            runMeta.textContent = `Status: DONE  |  success=${String(data.success === true)}`;
          }
          if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
          }
          try {
            es.close();
          } catch (_e) {
            /* ignore */
          }
          hideShotPopup();
          return;
        }
        const s = data.step != null ? `Krok ${data.step}` : "Krok ?";
        const a = data.action && data.action.type ? data.action.type : "—";
        appendLogLine(`${s}: ${a}`, "step");
        runMeta.textContent = `Status: RUNNING  |  ostatni krok: ${data.step != null ? data.step : "?"}`;
      };
      es.onerror = () => {
        appendLogLine("EventSource: połączenie przerwane lub błąd (sprawdź token / backend).", "err");
        hideShotPopup();
      };

      pollTimer = setInterval(async () => {
        try {
          const st = await adminFetch(`/api/test_runner/status/${runId}`);
          if (st.status !== "RUNNING" && pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
          }
        } catch {
          /* ignore */
        }
        try {
          const sh = await adminFetch(`/api/test_runner/screenshot/${runId}`);
          if (sh && sh.base64) {
            shot.src = `data:image/jpeg;base64,${sh.base64}`;
            shotStatus.textContent = "Ostatnia klatka: OK";
          }
        } catch (e) {
          if (e instanceof APIError && (e.status === 404 || e.status === 502)) {
            shotStatus.textContent = "Brak klatki (brak aktywnej sesji albo agent nie odpowiada)";
          }
        }
      }, 1500);
    } catch (e) {
      setRunningState(false);
      runMeta.textContent = "Status: —";
      showToast(errText(e, e.message), "error");
    }
  });

  stopBtn.addEventListener("click", () => {
    void stopRunningTest();
  });

  saveBtn.addEventListener("click", async () => {
    let name = filenameInp.value.trim() || "custom_scenario.json";
    if (!name.endsWith(".json")) {
      name += ".json";
    }
    const content = yamlTa.value;
    if (!content.trim()) {
      showToast("Pusty scenariusz.", "error");
      return;
    }
    try {
      const r = await adminFetch("/api/test_runner/save_scenario", {
        method: "POST",
        body: JSON.stringify({ filename: name, content }),
      });
      showToast("Zapisano: " + (r.path || name), "success");
      void loadScenarioList();
    } catch (e) {
      showToast(errText(e, e.message), "error");
    }
  });

  await loadScenarioList();

  if (useCustomLlm.checked) {
    void loadLlmModelList(true);
  } else {
    const o = el("option", "", "gemma4:e4b");
    o.value = "gemma4:e4b";
    modelSelect.appendChild(o);
  }

  void refreshAgentHealth();
}
