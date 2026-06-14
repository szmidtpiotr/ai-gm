/**
 * REGRESSION #594 — onboarding cards + knowledge tips zunifikowane (jeden wpis, dwie powierzchnie).
 * Acceptance: /api/knowledge-tips zwraca wpisy oznaczone show_in_knowledge=1 — w tym
 * karty onboardingu (np. dice_roll), bo ten sam wpis może być widoczny w OBU miejscach.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #594 — onboarding cards also appear in player knowledge book", async ({ page }) => {
  const r = await page.request.get("/api/knowledge-tips");
  expect(r.ok(), "knowledge-tips nie odpowiada 200 (#594)").toBeTruthy();
  const body = await r.json();
  const keys = (body.tips || []).map((t) => t.tip_key);

  expect(keys.length, "powinny istnieć wpisy w Księdze Wiedzy").toBeGreaterThan(0);
  // seed oznacza karty onboardingu jako widoczne także w Wiedzy → muszą tu być
  expect(
    keys.includes("damage_taken"),
    "karta onboardingu 'damage_taken' powinna być widoczna też w Wiedzy (#594)"
  ).toBeTruthy();
});
