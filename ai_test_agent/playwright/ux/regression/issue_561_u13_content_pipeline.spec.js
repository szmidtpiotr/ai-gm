/**
 * REGRESSION #561 (U13) — Content pipeline: integralność treści po jednej ścieżce walidacji.
 * Acceptance: GET /api/admin/db-lint (ta sama warstwa, którą seed-lint U13 uruchamia na seedach)
 * zwraca raport bez ERRORS na żywej bazie DEV — exit_code <= 1 (0=czysto / 1=warnings dozwolone).
 * Egzekwuje też autoryzację: bez tokenu = 401.
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

test("REGRESSION #561 U13 — db-lint wymaga autoryzacji (401 bez tokenu)", async ({ request }) => {
  const r = await request.get(`${BASE}/api/admin/db-lint`);
  expect(r.status(), "db-lint bez tokenu powinien dać 401").toBe(401);
});

test("REGRESSION #561 U13 — żywa baza DEV bez błędów integralności (exit_code <= 1)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get(`${BASE}/api/admin/db-lint`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `db-lint nie odpowiada 200 (#561): ${r.status()}`).toBeTruthy();
  const body = await r.json();

  // Kontrakt raportu (U12 surface, której pilnuje pipeline U13).
  expect(Array.isArray(body.errors), "errors musi być tablicą").toBeTruthy();
  expect(Array.isArray(body.warnings), "warnings musi być tablicą").toBeTruthy();
  expect(typeof body.exit_code, "exit_code musi być liczbą").toBe("number");

  // Pipeline U13 gwarantuje 0 ERRORS — warnings (zadania treści) są dozwolone.
  expect(body.errors.length, `nieoczekiwane ERRORY integralności: ${JSON.stringify(body.errors)}`).toBe(0);
  expect(body.exit_code, "exit_code musi być 0 lub 1 (brak errorów)").toBeLessThanOrEqual(1);
});
