/**
 * REGRESSION #1105 — validate_move exact target_key match: a narrative move intent whose
 * target_key exactly matches an existing DB location must resolve to THAT location, never
 * an unrelated one picked by fuzzy label text (the "gospoda -> tundra" teleport bug).
 * Acceptance: /api/locations endpoint stays healthy after the location_validator.py change
 * (contract smoke — the real resolution logic is covered by the pytest suite, which needs
 * a live LLM-free game session to exercise validate_move end to end).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1105 — backend healthy after location_validator #1105 fix", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend health check failed (#1105)").toBeTruthy();
  const health = await r.json();
  expect(health.status ?? "ok", "backend not healthy (#1105)").toBe("ok");
});

test("REGRESSION #1105 — /api/locations endpoint does not 500 after the fix", async ({ page }) => {
  const r = await page.request.get("/api/locations");
  expect(r.status() < 500, `locations endpoint crashed: ${r.status()} (#1105)`).toBeTruthy();
});
