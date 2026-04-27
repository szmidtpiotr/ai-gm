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
  const collapsed = page.locator("#llm-controls.llm-controls--collapsed");
  if (await collapsed.count()) {
    await page.click("#llm-settings-toggle-btn");
  }
  await page.waitForSelector("#campaign-select", { state: "visible", timeout: 15000 });
}

module.exports = { login, loadConfig };
