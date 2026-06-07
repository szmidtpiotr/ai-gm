/**
 * Acceptance — C12 (#366). Part of the C1–C19 FAZA 1 suite.
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

test("C12 (#366) — [SPEND_GOLD] dedukuje z configu, nie z LLM", async ({ page }) => {
  const reset = await enterGame(page);
  const before = await playerState(reset.character_id);
  // Ask to buy something cheap; gold must only drop by a config amount, and
  // never below zero. (Full determinism asserted in pytest.)
  await sendTurnAndWaitForGm(page, "kupuję bochenek chleba u piekarza", { timeout: TURN });
  const after = await playerState(reset.character_id);
  expect(after.gold_gp, "Złoto spadło poniżej zera (C12)").toBeGreaterThanOrEqual(0);
  expect(after.gold_gp, "Złoto wzrosło po zakupie (C12)").toBeLessThanOrEqual(before.gold_gp);
});
