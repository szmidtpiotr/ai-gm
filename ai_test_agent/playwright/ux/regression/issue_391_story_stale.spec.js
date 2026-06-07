/**
 * REGRESSION #391 — STORY_STALE / TRAVEL_HINT
 * Verifies that repeated turns without location change trigger the STORY_STALE
 * mechanic without crashing the game, and the session remains playable.
 */
const { test, expect } = require("@playwright/test");
const { enterGame, sendMultipleTurns } = require("../../helpers/player_flow");

test.describe("REGRESSION #391 — STORY_STALE / TRAVEL_HINT", () => {
  test("6 identical turns trigger story_stale without crash", async ({ page }) => {
    await enterGame(page);
    await sendMultipleTurns(page, "czekam", 6);
    await expect(page.locator("#game-screen.screen--active")).toBeVisible();
    await expect(page.locator("#send-btn")).toBeEnabled();
  });

  test("game remains playable past story_stale threshold (8 turns)", async ({ page }) => {
    await enterGame(page);
    await sendMultipleTurns(page, "czekam", 8);
    await expect(page.locator("#game-screen.screen--active")).toBeVisible();
    await expect(page.locator("#chat-input")).toBeEnabled();
    // GM must still respond (last bubble visible)
    const lastBubble = page.locator("#chat-messages .chat-bubble--gm:not(.chat-bubble--typing)").last();
    await expect(lastBubble).toBeVisible();
    await expect(lastBubble).not.toHaveText(/^\s*$/);
  });
});
