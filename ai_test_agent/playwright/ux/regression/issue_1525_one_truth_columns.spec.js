/**
 * REGRESSION #1525 (Sprzątanie lokacji, fala 2) — jedna prawda na informację.
 * Acceptance: karta lokacji nie ma już duplikatów kolumn — „czy stoi na mapie"
 * liczy się z heksa (kanon), `created_by` wraca z API bez cichej podmiany
 * (`forge` = `forge`), a status recenzji ma tylko 3 legalne wartości.
 */
const { test, expect } = require("@playwright/test");

const LEGAL_REVIEW_STATUS = ["permanent", "pending_review", "discarded"];
const LEGAL_CREATED_BY = [
  "seed", "admin_manual", "admin_kreator", "gm_runtime", "forge", "auto_generated",
];

async function adminAuth(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `admin dev-login failed: ${r.status()}`).toBeTruthy();
  return { Authorization: `Bearer ${(await r.json()).token}` };
}

async function fetchLocations(page) {
  const headers = await adminAuth(page);
  const r = await page.request.get("/api/locations?limit=1000", { headers });
  expect(r.ok(), "GET /api/locations nie odpowiada 200 (#1525)").toBeTruthy();
  const body = await r.json();
  const locs = Array.isArray(body) ? body : (body.items || body.locations || []);
  expect(locs.length, "brak lokacji w odpowiedzi API").toBeGreaterThan(0);
  return locs;
}

test("REGRESSION #1525 — API lokacji nie zwraca skasowanych kolumn", async ({ page }) => {
  const locs = await fetchLocations(page);

  const withPlacement = locs.filter((l) => "placement" in l).map((l) => l.key);
  expect(withPlacement, "kolumna `placement` skasowana — nie może wracać z API").toEqual([]);

  const withAiFlag = locs.filter((l) => "ai_generated" in l).map((l) => l.key);
  expect(withAiFlag, "flaga `ai_generated` skasowana — proweniencja żyje w `created_by`").toEqual([]);
});

test("REGRESSION #1525 — `created_by` bez cichej podmiany na gm_runtime", async ({ page }) => {
  const locs = await fetchLocations(page);

  const bad = [...new Set(locs.map((l) => l.created_by).filter((v) => !LEGAL_CREATED_BY.includes(v)))];
  expect(bad, `\`created_by\` spoza enuma: ${bad.join(", ")}`).toEqual([]);

  // Przed #1525 API mapowało 'forge'/'auto_generated' na 'gm_runtime' na wyjściu.
  const sources = new Set(locs.map((l) => l.created_by));
  const smuggled = ["forge", "auto_generated"].filter((v) => sources.has(v));
  expect(smuggled.length, "żadne z realnie zapisywanych źródeł nie przechodzi przez API").toBeGreaterThan(0);
});

test("REGRESSION #1525 — tylko 3 legalne statusy recenzji", async ({ page }) => {
  const locs = await fetchLocations(page);
  const bad = [...new Set(locs.map((l) => l.review_status).filter((v) => v && !LEGAL_REVIEW_STATUS.includes(v)))];
  expect(bad, `status recenzji spoza 3 legalnych wartości: ${bad.join(", ")}`).toEqual([]);
});

test("REGRESSION #1525 — pula floating liczona z kanonu heksa", async ({ page }) => {
  const headers = await adminAuth(page);

  const mapRes = await page.request.get("/api/admin/world/locations-map", { headers });
  expect(mapRes.ok(), "GET /api/admin/world/locations-map nie odpowiada 200").toBeTruthy();
  const placed = ((await mapRes.json()).locations || []).filter((l) => l.q !== null && l.q !== undefined);
  expect(placed.length, "mapa świata nie zwraca żadnej osadzonej lokacji").toBeGreaterThan(0);

  const floatRes = await page.request.get("/api/admin/locations/floating", { headers });
  expect(floatRes.ok(), "GET /api/admin/locations/floating nie odpowiada 200").toBeTruthy();
  const floatBody = await floatRes.json();
  const floating = Array.isArray(floatBody) ? floatBody : (floatBody.locations || floatBody.items || []);

  // Kanon i pula floating to rozłączne zbiory — przed #1525 rozjeżdżały się,
  // bo pula czytała kolumnę `placement`, a mapa wskazanie z heksa.
  const placedKeys = new Set(placed.map((l) => l.key));
  const overlap = floating.map((l) => l.key).filter((k) => placedKeys.has(k));
  expect(overlap, `osadzone lokacje wróciły do puli floating: ${overlap.join(", ")}`).toEqual([]);

  // Sub-lokacja należy do mapy lokalnej huba, nie do mapy świata.
  const subsOnWorldMap = placed.filter((l) => l.location_type === "sub").map((l) => l.key);
  expect(subsOnWorldMap, `sub-lokacje osadzone na mapie świata: ${subsOnWorldMap.join(", ")}`).toEqual([]);
});
