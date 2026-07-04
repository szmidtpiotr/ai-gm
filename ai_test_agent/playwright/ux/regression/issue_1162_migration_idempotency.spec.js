/**
 * REGRESSION #1162 / #1163 / #1164 — migration runner idempotency + single-boot completeness.
 * The migration runners were rewritten (schema_migrations applied-set + fix-point loop) so that
 * (a) admin runtime edits survive restarts, (b) a fresh DB is complete after one boot, and
 * (c) the XP meta keys have a single canonical value. This spec is the deployed-backend smoke:
 * it proves the new boot sequence did NOT crash the backend and left the config surface intact.
 * Acceptance: /api/health is 200 and /api/mechanics/skills returns a populated skills catalog.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1162 — backend boots clean after migration-runner rewrite", async ({ page }) => {
  const health = await page.request.get("/api/health");
  expect(health.ok(), "backend nie wstał po zmianie migracji (#1163)").toBeTruthy();
});

test("REGRESSION #1162 — config tables intact post-migration (skills catalog)", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "endpoint umiejętności nie odpowiada 200 (#1162)").toBeTruthy();
  const body = await r.json();
  // game_config_skills musi być zaseedowane i nienaruszone po przebudowie runnerów migracji.
  expect(Array.isArray(body.skills)).toBeTruthy();
  expect(body.skills.length, "pusty katalog umiejętności — seed migracji uszkodzony").toBeGreaterThan(5);
});
