/**
 * REGRESSION #625 (HI2) — sekcja „Bohaterowie": wzbogacony odczyt listy hero-first.
 * Lista GET /api/admin/characters musi pokazywać też bohaterów IDLE (LEFT JOIN) oraz
 * dołączać kolumny archetype/level/status/hp/max_hp/owner_name dla tabeli Inspektora.
 * Acceptance: admin (token) dostaje wzbogaconą listę z kompletem kolumn; bez tokenu → 401/403.
 * Modal/UI weryfikowany ręcznie + przez /game-screen (frontend tylko-szkielet w HI2).
 */
const { test, expect } = require("@playwright/test");

const REQUIRED_COLS = [
  "id", "name", "campaign_id", "user_id", "campaign_title",
  "status", "owner_name", "archetype", "level", "hp", "max_hp",
];

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200 (#625)").toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #625 — lista bohaterów ma wzbogacone kolumny", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };

  const list = await page.request.get("/api/admin/characters", { headers });
  expect(list.ok(), "lista bohaterów nie odpowiada 200 (#625)").toBeTruthy();
  const items = (await list.json()).items || [];
  expect(items.length, "brak bohaterów do wylistowania (#625)").toBeGreaterThan(0);

  for (const col of REQUIRED_COLS) {
    expect(col in items[0], `lista bez kolumny ${col} (#625)`).toBeTruthy();
  }
});

test("REGRESSION #625 — bohaterowie IDLE (bez kampanii) są na liście", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };

  const items = ((await (await page.request.get("/api/admin/characters", { headers })).json()).items) || [];
  // Hero-first: bohater idle ma campaign_id === null i nadal MUSI być widoczny (LEFT JOIN).
  const idle = items.filter(h => h.campaign_id == null);
  // Jeśli akurat brak idle w DB — test nie może fałszywie przejść: sprawdź że LEFT JOIN nie odcina
  // (każdy element z campaign_id null ma poprawnie campaign_title null, nie wyrzucony z wyniku).
  for (const h of idle) {
    expect(h.campaign_title == null, "idle bohater powinien mieć puste campaign_title (#625)").toBeTruthy();
    expect("status" in h, "idle bohater bez pola status (#625)").toBeTruthy();
  }
  // Asercja dodatnia: na koncie Demo istnieją idle bohaterowie (uwolnieni hero-first).
  expect(idle.length, "LEFT JOIN nie zwraca idle bohaterów (#625)").toBeGreaterThan(0);
});

test("REGRESSION #625 — lista wymaga tokenu admina", async ({ page }) => {
  const r = await page.request.get("/api/admin/characters");
  expect([401, 403].includes(r.status()), "lista bez tokenu musi dać 401/403 (#625)").toBeTruthy();
});
