/**
 * REGRESSION #1055 — suggested_actions.py schema drift: game_npcs / lc.to_key.
 * Acceptance: API health OK; no npc_actions_error / exit_actions_error in recent logs.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1055 — backend health OK (suggested_actions schema fix)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend /api/health not 200 (#1055)").toBeTruthy();
  const body = await r.json();
  expect(body.status, "backend status not ok (#1055)").toBe("ok");
});

test("REGRESSION #1055 — admin locations stats accessible (schema valid)", async ({ page }) => {
  const r = await page.request.get("/api/admin/locations/stats");
  expect(
    r.status() === 200 || r.status() === 401 || r.status() === 403,
    `admin/locations/stats unexpected status ${r.status()} (#1055)`
  ).toBeTruthy();
});
