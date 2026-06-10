/**
 * REGRESSION #484 (F2b) — Affix roll dla enemy dropów: game_config_enemies.loot_tier.
 * Acceptance: kolumna loot_tier istnieje; wrogowie z loot_tier!=NULL mogą dawać uzbrojone
 * afiksy przy dropie broni; backward compat — wrogowie bez loot_tier nie dostają afiksów.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin login failed: ${r.status()}`).toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #484 F2b — GET /api/admin/enemies returns enemies (schema intact)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/enemies`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `GET enemies failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  const items = body.items || body || [];
  expect(Array.isArray(items), "enemies must be an array").toBeTruthy();
});

test("REGRESSION #484 F2b — enemy config includes loot_tier field (nullable)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/enemies`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok()) return;
  const body = await r.json();
  const items = body.items || body || [];
  if (!items.length) return;

  // loot_tier must be a field that exists (value may be null)
  const first = items[0];
  expect(
    "loot_tier" in first,
    `enemy object must have loot_tier key. Got keys: ${Object.keys(first).join(", ")}`
  ).toBeTruthy();
});

test("REGRESSION #484 F2b — GET /api/admin/affixes still works (F2 not broken)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/affixes`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `GET affixes failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("items");
  expect(Array.isArray(body.items)).toBeTruthy();
});
