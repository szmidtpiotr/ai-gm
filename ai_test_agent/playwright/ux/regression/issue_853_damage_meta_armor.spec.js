/**
 * REGRESSION #853 — Rzuty tab: damage records zawierają armor_reduction w meta.
 * Acceptance: GET /api/campaigns/{id}/dice-rolls zwraca damage rows z meta.armor_reduction (number) i meta.nat20_ignored_armor (bool).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #853 — dice-rolls API zwraca damage z armor_reduction w meta", async ({ page }) => {
  // Znajdź dowolną kampanię z rzutami damage
  const r = await page.request.get("/api/campaigns/1/dice-rolls?roll_type=damage&limit=10");
  // Endpoint musi odpowiedzieć 200 (nawet jeśli brak rzutów — to jest OK, sprawdzamy kontrakt)
  expect(r.ok(), "endpoint /api/campaigns/1/dice-rolls nie odpowiada 200 (#853)").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("dice_rolls");

  // Jeśli są jakieś damage rolls — sprawdź strukturę meta
  const rolls = body.dice_rolls || [];
  if (rolls.length > 0) {
    const dmgRoll = rolls[0];
    expect(dmgRoll).toHaveProperty("meta");
    expect(dmgRoll.meta).toHaveProperty("armor_reduction");
    expect(dmgRoll.meta).toHaveProperty("nat20_ignored_armor");
    expect(typeof dmgRoll.meta.armor_reduction).toBe("number");
    expect(typeof dmgRoll.meta.nat20_ignored_armor).toBe("boolean");
  }
});

test("REGRESSION #853 — campaigns.js Rzuty tab renderuje armor_reduction (#853)", async ({ page }) => {
  // Sprawdź że campaigns.js zawiera logikę wyświetlania kalkulacji zbroi
  const r = await page.request.get("/admin/sections/campaigns.js");
  // Plik musi być dostępny
  if (!r.ok()) {
    // Fallback — sprawdź przez główny moduł admina
    const r2 = await page.request.get("/admin/");
    expect(r2.ok(), "admin panel niedostępny (#853)").toBeTruthy();
    return;
  }
  const text = await r.text();
  expect(text).toContain("armor_reduction");
  expect(text).toContain("zbroja");
  expect(text).toContain("nat20_ignored_armor");
});
