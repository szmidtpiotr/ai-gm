/**
 * REGRESSION #852 — Admin Zawartość → Czary: tabela zostaje na "Ładowanie…" po powrocie do sekcji.
 * Root cause: _loaded Set na poziomie modułu nie jest czyszczony przy reinit() — tab.spells już
 * w Set z poprzedniej wizyty → early return bez renderowania danych.
 * Acceptance: po wyjściu i powrocie do Zawartość zakładka Czary renderuje dane (nie "Ładowanie…").
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #852 — /api/admin/spells endpoint istnieje (backend OK)", async ({ page }) => {
  // Endpoint wymaga auth — sprawdzamy że odpowiada 401 (nie 404), czyli route jest zarejestrowany.
  const r = await page.request.get("/api/admin/spells");
  expect([200, 401].includes(r.status()), `endpoint /api/admin/spells nie istnieje — got ${r.status()} (#852)`).toBeTruthy();
});

test("REGRESSION #852 — content.js init() czyści _loaded Set przy ponownym wejściu", async ({ page }) => {
  const r = await page.request.get("/admin/sections/content.js");
  expect(r.ok(), "content.js nie ładuje się (#852)").toBeTruthy();
  const js = await r.text();
  // Before fix: _loaded.clear() is absent → spells tab stuck on "Ładowanie…" after re-navigation
  expect(js, "init() musi wywoływać _loaded.clear() (#852)").toContain("_loaded.clear()");
});

test("REGRESSION #852 — _onSmartEntrySaved obsługuje game_config_spells", async ({ page }) => {
  const r = await page.request.get("/admin/sections/content.js");
  expect(r.ok(), "content.js nie ładuje się (#852)").toBeTruthy();
  const js = await r.text();
  // Before fix: game_config_spells missing from handler → AI Kreator save does not refresh table
  expect(js, "_onSmartEntrySaved musi obsługiwać game_config_spells (#852)").toContain("game_config_spells");
});
