/**
 * REGRESSION #1023 (BALANS) — Enemy level gate: narrator cannot see elite/boss enemies
 * for low-level heroes in [AVAILABLE CONTENT] block.
 * Acceptance: game_config_enemies has min_level; elite ≥ 6, boss ≥ 10.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  if (!r.ok()) return null;
  const body = await r.json();
  return body.token || body.access_token || null;
}

test("REGRESSION #1023 — game_config_enemies has min_level field", async ({ page }) => {
  const token = await adminToken(page);
  expect(token, "admin login must succeed (#1023)").toBeTruthy();

  const r = await page.request.get("/api/admin/enemies", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "enemies endpoint must return 200 (#1023)").toBeTruthy();

  const body = await r.json();
  const enemies = body.items || body;
  expect(Array.isArray(enemies), "must return array of enemies").toBeTruthy();
  expect(enemies.length, "must have at least one enemy").toBeGreaterThan(0);

  const first = enemies[0];
  expect(
    "min_level" in first,
    `min_level missing on enemy object: ${JSON.stringify(Object.keys(first))}`
  ).toBeTruthy();
});

test("REGRESSION #1023 — elite enemies have min_level >= 6", async ({ page }) => {
  const token = await adminToken(page);
  expect(token, "admin login must succeed (#1023)").toBeTruthy();

  const r = await page.request.get("/api/admin/enemies", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();

  const body = await r.json();
  const enemies = body.items || body;
  const elites = enemies.filter((e) => e.tier === "elite");
  expect(elites.length, "must have at least one elite enemy").toBeGreaterThan(0);

  for (const e of elites) {
    expect(
      (e.min_level ?? 0) >= 6,
      `Elite enemy ${e.key} has min_level=${e.min_level} (expected >= 6)`
    ).toBeTruthy();
  }
});

test("REGRESSION #1023 — boss enemies have min_level >= 10", async ({ page }) => {
  const token = await adminToken(page);
  expect(token, "admin login must succeed (#1023)").toBeTruthy();

  const r = await page.request.get("/api/admin/enemies", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();

  const body = await r.json();
  const enemies = body.items || body;
  const bosses = enemies.filter((e) => e.tier === "boss");
  expect(bosses.length, "must have at least one boss enemy").toBeGreaterThan(0);

  for (const e of bosses) {
    expect(
      (e.min_level ?? 0) >= 10,
      `Boss enemy ${e.key} has min_level=${e.min_level} (expected >= 10)`
    ).toBeTruthy();
  }
});
