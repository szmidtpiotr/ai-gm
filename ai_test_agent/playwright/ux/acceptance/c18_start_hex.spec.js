/**
 * Acceptance — C18 (#374). Part of the C1–C19 FAZA 1 suite.
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

test("C18 (#374) — nowa kampania startuje na istniejącym/0,0 hexie", async ({ page, request }) => {
  // The seeded test campaign must have a sane start location (not an empty
  // fringe). Asserted thoroughly in pytest against world_hexes; here we check
  // the player has a non-empty, known location after entering.
  const reset = await enterGame(page);
  const st = await playerState(reset.character_id);
  expect(st.location, "Kampania bez startowej lokacji (C18)").toBeTruthy();
});
