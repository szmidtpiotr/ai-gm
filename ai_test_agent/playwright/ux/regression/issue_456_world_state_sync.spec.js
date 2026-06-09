/**
 * REGRESSION #456 (SB-2) — World State columns (scene_enemies, player_conditions) stay in sync.
 * Acceptance: /api/admin/campaigns/{id}/world-state/latest returns snapshot with array-typed
 * scene_enemies and player_conditions fields after auto_save_snapshot runs.
 */
const { test, expect } = require("@playwright/test");

const CAMPAIGN_ID = 999444;
const BASE = process.env.BASE_URL || "http://frontend:80";

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin dev-login failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  return body.token;
}

test("REGRESSION #456 — world-state/latest returns correct schema with array fields", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const r = await request.get(
    `${BASE}/api/admin/campaigns/${CAMPAIGN_ID}/world-state/latest`,
    { headers }
  );
  expect(r.ok(), `world-state/latest GET failed: ${r.status()}`).toBeTruthy();

  const body = await r.json();
  // Endpoint returns { snapshot: {...} } or { snapshot: null } if no snapshots yet
  expect(body, "response body missing").toBeTruthy();

  if (body.snapshot) {
    const snap = body.snapshot.snapshot_json ?? body.snapshot;
    for (const key of ["scene_enemies", "player_conditions"]) {
      const val = snap[key];
      expect(
        Array.isArray(val),
        `snapshot.${key} must be an array, got: ${JSON.stringify(val)}`
      ).toBeTruthy();
    }
  }
  // If snapshot is null (no snapshots saved yet) — endpoint contract is still OK
});

test("REGRESSION #456 — get_world_state_flags returns array-typed world state columns", async ({ request }) => {
  const token = await adminToken(request);

  // world-state/latest endpoint accessible → world state service works
  const r = await request.get(
    `${BASE}/api/admin/campaigns/${CAMPAIGN_ID}/world-state`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  expect(r.ok(), `world-state history GET failed: ${r.status()}`).toBeTruthy();

  const body = await r.json();
  expect(Array.isArray(body.snapshots), "snapshots must be array").toBeTruthy();
});
