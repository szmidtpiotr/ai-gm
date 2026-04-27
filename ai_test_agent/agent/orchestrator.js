const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");
const { buildSnapshot } = require("./snapshot");
const { LLMClient } = require("./llm_client");
const { validate } = require("./action_validator");
const { execute } = require("./action_executor");
const { DEFAULTS } = require("./models");
const { loadConfig, resetTestEnv, getPlayerState } = require("../playwright/helpers/game_state");
const { login } = require("../playwright/helpers/auth");

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

/**
 * @param {object} scenario
 * @param {object} [options]
 * @param {boolean} [options.headed]
 * @param {function} [options.onStep]
 */
async function run(scenario, options = {}) {
  const { headed = false, onStep = null } = options;
  const cfg = loadConfig();
  const backendUrl = process.env.BACKEND_URL || "http://192.168.1.61:8100";
  const baseUrl = process.env.BASE_URL || "http://192.168.1.61:3002";
  const maxSteps = scenario.max_steps || DEFAULTS.MAX_STEPS;
  const totalTimeoutMs = scenario.total_timeout_ms || DEFAULTS.TOTAL_TIMEOUT_MS;
  const startMs = Date.now();

  process.env.BACKEND_URL = backendUrl;

  await resetTestEnv();

  const videoDir = path.resolve(__dirname, "../playwright-results/videos");
  ensureDir(videoDir);

  const browser = await chromium.launch({ headless: !headed });
  const context = await browser.newContext({
    recordVideo: { dir: videoDir },
  });
  const page = await context.newPage();

  let result = { success: false, reason: "max_steps_reached", steps: 0, exploit_found: false };
  let terminal = false;

  try {
    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await login(page);

    const label = (scenario.campaign_label || "AI Test Campaign").trim();
    await page.waitForSelector("#campaign-select", { state: "visible", timeout: 15_000 });
    await page.selectOption("#campaign-select", { label });
    const createName = page.locator("#character-create-name");
    if (await createName.isVisible().catch(() => false)) {
      await createName.fill("TestPlayer");
      await page.click("#character-create-submit");
    }
    await page.waitForSelector("textarea#input", { timeout: 20_000 });
    await page.waitForFunction(
      () => {
        const b = document.querySelector("#send-btn");
        return b && !b.disabled;
      },
      null,
      { timeout: 30_000 }
    );

    const llm = new LLMClient(scenario);
    const history = [];
    const actionHistory = [];
    let step = 0;

    while (step < maxSteps) {
      if (Date.now() - startMs > totalTimeoutMs) {
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
      const raw = await llm.decide(snapshot, history);
      const action = validate(raw, actionHistory);

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
        if (locationMatch && questOk && c.location_changed_to) {
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
      result = { success: false, reason: "max_steps_reached", steps, exploit_found: false };
    }
  } finally {
    await context.close();
    await browser.close();
  }

  return result;
}

module.exports = { run };
