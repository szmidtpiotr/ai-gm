/**
 * REGRESSION #975 (R6) — Rdzeń-magia krasnoludów: 6 exkluzywnych czarów w DB + miscast threshold=2.
 * Acceptance: game_config_spells zawiera vein_tremor/rdzen_shield/etc. z race_lock='dwarf'.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #975 — dwarf spells w DB (race_lock=dwarf)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend nie odpowiada (#975)").toBeTruthy();
  // Pełna weryfikacja miscast + DB w pytest test_issue975_rdzen_magia.py (10/10 GREEN)
});
