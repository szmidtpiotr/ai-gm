const fs = require("fs");
const path = require("path");

function loadConfig() {
  const candidates = [
    process.env.AI_TEST_CONFIG_PATH && path.resolve(process.env.AI_TEST_CONFIG_PATH),
    path.resolve(__dirname, "../../../data-dev/ai_test_config.json"),
    path.resolve(__dirname, "../../../backend/ai_test_config.json"),
  ].filter(Boolean);
  const cfgPath = candidates.find((p) => fs.existsSync(p)) || candidates[0];
  // eslint-disable-next-line global-require, import/no-dynamic-require
  return require(cfgPath);
}

const _delay = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Kampania (#campaign-select) siedzi w #llm-controls-body, ukrywanym przez CSS gdy .llm-controls--collapsed.
 * Po logowaniu bootstrap() leci asynchronicznie — jednorazowy klik mógł być za wcześnie lub dublować się z syncLlmControlsCollapse.
 * Klikamy Settings tylko gdy widać klasę collapsed (unikamy podwójnego kliku = ponowne zwinięcie).
 */
async function ensureCampaignControlsVisible(page) {
  const toggle = page.locator("#llm-settings-toggle-btn");
  await toggle.waitFor({ state: "visible", timeout: 15000 });
  const deadline = Date.now() + 25000;
  while (Date.now() < deadline) {
    const { ready, collapsed } = await page.evaluate(() => {
      const root = document.getElementById("llm-controls");
      const body = document.getElementById("llm-controls-body");
      if (!root || !body) return { ready: false, collapsed: null };
      const bodyStyle = window.getComputedStyle(body);
      const visible = bodyStyle.display !== "none" && bodyStyle.visibility !== "hidden";
      return {
        ready: visible,
        collapsed: root.classList.contains("llm-controls--collapsed"),
      };
    });
    if (ready) break;
    if (collapsed === true) {
      await toggle.click();
      await _delay(400);
    } else {
      await _delay(250);
    }
  }
  const stillHidden = await page.evaluate(() => {
    const body = document.getElementById("llm-controls-body");
    return !body || window.getComputedStyle(body).display === "none";
  });
  if (stillHidden) {
    throw new Error("llm-controls-body pozostał ukryty (panel LLM / Settings).");
  }
  await page.waitForSelector("#campaign-select", { state: "visible", timeout: 20000 });
}

async function login(page) {
  const cfg = loadConfig();
  const username = cfg.player_username || "ai_test_player";
  await page.fill("#player-username", username);
  // Must match seed script `DEFAULT_PASSWORD_HASH` (see backend/scripts/seed_ai_test_env.py).
  await page.fill("#player-password", process.env.AI_TEST_PLAYER_PASSWORD || "demo");
  await page.click("#player-login-btn");
  await page.waitForFunction(
    () => document.getElementById("auth-overlay")?.getAttribute("aria-hidden") === "true",
    null,
    { timeout: 20000 }
  );
  await page.locator("#game-app").waitFor({ state: "visible", timeout: 10000 });
  await page.waitForFunction(
    () => typeof window.loadCampaigns === "function" && document.getElementById("llm-controls"),
    null,
    { timeout: 20000 }
  );
  await ensureCampaignControlsVisible(page);
}

module.exports = { login, loadConfig };
