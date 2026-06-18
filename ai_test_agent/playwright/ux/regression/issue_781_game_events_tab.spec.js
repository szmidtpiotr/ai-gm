/**
 * REGRESSION #781 — Zakładka 🗓 Zdarzenia w monitorze kampanii (game_events per-campaign).
 * Acceptance: GET /api/campaigns/{id}/game-events zwraca kształt {campaign_id, count, game_events[]}.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #781 — endpoint game-events zwraca poprawny kształt", async ({ page }) => {
  // Kampania 1 może nie istnieć — endpoint i tak musi zwrócić 200 z pustą listą (nie 500/404)
  const r = await page.request.get("/api/campaigns/1/game-events?limit=10");
  expect(r.status(), "GET /api/campaigns/1/game-events powinien zwrócić 200 (#781)").toBe(200);
  const body = await r.json();
  expect(body).toHaveProperty("campaign_id");
  expect(body).toHaveProperty("count");
  expect(Array.isArray(body.game_events), "game_events musi być tablicą (#781)").toBeTruthy();
});

test("REGRESSION #781 — filtr event_type działa (kontrakt)", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1/game-events?event_type=gold_grant&limit=10");
  expect(r.status()).toBe(200);
  const body = await r.json();
  // wszystkie zwrócone wiersze (jeśli są) muszą mieć typ gold_grant
  for (const ev of body.game_events) {
    expect(ev.event_type).toBe("gold_grant");
  }
});

test("REGRESSION #781 — każde zdarzenie ma data jako obiekt", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1/game-events?limit=50");
  expect(r.status()).toBe(200);
  const body = await r.json();
  for (const ev of body.game_events) {
    expect(typeof ev.data).toBe("object");
    expect(ev).toHaveProperty("event_type");
    expect(ev).toHaveProperty("created_at");
  }
});
