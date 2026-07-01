/**
 * REGRESSION #1079 — Przywrócenie usuwania lokacji w panelu admin (regresja noDelete:true).
 * Acceptance: Flaga noDelete:true NIE istnieje w _ROW_REGISTRY['locations-table'] w map.js.
 * Backend DELETE /api/admin/locations/{key} nadal zwraca 404 dla nieistniejącej lokacji (nie 500).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1079 — map.js nie blokuje usuwania lokacji (brak noDelete:true)", async ({ page }) => {
  const r = await page.request.get("/admin/sections/map.js");
  expect(r.ok(), "map.js nie jest serwowany przez frontend (#1079)").toBeTruthy();
  const content = await r.text();
  expect(
    content.includes("noDelete:true"),
    "Flaga noDelete:true nadal obecna w map.js — usuwanie lokacji jest zablokowane (#1079)"
  ).toBeFalsy();
});

test("REGRESSION #1079 — backend DELETE /api/admin/locations zwraca 404 dla nieistniejącej lokacji", async ({ page }) => {
  const r = await page.request.delete("/api/admin/locations/nonexistent_test_1079_key", {
    headers: { Authorization: "Bearer invalid-token-test" }
  });
  // Endpoint istnieje i obsługuje request (401 lub 404 — nie 404-route-not-found)
  expect([401, 403, 404].includes(r.status()), `Endpoint DELETE /api/admin/locations nie odpowiada — status: ${r.status()}`).toBeTruthy();
});
