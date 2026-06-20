/**
 * REGRESSION #765 — Odzyskiwanie amunicji: endpoint zwraca szansę (40%) i wynik odzysku.
 * Acceptance: GET ammo-spent podaje szansę startową 0.40 + ile wystrzelono;
 * POST recover-ammo zwraca strukturę odzysku (recovered/total) bez błędu.
 */
const { test, expect } = require("@playwright/test");

const CAMPAIGN = 1; // dowolna kampania — endpoint czyta ostatnią walkę (lub pustą)

test("REGRESSION #765 — ammo-spect podaje szansę 40%", async ({ request }) => {
  const r = await request.get(`/api/campaigns/${CAMPAIGN}/combat/ammo-spent`);
  expect(r.ok(), "GET ammo-spent != 200").toBeTruthy();
  const { ok, data } = await r.json();
  expect(ok).toBeTruthy();
  expect(data, "brak data w odpowiedzi").toBeTruthy();
  expect(data.chance, "szansa odzysku startowa musi być 0.40").toBe(0.4);
  expect(typeof data.total, "total powinno być liczbą").toBe("number");
  expect(typeof data.fired, "fired powinno być obiektem").toBe("object");
});

test("REGRESSION #765 — recover-ammo zwraca strukturę odzysku", async ({ request }) => {
  const r = await request.post(`/api/campaigns/${CAMPAIGN}/combat/recover-ammo`);
  expect(r.ok(), "POST recover-ammo != 200").toBeTruthy();
  const { ok, data } = await r.json();
  expect(ok).toBeTruthy();
  expect(data, "brak data").toBeTruthy();
  expect(typeof data.total, "total powinno być liczbą").toBe("number");
  expect(data.recovered, "recovered powinno być obiektem").toBeTruthy();
  expect(typeof data.recovered).toBe("object");
});
