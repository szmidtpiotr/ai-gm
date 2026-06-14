/**
 * REGRESSION #581 (S1) — Margines sukcesu: 4 stopnie wyniku testu umiejętności.
 * Acceptance (asset/kontrakt, deterministyczny):
 *  - app.js render karty rzutu skilla używa pola `sr.margin` i mapuje na 4 stopnie
 *    (Sukces krytyczny / Sukces / Porażka / Porażka krytyczna) zamiast binarnego sukces/porażka.
 *  - Karta pokazuje margines liczbowo (np. "Sukces +7").
 * Pełna ścieżka (gracz prowokuje testy o różnym marginesie → narracja różnicuje stopnie)
 *  — weryfikacja manualna / game-test-player.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #581 — karta rzutu skilla pokazuje margines i 4 stopnie", async ({ page }) => {
  const js = await page.request.get(`/js/app.js?v=s1-margin-2026-06-14`);
  expect(js.ok(), "app.js nie odpowiada 200 (#581)").toBeTruthy();
  const src = await js.text();

  // Wytnij ciało funkcji resolveSkillTest
  const start = src.indexOf("async function resolveSkillTest");
  expect(start, "brak funkcji resolveSkillTest (#581)").toBeGreaterThan(-1);
  const body = src.slice(start, start + 1600);

  // Używa pola margin z backendu
  expect(body.includes("sr.margin"), "render nie czyta sr.margin (#581)").toBeTruthy();

  // Mapuje 4 stopnie wg outcome
  expect(body.includes("CRITICAL_SUCCESS"), "brak stopnia CRITICAL_SUCCESS w renderze (#581)").toBeTruthy();
  expect(body.includes("CRITICAL_FAILURE"), "brak stopnia CRITICAL_FAILURE w renderze (#581)").toBeTruthy();

  // Pokazuje słowne stopnie krytyczne (nie tylko binarne Sukces/Porażka)
  expect(body.includes("Sukces krytyczny"), "brak etykiety 'Sukces krytyczny' (#581)").toBeTruthy();
  expect(body.includes("Porażka krytyczna"), "brak etykiety 'Porażka krytyczna' (#581)").toBeTruthy();

  // Margines pokazywany ze znakiem
  expect(body.includes("marginStr"), "margines nie jest renderowany w karcie rzutu (#581)").toBeTruthy();
});
