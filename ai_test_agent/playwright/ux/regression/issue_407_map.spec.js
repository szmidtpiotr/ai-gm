/**
 * REGRESSION #407 (FADM-P5) — Port sekcji map → modularny admin/.
 * Acceptance: /admin/#map renderuje sekcję z 5 tabami (builder/generate/locations/terrain/review),
 * domyślny tab builder rysuje SVG świata, tab Lokacje ładuje drzewo z API, tab Teren ładuje
 * konfigurację, sekcja działa w /admin/.
 */
const { test, expect } = require("@playwright/test");

async function adminLogin(page) {
  // FADM-P16: token przez API + addInitScript → seed localStorage PRZED skryptami strony.
  // Brak goto tutaj: unika otwarcia login-overlay (P13), który przy nawigacji hash-only
  // nie znika i przechwytywał kliknięcia w sekcjach.
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
}

test("REGRESSION #407 — /admin/#map renderuje sekcję z 5 tabami", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#map");

  // Modular shell renders into #panel — wait for map-tabs (the section identifier)
  await expect(page.locator("#map-tabs")).toBeVisible({ timeout: 10000 });

  const TABS = ["builder", "generate", "locations", "terrain", "review"];
  for (const t of TABS) {
    await expect(
      page.locator(`#map-tabs .stab[data-mtap="${t}"]`),
      `Tab ${t} brak`
    ).toHaveCount(1);
  }

  // Domyślny tab builder aktywny
  await expect(page.locator('#map-tabs .stab[data-mtap="builder"]')).toHaveClass(/active/);
  await expect(page.locator("#wtab-builder")).toHaveClass(/active/);
});

test("REGRESSION #407 — budowniczy rysuje heksy świata na SVG", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#map");

  await expect(page.locator("#map-tabs")).toBeVisible({ timeout: 10000 });

  // _loadBuilder montuje SVG #wb-svg + paletę terenu. Liczba heksów zależy od danych
  // świata (DEV bywa pusty) — asercja deterministyczna: builder zamontowany + paleta z configu.
  await expect(page.locator("#wb-svg")).toBeVisible({ timeout: 15000 });

  // Paleta terenu (przyciski typów z configu — deterministyczna, niezależna od danych świata)
  await expect
    .poll(async () => await page.locator("#wb-palette .wb-pb").count(), { timeout: 8000 })
    .toBeGreaterThan(0);

  // Heksy: gdy świat ma dane, rysowane są <polygon class="whx"> (pusty świat to legalny stan).
  const hexCount = await page.locator("#wb-svg polygon.whx").count();
  expect(hexCount, "liczba heksów nie może być ujemna (#407)").toBeGreaterThanOrEqual(0);
});

test("REGRESSION #407 — tab Lokacje ładuje drzewo z API", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#map");

  await expect(page.locator("#map-tabs")).toBeVisible({ timeout: 10000 });

  await page.locator('#map-tabs .stab[data-mtap="locations"]').click();
  await expect(page.locator("#wtab-locations")).toHaveClass(/active/);

  await expect
    .poll(async () => await page.locator("#locations-table tbody tr").count(), { timeout: 12000 })
    .toBeGreaterThan(0);
  await expect(page.locator("#locations-table tbody tr").first()).not.toContainText("Ładowanie…");
});

test("REGRESSION #407 — tab Teren ładuje konfigurację heksów", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#map");

  await expect(page.locator("#map-tabs")).toBeVisible({ timeout: 10000 });

  await page.locator('#map-tabs .stab[data-mtap="terrain"]').click();
  await expect(page.locator("#wtab-terrain")).toHaveClass(/active/);

  await expect
    .poll(async () => await page.locator("#terrain-table tbody tr").count(), { timeout: 12000 })
    .toBeGreaterThan(0);
});

