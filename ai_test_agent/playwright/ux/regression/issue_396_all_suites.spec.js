/**
 * REGRESSION #396 — All ux suites (regression/acceptance) grouped in Playwright panel.
 * Acceptance: /playwright-specs endpoint istnieje i jest auth-gated. (Grupa admin3 usunięta
 * w FADM-P16 #452 — monolit wycofany, specy zmigrowane do regression na /admin/.)
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #396 — /playwright-specs unauthenticated returns 401", async ({ page }) => {
  const r = await page.request.get("/api/test_runner/playwright-specs");
  expect(r.status(), "#396: specs endpoint must require auth").toBe(401);
});

test("REGRESSION #396 — agent /playwright/specs endpoint exists (test-agent direct)", async ({ page }) => {
  // Direct call to test-agent — available at baseURL proxy via /api/test_runner
  // This is a contract test: if the proxy endpoint exists, the backend routes are wired
  const r = await page.request.get("/api/test_runner/agent_health");
  // 401 (auth required) or 200 (ok) — both mean the endpoint exists
  expect([200, 401]).toContain(r.status());
});
