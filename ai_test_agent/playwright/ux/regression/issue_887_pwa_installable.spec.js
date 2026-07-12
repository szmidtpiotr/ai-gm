/**
 * REGRESSION #887 (Faza N5 of #602) — PWA installable (ŻAR / front-v2).
 * Locks the installability surface so the Android/iOS "add to home screen" +
 * post-install web push keep working. Device install itself is a manual check.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #887 — /v2/ index ma tagi instalowalności", async ({ request }) => {
  const r = await request.get(`${BASE}/v2/`);
  expect(r.ok(), `/v2/ nie serwowane: ${r.status()}`).toBeTruthy();
  const html = await r.text();
  expect(html.includes('rel="manifest"'), "brak <link rel=manifest>").toBeTruthy();
  expect(html.includes("apple-mobile-web-app-capable"), "brak apple-mobile-web-app-capable (iOS)").toBeTruthy();
  expect(html.includes("apple-touch-icon"), "brak apple-touch-icon (iOS)").toBeTruthy();
  expect(html.includes("theme-color"), "brak theme-color").toBeTruthy();
});

test("REGRESSION #887 — manifest: standalone + ikony (w tym maskable)", async ({ request }) => {
  const r = await request.get(`${BASE}/v2/manifest.webmanifest`);
  expect(r.ok()).toBeTruthy();
  const m = await r.json();
  expect(m.display, "display musi być standalone").toBe("standalone");
  expect(m.start_url && m.scope, "brak start_url/scope").toBeTruthy();
  expect(m.icons.length, "za mało ikon").toBeGreaterThanOrEqual(2);
  expect(m.icons.some((i) => i.purpose === "maskable"), "brak ikony maskable (Android)").toBeTruthy();
});

test("REGRESSION #887 — service worker /v2/sw.js: PWA + push", async ({ request }) => {
  const r = await request.get(`${BASE}/v2/sw.js`);
  expect(r.ok()).toBeTruthy();
  const txt = await r.text();
  // offline shell (install/fetch) + web push handler both present
  expect(txt.includes("install"), "SW bez handlera install").toBeTruthy();
  expect(txt.includes("addEventListener('push'") || txt.includes('addEventListener("push"'),
    "SW bez handlera push").toBeTruthy();
});
