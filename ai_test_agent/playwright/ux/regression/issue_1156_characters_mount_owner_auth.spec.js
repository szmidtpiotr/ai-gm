/**
 * REGRESSION #1156 (SEC) — usunięty podwójny bare mount characters + owner-auth na sheet.
 * Acceptance: bare /heroes (bez /api) → 404; /api/heroes → 200; GET sheet bez user_id → 422.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1156 — bare /heroes nie serwuje payloadu backendu", async ({ page }) => {
  // Przez proxy nginx bare (/heroes bez /api) wpada w SPA (HTML). Po usunięciu
  // bare mountu backend NIE zwraca już JSON-a z listą bohaterów pod tą ścieżką.
  const bare = await page.request.get("/heroes?user_id=1");
  const ctype = bare.headers()["content-type"] || "";
  expect(ctype.includes("application/json"), "bare /heroes wciąż zwraca JSON backendu").toBeFalsy();
});

test("REGRESSION #1156 — /api/heroes dalej działa", async ({ page }) => {
  const api = await page.request.get("/api/heroes?user_id=1");
  expect(api.status()).toBe(200);
});

test("REGRESSION #1156 — sheet wymaga user_id (owner-auth)", async ({ page }) => {
  const list = await page.request.get("/api/heroes?user_id=1");
  expect(list.status()).toBe(200);
  const body = await list.json();
  const heroes = body.heroes || body.characters || [];
  const cid = (heroes.find((h) => Number(h.id) !== 999420) || {}).id;
  test.skip(!cid, "brak testowego bohatera usera 1");
  const noUser = await page.request.get(`/api/characters/${cid}/sheet`);
  expect(noUser.status(), "sheet bez user_id nie odrzucony").toBe(422);
  const wrong = await page.request.get(`/api/characters/${cid}/sheet?user_id=99999999`);
  expect(wrong.status(), "sheet cudzego właściciela nie odrzucony").toBe(403);
});
