/**
 * Player UI flows for the current front/ SPA (hero-first, 2026).
 * Requires AI_TEST_MODE=1 and AI_TEST_STUB_LLM=1 on the backend.
 */
const { expect } = require("@playwright/test");
const { loadConfig } = require("./auth");
const { resetTestEnv } = require("./game_state");

const DEFAULT_USER = "ai_test_player";
const DEFAULT_PASS = process.env.AI_TEST_PLAYER_PASSWORD || "demo";
const DEFAULT_HERO = "TestPlayer";
const DEFAULT_CAMPAIGN = "AI Test Campaign";

async function clearBrowserState(page) {
  await page.addInitScript(() => {
    try {
      localStorage.clear();
      sessionStorage.clear();
    } catch (_) {
      /* ignore */
    }
  });
}

async function dismissOnboardingIfPresent(page) {
  const cta = page.locator("#onboarding-cta");
  if (await cta.isVisible({ timeout: 3000 }).catch(() => false)) {
    await cta.click();
    const start = page.locator("#onboarding-start");
    if (await start.isVisible({ timeout: 5000 }).catch(() => false)) {
      await start.click();
    }
  }
}

async function login(page, { username = DEFAULT_USER, password = DEFAULT_PASS } = {}) {
  await page.goto("/");
  await page.waitForSelector("#login-screen.screen--active", { timeout: 15000 });
  await page.fill("#login-username", username);
  await page.fill("#login-password", password);
  await page.locator("#login-form button[type='submit']").click();
  // Wait for any post-login screen (onboarding, heroes, or game) before attempting dismiss.
  // The login API call can take several seconds, so we wait here instead of hoping the
  // 3s timeout in dismissOnboardingIfPresent is enough.
  await page.waitForFunction(
    () => {
      const ids = ["onboarding-screen", "heroes-screen", "game-screen"];
      return ids.some((id) => document.getElementById(id)?.classList.contains("screen--active"));
    },
    null,
    { timeout: 25000 },
  );
  await dismissOnboardingIfPresent(page);
  // Now wait for heroes or game (onboarding dismissed above)
  await page.waitForFunction(
    () => {
      const heroes = document.getElementById("heroes-screen");
      const game = document.getElementById("game-screen");
      return (
        heroes?.classList.contains("screen--active") || game?.classList.contains("screen--active")
      );
    },
    null,
    { timeout: 15000 },
  );
}

async function openHeroAndCampaign(
  page,
  { heroName = DEFAULT_HERO, campaignTitle = DEFAULT_CAMPAIGN, campaignId = null } = {},
) {
  // Always navigate away from game screen first to guarantee fresh campaign selection.
  // Without this, if the browser auto-restores to a PREVIOUS campaign on login, openHeroAndCampaign
  // would return early (onGame=true) without navigating to the seeded campaign.
  const onGame = await page.evaluate(
    () => document.getElementById("game-screen")?.classList.contains("screen--active"),
  );
  if (onGame) {
    // Navigate back to heroes so we can select the right campaign by ID.
    await page.locator("#home-btn").click().catch(() => {});
    await page.waitForSelector("#heroes-screen.screen--active", { timeout: 15000 }).catch(() => {});
  }

  const onHeroes = await page.evaluate(
    () => document.getElementById("heroes-screen")?.classList.contains("screen--active"),
  );
  if (onHeroes) {
    const card = page.locator(".hero-card").filter({ hasText: heroName }).first();
    await card.waitFor({ state: "visible", timeout: 15000 });
    await card.click();
    const idleProceed = page.locator("#idle-hero-panel-proceed");
    if (await idleProceed.isVisible().catch(() => false)) {
      await idleProceed.click();
    }
  }

  await page.waitForSelector("#campaigns-screen.screen--active", { timeout: 20000 });
  // Prefer selecting by campaign ID (exact match) when available, to avoid picking a stale
  // campaign with the same title from a previous test run.
  const campBtn = campaignId
    ? page.locator(`button.campaign-card[data-campaign-id="${campaignId}"]`)
    : page.locator("button.campaign-card").filter({ hasText: campaignTitle }).first();
  await campBtn.waitFor({ state: "visible", timeout: 15000 });
  await campBtn.click();

  await page.waitForSelector("#game-screen.screen--active", { timeout: 30000 });
  await page.waitForSelector("#send-btn", { state: "visible", timeout: 15000 });
}

async function enterGame(page, opts = {}) {
  await clearBrowserState(page);
  const reset = await resetTestEnv();
  expect(reset.reset).toBe(true);
  await login(page, opts);
  // Pass campaign_id so openHeroAndCampaign selects the exact seeded campaign (not a stale one).
  await openHeroAndCampaign(page, { ...opts, campaignId: reset.campaign_id });
  return reset;
}

async function sendTurnAndWaitForGm(page, text, { timeout = 90000 } = {}) {
  await page.fill("#chat-input", text);
  await page.click("#send-btn");
  const gmBubble = page.locator(
    "#chat-messages .chat-bubble--gm:not(.chat-bubble--typing):not(.chat-bubble--streaming)",
  ).last();
  await expect(gmBubble).toBeVisible({ timeout });
  await expect(gmBubble).not.toHaveText(/^\s*$/);
  return gmBubble;
}

async function sendMultipleTurns(page, text, count, opts = {}) {
  const results = [];
  for (let i = 0; i < count; i++) {
    const bubble = await sendTurnAndWaitForGm(page, text, opts);
    const content = await bubble.textContent();
    results.push(content);
    if (opts.afterEach) await opts.afterEach(content, i);
  }
  return results;
}

async function openCharacterSheet(page) {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#mobile-bottom-bar button[data-mbb="character"]').click();
  await page.waitForSelector("#sheet-panel.sheet-panel--open", { timeout: 10000 });
  await expect(page.locator("#sheet-character-name")).toBeVisible();
}

module.exports = {
  clearBrowserState,
  login,
  openHeroAndCampaign,
  enterGame,
  sendTurnAndWaitForGm,
  sendMultipleTurns,
  openCharacterSheet,
  loadConfig,
  DEFAULT_USER,
  DEFAULT_HERO,
  DEFAULT_CAMPAIGN,
};
