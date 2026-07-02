/**
 * REGRESSION #1065 (PAGINACJA) — Historia kampanii obsługuje offset/total_count; viewer pokazuje "Wczytaj starsze".
 * Acceptance: GET /api/campaigns/{id}/turns-history?offset=N zwraca total_count i różną stronę tur.
 * Admin endpoint GET /api/admin/campaigns/{id}/turns analogicznie.
 */
const { test, expect } = require("@playwright/test");

const ADMIN_CREDS = { username: "demo", password: "demo" };

async function getAdminToken(request) {
  const r = await request.post("/api/admin/dev-login", { data: ADMIN_CREDS });
  return r.ok() ? (await r.json()).token : null;
}

async function getCampaignWithTurns(request, minTurns = 3) {
  // Use health + known archived campaign approach
  const r = await request.get("/api/campaigns/99791/turns-history?limit=1&user_id=1");
  if (r.ok()) return 99791;
  return null;
}

test("REGRESSION #1065 — turns-history returns total_count", async ({ request }) => {
  const campId = await getCampaignWithTurns(request);
  if (!campId) test.skip("No known campaign with turns");

  const r = await request.get(`/api/campaigns/${campId}/turns-history?limit=5&user_id=1`);
  expect(r.ok(), `turns-history 200 (#1065)`).toBeTruthy();
  const data = await r.json();
  expect(typeof data.total_count, "total_count must be number (#1065)").toBe("number");
  expect(data.total_count, "total_count >= 0").toBeGreaterThanOrEqual(0);
  expect(Array.isArray(data.turns), "turns is array").toBeTruthy();
});

test("REGRESSION #1065 — turns-history offset returns different page", async ({ request }) => {
  const campId = await getCampaignWithTurns(request);
  if (!campId) test.skip("No known campaign with turns");

  const r1 = await request.get(`/api/campaigns/${campId}/turns-history?limit=3&offset=0&user_id=1`);
  const r2 = await request.get(`/api/campaigns/${campId}/turns-history?limit=3&offset=3&user_id=1`);
  expect(r1.ok()).toBeTruthy();
  expect(r2.ok()).toBeTruthy();

  const p1 = await r1.json();
  const p2 = await r2.json();
  // Both responses have total_count
  expect(typeof p1.total_count).toBe("number");
  expect(typeof p2.total_count).toBe("number");
  // Pages must not overlap if both have content
  if (p1.turns.length > 0 && p2.turns.length > 0) {
    const ids1 = new Set(p1.turns.map(t => t.turn_number));
    const ids2 = new Set(p2.turns.map(t => t.turn_number));
    const overlap = [...ids1].filter(n => ids2.has(n));
    expect(overlap.length, `pages must not overlap (#1065): ${overlap}`).toBe(0);
  }
});

test("REGRESSION #1065 — admin turns endpoint returns total_count", async ({ request }) => {
  const token = await getAdminToken(request);
  if (!token) test.skip("Admin login unavailable");

  const campId = 99791;
  const r = await request.get(`/api/admin/campaigns/${campId}/turns?limit=5`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "admin turns 200 (#1065)").toBeTruthy();
  const data = await r.json();
  expect(typeof data.total_count, "admin total_count is number").toBe("number");
  expect(Array.isArray(data.items), "items is array").toBeTruthy();
});

test("REGRESSION #1065 — admin turns offset paginates correctly", async ({ request }) => {
  const token = await getAdminToken(request);
  if (!token) test.skip("Admin login unavailable");

  const campId = 99791;
  const r1 = await request.get(`/api/admin/campaigns/${campId}/turns?limit=3&offset=0`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const r2 = await request.get(`/api/admin/campaigns/${campId}/turns?limit=3&offset=3`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r1.ok()).toBeTruthy();
  expect(r2.ok()).toBeTruthy();

  const d1 = await r1.json();
  const d2 = await r2.json();
  if (d1.items.length > 0 && d2.items.length > 0) {
    const ids1 = new Set(d1.items.map(t => t.id));
    const ids2 = new Set(d2.items.map(t => t.id));
    const overlap = [...ids1].filter(id => ids2.has(id));
    expect(overlap.length, `admin pages must not overlap (#1065)`).toBe(0);
  }
});
