/**
 * REGRESSION #481 (F21) — World State history endpoints exist and diff endpoint works.
 * Acceptance: GET /api/admin/campaigns/{id}/world-state returns snapshot list;
 *             diff endpoint returns 404 for nonexistent snapshot IDs.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin dev-login failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  return body.token;
}

test("REGRESSION #481 — world-state history list endpoint returns shape", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const r = await request.get(`${BASE}/api/admin/campaigns/1/world-state`, { headers });
  expect(r.ok(), `world-state endpoint must return 200 (#481), got ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("snapshots");
  expect(body).toHaveProperty("latest");
  expect(Array.isArray(body.snapshots), "snapshots must be array").toBeTruthy();
});

test("REGRESSION #481 — world-state latest endpoint returns shape", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const r = await request.get(`${BASE}/api/admin/campaigns/1/world-state/latest`, { headers });
  expect(r.ok(), `world-state/latest must return 200 (#481), got ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("snapshot");
});

test("REGRESSION #481 — world-state diff endpoint returns 404 for nonexistent snap", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const r = await request.get(`${BASE}/api/admin/campaigns/1/world-state/diff?a=999999&b=999998`, { headers });
  expect(r.status()).toBe(404);
});
