/**
 * REGRESSION #355 — C1 STORY_STALE: after N turns without changing location the
 * GM must nudge the player to move (NPC, event, or road description).
 * Acceptance: po 5 turach w tej samej lokacji LLM sugeruje ruch.
 */
const { test, expect } = require("@playwright/test");
const { enterGame } = require("../../helpers/player_flow");
const { playUntilGoal, containsAny, TRAVEL_HINT_WORDS } = require("../../helpers/acceptance");

const TURN = 70_000;

test("REGRESSION #355 — STORY_STALE › LLM sugeruje ruch po staniu w miejscu", async ({ page }) => {
  test.setTimeout(12 * TURN + 60_000);
  await enterGame(page);
  const res = await playUntilGoal(page, {
    messages: ["czekam", "rozglądam się", "stoję w miejscu", "nasłuchuję"],
    maxTurns: 12,
    turnTimeout: TURN,
    goal: async ({ page, text }) => {
      const pill = await page
        .locator(".travel-hint, [data-travel-hint], .story-stale-hint")
        .count()
        .catch(() => 0);
      return pill > 0 || containsAny(text, TRAVEL_HINT_WORDS);
    },
  });
  expect(
    res.achieved,
    `LLM nie zasugerował ruchu w ${res.turns} turach w tej samej lokacji (#355)`,
  ).toBeTruthy();
});
