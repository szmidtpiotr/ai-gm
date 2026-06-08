/**
 * REGRESSION #428 (E13) — generic encounter pool is deployed + admin list is gated.
 * The seeded pool (biome/trigger/level tags) and biome/level matching are covered
 * deterministically by pytest. This spec confirms the admin encounters endpoint is
 * live and auth-gated (so the pool is reachable only by admins).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #428 — forge encounters endpoint is auth-gated", async ({ page }) => {
  const r = await page.request.get("/api/admin/forge/encounters");
  // Endpoint deployed; without an admin token it must reject (401), never 404.
  expect([401, 200].includes(r.status()), `forge encounters endpoint missing (#428): ${r.status()}`).toBeTruthy();
  expect(r.status(), "encounters endpoint must be auth-gated (#428)").toBe(401);
});
