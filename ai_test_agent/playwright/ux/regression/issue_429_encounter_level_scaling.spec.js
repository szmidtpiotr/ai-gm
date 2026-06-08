/**
 * REGRESSION #429 (E14) — encounter level scaling does not break the turn pipeline.
 * The level-band gating (encounter_matches: level_min/level_max) is unit-tested by
 * pytest. This spec is a deployment smoke: the API health + campaigns endpoints still
 * respond 200 after wiring the new level filter into the encounter engine.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #429 — backend healthy after encounter level-scaling wiring", async ({ page }) => {
  const h = await page.request.get("/api/health");
  expect(h.ok(), "health endpoint not 200 (#429)").toBeTruthy();

  const c = await page.request.get("/api/campaigns");
  expect(c.ok(), "campaigns endpoint not 200 (#429)").toBeTruthy();
});
