/**
 * REGRESSION #673 (L4) — Ruch przez drzwi: POST /api/dungeons/move.
 * Acceptance: endpoint istnieje, zwraca ok+node lub ok:false+reason, 409 gdy brak runu.
 */
const { test, expect } = require("@playwright/test");

const API = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #673 L4 — /dungeons/move bez aktywnego runu zwraca 409", async ({ request }) => {
  // Kampania 9999 nie istnieje → brak aktywnego v2 runu → 409
  const r = await request.post(`${API}/api/dungeons/move`, {
    data: { character_id: 1, campaign_id: 9999, direction: "N" },
    failOnStatusCode: false,
  });
  const status = r.status();
  expect(
    status === 409 || status === 422,
    `Oczekiwano 409 (brak runu) lub 422 (walidacja), got ${status}`
  ).toBeTruthy();
});

test("REGRESSION #673 L4 — /dungeons/move bez direction zwraca 422", async ({ request }) => {
  const r = await request.post(`${API}/api/dungeons/move`, {
    data: { character_id: 1, campaign_id: 1 },
    failOnStatusCode: false,
  });
  // Brakujące wymagane pole direction → 422 Unprocessable Entity
  expect(r.status(), "Brak direction powinno dać 422 (#673)").toBe(422);
});

test("REGRESSION #673 L4 — GET /dungeons zwraca listę (serwis działa po L4)", async ({ request }) => {
  const r = await request.get(`${API}/api/dungeons`);
  expect(r.ok(), "GET /dungeons powinno być 200 (#673 backward-compat)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.dungeons), "dungeons powinno być tablicą").toBeTruthy();
});
