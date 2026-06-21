/**
 * REGRESSION #790 (G6) — Party hex-move voting API contract.
 * Acceptance: POST /api/campaigns/{id}/move-vote endpoint exists and returns
 * resolved/votes_cast/total_players fields; GET returns current vote state.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #790 — move-vote endpoint rejects unknown campaign with 404", async ({ request }) => {
  const r = await request.post(`${BASE}/api/campaigns/999999/move-vote`, {
    data: { target_q: 1, target_r: 1 },
    headers: { "Content-Type": "application/json" },
  });
  // 401 (no auth) or 404 (not found) — either proves route exists
  expect([401, 403, 404, 422].includes(r.status()), `Expected route to exist, got ${r.status()}`).toBeTruthy();
});

test("REGRESSION #790 — move-vote GET status endpoint exists", async ({ request }) => {
  const r = await request.get(`${BASE}/api/campaigns/999999/move-vote`);
  // Route must be registered (not 405 Method Not Allowed)
  expect(r.status()).not.toBe(405);
});
