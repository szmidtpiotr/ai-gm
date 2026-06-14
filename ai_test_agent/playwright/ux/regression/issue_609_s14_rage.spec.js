/**
 * REGRESSION #609 (S14) — kondycja `rage` (prymityw condition_immunity + broken_by) jest zaseedowana i aktywna.
 * Acceptance: katalog kondycji gracza zawiera `rage` (Furia) z opisem odporności i bonusu do walki wręcz.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #609 — rage condition seeded & active", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "GET /api/mechanics/conditions nie odpowiada 200 (#609)").toBeTruthy();
  const body = await r.json();
  const list = Array.isArray(body.conditions) ? body.conditions : [];
  const rage = list.find((c) => c.key === "rage");
  expect(rage, "kondycja 'rage' nie istnieje w katalogu (#609)").toBeTruthy();
  expect(rage.label).toBe("Furia");
  // opis musi sygnalizować odporność (immune_to) i bonus do walki wręcz (+3 damage_bonus)
  expect(/odporno/i.test(rage.description || ""), "opis rage bez wzmianki o odporności").toBeTruthy();
  expect(/wręcz/i.test(rage.description || ""), "opis rage bez wzmianki o walce wręcz").toBeTruthy();
});
