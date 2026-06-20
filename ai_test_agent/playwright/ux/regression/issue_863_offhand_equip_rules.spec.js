/**
 * REGRESSION #863 (#598 follow-up) — equip-rules off-hand spójne z dual-wield.
 * Reguła: ręka pomocnicza przyjmuje tylko LEKKIE bronie 'either' + tarcze;
 * ciężka 'either' i 2H-w-main → odrzucone. Backend wystawia `is_light` na wierszach
 * broni w ekwipunku, żeby front mógł lustrzanie gatować slot off_hand.
 * Acceptance: GET /api/inventory/{cid} zwraca pole `is_light` na każdej broni.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #863 — inventory wystawia is_light na broni (gating off-hand)", async ({ page }) => {
  // Char 2 (demo) ma broń w ekwipunku — kontrakt payloadu po #863.
  const r = await page.request.get("/api/inventory/2");
  expect(r.ok(), "GET /api/inventory/2 nie odpowiada 200 (#863)").toBeTruthy();
  const body = await r.json();
  const rows = Array.isArray(body) ? body : (body.data || body.items || []);
  const weapons = rows.filter((it) => String(it.item_type || "").toLowerCase() === "weapon");
  expect(weapons.length, "brak broni w ekwipunku char 2 — nie da się zweryfikować is_light").toBeGreaterThan(0);
  // Każda broń musi nieść pole is_light (true/false) — nie undefined.
  for (const w of weapons) {
    expect(
      Object.prototype.hasOwnProperty.call(w, "is_light"),
      `broń ${w.key} bez pola is_light (#863)`
    ).toBeTruthy();
    expect([true, false, null]).toContain(w.is_light);
  }
});
