/**
 * Wizard step screenshots — verify inline descriptions (no tooltip popups)
 */
const { chromium } = require('playwright');

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

  // Click "Nowy Bohater" to start wizard
  await page.waitForSelector('#new-hero-btn', { timeout: 6000 });
  await page.click('#new-hero-btn');
  await page.waitForTimeout(1500);

  // Screenshot step 1 BEFORE fill
  await page.screenshot({ path: '/tmp/wiz_step1.png', fullPage: false });

  // Fill required fields (name + select archetype)
  const nameInput = await page.$('#wizard-hero-name, input[placeholder*="Aldric"], input[placeholder*="imię"]');
  if (nameInput) {
    await nameInput.fill('Test Bohater');
    process.stderr.write('Name filled\n');
  }

  // Select Wojownik archetype if not selected
  const archCard = await page.$('.archetype-card:first-child, .wizard-archetype-card:first-child');
  if (archCard) { await archCard.click(); }
  await page.waitForTimeout(300);

  // Advance to step 2 (stats)
  await page.click('#wizard-next');
  await page.waitForTimeout(2500);

  const step = await page.evaluate(() => {
    const h = document.querySelector('.wizard-step-indicator, [class*="step"]');
    return h ? h.textContent.trim() : 'unknown';
  });
  process.stderr.write('After next: ' + step + '\n');

  await page.screenshot({ path: '/tmp/wiz_step2.png', fullPage: false });

  // Check if we're on step 2
  const statsVisible = await page.$('.wizard-stat-row') !== null;
  process.stderr.write('Stats visible: ' + statsVisible + '\n');

  // Advance to step 3 (skills)
  const nextBtn = await page.$('#wizard-next');
  if (nextBtn) {
    await nextBtn.click();
    await page.waitForTimeout(2500);
    await page.screenshot({ path: '/tmp/game_screen_out.png', fullPage: false });
    process.stderr.write('Step 3 done\n');
  }

  await browser.close();
})().catch(e => { process.stderr.write('ERROR: ' + e.message + '\n'); process.exit(1); });
