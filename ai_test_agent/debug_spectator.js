const { chromium } = require('./node_modules/playwright');

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  const consoleLogs = [];
  page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
  
  const networkReqs = [];
  page.on('request', req => {
    if (req.url().includes('/api/')) {
      networkReqs.push(`REQ: ${req.method()} ${req.url().replace('http://frontend:80', '')}`);
    }
  });
  page.on('response', async resp => {
    if (resp.url().includes('/api/')) {
      networkReqs.push(`RES: ${resp.status()} ${resp.url().replace('http://frontend:80', '')}`);
    }
  });

  console.log('Navigating to admin2...');
  await page.goto('http://frontend:80/admin2/', { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(2000);
  console.log('Page title:', await page.title());
  
  // Find and click analytics
  const navLinks = await page.$$('nav a, .sidebar a, [data-section]');
  console.log('Nav links found:', navLinks.length);
  for (const link of navLinks) {
    const txt = await link.textContent().catch(() => '');
    const ds = await link.getAttribute('data-section').catch(() => '');
    if (txt.includes('nalyt') || ds.includes('nalyt')) {
      await link.click();
      console.log('Clicked analytics nav');
      break;
    }
  }
  await page.waitForTimeout(1000);
  
  // Find MCP tab
  const allBtns = await page.$$('button, .tab-btn, [data-tab]');
  for (const btn of allBtns) {
    const txt = await btn.textContent().catch(() => '');
    if (txt.trim() === 'MCP' || txt.includes('MCP')) {
      await btn.click();
      console.log('Clicked MCP tab');
      break;
    }
  }
  
  await page.waitForTimeout(6000); // Wait for iframe + demo init
  
  // Check diag bar
  const diagText = await page.$eval('#mcp-diag-bar', el => el.textContent).catch(() => 'NOT FOUND');
  console.log('Diag bar:', diagText);
  
  // Check iframe
  const iframeEl = await page.$('#mcp-player-iframe');
  if (iframeEl) {
    const frame = await iframeEl.contentFrame().catch(() => null);
    if (frame) {
      const screenId = await frame.evaluate(() => {
        const active = document.querySelector('.screen--active');
        return active ? active.id : 'none';
      }).catch(e => `err: ${e.message}`);
      console.log('Iframe screen:', screenId);
      
      const chatCount = await frame.evaluate(() => {
        const el = document.getElementById('chat-messages');
        return el ? el.children.length : -1;
      }).catch(e => `err: ${e.message}`);
      console.log('Chat message count:', chatCount);
      
      const heroName = await frame.evaluate(() => {
        return document.getElementById('character-name-display')?.textContent || 'N/A';
      }).catch(() => 'N/A');
      console.log('Hero name:', heroName);
      
      // Get localStorage
      const ls = await frame.evaluate(() => ({
        token: localStorage.getItem('token') ? 'SET' : 'MISSING',
        aigm_access_token: localStorage.getItem('aigm_access_token') ? 'SET' : 'MISSING',
        aigm_hero_id: localStorage.getItem('aigm_hero_id'),
        aigm_campaign_id: localStorage.getItem('aigm_campaign_id'),
      })).catch(e => `err: ${e.message}`);
      console.log('localStorage:', JSON.stringify(ls));
    } else {
      console.log('Could not get iframe frame');
    }
  } else {
    console.log('No iframe found');
  }
  
  console.log('\n=== CONSOLE LOGS ===');
  consoleLogs.forEach(l => console.log(l));
  
  console.log('\n=== NETWORK ===');
  networkReqs.forEach(r => console.log(r));
  
  await browser.close();
}

main().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
