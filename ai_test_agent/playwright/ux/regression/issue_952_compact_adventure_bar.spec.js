/**
 * REGRESSION #952 (interface-design) — kompaktowy "pasek przygody" gry.
 * Acceptance: górna belka to jeden rząd; akcje drugorzędne (Dziennik, Księga,
 * Ustawienia) chowają się pod hamburgerem ☰ (dropdown), Mapa zostaje osobną
 * ikoną obok ☰; brak osobnego wiersza "Poziom • HP".
 */
const { test, expect } = require("@playwright/test");
const { enterGame } = require("../../helpers/player_flow");

test("REGRESSION #952 — belka gry: 🗺 + ☰ menu, jeden rząd", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await enterGame(page);
  await page.waitForSelector("#game-screen.screen--active", { timeout: 15000 });

  // 1. Hamburger ☰ istnieje w pasku
  const menuBtn = page.locator("#game-menu-btn");
  await expect(menuBtn, "brak przycisku ☰ #game-menu-btn (#952)").toBeVisible();

  // 2. Mapa zostaje osobną ikoną w pasku (nie schowana w menu)
  await expect(page.locator(".header--game #open-map-btn"), "Mapa powinna być osobną ikoną w pasku").toBeVisible();

  // 3. Menu domyślnie schowane
  const menu = page.locator("#game-menu");
  await expect(menu, "#game-menu powinno być schowane na starcie").toBeHidden();

  // 4. Klik ☰ otwiera dropdown z akcjami drugorzędnymi
  await menuBtn.click();
  await expect(menu, "menu nie otworzyło się po kliknięciu ☰").toBeVisible();
  await expect(page.locator("#game-menu #open-journal-btn"), "Dziennik w menu").toBeVisible();
  await expect(page.locator("#game-menu #open-codex-btn"), "Księga Zasad w menu").toBeVisible();
  await expect(page.locator("#game-menu #open-settings-btn"), "Ustawienia w menu").toBeVisible();

  // 5. Klik poza menu zamyka je
  await page.locator("#chat-messages").click({ position: { x: 10, y: 10 } }).catch(() => {});
  await expect(menu, "menu powinno zamknąć się po kliknięciu poza").toBeHidden();

  // 6. Brak stałego, widocznego wiersza "Poziom • HP" — character-stats-display nie jest widoczny
  const statsVisible = await page.locator("#character-stats-display").isVisible().catch(() => false);
  expect(statsVisible, "wiersz 'Poziom • HP' powinien zniknąć z paska (hidden)").toBeFalsy();

  // 7. Pasek to pojedynczy kompaktowy rząd (~48–52px, tolerancja do 64px)
  const h = await page.locator(".header--game").evaluate((el) => el.getBoundingClientRect().height);
  expect(h, `pasek za wysoki (${h}px) — ma być ~48–52px (#952)`).toBeLessThanOrEqual(64);
});
