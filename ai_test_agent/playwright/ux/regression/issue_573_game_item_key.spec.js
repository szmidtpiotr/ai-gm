/**
 * REGRESSION #573 (część 1) — ekwipunek rozwiązuje przedmioty z katalogu (unified game_items).
 * Sama kolumna game_item_key (FK) jest weryfikowana pytestem + odczytem DB; tu sprawdzamy
 * obserwowalny kontrakt: pozycje ekwipunku mają rozwiązane etykiety z katalogu.
 * Acceptance: /api/inventory/{id} zwraca pozycje z niepustymi label/key.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #573 — ekwipunek rozwiązuje etykiety z katalogu", async ({ page }) => {
  const r = await page.request.get("/api/inventory/2");
  expect(r.ok(), "endpoint /inventory nie odpowiada 200").toBeTruthy();
  const body = await r.json();
  const items = (body.data) || [];
  expect(items.length, "ekwipunek pusty").toBeGreaterThan(0);
  for (const it of items) {
    expect(String(it.label || "").length, `pozycja bez etykiety: ${JSON.stringify(it)}`).toBeGreaterThan(0);
    expect(String(it.key || "").length).toBeGreaterThan(0);
  }
});
