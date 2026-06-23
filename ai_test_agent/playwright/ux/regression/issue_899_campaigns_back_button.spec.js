/**
 * REGRESSION #899 (FIX) — Back button on campaigns screen navigates to heroes list.
 * Acceptance: clicking ← on campaigns screen returns to heroes screen without logout.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #899 — campaigns screen has back button element in DOM", async ({ page }) => {
  await page.goto("/");

  // Login
  await page.waitForSelector("#login-username", { timeout: 10000 });
  await page.fill("#login-username", "demo");
  await page.fill("#login-password", "demo");
  await page.click("#login-form button");
  await page.waitForTimeout(2000);

  // Click first hero to reach campaigns screen
  await page.click(".hero-card", { timeout: 8000 });
  await page.waitForTimeout(1500);

  // campaigns-back button must exist and be visible
  const backBtn = page.locator("#campaigns-back");
  await expect(backBtn, "#campaigns-back button not found on campaigns screen (#899)").toBeVisible({ timeout: 5000 });

  // button must have header__back class (pattern consistency)
  await expect(backBtn).toHaveClass(/header__back/);
});

test("REGRESSION #899 — clicking back button returns to heroes screen", async ({ page }) => {
  await page.goto("/");

  // Login
  await page.waitForSelector("#login-username", { timeout: 10000 });
  await page.fill("#login-username", "demo");
  await page.fill("#login-password", "demo");
  await page.click("#login-form button");
  await page.waitForTimeout(2000);

  // Navigate to campaigns
  await page.click(".hero-card", { timeout: 8000 });
  await page.waitForTimeout(1500);

  // Verify on campaigns screen
  await expect(page.locator("#campaigns-screen")).toBeVisible({ timeout: 5000 });

  // Click back
  await page.click("#campaigns-back");
  await page.waitForTimeout(1000);

  // Must be back on heroes screen, not logged out
  await expect(page.locator("#heroes-screen"), "heroes screen not visible after clicking back (#899)").toBeVisible({ timeout: 5000 });
  await expect(page.locator("#login-screen"), "ended up on login screen — regression: back triggered logout").toBeHidden();
});
