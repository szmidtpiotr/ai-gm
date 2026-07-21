/**
 * REGRESSION #1528 (Fala 0 sprzatania lokacji) — kanon mapy swiata musi byc czysty:
 * zadnych wiazan do obozowisk/rekordow testowych, zadnych wiazan do lokacji, ktore
 * nie istnieja lub sa nieaktywne, a nazwany heks osady wiaze swoja kanoniczna lokacje.
 *
 * Acceptance: heks (23,23) "Karczma Pod Trzema Krukami" wskazuje `trzech_krukow`
 * (nie wygenerowany duplikat `trzech_krukow_2`), a mapa nie zawiera smieci runtime.
 */
const { test, expect } = require("@playwright/test");

const JUNK = /^(temp_camp_|parent_immut|test_|sbx_|scn_)/i;

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(resp.ok(), "dev-login nie odpowiada 200").toBeTruthy();
  const { token } = await resp.json();
  expect(token, "brak tokenu admina").toBeTruthy();
  return token;
}

async function fetchHexes(page, region) {
  const token = await adminToken(page);
  const r = await page.request.get(`/api/admin/world/map?region=${region}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `/api/admin/world/map?region=${region} nie odpowiada 200 (#1528)`).toBeTruthy();
  const body = await r.json();
  return body.hexes || [];
}

test("REGRESSION #1528 — kanon mapy Kresow bez smieci runtime", async ({ page }) => {
  const hexes = await fetchHexes(page, "kresy");
  expect(hexes.length, "mapa Kresow pusta").toBeGreaterThan(100);

  const junk = hexes.filter((h) => h.location_key && JUNK.test(h.location_key));
  expect(
    junk.map((h) => `(${h.q},${h.r})->${h.location_key}`).join(", "),
    "smieciowe wiazania w kanonie mapy (#1528)"
  ).toBe("");
});

test("REGRESSION #1528 — nazwany heks osady wiaze swoja kanoniczna lokacje", async ({ page }) => {
  const hexes = await fetchHexes(page, "kresy");
  const karczma = hexes.find((h) => (h.label || "").trim() === "Karczma Pod Trzema Krukami");

  expect(karczma, "brak heksa 'Karczma Pod Trzema Krukami' na mapie").toBeTruthy();
  expect(
    karczma.location_key,
    `heks (${karczma?.q},${karczma?.r}) wiaze duplikat zamiast kanonicznej karczmy (#1528)`
  ).toBe("trzech_krukow");
});

test("REGRESSION #1528 — kazde wiazanie wskazuje istniejaca lokacje", async ({ page }) => {
  const token = await adminToken(page);
  const hexes = await fetchHexes(page, "kresy");
  const linked = hexes.filter((h) => h.location_key);
  expect(linked.length, "Kresy stracily wszystkie wiazania").toBeGreaterThan(5);

  // Punktowo per klucz — lista /api/locations jest paginowana, wiec sprawdzenie
  // przez zbior wszystkich lokacji dawaloby falszywe alarmy.
  const dangling = [];
  for (const h of linked) {
    const r = await page.request.get(`/api/locations/${encodeURIComponent(h.location_key)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok()) dangling.push(`(${h.q},${h.r})->${h.location_key} [HTTP ${r.status()}]`);
  }

  expect(
    dangling.join(", "),
    "heksy wskazujace lokacje, ktorej nie da sie pobrac (#1528)"
  ).toBe("");
});
