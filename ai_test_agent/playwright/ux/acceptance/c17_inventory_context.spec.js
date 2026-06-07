/**
 * Acceptance — C17 (#373). Part of the C1–C19 FAZA 1 suite.
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

test("C17 (#373) — LLM nie narruje utraty ekwipunku, zna broń i złoto", async ({ page }) => {
  test.setTimeout(8 * TURN + 60_000);
  const reset = await enterGame(page);
  const st = await playerState(reset.character_id);
  // Only meaningful when the hero actually has gear/gold — otherwise "no
  // weapon" narration would be correct. Deterministic check lives in pytest
  // (test_c17_inventory_context_block_mentions_gear).
  test.skip(
    st.inventory.length + st.gold_gp === 0,
    "Bohater testowy bez ekwipunku/złota — C17 weryfikowane w pytest",
  );
  // Opening bubble + a few turns must not claim the hero lost their gear.
  const res = await playUntilGoal(page, {
    messages: [
      "sprawdzam swój ekwipunek i broń",
      "zaglądam do sakiewki, ile mam złota?",
      "przyglądam się swojemu uzbrojeniu",
    ],
    maxTurns: 5,
    turnTimeout: TURN,
    goal: () => false,
  });
  const lossNarrated = res.responses.filter((r) => containsAny(r, EQUIPMENT_LOSS_WORDS));
  expect(
    lossNarrated.length,
    `LLM narrował utratę ekwipunku mimo że postać ma przedmioty (C17): ${lossNarrated[0] || ""}`,
  ).toBe(0);
  // Sanity: the hero actually has gear/gold to talk about.
  expect(st.inventory.length + st.gold_gp, "Postać testowa nie ma ekwipunku ani złota").toBeGreaterThan(0);
});
