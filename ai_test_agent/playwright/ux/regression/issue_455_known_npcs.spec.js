/**
 * REGRESSION #455 (SB-1) — GET /admin/campaigns/{id}/known-npcs returns NPC list.
 * Acceptance: endpoint returns {"npcs": [...], "count": N} for any active campaign;
 * auth guard rejects unauthenticated requests.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
const CAMPAIGN_ID = 1;

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin login failed: ${r.status()}`).toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #455 — known-npcs endpoint returns 200 with npcs + count", async ({ request }) => {
  const token = await adminToken(request);

  const r = await request.get(`${BASE}/api/admin/campaigns/${CAMPAIGN_ID}/known-npcs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `known-npcs GET failed: ${r.status()}`).toBeTruthy();

  const body = await r.json();
  expect(Array.isArray(body.npcs), "body.npcs must be array").toBeTruthy();
  expect(typeof body.count === "number", "body.count must be number").toBeTruthy();
  expect(body.count, "count must equal npcs length").toBe(body.npcs.length);
});

test("REGRESSION #455 — known-npcs requires auth (no token → 401/403)", async ({ request }) => {
  const r = await request.get(`${BASE}/api/admin/campaigns/${CAMPAIGN_ID}/known-npcs`);
  expect(
    r.status() === 401 || r.status() === 403,
    `Expected 401/403 without auth, got: ${r.status()}`
  ).toBeTruthy();
});

test("REGRESSION #455 — demo campaign has at least one NPC (Merchant from memory)", async ({ request }) => {
  const token = await adminToken(request);

  const r = await request.get(`${BASE}/api/admin/campaigns/${CAMPAIGN_ID}/known-npcs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();

  const body = await r.json();
  expect(body.count, "demo campaign must have at least one NPC").toBeGreaterThan(0);

  const labels = body.npcs.map((n) => n.label);
  expect(labels, "Merchant must be in demo campaign NPCs").toContain("Merchant");
});
