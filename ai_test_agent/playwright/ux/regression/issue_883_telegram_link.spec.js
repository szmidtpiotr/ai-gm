/**
 * REGRESSION #883 (Faza N1 of #602) — Telegram easy-click linking.
 * Request-level contract (redeem/bind logic covered exhaustively by pytest
 * test_issue883_telegram_link.py). Here we lock the deployed HTTP surface:
 *   - link-token / status / notify-prefs are JWT-gated (401 without auth)
 *   - webhook accepts an update and always answers 200 (no retry-storm)
 *   - webhook ignores non-/start updates
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #883 — link-token wymaga auth (401)", async ({ request }) => {
  const r = await request.post(`${BASE}/api/users/telegram/link-token`);
  expect(r.status(), "link-token bez tokenu powinien być 401").toBe(401);
});

test("REGRESSION #883 — telegram/status wymaga auth (401)", async ({ request }) => {
  const r = await request.get(`${BASE}/api/users/telegram/status`);
  expect(r.status()).toBe(401);
});

test("REGRESSION #883 — notify-prefs wymaga auth (401)", async ({ request }) => {
  const r = await request.get(`${BASE}/api/users/notify-prefs`);
  expect(r.status()).toBe(401);
});

test("REGRESSION #883 — webhook ignoruje nie-/start i zwraca 200", async ({ request }) => {
  const r = await request.post(`${BASE}/api/telegram/webhook`, {
    data: { message: { text: "cześć", chat: { id: 1 } } },
  });
  expect(r.ok(), `webhook nie 200: ${r.status()}`).toBeTruthy();
  const b = await r.json();
  expect(b.ok).toBeTruthy();
  expect(b.handled).toBeFalsy();
});

test("REGRESSION #883 — webhook na zły token: handled, nie linked", async ({ request }) => {
  const r = await request.post(`${BASE}/api/telegram/webhook`, {
    data: { message: { text: "/start nieistniejacy_token", chat: { id: 999999 } } },
  });
  expect(r.ok()).toBeTruthy();
  const b = await r.json();
  expect(b.handled).toBeTruthy();
  expect(b.linked).toBeFalsy();
});
