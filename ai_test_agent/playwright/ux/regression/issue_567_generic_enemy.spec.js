/**
 * REGRESSION #567 — generyczny placeholder „Wróg" (key='enemy') nie wybierany przy walce.
 * Logika dopasowania jest backendowa (`_resolve_enemy_key_from_context`) i pokryta pytest
 * (`test_issue567_generic_enemy_placeholder.py`, 3/3). Ten spec to kotwica integralności:
 *  - placeholder 'enemy' nadal istnieje w katalogu (nie usunęliśmy danych),
 *  - backend żyje (endpoint enemies odpowiada).
 * Pełny scenariusz (atak „na wroga" nie tworzy przeciwnika „Wróg") — weryfikacja /game-test-player.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #567 — katalog wrogów odpowiada, placeholder nietknięty", async ({ page }) => {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await login.json();
  const r = await page.request.get("/api/admin/enemies", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "endpoint /admin/enemies nie odpowiada 200 (#567)").toBeTruthy();
  const body = await r.json();
  const rows = Array.isArray(body) ? body : (body.items || body.data || body.enemies || []);
  expect(Array.isArray(rows), "brak listy wrogów (#567)").toBeTruthy();
  // Placeholder ma istnieć (jest fallbackiem danych), ale logika go pomija — patrz pytest.
  const placeholder = rows.find((e) => String(e.key) === "enemy");
  expect(placeholder, "placeholder 'enemy' zniknął z katalogu — sprawdź migracje (#567)").toBeTruthy();
});
