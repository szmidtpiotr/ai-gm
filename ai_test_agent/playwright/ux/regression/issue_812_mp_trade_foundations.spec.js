/**
 * REGRESSION #812 (G14) — Handel MP odłożony: fundamenty DB gotowe, brak implementacji.
 * Acceptance: character_inventory + campaign_members dostępne przez API; brak endpointu /trade/offer.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #812 — inventory endpoint istnieje (fundament handlu MP)", async ({ page }) => {
  // character_inventory jest fundamentem przyszłego handlu — endpoint /api/admin/characters musi istnieć
  // 401 = wymaga auth (endpoint istnieje), 404 = endpoint usunięty (fundament zepsuty)
  const r = await page.request.get("/api/admin/characters");
  const status = r.status();
  expect(
    status !== 404 && status !== 405,
    `GET /api/admin/characters zwrócił ${status} — endpoint nie istnieje, fundament character_inventory niedostępny (#812)`
  ).toBeTruthy();
});

test("REGRESSION #812 — /trade/offer nie istnieje (G14 poprawnie odłożone)", async ({ page }) => {
  // G14 nie może być wdrożone bez decyzji Piotra — endpoint handlu nie może istnieć
  const r = await page.request.post("/api/campaigns/1/trade/offer", {
    data: {},
    headers: { "Content-Type": "application/json" },
  });
  // 404 lub 405 = endpoint nie istnieje (poprawny stan "later")
  // 422 lub 401 = endpoint istnieje ale brak auth/danych — G14 przedwcześnie wdrożone
  const status = r.status();
  expect(
    status === 404 || status === 405 || status === 403,
    `POST /api/campaigns/1/trade/offer zwrócił ${status} — jeśli 200/422/401, G14 mogło być wdrożone bez decyzji (#812)`
  ).toBeTruthy();
});
