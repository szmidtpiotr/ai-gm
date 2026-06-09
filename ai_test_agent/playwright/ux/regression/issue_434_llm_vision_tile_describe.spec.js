/**
 * REGRESSION #434 (E19) — LLM Vision: dungeon tile image → room description.
 * Acceptance: GET /admin/dungeon-tiles?needs_description=1 filters tiles missing descriptions.
 * PATCH /admin/dungeon-tiles/{id} with room_description saves to DB.
 * vision_service module importable in backend.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

let adminToken = null;

async function getAdminToken(request) {
  if (adminToken) return adminToken;
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin login failed: ${r.status()}`).toBeTruthy();
  adminToken = (await r.json()).token;
  return adminToken;
}

test("REGRESSION #434 — GET /admin/dungeon-tiles?needs_description=1 returns 200", async ({ request }) => {
  const token = await getAdminToken(request);
  const r = await request.get(`${BASE}/api/admin/dungeon-tiles?needs_description=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `needs_description filter failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.tiles), "response must have tiles array").toBeTruthy();
});

test("REGRESSION #434 — needs_description=1 returns only tiles with empty room_description", async ({ request }) => {
  const token = await getAdminToken(request);
  const r = await request.get(`${BASE}/api/admin/dungeon-tiles?needs_description=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const { tiles } = await r.json();
  for (const t of tiles) {
    const desc = t.room_description || "";
    expect(
      desc.length,
      `Tile ${t.id} has non-empty room_description but was returned by needs_description filter`
    ).toBe(0);
  }
});

test("REGRESSION #434 — PATCH room_description saves (200 + ok:true)", async ({ request }) => {
  const token = await getAdminToken(request);

  // Find a tile to test with
  const listR = await request.get(`${BASE}/api/admin/dungeon-tiles`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(listR.ok()).toBeTruthy();
  const { tiles } = await listR.json();
  expect(tiles.length, "need at least one tile to test PATCH").toBeGreaterThan(0);
  const tileId = tiles[0].id;
  const originalDesc = tiles[0].room_description || "";

  const testDesc = "__playwright_e19_test__";
  const r = await request.patch(`${BASE}/api/admin/dungeon-tiles/${tileId}`, {
    data: { room_description: testDesc },
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `PATCH failed: ${r.status()}`).toBeTruthy();
  expect((await r.json()).ok).toBe(true);

  // Restore
  await request.patch(`${BASE}/api/admin/dungeon-tiles/${tileId}`, {
    data: { room_description: originalDesc },
    headers: { Authorization: `Bearer ${token}` },
  });
});
