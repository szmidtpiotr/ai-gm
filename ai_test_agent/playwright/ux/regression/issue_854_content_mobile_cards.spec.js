/**
 * REGRESSION #854 (M2-1) — Sekcja Zawartość: tabele kart/scroll na mobile @390px.
 * Acceptance: listy encji (bronie, zbroja, itd.) renderują się w card-view;
 * brak poziomego scrolla strony; komórki mają data-label; brak regresji @1024px;
 * loot entries modal pozostaje scroll.
 */
const { test, expect } = require('@playwright/test');

const ADMIN_URL = '/admin/';

async function loginAndGoContent(page, tab) {
  await page.goto(ADMIN_URL);
  await page.waitForSelector('#login-user', { timeout: 8000 });
  await page.fill('#login-user', 'demo');
  await page.fill('#login-pass', 'demo');
  await page.click('#login-submit');
  await page.waitForFunction(
    () => !document.getElementById('login-overlay')?.classList.contains('open'),
    { timeout: 8000 }
  );
  await page.waitForTimeout(800);
  await page.evaluate(() => { window.location.hash = '#content'; });
  await page.waitForTimeout(3000);
  if (tab) {
    await page.click(`[data-tab="${tab}"]`, { timeout: 5000 });
    await page.waitForTimeout(2000);
  }
}

// ─── Mobile tests ─────────────────────────────────────────────────────────────

test('REGRESSION #854 — @390px brak poziomego scrolla (content weapons)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginAndGoContent(page, null);

  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth, `Poziomy scroll: scrollWidth(${scrollWidth}) > clientWidth(${clientWidth})`).toBeLessThanOrEqual(clientWidth);
});

test('REGRESSION #854 — @390px weapons-table renderuje card-view (thead ukryty)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginAndGoContent(page, null);

  // Wait for data to load
  await page.waitForFunction(() => {
    const tbody = document.querySelector('#weapons-table tbody');
    return tbody && !tbody.textContent.includes('Ładowanie');
  }, { timeout: 10000 }).catch(() => {});

  // In card-view, thead tr is display:none
  const headerRowHidden = await page.evaluate(() => {
    const theadTr = document.querySelector('#weapons-table thead tr');
    if (!theadTr) return true;
    return window.getComputedStyle(theadTr).display === 'none';
  });
  expect(headerRowHidden, 'weapons thead tr powinien być ukryty w card-view (@390px)').toBe(true);
});

test('REGRESSION #854 — @390px weapons tbody cells have data-label attributes', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginAndGoContent(page, null);

  await page.waitForFunction(() => {
    const tbody = document.querySelector('#weapons-table tbody');
    return tbody && !tbody.textContent.includes('Ładowanie');
  }, { timeout: 10000 }).catch(() => {});

  const labelCount = await page.evaluate(() => {
    return document.querySelectorAll('#weapons-table tbody td[data-label]').length;
  });
  expect(labelCount, 'Komórki weapons tbody powinny mieć data-label (dla ::before w card-view)').toBeGreaterThan(0);
});

test('REGRESSION #854 — @390px consumables card-view (thead ukryty)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginAndGoContent(page, 'consumables');

  await page.waitForFunction(() => {
    const tbody = document.querySelector('#consumables-table tbody');
    return tbody && !tbody.textContent.includes('Ładowanie');
  }, { timeout: 10000 }).catch(() => {});

  const headerRowHidden = await page.evaluate(() => {
    const theadTr = document.querySelector('#consumables-table thead tr');
    if (!theadTr) return true;
    return window.getComputedStyle(theadTr).display === 'none';
  });
  expect(headerRowHidden, 'consumables thead tr powinien być ukryty w card-view (@390px)').toBe(true);
});

// ─── Desktop regression ───────────────────────────────────────────────────────

test('REGRESSION #854 — @1200px brak regresji desktop (tabela broni widoczna)', async ({ page }) => {
  await page.setViewportSize({ width: 1200, height: 900 });
  await loginAndGoContent(page, null);

  await page.waitForFunction(() => {
    const tbody = document.querySelector('#weapons-table tbody');
    return tbody && !tbody.textContent.includes('Ładowanie');
  }, { timeout: 10000 }).catch(() => {});

  // At desktop, thead tr must be visible (table layout, not card-view)
  const headerRowVisible = await page.evaluate(() => {
    const theadTr = document.querySelector('#weapons-table thead tr');
    if (!theadTr) return false;
    return window.getComputedStyle(theadTr).display !== 'none';
  });
  expect(headerRowVisible, 'weapons thead tr powinien być widoczny @1200px (tabela desktop)').toBe(true);

  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});
