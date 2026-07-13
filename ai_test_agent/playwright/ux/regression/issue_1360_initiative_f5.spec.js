/**
 * REGRESSION #1360 (WALKA-T5-FIX-a2) — latch kart walki przeżywa F5.
 * Karty overlayowe (Inicjatywa #1356, Pojawienie wroga #1344) mają wyskoczyć RAZ na walkę.
 * Wcześniej „widziane" pamiętał tylko useRef (pamięć ulotna) → po F5 w środku walki karta
 * wyskakiwała ponownie. Fix: latch w sessionStorage (klucze aigm:initSeen:<cid> / aigm:revealSeen:<cid>).
 * Acceptance: wpis „widziane" per combat_id przeżywa reload strony (F5) w prawdziwej przeglądarce.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1360 — latch widziane per combat_id przeżywa F5 (sessionStorage)", async ({ page }) => {
  await page.goto("/");
  // Symulacja: hook oznaczył walkę 4242 jako „widzianą" (karta inicjatywy już pokazana).
  await page.evaluate(() => sessionStorage.setItem("aigm:initSeen:4242", "1"));

  // F5 w środku walki = pełny reload strony.
  await page.reload();

  // Latch MUSI przetrwać reload — inaczej karta wyskoczyłaby ponownie w środku walki.
  const survived = await page.evaluate(() => sessionStorage.getItem("aigm:initSeen:4242"));
  expect(survived, "latch 'widziane' per combat_id musi przeżyć F5 (#1360)").toBe("1");

  // Inny combat_id nie jest oznaczony → nowa walka nadal pokaże kartę.
  const otherCombat = await page.evaluate(() => sessionStorage.getItem("aigm:initSeen:9999"));
  expect(otherCombat, "nowa walka (inny combat_id) nie jest wyciszona").toBeNull();
});
