/**
 * REGRESSION #1172 — JWT auto-refresh musi synchronizować in-memory authToken.
 * Acceptance: po odświeżeniu tokena game.js (recap/journal/bugreport) nie wysyła
 * już wygasłego `Bearer ${authToken}`. Weryfikacja kontraktu źródła app.js:
 * _tryRefreshAccessToken zapisuje access_token do authToken ORAZ legacy 'token'.
 *
 * Bug był czysto kliencki (code-review, żaden endpoint się nie zmienił), więc
 * regresja pilnuje że fix nie zostanie cofnięty.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1172 — refresh zapisuje authToken + legacy token", async ({ page }) => {
  const r = await page.request.get("/js/app.js?probe=1172");
  expect(r.ok(), "app.js nie serwuje się (200)").toBeTruthy();
  const src = await r.text();

  // Wytnij ciało _tryRefreshAccessToken, żeby asercje dotyczyły właściwego miejsca.
  const start = src.indexOf("_tryRefreshAccessToken");
  expect(start, "brak funkcji _tryRefreshAccessToken w app.js").toBeGreaterThan(-1);
  const body = src.slice(start, start + 1200);

  expect(body, "refresh nie ustawia in-memory authToken (#1172)").toContain("authToken = data.access_token");
  expect(body, "refresh nie ustawia legacy klucza 'token' (#1172)").toMatch(/localStorage\.setItem\(['"]token['"], data\.access_token\)/);
});
