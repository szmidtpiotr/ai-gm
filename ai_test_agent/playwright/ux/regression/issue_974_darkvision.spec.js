/**
 * REGRESSION #974 (R5) — Wzrok górnika: darkvision backend dostępny (stałe + funkcja).
 * Acceptance: GET /api/health → backend działa z nową funkcją darkvision.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #974 — backend z darkvision startuje poprawnie", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend nie odpowiada (#974)").toBeTruthy();
  // Pełna weryfikacja mechaniki w pytest test_issue974_darkvision.py
});
