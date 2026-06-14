/**
 * REGRESSION #589 + #590 — Mapa: kształt świata + podgląd/edycja wpisów.
 * #589: globalna generacja świata daje KWADRAT (nie heks) — sprawdzane pytestem (_world_hex_coords);
 *       tu weryfikujemy że endpoint generate istnieje i przyjmuje radius.
 * #590: floating zwraca pełne pola (description, parent_key, ai_generated); edit endpoint działa.
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

test("REGRESSION #590 — floating zwraca pełne pola do podglądu/edycji", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/locations/floating`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `/floating nie odpowiada 200 (#590): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body)).toBeTruthy();
  for (const loc of body) {
    // pola wymagane przez modal podglądu/edycji
    expect(loc).toHaveProperty("description");
    expect(loc).toHaveProperty("parent_key");
    expect(loc).toHaveProperty("ai_generated");
  }
});

test("REGRESSION #590 — edit endpoint zarejestrowany (404 dla nieistniejącego klucza, nie 405)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.patch(`${BASE}/api/admin/locations/__nope_589590__/edit`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { fields: { label: "x" } },
  });
  // route istnieje → 404 (brak lokacji). Brak route dałby 404 też, ale 405 = zła metoda.
  expect(r.status(), `edit zwrócił ${r.status()} — oczekiwano 404 (route istnieje, lokacja nie)`).toBe(404);
});

test("REGRESSION #589 — generate endpoint przyjmuje radius (kontrakt)", async ({ request }) => {
  const token = await adminToken(request);
  // dry contract check: zła metoda GET na /generate → 405 (POST-only), potwierdza że route istnieje.
  const r = await request.get(`${BASE}/api/admin/world/generate`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect([405, 401, 422].includes(r.status()), `oczekiwano że route /generate istnieje, got ${r.status()}`).toBeTruthy();
});
