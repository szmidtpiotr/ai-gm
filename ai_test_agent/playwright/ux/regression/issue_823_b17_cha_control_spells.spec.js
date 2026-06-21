/**
 * REGRESSION #823 (B17) — czary kontroli umysłu charm_person + mass_fear (decyzja D3: na INT).
 * Pełna logika silnika (pojedynek INT vs WIS, effect_aoe→feared na wszystkich, miscast, mana)
 * pokryta pytest test_issue823_b17_cha_control_spells.py (9/9). Ten spec to kontrakt danych:
 * katalog czarów wystawia oba czary z poprawnym spell_type/effect_type po seedzie B17.
 * Acceptance: GET /api/admin/spells zawiera charm_person (effect/charmed) i mass_fear (effect_aoe/feared).
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

test("REGRESSION #823 — charm_person + mass_fear w katalogu z poprawnym spell_type/effect_type (D3: INT)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/spells nie zwrócił 200").toBeTruthy();
  const items = (await r.json()).items || [];

  const charm = items.find((s) => s.key === "charm_person");
  expect(charm, "brak czaru charm_person w katalogu (seed B17)").toBeTruthy();
  expect(charm.spell_type, "charm_person musi być spell_type=effect").toBe("effect");
  expect(charm.effect_type, "charm_person musi nakładać kondycję charmed").toBe("charmed");

  const fear = items.find((s) => s.key === "mass_fear");
  expect(fear, "brak czaru mass_fear w katalogu (seed B17)").toBeTruthy();
  expect(fear.spell_type, "mass_fear musi być spell_type=effect_aoe (gałąź AoE-kontroli)").toBe("effect_aoe");
  expect(fear.effect_type, "mass_fear musi nakładać kondycję feared").toBe("feared");
  expect(Number(fear.aoe) === 1, "mass_fear musi mieć aoe=1 (obszar)").toBeTruthy();
});
