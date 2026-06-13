/**
 * REGRESSION #554 (U10) — Effect schema lockdown (decyzja C: hybryda).
 * Acceptance: walidator effect_json przyjmuje LCK + cele pochodne (ac/attack_bonus/
 *             damage_bonus/initiative) jako stat dla static_stat_modifier, a odrzuca
 *             losowy stat — przez prawdziwą ścieżkę zapisu admina (POST /admin/affixes).
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

function effect(stat) {
  return JSON.stringify({
    schema_version: 1,
    effect_category: "gear_bonus",
    effects: [{ type: "static_stat_modifier", stat, value: 1 }],
  });
}

test("REGRESSION #554 (U10) — affix z stat=LCK jest przyjmowany", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  const key = "u10_lck_probe";

  // sprzątanie na wszelki wypadek
  await request.delete(`${BASE}/api/admin/affixes/${key}`, { headers });

  const r = await request.post(`${BASE}/api/admin/affixes`, {
    headers,
    data: { key, name: "U10 LCK probe", tier: 1, allowed_item_types: "weapon", effect_json: effect("LCK") },
  });
  expect(r.ok(), `LCK powinno przejść walidację, status: ${r.status()}`).toBeTruthy();

  // sprzątanie
  await request.delete(`${BASE}/api/admin/affixes/${key}`, { headers });
});

test("REGRESSION #554 (U10) — affix z celem pochodnym stat=ac jest przyjmowany", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  const key = "u10_ac_probe";

  await request.delete(`${BASE}/api/admin/affixes/${key}`, { headers });
  const r = await request.post(`${BASE}/api/admin/affixes`, {
    headers,
    data: { key, name: "U10 ac probe", tier: 1, allowed_item_types: "weapon", effect_json: effect("ac") },
  });
  expect(r.ok(), `stat=ac powinno przejść, status: ${r.status()}`).toBeTruthy();
  await request.delete(`${BASE}/api/admin/affixes/${key}`, { headers });
});

test("REGRESSION #554 (U10) — affix z losowym stat=FOO jest odrzucany (lockdown trzyma)", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  const key = "u10_foo_probe";

  await request.delete(`${BASE}/api/admin/affixes/${key}`, { headers });
  const r = await request.post(`${BASE}/api/admin/affixes`, {
    headers,
    data: { key, name: "U10 foo probe", tier: 1, allowed_item_types: "weapon", effect_json: effect("FOO") },
  });
  expect(r.ok(), `losowy stat FOO NIE powinien przejść (status ${r.status()})`).toBeFalsy();
  // gdyby jednak powstał — sprzątamy
  await request.delete(`${BASE}/api/admin/affixes/${key}`, { headers });
});
