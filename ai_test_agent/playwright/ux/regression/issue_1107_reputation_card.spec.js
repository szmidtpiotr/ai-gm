/**
 * REGRESSION #1107 (reputation_card) — Sekcja Reputacja widoczna na karcie bohatera poniżej cech i umiejętności.
 * Acceptance: element #sheet-reputation-section istnieje w DOM karty bohatera; endpoint zwraca poprawny kontrakt.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1107 — element #sheet-reputation-section istnieje w DOM karty bohatera", async ({ page }) => {
  await page.goto("/");
  // Element musi być w HTML (nawet ukryty przed załadowaniem danych)
  const repSection = page.locator("#sheet-reputation-section");
  await expect(repSection, "brak #sheet-reputation-section w DOM — sekcja reputacji nie dodana (#1107)")
    .toBeAttached();
});

test("REGRESSION #1107 — endpoint reputacji zwraca tier + scope_key dla bohatera z danymi", async ({ page }) => {
  // character 999420 ma wpis w character_reputation (siwe_granie, -15)
  const r = await page.request.get("/api/characters/999420/reputation");
  expect(r.ok(), "endpoint /api/characters/999420/reputation nie odpowiada 200 (#1107)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.reputation), "reputation musi być listą").toBeTruthy();
  expect(body.reputation.length, "bohater 999420 ma wpis reputacji — lista nie może być pusta").toBeGreaterThan(0);
  const row = body.reputation[0];
  expect(row).toHaveProperty("scope_key");
  expect(row).toHaveProperty("value");
  expect(["exalted", "friendly", "neutral", "disliked", "hated"]).toContain(row.tier);
});
