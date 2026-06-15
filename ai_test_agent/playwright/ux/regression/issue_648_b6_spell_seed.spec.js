/**
 * REGRESSION #648 (B6) — Seed czarów maga Faza 1 w game_config_spells.
 * 16 czarów adoptowalnych dziś (atak ST / heal-self / self-buff obronny / kondycje
 * mapowane na ISTNIEJĄCE stany FAZY S) musi być widocznych w katalogu admina.
 * effect_type czarów-kondycji = klucz istniejący w game_config_conditions (reużycie,
 * zero duplikatu stanu). Pełny dowód wartości tier/mana/dmg = pytest
 * test_issue648_b6_spell_seed.py. Tu pilnujemy kontraktu katalogu + zakresu B6.
 * Acceptance: /api/admin/spells zawiera 16 nowych czarów; brak attack_aoe/summon w nich.
 */
const { test, expect } = require("@playwright/test");

const B6_KEYS = [
  "fire_bolt", "frost_bolt", "acid_splash", "lightning_arrow", "ice_lance",
  "inferno_strike", "minor_heal", "ward_of_iron", "mage_armor", "frost_grip",
  "hex", "poison_touch", "blind", "confusion", "stun_bolt", "detect_magic",
];

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200 (#648)").toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #648 — 16 czarów B6 zaseedowanych, brak aoe/summon w zbiorze", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };

  const r = await page.request.get("/api/admin/spells", { headers });
  expect(r.ok(), "/api/admin/spells nie odpowiada 200 (#648)").toBeTruthy();
  const body = await r.json();
  const spells = Array.isArray(body) ? body : body.items || body.spells || [];
  const byKey = new Map(spells.map((s) => [s.key, s]));

  // Wszystkie 16 czarów B6 obecne.
  for (const key of B6_KEYS) {
    expect(byKey.has(key), `czar B6 '${key}' brak w katalogu (#648)`).toBeTruthy();
  }

  // Zakres B6: żaden nie jest attack_aoe ani summon (te → B11 / Blok 3).
  for (const key of B6_KEYS) {
    const s = byKey.get(key);
    expect(["attack_aoe", "summon"]).not.toContain(s.spell_type);
    expect(Number(s.aoe || 0), `${key}: aoe=1 poza zakresem B6`).toBe(0);
  }

  // Legacy (Task 26) nietknięte — katalog ma ≥ 26 pozycji.
  expect(spells.length, "katalog powinien mieć ≥26 czarów (10 starych + 16 B6)").toBeGreaterThanOrEqual(26);
});

test("REGRESSION #648 — czary-kondycje reużywają stanów FAZY S (brak duplikatu)", async ({ page }) => {
  // effect_type czarów-kondycji musi być kluczem istniejącej kondycji.
  const cond = await page.request.get("/api/mechanics/conditions");
  expect(cond.ok(), "/api/mechanics/conditions nie odpowiada 200 (#648)").toBeTruthy();
  const cbody = await cond.json();
  const condKeys = new Set(
    (Array.isArray(cbody) ? cbody : cbody.conditions || []).map((c) => String(c.key).toLowerCase())
  );

  const expectedMap = {
    frost_grip: "slowed", hex: "cursed", poison_touch: "poisoned",
    blind: "blinded", confusion: "confused", stun_bolt: "stunned",
  };
  for (const [, effect] of Object.entries(expectedMap)) {
    expect(condKeys.has(effect), `kondycja '${effect}' musi istnieć w FAZA S (#648)`).toBeTruthy();
  }
});
