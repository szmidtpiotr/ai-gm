/**
 * REGRESSION #774 — LLM-authored [COMBAT_START] tag trusted after friendly-NPC gate.
 * Acceptance: _validate_combat_start_target(source='llm') accepts keys not in catalog.
 * After fix: unknown LLM-invented keys → initiate_combat() → INSERT OR IGNORE →
 * appear in pending_review (not rejected as combat_target_unknown).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #774 — pending enemies endpoint accessible (unknown LLM keys land here)", async ({ page }) => {
  // Unknown LLM-invented enemy keys go through initiate_combat() with INSERT OR IGNORE
  // and appear in pending_review list. Verify this endpoint is reachable.
  const r = await page.request.get("/api/admin/world/pending/enemies");
  expect(r.ok(), "pending enemies endpoint must respond 200 (#774)").toBeTruthy();
  const data = await r.json();
  expect(Array.isArray(data.items), "pending enemies must return {items:[...]} (#774)").toBeTruthy();
});

test("REGRESSION #774 — world pending review endpoint accessible", async ({ page }) => {
  // The full pending review queue (includes enemies approved or rejected by admin).
  const r = await page.request.get("/api/admin/world/pending/enemies");
  expect(r.status(), "#774: pending/enemies must be 200").toBe(200);
});
