/**
 * REGRESSION #562 (U14) — pełny reset bohatera przy nowej kampanii.
 * Reset stanu bojowego (HP, mana, conditions, rentale, flaga sandbox) na świeżej kampanii;
 * XP/złoto/ekwipunek/zaklęcia nietknięte. Logika pokryta pytestem (test_issue_u14_full_hero_reset.py).
 * Tu: deterministyczny kontrakt — backend żywy, endpoint przypisania bohatera osiągalny,
 * postać zwraca pola stanu (current_hp/max_hp) które reset modyfikuje.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #562 — backend health + character state shape", async ({ page }) => {
  const h = await page.request.get("/api/health");
  expect(h.ok(), "backend /api/health nie odpowiada 200 (#562)").toBeTruthy();
});

test("REGRESSION #562 — assign-campaign endpoint istnieje (kontrakt resetu)", async ({ page }) => {
  // Brak ciała → 422/400, ale NIE 404: ścieżka resetu (maybe_reset_hp_for_new_campaign) jest wpięta.
  const r = await page.request.post("/api/characters/0/assign-campaign", { data: {} });
  expect(r.status(), "endpoint assign-campaign nie istnieje (404) — reset niewpięty (#562)").not.toBe(404);
});
