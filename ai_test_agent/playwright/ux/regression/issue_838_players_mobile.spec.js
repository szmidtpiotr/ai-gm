/**
 * REGRESSION #838 (M1) — Sekcja Gracze mobile @390px: card-view + drawer tabs.
 * Acceptance: brak poziomego scrolla, lista graczy w card-view, szuflada gracza
 * z tabami (Info/Kampanie/LLM/Tryby gry) używalna na telefonie; brak regresji @1024px.
 */
const { test, expect } = require('@playwright/test');

const ADMIN_URL = '/admin/';

/** Login to admin panel and navigate to players section. */
async function loginAndGoPlayers(page) {
  await page.goto(ADMIN_URL);
  await page.waitForSelector('#login-user', { timeout: 8000 });
  await page.fill('#login-user', 'demo');
  await page.fill('#login-pass', 'demo');
  await page.click('#login-submit');
  await page.waitForFunction(
    () => !document.getElementById('login-overlay')?.classList.contains('open'),
    { timeout: 8000 }
  );
  await page.waitForTimeout(1000);
  await page.evaluate(() => { window.location.hash = '#players'; });
  await page.waitForTimeout(3000);
}

// ─── Mobile tests ─────────────────────────────────────────────────────────────

test('REGRESSION #838 — @390px brak poziomego scrolla strony (players)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginAndGoPlayers(page);

  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth, `Poziomy scroll: scrollWidth(${scrollWidth}) > clientWidth(${clientWidth})`).toBeLessThanOrEqual(clientWidth);
});

test('REGRESSION #838 — @390px lista graczy renderuje card-view (nie tabela desktop)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginAndGoPlayers(page);

  // In card-view, thead tr is display:none; check that the header row is hidden
  const headerRowHidden = await page.evaluate(() => {
    const theadTr = document.querySelector('#players-table thead tr');
    if (!theadTr) return true; // no row = hidden
    return window.getComputedStyle(theadTr).display === 'none';
  });
  expect(headerRowHidden, 'thead tr powinien być ukryty w trybie card-view (@390px)').toBe(true);
});

test('REGRESSION #838 — @390px drawer gracza otwiera się i ma 4 taby', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginAndGoPlayers(page);

  // Open drawer for first player
  await page.click('button.btn-icon[title="Otwórz panel gracza"]', { timeout: 5000 });
  await page.waitForTimeout(1500);

  const drawerOpen = await page.evaluate(() => document.querySelector('.pdrawer')?.classList.contains('open'));
  expect(drawerOpen, 'Drawer powinien być otwarty (.pdrawer.open)').toBe(true);

  // All 4 tabs should be present
  const tabs = await page.$$eval('.pdrawer-tab', els => els.map(e => e.textContent.trim()));
  expect(tabs).toContain('Info');
  expect(tabs).toContain('Kampanie');
  expect(tabs).toContain('LLM');
  expect(tabs).toContain('Tryby gry');

  // No horizontal overflow with drawer open
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});

// ─── Desktop regression ───────────────────────────────────────────────────────

test('REGRESSION #838 — @1200px brak regresji desktop (tabela graczy widoczna)', async ({ page }) => {
  await page.setViewportSize({ width: 1200, height: 900 });
  await loginAndGoPlayers(page);

  // At desktop width, thead tr should be visible (table layout, not card-view)
  const headerRowVisible = await page.evaluate(() => {
    const theadTr = document.querySelector('#players-table thead tr');
    if (!theadTr) return false;
    return window.getComputedStyle(theadTr).display !== 'none';
  });
  expect(headerRowVisible, 'thead tr powinien być widoczny @1200px (desktop table-view)').toBe(true);

  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});
