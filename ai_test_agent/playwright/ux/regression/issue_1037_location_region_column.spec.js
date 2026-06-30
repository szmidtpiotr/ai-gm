/**
 * REGRESSION #1037 (RM8) — Lokacje API zwraca pole region; tabela admina ma kolumnę Kraina.
 * Acceptance: /api/locations/admin/locations zawiera region w każdym wierszu; filtr dropdown widoczny w UI.
 */
const { test, expect } = require("@playwright/test");

async function getAdminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login failed (#1037)").toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #1037 — admin/locations API zwraca pole region", async ({ page }) => {
  const token = await getAdminToken(page);
  const r = await page.request.get("/api/locations/admin/locations?active_only=0", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "endpoint admin/locations nie odpowiada 200").toBeTruthy();
  const body = await r.json();
  const items = Array.isArray(body) ? body : (body.items || []);
  expect(items.length, "brak lokacji w odpowiedzi API").toBeGreaterThan(0);
  const first = items[0];
  expect(Object.prototype.hasOwnProperty.call(first, "region"),
    `Pole 'region' brakuje w odpowiedzi API. Pola: ${Object.keys(first).join(", ")}`
  ).toBeTruthy();
});

test("REGRESSION #1037 — lokacje z krainy siwe_granie mają region set", async ({ page }) => {
  const token = await getAdminToken(page);
  const r = await page.request.get("/api/locations/admin/locations?active_only=0", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const items = await r.json();
  const arr = Array.isArray(items) ? items : (items.items || []);
  const siweGranie = arr.filter(l => l.region === "siwe_granie");
  expect(siweGranie.length, "oczekiwano ≥1 lokacji z krainy siwe_granie").toBeGreaterThan(0);
});

test("REGRESSION #1037 — lokacje bez krainy mają region=null (nie undefined)", async ({ page }) => {
  const token = await getAdminToken(page);
  const r = await page.request.get("/api/locations/admin/locations?active_only=0", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const items = await r.json();
  const arr = Array.isArray(items) ? items : (items.items || []);
  const nullRegion = arr.filter(l => l.region === null);
  expect(nullRegion.length, "oczekiwano lokacji z region=null (floating/runtime)").toBeGreaterThan(0);
  for (const loc of nullRegion.slice(0, 5)) {
    expect(loc.region).toBeNull();
    expect(Object.prototype.hasOwnProperty.call(loc, "region"),
      `region key missing for loc ${loc.key}`
    ).toBeTruthy();
  }
});
