/**
 * REGRESSION #569 — widoczny modal rzutu k20 (3D) przy ataku w walce.
 * Acceptance (asset/kontrakt, deterministyczny):
 *  - app.js dostarcza `playCombatDiceRoll` i wpina ją w `handleCombatAttack` (przed resolve-attack).
 *  - reużywa dice-overlay (ten sam co testy umiejętności).
 * Pełny scenariusz (klik Atakuj → kostka 3D ląduje na wartości) — weryfikacja /game-test-player + zrzut.
 */
const { test, expect } = require("@playwright/test");

const V = "u17-combat-dice-2026-06-13";

test("REGRESSION #569 — app.js wpina modal kostki w atak walki", async ({ page }) => {
  const js = await page.request.get(`/js/app.js?v=${V}`);
  expect(js.ok()).toBeTruthy();
  const src = await js.text();

  expect(src.includes("function playCombatDiceRoll"), "brak funkcji playCombatDiceRoll (#569)").toBeTruthy();
  expect(src.includes("await playCombatDiceRoll(d20"), "handleCombatAttack nie woła modalu kostki (#569)").toBeTruthy();
  // Reużywa istniejący overlay kostki (parytet z testami umiejętności)
  expect(src.includes("dice-overlay"), "modal nie używa dice-overlay (#569)").toBeTruthy();

  // Overlay kostki istnieje w index.html
  const html = await page.request.get(`/`);
  const htmlText = await html.text();
  expect(htmlText.includes('id="dice-overlay"'), "brak dice-overlay w index.html (#569)").toBeTruthy();
});
