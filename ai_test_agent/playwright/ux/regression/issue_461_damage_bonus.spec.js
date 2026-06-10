/**
 * REGRESSION #461 (F1) — Unified Effects System: typed damage_bonus Effect Object.
 * Broń może nieść typowany efekt {"type":"damage_bonus","value":N} w effect_json;
 * silnik walki dodaje ten bonus do obrażeń (pokryte testem pytest).
 * Acceptance: admin tworzy broń z gear_bonus / damage_bonus effect_json, rekord
 * zapisuje się (200) i odczyt z katalogu /api/admin/weapons zwraca ten sam typowany
 * efekt — to dane, z których resolve_attack czyta flat damage_bonus.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
const WEAPON_KEY = "rgr461_bonus_blade";

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin dev-login failed: ${r.status()}`).toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #461 — weapon damage_bonus Effect Object round-trips through admin catalog", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  // Cleanup any leftover from a prior run (ignore 404).
  await request.delete(`${BASE}/api/admin/weapons/${WEAPON_KEY}`, { headers });

  const effectJson = JSON.stringify({
    schema_version: 1,
    effect_category: "gear_bonus",
    effects: [{ type: "damage_bonus", value: 5 }],
  });

  // 1) Create a weapon carrying a typed damage_bonus effect.
  const create = await request.post(`${BASE}/api/admin/weapons`, {
    headers,
    data: {
      key: WEAPON_KEY,
      label: "Ostrze Mocy (#461)",
      damage_die: "1d8",
      linked_stat: "STR",
      allowed_classes: ["warrior"],
      weapon_type: "melee",
      effect_json: effectJson,
    },
  });
  expect(create.ok(), `POST /admin/weapons failed: ${create.status()} (#461)`).toBeTruthy();

  // 2) Read it back from the catalog — effect_json must survive intact.
  const list = await request.get(`${BASE}/api/admin/weapons`, { headers });
  expect(list.ok(), `GET /admin/weapons failed: ${list.status()} (#461)`).toBeTruthy();
  const items = (await list.json()).items || [];
  const row = items.find((w) => w.key === WEAPON_KEY);
  expect(row, "utworzona broń nieobecna w katalogu (#461)").toBeTruthy();
  expect(row.effect_json, "broń nie ma effect_json po odczycie (#461)").toBeTruthy();

  const parsed = typeof row.effect_json === "string" ? JSON.parse(row.effect_json) : row.effect_json;
  const dmgEffect = (parsed.effects || []).find((e) => e.type === "damage_bonus");
  expect(dmgEffect, "effect_json nie zawiera typowanego damage_bonus (#461)").toBeTruthy();
  expect(Number(dmgEffect.value), "damage_bonus.value != 5 (#461)").toBe(5);

  // 3) Cleanup.
  await request.delete(`${BASE}/api/admin/weapons/${WEAPON_KEY}`, { headers });
});
