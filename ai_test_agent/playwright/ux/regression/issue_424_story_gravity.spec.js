/**
 * REGRESSION #424 (E9) — Story Gravity config endpoint, L3 forced scene OFF by default.
 * Acceptance: GET /api/settings/story-gravity returns thresholds 5/10/15 and l3_enabled=false.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #424 — story-gravity config served with L3 off by default", async ({ page }) => {
  const r = await page.request.get("/api/settings/story-gravity");
  expect(r.ok(), "/api/settings/story-gravity not 200 (#424)").toBeTruthy();
  const body = await r.json();
  const c = body.data || {};
  for (const k of ["enabled", "turns_l1", "turns_l2", "turns_l3", "l3_enabled"]) {
    expect(k in c, `config missing ${k} (#424)`).toBeTruthy();
  }
  expect(typeof c.turns_l1).toBe("number");
  expect(c.turns_l1).toBeLessThan(c.turns_l2);
  expect(c.turns_l2).toBeLessThan(c.turns_l3);
  // L3 forced scene must default OFF.
  expect(c.l3_enabled === false || c.l3_enabled === 0, "L3 must default OFF (#424)").toBeTruthy();
});
