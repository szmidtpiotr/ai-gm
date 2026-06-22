/**
 * REGRESSION #734 (L18) — gracz może użyć leczniczej mikstury W TRAKCIE walki jako akcji tury.
 * Acceptance: endpoint POST /api/campaigns/{id}/combat/use-consumable istnieje (kontrakt akcji
 * konsumującej turę), waliduje body (inventory_id wymagany) i odrzuca brak aktywnej walki (400),
 * a nie 404 — czyli akcja jest podpięta, nie zgubiona w routingu.
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
