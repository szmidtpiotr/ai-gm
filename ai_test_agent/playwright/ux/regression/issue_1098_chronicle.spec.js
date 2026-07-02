/**
 * REGRESSION #1098 (F-79) — Kronika bohatera: GET /characters/{id}/chronicle zwraca {legend, chapters, scars}.
 * Acceptance: endpoint istnieje, zwraca poprawną strukturę JSON; bohater z bliznami (Mizel 999420) ma scars[].
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1098 — /chronicle endpoint zwraca poprawną strukturę", async ({ page }) => {
  const r = await page.request.get("/api/characters/999420/chronicle");
  expect(r.ok(), "endpoint /chronicle nie odpowiada 200 (#1098)").toBeTruthy();

  const body = await r.json();
  expect(body, "brak klucza 'legend' w odpowiedzi").toHaveProperty("legend");
  expect(body, "brak klucza 'chapters' w odpowiedzi").toHaveProperty("chapters");
  expect(body, "brak klucza 'scars' w odpowiedzi").toHaveProperty("scars");

  expect(Array.isArray(body.chapters), "chapters nie jest tablicą").toBeTruthy();
  expect(Array.isArray(body.scars), "scars nie jest tablicą").toBeTruthy();
});

test("REGRESSION #1098 — Mizel (999420) ma bliznę porzucenia w scars[]", async ({ page }) => {
  const r = await page.request.get("/api/characters/999420/chronicle");
  expect(r.ok()).toBeTruthy();

  const body = await r.json();
  expect(body.scars.length, "Mizel powinien mieć ≥1 bliznę").toBeGreaterThanOrEqual(1);

  const scar = body.scars[0];
  expect(scar.abandonment_note, "blizna powinna mieć abandonment_note").toBeTruthy();
  expect(scar.outcome, "outcome blizny powinien być 'abandoned'").toBe("abandoned");
});

test("REGRESSION #1098 — /history nadal działa obok /chronicle", async ({ page }) => {
  const r = await page.request.get("/api/characters/999420/history");
  expect(r.ok(), "endpoint /history nie działa po dodaniu /chronicle").toBeTruthy();

  const body = await r.json();
  expect(body, "brak klucza 'history' w /history").toHaveProperty("history");
  expect(Array.isArray(body.history)).toBeTruthy();
});
