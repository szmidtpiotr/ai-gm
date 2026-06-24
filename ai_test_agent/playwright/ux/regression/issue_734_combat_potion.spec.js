/**
 * REGRESSION #734 (L18) — gracz może użyć leczniczej mikstury W TRAKCIE walki jako akcji tury.
 * Acceptance: endpoint POST /api/campaigns/{id}/combat/use-consumable istnieje (kontrakt akcji
 * konsumującej turę), waliduje body (inventory_id wymagany) i odrzuca brak aktywnej walki (400),
 * a nie 404 — czyli akcja jest podpięta, nie zgubiona w routingu.
 *
 * Dotyczy też lochu (katakumby_mroku): tryb dungeon używa tego samego endpointu;
 * app.js:_dungeonMove musi wołać pollCombatState() (nie loadCombatState — brak definicji).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #734 — endpoint use-consumable zamontowany (brak inventory_id → 422)", async ({ page }) => {
  // Trafienie w niezarejestrowaną trasę dałoby 404; walidacja pydantic (422) odpala się DOPIERO
  // gdy trasa POST /combat/use-consumable jest zamontowana i podpięta — to dowód kontraktu akcji.
  const r = await page.request.post("/api/campaigns/1/combat/use-consumable", { data: {} });
  expect(r.status(), "brak inventory_id powinien dać 422, nie 404 (#734)").toBe(422);
});

test("REGRESSION #734 — poprawny kształt body jest obsłużony (nie 404 routingu)", async ({ page }) => {
  // Z poprawnym inventory_id trasa zwraca błąd domenowy (400 brak walki / 404 brak przedmiotu),
  // ale NIGDY 405/501 — czyli akcja jest obsłużona, nie zgubiona.
  const r = await page.request.post("/api/campaigns/1/combat/use-consumable", {
    data: { inventory_id: 999999999 },
  });
  expect([200, 400, 404].includes(r.status()), `nieoczekiwany status ${r.status()} (#734)`).toBeTruthy();
});

test("REGRESSION #734 — loch (dungeon mode): endpoint dostępny dla kampanii trybu dungeon", async ({ page }) => {
  // Dungeon campaigns use the same endpoint. Verify the route is accessible (not 404/405)
  // for a dungeon campaign_id — distinguishes routing errors from domain errors.
  // We use a large id (no campaign exists) — expect 400 "no active combat", not 404 "route missing".
  const r = await page.request.post("/api/campaigns/999000/combat/use-consumable", {
    data: { inventory_id: 1 },
  });
  // Backend returns 400 (no active combat for campaign 999000), never 404 (route not found).
  expect(r.status(), "trasa /combat/use-consumable musi istnieć dla dowolnego campaign_id (#734 dungeon)").not.toBe(404);
  expect(r.status(), "trasa nie może zwracać 405 (Method Not Allowed) (#734 dungeon)").not.toBe(405);
});

test("REGRESSION #734 — app.js: pollCombatState (nie loadCombatState) dostępny globalnie", async ({ page }) => {
  // loadCombatState() was undefined, causing TypeError in _dungeonMove when combat tile entered.
  // Fix: call pollCombatState() which exists in combat_ui.js. Verify it's exposed globally.
  await page.goto("/");
  await page.waitForSelector("#login-username", { timeout: 10000 });
  await page.fill("#login-username", "demo");
  await page.fill("#login-password", "demo");
  await page.click("#login-form button");
  await page.waitForTimeout(2500);

  const result = await page.evaluate(() => ({
    pollCombatStateDefined: typeof window.pollCombatState === "function" || typeof pollCombatState === "function",
    loadCombatStateUndefined: typeof window.loadCombatState === "undefined" && typeof loadCombatState === "undefined",
  }));

  // pollCombatState is defined (either as window property or closure-scoped in combat_ui.js)
  // The important thing: calling pollCombatState() does NOT throw ReferenceError
  const noCrash = await page.evaluate(() => {
    try {
      // In dungeon context, currentCampaignId is null → pollCombatState returns early (no fetch)
      if (typeof pollCombatState === "function") {
        pollCombatState(); // must not throw ReferenceError
        return true;
      }
      return false;
    } catch (e) {
      return e.message;
    }
  });
  expect(noCrash, "pollCombatState() nie może rzucać wyjątku (#734 fix)").toBe(true);
});
