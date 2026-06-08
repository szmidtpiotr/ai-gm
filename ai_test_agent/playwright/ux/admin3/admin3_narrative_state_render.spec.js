/**
 * REGRESSION #381 (D6) — blok "Narrative State" RENDERUJE się w admin3.
 * Loguje do admin3, otwiera kampanię z zaseedowanym narrative_state i sprawdza, że
 * blok 📖 Narrative State pojawia się w DOM zakładek 🌍 Stan Świata oraz 🔍 Inspector.
 * Wymaga danych narrative_state w kampanii CAMPAIGN_ID (demo seed dla 1202).
 */
const { test, expect } = require("@playwright/test");

const ADMIN_USER = process.env.AI_TEST_ADMIN_USER || "ai_test_player";
const ADMIN_PASS = process.env.AI_TEST_ADMIN_PASS || "demo";
const CAMPAIGN_ID = 1202;

async function adminLogin(page) {
  await page.goto("/admin3/");
  await page.waitForSelector("#login-overlay.open", { timeout: 15000 });
  await page.fill("#login-user", ADMIN_USER);
  await page.fill("#login-pass", ADMIN_PASS);
  await page.click("#login-submit");
  await page.locator("#login-overlay").waitFor({ state: "hidden", timeout: 20000 });
}

test("REGRESSION #381 — Narrative State widoczny w Stan Świata i Inspector", async ({ page }) => {
  await adminLogin(page);

  // Otwórz modal kampanii bezpośrednio (globalna funkcja admin3).
  await page.evaluate(async (id) => { await window.openCampaignModal(id); }, CAMPAIGN_ID);
  await page.waitForTimeout(500);

  // 🌍 Stan Świata
  await page.click('[data-ctab="world"]');
  await expect(page.locator('#ctab-world')).toContainText('Narrative State', { timeout: 15000 });
  await expect(page.locator('#ctab-world')).toContainText('Aldric', { timeout: 5000 });

  // 🔍 Inspector
  await page.click('[data-ctab="inspector"]');
  await expect(page.locator('#ctab-inspector')).toContainText('Narrative State', { timeout: 15000 });
  await expect(page.locator('#ctab-inspector')).toContainText('Aldric', { timeout: 5000 });
});
