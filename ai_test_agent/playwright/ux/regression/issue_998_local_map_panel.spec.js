/**
 * REGRESSION #998 (FAZA ML) — Local sub-map panel API contract.
 * Acceptance: GET /local-map returns has_local_map + hexes with encounter_chance/id/label.
 * Local-travel endpoint returns moved/local_hex/clock shape.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #998 — /local-map returns has_local_map and hex fields for Wolanka hub", async ({ page }) => {
  // Campaign 99791 (Pierwsze Kroki) is in Wolanka which has ≥2 sub-locs
  const r = await page.request.get("/api/campaigns/99791/local-map");
  expect(r.ok(), "/local-map endpoint should return 200").toBeTruthy();

  const body = await r.json();
  expect(body.has_local_map, "has_local_map should be true for Wolanka").toBeTruthy();
  expect(Array.isArray(body.hexes), "hexes should be an array").toBeTruthy();
  expect(body.hexes.length, "should have ≥2 local hexes").toBeGreaterThanOrEqual(2);
  expect(body.hub_key, "hub_key should be present").toBeTruthy();
  expect(body.hub_label, "hub_label should be present").toBeTruthy();

  // Verify frontend-required fields on each hex
  for (const hex of body.hexes) {
    expect(typeof hex.id === "number", `hex.id must be a number (got ${typeof hex.id})`).toBeTruthy();
    expect(typeof hex.q === "number", "hex.q must be a number").toBeTruthy();
    expect(typeof hex.r === "number", "hex.r must be a number").toBeTruthy();
    expect(typeof hex.encounter_chance === "number", "hex.encounter_chance must be a number").toBeTruthy();
  }
});

test("REGRESSION #998 — safe hexes have encounter_chance=0, risky have encounter_chance>0", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/99791/local-map");
  expect(r.ok()).toBeTruthy();
  const { hexes } = await r.json();

  const safe = hexes.filter(h => h.encounter_chance === 0.0);
  const risky = hexes.filter(h => h.encounter_chance > 0.0);

  expect(safe.length, "at least one safe hex expected").toBeGreaterThan(0);
  expect(risky.length, "at least one risky hex expected").toBeGreaterThan(0);
});

test("REGRESSION #998 — /local-map returns has_local_map=false outside settlement", async ({ page }) => {
  // Campaign with no sub-locs should return has_local_map=false
  // Campaign 99784 is in step_wilkow (wilderness, no local hexes)
  const r = await page.request.get("/api/campaigns/99784/local-map");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  expect(body.has_local_map, "wilderness campaign should not have local map").toBeFalsy();
});
