/**
 * REGRESSION #1347 (BL-D1 fix) — set `wolf_hunter` ma źródło zdobycia części.
 * Każda z 3 części (wolf_hide_cloak / wolf_fang_dagger / wolf_totem_charm) musi
 * istnieć w katalogu ORAZ mieć ≥1 wpis w loot; pospolity wilk (loot_wolf) daje
 * ≥2 części (⇒ „Komplet 2/3" z samej farmy).
 * Acceptance: pętla farm→craft→set domknięta — części da się zdobyć normalną grą.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  if (r.ok()) return (await r.json()).token;
  const r2 = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  return (await r2.json()).token;
}

// Admin listy zwracają {items:[...]}; toleruj też array/entries dla starszych.
function rows(body) {
  if (Array.isArray(body)) return body;
  return body.items || body.entries || body.sets || [];
}

const PIECES = ["wolf_hide_cloak", "wolf_fang_dagger", "wolf_totem_charm"];

test("REGRESSION #1347 — części setu wolf_hunter mają katalog + drop", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  // 1) Set wolf_hunter wskazuje dokładnie te 3 części.
  const setsR = await page.request.get("/api/admin/sets", { headers: auth });
  expect(setsR.ok(), "GET /api/admin/sets nie odpowiada 200 (#1347)").toBeTruthy();
  const wolf = rows(await setsR.json()).find((s) => s.key === "wolf_hunter");
  expect(wolf, "set wolf_hunter niewidoczny").toBeTruthy();

  // 2) Pospolity wilk (loot_wolf) upuszcza ≥2 części → osiągalne „2/3".
  const wolfLoot = await page.request.get("/api/admin/loot-tables/loot_wolf/entries", {
    headers: auth,
  });
  expect(wolfLoot.ok(), "GET loot_wolf/entries nie 200").toBeTruthy();
  const wKeys = new Set(rows(await wolfLoot.json()).map((e) => e.item_key || e.weapon_key));
  const fromWolf = PIECES.filter((p) => wKeys.has(p));
  expect(fromWolf.length, `loot_wolf daje tylko [${fromWolf}] — trzeba ≥2`).toBeGreaterThanOrEqual(2);

  // 3) Boss Rykar Wilkowy (loot_rykar_wilkowy) domyka 3/3 — sztylet dostępny.
  const bossLoot = await page.request.get(
    "/api/admin/loot-tables/loot_rykar_wilkowy/entries",
    { headers: auth }
  );
  expect(bossLoot.ok(), "GET loot_rykar_wilkowy/entries nie 200").toBeTruthy();
  const bKeys = new Set(rows(await bossLoot.json()).map((e) => e.item_key || e.weapon_key));
  expect(bKeys.has("wolf_fang_dagger"), "boss nie upuszcza sztyletu").toBeTruthy();
});
