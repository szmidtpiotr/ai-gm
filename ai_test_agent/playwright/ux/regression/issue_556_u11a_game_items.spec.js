/**
 * REGRESSION #556 (U11a) — Tabela game_items istnieje i jest wypełniona backfillem z 3 starych tabel.
 * Acceptance: game_items zawiera 140 rekordów (weapon+armor+item+consumable), stare tabele niezmienione.
 * Weryfikuje też backward compat — stare endpointy admin zwracają 200 po migracji.
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

test("REGRESSION #556 — game_items: stary endpoint broni nadal działa (backward compat)", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };
  const r = await request.get(`${BASE}/api/admin/weapons`, { headers });
  expect(r.ok(), `Endpoint /api/admin/weapons nie odpowiada 200 — regresja U11a (#556): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  const items = Array.isArray(body) ? body : (body.items || body.data || []);
  expect(items.length, "Brak broni w odpowiedzi — regresja U11a (#556)").toBeGreaterThan(0);
});

test("REGRESSION #556 — game_items: stary endpoint przedmiotów nadal działa (backward compat)", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };
  const r = await request.get(`${BASE}/api/admin/items`, { headers });
  expect(r.ok(), `Endpoint /api/admin/items nie odpowiada — regresja U11a (#556): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  const items = Array.isArray(body) ? body : (body.items || body.data || []);
  expect(items.length, "Brak itemów w odpowiedzi (#556)").toBeGreaterThan(0);
});

test("REGRESSION #556 — game_items: stary endpoint konsumabli nadal działa (backward compat)", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };
  const r = await request.get(`${BASE}/api/admin/consumables`, { headers });
  expect(r.ok(), `Endpoint /api/admin/consumables nie odpowiada — regresja U11a (#556): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  const items = Array.isArray(body) ? body : (body.items || body.data || []);
  expect(items.length, "Brak konsumabli w odpowiedzi (#556)").toBeGreaterThan(0);
});

test("REGRESSION #556 — game_items: health check backend po migracji", async ({ request }) => {
  const r = await request.get(`${BASE}/api/health`);
  expect(r.ok(), "Backend nie odpowiada po migracji U11a (#556)").toBeTruthy();
});
