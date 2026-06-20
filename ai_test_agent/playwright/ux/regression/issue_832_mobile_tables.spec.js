/**
 * REGRESSION #832 (M0-3) — Mobile tables: card-view + scroll/sticky hybrid.
 * Acceptance: At 390px, content.js tables scroll horizontally with sticky first column;
 * campaigns/players/bugreports render as cards with data-label attributes.
 */
const { test, expect } = require('@playwright/test');

const ADMIN_URL = 'http://frontend:80/admin/';

async function adminLogin(page) {
  await page.goto(ADMIN_URL);
  await page.waitForSelector('#login-user', { timeout: 10000 });
  await page.fill('#login-user', 'demo');
  await page.fill('#login-pass', 'demo');
  await page.click('#login-submit');
  await page.waitForTimeout(2000);
}

test('REGRESSION #832 — components.css has mobile table utility classes', async ({ request }) => {
  const r = await request.get('http://frontend:80/admin/shared/components.css');
  expect(r.ok(), 'components.css should be accessible').toBeTruthy();
  const css = await r.text();
  expect(css, 'Missing .data-table--scroll').toContain('.data-table--scroll');
  expect(css, 'Missing .data-table--cards').toContain('.data-table--cards');
  expect(css, 'Missing data-label attr usage').toContain('attr(data-label)');
});

test('REGRESSION #832 — campaigns.js has data-table--cards and data-label', async ({ request }) => {
  const r = await request.get('http://frontend:80/admin/sections/campaigns.js');
  expect(r.ok()).toBeTruthy();
  const js = await r.text();
  expect(js, 'campaigns.js missing data-table--cards').toContain('data-table--cards');
  expect(js, 'campaigns.js missing data-label').toContain('data-label=');
});

test('REGRESSION #832 — content.js has data-table--scroll on table wrappers', async ({ request }) => {
  const r = await request.get('http://frontend:80/admin/sections/content.js');
  expect(r.ok()).toBeTruthy();
  const js = await r.text();
  expect(js, 'content.js missing data-table--scroll').toContain('data-table--scroll');
});

test('REGRESSION #832 — players.js has data-table--cards and data-label', async ({ request }) => {
  const r = await request.get('http://frontend:80/admin/sections/players.js');
  expect(r.ok()).toBeTruthy();
  const js = await r.text();
  expect(js, 'players.js missing data-table--cards').toContain('data-table--cards');
  expect(js, 'players.js missing data-label').toContain('data-label=');
});

test('REGRESSION #832 — bugreports.js has data-table--cards and data-label', async ({ request }) => {
  const r = await request.get('http://frontend:80/admin/sections/bugreports.js');
  expect(r.ok()).toBeTruthy();
  const js = await r.text();
  expect(js, 'bugreports.js missing data-table--cards').toContain('data-table--cards');
  expect(js, 'bugreports.js missing data-label').toContain('data-label=');
});

test('REGRESSION #832 — campaigns table has data-table--cards wrapper in DOM at 390px', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);

  // Open mobile drawer and navigate to campaigns
  const hamburger = page.locator('#hamburger-btn');
  if (await hamburger.isVisible()) {
    await hamburger.click();
    await page.waitForTimeout(300);
    const campLink = page.locator('#mobile-drawer-nav [data-section="campaigns"]');
    if (await campLink.count() > 0) {
      await campLink.click({ force: true });
      await page.waitForTimeout(1500);
    }
  }

  const wrapper = page.locator('.data-table--cards').first();
  await expect(wrapper, 'data-table--cards wrapper not in DOM').toBeAttached();
});
