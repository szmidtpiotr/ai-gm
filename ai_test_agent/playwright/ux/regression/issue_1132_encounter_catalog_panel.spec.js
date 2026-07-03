/**
 * REGRESSION #1132 (PT-D4c) — Kuźnia: panel Katalog encounterów (lista/filtr/zapis/delete).
 * Acceptance: GET /catalog listuje rekordy z metadanymi panelu (kind/times_used/quality_rating/title);
 * filtr kind zawęża; zapis draftu (INSERT) trafia do katalogu; DELETE usuwa rekord.
 */
const { test, expect } = require("@playwright/test");

// Dev admin token via demo/demo → dev-login (jak modular admin login).
async function adminToken(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił tokenu (#1132)").toBeTruthy();
  return (await r.json()).token;
}

test("REGRESSION #1132 — /catalog listuje encountery z metadanymi panelu", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get("/api/admin/forge/encounters/catalog", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "/catalog nie odpowiada 200 (#1132)").toBeTruthy();
  const body = await r.json();
  expect(body.ok).toBeTruthy();
  expect(Array.isArray(body.encounters)).toBeTruthy();
  expect(body.count, "katalog pusty — seed nie wgrany? (#1132)").toBeGreaterThan(0);
  const e = body.encounters[0];
  // metadane wymagane przez karty panelu
  for (const f of ["key", "kind", "title", "times_used", "quality_rating"]) {
    expect(e[f] !== undefined, `brak pola '${f}' w rekordzie katalogu (#1132)`).toBeTruthy();
  }
});

test("REGRESSION #1132 — filtr kind zawęża listę", async ({ request }) => {
  const token = await adminToken(request);
  const combat = await (
    await request.get("/api/admin/forge/encounters/catalog?kind=combat", {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).json();
  expect(combat.encounters.every((e) => e.kind === "combat"),
    "filtr kind=combat zwraca inne kind (#1132)").toBeTruthy();
  const social = await (
    await request.get("/api/admin/forge/encounters/catalog?kind=social", {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).json();
  expect(social.encounters.every((e) => e.kind === "social"),
    "filtr kind=social zwraca inne kind (#1132)").toBeTruthy();
});

test("REGRESSION #1132 — zapis draftu trafia do katalogu, potem DELETE go usuwa", async ({ request }) => {
  const token = await adminToken(request);
  const H = { Authorization: `Bearer ${token}` };
  // realny enemy_key ze schematu (anty-halucynacja)
  const sch = await (
    await request.get("/api/admin/forge/encounters/schema?kind=combat", { headers: H })
  ).json();
  const realKey = sch.enums.enemy_key[0].key;

  const save = await request.post("/api/admin/forge/encounters/save", {
    headers: H,
    data: {
      draft: {
        kind: "combat", biome: "forest",
        payload: { title: "PW katalog 1132", enemies: [{ enemy_key: realKey, count: 1 }] },
      },
    },
  });
  expect(save.ok(), "zapis draftu nie przeszedł (#1132)").toBeTruthy();
  const key = (await save.json()).key;

  // rekord widoczny na liście
  const list = await (
    await request.get("/api/admin/forge/encounters/catalog?kind=combat", { headers: H })
  ).json();
  expect(list.encounters.some((e) => e.key === key),
    "zapisany encounter nie pojawił się w katalogu (#1132)").toBeTruthy();

  // DELETE usuwa
  const del = await request.delete(`/api/admin/forge/encounters/catalog/${encodeURIComponent(key)}`, { headers: H });
  expect(del.ok(), "DELETE nie zwrócił 200 (#1132)").toBeTruthy();
  const after = await (
    await request.get("/api/admin/forge/encounters/catalog?kind=combat", { headers: H })
  ).json();
  expect(after.encounters.some((e) => e.key === key),
    "encounter nadal w katalogu po DELETE (#1132)").toBeFalsy();

  // usunięcie nieistniejącego → 404
  const del2 = await request.delete(`/api/admin/forge/encounters/catalog/${encodeURIComponent(key)}`, { headers: H });
  expect(del2.status(), "DELETE nieistniejącego powinien dać 404 (#1132)").toBe(404);
});
