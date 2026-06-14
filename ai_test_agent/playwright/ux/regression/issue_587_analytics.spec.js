/**
 * REGRESSION #587 — Overview → Zdarzenia: analytics events + llm endpoints istnieją.
 * Acceptance: GET /api/admin/analytics/events → 200 {events:[]}; /llm → 200 {by_type:[],slowest:[]}.
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

test("REGRESSION #587 — /analytics/events zwraca 200 z feedem", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/analytics/events?days=30`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `events endpoint nie odpowiada 200 (#587): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.events), "events musi być tablicą").toBeTruthy();
});

test("REGRESSION #587 — /analytics/llm zwraca 200 z by_type+slowest", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/analytics/llm?days=30`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `llm endpoint nie odpowiada 200 (#587): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.by_type), "by_type musi być tablicą").toBeTruthy();
  expect(Array.isArray(body.slowest), "slowest musi być tablicą").toBeTruthy();
});
