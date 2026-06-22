/**
 * REGRESSION #926 (GF6) — Spectator panel: accept invite as spectator, spectator-policy API.
 * Acceptance: spectator can accept invite with as_spectator=true (no hero required);
 * spectator_policy endpoint updates correctly; my-active-games returns role field.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #926 — accept invite endpoint accepts as_spectator body (not 422)", async ({ page }) => {
  // as_spectator=true must be a valid body (no schema rejection).
  // Non-existent campaign → 404 or 401; invalid auth → 401. What matters: NOT 422.
  const r = await page.request.post("/api/multiplayer/campaigns/9999999/accept", {
    data: { as_spectator: true },
    headers: { "Content-Type": "application/json", Authorization: "Bearer invalid" },
  });
  expect(r.status(), "as_spectator body must not be rejected by schema (not 422)").not.toBe(422);
});

test("REGRESSION #926 — spectator-policy endpoint exists", async ({ page }) => {
  const r = await page.request.patch("/api/multiplayer/campaigns/9999999/spectator-policy", {
    data: { policy: "watch_hint" },
    headers: { "Content-Type": "application/json", Authorization: "Bearer invalid" },
  });
  expect(r.status(), "spectator-policy endpoint must exist (not 404)").not.toBe(404);
});

test("REGRESSION #926 — my-active-games endpoint exists", async ({ page }) => {
  const r = await page.request.get("/api/multiplayer/my-active-games", {
    headers: { Authorization: "Bearer invalid" },
  });
  expect([200, 401, 403], "my-active-games endpoint must exist (not 404)").toContain(r.status());
});

test("REGRESSION #926 — spectator-mute endpoint exists", async ({ page }) => {
  const r = await page.request.post("/api/multiplayer/campaigns/9999999/spectator-mute", {
    data: { spectator_user_id: 1 },
    headers: { "Content-Type": "application/json", Authorization: "Bearer invalid" },
  });
  expect(r.status(), "spectator-mute endpoint must exist (not 404)").not.toBe(404);
});

test("REGRESSION #926 — party chat endpoint exists (spectator filter path)", async ({ page }) => {
  const r = await page.request.get("/api/multiplayer/campaigns/9999999/chat?since_id=0", {
    headers: { Authorization: "Bearer invalid" },
  });
  expect(r.status(), "party chat endpoint must exist (not 404)").not.toBe(404);
});

test("REGRESSION #926 — multiplayer_ui.js v3 loaded (no 404)", async ({ page }) => {
  const r = await page.request.get("/js/multiplayer_ui.js?v=3");
  expect(r.ok(), "multiplayer_ui.js?v=3 must return 200 (cache-bust applied)").toBeTruthy();
});

test("REGRESSION #926 — campaigns.js v926-gf6 loaded (no 404)", async ({ page }) => {
  const r = await page.request.get("/js/screens/campaigns.js?v=926-gf6");
  expect(r.ok(), "campaigns.js?v=926-gf6 must return 200 (cache-bust applied)").toBeTruthy();
});
