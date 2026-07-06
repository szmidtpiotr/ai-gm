/**
 * REGRESSION #1167/#1188 — Warsztat kampanii RESTORE, Bank Pomysłów RETIRE.
 * Acceptance: /api/admin/campaigns/{id}/workshop/message już nie jest 404
 * (router zarejestrowany); /api/admin/ideas* zniknął (Bank retired → 404).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1167 — Warsztat kampanii zarejestrowany (nie 404)", async ({ page }) => {
  // Bez tokenu → 401/403/422, ale NIGDY 404 (route istnieje).
  const r = await page.request.post("/api/admin/campaigns/1/workshop/message", {
    data: { message: "ping" },
  });
  expect(r.status(), "Warsztat message endpoint nie może być 404 (#1167)").not.toBe(404);
  expect([401, 403, 422, 400, 200, 500]).toContain(r.status());
});

test("REGRESSION #1188 — Bank Pomysłów wycofany (/api/admin/ideas → 404)", async ({ page }) => {
  const r = await page.request.get("/api/admin/ideas");
  expect(r.status(), "Bank Pomysłów powinien być retired (404)").toBe(404);
});
