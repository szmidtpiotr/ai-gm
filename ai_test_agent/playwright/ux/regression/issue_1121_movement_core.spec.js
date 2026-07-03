/**
 * REGRESSION #1121 (PT11) — wspólny rdzeń ruchu movement_service.
 * Acceptance: po zjednoczeniu world+local na jeden rdzeń krok-koszt-ryzyko
 * endpointy ruchu nadal odpowiadają poprawnym kontraktem (zachowanie bez zmian).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1121 — backend zdrowy po refaktorze rdzenia ruchu", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend /api/health nie odpowiada 200 (#1121)").toBeTruthy();
});

test("REGRESSION #1121 — local-map endpoint nie wybucha po unify (kontrakt)", async ({ page }) => {
  // Refactor przepiął local-travel na wspólny rdzeń; GET local-map musi nadal
  // zwracać spójny kontrakt (200 z polami) albo czysto 404 — NIGDY 500.
  const r = await page.request.get("/api/campaigns/1/local-map");
  expect([200, 404], `local-map zwróciło ${r.status()} (#1121)`).toContain(r.status());
  if (r.status() === 200) {
    const body = await r.json();
    expect(body, "brak pola has_local_map w kontrakcie local-map (#1121)").toHaveProperty(
      "has_local_map"
    );
    expect(Array.isArray(body.hexes), "hexes nie jest listą (#1121)").toBeTruthy();
  }
});
