/**
 * REGRESSION #566 — narracja rzutu walki nie jest blokowana „Walka trwa!" + idzie strumieniem.
 * Acceptance (asset/kontrakt, deterministyczny):
 *  - app.js: sendCombatNarration używa toru strumieniowego (_sendTurnStream), NIE zwykłego
 *    apiRequest POST /turns — dzięki temu renderuje kartę [GM_ROLL] i omija mis-blok.
 *  - Tor strumieniowy obsługuje [GM_ROLL] (karta kostki).
 * Pełna ścieżka (klik Atakuj → karta rzutu, brak „Walka trwa!") — weryfikacja manualna / game-test-player.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #566 — sendCombatNarration idzie strumieniem (_sendTurnStream)", async ({ page }) => {
  const js = await page.request.get(`/js/app.js?v=u17-drop-celebration-2026-06-13b`);
  expect(js.ok()).toBeTruthy();
  const src = await js.text();

  // Wytnij ciało funkcji sendCombatNarration
  const start = src.indexOf("async function sendCombatNarration");
  expect(start, "brak funkcji sendCombatNarration (#566)").toBeGreaterThan(-1);
  const body = src.slice(start, start + 800);

  expect(body.includes("_sendTurnStream"), "sendCombatNarration nie używa toru strumieniowego (#566)").toBeTruthy();
  expect(
    body.includes("apiRequest('POST', `/campaigns/${currentCampaignId}/turns`"),
    "sendCombatNarration nadal woła zwykły /turns — mis-blok wróci (#566)"
  ).toBeFalsy();

  // Tor strumieniowy nadal obsługuje kartę rzutu
  expect(src.includes("[GM_ROLL]"), "brak obsługi [GM_ROLL] w streamie (#566)").toBeTruthy();
});
