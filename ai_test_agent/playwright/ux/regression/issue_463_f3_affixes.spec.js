/**
 * REGRESSION #463 (F3) — Admin Affix Builder: POST/PATCH/DELETE /api/admin/affixes.
 * Acceptance: admin can create, update, delete affixes via API; Afiksy tab visible in Zawartość.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
const TEST_KEY = "pw463_test_affix";

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin login failed: ${r.status()}`).toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #463 F3 — POST /api/admin/affixes creates new affix", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  // Cleanup leftovers
  await request.delete(`${BASE}/api/admin/affixes/${TEST_KEY}`, { headers });

  const create = await request.post(`${BASE}/api/admin/affixes`, {
    headers,
    data: {
      key: TEST_KEY,
      name: "Playwright Test Affix",
      tier: 2,
      allowed_item_types: "weapon",
      effect_json: JSON.stringify({
        schema_version: 1,
        effect_category: "gear_bonus",
        effects: [{ type: "damage_bonus", value: 3 }],
      }),
      is_active: true,
    },
  });
  expect(create.ok(), `POST /admin/affixes failed: ${create.status()} — ${await create.text()}`).toBeTruthy();
  const body = await create.json();
  expect(body.item?.key, "created item must have key").toBe(TEST_KEY);

  // Verify in list
  const list = await request.get(`${BASE}/api/admin/affixes`, { headers });
  expect(list.ok(), `GET /admin/affixes failed: ${list.status()}`).toBeTruthy();
  const items = (await list.json()).items || [];
  const found = items.find((a) => a.key === TEST_KEY);
  expect(found, `${TEST_KEY} not in affix list after create`).toBeTruthy();
  expect(found?.tier, "tier should be 2").toBe(2);

  await request.delete(`${BASE}/api/admin/affixes/${TEST_KEY}`, { headers });
});

test("REGRESSION #463 F3 — PATCH /api/admin/affixes/:key updates affix name", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  await request.delete(`${BASE}/api/admin/affixes/${TEST_KEY}`, { headers });
  await request.post(`${BASE}/api/admin/affixes`, {
    headers,
    data: { key: TEST_KEY, name: "Original", tier: 1, allowed_item_types: "weapon" },
  });

  const patch = await request.patch(`${BASE}/api/admin/affixes/${TEST_KEY}`, {
    headers,
    data: { name: "Updated by Playwright" },
  });
  expect(patch.ok(), `PATCH failed: ${patch.status()} — ${await patch.text()}`).toBeTruthy();
  const body = await patch.json();
  expect(body.item?.name, "name should be updated").toBe("Updated by Playwright");

  await request.delete(`${BASE}/api/admin/affixes/${TEST_KEY}`, { headers });
});

test("REGRESSION #463 F3 — DELETE /api/admin/affixes/:key removes affix", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  await request.post(`${BASE}/api/admin/affixes`, {
    headers,
    data: { key: TEST_KEY, name: "To Delete", tier: 1, allowed_item_types: "weapon" },
  });

  const del = await request.delete(`${BASE}/api/admin/affixes/${TEST_KEY}`, { headers });
  expect(del.ok(), `DELETE failed: ${del.status()} — ${await del.text()}`).toBeTruthy();

  // Verify gone
  const list = await request.get(`${BASE}/api/admin/affixes`, { headers });
  const items = (await list.json()).items || [];
  const found = items.find((a) => a.key === TEST_KEY);
  expect(found, "affix should be absent after delete").toBeFalsy();
});

test("REGRESSION #463 F3 — GET /api/admin/affixes returns items list", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/affixes`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `GET /admin/affixes failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body, "response must have items key").toHaveProperty("items");
  expect(Array.isArray(body.items), "items must be array").toBeTruthy();
});
