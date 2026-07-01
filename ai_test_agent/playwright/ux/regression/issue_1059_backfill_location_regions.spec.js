/**
 * REGRESSION #1059 (RM) — Wszystkie aktywne lokacje mają przypisany region po backfillu.
 * Acceptance: GET /api/locations zwraca 0 lokacji z region=null.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "admin login must succeed (#1059)").toBeTruthy();
  const body = await login.json();
  const token = body.token || body.access_token;
  expect(token, "login must return token (#1059)").toBeTruthy();
  return token;
}

test("REGRESSION #1059 — brak aktywnych lokacji z region=null po backfillu", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const r = await page.request.get("/api/locations", auth);
  expect(r.ok(), "GET /api/locations musi zwrócić 200 (#1059)").toBeTruthy();

  const items = await r.json();
  expect(Array.isArray(items), "odpowiedź powinna być tablicą lokacji (#1059)").toBeTruthy();

  const nullRegion = items.filter((loc) => loc.region == null || loc.region === "");
  expect(
    nullRegion.length,
    `Znaleziono ${nullRegion.length} lokacji bez regionu: ${nullRegion.slice(0, 3).map((l) => l.key).join(", ")} (#1059)`
  ).toBe(0);
});
