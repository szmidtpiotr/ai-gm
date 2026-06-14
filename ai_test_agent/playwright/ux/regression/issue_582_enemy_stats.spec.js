/**
 * REGRESSION #582 (S2) — Staty wrogów: stats_json + archetypy + seed heurystyką.
 * Acceptance: tworząc wroga przez API admin BEZ statów, dostaje 7 statów z archetypu
 *             (bandyta_lucznik → DEX 15); jawnie podane staty są zachowane; lista
 *             wrogów zwraca stats_json. Ścieżka walki niezmieniona (poza testem).
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

test("REGRESSION #582 — nowy wróg dostaje staty z archetypu (DEX 15 dla łucznika)", async ({ request }) => {
  const token = await adminToken(request);
  const auth = { Authorization: `Bearer ${token}` };
  const key = "s2_pw_bandyta_lucznik";

  // cleanup z poprzedniego uruchomienia
  await request.delete(`${BASE}/api/admin/enemies/${key}?force=true`, { headers: auth });

  // create BEZ stats_json → backend wyprowadza z archetypu (strzelec wygrywa po "lucznik")
  const create = await request.post(`${BASE}/api/admin/enemies`, {
    headers: auth,
    data: {
      key, label: "Bandyta Łucznik", tier: "standard",
      hp_base: 12, ac_base: 11, attack_bonus: 2, damage_die: "1d6",
    },
  });
  expect(create.ok(), `create enemy failed: ${create.status()}`).toBeTruthy();
  const item = (await create.json()).item;
  expect(item.stats_json, "stats_json powinno być wypełnione").toBeTruthy();
  expect(item.stats_json.DEX, "łucznik → DEX 15 (archetyp strzelec)").toBe(15);

  // lista wrogów zwraca stats_json
  const list = await request.get(`${BASE}/api/admin/enemies`, { headers: auth });
  expect(list.ok()).toBeTruthy();
  const rows = (await list.json()).items || (await (await request.get(`${BASE}/api/admin/enemies`, { headers: auth })).json());
  // tolerancyjnie: lista może zwracać {items:[...]} lub [...]
  const arr = Array.isArray(rows) ? rows : (rows.items || []);
  const found = arr.find((e) => e.key === key);
  expect(found, "nowy wróg widoczny na liście").toBeTruthy();
  expect(found.stats_json && found.stats_json.DEX).toBe(15);

  await request.delete(`${BASE}/api/admin/enemies/${key}?force=true`, { headers: auth });
});

test("REGRESSION #582 — jawnie podane staty są zachowane (nie nadpisane archetypem)", async ({ request }) => {
  const token = await adminToken(request);
  const auth = { Authorization: `Bearer ${token}` };
  const key = "s2_pw_custom_stats";

  await request.delete(`${BASE}/api/admin/enemies/${key}?force=true`, { headers: auth });

  const create = await request.post(`${BASE}/api/admin/enemies`, {
    headers: auth,
    data: {
      key, label: "Wróg Custom", tier: "standard",
      hp_base: 12, ac_base: 11, attack_bonus: 2, damage_die: "1d6",
      stats_json: { STR: 18, LCK: 5 },
    },
  });
  expect(create.ok(), `create enemy failed: ${create.status()}`).toBeTruthy();
  const item = (await create.json()).item;
  expect(item.stats_json.STR).toBe(18);
  expect(item.stats_json.LCK).toBe(5);

  await request.delete(`${BASE}/api/admin/enemies/${key}?force=true`, { headers: auth });
});
