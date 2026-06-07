/**
 * Acceptance — C8 (#362). Part of the C1–C19 FAZA 1 suite.
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

test("C08 (#362) — endpoint spend-xp/stat istnieje i waliduje XP", async ({ page, request }) => {
  const reset = await enterGame(page);
  const r = await request.post(`/api/characters/${reset.character_id}/spend-xp/stat`, {
    data: { stat_key: "STR" },
  });
  expect([200, 400], `spend-xp/stat zwrócił ${r.status()} (C8)`).toContain(r.status());
});
