/**
 * REGRESSION #861 (#598 follow-up) — render dual-wield w UI walki gracza:
 * drugi cios off-hand jako osobna karta + badge „Parujesz (+N)" przy ataku wroga.
 * Acceptance: karta combat_turn z meta.offhand → label „DRUGI CIOS"; atak wroga z
 * meta.parry_bonus → badge parowania; brak flag → render bez zmian (zero regresji).
 *
 * Deterministyczne: testuje czyste helpery renderujące (window._combatMetaIsOffhand /
 * window._combatParryBadgeHtml) — bez LLM i bez żywej walki dual-wield (e2e zostawiamy pytestowi).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #861 — helpery dual-wield UI dostępne i poprawne", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector("#login-screen.screen--active", { timeout: 15000 });

  // Helpery wystawione przez app.js przy parsowaniu — dostępne bez logowania.
  const exposed = await page.evaluate(() => ({
    isOffhand: typeof window._combatMetaIsOffhand === "function",
    parryBadge: typeof window._combatParryBadgeHtml === "function",
  }));
  expect(exposed.isOffhand, "brak window._combatMetaIsOffhand (#861)").toBeTruthy();
  expect(exposed.parryBadge, "brak window._combatParryBadgeHtml (#861)").toBeTruthy();

  // Drugi cios off-hand → rozpoznany.
  const offhandTrue = await page.evaluate(() => window._combatMetaIsOffhand({ offhand: true }));
  expect(offhandTrue, "meta.offhand:true musi dać kartę 'drugi cios'").toBeTruthy();

  // Główny cios / brak flagi → NIE off-hand (zero regresji).
  const offhandFalse = await page.evaluate(() => [
    window._combatMetaIsOffhand({ offhand: false }),
    window._combatMetaIsOffhand({}),
    window._combatMetaIsOffhand(null),
  ]);
  expect(offhandFalse.every((v) => v === false), "główny atak nie może być off-hand").toBeTruthy();

  // Parowanie → badge z liczbą; brak → pusty string.
  const parry = await page.evaluate(() => ({
    withBonus: window._combatParryBadgeHtml({ parry_bonus: 2 }),
    zero: window._combatParryBadgeHtml({ parry_bonus: 0 }),
    absent: window._combatParryBadgeHtml({}),
  }));
  expect(parry.withBonus).toContain("Parujesz (+2");
  expect(parry.zero, "parry_bonus:0 → bez badge").toBe("");
  expect(parry.absent, "brak parry_bonus → bez badge").toBe("");
});
