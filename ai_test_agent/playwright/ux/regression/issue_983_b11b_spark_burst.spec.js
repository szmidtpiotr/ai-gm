/**
 * REGRESSION #983 (B11b) — spark_burst: najtańszy czar AoE maga (tier 1) w starterze.
 * Rozszerza B11 (#659, silnik attack_aoe). Logika silnika pokryta pytest
 * test_issue983_b11b_spark_burst.py (6/6) + weryfikacja w Sandbox (3 cele trafione).
 * Ten spec to kontrakt DANYCH: spark_burst istnieje jako attack_aoe T1/3m/1d4/aoe=1.
 * Acceptance: spark_burst spell_type=attack_aoe, tier 1, mana 3, 1d4, aoe=1.
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

test("REGRESSION #983 — spark_burst to attack_aoe tier 1 z poprawnymi parametrami", async ({ request }) => {
  const token = await adminToken(request);

  const spellsResp = await request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(spellsResp.ok(), "GET /api/admin/spells nie zwrócił 200").toBeTruthy();
  const spells = (await spellsResp.json()).items || [];
  const s = Object.fromEntries(spells.map((x) => [x.key, x]))["spark_burst"];

  expect(s, "brak czaru spark_burst w katalogu").toBeTruthy();
  expect(s.spell_type, "spark_burst musi być typu attack_aoe").toBe("attack_aoe");
  expect(Number(s.tier), "spark_burst tier musi = 1").toBe(1);
  expect(Number(s.mana_cost), "spark_burst mana_cost musi = 3").toBe(3);
  expect(String(s.damage_die), "spark_burst damage_die musi = 1d4").toBe("1d4");
  expect(Number(s.aoe), "spark_burst aoe flag musi = 1 (wszyscy wrogowie)").toBe(1);
});
