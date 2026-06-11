/**
 * REGRESSION #468 (F8) — Robbery encounter: robbery_service deployed, gold steal works.
 * Acceptance: robbery config readable (health check), endpoints not broken after addition.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #468 — backend healthy after robbery_service deployment", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend not healthy — robbery_service may have caused import error").toBeTruthy();
});

test("REGRESSION #468 — repair-item endpoint not broken by robbery_service addition", async ({ page }) => {
  const r = await page.request.post("/api/characters/0/repair-item", {
    data: { inventory_id: 1, user_id: 999 },
  });
  expect([403, 404, 422].includes(r.status()), `characters router broken — got ${r.status()}`).toBeTruthy();
});

test("REGRESSION #468 — craft apply-affix endpoint not broken by robbery_service addition", async ({ page }) => {
  const r = await page.request.post("/api/characters/0/craft/apply-affix", {
    data: { inventory_id: 1, tier: 1, user_id: 999 },
  });
  expect([403, 404, 422].includes(r.status()), `craft endpoint broken — got ${r.status()}`).toBeTruthy();
});
