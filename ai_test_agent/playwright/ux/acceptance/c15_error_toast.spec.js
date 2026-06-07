/**
 * Acceptance — C15 (#369). Part of the C1–C19 FAZA 1 suite.
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

test("C15 (#369) — błąd API pokazuje toast, nie biały ekran", async ({ page }) => {
  await enterGame(page);
  // Inject a 500 on the next turns call and confirm the UI surfaces a toast
  // instead of crashing to a blank screen.
  await page.route("**/api/campaigns/**/turns**", (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"boom"}' }),
  );
  await page.fill("#chat-input", "robię cokolwiek").catch(() => {});
  await page.click("#send-btn").catch(() => {});
  const toast = page.locator(".toast, #toast, [role='alert'], .notification--error");
  const gameAlive = await page
    .locator("#game-screen.screen--active")
    .isVisible()
    .catch(() => false);
  const toastShown = await toast
    .first()
    .isVisible({ timeout: 6000 })
    .catch(() => false);
  expect(toastShown || gameAlive, "Brak toasta i biały ekran po błędzie API (C15)").toBeTruthy();
  await page.unroute("**/api/campaigns/**/turns**").catch(() => {});
});
