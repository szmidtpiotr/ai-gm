/**
 * REGRESSION #559 (U12) — db_lint endpoint zwraca raport integralności bazy.
 * Acceptance: GET /api/admin/db-lint → 200 z {errors, warnings, exit_code}.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #559 — db-lint endpoint odpowiada 200 z poprawną strukturą", async ({ page }) => {
  const r = await page.request.get("/api/admin/db-lint");
  expect(r.ok(), "endpoint /api/admin/db-lint nie odpowiada 200 (#559)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.errors), "pole 'errors' musi być tablicą (#559)").toBeTruthy();
  expect(Array.isArray(body.warnings), "pole 'warnings' musi być tablicą (#559)").toBeTruthy();
  expect([0, 1, 2], "exit_code musi być 0/1/2 (#559)").toContain(body.exit_code);
});

test("REGRESSION #559 — db-lint exit_code odzwierciedla stan bazy", async ({ page }) => {
  const r = await page.request.get("/api/admin/db-lint");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  // Baza DEV ma znane warnings (efekty konsumable) więc exit_code IN (0, 1)
  // exit_code=2 oznaczałby poważne błędy FK — alertuj w raporcie
  expect(body.exit_code, `Krytyczne błędy FK w bazie DEV: ${JSON.stringify(body.errors)}`).toBeLessThanOrEqual(1);
});
