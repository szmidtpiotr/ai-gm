/**
 * REGRESSION #584 (S4) — Testy przeciwne na prawdziwych statach (aktor-agnostycznie).
 * Acceptance: opposed test broni się prawdziwym statem celu, więc różni przeciwnicy dają
 *             różny próg. Tu weryfikujemy deterministyczny substrat: osiłek (brute) ma
 *             niższe WIS niż kapłan (caster), więc perswazja na osiłku jest łatwiejsza;
 *             oraz że skille społeczne z testem przeciwnym są w katalogu mechaniki.
 *             Sam rzut opponenta (d20 + stat_mod + kondycje) pokrywa pytest.
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

test("REGRESSION #584 — osiłek ma niższe WIS niż kapłan (perswazja na osiłku łatwiejsza)", async ({ request }) => {
  const token = await adminToken(request);
  const auth = { Authorization: `Bearer ${token}` };
  const brute = "s4_pw_osilek";
  const caster = "s4_pw_kaplan";

  for (const k of [brute, caster]) {
    await request.delete(`${BASE}/api/admin/enemies/${k}?force=true`, { headers: auth });
  }

  // brute archetyp (osiłek) → WIS niskie
  const c1 = await request.post(`${BASE}/api/admin/enemies`, {
    headers: auth,
    data: { key: brute, label: "Osiłek Brutus", tier: "standard",
            hp_base: 16, ac_base: 12, attack_bonus: 3, damage_die: "1d8" },
  });
  expect(c1.ok(), `create brute failed: ${c1.status()}`).toBeTruthy();
  const bruteStats = (await c1.json()).item.stats_json;

  // caster archetyp (kapłan) → WIS wysokie
  const c2 = await request.post(`${BASE}/api/admin/enemies`, {
    headers: auth,
    data: { key: caster, label: "Kapłan Mrocznego Kultu", tier: "standard",
            hp_base: 12, ac_base: 11, attack_bonus: 1, damage_die: "1d4" },
  });
  expect(c2.ok(), `create caster failed: ${c2.status()}`).toBeTruthy();
  const casterStats = (await c2.json()).item.stats_json;

  expect(bruteStats && casterStats, "oba wrogi mają stats_json").toBeTruthy();
  // To jest mechaniczny powód, dla którego perswazja (vs WIS) na osiłku jest łatwiejsza.
  expect(bruteStats.WIS, "osiłek WIS < kapłan WIS").toBeLessThan(casterStats.WIS);

  for (const k of [brute, caster]) {
    await request.delete(`${BASE}/api/admin/enemies/${k}?force=true`, { headers: auth });
  }
});

test("REGRESSION #584 — katalog mechaniki zawiera skille społeczne z testem przeciwnym", async ({ request }) => {
  const r = await request.get(`${BASE}/api/mechanics/skills`);
  expect(r.ok(), `mechanics/skills nie odpowiada 200: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  const rows = Array.isArray(body) ? body : (body.items || body.skills || []);
  const keys = new Set(rows.map((s) => (s.key || s.skill_key || "").toLowerCase()));
  for (const social of ["persuasion", "deception", "intimidation"]) {
    expect(keys.has(social), `skill '${social}' (opposed) obecny w katalogu`).toBeTruthy();
  }
});
