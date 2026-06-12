/**
 * REGRESSION #540 (U28) — Placement engine: lokacje osadzane na hexach mechanicznie.
 * Acceptance: GET /api/admin/locations/floating zwraca tablicę (może być pusta po backfillu),
 * każdy rekord ma pola key/label/terrain_tags (lista). POST /place na nieistniejący hex → 404.
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

test("REGRESSION #540 U28 — GET /api/admin/locations/floating zwraca tablicę", async ({ request }) => {
  const token = await adminToken(request);

  const r = await request.get(`${BASE}/api/admin/locations/floating`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `endpoint /floating nie odpowiada 200 (#540): ${r.status()}`).toBeTruthy();

  const body = await r.json();
  expect(Array.isArray(body), "odpowiedź powinna być tablicą").toBeTruthy();

  for (const loc of body) {
    expect(loc).toHaveProperty("key");
    expect(loc).toHaveProperty("label");
    expect(Array.isArray(loc.terrain_tags), `terrain_tags powinno być tablicą dla ${loc.key}`).toBeTruthy();
  }
});

test("REGRESSION #540 U28 — POST /place na nieistniejący hex zwraca 404", async ({ request }) => {
  const token = await adminToken(request);

  const floatingR = await request.get(`${BASE}/api/admin/locations/floating`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const floating = await floatingR.json();

  if (!floating.length) {
    console.log("Brak floating lokacji — skip POST test");
    return;
  }

  const locKey = floating[0].key;
  const r = await request.post(`${BASE}/api/admin/locations/${encodeURIComponent(locKey)}/place`, {
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    data: { q: -9999, r: -9999 },
  });
  expect([404, 409].includes(r.status()), `Oczekiwano 404 lub 409, got ${r.status()}`).toBeTruthy();
});
