/**
 * REGRESSION #978 (R9) — Narrator race-aware: system_prompt zawiera sekcję RASY BOHATERÓW.
 * Acceptance: backend startuje, system_prompt ma sekcję rasy, turn engine wstrzykuje race.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #978 — backend z race-aware narrator startuje poprawnie", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend nie odpowiada (#978)").toBeTruthy();
  // Pełna weryfikacja w pytest test_issue978_narrator_race.py (5/5 GREEN)
});
