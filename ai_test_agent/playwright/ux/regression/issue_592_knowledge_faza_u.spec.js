/**
 * REGRESSION #592 — knowledge_book zawiera 4 wpisy mechanik FAZY U.
 * Acceptance: GET /api/admin/knowledge-book zawiera tip_key:
 *   durability, robbery_raids, affix_pity_timer, economy_telemetry.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
const EXPECTED = ["durability", "robbery_raids", "affix_pity_timer", "economy_telemetry"];

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin dev-login failed: ${r.status()}`).toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #592 — 4 wpisy FAZY U w knowledge_book", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/knowledge-book`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `knowledge-book endpoint nie 200 (#592): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  const rows = Array.isArray(body) ? body : body.items || body.tips || [];
  const keys = new Set(rows.map((t) => t.tip_key));
  for (const k of EXPECTED) {
    expect(keys.has(k), `brak wpisu '${k}' w knowledge_book (#592)`).toBeTruthy();
  }
});
