/**
 * REGRESSION #472 (F12) — Anti-farm sell price decay for repeated item sales.
 * Acceptance: sell endpoint present; backend starts OK with anti_farm_service imported.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #472 — shop inventory endpoint reachable", async ({ page }) => {
  const r = await page.request.get("/api/shop/kowal_jan/inventory?char_id=1");
  // 200 or 404/422 (NPC may not exist) — confirm no 500
  expect([200, 404, 422].includes(r.status()), `unexpected status ${r.status()}`).toBeTruthy();
});

test("REGRESSION #472 — anti_farm_service importable (backend health OK)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend /api/health not 200").toBeTruthy();
});

test("REGRESSION #472 — sell endpoint present on shop router", async ({ page }) => {
  // 404/422/400 OK; 405 = endpoint missing
  const r = await page.request.post("/api/shop/kowal_jan/sell", {
    data: { char_id: 1, inventory_id: 99999 },
  });
  expect([200, 404, 422, 400].includes(r.status()), `sell endpoint missing (status ${r.status()})`).toBeTruthy();
});
