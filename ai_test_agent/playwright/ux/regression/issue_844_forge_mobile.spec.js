/**
 * REGRESSION #844 (M3) — Kuźnia (forge.js) używalna na mobile @390px.
 * Acceptance: brak poziomego scrolla strony, sekcja ładuje się poprawnie,
 * tab „Agent AI" widoczny i klikalny, pływający chat nie wychodzi poza viewport.
 */
const { test, expect } = require('@playwright/test');

const ADMIN_URL = 'http://frontend:80/admin/';

test.use({ viewport: { width: 390, height: 844 } });

test('REGRESSION #844 — Kuźnia @390px: brak horizontal scroll, zakładki dostępne', async ({ page }) => {
  // Zaloguj jako admin
  await page.goto(ADMIN_URL + '#forge');
  await page.waitForTimeout(600);

  // Jeśli login overlay — zaloguj
  const loginOverlay = page.locator('#login-overlay');
  if (await loginOverlay.isVisible()) {
    await page.fill('#login-user', 'demo');
    await page.fill('#login-pass', 'demo');
    await page.click('#login-submit');
    await page.waitForTimeout(800);
  }

  // Nawiguj do sekcji Kuźnia przez hash
  await page.goto(ADMIN_URL + '#forge');
  await page.waitForTimeout(1200);

  // Sprawdź brak poziomego scrolla strony
  const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const windowWidth = await page.evaluate(() => window.innerWidth);
  expect(bodyScrollWidth, `Poziomy scroll strony: scrollWidth=${bodyScrollWidth} > innerWidth=${windowWidth}`).toBeLessThanOrEqual(windowWidth + 2);

  // Nagłówek sekcji widoczny
  const heading = page.locator('.section-heading');
  await expect(heading).toBeVisible();

  // Zakładki forge dostępne (stab-bar scroll)
  const stabBar = page.locator('#forge-tabs');
  await expect(stabBar).toBeVisible();

  // Tab Agent AI aktywny domyślnie
  const agentTab = page.locator('#forge-tabs .stab.active');
  await expect(agentTab).toBeVisible();

  // Pływający chat: nie wychodzi poza viewport gdy zamknięty
  const floatChat = page.locator('#forge-float-chat');
  const chatBox = await floatChat.boundingBox();
  if (chatBox && !await page.locator('#forge-float-chat.ffc-hidden').isVisible()) {
    expect(chatBox.x + chatBox.width, 'Floating chat wychodzi poza prawą krawędź').toBeLessThanOrEqual(windowWidth + 2);
  }
});

test('REGRESSION #844 — Kuźnia @390px: zakładka Szablony nie powoduje horizontal scroll', async ({ page }) => {
  await page.goto(ADMIN_URL + '#forge');
  await page.waitForTimeout(600);

  const loginOverlay = page.locator('#login-overlay');
  if (await loginOverlay.isVisible()) {
    await page.fill('#login-user', 'demo');
    await page.fill('#login-pass', 'demo');
    await page.click('#login-submit');
    await page.waitForTimeout(800);
  }

  await page.goto(ADMIN_URL + '#forge');
  await page.waitForTimeout(1200);

  // Kliknij zakładkę Szablony
  const tplTab = page.locator('#forge-tabs .stab[data-forgetab="templates"]');
  await tplTab.click();
  await page.waitForTimeout(600);

  const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const windowWidth = await page.evaluate(() => window.innerWidth);
  expect(bodyScrollWidth, `Poziomy scroll po kliknięciu Szablony: scrollWidth=${bodyScrollWidth} > innerWidth=${windowWidth}`).toBeLessThanOrEqual(windowWidth + 2);
});
