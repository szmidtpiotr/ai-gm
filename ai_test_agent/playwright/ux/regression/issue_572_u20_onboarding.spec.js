/**
 * REGRESSION #572 (U20) — Onboarding: poprawki triggerów kart.
 * Acceptance: nowe karty (durability, raids, crafter) istnieją w bibliotece kart,
 * karta rzutu wymienia „Biegłość" (proficiency), karta XP tłumaczy JAK wydać PD.
 * Test kontraktowy (bez LLM): oznacza karty jako widziane dla dedykowanego user_id,
 * potem czyta bibliotekę /mechanic-cards i sprawdza obecność + treść.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #572 — U20 onboarding cards present + content", async ({ page }) => {
  const uid = 990572; // dedicated regression user (no FK on seen_mechanics)
  const keys = ["durability", "raids", "crafter", "dice_roll", "xp_gained", "death_save"];

  for (const key of keys) {
    const p = await page.request.post(`/api/users/${uid}/seen-mechanics`, {
      data: { mechanic_key: key },
    });
    expect(p.ok(), `POST seen-mechanics ${key} nie 2xx (#572)`).toBeTruthy();
  }

  const r = await page.request.get(`/api/users/${uid}/mechanic-cards`);
  expect(r.ok(), "GET mechanic-cards nie 2xx (#572)").toBeTruthy();
  const body = await r.json();
  const byKey = Object.fromEntries((body.cards || []).map((c) => [c.mechanic_key, c]));

  // Nowe karty U20
  expect(byKey.durability, "brak karty durability (#572)").toBeTruthy();
  expect(byKey.raids, "brak karty raids (#572)").toBeTruthy();
  expect(byKey.crafter, "brak karty crafter (#572)").toBeTruthy();

  // Treść ujednolicona z UI
  expect(byKey.dice_roll.content, "karta rzutu bez Biegłości (#572)").toContain("Biegłość");
  expect(byKey.xp_gained.content, "karta XP bez instrukcji wydania (#572)").toContain("Ucz się");
});
