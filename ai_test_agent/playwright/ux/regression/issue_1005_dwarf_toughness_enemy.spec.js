/**
 * REGRESSION #1005 — Twardy jak kamień: przynajmniej 1 aktywny wróg z damage_type in {poison,dark,rdzen}.
 * Acceptance: giant_spider ma damage_type='poison'; mechanic Krasnoludowej Toughness osiągalny w rozgrywce.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "admin login must succeed (#1005)").toBeTruthy();
  const body = await login.json();
  const token = body.token || body.access_token;
  expect(token, "login must return token (#1005)").toBeTruthy();
  return token;
}

test("REGRESSION #1005 — giant_spider ma damage_type=poison", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const r = await page.request.get("/api/admin/enemies", auth);
  expect(r.ok(), "endpoint /api/admin/enemies nie odpowiada 200 (#1005)").toBeTruthy();
  const enemies = await r.json();

  const list = Array.isArray(enemies) ? enemies : (enemies.enemies ?? enemies.items ?? []);
  const spider = list.find((e) => e.key === "giant_spider");
  expect(spider, "giant_spider nie istnieje w odpowiedzi API (#1005)").toBeTruthy();
  expect(spider.damage_type, "giant_spider.damage_type powinien być 'poison' (#1005)").toBe("poison");
});

test("REGRESSION #1005 — przynajmniej 1 aktywny wróg z damage_type w {poison,dark,rdzen}", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const r = await page.request.get("/api/admin/enemies", auth);
  expect(r.ok(), "endpoint /api/admin/enemies nie odpowiada 200 (#1005)").toBeTruthy();
  const enemies = await r.json();

  const list = Array.isArray(enemies) ? enemies : (enemies.enemies ?? enemies.items ?? []);
  const TOUGHNESS_TYPES = new Set(["poison", "dark", "rdzen"]);
  const qualifying = list.filter(
    (e) => e.is_active !== false && TOUGHNESS_TYPES.has(e.damage_type)
  );
  expect(
    qualifying.length,
    `Brak aktywnego wroga z damage_type in {poison,dark,rdzen}. Mechanic 'Twardy jak kamień' nieosiągalny. Znalezione: ${qualifying.map((e) => e.key).join(",") || "brak"}`
  ).toBeGreaterThanOrEqual(1);
});
