/**
 * REGRESSION #1210 — port 4 mechanik walki V2 (Strach/Groza, hit-location,
 * death-save ladder, flee) do żywej combat_service.
 * Acceptance: endpoint /combat/flee istnieje (400 bez aktywnej walki) i 6 warunków
 * ran krytycznych jest w katalogu game_config_conditions (mechaniki wpięte, nie martwe).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1210 — flee endpoint istnieje i waliduje brak walki", async ({ page }) => {
  const r = await page.request.post(
    "/api/campaigns/999999999/combat/flee"
  );
  // Bez aktywnej walki → 400 (no_active_combat), NIE 404/500. Dowód że route żyje.
  expect(r.status(), "flee bez walki musi zwrócić 400 (#1210)").toBe(400);
  const body = await r.json();
  expect(String(body.detail || "")).toContain("no_active_combat");
});

test("REGRESSION #1210 — 6 warunków ran krytycznych w katalogu", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "katalog warunków musi odpowiadać 200 (#1210)").toBeTruthy();
  const body = await r.json();
  const list = Array.isArray(body) ? body : body.conditions || body.items || [];
  const keys = new Set(list.map((c) => c.key));
  for (const k of ["dazed", "winded", "arm_wound", "leg_wound", "disarmed", "hobbled"]) {
    expect(keys.has(k), `brak warunku '${k}' w katalogu (#1210)`).toBeTruthy();
  }
});
