/**
 * REGRESSION #407 (FADM-P5) — Port sekcji map → modularny admin/.
 * Acceptance: /admin/#map renderuje sekcję z 5 tabami (builder/generate/locations/terrain/review),
 * domyślny tab builder rysuje SVG świata, tab Lokacje ładuje drzewo z API, tab Teren ładuje
 * konfigurację, admin3 żyje po ANTY-GROB.
 */
const { test, expect } = require("@playwright/test");

async function adminLogin(page) {
  await page.goto("/admin3/");
  const overlay = page.locator("#login-overlay");
  if (await overlay.isVisible({ timeout: 5000 }).catch(() => false)) {
    await page.fill("#login-user", "demo");
    await page.fill("#login-pass", "demo");
    await page.click("#login-submit");
    await page.waitForSelector("#login-overlay", { state: "hidden", timeout: 10000 });
  }
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

  // _loadBuilder pobiera /api/admin/world/map i rysuje <polygon class="whx"> per heks.
  // Świat DEV ma wygenerowane heksy → oczekujemy >0 poligonów po dorysowaniu.
  await expect
    .poll(async () => await page.locator("#wb-svg polygon.whx").count(), { timeout: 15000 })
    .toBeGreaterThan(0);

  // Paleta terenu (przyciski typów) też się wypełnia
  await expect
    .poll(async () => await page.locator("#wb-palette .wb-pb").count(), { timeout: 8000 })
    .toBeGreaterThan(0);
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

test("REGRESSION #407 — admin3 nadal żyje po ANTY-GROB", async ({ page }) => {
  await adminLogin(page);
  await expect(page).toHaveURL(/\/admin3\//);
});
