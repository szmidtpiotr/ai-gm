/**
 * REGRESSION #1131 (PT-D4b) — Forge: autoring AI encounterów (FK-enum, anty-halucynacja).
 * Acceptance: schema zwraca realne enumy FK; zapis z wymyślonym enemy_key odrzucony (400);
 * zapis z realnym enemy_key przechodzi (200 + klucz w katalogu).
 */
const { test, expect } = require("@playwright/test");

// Dev admin token via demo/demo → dev-login (jak modular admin login).
async function adminToken(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił tokenu (#1131)").toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #1131 — schema combat zwraca enum enemy_key z katalogu", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get("/api/admin/forge/encounters/schema?kind=combat", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "schema combat nie odpowiada 200 (#1131)").toBeTruthy();
  const body = await r.json();
  expect(body.kind).toBe("combat");
  expect(Array.isArray(body.enums.enemy_key)).toBeTruthy();
  expect(body.enums.enemy_key.length, "enum enemy_key pusty (#1131)").toBeGreaterThan(0);
  // free-text tylko otoczka
  const enemiesField = body.fields.find((f) => f.name === "enemies");
  expect(enemiesField && enemiesField.enum_ref).toBe("enemy_key");
});

test("REGRESSION #1131 — schema social zwraca enum skill", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get("/api/admin/forge/encounters/schema?kind=social", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  expect(body.enums.skill.length, "enum skill pusty (#1131)").toBeGreaterThan(0);
});

test("REGRESSION #1131 — zapis z wymyślonym enemy_key odrzucony (400)", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.post("/api/admin/forge/encounters/save", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      draft: {
        kind: "combat",
        title: "PW zmyslony 1131",
        biome: "forest",
        payload: { enemies: [{ enemy_key: "smok_widmo_1131", count: 1 }] },
      },
    },
  });
  expect(r.status(), "wymyślony klucz FK powinien dać 400 (#1131)").toBe(400);
});

test("REGRESSION #1131 — zapis z realnym enemy_key przechodzi i trafia do katalogu", async ({ request }) => {
  const token = await adminToken(request);
  // pobierz realny klucz ze schematu
  const sch = await (
    await request.get("/api/admin/forge/encounters/schema?kind=combat", {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).json();
  const realKey = sch.enums.enemy_key[0].key;

  const save = await request.post("/api/admin/forge/encounters/save", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      draft: {
        kind: "combat",
        title: "PW happy 1131",
        biome: "forest",
        payload: { enemies: [{ enemy_key: realKey, count: 1 }], scene_setup: "x" },
      },
    },
  });
  expect(save.ok(), "zapis z realnym kluczem powinien przejść (#1131)").toBeTruthy();
  const body = await save.json();
  expect(body.ok).toBeTruthy();
  expect(typeof body.key).toBe("string");
});
