/**
 * REGRESSION #593 — Web Push pełny stack (port do ŻAR / front-v2).
 *
 * Player UI przeniesione do front-v2 (/v2/, React) — stary frontend/front ZAMROŻONY.
 * Ten spec sprawdza WDROŻONĄ powierzchnię ŻAR na poziomie żądań (bez logowania):
 *   1) /api/push/vapid-public-key → 200 z kluczem
 *   2) /api/push/diagnostics → serwer gotów (configured + pywebpush + klucz ładowalny)
 *   3) /v2/sw.js serwowany + zawiera handler push
 *   4) /v2/manifest.webmanifest serwowany + poprawny (PWA installable)
 *
 * Render przycisku „Włącz powiadomienia" (PushButton w Profile) jest za loginem
 * i weryfikowany osobno w spec 1266 UI; tu trzymamy kontrakt deploy/backend.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #593 — /api/push/vapid-public-key zwraca 200 z kluczem", async ({ request }) => {
  const r = await request.get(`${BASE}/api/push/vapid-public-key`);
  expect(r.ok(), `vapid endpoint nie 200 (#593): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(typeof body.publicKey === "string" && body.publicKey.length > 20, "brak publicKey").toBeTruthy();
});

test("REGRESSION #593 — /api/push/diagnostics: serwer gotów do wysyłki", async ({ request }) => {
  const r = await request.get(`${BASE}/api/push/diagnostics`);
  expect(r.ok(), `diagnostics nie 200 (#593): ${r.status()}`).toBeTruthy();
  const d = await r.json();
  expect(d.configured, "serwer nie configured (#593)").toBeTruthy();
  expect(d.pywebpush_installed, "brak pywebpush (#593)").toBeTruthy();
  expect(d.private_key_loadable, "klucz VAPID nieładowalny (#593)").toBeTruthy();
});

test("REGRESSION #593 — /v2/sw.js serwowany + handler push", async ({ request }) => {
  const r = await request.get(`${BASE}/v2/sw.js`);
  expect(r.ok(), `/v2/sw.js nie serwowany (#593): ${r.status()}`).toBeTruthy();
  const txt = await r.text();
  expect(txt.includes("addEventListener('push'") || txt.includes('addEventListener("push"'),
    "/v2/sw.js nie zawiera handlera push").toBeTruthy();
});

test("REGRESSION #593 — /v2/manifest.webmanifest poprawny (PWA)", async ({ request }) => {
  const r = await request.get(`${BASE}/v2/manifest.webmanifest`);
  expect(r.ok(), `/v2/manifest nie serwowany (#593/N5): ${r.status()}`).toBeTruthy();
  const m = await r.json();
  expect(Array.isArray(m.icons) && m.icons.length > 0, "manifest bez ikon").toBeTruthy();
  expect(!!m.start_url, "manifest bez start_url").toBeTruthy();
});
