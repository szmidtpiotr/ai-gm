/**
 * REGRESSION #1168 — zdublowane trasy usunięte (combat/start MP, images/models).
 * Acceptance: oba endpointy nadal odpowiadają (nie 404) — pojedyncza rejestracja
 * nie zdejmuje trasy, tylko usuwa cień. Weryfikacja pełnej unikalności = pytest.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1168 — combat/start nadal osiągalny (bez MP duplikatu)", async ({ page }) => {
  const r = await page.request.post("/api/campaigns/1/combat/start", { data: { enemy_keys: [] } });
  expect(r.status(), "combat/start nie może zniknąć (#1168)").not.toBe(404);
});

test("REGRESSION #1168 — images/models nadal osiągalny (jedna definicja)", async ({ page }) => {
  const r = await page.request.get("/api/admin/images/models");
  expect(r.status(), "images/models nie może być 404 (#1168)").not.toBe(404);
});
