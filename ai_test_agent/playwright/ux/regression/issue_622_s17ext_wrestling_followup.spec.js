/**
 * REGRESSION #622 (S17-EXT) — Follow-up zapasów gated za wrestling rank ≥ 3 (solo).
 * Udane zapasy (SUCCESS/CRITICAL_SUCCESS) z rank ≥ 3 dają słabszy darmowy cios (obrażenia ÷2)
 * w tej samej turze, logowany jako event 'wrestling_followup'. Frontend gracza musi renderować
 * kartę „Dodatkowy cios". Ten test sprawdza kontrakt frontendu: wdrożony app.js wpina obsługę
 * eventu (filtr feedu walki + gałąź renderująca kartę).
 * Acceptance: app.js serwowany na DEV zawiera obsługę 'wrestling_followup' (filtr + karta z ÷2).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #622 — app.js wpina kartę wrestling_followup (÷2 cios)", async ({ page }) => {
  const r = await page.request.get("/js/app.js");
  expect(r.ok(), "/js/app.js nie odpowiada 200 (#622)").toBeTruthy();
  const src = await r.text();

  // Event 'wrestling_followup' przepuszczony przez filtr feedu walki.
  expect(
    src.includes("wrestling_followup"),
    "app.js nie zawiera obsługi eventu 'wrestling_followup' (#622)"
  ).toBeTruthy();

  // Karta pokazuje słabszy cios (połowa obrażeń) — komunikat dla gracza.
  expect(
    src.includes("Dodatkowy cios"),
    "app.js nie renderuje karty 'Dodatkowy cios' (#622)"
  ).toBeTruthy();

  // Handler zapasów MUSI od razu opróżnić feed walki, inaczej follow-up pojawia się
  // dopiero po turze wroga (out-of-context). Sprawdzamy, że handleCombatWrestle woła
  // fetchAndAppendNewCombatTurns w tym samym przebiegu.
  const wrestleHandler = src.slice(src.indexOf("async function handleCombatWrestle"));
  const handlerBody = wrestleHandler.slice(0, wrestleHandler.indexOf("async function handleCombatFlee"));
  expect(
    handlerBody.includes("fetchAndAppendNewCombatTurns"),
    "handleCombatWrestle nie opróżnia feedu walki — follow-up renderuje się za późno (#622)"
  ).toBeTruthy();
});
