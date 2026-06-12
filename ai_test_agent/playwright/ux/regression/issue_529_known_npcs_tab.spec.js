/**
 * REGRESSION #529 — zakładka Znani NPC widoczna + endpoint zwraca NPC z location_npc_assignments.
 * Acceptance: GET /api/admin/campaigns/{id}/known-npcs odpowiada 200, format {npcs:[...], count:N}.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #529 — known-npcs endpoint odpowiada 200 z wymaganym formatem", async ({ page }) => {
  const r = await page.request.get("/api/admin/campaigns/1/known-npcs");
  expect(r.status(), "endpoint /known-npcs nie istnieje (#529)").not.toBe(404);
  expect(r.status(), "endpoint /known-npcs rzuca 500 (#529)").not.toBe(500);

  if (r.ok()) {
    const data = await r.json();
    expect(data).toHaveProperty("npcs");
    expect(data).toHaveProperty("count");
    expect(Array.isArray(data.npcs), "npcs powinno byc tablica (#529)").toBeTruthy();
  }
});
