/**
 * HUD-focused screenshot — enters campaign and captures full game UI
 * showing HP/Mana, Gold, XP bar, and Quests panel.
 * Usage: node hud_screenshot.js <campaignId>
 */
const { chromium } = require('playwright');
const campaignId = parseInt(process.argv[2] || '999436');

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 420, height: 900 });

  page.on('console', m => {
    if (['error','warning'].includes(m.type()))
      process.stderr.write('PAGE ' + m.type() + ': ' + m.text().slice(0,120) + '\n');
  });

  await page.goto('http://frontend:80/');
  await page.waitForSelector('#login-username', { timeout: 10000 });
  await page.fill('#login-username', 'demo');
  await page.fill('#login-password', 'demo');
  await page.click('#login-form button');
  await page.waitForTimeout(3000);

  // Enter campaign
  await page.evaluate(async (cid) => {
    const camp = await fetch(`/api/campaigns/${cid}`).then(r => r.json());
    if (typeof selectCampaign === 'function') await selectCampaign(camp);
  }, campaignId);
  await page.waitForTimeout(4000);

  // Scroll to top to show HUD
  await page.evaluate(() => {
    const chat = document.getElementById('chat-messages') || document.getElementById('messages') || document.querySelector('.chat');
    if (chat) chat.scrollTop = 0;
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(500);

  await page.screenshot({ path: '/tmp/game_screen_out.png', fullPage: false });
  await browser.close();
})().catch(e => { process.stderr.write('ERROR: ' + e.message + '\n'); process.exit(1); });
