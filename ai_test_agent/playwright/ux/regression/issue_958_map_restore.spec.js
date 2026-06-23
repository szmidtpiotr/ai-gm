/**
 * REGRESSION #958 — Endpoint POST /api/admin/world/map/restore istnieje i zwraca poprawną odpowiedź.
 * Acceptance: endpoint odpowiada 200 z ok=true i count>0 przy poprawnym tokenie; 401 bez tokenu.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #958 — map/restore wymaga autoryzacji (401 bez tokenu)", async ({ page }) => {
  const r = await page.request.post("/api/admin/world/map/restore");
  expect(r.status(), "restore bez tokenu powinno zwrócić 401 (#958)").toBe(401);
});

test("REGRESSION #958 — map/snapshot nadal działa (backward compat)", async ({ page }) => {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "dev-login failed").toBeTruthy();
  const { token } = await login.json();

  const r = await page.request.post("/api/admin/world/map/snapshot", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "snapshot endpoint broken (#958)").toBeTruthy();
  const body = await r.json();
  expect(body.ok, "snapshot ok nie true").toBe(true);
  expect(body.count, "snapshot count = 0").toBeGreaterThan(0);
});

test("REGRESSION #958 — map/restore zwraca ok=true i count>0 z tokenem", async ({ page }) => {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "dev-login failed").toBeTruthy();
  const { token } = await login.json();

  const r = await page.request.post("/api/admin/world/map/restore", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status(), `restore failed: ${r.status()}`).toBe(200);
  const body = await r.json();
  expect(body.ok, "restore ok nie true (#958)").toBe(true);
  expect(body.count, "restore count = 0 (#958)").toBeGreaterThan(0);
});
