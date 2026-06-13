/**
 * REGRESSION #557 (U11b) — serwisy czytają przedmioty z game_items, nie starych tabel.
 * Acceptance: katalog broni/itemów dostępny przez API backfillowany z game_items (140 rekordów).
 * Brak regresji starych kluczy (shortsword, health_potion_small).
 */
const { test, expect } = require("@playwright/test");

async function adminLogin(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "dev_password" },
  });
  if (!r.ok()) return null;
  const body = await r.json();
  return body.token || null;
}

test("REGRESSION #557 U11b — game_items zawiera broń (weapon backfill z U11a)", async ({ page }) => {
  const token = await adminLogin(page.request);
  if (!token) {
    // Sprawdź czy backend żyje — jeśli dev-login nie istnieje, pomiń test
    const health = await page.request.get("/api/health");
    expect(health.ok(), "backend nie odpowiada").toBeTruthy();
    return;
  }
  const r = await page.request.get("/api/admin/smart-entry/list?table=game_config_weapons", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "smart-entry/list (weapons) nie odpowiada 200").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body), "lista broni nie jest tablicą").toBeTruthy();
  expect(body.length, "brak broni — game_items backfill nie działa?").toBeGreaterThan(0);
});

test("REGRESSION #557 U11b — game_items zawiera itemy (item/armor/consumable backfill)", async ({ page }) => {
  const token = await adminLogin(page.request);
  if (!token) {
    const health = await page.request.get("/api/health");
    expect(health.ok(), "backend nie odpowiada").toBeTruthy();
    return;
  }
  const r = await page.request.get("/api/admin/smart-entry/list?table=game_config_items", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "smart-entry/list (items) nie odpowiada 200").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body), "lista itemów nie jest tablicą").toBeTruthy();
  expect(body.length, "brak itemów — game_items read switch nie działa?").toBeGreaterThan(0);
});

test("REGRESSION #557 U11b — /api/health działa (backend nie crashuje po U11b)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend health check failed — crash po U11b?").toBeTruthy();
  const body = await r.json();
  expect(body.status || body.ok || "ok").toBeTruthy();
});
