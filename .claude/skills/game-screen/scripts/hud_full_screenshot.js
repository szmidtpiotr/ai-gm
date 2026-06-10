/**
 * Full HUD screenshot — shows HP/Mana, Gold, XP bar, Quests panel
 * Usage: node hud_full_screenshot.js <campaignId>
 */
const { chromium } = require('playwright');
const campaignId = parseInt(process.argv[2] || '1214');

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 430, height: 932 });

  page.on('console', m => {
    if (['error','warning'].includes(m.type()))
      process.stderr.write('PAGE ' + m.type() + ': ' + m.text().slice(0,180) + '\n');
  });

  // Login
  await page.goto('http://frontend:80/');
  await page.waitForSelector('#login-username', { timeout: 10000 });
  await page.fill('#login-username', 'demo');
  await page.fill('#login-password', 'demo');
  await page.click('#login-form button');
  await page.waitForTimeout(3000);

  // Enter campaign via API
  await page.evaluate(async (cid) => {
    const r = await fetch(`/api/campaigns/${cid}`).then(r => r.json());
    if (typeof selectCampaign === 'function') await selectCampaign(r);
  }, campaignId);
  await page.waitForTimeout(4000);

  // Main screenshot
  await page.screenshot({ path: '/tmp/game_screen_out.png', fullPage: false });

  // Log all IDs/classes that might be HUD elements
  const hudInfo = await page.evaluate(() => {
    const els = document.querySelectorAll('[id*="hp"], [id*="mana"], [id*="gold"], [id*="xp"], [id*="quest"], [class*="hud"], [class*="stat-bar"], [class*="xp"]');
    return Array.from(els).map(e => `${e.tagName}#${e.id}.${e.className.trim().replace(/\s+/g,' ')} text="${e.textContent.trim().slice(0,40)}"`);
  });
  process.stderr.write('HUD elements:\n' + hudInfo.join('\n') + '\n');

  // Try quests button
  const btns = await page.evaluate(() => {
    const all = document.querySelectorAll('button');
    return Array.from(all).map(b => `#${b.id} class="${b.className}" text="${b.textContent.trim().slice(0,30)}"`);
  });
  process.stderr.write('Buttons:\n' + btns.join('\n') + '\n');

  await browser.close();
})().catch(e => { process.stderr.write('ERROR: ' + e.message + '\n'); process.exit(1); });
