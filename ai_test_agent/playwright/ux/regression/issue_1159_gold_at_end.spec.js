/**
 * REGRESSION #1159 — gold_at_end (kronika/historia) czytane z kolumny characters.gold_gp,
 *   nie z sheet_json.gold (którego nikt nie zapisuje → gold_at_end zawsze 0).
 * Pełna logika pokryta pytestem backend/tests/test_issue1159_gold_at_end.py (RED→GREEN:
 *   get_character_gold(conn,id) zwraca kolumnę; sheet_json ignorowany).
 * Ścieżki (close_campaign_with_summary, bug_report) odpalają się tylko przy końcu kampanii —
 * brak deterministycznego endpointu admina, więc ten spec to smoke: backend musi wstać
 * z poprawionym economy_service/turns/campaigns/bug_report (regresja importu/500).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1159 — backend zdrowy po fixie odczytu złota", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "/api/health nie 200 — backend nie wstał po fixie #1159").toBeTruthy();
});
