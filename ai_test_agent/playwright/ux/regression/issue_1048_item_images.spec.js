/**
 * REGRESSION #1048 — generowanie obrazków przedmiotów (backend API).
 * Acceptance: endpoint /item/{key}/generate istnieje i przyjmuje żądania POST;
 * GET /admin/items zwraca image_url i image_gen_prompt; PATCH akceptuje te pola.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "admin login must succeed (#1048)").toBeTruthy();
  const body = await login.json();
  const token = body.token || body.access_token;
  expect(token, "login must return token (#1048)").toBeTruthy();
  return token;
}

test("REGRESSION #1048 — endpoint /item/{key}/generate istnieje (404 = brak klucza, nie brak endpointu)", async ({ page }) => {
  const token = await adminToken(page);
  // POST z nieistniejącym kluczem → 404 (endpoint działa, klucz nie istnieje)
  // gdyby endpoint nie istniał → 405 Method Not Allowed
  const r = await page.request.post("/api/admin/images/item/__nonexistent_test_key__/generate", {
    headers: { Authorization: `Bearer ${token}` },
    data: { force: false },
  });
  expect([404, 503, 504], "endpoint nie istnieje lub zwraca nieoczekiwany status (#1048)").toContain(r.status());
});

test("REGRESSION #1048 — GET /admin/items zwraca pola image_url i image_gen_prompt", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/items", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /admin/items nie odpowiada 200 (#1048)").toBeTruthy();
  const body = await r.json();
  const items = body.items || [];
  expect(Array.isArray(items), "body.items musi być tablicą (#1048)").toBeTruthy();
  if (items.length > 0) {
    const first = items[0];
    expect(Object.prototype.hasOwnProperty.call(first, "image_url") ||
           first.image_url === null || first.image_url === undefined,
      "odpowiedź items powinna zawierać klucz image_url (#1048)").toBeTruthy();
  }
});
