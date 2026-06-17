/**
 * REGRESSION #692 (L20a) — Persystencja portretów wrogów i NPC.
 * Acceptance: PATCH /api/admin/enemies/{key} z image_url zwraca image_url w odpowiedzi;
 * GET /api/admin/enemies zwraca image_url w każdym rekordzie; PATCH /api/admin/npcs/{id} zapisuje image_url.
 */
const { test, expect } = require("@playwright/test");

const ADMIN_CREDS = { username: "demo", password: "demo" };

async function getAdminToken(request) {
  const r = await request.post("/api/admin/dev-login", { data: ADMIN_CREDS });
  expect(r.ok()).toBeTruthy();
  const { token } = await r.json();
  return token;
}

test("REGRESSION #692 (L20a) — enemies list contains image_url field", async ({ request }) => {
  const token = await getAdminToken(request);
  const r = await request.get("/api/admin/enemies", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/enemies failed").toBeTruthy();
  const body = await r.json();
  const items = body.items ?? [];
  expect(items.length, "No enemies found").toBeGreaterThan(0);
  expect(
    "image_url" in items[0],
    `image_url missing from enemy record. Keys: ${Object.keys(items[0]).join(", ")}`
  ).toBeTruthy();
});

test("REGRESSION #692 (L20a) — PATCH enemy image_url persists", async ({ request }) => {
  const token = await getAdminToken(request);

  // find first active enemy key
  const listR = await request.get("/api/admin/enemies", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const { items } = await listR.json();
  const enemy = items.find((e) => e.is_active);
  expect(enemy, "No active enemy found").toBeTruthy();
  const key = enemy.key;

  const testUrl = `/static/portraits/test_${key}.png`;

  // PATCH image_url
  const patchR = await request.patch(`/api/admin/enemies/${key}`, {
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    data: { image_url: testUrl },
  });
  expect(patchR.ok(), `PATCH enemy failed: ${await patchR.text()}`).toBeTruthy();
  const { item } = await patchR.json();
  expect(item.image_url, "image_url not returned in PATCH response").toBe(testUrl);

  // cleanup
  await request.patch(`/api/admin/enemies/${key}`, {
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    data: { image_url: enemy.image_url ?? null },
  });
});

test("REGRESSION #692 (L20a) — PATCH NPC image_url persists", async ({ request }) => {
  const token = await getAdminToken(request);

  // find first NPC
  const listR = await request.get("/api/admin/npcs", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(listR.ok()).toBeTruthy();
  const body = await listR.json();
  const npcs = body.items ?? body.data ?? [];
  if (npcs.length === 0) {
    test.skip();
    return;
  }
  const npc = npcs[0];
  const npcId = npc.id;
  const testUrl = `/static/portraits/test_npc_${npcId}.png`;
  const originalUrl = npc.image_url ?? null;

  const patchR = await request.patch(`/api/admin/npcs/${npcId}`, {
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    data: { image_url: testUrl },
  });
  expect(patchR.ok(), `PATCH NPC failed: ${await patchR.text()}`).toBeTruthy();

  // verify via GET
  const getR = await request.get(`/api/admin/npcs/${npcId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(getR.ok()).toBeTruthy();
  const getBody = await getR.json();
  const fetchedNpc = getBody.data ?? getBody;
  expect(fetchedNpc.image_url, "NPC image_url not persisted").toBe(testUrl);

  // cleanup
  await request.patch(`/api/admin/npcs/${npcId}`, {
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    data: { image_url: originalUrl },
  });
});
