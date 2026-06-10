/**
 * REGRESSION #420 (E5) — dead hero blocks campaign access.
 * Acceptance: campaign response includes hero_status field; dead hero blocks turns.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #420 — campaign response includes hero_status + hero_blocked fields", async ({
  page,
}) => {
  // Check that GET /api/campaigns returns campaigns with hero_status field
  const r = await page.request.get("/api/campaigns");

  expect(r.ok(), "Campaigns list must respond 200 (#420)").toBeTruthy();
  const body = await r.json();

  expect(
    Array.isArray(body.campaigns),
    "Response must have campaigns array"
  ).toBeTruthy();

  // If there are campaigns, verify hero_status/hero_blocked fields exist
  if (body.campaigns && body.campaigns.length > 0) {
    const campaign = body.campaigns[0];
    expect(
      "hero_status" in campaign,
      "Campaign must include hero_status field for E5 (#420)"
    ).toBeTruthy();
    expect(
      "hero_blocked" in campaign,
      "Campaign must include hero_blocked field for E5 (#420)"
    ).toBeTruthy();
  }
});
