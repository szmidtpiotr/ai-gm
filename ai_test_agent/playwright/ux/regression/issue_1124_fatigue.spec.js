/**
 * REGRESSION #1124 (PT-D1) — Zmęczenie: kondycja `exhausted` przeprojektowana na 3 progi.
 * Acceptance: katalog kondycji zwraca `exhausted` z opisem zmęczenia podróżnego
 * (marsz >8h / brak noclegu), co potwierdza że migracja effect_json/description weszła.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1124 — exhausted to zmęczenie podróżne (3 progi)", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "endpoint /api/mechanics/conditions nie odpowiada 200 (#1124)").toBeTruthy();
  const body = await r.json();

  // Endpoint zwraca listę kondycji (lub {conditions:[...]}) — znormalizuj.
  const list = Array.isArray(body) ? body : (body.conditions || body.items || []);
  expect(Array.isArray(list) && list.length > 0, "brak listy kondycji").toBeTruthy();

  const exhausted = list.find(
    (c) => String(c.key || c.condition_type || "").toLowerCase() === "exhausted"
  );
  expect(exhausted, "brak kondycji `exhausted` w katalogu (#1124)").toBeTruthy();

  const desc = String(exhausted.description || exhausted.catalog_description || "").toLowerCase();
  // Opis po redesignie mówi o zmęczeniu z marszu / noclegu — nie o starym STR/DEX/CON -3.
  expect(
    desc.includes("zmęczenie") || desc.includes("marsz") || desc.includes("stack"),
    "opis `exhausted` nie odzwierciedla redesignu zmęczenia podróżnego (#1124)"
  ).toBeTruthy();
});
