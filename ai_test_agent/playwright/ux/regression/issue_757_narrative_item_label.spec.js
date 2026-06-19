/**
 * REGRESSION #757 — plecak pokazuje nazwę narracyjnego przedmiotu, nie surowy klucz.
 * Acceptance: żaden wiersz inventory char 999420 (Mizel) nie ma label = 'narrative_item_*';
 * przedmiot id 485 (#99791) rozwiązuje się do czytelnej nazwy. Read-only GET (bez zmian stanu).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #757 — inventory label nie jest surowym kluczem narrative_item_*", async ({ page }) => {
  const r = await page.request.get("/api/inventory/999420");
  expect(r.ok(), "endpoint inventory nie odpowiada 200 (#757)").toBeTruthy();
  const body = await r.json();
  expect(body.ok, "odpowiedź inventory ok=false (#757)").toBeTruthy();
  const items = Array.isArray(body.data) ? body.data : [];

  // Żaden label nie może być surowym kluczem slug.
  const leaked = items.filter(it => /^narrative_item_/.test(String(it.label || "")));
  expect(
    leaked.length,
    `wycieka surowy klucz zamiast nazwy: ${leaked.map(i => i.label).join(", ")}`
  ).toBe(0);

  // Item id 485 (jeśli nadal w plecaku) — label musi być czytelny, nie klucz.
  const it485 = items.find(it => Number(it.id) === 485);
  if (it485) {
    expect(String(it485.label || ""), "id 485 nadal pokazuje surowy klucz").not.toMatch(/^narrative_item_/);
    expect(String(it485.label || "").trim().length, "id 485 ma pusty label").toBeGreaterThan(0);
  }
});
