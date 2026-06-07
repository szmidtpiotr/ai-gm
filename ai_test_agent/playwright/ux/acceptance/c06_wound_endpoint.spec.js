/**
 * Acceptance — C6 (#359). Part of the C1–C19 FAZA 1 suite.
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

test("C06 (#359) — endpoint progów ran zwraca dane", async ({ request }) => {
  const r = await request.get("/api/config/wound-thresholds");
  expect(r.status()).toBe(200);
  const b = await r.json();
  expect(typeof b.healthy_pct === "number" || typeof b.moderate_pct === "number").toBeTruthy();
});
