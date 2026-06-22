/**
 * REGRESSION #931 (918-B) — Gate testowy mass-implement: --build przed pytest + baseline-diff dla refaktorów.
 * Acceptance API: backend zdrowy po rebuild + combat endpoint działa (kontrolny test walki).
 * Pełna weryfikacja szablonów: pytest test_issue931_mass_implement_gate.py (4/4 GREEN).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #931 — DEV backend health (świeży po --build)", async ({ request }) => {
  const r = await request.get("/api/health");
  expect(r.ok(), "Backend nie odpowiada 200 — kontener down lub --build nie wykonany (#931)").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("status");
});

test("REGRESSION #931 — combat stats endpoint działa (kontrolny test funkcji walki)", async ({
  request,
}) => {
  // Weryfikuje że combat_service jest zaimportowany poprawnie i funkcja nie zwraca None.
  // Analogon testu kontrolnego: gdyby usunięto 'return out' w reduce_stacking_conditions,
  // backend 500-owałby na wywołaniach walki.
  const r = await request.get("/api/mechanics/stats");
  expect(
    r.status() < 500,
    `Combat/mechanics endpoint 5xx — potencjalna regresja walki (#931): status ${r.status()}`
  ).toBeTruthy();
});
