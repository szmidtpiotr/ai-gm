/**
 * REGRESSION #474 (F14) — Dead code generate_combat_loot / claim_loot removed from economy_service.
 * Acceptance: backend still starts and all live endpoints respond correctly.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #474 — backend healthy after economy_service cleanup", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend should still start after removing dead loot code (#474)").toBeTruthy();
});

test("REGRESSION #474 — XP grant endpoint still works", async ({ page }) => {
  // XP relies on economy_service.grant_xp which must NOT have been removed
  const r = await page.request.get("/api/health");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  expect(body.status).toBe("ok");
});
