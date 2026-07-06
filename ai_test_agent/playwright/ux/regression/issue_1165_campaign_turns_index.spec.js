/**
 * REGRESSION #1165 (PERF/code-review) — indeks na campaign_turns.campaign_id.
 * Acceptance: backend wstaje po migracji (indeks dodany do ADMIN_MIGRATIONS bez crashu),
 * a najgorętsza tabela odpowiada — /api/health = 200.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1165 — backend zdrowy po migracji indeksu campaign_turns", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "/api/health nie zwraca 200 — migracja #1165 mogła wysypać boot").toBeTruthy();
  const body = await r.json();
  expect(body, "brak ciała odpowiedzi /api/health (#1165)").toBeTruthy();
});
