/**
 * Acceptance — C9 (#363). Part of the C1–C19 FAZA 1 suite.
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

test("C09 (#363) — modal nauki/awansu (wydawanie PD) otwiera się", async ({ page }) => {
  await enterGame(page);
  // Rest + learn controls live in the character sheet panel (#sheet-rest-actions).
  await openCharacterSheet(page);
  const awansuj = page.locator("#btn-awansuj");
  await expect(awansuj, "Brak przycisku Awansuj/Ucz się (C9)").toBeVisible({ timeout: 8000 });
  await awansuj.click();
  await expect(
    page.locator("#awansuj-modal"),
    "Modal Awansuj (wydawanie PD) nie otworzył się (C9)",
  ).toBeVisible({ timeout: 8000 });
});
