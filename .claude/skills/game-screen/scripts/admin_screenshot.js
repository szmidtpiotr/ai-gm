/**
 * Admin panel screenshot — navigates to a specific campaign tab.
 * Usage: node admin_screenshot.js <campaignId> [tab]
 *   tab: plan | turns | overview | map | warsztat (default: plan)
 * Output: /tmp/game_screen_out.png
 */

const { chromium } = require('playwright');

const campaignId = process.argv[2] ? parseInt(process.argv[2]) : null;
const tab = process.argv[3] || 'plan';

if (!campaignId) {
  process.stderr.write('Usage: node admin_screenshot.js <campaignId> [tab]\n');
  process.exit(1);
}

(async () => {
  const browser = await chromium.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1400, height: 900 });

  page.on('console', m => {
    if (['error', 'warning'].includes(m.type())) {
      process.stderr.write('PAGE ' + m.type() + ': ' + m.text().slice(0, 200) + '\n');
    }
  });

  // Go to admin panel
  await page.goto('http://frontend:80/admin/');
  await page.waitForTimeout(2000);

  // Login if needed
  const loginInput = page.locator('#admin-login-username, input[name="username"], input[placeholder*="login"], input[placeholder*="Login"]').first();
  const loginVisible = await loginInput.isVisible().catch(() => false);
  if (loginVisible) {
    await loginInput.fill('admin');
    const passInput = page.locator('#admin-login-password, input[type="password"]').first();
    await passInput.fill('admin');
    const loginBtn = page.locator('button[type="submit"], .login-btn, button:has-text("Zaloguj"), button:has-text("Login")').first();
    await loginBtn.click();
    await page.waitForTimeout(2000);
  }

  // Navigate to campaigns section
  const campaignsNav = page.locator('[data-section="campaigns"], nav a:has-text("Kampanie"), .nav-item:has-text("Kampanie")').first();
  await campaignsNav.click().catch(async () => {
    // Try hash navigation
    await page.goto('http://frontend:80/admin/#campaigns');
  });
  await page.waitForTimeout(2000);

  // Find and click the campaign card
  // Try to find campaign by id - click the kebab/details button or card itself
  const campaignCard = page.locator(`[data-campaign-id="${campaignId}"], .campaign-card[data-id="${campaignId}"]`).first();
  const cardVisible = await campaignCard.isVisible().catch(() => false);

  if (cardVisible) {
    await campaignCard.click();
  } else {
    // Try clicking any button with the campaign id
    const detailBtn = page.locator(`button[data-id="${campaignId}"], [data-campaign="${campaignId}"]`).first();
    await detailBtn.click().catch(() => {});
  }
  await page.waitForTimeout(2000);

  // Click the target tab
  const tabMap = {
    plan: ['Plan GM', 'plan', 'Plan'],
    turns: ['Tury', 'turns'],
    overview: ['Przegląd', 'overview'],
    map: ['Mapa', 'map'],
    warsztat: ['Warsztat', 'warsztat'],
  };
  const tabLabels = tabMap[tab] || [tab];

  for (const label of tabLabels) {
    const tabBtn = page.locator(`.modal-tab[data-tab="${label}"], button.tab:has-text("${label}"), [role="tab"]:has-text("${label}"), .tab-btn:has-text("${label}")`).first();
    const tabVisible = await tabBtn.isVisible().catch(() => false);
    if (tabVisible) {
      await tabBtn.click();
      await page.waitForTimeout(1500);
      break;
    }
  }

  await page.waitForTimeout(1000);
  await page.screenshot({ path: '/tmp/game_screen_out.png', fullPage: false });
  await browser.close();
})().catch(e => {
  process.stderr.write('ERROR: ' + e.message + '\n');
  process.exit(1);
});
