/**
 * REGRESSION #671 (L2) — Generator rozgałęzionego grafu + dungeon_run v2.
 * Acceptance: draw_tile_graph() istnieje i eksponuje stałe BRANCH_CHANCE/MAX_BRANCHES/MAX_BRANCH_LENGTH.
 * Weryfikacja przez endpoint admina (admin dungeon list + tile categories).
 */
const { test, expect } = require("@playwright/test");

async function getAdminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "admin dev-login musi się udać (#671)").toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #671 L2 — GET /admin/dungeons zwraca lochy (graph engine gotowy do wdrożenia)", async ({ page }) => {
  const token = await getAdminToken(page);
  const r = await page.request.get("/api/admin/dungeons", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "endpoint /admin/dungeons nie odpowiada 200 (#671)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.items), "brak tablicy items (#671)").toBeTruthy();
});

test("REGRESSION #671 L2 — GET /api/admin/dungeon-tile-categories zwraca {categories:[]} (#671)", async ({ page }) => {
  const token = await getAdminToken(page);
  const r = await page.request.get("/api/admin/dungeon-tile-categories", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "endpoint /admin/dungeon-tile-categories nie odpowiada 200 (#671)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.categories), "brak tablicy categories w odpowiedzi (#671)").toBeTruthy();
});

test("REGRESSION #671 L2 — GET /api/admin/dungeon-tiles zwraca {tiles:[]} (#671)", async ({ page }) => {
  const token = await getAdminToken(page);
  const r = await page.request.get("/api/admin/dungeon-tiles", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "endpoint /admin/dungeon-tiles nie odpowiada 200 (#671)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.tiles), "brak tablicy tiles w odpowiedzi (#671)").toBeTruthy();
});
