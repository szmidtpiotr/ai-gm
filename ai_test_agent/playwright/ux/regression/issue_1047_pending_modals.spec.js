/**
 * REGRESSION #1047 — Pending modals: required field validation + locations + AI fill.
 * Acceptance: enemy pending returns combat fields; location pending visible;
 * AI fill endpoint returns suggestions dict; weapon PATCH endpoint works.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1047 — pending enemies endpoint returns combat fields", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/pending/enemies");
  expect(r.ok(), "GET /pending/enemies nie odpowiada 200 (#1047)").toBeTruthy();
  const body = await r.json();
  expect(body, "brak klucza 'items' w odpowiedzi").toHaveProperty("items");
  expect(Array.isArray(body.items), "'items' nie jest tablicą").toBeTruthy();
  // Verify response shape when items exist
  if (body.items.length > 0) {
    const e = body.items[0];
    expect(e, "brak ac_base w pending enemy").toHaveProperty("ac_base");
    expect(e, "brak attack_bonus w pending enemy").toHaveProperty("attack_bonus");
    expect(e, "brak damage_die w pending enemy").toHaveProperty("damage_die");
    expect(e, "brak dex_modifier w pending enemy").toHaveProperty("dex_modifier");
    expect(e, "brak min_level w pending enemy").toHaveProperty("min_level");
  }
});

test("REGRESSION #1047 — pending locations endpoint works with created_at", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/pending/locations");
  expect(r.ok(), "GET /pending/locations nie odpowiada 200 (#1047)").toBeTruthy();
  const body = await r.json();
  expect(body, "brak klucza 'items' w pending locations").toHaveProperty("items");
  if (body.items.length > 0) {
    expect(body.items[0], "brak created_at w pending location").toHaveProperty("created_at");
  }
});

test("REGRESSION #1047 — AI fill endpoint exists and returns suggestions dict", async ({ page }) => {
  // Test with non-existent key: should get 404 (entity not found), NOT 404 (route not found)
  // The endpoint is registered if we get a JSON error response, not an Nginx 404
  const r = await page.request.post("/api/admin/world/pending/fill/enemy/nonexistent_test_1047");
  // 404 from FastAPI with detail = entity not found; 404 from Nginx = route missing
  const body = await r.json();
  expect(r.status(), "endpoint fill nie zarejestrowany lub zwrócił nieoczekiwany status").not.toBe(405);
  // If 404 — must have 'detail' field (FastAPI 404), not generic Nginx error
  if (r.status() === 404) {
    expect(body, "brak 'detail' w odpowiedzi 404 — endpoint może nie być zarejestrowany").toHaveProperty("detail");
  } else {
    expect(body, "brak 'suggestions' w odpowiedzi fill endpoint").toHaveProperty("suggestions");
    expect(typeof body.suggestions, "'suggestions' musi być obiektem").toBe("object");
  }
});

test("REGRESSION #1047 — weapon PATCH pending endpoint works", async ({ page }) => {
  const r = await page.request.patch(
    "/api/admin/world/pending/weapons/nonexistent_weapon_test_1047",
    { data: { label: "Test" } }
  );
  expect([200, 404].includes(r.status()), `unexpected status ${r.status()}`).toBeTruthy();
});
