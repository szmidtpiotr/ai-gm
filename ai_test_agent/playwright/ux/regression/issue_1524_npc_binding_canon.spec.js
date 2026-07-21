/**
 * REGRESSION #1524 (Fala 1 sprzatania lokacji) — obsada NPC ma jedno zrodlo prawdy.
 * Sprawdza na zywej bazie: gospodarz siedzi w sub-lokacji (makro-hub pusty),
 * `npc_keys` jest wylacznie lustrem przypisan, a gospoda "Pod Zlamanym Rogiem"
 * stoi w kanonie z wlasna karczmarka.
 *
 * Acceptance: heks (24,13) wskazuje `gospoda_pod_zlamanym_rogiem`, jej izba ma
 * gospodarza, a zadne makro z sub-lokacjami nie trzyma NPC.
 */
const { test, expect } = require("@playwright/test");

const INN = "gospoda_pod_zlamanym_rogiem";
const INN_HALL = "zlamany_rog_izba";

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(resp.ok(), "dev-login nie odpowiada 200").toBeTruthy();
  const { token } = await resp.json();
  expect(token, "brak tokenu admina").toBeTruthy();
  return token;
}

async function getJSON(page, url, token) {
  const r = await page.request.get(url, { headers: { Authorization: `Bearer ${token}` } });
  expect(r.ok(), `${url} nie odpowiada 200 (#1524)`).toBeTruthy();
  return r.json();
}

test("REGRESSION #1524 — gospoda Pod Zlamanym Rogiem w kanonie, gospodarz w izbie", async ({ page }) => {
  const token = await adminToken(page);

  const inn = await getJSON(page, `/api/locations/${INN}`, token);
  expect(inn.location_type, "gospoda musi byc makro").toBe("macro");
  expect(inn.canonical, "gospoda musi byc kanoniczna").toBeTruthy();
  expect(inn.npc_keys, "makro-hub musi byc pusty (#1524 decyzja 2)").toEqual([]);

  const hall = await getJSON(page, `/api/locations/${INN_HALL}`, token);
  expect(hall.parent_key, "izba musi wisiec pod gospoda").toBe(INN);
  expect(hall.npc_keys.length, "izba szynkowa bez gospodarza").toBeGreaterThan(0);

  // Heks (24,13) nosi nazwe gospody i musi na nia wskazywac (fala 0 zostawila go pustym).
  const map = await getJSON(page, "/api/admin/world/map?region=kresy", token);
  const hex = (map.hexes || []).find((h) => h.q === 24 && h.r === 13);
  expect(hex, "brak heksa (24,13) w kanonie Kresow").toBeTruthy();
  expect(hex.location_key, "heks (24,13) nie wskazuje gospody (#1524)").toBe(INN);
});

test("REGRESSION #1524 — zaden makro-hub z sub-lokacjami nie trzyma NPC", async ({ page }) => {
  const token = await adminToken(page);
  const body = await getJSON(page, "/api/locations?limit=1000", token);
  const rows = body.data || body.items || body.locations || body;
  expect(Array.isArray(rows), "lista lokacji ma nieoczekiwany ksztalt").toBeTruthy();

  const parents = new Set(rows.map((r) => r.parent_key).filter(Boolean));
  const offenders = rows
    .filter((r) => r.location_type === "macro" && parents.has(r.key))
    .filter((r) => (r.npc_keys || []).length > 0)
    .map((r) => `${r.key}:${(r.npc_keys || []).join("+")}`);

  expect(offenders.join(", "), "gospodarze wisza na makro-hubie zamiast w sub-lokacji (#1524)").toBe("");
});
