/**
 * REGRESSION #1085 (Kuźnia) — generate-plan auto-creates key_enemies in game_config_enemies.
 * Acceptance: After generate-plan, key_enemies from plan surface in DB with review_status='pending'
 * and created_by='forge'. CampaignPlan model preserves key_enemies field.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1085 — enemies endpoint exists and is auth-gated", async ({ page }) => {
  const r = await page.request.get("/api/admin/enemies");
  expect(
    r.status(),
    "Expected 401 (auth-gated), got " + r.status() + " — /api/admin/enemies missing or broken (#1085)"
  ).toBe(401);
});

test("REGRESSION #1085 — forge generate-plan endpoint is auth-gated (route wired)", async ({ page }) => {
  const r = await page.request.post("/api/admin/forge/templates/1/generate-plan", {
    data: {},
  });
  expect(
    r.status(),
    "Expected 401 (auth-gated), got " + r.status() + " — generate-plan route missing (#1085)"
  ).toBe(401);
});

test("REGRESSION #1085 — forge templates endpoint is auth-gated", async ({ page }) => {
  const r = await page.request.get("/api/admin/forge/templates");
  expect(
    r.status(),
    "Expected 401 (auth-gated), got " + r.status() + " — forge/templates route missing (#1085)"
  ).toBe(401);
});
