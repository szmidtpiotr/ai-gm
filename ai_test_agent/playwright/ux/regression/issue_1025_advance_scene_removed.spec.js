/**
 * REGRESSION #1025 — „Następna scena" button and advance-scene endpoints removed (V1 legacy).
 * Acceptance: POST /api/admin/campaigns/{id}/gm-plan/advance-scene returns 404 (not 422/200).
 *             Button no longer present in Plan GM HTML.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1025 — admin advance-scene endpoint removed (returns 404)", async ({ page }) => {
  const r = await page.request.post(
    "/api/admin/campaigns/1/gm-plan/advance-scene",
    { data: { note: "" }, headers: { "Content-Type": "application/json" } }
  );
  expect(r.status(), "advance-scene endpoint still exists — should be 404 (#1025)").toBe(404);
});

test("REGRESSION #1025 — player advance-scene endpoint removed (returns 404)", async ({ page }) => {
  const r = await page.request.post("/api/campaigns/1/gm-plan/advance-scene");
  expect(r.status(), "player advance-scene endpoint still exists — should be 404 (#1025)").toBe(404);
});
