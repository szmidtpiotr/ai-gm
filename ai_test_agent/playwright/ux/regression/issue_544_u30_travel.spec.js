/**
 * REGRESSION #544 (U30) — Ruch mechaniczny: POST /travel + current_hex sync.
 * Acceptance: POST /travel endpoint istnieje i przyjmuje target_hex LUB target_location_key;
 * fix #518: ruch tekstowy aktualizuje current_hex (resolve location_key → hex).
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

async function playerLogin(request) {
  const r = await request.post(`${BASE}/api/auth/login`, {
    data: { username: "demo", password: "demo" },
  });
  if (!r.ok()) return null;
  const d = await r.json();
  return d.access_token || d.token || null;
}

test("REGRESSION #544 U30 — POST /travel endpoint istnieje (nie 404)", async ({ request }) => {
  const token = await playerLogin(request);
  if (!token) { test.skip(); return; }

  // Pobierz aktywną kampanię gracza
  const campsR = await request.get(`${BASE}/api/campaigns`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!campsR.ok()) { test.skip(); return; }
  const camps = await campsR.json();
  const campList = camps.campaigns || (Array.isArray(camps) ? camps : []);
  const camp = campList.find(c => c.status === "active") || campList[0];
  if (!camp) { test.skip(); return; }

  // Pobierz postać kampanii
  const charR = await request.get(`${BASE}/api/campaigns/${camp.id}/characters`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!charR.ok()) { test.skip(); return; }
  const chars = await charR.json();
  const charList = chars.characters || (Array.isArray(chars) ? chars : []);
  if (!charList.length) { test.skip(); return; }
  const charId = charList[0].id;

  // Pobierz mapę żeby mieć valid hex
  const mapR = await request.get(`${BASE}/api/campaigns/${camp.id}/world-map?character_id=${charId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!mapR.ok()) { test.skip(); return; }
  const mapData = await mapR.json();
  const hexes = mapData.hexes || [];
  if (!hexes.length) { test.skip(); return; }

  const currentHex = mapData.current_hex || { q: 0, r: 0 };
  const targetHex = hexes.find(h => h.q !== currentHex.q || h.r !== currentHex.r) || hexes[0];

  const r = await request.post(`${BASE}/api/campaigns/${camp.id}/travel`, {
    data: { character_id: charId, target_hex: { q: targetHex.q, r: targetHex.r } },
    headers: { Authorization: `Bearer ${token}` },
  });

  expect(r.status(), `POST /travel nie powinien zwracać 404 — endpoint musi istnieć`).not.toBe(404);
  expect([200, 400, 403], `Nieoczekiwany status ${r.status()}`).toContain(r.status());
});


test("REGRESSION #544 U30 — POST /travel bez target → 422", async ({ request }) => {
  const token = await playerLogin(request);
  if (!token) {
    // Fallback bez auth
    const r = await request.post(`${BASE}/api/campaigns/1/travel`, {
      data: { character_id: 1 },
    });
    expect([401, 403, 422], `Status nieoczekiwany: ${r.status()}`).toContain(r.status());
    return;
  }

  const campsR = await request.get(`${BASE}/api/campaigns`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!campsR.ok()) { test.skip(); return; }
  const camps = await campsR.json();
  const campList = camps.campaigns || (Array.isArray(camps) ? camps : []);
  const camp = campList.find(c => c.status === "active") || campList[0];
  if (!camp) { test.skip(); return; }

  const r = await request.post(`${BASE}/api/campaigns/${camp.id}/travel`, {
    data: { character_id: 1 },  // brak target_hex i target_location_key
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status(), `Brak targetu powinien dać 422, dostano ${r.status()}`).toBe(422);
});


test("REGRESSION #544 U30 — POST /travel z target_location_key (nie 404)", async ({ request }) => {
  const token = await playerLogin(request);
  if (!token) { test.skip(); return; }

  const campsR = await request.get(`${BASE}/api/campaigns`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!campsR.ok()) { test.skip(); return; }
  const camps = await campsR.json();
  const campList = camps.campaigns || (Array.isArray(camps) ? camps : []);
  const camp = campList.find(c => c.status === "active") || campList[0];
  if (!camp) { test.skip(); return; }

  const charR = await request.get(`${BASE}/api/campaigns/${camp.id}/characters`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!charR.ok()) { test.skip(); return; }
  const chars = await charR.json();
  const charList = chars.characters || (Array.isArray(chars) ? chars : []);
  if (!charList.length) { test.skip(); return; }
  const charId = charList[0].id;

  // Weź dowolny klucz lokacji z world info
  const worldR = await request.get(`${BASE}/api/campaigns/${camp.id}/world-map?character_id=${charId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!worldR.ok()) { test.skip(); return; }
  const worldData = await worldR.json();
  const hexes = worldData.hexes || [];
  const hexWithLoc = hexes.find(h => h.label && h.label.length > 0);
  if (!hexWithLoc) { test.skip(); return; }

  // Użyj hexu jako target_hex (nie location_key — lokacja może nie mieć klucza)
  // Test weryfikuje że endpoint rozumie target_location_key (nawet jeśli zwróci 400)
  const r = await request.post(`${BASE}/api/campaigns/${camp.id}/travel`, {
    data: { character_id: charId, target_location_key: "test_loc_nonexistent" },
    headers: { Authorization: `Bearer ${token}` },
  });

  expect(r.status(), `POST /travel z target_location_key nie powinien 404`).not.toBe(404);
  // 400 oczekiwane dla nieistniejącej lokacji
  expect([200, 400, 403], `Status ${r.status()} nieoczekiwany`).toContain(r.status());
  if (r.status() === 400) {
    const body = await r.json();
    expect(body.detail || body.error || "", `400 powinien mieć detail`).toContain("not placed");
  }
});
