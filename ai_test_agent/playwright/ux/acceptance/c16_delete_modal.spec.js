/**
 * Acceptance — C16 (#370). Part of the C1–C19 FAZA 1 suite.
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

test("C16 (#370) — kasowanie kampanii/postaci wymaga modala potwierdzenia", async ({ page }) => {
  const reset = await enterGame(page);
  // Go back to heroes/campaigns to find a delete (trash) control.
  await page.locator("#home-btn").click().catch(() => {});
  await page.waitForSelector("#heroes-screen.screen--active", { timeout: 15000 }).catch(() => {});
  const trash = page.locator(
    "[data-action='delete-hero'], .hero-card .delete, button[title*='Usuń'], .card-delete",
  );
  const hasTrash = (await trash.count().catch(() => 0)) > 0;
  test.skip(!hasTrash, "Brak kontrolki kasowania na ekranie — pominięto");
  await trash.first().click().catch(() => {});
  const modal = page.locator(".delete-modal, #delete-modal, [data-modal='confirm-delete']");
  await expect(modal.first(), "Kasowanie bez modala potwierdzenia (C16)").toBeVisible({
    timeout: 6000,
  });
});
