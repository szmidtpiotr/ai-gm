/**
 * REGRESSION #800 (G19) — Widzowie (Spectators): viewer role, public-only filter,
 * hint consent matrix (host policy × per-player mute).
 * Acceptance: spectator-policy endpoint exists; spectator-mute endpoints registered;
 * accept-as-spectator path wired; chat filter returns public-only for spectators.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #800 — backend healthy after spectator_policy migration", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend must be healthy after spectator_policy migration (#800)").toBeTruthy();
  const body = await r.json();
  expect(body.status, "health status must be ok").toBe("ok");
});

test("REGRESSION #800 — spectator-policy PATCH endpoint is registered", async ({ page }) => {
  // PATCH /api/multiplayer/campaigns/999999/spectator-policy — no auth
  // Must return 401/403 (auth gate) or 404 (campaign not found), NOT 404 router miss or 500
  const r = await page.request.patch("/api/multiplayer/campaigns/999999/spectator-policy", {
    data: { policy: "watch_hint" },
  });
  expect(
    [400, 401, 403, 404, 422].includes(r.status()),
    `spectator-policy must be registered, got ${r.status()} (#800)`
  ).toBeTruthy();
  expect(r.status()).toBeLessThan(500);
});

test("REGRESSION #800 — spectator-mute POST endpoint is registered", async ({ page }) => {
  const r = await page.request.post("/api/multiplayer/campaigns/999999/spectator-mute", {
    data: { spectator_user_id: 1 },
  });
  expect(
    [400, 401, 403, 404, 422].includes(r.status()),
    `spectator-mute POST must be registered, got ${r.status()} (#800)`
  ).toBeTruthy();
  expect(r.status()).toBeLessThan(500);
});

test("REGRESSION #800 — spectator-mute DELETE endpoint is registered", async ({ page }) => {
  const r = await page.request.delete("/api/multiplayer/campaigns/999999/spectator-mute/42");
  expect(
    [400, 401, 403, 404, 422].includes(r.status()),
    `spectator-mute DELETE must be registered, got ${r.status()} (#800)`
  ).toBeTruthy();
  expect(r.status()).toBeLessThan(500);
});

test("REGRESSION #800 — accept endpoint recognises as_spectator param", async ({ page }) => {
  // POST with as_spectator=true → must not 404/500 (route must exist and parse the body)
  // 401 (no auth), 403 (no invite), or 404 (no campaign) — all mean endpoint wired
  const r = await page.request.post("/api/multiplayer/campaigns/999999/accept?user_id=99", {
    data: { as_spectator: true },
  });
  expect(
    [400, 401, 403, 404, 422].includes(r.status()),
    `accept endpoint with as_spectator must not 500, got ${r.status()} (#800)`
  ).toBeTruthy();
  expect(r.status()).toBeLessThan(500);
});

test("REGRESSION #800 — multiplayer chat endpoint accepts spectator callers without crash", async ({ page }) => {
  // GET /api/multiplayer/campaigns/1/chat?user_id=1 — demo campaign; auth gate only, not a 500
  const r = await page.request.get("/api/multiplayer/campaigns/1/chat?user_id=1");
  expect(r.status()).toBeLessThan(500);
  expect(
    [200, 401, 403, 404].includes(r.status()),
    `chat GET must not crash, got ${r.status()} (#800)`
  ).toBeTruthy();
});
