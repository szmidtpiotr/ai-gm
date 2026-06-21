/**
 * REGRESSION #593 — Web Push diagnostics endpoint + readiness contract.
 * Po 3 rundach „nadal nie działa" dołożyliśmy serwerową lampkę kontrolną:
 * GET /api/push/diagnostics zwraca stan gotowości push (klucze, biblioteka,
 * ładowalność klucza) BEZ ujawniania sekretów. Acceptance: endpoint 200 +
 * pola gotowości; vapid-public-key nadal 200; diagnostyka nie wycieka klucza.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #593 — /api/push/diagnostics zwraca stan gotowości serwera", async ({ page }) => {
  const r = await page.request.get("/api/push/diagnostics");
  expect(r.ok(), "diagnostics nie odpowiada 200 (#593)").toBeTruthy();
  const body = await r.json();
  for (const k of ["configured", "pywebpush_installed", "private_key_loadable", "public_key_len", "private_key_len", "has_email"]) {
    expect(body, `brak pola ${k} w diagnostyce (#593)`).toHaveProperty(k);
  }
  // Na DEV stack push jest skonfigurowany — biblioteka i klucz muszą być sprawne.
  expect(body.pywebpush_installed, "pywebpush niezainstalowany (#593)").toBeTruthy();
  expect(body.configured, "VAPID nieskonfigurowany na DEV (#593)").toBeTruthy();
  expect(body.private_key_loadable, "klucz VAPID nie ładuje się — uszkodzony (#593)").toBeTruthy();
});

test("REGRESSION #593 — diagnostyka NIE ujawnia surowego klucza prywatnego", async ({ page }) => {
  const r = await page.request.get("/api/push/diagnostics");
  const raw = await r.text();
  // Endpoint jest bez auth — eksponuje tylko długości/flagi, nigdy materiału klucza.
  expect(/private_key.?:.?".{20,}"/.test(raw), "diagnostyka zwraca surowy klucz (#593)").toBeFalsy();
});

test("REGRESSION #593 — vapid-public-key nadal 200 z kluczem", async ({ page }) => {
  const r = await page.request.get("/api/push/vapid-public-key");
  expect(r.ok(), "vapid-public-key nie 200 (#593)").toBeTruthy();
  const body = await r.json();
  expect(body.publicKey && body.publicKey.length > 80, "klucz publiczny niepoprawnej długości (#593)").toBeTruthy();
});
