/**
 * REGRESSION #993 (FAZA ML) — Local hex map (map_level=1) for hub sub-locations.
 * Acceptance: GET /api/campaigns/{id}/local-map returns has_local_map and hexes array;
 *             local-map endpoint is reachable and returns expected shape.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #993 — local-map endpoint responds with correct shape", async ({ page }) => {
  // Pick demo campaign (id=1 — always exists in DEV seed)
  const r = await page.request.get("/api/campaigns/1/local-map");
  expect(r.ok(), "local-map endpoint must respond 200 (#993)").toBeTruthy();

  const body = await r.json();
  expect(typeof body.has_local_map, "has_local_map must be boolean").toBe("boolean");
  expect(Array.isArray(body.hexes), "hexes must be an array").toBeTruthy();
});

test("REGRESSION #993 — local-map hexes have map_level=1 when present", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1/local-map");
  expect(r.ok()).toBeTruthy();

  const body = await r.json();
  if (body.hexes.length > 0) {
    for (const hex of body.hexes) {
      expect(hex.map_level, "All local hexes must have map_level=1").toBe(1);
    }
  }
});

test("REGRESSION #993 — local-travel rejects invalid hex_id", async ({ page }) => {
  const r = await page.request.post("/api/campaigns/1/local-travel", {
    data: { hex_id: 999999 },
    headers: { "Content-Type": "application/json" },
  });
  // Expect 404 for non-existent local hex
  expect(r.status(), "Non-existent hex_id must return 404").toBe(404);
});
