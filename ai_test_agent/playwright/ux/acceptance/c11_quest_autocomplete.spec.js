/**
 * Acceptance — C11 (#365). Part of the C1–C19 FAZA 1 suite.
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

test("C11 (#365) — quest auto-completuje po wykonaniu celu", async () => {
  // Auto-completion logic (kill/location matcher + reward parsing) is verified
  // deterministically in pytest (test_c11_*). E2E would depend on first getting
  // the LLM to emit a quest (see C10).
  test.skip(true, "C11 weryfikowane w pytest (check_kill/location_quest)");
});
