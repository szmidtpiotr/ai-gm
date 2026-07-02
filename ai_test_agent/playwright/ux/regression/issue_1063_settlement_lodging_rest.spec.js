/**
 * REGRESSION #1063 (REST) — osada z sub-lokacją inn/tavern liczy się jako bezpieczna do odpoczynku,
 * nawet gdy sama osada nie ma własnej flagi safe_for_rest ustawionej ręcznie.
 * Acceptance: rest endpoint pozostaje zdrowy po dodaniu world_service.settlement_lodging()
 * do rest_service._is_safe_for_character i suggested_actions._is_safe_for_rest — żądanie dla
 * nieistniejącej postaci zwraca ustrukturyzowany błąd 4xx, nigdy 500. Właściwa logika
 * (macro bez flagi + sub-lokacja 'tavern'/'inn' → rest dozwolony) jest deterministycznie
 * pokryta testem pytest test_issue1063_settlement_lodging_rest.py.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1063 — rest endpoint healthy after settlement-lodging gate", async ({ page }) => {
  const health = await page.request.get("/api/health");
  expect(health.ok(), "Backend health check failed (#1063)").toBeTruthy();

  const r = await page.request.post("/api/characters/1/rest?type=short");
  expect(r.status(), "rest endpoint returned 500 — settlement_lodging gate broke it (#1063)").not.toBe(500);
  expect(r.status() < 500, `unexpected server error ${r.status()} (#1063)`).toBeTruthy();
});
