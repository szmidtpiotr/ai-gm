/**
 * REGRESSION #1399 — detektor duplikatów treści: skan, licznik badge, kontrakt merge.
 * Acceptance: GET /api/admin/duplicates zwraca grupy per tabela (items/consumables/weapons)
 * + cross + excess; GET /count zwraca liczbę do badge; endpointy wymagają tokenu admina.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(resp.ok(), "dev-login nie działa (#1399)").toBeTruthy();
  return (await resp.json()).token;
}

test("REGRESSION #1399 — skan duplikatów zwraca grupy i licznik", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const cnt = await page.request.get("/api/admin/duplicates/count", auth);
  expect(cnt.ok(), "GET /count nie odpowiada 200 (#1399)").toBeTruthy();
  const { count } = await cnt.json();
  expect(typeof count, "count musi być liczbą").toBe("number");

  const scan = await page.request.get("/api/admin/duplicates", auth);
  expect(scan.ok(), "GET /duplicates nie odpowiada 200 (#1399)").toBeTruthy();
  const body = await scan.json();
  expect(body.tables, "brak sekcji tables").toBeTruthy();
  for (const t of ["items", "consumables", "weapons"]) {
    expect(Array.isArray(body.tables[t]), `tables.${t} musi być tablicą`).toBeTruthy();
  }
  expect(Array.isArray(body.cross), "cross musi być tablicą").toBeTruthy();
  expect(body.excess, "excess musi zgadzać się z /count").toBe(count);

  // Każda grupa ma match + rekordy z kluczem i licznikiem użyć.
  const firstGroup = Object.values(body.tables).flat()[0];
  if (firstGroup) {
    expect(["exact", "fuzzy"]).toContain(firstGroup.match);
    expect(firstGroup.records.length).toBeGreaterThan(1);
    expect(firstGroup.records[0].key).toBeTruthy();
    expect(typeof firstGroup.records[0].refs).toBe("number");
  }
});

test("REGRESSION #1399 — endpointy wymagają tokenu admina", async ({ page }) => {
  const noAuth = await page.request.get("/api/admin/duplicates/count");
  expect(noAuth.status(), "bez tokenu musi być 401 (#1399)").toBe(401);

  const token = await adminToken(page);
  const badMerge = await page.request.post("/api/admin/duplicates/merge", {
    headers: { Authorization: `Bearer ${token}` },
    data: { table: "enemies", keep_key: "x", remove_keys: ["y"] },
  });
  expect(badMerge.status(), "nieznana tabela musi dać 400 (#1399)").toBe(400);
});
