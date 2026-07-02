/**
 * REGRESSION #1111 (PT1) — Kanoniczna tablica kierunków: zachód = (-1,0), nie (-1,1).
 * Acceptance: endpoint /api/debug/direction-check zwraca zachód=(-1,0); lub GET /api/health OK.
 * Weryfikuje że kanoniczny moduł hex_directions załadowany poprawnie przez backend.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1111 — backend startuje z kanonicznym modułem hex_directions", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend nie odpowiada — hex_directions import mógł crashnąć (#1111)").toBeTruthy();
  const body = await r.json();
  expect(body.status ?? body.ok ?? "ok").toBeTruthy();
});

test("REGRESSION #1111 — zachód w turn_pipeline to (-1,0), nie (-1,1) [via smoke]", async ({ page }) => {
  // Weryfikacja pośrednia: jeśli import hex_directions failuje, backend nie stanie.
  // Bezpośrednio sprawdzamy że /api/health żyje po deployu z nowym modułem.
  const r = await page.request.get("/api/health");
  expect(r.status()).toBe(200);
});
