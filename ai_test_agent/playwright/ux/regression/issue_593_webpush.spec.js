/**
 * REGRESSION #593 — Web Push pełny stack.
 * Acceptance: VAPID public key endpoint → 200; sw.js serwowany; UI gracza ma przycisk
 * „Włącz powiadomienia” + globalne funkcje subscribe (enablePushNotifications, helper base64).
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #593 — /api/push/vapid-public-key zwraca 200 z kluczem", async ({ request }) => {
  const r = await request.get(`${BASE}/api/push/vapid-public-key`);
  expect(r.ok(), `vapid endpoint nie 200 (#593): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(typeof body.publicKey === "string" && body.publicKey.length > 20, "brak publicKey").toBeTruthy();
});

test("REGRESSION #593 — service worker sw.js jest serwowany", async ({ request }) => {
  const r = await request.get(`${BASE}/sw.js`);
  expect(r.ok(), `sw.js nie serwowany (#593): ${r.status()}`).toBeTruthy();
  const txt = await r.text();
  expect(txt.includes("addEventListener('push'") || txt.includes('addEventListener("push"'),
    "sw.js nie zawiera handlera push").toBeTruthy();
});

test("REGRESSION #593 — UI gracza: przycisk + globalny subscribe flow", async ({ page }) => {
  await page.goto(`${BASE}/`);
  await page.waitForTimeout(1200);

  // przycisk w panelu ustawień (może być ukryty w foldzie, ale w DOM)
  await expect(page.locator("#enable-push-btn"), "brak przycisku Włącz powiadomienia (#593)").toHaveCount(1);

  // globalne funkcje z app.js (script klasyczny → deklaracje są na window)
  const ok = await page.evaluate(() =>
    typeof window.enablePushNotifications === "function" &&
    typeof window._urlBase64ToUint8Array === "function"
  );
  expect(ok, "brak globalnych funkcji push (#593)").toBeTruthy();

  // helper base64url → Uint8Array działa poprawnie
  const len = await page.evaluate(() => window._urlBase64ToUint8Array("BFUlKfy5W12txHxF5mGHVRtuMZ").length);
  expect(len).toBeGreaterThan(0);
});
