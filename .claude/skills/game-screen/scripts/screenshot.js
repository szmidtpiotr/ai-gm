/**
 * game-screen Playwright screenshot script.
 *
 * Usage: node screenshot.js <mode> [campaignId]
 *   mode: heroes | campaign | death | login
 *   campaignId: numeric campaign id (for campaign/death modes)
 *
 * Output: writes PNG to /tmp/game_screen_out.png
 */

const { chromium } = require('playwright');

const mode = process.argv[2] || 'heroes';
const campaignId = process.argv[3] ? parseInt(process.argv[3]) : null;

(async () => {
  const browser = await chromium.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 900 });

  page.on('console', m => {
    if (['error', 'warning'].includes(m.type())) {
      process.stderr.write('PAGE ' + m.type() + ': ' + m.text().slice(0, 120) + '\n');
    }
  });

  await page.goto('http://frontend:80/');

  if (mode === 'login') {
    await page.waitForSelector('#login-username', { timeout: 10000 });
    await page.screenshot({ path: '/tmp/game_screen_out.png' });
    await browser.close();
    return;
  }

  // Login
  await page.waitForSelector('#login-username', { timeout: 10000 });
  await page.fill('#login-username', 'demo');
  await page.fill('#login-password', 'demo');
  await page.click('#login-form button');
  await page.waitForTimeout(3000);

  if (mode === 'heroes' || !campaignId) {
    // Already on heroes screen after login
    await page.waitForTimeout(500);
    await page.screenshot({ path: '/tmp/game_screen_out.png' });
    await browser.close();
    return;
  }

  // Enter campaign
  await page.evaluate(async (cid) => {
    window.currentCampaignId = cid;
    const camp = await fetch(`/api/campaigns/${cid}`).then(r => r.json());
    window.currentCampaign = camp;
    if (typeof selectCampaign === 'function') {
      await selectCampaign(camp);
    }
  }, campaignId);
  await page.waitForTimeout(3000);

  if (mode === 'death') {
    // Force death screen (campaign must be ended)
    await page.evaluate(async (cid) => {
      window.currentCampaignId = cid;
      if (typeof showDeathScreen === 'function') {
        await showDeathScreen(window.characterData?.name || 'Bohater');
      }
    }, campaignId);
    await page.waitForTimeout(2000);
  }

  await page.screenshot({ path: '/tmp/game_screen_out.png' });
  await browser.close();
})().catch(e => {
  process.stderr.write('ERROR: ' + e.message + '\n');
  process.exit(1);
});
