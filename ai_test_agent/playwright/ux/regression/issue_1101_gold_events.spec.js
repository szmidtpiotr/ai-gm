/**
 * REGRESSION #1101 (gold_events) — service payments must be VISIBLE.
 * The 💰 chat bubble ("-2 zł — Gospoda: posiłek") is built from
 * game_config_services (label + cost_gp). This asserts the data source the
 * bubble depends on is intact: tavern_meal is active, priced, and labelled.
 * Acceptance: /api/debug/service-price?key=tavern_meal → found, integer cost, label.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1101 — tavern_meal service has label + integer cost (bubble data source)", async ({ page }) => {
  const r = await page.request.get("/api/debug/service-price?key=tavern_meal");
  expect(r.ok(), "service-price endpoint nie odpowiada 200 (#1101)").toBeTruthy();
  const body = await r.json();
  expect(body.found, "tavern_meal musi istnieć i być aktywne (#1101)").toBeTruthy();
  expect(Number.isInteger(body.cost_gp), "cost_gp musi być liczbą całkowitą (#1101)").toBeTruthy();
  expect(body.cost_gp).toBeGreaterThan(0);
  expect(typeof body.label === "string" && body.label.length > 0,
    "usługa musi mieć etykietę do dymka 💰 (#1101)").toBeTruthy();
});

test("REGRESSION #1101 — unknown service → found=false, no fake bubble data", async ({ page }) => {
  const r = await page.request.get("/api/debug/service-price?key=__nope_1101__");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  expect(body.found, "nieznana usługa nie może zwracać danych (#1101)").toBeFalsy();
});
