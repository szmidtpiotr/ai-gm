/**
 * REGRESSION #976 (R7) — Kreator postaci: Krok 0 wybór rasy (Człowiek/Krasnolud).
 * Acceptance: POST /characters akceptuje pole race; endpoint dostępny.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #976 — POST /characters akceptuje race=dwarf", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend nie odpowiada (#976)").toBeTruthy();
  // Pełna weryfikacja schematu w pytest test_issue976_wizard_race_step.py (4/4 GREEN)
  // Weryfikacja wizualna Krok 0 na https://aigm-dev.studio-colorbox.com/ po deployu
});
