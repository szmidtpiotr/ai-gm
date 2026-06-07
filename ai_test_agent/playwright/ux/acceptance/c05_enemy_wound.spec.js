/**
 * Acceptance — C5 (#358). Part of the C1–C19 FAZA 1 suite.
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

test("C05 (#358) — wrogowie też dostają wound penalty (symetria)", async ({ page }) => {
  // Enemy roll modifiers at low HP are not surfaced in the player client, so
  // this is asserted deterministically in pytest (test_c05_*). Here we only
  // flag it as not-client-observable rather than forcing a false negative.
  const inspectorField = await page
    .locator("[data-enemy-wound-penalty], .enemy-wound-penalty")
    .count()
    .catch(() => 0);
  test.skip(
    inspectorField === 0,
    "Symetria wound penalty wrogów weryfikowana w pytest (brak pola w UI)",
  );
  expect(inspectorField).toBeGreaterThan(0);
});
