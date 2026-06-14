/**
 * REGRESSION #613 (S18) — prymityw behavior_override + pełne confused/berserk/panicked.
 * Acceptance: katalog kondycji zawiera berserk (atak najbliższego niezależnie od frakcji) oraz
 * confused (k4 steruje turą) i panicked (wymuszona ucieczka) — kondycja steruje turą aktora.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #613 — behavior_override: berserk/confused/panicked w katalogu", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "GET /api/mechanics/conditions nie odpowiada 200 (#613)").toBeTruthy();
  const body = await r.json();
  const list = Array.isArray(body.conditions) ? body.conditions : [];
  const byKey = Object.fromEntries(list.filter((c) => c && c.key).map((c) => [c.key, c]));

  // berserk = nowa kondycja S18: atak najbliższego niezależnie od frakcji.
  const berserk = byKey.berserk;
  expect(berserk, "kondycja 'berserk' nie istnieje w katalogu (#613)").toBeTruthy();
  expect(/niezależnie od frakcji/i.test(berserk.description || ""), "opis berserk bez 'niezależnie od frakcji'").toBeTruthy();

  // confused podniesiony — k4 steruje turą.
  const confused = byKey.confused;
  expect(confused, "kondycja 'confused' nie istnieje (#613)").toBeTruthy();
  expect(/k4/i.test(confused.description || ""), "opis confused bez wzmianki o k4 (#613)").toBeTruthy();

  // panicked podniesiony — wymuszona ucieczka.
  const panicked = byKey.panicked;
  expect(panicked, "kondycja 'panicked' nie istnieje (#613)").toBeTruthy();
  expect(/ucieczk/i.test(panicked.description || ""), "opis panicked bez wzmianki o ucieczce (#613)").toBeTruthy();
});
