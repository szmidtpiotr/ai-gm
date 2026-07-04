/**
 * REGRESSION #1202 — content-as-code + DEV↔PROD schema alignment.
 * Acceptance: after schema-drop migration (B) + seed apply (A), game content is
 * still served — items and dungeons endpoints return non-empty seeded data, and
 * the dropped legacy columns are not exposed in item payloads.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1202 — seeded item content served, no legacy columns", async ({ page }) => {
  const r = await page.request.get("/api/items");
  expect(r.ok(), "GET /api/items must return 200 (#1202)").toBeTruthy();
  const body = await r.json();
  expect(body.ok).toBeTruthy();
  expect(Array.isArray(body.data)).toBeTruthy();
  expect(body.data.length, "items catalog must be non-empty after seed (#1202)").toBeGreaterThan(0);

  // Dropped legacy column (#1202 B) must not surface on item records.
  const sample = body.data[0];
  expect("image_prompt" in sample, "image_prompt was dropped (#1202 B)").toBeFalsy();
});

test("REGRESSION #1202 — seeded dungeon content served", async ({ page }) => {
  const r = await page.request.get("/api/dungeons");
  expect(r.ok(), "GET /api/dungeons must return 200 (#1202)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.dungeons)).toBeTruthy();
  expect(body.dungeons.length, "dungeon seeds must be non-empty (#1202)").toBeGreaterThan(0);
  // Dropped legacy column must not surface.
  expect("difficulty_config_json" in (body.dungeons[0] || {}), "difficulty_config_json dropped (#1202 B)").toBeFalsy();
});
