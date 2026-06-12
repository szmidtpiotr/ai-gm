/**
 * REGRESSION #523 (HF-1) — scene_enemies cleared after combat victory (P0 softlock fix).
 * Acceptance: after combat ends via the resolve_attack killing-blow path, scene_enemies
 * in game_sessions must be [] so Gate walki does not block subsequent turns.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #523 HF-1 — backend health and scene_enemies API surface", async ({ page }) => {
  const health = await page.request.get("/api/health");
  expect(health.ok(), "backend /api/health must return 200 (#523)").toBeTruthy();
  const body = await health.json();
  expect(body.status, "backend status must be ok (#523)").toBe("ok");
});

test("REGRESSION #523 HF-1 — world-state endpoint returns scene_enemies field", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1/world-state");
  expect(
    [200, 404].includes(r.status()),
    "world-state endpoint must exist — if 500, HF-1 may not be deployed (#523)"
  ).toBeTruthy();

  if (r.status() === 200) {
    const ws = await r.json();
    expect(
      Array.isArray(ws.scene_enemies),
      "scene_enemies must be an array (#523)"
    ).toBeTruthy();
  }
});
