/**
 * REGRESSION #780 (D1/D2/D3) — Atak z zaskoczenia + bramka intencji po przewadze.
 * Acceptance: frontend dostarcza renderer 3-przyciskowej bramki (Atak/Zastraszenie/
 * Wycofaj), a cache-bust app.js jest podbity. Mechanika (auto-hit, burst, skalowanie
 * sneak) pokryta pytestem; tu deterministyczny strażnik wdrożenia UI bramki.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #780 — gate renderer shipped + cache-bust bumped", async ({ page }) => {
  // index.html musi ładować app.js z nową wersją (bust cache po zmianie współdzielonego modułu)
  const idx = await page.request.get("/index.html");
  expect(idx.ok(), "index.html nie odpowiada 200 (#780)").toBeTruthy();
  const html = await idx.text();
  expect(html, "brak bumpa cache app.js?v=780 (#780)").toContain("app.js?v=780-advantage-gate");

  // app.js musi zawierać renderer bramki intencji + obsługę pola advantage_gate
  const js = await page.request.get("/js/app.js?v=780-advantage-gate-2026-06-19");
  expect(js.ok(), "app.js nie odpowiada 200 (#780)").toBeTruthy();
  const src = await js.text();
  expect(src, "brak funkcji renderAdvantageGate (#780)").toContain("function renderAdvantageGate");
  expect(src, "resolveSkillTest nie czyta advantage_gate (#780)").toContain("response.advantage_gate");
});
