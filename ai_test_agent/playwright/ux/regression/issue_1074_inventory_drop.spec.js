/**
 * REGRESSION #1074 — Wyrzucanie przedmiotów z plecaka + potwierdzenie.
 * Acceptance: Przedmioty w Plecaku mają przycisk "Wyrzuć" (data-action="drop");
 * API DELETE /inventory/{char}/{inv} działa poprawnie.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

// A. API smoke — DELETE endpoint reachable
test("REGRESSION #1074 (A) — DELETE /inventory endpoint responds", async ({ page }) => {
  const r = await page.request.delete(`${BASE}/api/inventory/9999999/9999999`);
  expect([400, 404].includes(r.status()), `Expected 400/404, got ${r.status()}`).toBeTruthy();
});

// B. GET /inventory returns array with proper structure
test("REGRESSION #1074 (B) — GET /inventory returns item array", async ({ page }) => {
  const loginResp = await page.request.post(`${BASE}/api/auth/login`, {
    data: { username: "demo", password: "demo" },
  });
  if (!loginResp.ok()) { test.skip(true, "demo login unavailable"); return; }
  const loginData = await loginResp.json();
  const token = loginData?.access_token || loginData?.data?.access_token;
  if (!token) { test.skip(true, "no token"); return; }

  const charsResp = await page.request.get(`${BASE}/api/characters/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!charsResp.ok()) { test.skip(true, "no characters"); return; }
  const chars = await charsResp.json();
  const charId = Array.isArray(chars?.data) ? chars.data[0]?.id :
                 Array.isArray(chars) ? chars[0]?.id : null;
  if (!charId) { test.skip(true, "no character"); return; }

  const invResp = await page.request.get(`${BASE}/api/inventory/${charId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(invResp.ok(), "Inventory endpoint must succeed").toBeTruthy();
  const inv = await invResp.json();
  expect(Array.isArray(inv?.data), "inv.data must be array").toBeTruthy();
});

// C. UI: backpack rows must have drop button — FAILS before fix
test("REGRESSION #1074 (C) — Backpack items have [data-action=drop] button", async ({ page }) => {
  await page.goto(`${BASE}/`);

  // Wait for login screen
  await page.waitForSelector("#login-screen.screen--active, #login-screen, .login-form", { timeout: 15000 });

  // Fill login form
  await page.locator("#login-username, input[name='username'], input[placeholder*='login']").first().fill("demo");
  await page.locator("#login-password, input[type='password']").first().fill("demo");
  await page.locator("#login-form button[type='submit'], button:has-text('Zaloguj')").first().click();

  // Wait for post-login screen (heroes, campaigns, or game)
  await page.waitForFunction(
    () => {
      const ids = ["heroes-screen", "campaigns-screen", "game-screen", "onboarding-screen"];
      return ids.some(id => document.getElementById(id)?.classList.contains("screen--active"));
    },
    null,
    { timeout: 25000 }
  );

  // Skip onboarding if present
  const cta = page.locator("#onboarding-cta");
  if (await cta.isVisible({ timeout: 2000 }).catch(() => false)) {
    await cta.click();
    const start = page.locator("#onboarding-start");
    if (await start.isVisible({ timeout: 3000 }).catch(() => false)) await start.click();
  }

  // Navigate through heroes → campaigns → game if needed
  const heroScreen = page.locator("#heroes-screen.screen--active");
  if (await heroScreen.isVisible({ timeout: 2000 }).catch(() => false)) {
    const heroCard = page.locator(".hero-card").first();
    await heroCard.waitFor({ state: "visible", timeout: 10000 });
    await heroCard.click();
    const idleBtn = page.locator("#idle-hero-panel-proceed");
    if (await idleBtn.isVisible({ timeout: 3000 }).catch(() => false)) await idleBtn.click();
  }

  const campScreen = page.locator("#campaigns-screen.screen--active");
  if (await campScreen.isVisible({ timeout: 3000 }).catch(() => false)) {
    const campCard = page.locator("button.campaign-card").first();
    await campCard.waitFor({ state: "visible", timeout: 10000 });
    await campCard.click();
  }

  // Wait for game screen
  await page.waitForSelector("#game-screen.screen--active", { timeout: 30000 });
  await page.waitForSelector("#send-btn", { state: "visible", timeout: 15000 });

  // Open character sheet
  const sheetBtnSel = '[data-action="open-sheet"], .hud__sheet-btn, #sheet-btn, button[title*="Postać"]';
  const sheetBtn = page.locator(sheetBtnSel).first();
  await sheetBtn.waitFor({ state: "visible", timeout: 10000 });
  await sheetBtn.click();
  await page.waitForTimeout(600);

  // Switch to inventory tab
  const invTabSel = '[data-sheet-tab="inventory"], [data-tab="inventory"], button:has-text("Ekwipunek"), button:has-text("Plecak")';
  const invTab = page.locator(invTabSel).first();
  if (await invTab.isVisible({ timeout: 2000 }).catch(() => false)) {
    await invTab.click();
    await page.waitForTimeout(600);
  }

  // Backpack list must be in DOM
  const backpack = page.locator('#sheet-backpack');
  await expect(backpack).toBeAttached({ timeout: 5000 });

  // Get backpack row count
  const rows = backpack.locator('.inv-row');
  const rowCount = await rows.count();

  if (rowCount === 0) {
    // Try to add an item via admin cheat
    await page.locator('#chat-input').fill('/add health_potion 1').catch(() => {});
    await page.locator('#send-btn').click().catch(() => {});
    await page.waitForTimeout(2500);
    // Re-click inventory tab to refresh
    if (await invTab.isVisible({ timeout: 1000 }).catch(() => false)) {
      await invTab.click();
      await page.waitForTimeout(600);
    }
  }

  const finalRowCount = await rows.count();
  if (finalRowCount === 0) {
    test.skip(true, "No backpack items available for this hero");
    return;
  }

  // KEY CHECK: backpack rows must have drop buttons
  const dropBtns = backpack.locator('[data-action="drop"]');
  const dropCount = await dropBtns.count();
  expect(
    dropCount,
    `No [data-action=drop] buttons found in #sheet-backpack (${finalRowCount} rows present). Fix: add drop button to _renderBackpackRow() in game.js (#1074)`
  ).toBeGreaterThan(0);
});
