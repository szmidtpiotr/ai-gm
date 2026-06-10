/**
 * End screen screenshot — shows campaign end summary + epitaph
 */
const { chromium } = require('playwright');
const campaignId = parseInt(process.argv[2] || '999435');

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 900 });

  // Login
  await page.goto('http://frontend:80/');
  await page.waitForSelector('#login-username', { timeout: 10000 });
  await page.fill('#login-username', 'demo');
  await page.fill('#login-password', 'demo');
  await page.click('#login-form button');
  await page.waitForTimeout(3000);

  // Enter campaign
  await page.evaluate(async (cid) => {
    const r = await fetch(`/api/campaigns/${cid}`).then(r => r.json());
    if (typeof selectCampaign === 'function') await selectCampaign(r);
  }, campaignId);
  await page.waitForTimeout(4000);

  // Wait for end screen to appear (should auto-show for finished campaigns)
  await page.waitForSelector('[id*="end"], [class*="end"], [data-screen*="end"], .death-screen, .campaign-end, #campaign-complete', { timeout: 5000 }).catch(() => null);

  await page.screenshot({ path: '/tmp/game_screen_out.png', fullPage: false });
  await browser.close();
})().catch(e => { process.stderr.write('ERROR: ' + e.message + '\n'); process.exit(1); });
