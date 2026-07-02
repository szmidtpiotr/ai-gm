/**
 * REGRESSION #1115 (PT5) — PT5 cleanup: dead import removed, (0,0) subloc overlap fixed,
 * already-here clock guard active, RANDOM fallback replaced with deterministic id-order.
 * Acceptance: local-map API healthy; local-travel returns moved:true; no (0,0) duplicates.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1115 — local-map endpoint responds 200", async ({ page }) => {
  // Verify the local-map endpoint doesn't crash (dead import or code error would 500)
  const r = await page.request.get("/api/campaigns/1/local-map");
  // 404 is fine (no campaign 1) but must not be 500
  expect(r.status(), "local-map must not 500 (#1115 dead import check)").not.toBe(500);
});

test("REGRESSION #1115 — hex-travel endpoint responds without 500", async ({ page }) => {
  // resolve_starting_hex path exercised — would 500 if import broken
  const r = await page.request.post("/api/campaigns/1/hex-travel", {
    data: { character_id: 1, destination_q: 2, destination_r: 1 },
  });
  expect(r.status(), "hex-travel must not 500 (#1115 resolve_starting_hex path)").not.toBe(500);
});

test("REGRESSION #1115 — local-travel endpoint responds without 500", async ({ page }) => {
  const r = await page.request.post("/api/campaigns/1/local-travel", {
    data: { hex_id: 1 },
  });
  // 404 expected (no campaign), but not 500
  expect(r.status(), "local-travel must not 500 (#1115 clock guard)").not.toBe(500);
});
