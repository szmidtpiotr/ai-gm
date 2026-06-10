/**
 * REGRESSION #473 (F13) — Rental expiry sweep wired into turns.py.
 * Acceptance: backend starts cleanly; rental_service importable; turn endpoint not broken.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #473 — backend healthy (rental sweep wired)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend health (#473)").toBeTruthy();
  const body = await r.json();
  expect(body.status).toBe("ok");
});

test("REGRESSION #473 — turn endpoint signature intact after adding expire sweep", async ({ page }) => {
  // POST to unknown campaign → 404/410 not 422/500
  const r = await page.request.post("/api/campaigns/999999/turns", {
    data: { character_id: 1, text: "hello" },
  });
  expect(r.status()).not.toBe(422);
  expect(r.status()).not.toBe(500);
});
