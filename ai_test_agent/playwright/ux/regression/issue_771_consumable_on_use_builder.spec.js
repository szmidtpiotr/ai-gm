/**
 * REGRESSION #771 — Consumable on-use effect builder: damage_enemy + apply_condition(target).
 * Acceptance: migracja effect_json przeszła; backend nie crashuje na use konsumabla;
 * endpoint /api/inventory/{cid}/use istnieje i zwraca sensowny błąd nie 500.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #771 — backend healthy after consumable migration (pending enemies OK)", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/pending/enemies");
  expect(r.ok(), "backend not OK after consumable migration — pending/enemies 500 (#771)").toBeTruthy();
});

test("REGRESSION #771 — inventory use endpoint does not crash (returns 404/400 not 500)", async ({ page }) => {
  // POST with nonexistent ids → 404, NOT 500 crash (which would indicate dispatch bug)
  const r = await page.request.post("/api/inventory/999999/use", {
    data: { inventory_id: 999999 },
  });
  expect(r.status(), "inventory use endpoint returned 500 — consumable dispatch crash (#771)").not.toBe(500);
  expect([400, 404, 422].includes(r.status()), "expected 400/404/422 for nonexistent item (#771)").toBeTruthy();
});

test("REGRESSION #771 — health endpoint OK after migration", async ({ page }) => {
  const r = await page.request.get("/api/healthz");
  expect(r.ok(), "healthz not OK (#771 migration side effect guard)").toBeTruthy();
});
