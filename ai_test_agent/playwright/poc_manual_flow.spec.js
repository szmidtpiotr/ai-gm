const { test, expect } = require("@playwright/test");
const { login, loadConfig } = require("./helpers/auth");
const { resetTestEnv, getPlayerState } = require("./helpers/game_state");
const path = require("path");
const fs = require("fs");

let cfg;

test.beforeAll(async () => {
  cfg = loadConfig();
  const result = await resetTestEnv();
  expect(result.reset).toBe(true);
});

test("poc_manual_flow: login -> campaign -> chat -> GM response", async ({ page }) => {
  await page.goto("/");
  await login(page);

  const campaignSelect = page.locator("#campaign-select");
  await campaignSelect.waitFor({ state: "visible", timeout: 10000 });
  await page.selectOption("#campaign-select", { label: "AI Test Campaign" });

  const createName = page.locator("#character-create-name");
  if (await createName.isVisible().catch(() => false)) {
    await createName.fill("TestPlayer");
    await page.click("#character-create-submit");
  }

  await page.waitForSelector("#send-btn", { timeout: 15000 });
  await page.fill("textarea#input", "Czy możesz mi opisać otoczenie?");
  await page.click("#send-btn");

  // Archiwalne błędy (np. brak Ollama) mają .is-archived-bubble i są ukryte — czekamy na widoczną odpowiedź GM.
  await page.waitForSelector("#chat .message.assistant:not(.is-archived-bubble)", {
    state: "visible",
    timeout: 60000,
  });
  const state = await getPlayerState(cfg.character_id);
  expect(Boolean(state.location)).toBe(true);

  const screenshotsDir = path.resolve(__dirname, "../screenshots");
  fs.mkdirSync(screenshotsDir, { recursive: true });
  await page.screenshot({ path: path.join(screenshotsDir, "poc_step_8.png") });
});
