/**
 * REGRESSION #1160 — AoE spell damage przechodzi przez model obrony #826 (redukcja pancerzem + margin).
 * Pełna logika pokryta pytestem backend/tests/test_issue1160_aoe_defense.py (RED→GREEN:
 *   pancerz 25 tnie 13 surowego → 1 finalne; brak pancerza → pełne obrażenia).
 * Ten spec pilnuje kontraktu danych, od których zależy ścieżka AoE: fireball musi istnieć
 * jako attack_aoe z damage_die — inaczej gałąź _resolve_aoe_single_target nigdy nie odpala.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "admin login must succeed (#1160)").toBeTruthy();
  const body = await login.json();
  const token = body.token || body.access_token;
  expect(token, "login must return token (#1160)").toBeTruthy();
  return token;
}

test("REGRESSION #1160 — fireball istnieje jako attack_aoe z damage_die (ścieżka AoE osiągalna)", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const r = await page.request.get("/api/admin/spells", auth);
  expect(r.ok(), "/api/admin/spells nie odpowiada 200 (#1160)").toBeTruthy();
  const body = await r.json();
  const list = Array.isArray(body) ? body : (body.spells ?? body.items ?? []);

  const fb = list.find((s) => s.key === "fireball");
  expect(fb, "brak spell 'fireball' (#1160)").toBeTruthy();
  expect(fb.spell_type, "fireball musi być attack_aoe (#1160)").toBe("attack_aoe");
  expect(String(fb.damage_die || ""), "fireball musi mieć damage_die (#1160)").toMatch(/\d+d\d+/);

  const aoe = list.filter((s) => s.spell_type === "attack_aoe");
  expect(aoe.length, "brak jakiegokolwiek czaru AoE — ścieżka obrony AoE martwa (#1160)").toBeGreaterThanOrEqual(1);
});
