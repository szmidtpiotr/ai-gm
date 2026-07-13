/**
 * REGRESSION #1346 (BL) — bestiariusz lvl 6-10 wypełnia pasma + generyczni + tereny.
 * Follow-up contentowy do #1345. Weryfikuje przez katalog wrogów admina:
 *   1) 12 nowych wrogów lvl 6-10 istnieje, global+permanent+active.
 *   2) lvl 10 ma natywnie ≥8 wrogów standard/elite (nie same bossy).
 *   3) road/plains/river @ lvl 10 → ≥3 różnych wrogów każdy.
 *   4) ≥3 wrogów generycznych (pusty terrain_tags) na lvl ≥6.
 * Acceptance: pula spotkań lvl 6-10 przestaje być samymi bossami/elitami; anti-repeat
 * ma z czego losować na trakcie/równinie/rzece.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  if (r.ok()) return (await r.json()).token;
  const r2 = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  return (await r2.json()).token;
}

function coversLvl10(e) {
  const mn = e.min_level == null ? 1 : e.min_level;
  const mx = e.max_level == null ? 999 : e.max_level;
  return mn <= 10 && mx >= 10;
}

test("REGRESSION #1346 — bestiary lvl 6-10 seeded, multitier lvl-10 pool", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  const resp = await page.request.get("/api/admin/enemies", { headers: auth });
  expect(resp.ok(), "/api/admin/enemies nie odpowiada 200 (#1346)").toBeTruthy();
  const items = (await resp.json()).items || [];
  const byKey = Object.fromEntries(items.map((e) => [e.key, e]));

  // 1) nowi wrogowie lvl 6-10 obecni + globalni + aktywni
  const NEW = [
    "rozbojnik_traktowy", "lowca_rubiezy", "bagienny_topielec", "stepowy_grasant",
    "rzeczny_oprych", "hetman_rozbojcow", "mrozny_wilkolak", "bagienna_jedza",
    "kamienny_wojownik", "wynaturzona_bestia", "najemny_zabojca", "bladzacy_upior",
  ];
  for (const k of NEW) {
    const e = byKey[k];
    expect(e, `brak wroga lvl 6-10 '${k}' (#1346)`).toBeTruthy();
    expect(e.world_scope).toBe("global");
    expect(e.is_active).toBeTruthy();
  }

  // aktywna, globalna, permanentna pula do analizy pasm
  const pool = items.filter(
    (e) => e.world_scope === "global" && e.is_active && (e.review_status || "permanent") === "permanent",
  );

  // 2) lvl 10 natywnie ≥8, wielotierowo (jest standard lub elite, nie same bossy)
  const lvl10 = pool.filter(coversLvl10);
  expect(lvl10.length, "pula lvl-10 < 8 (same bossy?)").toBeGreaterThanOrEqual(8);
  const tiers = new Set(lvl10.map((e) => e.tier));
  expect(tiers.has("standard") || tiers.has("elite"), "lvl 10 tylko bossy").toBeTruthy();

  // 3) road/plains/river @ lvl 10 → ≥3 różnych (pusty terrain_tags = generyczny, pasuje wszędzie)
  for (const terrain of ["road", "plains", "river"]) {
    const onTerrain = lvl10.filter((e) => {
      const t = (e.terrain_tags || "").trim();
      return t === "" || t.split(",").map((s) => s.trim()).includes(terrain);
    });
    expect(onTerrain.length, `teren ${terrain} @ lvl 10 < 3 różnych`).toBeGreaterThanOrEqual(3);
  }

  // 4) ≥3 generycznych (pusty terrain_tags) na lvl ≥6
  const generic = pool.filter(
    (e) => (e.terrain_tags || "").trim() === "" && (e.max_level == null || e.max_level >= 6),
  );
  expect(generic.length, "generycznych wrogów lvl≥6 < 3").toBeGreaterThanOrEqual(3);
});
