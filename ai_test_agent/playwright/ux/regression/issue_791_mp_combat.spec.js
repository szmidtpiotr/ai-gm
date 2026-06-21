/**
 * REGRESSION #791 (G7) — Walka MP: endpointy /combat/start i /combat/action dostępne.
 * Acceptance: POST /api/multiplayer/campaigns/999/combat/start zwraca 400 (brak kampanii),
 * nie 404 (endpointu nie ma) — co potwierdza że endpoint istnieje i routing działa.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #791 G7 — endpoint /campaigns/{id}/combat/start istnieje (routing)", async ({ page }) => {
  const r = await page.request.post("/api/campaigns/999999/combat/start", {
    data: { enemy_keys: ["goblin"] },
  });
  // 400 = endpoint exists but campaign not found / validation error
  // 404 = endpoint doesn't exist (routing broken)
  // 401 = auth required but endpoint exists
  expect([400, 401, 422], "endpoint /combat/start powinien istnieć (nie 404)").toContain(r.status());
});

test("REGRESSION #791 G7 — endpoint /campaigns/{id}/combat/action istnieje (routing)", async ({ page }) => {
  const r = await page.request.post("/api/campaigns/999999/combat/action", {
    data: {
      action_type: "defense",
      character_id: 1,
    },
  });
  expect([400, 401, 422], "endpoint /combat/action powinien istnieć (nie 404)").toContain(r.status());
});
