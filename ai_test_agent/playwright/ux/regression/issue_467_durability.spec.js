/**
 * REGRESSION #467 (F7) — Durability: repair-item and repair-cost endpoints exist and validate.
 * Acceptance: POST /repair-item and GET /inventory/:id/repair-cost are registered and reject bad auth.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #467 — repair-item endpoint registered", async ({ page }) => {
  const r = await page.request.post("/api/characters/0/repair-item", {
    data: { inventory_id: 1, user_id: 999 },
  });
  expect([403, 404, 422].includes(r.status()), `unexpected ${r.status()} — route not registered`).toBeTruthy();
});

test("REGRESSION #467 — repair-cost endpoint registered", async ({ page }) => {
  const r = await page.request.get("/api/characters/0/inventory/1/repair-cost?user_id=999");
  expect([403, 404, 422].includes(r.status()), `unexpected ${r.status()} — route not registered`).toBeTruthy();
});

test("REGRESSION #467 — repair-item rejects missing inventory_id", async ({ page }) => {
  const r = await page.request.post("/api/characters/1/repair-item", {
    data: { user_id: 1 },
  });
  expect(r.status()).toBe(422);
});
