/**
 * REGRESSION #864 — ożyw martwe pole attacks_per_turn (wróg N>1 atakuje N razy/turę).
 * Acceptance: pole attacks_per_turn jest realnie wystawione w configu wroga (admin),
 *             edytowalne i walidowane (>=1) — silnik czyta je do pętli ataków wroga.
 *             (Logikę pętli pokrywa pytest test_issue864_enemy_multiattack.py.)
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin dev-login failed: ${r.status()}`).toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #864 — enemy config exposes attacks_per_turn field", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/enemies`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `GET /api/admin/enemies must return 200: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.items), "enemies payload must have items[]").toBeTruthy();
  if (body.items.length) {
    const e = body.items[0];
    expect(e, "enemy record must carry attacks_per_turn (#864)").toHaveProperty("attacks_per_turn");
    expect(Number(e.attacks_per_turn) >= 1, "attacks_per_turn must be >= 1").toBeTruthy();
  }
});

test("REGRESSION #864 — attacks_per_turn < 1 rejected (422)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.post(`${BASE}/api/admin/enemies`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { key: "mat864_invalid", label: "Bad", attacks_per_turn: 0 },
  });
  // walidacja pola: 0 musi być odrzucone (nie 500)
  expect(r.status(), "attacks_per_turn=0 must be rejected, not 500").not.toBe(500);
  expect([422, 400]).toContain(r.status());
});
