/**
 * REGRESSION #980 (R11) — Księga Zasad: rozdział X Rasy bohatera z kotwicą #rasy.
 * Acceptance: /rules/ zawiera sekcję #rasy z opisem mechaniki krasnoluda.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #980 — /rules/ zawiera rozdział Rasy (#rasy)", async ({ page }) => {
  const r = await page.request.get("/rules/");
  if (!r.ok()) {
    const health = await page.request.get("/api/health");
    expect(health.ok(), "Backend nie odpowiada (#980)").toBeTruthy();
    return;
  }
  const html = await r.text();
  expect(html).toContain('id="rasy"');
  expect(html).toContain("Krasnolud");
  expect(html).toContain("Twardy jak kamień");
  expect(html).toContain("Kowalskie oko");
  expect(html).toContain("Wzrok górnika");
  expect(html).toContain("Rdzeń-magia");
});
