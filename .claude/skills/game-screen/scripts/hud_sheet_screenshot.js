/**
 * Character sheet HUD screenshot — shows HP/Mana, Gold, XP bar
 * Usage: node hud_sheet_screenshot.js <campaignId>
 */
const { chromium } = require('playwright');
const campaignId = parseInt(process.argv[2] || '1214');

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 430, height: 932 });

  // Login
  await page.goto('http://frontend:80/');
  await page.waitForSelector('#login-username', { timeout: 10000 });
  await page.fill('#login-username', 'demo');
  await page.fill('#login-password', 'demo');
  await page.click('#login-form button');
  await page.waitForTimeout(2500);

  // Enter campaign
  await page.evaluate(async (cid) => {
    const r = await fetch(`/api/campaigns/${cid}`).then(r => r.json());
    if (typeof selectCampaign === 'function') await selectCampaign(r);
  }, campaignId);
  await page.waitForTimeout(4000);

  // Screenshot 1 — game screen (narrative + header HP)
  await page.screenshot({ path: '/tmp/hud_game.png', fullPage: false });

  // Click "Postać" (character sheet) tab
  const tabs = await page.$$('.mbb-btn');
  if (tabs.length >= 2) {
    await tabs[1].click(); // index 1 = Postać
    await page.waitForTimeout(1500);
  }
  await page.screenshot({ path: '/tmp/hud_sheet.png', fullPage: false });

  // Click "Ekwipunek" tab to show gold
  if (tabs.length >= 3) {
    await tabs[2].click(); // index 2 = Ekwipunek
    await page.waitForTimeout(1000);
  }
  await page.screenshot({ path: '/tmp/game_screen_out.png', fullPage: false });

  await browser.close();
})().catch(e => { process.stderr.write('ERROR: ' + e.message + '\n'); process.exit(1); });
