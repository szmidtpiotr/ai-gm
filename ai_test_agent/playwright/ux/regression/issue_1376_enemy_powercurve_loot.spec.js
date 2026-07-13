/**
 * REGRESSION #1376 (BL) — spójny power-curve wrogów + loot (follow-up #1346).
 * Weryfikuje przez katalog admina, licząc threat mirror silnika:
 *   1) brak inwersji elite/standard: min(threat elit) > max(threat standardów).
 *   2) brak inwersji boss/elite: min(threat bossów) > max(threat elit).
 *   3) loot_tier nie zaśmiecony (poor/rich/treasure) — ∈ {NULL, weak/standard/elite/boss}.
 * Acceptance: drabina tierów monotoniczna (feeduje rangi #1332 + budżet #1331);
 * "elita" zawsze silniejsza od "zwykłego" na styku poziomów.
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

// mirror encounter_service.enemy_threat_value: hp*1 + dpr*2 + atk*1 + armor*0.5
function avgDie(die) {
  const m = String(die || "").match(/^(\d*)d(\d+)$/i);
  if (!m) return 0;
  const n = m[1] ? parseInt(m[1], 10) : 1;
  const f = parseInt(m[2], 10);
  return n * (f + 1) / 2;
}
function threat(e) {
  const hp = e.hp_base || 1;
  const apt = Math.max(1, e.attacks_per_turn || 1);
  const dpr = (avgDie(e.damage_die) + (e.damage_bonus || 0)) * apt;
  const armor = Math.max(0, (e.ac_base || 10) - 10);
  return hp * 1.0 + dpr * 2.0 + (e.attack_bonus || 0) * 1.0 + armor * 0.5;
}

const VALID_LOOT_TIER = new Set(["", "weak", "standard", "elite", "boss"]);

test("REGRESSION #1376 — tier power-curve monotoniczny, loot_tier czysty", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };

  const resp = await page.request.get("/api/admin/enemies", { headers: auth });
  expect(resp.ok(), "/api/admin/enemies nie odpowiada 200 (#1376)").toBeTruthy();
  const items = (await resp.json()).items || [];
  const pool = items.filter(
    (e) => e.world_scope === "global" && e.is_active && (e.review_status || "permanent") === "permanent",
  );

  const byTier = { standard: [], elite: [], boss: [] };
  for (const e of pool) if (byTier[e.tier]) byTier[e.tier].push({ key: e.key, t: threat(e) });

  const maxT = (a) => a.reduce((m, x) => (x.t > m.t ? x : m));
  const minT = (a) => a.reduce((m, x) => (x.t < m.t ? x : m));

  // 1) elite > standard
  const maxStd = maxT(byTier.standard);
  const minElite = minT(byTier.elite);
  expect(
    minElite.t,
    `INWERSJA elite/standard: ${minElite.key}=${minElite.t} <= ${maxStd.key}=${maxStd.t}`,
  ).toBeGreaterThan(maxStd.t);

  // 2) boss > elite
  const maxElite = maxT(byTier.elite);
  const minBoss = minT(byTier.boss);
  expect(
    minBoss.t,
    `INWERSJA boss/elite: ${minBoss.key}=${minBoss.t} <= ${maxElite.key}=${maxElite.t}`,
  ).toBeGreaterThan(maxElite.t);

  // 3) loot_tier czysty
  const polluted = pool
    .filter((e) => e.loot_tier != null && !VALID_LOOT_TIER.has(String(e.loot_tier).trim().toLowerCase()))
    .map((e) => `${e.key}:${e.loot_tier}`);
  expect(polluted, `loot_tier zaśmiecony: ${polluted.slice(0, 8)}`).toEqual([]);
});
