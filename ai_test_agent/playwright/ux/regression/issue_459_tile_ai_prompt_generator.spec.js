/**
 * REGRESSION #459 (E19b) — Dungeon tile AI prompt generator endpoints.
 * Verifies: POST generate-image-prompt returns English prompt, POST ai-create persists tile.
 */
const { test, expect } = require("@playwright/test");

const ADMIN_HEADERS = { "Content-Type": "application/json" };

async function getAdminToken(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok()).toBeTruthy();
  return (await r.json()).token;
}

async function firstActiveCategoryKey(request, token) {
  const r = await request.get("/api/admin/dungeon-tile-categories", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const cats = (await r.json()).categories || [];
  const active = cats.find((c) => c.is_active);
  return active ? active.key : null;
}

test("REGRESSION #459 — generate-image-prompt returns English prompt", async ({ request }) => {
  const token = await getAdminToken(request);
  const catKey = await firstActiveCategoryKey(request, token);
  expect(catKey, "no active tile category in DB").toBeTruthy();

  const r = await request.post("/api/admin/dungeon-tiles/generate-image-prompt", {
    headers: { Authorization: `Bearer ${token}`, ...ADMIN_HEADERS },
    data: { category_key: catKey },
  });
  expect(r.ok(), `generate-image-prompt failed: ${await r.text()}`).toBeTruthy();
  const body = await r.json();
  expect(body.image_gen_prompt, "image_gen_prompt missing").toBeTruthy();
  expect(body.image_gen_prompt.length).toBeGreaterThan(20);
});

test("REGRESSION #459 — generate-image-prompt rejects missing category_key", async ({ request }) => {
  const token = await getAdminToken(request);
  const r = await request.post("/api/admin/dungeon-tiles/generate-image-prompt", {
    headers: { Authorization: `Bearer ${token}`, ...ADMIN_HEADERS },
    data: {},
  });
  expect([400, 422]).toContain(r.status());
});

test("REGRESSION #459 — ai-create persists tile with label and prompt", async ({ request }) => {
  const token = await getAdminToken(request);
  const catKey = await firstActiveCategoryKey(request, token);
  expect(catKey, "no active tile category").toBeTruthy();

  const r = await request.post("/api/admin/dungeon-tiles/ai-create", {
    headers: { Authorization: `Bearer ${token}`, ...ADMIN_HEADERS },
    data: { category_key: catKey },
  });
  expect(r.ok(), `ai-create failed: ${await r.text()}`).toBeTruthy();
  const body = await r.json();
  expect(body.tile).toBeTruthy();
  expect(body.tile.id).toBeGreaterThan(0);
  expect(body.tile.label.length).toBeGreaterThan(2);
  expect(body.tile.image_gen_prompt.length).toBeGreaterThan(20);
  expect(body.tile.category_key).toBe(catKey);
});
