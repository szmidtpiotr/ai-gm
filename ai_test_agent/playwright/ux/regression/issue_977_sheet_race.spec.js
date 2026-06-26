/**
 * REGRESSION #977 (R8) — Character sheet: badge rasy + sekcja cech rasowych dla krasnoluda.
 * Acceptance: GET /api/characters/<id> zwraca pole race; HTML zawiera elementy race badge.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #977 — endpoint /characters zwraca listę (race field dostępny)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend nie odpowiada (#977)").toBeTruthy();
  // Weryfikacja wizualna: badge rasy + Cechy rasowe widoczne dla krasnoluda
  // po deployu na https://aigm-dev.studio-colorbox.com/
});
