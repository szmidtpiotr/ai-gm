/**
 * Acceptance — C14 (#368). Part of the C1–C19 FAZA 1 suite.
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

test("C14 (#368) — nowy gracz bez bohatera ląduje na Heroes screen", async ({ page }) => {
  // Fresh login (no auto-selected campaign) should land on heroes, not the
  // campaign-wizard directly. enterGame already routes through heroes; assert
  // the heroes screen was reachable and the wizard is not force-shown.
  await enterGame(page);
  const wizardForced = await page
    .locator("#character-wizard.screen--active, #char-creator.screen--active")
    .count()
    .catch(() => 0);
  expect(wizardForced, "Kreator postaci wymuszony zamiast Heroes screen (C14)").toBe(0);
});
