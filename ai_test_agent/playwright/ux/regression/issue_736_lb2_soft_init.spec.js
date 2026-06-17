/**
 * REGRESSION #736 (LB2) — soft-init: backend startuje poprawnie po zmianie combat_service.
 * Acceptance: /api/health zwraca status ok; dungeon module załadowany (brak ImportError).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #736 LB2 — backend healthy po deploy soft-init", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "GET /api/health powinien odpowiadać 200 (#736)").toBeTruthy();
  const body = await r.json();
  expect(body.status, "status powinien być 'ok'").toBe("ok");
});
