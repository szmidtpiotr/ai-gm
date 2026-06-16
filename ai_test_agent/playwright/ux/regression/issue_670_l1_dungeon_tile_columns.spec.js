/**
 * REGRESSION #670 (L1) — Konfiguracja kafelkowa lochu w DB + admin.
 * Acceptance: PATCH /api/admin/dungeons/{key} zapisuje tile_category_key, tile_count,
 * boss_tile_id i endless_growth_n; GET zwraca je z powrotem.
 */
const { test, expect } = require("@playwright/test");

async function getAdminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "admin dev-login musi się udać (#670)").toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #670 L1 — GET /admin/dungeons zwraca kolumny kafelkowe", async ({ page }) => {
  const token = await getAdminToken(page);
  const r = await page.request.get("/api/admin/dungeons", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "endpoint /admin/dungeons nie odpowiada 200 (#670)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.items), "brak tablicy items").toBeTruthy();

  if (body.items.length > 0) {
    const d = body.items[0];
    expect("tile_category_key" in d, "brak klucza tile_category_key w odpowiedzi (#670)").toBeTruthy();
    expect("tile_count" in d, "brak klucza tile_count (#670)").toBeTruthy();
    expect("endless_growth_n" in d, "brak klucza endless_growth_n (#670)").toBeTruthy();
  }
});

test("REGRESSION #670 L1 — PATCH dungeons zapisuje endless_growth_n i tile_count", async ({ page }) => {
  const token = await getAdminToken(page);
  const authHeader = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const listR = await page.request.get("/api/admin/dungeons", { headers: authHeader });
  const body = await listR.json();
  const dungeon = body.items?.find(d => d.is_active) || body.items?.[0];
  if (!dungeon) { test.skip("Brak lochów w bazie"); return; }

  const key = dungeon.key;
  const patchR = await page.request.patch(`/api/admin/dungeons/${key}`, {
    headers: authHeader,
    data: { endless_growth_n: 3, tile_count: 5 },
  });
  expect(patchR.ok(), `PATCH dungeons/${key} nie 200 (#670)`).toBeTruthy();

  const getR = await page.request.get("/api/admin/dungeons", { headers: authHeader });
  const updated = (await getR.json()).items?.find(d => d.key === key);
  expect(updated?.endless_growth_n, "endless_growth_n nie zapisano (#670)").toBe(3);
  expect(updated?.tile_count, "tile_count nie zapisano (#670)").toBe(5);

  // Przywróć
  await page.request.patch(`/api/admin/dungeons/${key}`, {
    headers: authHeader,
    data: { endless_growth_n: dungeon.endless_growth_n ?? 0, tile_count: dungeon.tile_count ?? 6 },
  });
});
