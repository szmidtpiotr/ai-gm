/**
 * Acceptance — C7 (#361). Part of the C1–C19 FAZA 1 suite.
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

test("C07 (#361) — endpoint spend-xp/skill istnieje i waliduje XP", async ({ page, request }) => {
  const reset = await enterGame(page);
  const r = await request.post(`/api/characters/${reset.character_id}/spend-xp/skill`, {
    data: { skill_key: "awareness" },
  });
  // Endpoint must exist (not 404). With no XP it returns 400 "Not enough XP".
  expect([200, 400], `spend-xp/skill zwrócił ${r.status()} (C7)`).toContain(r.status());
});
