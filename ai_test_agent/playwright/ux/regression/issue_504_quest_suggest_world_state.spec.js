/**
 * REGRESSION #504 (C10) — QUEST_SUGGEST pipeline: parse → game_sessions.active_quests → snapshot.
 * Acceptance: /world-state endpoint returns valid snapshot structure with active_quests array.
 * Structural contract test — does not depend on live quest data from specific campaigns.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #504 — world-state endpoint returns valid snapshot structure", async ({ page }) => {
  const loginResp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(loginResp.ok(), "admin login must succeed (#504)").toBeTruthy();
  const loginBody = await loginResp.json();
  const token = loginBody.token || loginBody.access_token;
  expect(token, "login must return token (#504)").toBeTruthy();

  // Use campaign 1204 which has known snapshots
  const r = await page.request.get("/api/admin/campaigns/1204/world-state", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "world-state endpoint must return 200 (#504)").toBeTruthy();

  const body = await r.json();
  expect(body.snapshots, "response must have snapshots array (#504)").toBeDefined();
  expect(Array.isArray(body.snapshots), "snapshots must be array (#504)").toBeTruthy();
  expect(body.snapshots.length, "campaign 1204 must have snapshots (#504)").toBeGreaterThan(0);

  // Structural contract: latest snapshot must have active_quests key as array
  const snap = body.latest?.snapshot_json || body.snapshots[0]?.snapshot_json;
  expect(snap, "snapshot_json must be present (#504)").toBeDefined();
  expect(Array.isArray(snap.active_quests), "snapshot_json.active_quests must be array (#504)").toBeTruthy();

  // No QUEST_SUGGEST tags should leak into stored narrative
  const narrative = typeof snap.narrative === "string" ? snap.narrative : JSON.stringify(snap);
  expect(narrative.includes("[QUEST_SUGGEST"), "QUEST_SUGGEST tag must be stripped before storing (#504)").toBeFalsy();
});

test("REGRESSION #504 — quest_suggest_parser: backend healthy (C10 deployed)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend must be healthy (#504 — C10 parser deployed)").toBeTruthy();
});
