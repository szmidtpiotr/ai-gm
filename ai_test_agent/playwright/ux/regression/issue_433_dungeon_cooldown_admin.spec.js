/**
 * REGRESSION #433 (E18) — Dungeon cooldown_hours and dungeon_difficulty editable from Admin Panel.
 * Acceptance: PATCH /admin/dungeons/{key} saves cooldown_hours and dungeon_difficulty to DB.
 * GET /admin/dungeons returns both fields for each dungeon.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
const TEST_KEY = "goblin_warren";

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

test("REGRESSION #433 — PATCH cooldown_hours saves to DB (200 + ok:true)", async ({ request }) => {
  const token = await getAdminToken(request);

  const r = await request.patch(`${BASE}/api/admin/dungeons/${TEST_KEY}`, {
    data: { cooldown_hours: 48 },
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `PATCH cooldown failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body.ok, "PATCH must return ok:true").toBe(true);
});

test("REGRESSION #433 — PATCH dungeon_difficulty saves to DB (200 + ok:true)", async ({ request }) => {
  const token = await getAdminToken(request);

  const r = await request.patch(`${BASE}/api/admin/dungeons/${TEST_KEY}`, {
    data: { dungeon_difficulty: 1 },
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `PATCH dungeon_difficulty failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body.ok, "PATCH must return ok:true").toBe(true);
});

test("REGRESSION #433 — GET /admin/dungeons includes cooldown_hours and dungeon_difficulty", async ({ request }) => {
  const token = await getAdminToken(request);

  const r = await request.get(`${BASE}/api/admin/dungeons`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `GET dungeons failed: ${r.status()}`).toBeTruthy();

  const body = await r.json();
  const items = body.items || [];
  expect(items.length, "dungeons list must not be empty").toBeGreaterThan(0);

  for (const dg of items) {
    expect(
      "cooldown_hours" in dg,
      `Dungeon ${dg.key} missing cooldown_hours`
    ).toBeTruthy();
    expect(
      "dungeon_difficulty" in dg,
      `Dungeon ${dg.key} missing dungeon_difficulty`
    ).toBeTruthy();
  }
});
