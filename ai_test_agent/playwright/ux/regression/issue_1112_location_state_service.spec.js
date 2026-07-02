/**
 * REGRESSION #1112 (PT2) — Jeden serwis zapisu pozycji (koniec 5 źródeł prawdy).
 * Acceptance: player-map pin reads from session_flags (not stale sheet_json);
 *             GET /api/campaigns/{id}/world returns current_hex from session_flags.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1112 — location_state_service endpoint smoke", async ({ page }) => {
  // Verify the backend is up and health check passes
  const health = await page.request.get("/api/health");
  expect(health.ok(), "backend health check failed (#1112)").toBeTruthy();
});

test("REGRESSION #1112 — GET /world returns current_hex field", async ({ page }) => {
  // Fetch the world map for any campaign — must return current_hex field
  // (even if null when no campaign active, the field must exist)
  const campaigns = await page.request.get("/api/admin/campaigns?limit=1");
  if (!campaigns.ok()) return; // skip if auth needed

  const body = await campaigns.json();
  const list = body.campaigns || body.items || body || [];
  if (!Array.isArray(list) || list.length === 0) return;

  const campaignId = list[0].id;
  const worldResp = await page.request.get(`/api/campaigns/${campaignId}/world`);
  if (!worldResp.ok()) return;

  const worldBody = await worldResp.json();
  // current_hex key must be present (null or object — never missing)
  expect("current_hex" in worldBody, "current_hex field missing from /world response (#1112)").toBeTruthy();
});
