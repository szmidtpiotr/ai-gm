/**
 * REGRESSION #462 (F2) — Affix System: game_config_affixes katalog z typed Effect Objects.
 * Afiks broni niesie {"type":"damage_bonus","value":N} (schema F1); silnik walki sumuje
 * damage_bonus z afiksów założonej broni (pokryte testem pytest).
 * Acceptance: endpoint /api/admin/affixes zwraca katalog afiksów, każdy z poprawnym
 * effect_json (gear_bonus / damage_bonus) — dane, z których resolve_attack czyta bonus.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin dev-login failed: ${r.status()}`).toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #462 — affix catalog exposes typed damage_bonus Effect Objects", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const r = await request.get(`${BASE}/api/admin/affixes`, { headers });
  expect(r.ok(), `GET /admin/affixes failed: ${r.status()} (#462)`).toBeTruthy();

  const items = (await r.json()).items;
  expect(Array.isArray(items), "/admin/affixes.items musi być tablicą (#462)").toBeTruthy();

  // Starter affixes seedowane migracją — 'sharp' musi istnieć.
  const sharp = items.find((a) => a.key === "sharp");
  expect(sharp, "starter affix 'sharp' nieobecny w katalogu (#462)").toBeTruthy();
  expect(sharp.tier, "affix musi mieć tier (#462)").toBeGreaterThanOrEqual(1);
  expect(sharp.allowed_item_types, "affix musi mieć allowed_item_types (#462)").toBeTruthy();

  // effect_json niesie typowany damage_bonus — to konsumuje resolve_attack.
  const parsed = typeof sharp.effect_json === "string" ? JSON.parse(sharp.effect_json) : sharp.effect_json;
  expect(parsed.effect_category, "affix effect_category != gear_bonus (#462)").toBe("gear_bonus");
  const dmg = (parsed.effects || []).find((e) => e.type === "damage_bonus");
  expect(dmg, "affix 'sharp' nie ma typowanego damage_bonus (#462)").toBeTruthy();
  expect(Number(dmg.value), "damage_bonus.value musi być > 0 (#462)").toBeGreaterThan(0);
});
