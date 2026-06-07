/**
 * Acceptance — C4 (#360). Part of the C1–C19 FAZA 1 suite.
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

test("C04 (#360) — wound penalty progi spójne (utility/endpoint)", async ({ request }) => {
  const r = await request.get("/api/config/wound-thresholds");
  expect(r.status(), "Brak kanonicznego źródła progów ran (C4/C6)").toBe(200);
  const body = await r.json();
  expect(body).toHaveProperty("critical_pct");
  expect(body).toHaveProperty("moderate_pct");
});
