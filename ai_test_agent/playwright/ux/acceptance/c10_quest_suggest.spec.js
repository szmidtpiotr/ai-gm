/**
 * Acceptance — C10 (#364). Part of the C1–C19 FAZA 1 suite.
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

test("C10 (#364) — quest trafia do active_quests przez QUEST_SUGGEST", async () => {
  // Quests are stored in world_state_flags (not the character sheet) and the
  // LLM emitting the tag on cue is prompt-dependent/flaky. The parser +
  // storage round-trip is verified deterministically in pytest
  // (test_c10_quest_suggest_parser_and_storage).
  test.skip(true, "C10 weryfikowane w pytest (parser + world_state_flags)");
});
