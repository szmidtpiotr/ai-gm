/**
 * REGRESSION #623 (HI1) — Inspektor Bohatera: backend /full + luki zapisu + guard.
 * Czysty agregat GET /api/admin/characters/{id}/full (staty, skille, hp/mana, kondycje,
 * ekwipunek, zaklęcia, xp, questy + is_live_locked) oraz nowe luki zapisu w admin_cheat
 * (set skill / set mana / add+remove condition) z audytem. Pełna logika + guard live_locked
 * pokryte pytestem test_hi1_inspector_backend.py.
 * Acceptance (deterministyczny): admin (token) dostaje komplet pól z /full; bez tokenu → 401/403;
 * mutacja inspektora (set skill) zwraca ok=true.
 */
const { test, expect } = require("@playwright/test");

const REQUIRED_KEYS = [
  "id", "name", "gold_gp", "archetype", "level", "stats", "stat_modifiers",
  "skills", "hp", "max_hp", "mana", "max_mana", "conditions",
  "inventory", "spells", "xp", "quests_active", "quests_completed", "is_live_locked",
];

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200 (#623)").toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #623 — /full zwraca komplet pól dla admina", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };

  const list = await page.request.get("/api/admin/characters?owner_id=1", { headers });
  expect(list.ok(), "lista postaci Demo nie odpowiada 200 (#623)").toBeTruthy();
  const items = (await list.json()).items || [];
  expect(items.length, "brak bohaterów Demo do inspekcji (#623)").toBeGreaterThan(0);
  const cid = items[0].id;

  const full = await page.request.get(`/api/admin/characters/${cid}/full`, { headers });
  expect(full.ok(), "/full nie odpowiada 200 (#623)").toBeTruthy();
  const body = await full.json();
  for (const k of REQUIRED_KEYS) {
    expect(k in body, `/full bez pola ${k} (#623)`).toBeTruthy();
  }
  expect(typeof body.is_live_locked, "is_live_locked musi być bool (#623)").toBe("boolean");
});

test("REGRESSION #623 — /full wymaga tokenu admina", async ({ page }) => {
  const r = await page.request.get("/api/admin/characters/1/full");
  expect([401, 403].includes(r.status()), "/full bez tokenu musi dać 401/403 (#623)").toBeTruthy();
});

test("REGRESSION #623 — luka zapisu set skill działa (inspector)", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };

  const list = await page.request.get("/api/admin/characters?owner_id=1", { headers });
  const cid = ((await list.json()).items || [])[0].id;

  // odczyt obecnego ranku, by przywrócić po teście
  const before = await (await page.request.get(`/api/admin/characters/${cid}/full`, { headers })).json();
  const prev = (before.skills && before.skills.stealth) || 0;

  const set = await page.request.post(`/api/admin/cheat/${cid}`, {
    headers,
    data: { cmd: "set skill", key: "stealth", value: 1, inspector: true },
  });
  expect(set.ok(), "set skill nie zwrócił 200 (#623)").toBeTruthy();
  expect((await set.json()).result.rank, "set skill nie ustawił ranku (#623)").toBe(1);

  // revert
  await page.request.post(`/api/admin/cheat/${cid}`, {
    headers,
    data: { cmd: "set skill", key: "stealth", value: prev, inspector: true },
  });
});
