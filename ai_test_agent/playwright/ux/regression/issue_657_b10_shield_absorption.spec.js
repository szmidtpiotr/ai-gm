/**
 * REGRESSION #657 (B10) — tarcze maga mają pulę absorpcji (temp-HP) w effect_json.
 * Logika silnika (rzut tarczy w walce → absorb_hp na graczu, obrażenia wroga soaked przed HP,
 * non-stacking, blocked przy braku many) w pełni pokryta pytest
 * test_issue657_b10_shield_absorption.py (12/12). Ten spec to kontrakt DANYCH, na którym stoi
 * gałąź silnika: ward_of_iron i mage_armor to czary `defense` z effect_json.absorb > 0,
 * a migracja ustawiła wartości startowe (ward 6, mage 10).
 * Acceptance: ward_of_iron defense+absorb=6; mage_armor defense+absorb=10.
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

test("REGRESSION #657 — ward_of_iron/mage_armor to defense z pulą absorpcji w effect_json", async ({ request }) => {
  const token = await adminToken(request);

  const spellsResp = await request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(spellsResp.ok(), "GET /api/admin/spells nie zwrócił 200").toBeTruthy();
  const spells = (await spellsResp.json()).items || [];
  const spellByKey = Object.fromEntries(spells.map((s) => [s.key, s]));

  // Oczekiwane pule absorpcji (Numbers Policy #657 — wartości startowe).
  const EXPECTED = { ward_of_iron: 6, mage_armor: 10 };

  for (const [key, absorb] of Object.entries(EXPECTED)) {
    const s = spellByKey[key];
    expect(s, `brak czaru obronnego ${key} w katalogu`).toBeTruthy();
    expect(s.spell_type, `${key} musi być typu defense`).toBe("defense");
    let ej = {};
    try { ej = JSON.parse(s.effect_json || "{}"); } catch { ej = {}; }
    expect(Number(ej.absorb), `${key} effect_json.absorb musi = ${absorb}`).toBe(absorb);
  }
});
