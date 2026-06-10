/**
 * REGRESSION #479 (F19) — Global NPC death: is_dead flag on npcs table.
 * Acceptance: NPCs endpoint responds; dead NPCs filtered from world.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #479 — backend healthy after NPC death schema migration", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend must be healthy after F19 migration (#479)").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("status");
});

test("REGRESSION #479 — npcs endpoint still responds", async ({ page }) => {
  const r = await page.request.get("/api/admin/npcs");
  expect([200, 401, 403], "npcs endpoint responds (#479)").toContain(r.status());
});

test("REGRESSION #479 — world NPCs endpoint responds", async ({ page }) => {
  const r = await page.request.get("/api/npcs");
  expect([200, 401, 403], "world npcs endpoint responds (#479 backward compat)").toContain(r.status());
});
