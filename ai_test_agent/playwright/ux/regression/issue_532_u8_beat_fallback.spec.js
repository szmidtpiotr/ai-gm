/**
 * REGRESSION #532 (U8) — Beat fallback + Story Gravity: weryfikuje że /api/settings/story-gravity
 * zwraca l3_enabled_gotowa i że endpoint /api/admin/campaigns/{id}/gm-plan zawiera story_gravity.
 * Acceptance: admin może zobaczyć stan Story Gravity w zakładce Plan GM kampanii.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #532 U8 — story-gravity config contains l3_enabled_gotowa", async ({ page }) => {
  const r = await page.request.get("/api/settings/story-gravity");
  expect(r.ok(), "settings/story-gravity endpoint nie odpowiada 200 (#532)").toBeTruthy();
  const body = await r.json();
  expect(body.ok, "response.ok powinno być true").toBeTruthy();
  const cfg = body.data || {};
  expect(
    typeof cfg.l3_enabled_gotowa === "boolean",
    `l3_enabled_gotowa powinno być boolean (#532)`
  ).toBeTruthy();
  expect(cfg.l3_enabled_gotowa, "l3_enabled_gotowa domyślnie true dla Gotowej Kampanii").toBe(true);
  expect(typeof cfg.turns_l1 === "number", "turns_l1 powinno być liczbą").toBeTruthy();
});

test("REGRESSION #532 U8 — gm-plan endpoint includes story_gravity field", async ({ page }) => {
  const listResp = await page.request.get("/api/admin/campaigns?limit=5");
  if (!listResp.ok()) { test.skip(); return; }
  const listBody = await listResp.json();
  const campaigns = listBody.items || listBody.campaigns || [];
  if (!campaigns.length) { test.skip(); return; }
  const campId = campaigns[0].id;
  const r = await page.request.get(`/api/admin/campaigns/${campId}/gm-plan`);
  expect(r.ok(), `gm-plan for campaign ${campId} not 200 (#532)`).toBeTruthy();
  const body = await r.json();
  expect(
    typeof body.story_gravity === "object" && body.story_gravity !== null,
    "story_gravity should be object in gm-plan response (#532)"
  ).toBeTruthy();
  expect(typeof body.story_gravity.level === "number", "story_gravity.level should be number").toBeTruthy();
  expect(typeof body.story_gravity.turns_since_beat === "number", "turns_since_beat should be number").toBeTruthy();
});
