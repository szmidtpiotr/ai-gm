/**
 * Acceptance — C2 (#356). Part of the C1–C19 FAZA 1 suite.
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

test("C02 (#356) — ruch na nieistniejący hex zwraca 400", async ({ page, request }) => {
  const reset = await enterGame(page);
  // Try to move onto an absurd hex through the turn intent; the move must be
  // rejected (blocked) rather than silently teleporting the player.
  const before = await playerState(reset.character_id);
  await sendTurnAndWaitForGm(page, "natychmiast teleportuję się na hex 999,999", {
    timeout: TURN,
  });
  const after = await playerState(reset.character_id);
  expect(
    after.location,
    "Gracz przeniósł się na nieistniejący hex (C2 walidacja ruchu)",
  ).toBe(before.location);
});
