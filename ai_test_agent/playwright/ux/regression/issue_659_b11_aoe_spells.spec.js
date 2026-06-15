/**
 * REGRESSION #659 (B11) — czary AoE maga (attack_aoe) uderzają wielu wrogów.
 * Logika silnika (1 rzut d20 vs cel główny, obrażenia każdemu żywemu wrogowi przy aoe=1,
 * maks 3 przy aoe=0/chain, mana z góry, blocked przy braku many, Nat1 miscast, loot+XP per kill)
 * w pełni pokryta pytest test_issue659_b11_aoe_spells.py (10/10). Ten spec to kontrakt DANYCH,
 * na którym stoi gałąź silnika: burning_arc/chain_lightning/fireball to czary `attack_aoe`
 * z poprawnym tier/mana/damage_die/aoe (wartości startowe Numbers Policy #659).
 * Acceptance: burning_arc T2/4m/1d6/aoe=1, chain_lightning T4/5m/2d6/aoe=0, fireball T5/6m/3d6/aoe=1.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "admin dev-login demo/demo nie zwrócił 200").toBeTruthy();
  const body = await r.json();
  expect(body.token, "brak tokenu admina").toBeTruthy();
  return body.token;
}

test("REGRESSION #659 — burning_arc/chain_lightning/fireball to attack_aoe z poprawnymi parametrami", async ({ request }) => {
  const token = await adminToken(request);

  const spellsResp = await request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(spellsResp.ok(), "GET /api/admin/spells nie zwrócił 200").toBeTruthy();
  const spells = (await spellsResp.json()).items || [];
  const spellByKey = Object.fromEntries(spells.map((s) => [s.key, s]));

  // Numbers Policy #659 — wartości startowe (tuning po B13).
  const EXPECTED = {
    burning_arc:     { tier: 2, mana_cost: 4, damage_die: "1d6", aoe: 1 },
    chain_lightning: { tier: 4, mana_cost: 5, damage_die: "2d6", aoe: 0 },
    fireball:        { tier: 5, mana_cost: 6, damage_die: "3d6", aoe: 1 },
  };

  for (const [key, exp] of Object.entries(EXPECTED)) {
    const s = spellByKey[key];
    expect(s, `brak czaru AoE ${key} w katalogu`).toBeTruthy();
    expect(s.spell_type, `${key} musi być typu attack_aoe`).toBe("attack_aoe");
    expect(Number(s.tier), `${key} tier musi = ${exp.tier}`).toBe(exp.tier);
    expect(Number(s.mana_cost), `${key} mana_cost musi = ${exp.mana_cost}`).toBe(exp.mana_cost);
    expect(String(s.damage_die), `${key} damage_die musi = ${exp.damage_die}`).toBe(exp.damage_die);
    expect(Number(s.aoe), `${key} aoe flag musi = ${exp.aoe}`).toBe(exp.aoe);
  }
});
