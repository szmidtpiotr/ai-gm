/**
 * REGRESSION #860 (COMBAT) — short/long rest must be blocked while combat is active.
 * Acceptance: rest endpoint stays healthy after adding the active_combat gate —
 * a non-combat rest request returns a structured 4xx (never a 500), proving the new
 * gate (rest_service._has_active_combat) doesn't break the endpoint. Full in-combat
 * 409 "in_combat" path is covered deterministically by the pytest unit test.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #860 — rest endpoint healthy after combat gate", async ({ page }) => {
  // No active combat for a bogus/idle character → endpoint must respond with a
  // structured client error, NOT a 500 (which the new gate could cause if wired wrong).
  const r = await page.request.post("/api/characters/1/rest?type=short");
  expect(r.status(), "rest endpoint returned 500 — gate broke it (#860)").not.toBe(500);
  expect(r.status() < 500, `unexpected server error ${r.status()} (#860)`).toBeTruthy();
});
