/**
 * REGRESSION #422 (E7) — campaign_templates required_npc_keys / required_beats / player_visible.
 * Acceptance: published-template payload from /api/campaign-templates carries the 3 new fields.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #422 — template payload exposes new fields", async ({ page }) => {
  const r = await page.request.get("/api/campaign-templates");
  expect(r.ok(), "/api/campaign-templates not 200 (#422)").toBeTruthy();
  const body = await r.json();
  test.skip(!body.items || !body.items.length, "no published templates to inspect");

  const t = body.items[0];
  expect("required_npc_keys" in t, "missing required_npc_keys (#422)").toBeTruthy();
  expect("required_beats" in t, "missing required_beats (#422)").toBeTruthy();
  expect("player_visible" in t, "missing player_visible (#422)").toBeTruthy();
  expect(Array.isArray(t.required_npc_keys), "required_npc_keys must be array (#422)").toBeTruthy();
  expect(Array.isArray(t.required_beats), "required_beats must be array (#422)").toBeTruthy();
});
