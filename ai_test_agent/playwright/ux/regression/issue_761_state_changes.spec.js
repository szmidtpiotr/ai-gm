/**
 * REGRESSION #761 — rejestr zmian zasobów/kondycji (state_changes).
 * Acceptance: endpoint GET /api/campaigns/{id}/state-changes odpowiada 200 ze strukturą,
 * filtr resource respektowany.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #761 — state-changes zwraca strukturę", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1/state-changes?limit=5");
  expect(r.ok(), "state-changes nie odpowiada 200 (#761)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.state_changes)).toBeTruthy();
});

test("REGRESSION #761 — filtr resource respektowany", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1/state-changes?resource=hp&limit=10");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  for (const c of body.state_changes) expect(c.resource).toBe("hp");
});
