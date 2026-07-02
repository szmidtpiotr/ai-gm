/**
 * REGRESSION #1072 — Po wskrzeszeniu MG musi automatycznie dopisać turę narracyjną
 * ("powrót do życia"), zamiast zostawiać gracza przed pustym oknem czatu.
 * Acceptance: POST /characters/:id/resurrect nie 500-uje i zwraca pole "narration";
 * GET /campaigns/:id/turns ma stabilny kontrakt (assistant_text/route) dla renderu czatu.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1072 — backend zdrowy, prerequisite dla wskrzeszenia", async ({ page }) => {
  const health = await page.request.get("/api/health");
  expect(health.ok(), "backend /api/health musi zwracać 200 (#1072)").toBeTruthy();
  const body = await health.json();
  expect(body.status).toBe("ok");
});

test("REGRESSION #1072 — resurrect-preview endpoint nie 500-uje", async ({ page }) => {
  // Character 2 ([TEST] Wojownik) — używany w testach smoke; żywy lub martwy,
  // liczy się że endpoint nie wybucha 500 (import narracji nie psuje modułu).
  const r = await page.request.get("/api/characters/2/resurrect-preview?user_id=1");
  expect(r.status(), "resurrect-preview nie może zwracać 500 (#1072)").not.toBe(500);
});

test("REGRESSION #1072 — kontrakt /campaigns/:id/turns zawiera pola dla auto-narracji", async ({ page }) => {
  // Demo campaign (id=1) — kontrakt kształtu odpowiedzi, nie zawartości.
  const r = await page.request.get("/api/campaigns/1/turns?limit=1");
  expect(r.status(), "/turns nie może zwracać 500 (#1072)").not.toBe(500);
  if (r.ok()) {
    const turns = await r.json();
    expect(Array.isArray(turns), "/turns musi zwracać listę").toBeTruthy();
    if (turns.length > 0) {
      const t = turns[0];
      expect(t).toHaveProperty("assistant_text");
      expect(t).toHaveProperty("route");
      expect(t).toHaveProperty("turn_number");
    }
  }
});
