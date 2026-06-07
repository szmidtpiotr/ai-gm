/**
 * Acceptance — C3 (#357). Part of the C1–C19 FAZA 1 suite.
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

test("C03 (#357) — ATTACK bez wrogów nie startuje walki", async ({ page }) => {
  test.setTimeout(6 * TURN + 60_000);
  const reset = await enterGame(page);
  // Attack into empty air: the Gate must refuse — no combat banner appears.
  await sendTurnAndWaitForGm(page, "dobywam miecza i atakuję najbliższego wroga", {
    timeout: TURN,
  });
  const combatVisible = await page
    .locator("#combat-banner")
    .isVisible()
    .catch(() => false);
  expect(combatVisible, "Walka wystartowała mimo braku wrogów w scenie (C3 gate)").toBeFalsy();
  // Character must not have lost HP from a phantom fight.
  const st = await playerState(reset.character_id);
  expect(st.hp).toBe(st.max_hp);
});
