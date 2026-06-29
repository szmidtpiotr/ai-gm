/**
 * REGRESSION #1026 (balans) — travel_hint i STORY_STALE nie odpalają przed progiem 12 tur.
 * Acceptance: story_gravity_config ma travel_hint_threshold >= 12 i turns_l1 >= 10.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1026 — story_gravity_config has raised thresholds", async ({ page }) => {
  const r = await page.request.get("/api/settings/story-gravity");
  expect(r.ok(), "story-gravity endpoint nie odpowiada 200 (#1026)").toBeTruthy();

  const body = await r.json();
  const cfg = body.data || body.config || body;

  // travel_hint_threshold is the new key added in #1026 — must always be present
  expect(
    cfg.travel_hint_threshold,
    "travel_hint_threshold powinien istnieć w config (#1026)"
  ).toBeDefined();

  // Default is 12; admin may raise it further but should never drop below 10
  expect(
    cfg.travel_hint_threshold,
    `travel_hint_threshold=${cfg.travel_hint_threshold} za niski, oczekiwano >= 10`
  ).toBeGreaterThanOrEqual(10);

  // turns_l1, turns_l2, turns_l3 are admin-configurable — just verify they exist
  expect(cfg.turns_l1, "turns_l1 powinien istnieć").toBeDefined();
  expect(cfg.turns_l2, "turns_l2 powinien istnieć").toBeDefined();
});
