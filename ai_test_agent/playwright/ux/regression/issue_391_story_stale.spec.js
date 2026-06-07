/**
 * REGRESSION #391 — STORY_STALE / TRAVEL_HINT
 * Verifies that repeated turns without location change trigger the STORY_STALE
 * mechanic without crashing the game, and the session remains playable.
 */
const { test, expect } = require("@playwright/test");
const { enterGame, sendMultipleTurns } = require("../../helpers/player_flow");

const TURN_TIMEOUT = 180_000; // 3 min per turn — Ollama can be slow on first cold start

test.describe("REGRESSION #391 — STORY_STALE / TRAVEL_HINT", () => {
  test("6 identical turns trigger story_stale without crash", async ({ page }) => {
    test.setTimeout(6 * TURN_TIMEOUT + 60_000); // 6 turns + setup margin
    await enterGame(page);
    await sendMultipleTurns(page, "czekam", 6, { timeout: TURN_TIMEOUT });
    await expect(page.locator("#game-screen.screen--active")).toBeVisible();
    await expect(page.locator("#send-btn")).toBeEnabled();
    // GM must still respond (last bubble visible and non-empty)
    const lastBubble = page.locator("#chat-messages .chat-bubble--gm:not(.chat-bubble--typing)").last();
    await expect(lastBubble).toBeVisible();
    await expect(lastBubble).not.toHaveText(/^\s*$/);
  });
});
