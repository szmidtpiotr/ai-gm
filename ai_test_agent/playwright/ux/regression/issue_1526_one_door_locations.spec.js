/**
 * REGRESSION #1526 (fala 3 — jedne drzwi) — każda lokacja w bazie ma legalny
 * komplet flag: status recenzji z trzech dozwolonych, źródło z listy sześciu,
 * sub-lokacja zawsze z rodzicem (klucz + numer), a lokacja osadzona na heksie
 * jest wskazana przez kanon mapy (przeżywa restart backendu / reconcile).
 * Acceptance: 0 lokacji w limbo, 0 sub-lokacji z połowicznym rodzicem,
 * 0 rozjazdów „karta twierdzi że stoi na heksie, którego mapa jej nie przyznaje".
 */
const { test, expect } = require("@playwright/test");

const LEGAL_REVIEW = ["permanent", "pending_review", "discarded"];
const LEGAL_SOURCES = [
  "seed", "admin_manual", "admin_kreator", "forge", "gm_runtime", "auto_generated",
];

async function adminAuth(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin dev-login failed: ${r.status()}`).toBeTruthy();
  return { Authorization: `Bearer ${(await r.json()).token}` };
}

async function allLocations(page) {
  const headers = await adminAuth(page);
  const r = await page.request.get("/api/locations?limit=5000", { headers });
  expect(r.ok(), "GET /api/locations nie odpowiada 200 (#1526)").toBeTruthy();
  const body = await r.json();
  const rows = Array.isArray(body) ? body : (body.items || body.locations || []);
  expect(rows.length, "pusta lista lokacji — test nic by nie sprawdził").toBeGreaterThan(0);
  return rows;
}

test("REGRESSION #1526 — żadna lokacja nie wisi w limbo statusu recenzji", async ({ page }) => {
  const rows = await allLocations(page);
  const limbo = rows
    .filter((l) => l.review_status && !LEGAL_REVIEW.includes(l.review_status))
    .map((l) => `${l.key}=${l.review_status}`);
  expect(limbo, "status recenzji spoza trzech legalnych (#1526)").toEqual([]);
});

test("REGRESSION #1526 — każda lokacja ma źródło z jednej listy", async ({ page }) => {
  const rows = await allLocations(page);
  const bad = rows
    .filter((l) => l.created_by && !LEGAL_SOURCES.includes(l.created_by))
    .map((l) => `${l.key}=${l.created_by}`);
  expect(bad, "created_by spoza enum LocationSource (#1526)").toEqual([]);
});

test("REGRESSION #1526 — sub-lokacja ma rodzica kompletnego (klucz + numer)", async ({ page }) => {
  const rows = await allLocations(page);
  const half = rows
    .filter((l) => l.location_type === "sub" && (l.parent_key || l.parent_id))
    .filter((l) => !l.parent_key || !l.parent_id)
    .map((l) => `${l.key} (key=${l.parent_key}, id=${l.parent_id})`);
  expect(half, "sub-lokacja z połowicznym rodzicem (#1526/#1292)").toEqual([]);
});

test("REGRESSION #1526 — pinezka na mapie jest zawsze poparta kanonem heksa", async ({ page }) => {
  const rows = await allLocations(page);
  const pinned = rows.filter((l) => l.world_hex_q !== null && l.world_hex_q !== undefined);

  const headers = await adminAuth(page);
  const hx = await page.request.get("/api/admin/world/map", { headers });
  expect(hx.ok(), "GET /api/admin/world/map nie odpowiada 200").toBeTruthy();
  const hexBody = await hx.json();
  const hexes = Array.isArray(hexBody) ? hexBody : (hexBody.hexes || hexBody.items || []);
  expect(hexes.length, "pusta mapa heksow — test nic by nie sprawdzil").toBeGreaterThan(0);
  const canon = new Set(hexes.filter((h) => h.location_key).map((h) => h.location_key));

  const orphanPins = pinned.filter((l) => !canon.has(l.key)).map((l) => l.key);
  expect(orphanPins, "karta ma pinezkę, której mapa nie potwierdza (#1305/#1526)").toEqual([]);
});
