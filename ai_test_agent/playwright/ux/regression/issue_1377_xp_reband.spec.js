/**
 * REGRESSION #1377 (BL) — normalizacja XP + reband vampire_master (residua #1376).
 * Weryfikuje przez katalog admina, licząc threat mirror silnika:
 *   1) xp_award monotoniczny per tier: sortując po threat, xp nie maleje
 *      (łapie goblin xp=3 i niemonotoniczne bossy demon_lord 1800 > dragon 1500).
 *   2) vampire_master rebandowany na L8-10 (sufit elit, nie lvl 6-7).
 * (cap budżetu herszt = logika composer, pokryta pytestem.)
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

function avgDie(die) {
  const m = String(die || "").match(/^(\d*)d(\d+)$/i);
  if (!m) return 0;
  const n = m[1] ? parseInt(m[1], 10) : 1;
  return n * (parseInt(m[2], 10) + 1) / 2;
}
function threat(e) {
  const apt = Math.max(1, e.attacks_per_turn || 1);
  const dpr = (avgDie(e.damage_die) + (e.damage_bonus || 0)) * apt;
  const armor = Math.max(0, (e.ac_base || 10) - 10);
  return (e.hp_base || 1) + dpr * 2 + (e.attack_bonus || 0) + armor * 0.5;
}

test("REGRESSION #1377 — XP monotoniczny per tier + vampire_master L8-10", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };
  const resp = await page.request.get("/api/admin/enemies", { headers: auth });
  expect(resp.ok(), "/api/admin/enemies nie 200 (#1377)").toBeTruthy();
  const items = (await resp.json()).items || [];
  const pool = items.filter(
    (e) => e.world_scope === "global" && e.is_active && (e.review_status || "permanent") === "permanent",
  );

  // 1) XP monotoniczny per tier
  for (const tier of ["weak", "standard", "elite", "boss"]) {
    const seq = pool.filter((e) => e.tier === tier)
      .map((e) => ({ key: e.key, t: threat(e), xp: e.xp_award }))
      .sort((a, b) => a.t - b.t);
    let prev = { xp: -1, key: null };
    for (const e of seq) {
      expect(
        e.xp,
        `XP niemonotoniczny w ${tier}: ${e.key} t=${e.t.toFixed(1)} xp=${e.xp} < ${prev.key} xp=${prev.xp}`,
      ).toBeGreaterThanOrEqual(prev.xp);
      prev = e;
    }
  }

  // 2) vampire_master reband L8-10
  const vm = pool.find((e) => e.key === "vampire_master");
  expect(vm, "brak vampire_master").toBeTruthy();
  expect(vm.min_level, "vampire_master min_level != 8").toBe(8);
  expect(vm.max_level, "vampire_master max_level != 10").toBe(10);
});
