/**
 * REGRESSION #850 (Admin dice configurator) — verifies GET/POST /api/admin/dice-config
 * and public /api/game/dice-config endpoints work correctly.
 * Acceptance: admin can read and write dice config; public endpoint returns config without auth.
 */
const { test, expect } = require("@playwright/test");

let adminToken = null;

async function getAdminToken(request) {
  if (adminToken) return adminToken;
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok()).toBeTruthy();
  adminToken = (await r.json()).token;
  return adminToken;
}

test("REGRESSION #850 — GET /api/admin/dice-config returns config with required fields", async ({ request }) => {
  const token = await getAdminToken(request);
  const r = await request.get("/api/admin/dice-config", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/dice-config should return 200").toBeTruthy();
  const body = await r.json();
  expect(body.config, "response must have config key").toBeTruthy();
  expect(body.config.customColorset, "config must have customColorset").toBeTruthy();
  expect(body.config.gravity_multiplier, "config must have gravity_multiplier").toBeDefined();
  expect(body.config.baseScale, "config must have baseScale").toBeDefined();
});

test("REGRESSION #850 — POST /api/admin/dice-config saves and reads back", async ({ request }) => {
  const token = await getAdminToken(request);
  const testConfig = {
    customColorset: {
      foreground: "#aabbcc",
      background: ["#112233"],
      outline: "#ffffff",
      texture: "stone",
      material: "glass",
    },
    gravity_multiplier: 350,
    strength: 1.2,
    baseScale: 90,
    light_intensity: 1.0,
  };
  const postR = await request.post("/api/admin/dice-config", {
    data: { config: testConfig },
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(postR.ok(), "POST /api/admin/dice-config should return 200").toBeTruthy();
  expect((await postR.json()).ok).toBe(true);

  const getR = await request.get("/api/admin/dice-config", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const saved = (await getR.json()).config;
  expect(saved.customColorset.foreground).toBe("#aabbcc");
  expect(saved.customColorset.texture).toBe("stone");
  expect(saved.gravity_multiplier).toBe(350);
});

test("REGRESSION #850 — GET /api/game/dice-config is public (no auth required)", async ({ request }) => {
  const r = await request.get("/api/game/dice-config");
  expect(r.ok(), "/api/game/dice-config must return 200 without auth").toBeTruthy();
  const body = await r.json();
  expect(body.config).toBeTruthy();
  expect(body.config.customColorset).toBeTruthy();
});

test("REGRESSION #850 — admin endpoints require auth", async ({ request }) => {
  const r = await request.get("/api/admin/dice-config");
  expect([401, 403]).toContain(r.status());
});
