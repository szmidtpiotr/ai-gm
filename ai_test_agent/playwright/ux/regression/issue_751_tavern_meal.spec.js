/**
 * REGRESSION #751 — usługa gastronomiczna w karczmie ma własną cenę z bazy.
 * Posiłek (tavern_meal) = 2 GP, napój (tavern_drink) = 1 GP, nocleg (inn_night) nadal 5 GP.
 * Acceptance: gracz płacący za jedzenie traci 2 GP, nie 5 GP (inn_night).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #751 — tavern_meal kosztuje 2 GP (nie inn_night 5 GP)", async ({ page }) => {
  const r = await page.request.get("/api/debug/service-price?key=tavern_meal");
  expect(r.ok(), "endpoint /api/debug/service-price nie odpowiada 200 (#751)").toBeTruthy();
  const body = await r.json();
  expect(body.found, "usługa tavern_meal nie istnieje w game_config_services").toBeTruthy();
  expect(body.cost_gp, "posiłek musi kosztować 2 GP").toBe(2);
});

test("REGRESSION #751 — tavern_drink kosztuje 1 GP", async ({ page }) => {
  const r = await page.request.get("/api/debug/service-price?key=tavern_drink");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  expect(body.found, "usługa tavern_drink nie istnieje").toBeTruthy();
  expect(body.cost_gp).toBe(1);
});

test("REGRESSION #751 — inn_night nadal 5 GP (backward compat)", async ({ page }) => {
  const r = await page.request.get("/api/debug/service-price?key=inn_night");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  expect(body.found).toBeTruthy();
  expect(body.cost_gp, "nocleg musi pozostać 5 GP").toBe(5);
});
