const { test, expect } = require("@playwright/test");
const { clearBrowserState, login, DEFAULT_HERO } = require("../helpers/player_flow");
const { resetTestEnv } = require("../helpers/game_state");

test.describe("UX: login and heroes hub", () => {
  test.beforeEach(async ({ page }) => {
    await clearBrowserState(page);
    const result = await resetTestEnv();
    expect(result.reset).toBe(true);
  });

  test("login lands on heroes with TestPlayer card", async ({ page }) => {
    await login(page);
    await expect(page.locator("#heroes-screen.screen--active")).toBeVisible();
    await expect(page.locator(".hero-card").filter({ hasText: DEFAULT_HERO })).toBeVisible();
  });
});
