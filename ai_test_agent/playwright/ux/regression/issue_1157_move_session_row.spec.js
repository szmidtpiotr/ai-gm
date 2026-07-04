/**
 * REGRESSION #1157 — /move zapisuje lokalizację w wierszu game_sessions kluczowanym po campaign_id
 *   (wcześniej WHERE id = campaign_id trafiał w zły/nieistniejący wiersz i /move cicho nic nie robił).
 * Pełna logika pokryta pytestem backend/tests/test_issue1157_move_session_row.py (RED→GREEN:
 *   sesja id=5 != campaign_id=1 → zapis ląduje w wierszu campaign_id=1).
 * Brak dedykowanego endpointu admina dla tej ścieżki (zapis wewnętrzny w turn_commands.handle),
 * więc ten spec to smoke: backend musi wstać z poprawionym modułem (regresja importu/500).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1157 — backend zdrowy po fixie turn_commands", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "/api/health nie 200 — backend nie wstał po fixie #1157").toBeTruthy();
});
