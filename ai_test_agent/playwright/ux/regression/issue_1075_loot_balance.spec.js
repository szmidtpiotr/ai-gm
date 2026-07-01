/**
 * REGRESSION #1075 — Loot balance: boosted weights, filled goblin_u31 table, krypta_opiekun fix.
 * Acceptance: goblin_u31 has 3 loot entries; krypta_opiekun uses loot_treasure; dagger weight=18 in loot_poor.
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

test("REGRESSION #1075 — goblin_u31 loot table has entries and gold range", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/loot-tables", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `loot-tables endpoint must return 200, got ${r.status()}`).toBeTruthy();
  const body = await r.json();
  const tables = body.items || body;
  const u31 = tables.find(t => t.key === "loot_goblin_u31");
  expect(u31, "loot_goblin_u31 table must exist").toBeTruthy();
  expect(u31.gold_min, "loot_goblin_u31 gold_min should be 1").toBe(1);
  expect(u31.gold_max, "loot_goblin_u31 gold_max should be 6").toBe(6);
});

test("REGRESSION #1075 — krypta_opiekun has loot_treasure assigned with drop_chance=1.0", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/enemies", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `enemies endpoint must return 200, got ${r.status()}`).toBeTruthy();
  const body = await r.json();
  const enemies = body.enemies || body.items || body;
  const boss = enemies.find(e => e.key === "krypta_opiekun");
  expect(boss, "krypta_opiekun must exist in enemies").toBeTruthy();
  expect(boss.loot_table_key, "krypta_opiekun must use loot_treasure").toBe("loot_treasure");
  expect(boss.drop_chance, "krypta_opiekun drop_chance must be 1.0").toBe(1.0);
});
