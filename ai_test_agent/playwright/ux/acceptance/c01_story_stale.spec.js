/**
 * Acceptance — C1 (#355). Part of the C1–C19 FAZA 1 suite.
 * Split from c_series.spec.js so each task runs individually from
 * Admin3 → Narzędzia → 🎭 Playwright.
 */
const { test, expect } = require("@playwright/test");
const { enterGame, sendTurnAndWaitForGm, openCharacterSheet } = require("../../helpers/player_flow");
const {
  playUntilGoal,
  containsAny,
  playerState,
  TRAVEL_HINT_WORDS,
  NON_GP_CURRENCY_WORDS,
  EQUIPMENT_LOSS_WORDS,
} = require("../../helpers/acceptance");

const TURN = 70_000;

test("C01 (#355) — LLM sugeruje ruch po N turach w jednym miejscu", async ({ page }) => {
  test.setTimeout(14 * TURN + 60_000);
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
    `LLM nie zasugerował ruchu w ${res.turns} turach (C1 STORY_STALE)`,
  ).toBeTruthy();
});
