/**
 * REGRESSION #594 — onboarding cards + knowledge tips unified via `kind`.
 * Acceptance: /api/knowledge-tips zwraca wyłącznie wpisy kind='knowledge_tip' —
 * karty onboardingu (dice_roll, combat_start...) nie wyciekają do listy gracza.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #594 — knowledge-tips excludes onboarding cards", async ({ page }) => {
  const r = await page.request.get("/api/knowledge-tips");
  expect(r.ok(), "knowledge-tips nie odpowiada 200 (#594)").toBeTruthy();
  const body = await r.json();
  const keys = (body.tips || []).map((t) => t.tip_key);

  for (const onb of ["dice_roll", "combat_start", "damage_taken", "death_save"]) {
    expect(
      keys.includes(onb),
      `karta onboardingu '${onb}' nie powinna być w knowledge-tips (#594)`
    ).toBeFalsy();
  }
  expect(keys.length, "powinny istnieć wpisy knowledge_tip").toBeGreaterThan(0);
});
