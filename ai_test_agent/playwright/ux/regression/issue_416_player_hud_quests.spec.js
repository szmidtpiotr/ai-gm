/**
 * REGRESSION #416 (E1) — Player HUD quest bar loaded on campaign entry.
 * Acceptance: GET /api/campaigns/{id}/quests returns 200 with active_quests array;
 * quest bar is populated on enterGame() without waiting for a turn.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #416 — /campaigns/:id/quests endpoint returns active_quests", async ({ page }) => {
  // Find a campaign ID from the campaigns list
  const listResp = await page.request.get("/api/campaigns");
  expect(listResp.ok(), "campaigns list endpoint failed (#416)").toBeTruthy();
  const listBody = await listResp.json();
  const campaigns = listBody.campaigns || listBody;
  expect(Array.isArray(campaigns) && campaigns.length > 0, "no campaigns in DB (#416)").toBeTruthy();

  const campaignId = campaigns[0].id;

  // The new endpoint must exist and return the right shape
  const r = await page.request.get(`/api/campaigns/${campaignId}/quests`);
  expect(r.ok(), `GET /api/campaigns/${campaignId}/quests not 200 (#416)`).toBeTruthy();

  const body = await r.json();
  expect("active_quests" in body, "response missing active_quests field (#416)").toBeTruthy();
  expect(Array.isArray(body.active_quests), "active_quests must be array (#416)").toBeTruthy();
});

test("REGRESSION #416 — /campaigns/:id/quests 404 for unknown campaign", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/999999999/quests");
  expect(r.status(), "expected 404 for unknown campaign (#416)").toBe(404);
});
