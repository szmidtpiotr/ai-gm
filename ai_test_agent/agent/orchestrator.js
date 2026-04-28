const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");
const { buildSnapshot } = require("./snapshot");
const { LLMClient } = require("./llm_client");
const { validate } = require("./action_validator");
const { execute } = require("./action_executor");
const { DEFAULTS } = require("./models");
const { validateScenario } = require("./scenario_validator");
const { SELECTORS } = require("./ui_actions");
const { loadConfig, resetTestEnv, getPlayerState } = require("../playwright/helpers/game_state");
const { login } = require("../playwright/helpers/auth");

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

/**
 * UI ładuje tytuły z API; opcja może być "Tytuł" albo "Tytuł (brak bohatera)" — dokładne label
 * często nie pasuje. Preferujemy value = campaign_id z cfg JSON lub scenariusza.
 * @param {import('playwright').Page} page
 * @param {object} scenario
 * @param {object} cfg
 */
async function selectCampaignForTest(page, scenario, cfg) {
  const wantLabel = (scenario.campaign_label || "AI Test Campaign").trim();
  const idRaw =
    scenario.campaign_id != null && scenario.campaign_id !== ""
      ? scenario.campaign_id
      : cfg.campaign_id != null && cfg.campaign_id !== ""
        ? cfg.campaign_id
        : null;
  const wantId = idRaw == null ? null : String(idRaw);

  await page.waitForSelector("#campaign-select", { state: "visible", timeout: 20_000 });
  await page.waitForFunction(
    () => {
      const sel = document.getElementById("campaign-select");
      if (!sel) return false;
      if (sel.disabled) return false;
      return sel.options && sel.options.length > 0;
    },
    null,
    { timeout: 45_000 }
  );

  if (wantId) {
    const exists = await page.evaluate((id) => {
      const sel = document.getElementById("campaign-select");
      if (!sel || !sel.options) return false;
      return Array.from(sel.options).some((o) => String(o.value) === String(id));
    }, wantId);
    if (exists) {
      await page.selectOption("#campaign-select", { value: wantId });
      return;
    }
  }

  const esc = wantLabel.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  try {
    await page.selectOption("#campaign-select", { label: new RegExp(`^${esc}`) });
  } catch (e) {
    await page.selectOption("#campaign-select", { label: wantLabel });
  }
}

function logStructured(level, event, data = {}) {
  const ts = new Date().toISOString();
  const logEntry = {
    ts,
    level,
    service: "test-orchestrator",
    event,
    ...data,
  };
  console.log(JSON.stringify(logEntry));
}

/**
 * @param {object} scenario
 * @param {object} [options]
 * @param {boolean} [options.headed]
 * @param {function} [options.onStep]
 * @param {{ page: import('playwright').Page | null }} [options.sessionRef] module-level ref for live screenshots
 * @param {function} [options.isCancelled] funkcja zwracająca true jeśli test ma być zatrzymany
 */
async function run(scenario, options = {}) {
  const {
    headed = false,
    onStep = null,
    sessionRef = null,
    plannerLlm = null,
    isCancelled = () => false,
  } = options;
  const scenarioErrors = validateScenario(scenario);
  if (scenarioErrors.length) {
    throw new Error(`Nieprawidłowy scenariusz: ${scenarioErrors.join("; ")}`);
  }
  const cfg = loadConfig();
  const backendUrl = process.env.BACKEND_URL || "http://192.168.1.61:8100";
  const baseUrl = process.env.BASE_URL || "http://192.168.1.61:3002";
  const maxSteps = scenario.max_steps || DEFAULTS.MAX_STEPS;
  const totalTimeoutMs = scenario.total_timeout_ms || DEFAULTS.TOTAL_TIMEOUT_MS;
  const startMs = Date.now();
  const scenarioName = scenario.name || "unnamed";

  logStructured("info", "run_init", { scenario_name: scenarioName, max_steps: maxSteps, total_timeout_ms: totalTimeoutMs });

  process.env.BACKEND_URL = backendUrl;

  await resetTestEnv();

  const videoDir = path.resolve(__dirname, "../playwright-results/videos");
  ensureDir(videoDir);

  const browser = await chromium.launch({ headless: !headed });
  const context = await browser.newContext({
    recordVideo: { dir: videoDir },
  });
  const page = await context.newPage();
  if (sessionRef) {
    sessionRef.page = page;
  }

  let result = { success: false, reason: "max_steps_reached", steps: 0, exploit_found: false };
  let terminal = false;
  // Musi być zainicjalizowane zanim wejdziemy w try/finally,
  // bo przy błędach wcześnie w logu dostajemy "step is not defined".
  let step = 0;

  try {
    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await login(page);

    await selectCampaignForTest(page, scenario, cfg);
    const createName = page.locator("#character-create-name");
    if (await createName.isVisible().catch(() => false)) {
      await createName.fill("TestPlayer");
      await page.click("#character-create-submit");
    }
    await page.waitForSelector(SELECTORS.chatInput, { timeout: 20_000 });
    await page.waitForFunction(
      (sel) => {
        const b = document.querySelector(sel);
        return b && !b.disabled;
      },
      SELECTORS.sendBtn,
      { timeout: 30_000 }
    );

    const llm = new LLMClient(scenario, plannerLlm);
    const history = [];
    const actionHistory = [];

    logStructured("info", "run_login_complete", { campaign_id: cfg.campaign_id, character_id: cfg.character_id });

    while (step < maxSteps) {
      // Sprawdź czy test nie został anulowany
      if (isCancelled()) {
        logStructured("info", "run_cancelled_by_user", { step });
        result = { success: false, reason: "cancelled", steps: step, exploit_found: false };
        terminal = true;
        break;
      }

      if (Date.now() - startMs > totalTimeoutMs) {
        logStructured("warn", "run_timeout", { step, elapsed_ms: Date.now() - startMs });
        result = { success: false, reason: "total_timeout", steps: step, exploit_found: false };
        terminal = true;
        break;
      }

      const snapshot = await buildSnapshot(
        page,
        scenario,
        cfg.character_id,
        cfg.campaign_id,
        step,
        backendUrl
      );
      logStructured("debug", "step_snapshot", { step, gm_response_length: snapshot.gm_response?.length || 0 });

      if (isCancelled()) {
        logStructured("info", "run_cancelled_before_llm", { step });
        result = { success: false, reason: "cancelled", steps: step, exploit_found: false };
        terminal = true;
        break;
      }

      let raw;
      try {
        raw = await llm.decide(snapshot, history);
      } catch (e) {
        logStructured("error", "llm_decide_failed", { step, error: e && e.message ? e.message : String(e) });
        throw e;
      }
      logStructured("debug", "llm_decide_complete", { step, response_length: raw?.length || 0 });

      // validate() potrzebuje długości historii rozmowy (a nie samej listy typów akcji),
      // bo logika "pierwszy krok" ma wymusić wysłanie wiadomości zamiast czekania na GM.
      const action = validate(raw, history);
      logStructured("info", "step_action", { step, action_type: action.type, reasoning: action.reasoning?.slice(0, 100) });

      await page.evaluate(
        ({ s, a }) => {
          if (window.AITestOTel && typeof window.AITestOTel.logAction === "function") {
            window.AITestOTel.logAction(a.type, {
              step: s,
              reasoning: a.reasoning,
              params: JSON.stringify(a.params || {}),
            });
          }
        },
        { s: step, a: action }
      );

      if (onStep) {
        onStep({
          step,
          snapshot,
          action,
          timestamp: new Date().toISOString(),
        });
      }

      await execute(action, page);
      history.push({ snapshot, action });
      actionHistory.push({
        type: action.type,
        params: action.params,
        reasoning: action.reasoning,
      });

      if (action.type === "finish") {
        logStructured("info", "run_finished", { step, success: !!action.params?.success, reason: action.params?.reason });
        result = {
          success: !!action.params?.success,
          reason: String(action.params?.reason || "finished"),
          steps: step + 1,
          exploit_found: false,
        };
        terminal = true;
        break;
      }

      if (step > 0 && step % 5 === 0 && scenario.success_criteria) {
        const state = await getPlayerState(cfg.character_id);
        const c = scenario.success_criteria;
        const locationMatch =
          !c.location_changed_to || String(state.location || "") === c.location_changed_to;
        const questOk =
          c.quest_completed === false
            ? !(state.quests_completed || []).includes("EscapeDungeon")
            : true;
        logStructured("debug", "criteria_check", { step, location_match: locationMatch, quest_ok: questOk });
        if (locationMatch && questOk && c.location_changed_to) {
          logStructured("info", "criteria_met", { step, location: state.location });
          result = {
            success: true,
            reason: "criteria_met",
            steps: step + 1,
            exploit_found: true,
          };
          terminal = true;
          break;
        }
      }

      step += 1;
    }

    if (!terminal) {
      logStructured("info", "run_max_steps_reached", { steps: step });
      result = { success: false, reason: "max_steps_reached", steps, exploit_found: false };
    }
  } catch (err) {
    logStructured("error", "run_exception", { error: err && err.message ? err.message : String(err), step });
    throw err;
  } finally {
    // safeStep: unikamy crasha przy błędach we wczesnej inicjalizacji
    const safeStep = typeof step === "number" ? step : 0;
    logStructured("info", "run_cleanup", { duration_ms: Date.now() - startMs, final_step: safeStep });
    if (sessionRef) {
      sessionRef.page = null;
    }
    try { await context.close(); } catch (e) { /* ignore */ }
    try { await browser.close(); } catch (e) { /* ignore */ }
  }

  logStructured("info", "run_returning", { success: result.success, reason: result.reason, steps: result.steps });
  return result;
}

module.exports = { run };
