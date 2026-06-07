/**
 * Acceptance — C19 (#375). Part of the C1–C19 FAZA 1 suite.
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

test("C19 (#375) — bohater startuje kampanię z pełnym HP", async ({ page }) => {
  const reset = await enterGame(page); // reset_test_env restores full HP for the seeded hero
  const st = await playerState(reset.character_id);
  expect(st.hp, "Bohater nie ma pełnego HP na starcie (C19)").toBe(st.max_hp);
});
