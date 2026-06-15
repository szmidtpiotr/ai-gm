/**
 * REGRESSION #656 (B9) — czary kontroli mapują się na ISTNIEJĄCE kondycje FAZY S (reuse, zero duplikatu).
 * Logika trafienia (pojedynek INT vs WIS/CON, ½ many przy oporze, brak obrażeń, miscast) w pełni
 * pokryta pytest test_issue656_b9_spell_conditions.py (13/13). Ten spec to kontrakt DANYCH, na którym
 * stoi gałąź silnika: każdy z 6 wspieranych czarów `effect` ma effect_type = klucz kondycji
 * obecny w katalogu game_config_conditions, a `sleep`→`sleeping` jest jawnie WYKLUCZONY (brak takiej
 * kondycji w FAZIE S → silnik łagodnie odbija, nie tworzy nowego stanu).
 * Acceptance: dla każdego z 6 czarów effect istnieje kondycja FAZY S o tym kluczu; sleeping NIE istnieje.
 */
const { test, expect } = require("@playwright/test");

// 6 wspieranych czarów kontroli B9 → kondycja FAZY S (effect_type w game_config_spells).
const B9_EFFECT_SPELLS = {
  frost_grip: "slowed",
  hex: "cursed",
  poison_touch: "poisoned",
  blind: "blinded",
  confusion: "confused",
  stun_bolt: "stunned",
};

async function adminToken(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "admin dev-login demo/demo nie zwrócił 200").toBeTruthy();
  const body = await r.json();
  expect(body.token, "brak tokenu admina").toBeTruthy();
  return body.token;
}

test("REGRESSION #656 — 6 czarów kontroli mapuje się na kondycje FAZY S; sleeping wykluczony", async ({ request }) => {
  const token = await adminToken(request);

  const spellsResp = await request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(spellsResp.ok(), "GET /api/admin/spells nie zwrócił 200").toBeTruthy();
  const spells = (await spellsResp.json()).items || [];
  const spellByKey = Object.fromEntries(spells.map((s) => [s.key, s]));

  const condResp = await request.get("/api/mechanics/conditions");
  expect(condResp.ok(), "GET /api/mechanics/conditions nie zwrócił 200").toBeTruthy();
  const condBody = await condResp.json();
  const condList = Array.isArray(condBody) ? condBody : condBody.items || condBody.conditions || [];
  const condKeys = new Set(condList.map((c) => String(c.key || c.condition_key || c)));

  // Każdy wspierany czar: type=effect, effect_type = klucz kondycji obecny w katalogu FAZY S.
  for (const [spellKey, condKey] of Object.entries(B9_EFFECT_SPELLS)) {
    const s = spellByKey[spellKey];
    expect(s, `brak czaru kontroli ${spellKey} w katalogu`).toBeTruthy();
    expect(s.spell_type, `${spellKey} nie jest typu effect`).toBe("effect");
    expect(s.effect_type, `${spellKey} mapuje na ${condKey}`).toBe(condKey);
    expect(condKeys.has(condKey), `kondycja FAZY S '${condKey}' musi istniec (reuse, nie duplikat)`).toBeTruthy();
  }

  // sleep → sleeping: jawnie WYKLUCZONY z B9 — kondycja `sleeping` NIE istnieje w katalogu FAZY S.
  expect(condKeys.has("sleeping"), "'sleeping' nie powinno istniec — sleep jest wykluczony z B9").toBeFalsy();
});
