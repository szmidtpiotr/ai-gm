/**
 * REGRESSION #575 (U25) — Pity timer afiksów (drop boss-kill + reroll u craftera).
 * Acceptance (kontrakt API, deterministyczny — pity nie wywraca istniejących ścieżek):
 *  - GET /api/inventory/{cid} (bez auth) żyje — to powierzchnia, do której trafia grant_loot.
 *  - POST /api/characters/{cid}/craft/reroll-affix jest WPIĘTY (401 auth-gate, nie 404 route-missing
 *    ani 500 crash) — wpięcie pity do reroll_affix nie zepsuło trasy.
 *  - GET .../inventory/{inv}/affix-costs analogicznie wpięty (401, nie 404/500).
 * Pełna mechanika pity (3 bossy bez afiksu → gwarancja afiksu; 3 rerolle bez zmiany → inny afiks)
 * + trwałość liczników (tabela affix_pity) = pytest deterministyczny (mock rng) + sandbox admina.
 * Te ścieżki są auth-gated tokenem gracza (JWT) — niedostępnym deterministycznie w Playwright,
 * więc tu weryfikujemy WPIĘCIE trasy, a zachowanie pity pokrywa pytest.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
const CID = 2; // [TEST] Wojownik — istnieje na DEV

test("REGRESSION #575 — /inventory (cel grant_loot) odpowiada 200", async ({ request }) => {
  const r = await request.get(`${BASE}/api/inventory/${CID}`);
  expect(r.ok(), "endpoint /inventory nie odpowiada 200 (#575)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.data), "/inventory zwraca listę przedmiotów (#575)").toBeTruthy();
});

test("REGRESSION #575 — reroll-affix wpięty (401 auth-gate, nie 404/500)", async ({ request }) => {
  const r = await request.post(`${BASE}/api/characters/${CID}/craft/reroll-affix`, {
    data: { inventory_id: 99999999, affix_key: "__does_not_exist__" },
  });
  expect(
    [200, 401, 403].includes(r.status()),
    `reroll-affix zwrócił ${r.status()} — trasa niewpięta (404) lub crash (500) po wpięciu pity? (#575)`
  ).toBeTruthy();
});

test("REGRESSION #575 — affix-costs wpięty (401 auth-gate, nie 404/500)", async ({ request }) => {
  const r = await request.get(`${BASE}/api/characters/${CID}/inventory/1/affix-costs`);
  expect(
    [200, 401, 403].includes(r.status()),
    `affix-costs zwrócił ${r.status()} — trasa niewpięta lub crash? (#575)`
  ).toBeTruthy();
});
