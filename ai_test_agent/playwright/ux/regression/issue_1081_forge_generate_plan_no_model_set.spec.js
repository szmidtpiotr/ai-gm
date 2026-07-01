/**
 * REGRESSION #1081 — Kuźnia generate-plan: endpoint /api/admin/forge/templates/:id/generate-plan
 * returns 401 (auth required) — not 404 — confirming the route exists and is protected.
 * Acceptance: endpoint present, auth-gated; '404' would mean route was broken.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1081 — forge generate-plan endpoint exists and is auth-gated", async ({ page }) => {
  const r = await page.request.post("/api/admin/forge/templates/1/generate-plan", {
    data: { suggested_act_count: 2 },
  });
  expect(
    r.status(),
    "Expected 401 (auth required), got " + r.status() + " — endpoint missing or route broken"
  ).toBe(401);
});

test("REGRESSION #1081 — forge templates list endpoint responds", async ({ page }) => {
  const r = await page.request.get("/api/admin/forge/templates");
  expect(
    r.status(),
    "forge/templates must return 401 (auth-gated, not 404)"
  ).toBe(401);
});
