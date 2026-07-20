/**
 * REGRESSION #1482 (RM) — generator świata usunięty, masowe kasowanie mapy zablokowane.
 * Acceptance: POST /generate → 410; DELETE /clear na niepustej mapie → 403; pełny
 * restore bez ?region= → 403; generate-local (podmapy osad) i mapa świata działają.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "dev-login failed").toBeTruthy();
  return (await login.json()).token;
}

test("REGRESSION #1482 — POST /generate zwraca 410 (generator usunięty)", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.post("/api/admin/world/generate", {
    headers: { Authorization: `Bearer ${token}` },
    data: { seed: 1482, radius: 2 },
  });
  expect(r.status(), "generator świata musi być wyłączony (#1482)").toBe(410);
  const body = await r.json();
  expect(String(body.detail || ""), "410 musi tłumaczyć powód i wskazać ścieżkę per-kraina")
    .toContain("data/regions");
});

test("REGRESSION #1482 — DELETE /clear na niepustej mapie zwraca 403", async ({ page }) => {
  const token = await adminToken(page);
  const before = await page.request.get("/api/admin/world/map", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(before.ok(), "GET /map nie odpowiada").toBeTruthy();
  const hexCount = ((await before.json()).hexes || []).length;
  expect(hexCount, "test wymaga niepustej mapy świata").toBeGreaterThan(0);

  const r = await page.request.delete("/api/admin/world/clear", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status(), "masowe czyszczenie mapy musi być zablokowane (#1482)").toBe(403);

  const after = await page.request.get("/api/admin/world/map", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(((await after.json()).hexes || []).length, "mapa zmieniła rozmiar mimo guardu").toBe(hexCount);
});

test("REGRESSION #1482 — pełny restore bez ?region= zwraca 403 z podpowiedzią", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.post("/api/admin/world/map/restore", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status(), "pełny restore (wszystkie krainy) musi być zablokowany (#1482)").toBe(403);
  expect(String((await r.json()).detail || ""), "403 musi kierować na ?region=").toContain("region");
});

test("REGRESSION #1482 — mapa świata i podmapy osad nadal działają", async ({ page }) => {
  const token = await adminToken(page);
  const m = await page.request.get("/api/admin/world/map", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(m.ok(), "GET /map zepsuty").toBeTruthy();
  expect(((await m.json()).hexes || []).length, "mapa świata pusta").toBeGreaterThan(0);

  // generate-local żyje: nieistniejący hex-rodzic → 404 "Parent hex not found"
  // (a NIE 410 jak wyłączony generator świata). Nie ruszamy przy tym żadnej podmapy.
  const gl = await page.request.post("/api/admin/world/generate-local", {
    headers: { Authorization: `Bearer ${token}` },
    data: { parent_q: 99999, parent_r: 99999, radius: 1 },
  });
  expect(gl.status(), "generate-local nie może być wyłączony jak generator świata (#1482)").not.toBe(410);
  expect(String((await gl.json()).detail || ""), "generate-local (podmapy osad) musi zostać")
    .toContain("Parent hex not found");
});
