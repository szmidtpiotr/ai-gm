/**
 * REGRESSION #415 — Map endpoints: hex-terrain-config, generate, clear, locations-map all respond.
 * Acceptance: four previously 404 endpoints now return 401 (auth guard) or 200 (with auth).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #415 — /hex-terrain-config requires auth (not 404)", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/hex-terrain-config");
  // Must be 401 (auth guard active), NOT 404 (endpoint missing)
  expect(r.status(), "#415: /hex-terrain-config must not be 404").not.toBe(404);
  expect(r.status(), "#415: /hex-terrain-config must require auth").toBe(401);
});

test("REGRESSION #415 — /locations-map requires auth (not 404)", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/locations-map");
  expect(r.status(), "#415: /locations-map must not be 404").not.toBe(404);
  expect(r.status(), "#415: /locations-map must require auth").toBe(401);
});

test("REGRESSION #415 — POST /generate requires auth (not 404)", async ({ page }) => {
  const r = await page.request.post("/api/admin/world/generate", {
    data: { seed: 42, radius: 2 },
  });
  expect(r.status(), "#415: POST /generate must not be 404").not.toBe(404);
  expect(r.status(), "#415: POST /generate must require auth").toBe(401);
});

test("REGRESSION #415 — DELETE /clear requires auth (not 404)", async ({ page }) => {
  const r = await page.request.delete("/api/admin/world/clear");
  expect(r.status(), "#415: DELETE /clear must not be 404").not.toBe(404);
  expect(r.status(), "#415: DELETE /clear must require auth").toBe(401);
});
