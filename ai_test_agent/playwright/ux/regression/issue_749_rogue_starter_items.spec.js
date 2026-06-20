/**
 * REGRESSION #749 — Rogue w kampanii otrzymuje startowe wyposażenie (shortbow, dagger, leather_armor, 10 GP).
 * Acceptance: game_config_archetypes.rogue ma starter_items_json zawierający shortbow + dagger + leather_armor,
 * oraz starter_gold_gp = 10. Weryfikacja przez /api/admin/archetypes.
 */
const { test, expect } = require("@playwright/test");

async function getAdminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const body = await resp.json();
  return body.token;
}

test("REGRESSION #749 — rogue archetype ma niepusty starter_items_json", async ({ page }) => {
  const token = await getAdminToken(page);
  const r = await page.request.get("/api/admin/archetypes", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/archetypes nie odpowiada 200 (#749)").toBeTruthy();

  const body = await r.json();
  const items = Array.isArray(body) ? body : (body.items || []);
  const rogue = items.find(a => a.key === "rogue");
  expect(rogue, "Brak rekordu 'rogue' w /api/admin/archetypes (#749)").toBeTruthy();

  const starterItems = typeof rogue.starter_items_json === "string"
    ? JSON.parse(rogue.starter_items_json)
    : (rogue.starter_items_json || []);
  expect(Array.isArray(starterItems) && starterItems.length > 0,
    "rogue.starter_items_json pusta lub brak (#749)").toBeTruthy();
});

test("REGRESSION #749 — rogue dostaje shortbow + dagger w starter_items_json", async ({ page }) => {
  const token = await getAdminToken(page);
  const r = await page.request.get("/api/admin/archetypes", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await r.json();
  const items = Array.isArray(body) ? body : (body.items || []);
  const rogue = items.find(a => a.key === "rogue");
  expect(rogue, "Brak rekordu 'rogue' (#749)").toBeTruthy();

  const starterItems = typeof rogue.starter_items_json === "string"
    ? JSON.parse(rogue.starter_items_json)
    : (rogue.starter_items_json || []);
  const weaponKeys = starterItems.filter(i => i.weapon_key).map(i => i.weapon_key);

  expect(weaponKeys, "rogue musi mieć shortbow w starter_items_json (#749)").toContain("shortbow");
  expect(weaponKeys, "rogue musi mieć dagger w starter_items_json (#749)").toContain("dagger");
});

test("REGRESSION #749 — rogue dostaje leather_armor i 10 GP startowych", async ({ page }) => {
  const token = await getAdminToken(page);
  const r = await page.request.get("/api/admin/archetypes", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await r.json();
  const items = Array.isArray(body) ? body : (body.items || []);
  const rogue = items.find(a => a.key === "rogue");
  expect(rogue, "Brak rekordu 'rogue' (#749)").toBeTruthy();

  const starterItems = typeof rogue.starter_items_json === "string"
    ? JSON.parse(rogue.starter_items_json)
    : (rogue.starter_items_json || []);
  const itemKeys = starterItems.filter(i => i.item_key).map(i => i.item_key);
  expect(itemKeys, "rogue musi mieć leather_armor w starter_items_json (#749)").toContain("leather_armor");

  expect(parseInt(rogue.starter_gold_gp || 0), "rogue.starter_gold_gp musi być 10 (#749)").toBe(10);
});
