/**
 * REGRESSION #1181 (code-review) — centralizacja helperów stat_modifier/proficiency + migracja gold.
 * Refaktor jest backendowy: głównym ryzykiem jest zepsuty import z nowego app.core.mechanics,
 * który wywaliłby cały backend. Ten test potwierdza że aplikacja wstaje i odpowiada (wszystkie
 * zmigrowane moduły importują się poprawnie), oraz że endpoint zdrowia zwraca 200.
 * Acceptance: /api/health == 200 i backend serwuje ruch po refaktorze.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1181 — backend wstaje po centralizacji helperów", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "/api/health nie odpowiada 200 — możliwy zepsuty import app.core.mechanics (#1181)").toBeTruthy();
  const body = await r.json();
  expect(body, "brak ciała odpowiedzi /api/health").toBeTruthy();
});
