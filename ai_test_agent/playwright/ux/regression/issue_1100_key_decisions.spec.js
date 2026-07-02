/**
 * REGRESSION #1100 (Ustrukturyzowana pamięć bohatera) — migracja key_decisions_json
 * + rozszerzony chapter_summary_service ładują się bez błędu, backend zdrowy.
 * Acceptance: backend startuje z nową kolumną/kodem, endpoint zdrowia = 200
 * (kronika bohatera + ekstrakcja decyzji nie wywalają aplikacji).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1100 — backend healthy with key_decisions migration", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "endpoint /api/health nie odpowiada 200 (#1100)").toBeTruthy();
  const body = await r.json();
  // health payload shape may vary; just assert we got a JSON object back
  expect(body && typeof body === "object", "health nie zwrócił JSON (#1100)").toBeTruthy();
});
