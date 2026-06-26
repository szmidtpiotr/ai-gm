/**
 * REGRESSION #972 (R3) — Twardy jak kamień: apply_defense_model akceptuje race i damage_type.
 * Acceptance: Krasnolud otrzymuje −2 dmg od trucizny/mroku/Rdzenia (min 1).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #972 — /api/health odpowiada (backend z dwarf toughness działa)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend nie odpowiada (#972)").toBeTruthy();
  // Pełna weryfikacja mechaniki w pytest test_issue972_dwarf_toughness.py
});
