/**
 * REGRESSION #608 (S13) — kondycja `blessed` (prymityw on_zero_hp_save) jest zaseedowana i aktywna.
 * Acceptance: katalog kondycji gracza zawiera `blessed` (Pobłogosławiony) z opisem ratunku przy 0 HP.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #608 — blessed condition seeded & active", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "GET /api/mechanics/conditions nie odpowiada 200 (#608)").toBeTruthy();
  const body = await r.json();
  const list = Array.isArray(body.conditions) ? body.conditions : [];
  const blessed = list.find((c) => c.key === "blessed");
  expect(blessed, "kondycja 'blessed' nie istnieje w katalogu (#608)").toBeTruthy();
  expect(blessed.label).toBe("Pobłogosławiony");
  // opis musi sygnalizować mechanikę rzutu ratunkowego przy 0 HP (1 HP zamiast nieprzytomności)
  expect(/1 HP/i.test(blessed.description || ""), "opis blessed bez wzmianki o ratunku na 1 HP").toBeTruthy();
});
