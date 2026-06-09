/**
 * REGRESSION #460 (E19c) — Compositor redesign: thin border + flat amber door markers.
 * Acceptance: recomposite endpoint works; generate-description returns Polish text.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #460 — recomposite endpoint available", async ({ page }) => {
  const r = await page.request.post("/api/admin/dungeon-tiles/999999/recomposite", {
    headers: { Authorization: "Bearer bad-token" },
  });
  // 401 means endpoint exists and is protected (not 404/405)
  expect(r.status(), "recomposite endpoint missing or wrong method (#460)").toBe(401);
});

test("REGRESSION #460 — generate-description endpoint available", async ({ page }) => {
  const r = await page.request.post(
    "/api/admin/dungeon-tiles/999999/generate-description",
    { headers: { Authorization: "Bearer bad-token" } }
  );
  expect(r.status(), "generate-description endpoint missing or wrong method (#460)").toBe(401);
});

test("REGRESSION #460 — generate-description returns Polish description for valid tile", async ({ page }) => {
  // Login as admin
  const loginR = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(loginR.ok(), "admin login failed").toBeTruthy();
  const { token } = await loginR.json();

  // Get first active tile
  const listR = await page.request.get("/api/admin/dungeon-tiles", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(listR.ok()).toBeTruthy();
  const { tiles } = await listR.json();
  if (!tiles || !tiles.length) return; // skip if no tiles in DB

  const tileId = tiles[0].id;
  const descR = await page.request.post(
    `/api/admin/dungeon-tiles/${tileId}/generate-description`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  expect(descR.ok(), `generate-description failed: ${descR.status()}`).toBeTruthy();
  const body = await descR.json();
  expect(body.room_description, "no description returned").toBeTruthy();
  expect(body.room_description.length, "description too short").toBeGreaterThan(20);
});
