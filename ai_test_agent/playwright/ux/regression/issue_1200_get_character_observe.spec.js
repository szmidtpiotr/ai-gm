/**
 * REGRESSION #1200 (SEC) — get_character owner-check w trybie OBSERWACJI.
 * Acceptance: GET /api/characters/{id} nigdy nie blokuje (200, nie 403/422) —
 * niezależnie od tego czy przychodzi JWT. Enforcement dopiero w Fazie 2.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1200 — get_character nie blokuje (obserwacja)", async ({ page }) => {
  const list = await page.request.get("/api/heroes?user_id=1");
  expect(list.status()).toBe(200);
  const body = await list.json();
  const heroes = body.heroes || body.characters || [];
  const cid = (heroes.find((h) => Number(h.id) !== 999420) || {}).id;
  test.skip(!cid, "brak testowego bohatera usera 1");

  // Bez tokena (stary caller UI) — 200 jak dziś.
  const bare = await page.request.get(`/api/characters/${cid}`);
  expect(bare.status(), "get_character zablokował wywołanie bez JWT").toBe(200);
});
