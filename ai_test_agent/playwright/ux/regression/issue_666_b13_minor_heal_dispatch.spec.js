/**
 * REGRESSION #666 (B13) — minor_heal dispatched poprawnie w walce (bug: ścieżka ataku).
 *
 * Bug: spell_type='heal' nie miał dispatcha → minor_heal atakował wroga zamiast leczyć gracza.
 * Fix: _resolve_heal_spell_in_combat + dispatch blok w resolve_attack.
 *
 * Kontrakt danych: minor_heal musi mieć spell_type='heal' i heal_die='1d6' w katalogu.
 * Logika silnika (minor_heal leczy gracza, mana spada, nie atakuje wroga) = pytest 6/6.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "admin dev-login nie zwrócił 200").toBeTruthy();
  const body = await r.json();
  expect(body.token, "brak tokenu admina").toBeTruthy();
  return body.token;
}

test("REGRESSION #666 — minor_heal to spell_type='heal' z heal_die w katalogu", async ({ request }) => {
  const token = await adminToken(request);

  const spellsResp = await request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(spellsResp.ok(), "GET /api/admin/spells nie zwrócił 200").toBeTruthy();
  const spells = (await spellsResp.json()).items || [];
  const spell = spells.find((s) => s.key === "minor_heal");

  expect(spell, "brak minor_heal w katalogu czarów").toBeTruthy();
  expect(spell.spell_type, "minor_heal musi być spell_type='heal'").toBe("heal");
  expect(spell.heal_die, "minor_heal musi mieć heal_die (np. 1d6)").toBeTruthy();
  expect(spell.mana_cost, "minor_heal musi mieć mana_cost > 0").toBeGreaterThan(0);
});
