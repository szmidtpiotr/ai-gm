/**
 * REGRESSION #418 #419 (E3/E4) — Campaign run stats block in end/death summary.
 * Acceptance: GET /api/campaigns/{id}/end-summary carries a `stats` object with
 * turn_count, gold, npcs_met, quests_completed for an ended/completed campaign.
 */
const { test, expect } = require("@playwright/test");

async function findEndedCampaign(page) {
  const r = await page.request.get("/api/campaigns");
  if (!r.ok()) return null;
  const body = await r.json();
  const list = body.campaigns || body || [];
  return list.find((c) => ["ended", "completed"].includes(c.status));
}

test("REGRESSION #418/#419 — end-summary carries campaign stats", async ({ page }) => {
  const camp = await findEndedCampaign(page);
  test.skip(!camp, "no ended/completed campaign in DB");

  const r = await page.request.get(`/api/campaigns/${camp.id}/end-summary`);
  expect(r.ok(), "end-summary endpoint not 200 (#418/#419)").toBeTruthy();

  const data = await r.json();
  expect(data.stats, "payload missing stats block (#418/#419)").toBeTruthy();
  for (const k of ["turn_count", "gold", "npcs_met", "quests_completed"]) {
    expect(k in data.stats, `stats missing ${k} (#418/#419)`).toBeTruthy();
    expect(typeof data.stats[k], `${k} must be a number (#418/#419)`).toBe("number");
  }
  // Core fields preserved (no regression)
  for (const k of ["outcome", "epitaph", "level", "character_name"]) {
    expect(k in data, `core field ${k} lost (#418/#419)`).toBeTruthy();
  }
});
