/**
 * REGRESSION #408 (FADM-P6) — Port sekcji campaigns → modularny admin/.
 * Acceptance: /admin/#campaigns renderuje tabelę kampanii z danymi z API,
 * modal kampanii otwiera się i pokazuje 8 tabów, admin3 żyje po ANTY-GROB,
 * klik campaigns w admin3 przekierowuje do /admin/#campaigns.
 */
const { test, expect } = require("@playwright/test");

async function adminLogin(page) {
  await page.goto("/api/health");
  await page.evaluate(() => localStorage.removeItem('aigm_admin_token'));
  // #forge is not in PORTED set — requestAnimationFrame won't redirect, login overlay stays.
  await page.goto("/admin3/#forge");
  await page.waitForSelector("#login-overlay.open", { timeout: 15000 });
  await page.fill("#login-user", "demo");
  await page.fill("#login-pass", "demo");
  await page.click("#login-submit");
  await page.locator("#login-overlay").waitFor({ state: "hidden", timeout: 20000 });
}

test("REGRESSION #408 — /admin/#campaigns renderuje sekcję z tabelą kampanii", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#campaigns");

  // Modular shell renders into #panel — wait for campaigns-table
  await expect(page.locator("#campaigns-table")).toBeVisible({ timeout: 10000 });

  // Table must have thead with expected columns
  await expect(page.locator("#campaigns-table thead")).toBeVisible();

  // Filter chips present
  const chips = page.locator("#panel .filter-group .chip");
  await expect(chips).toHaveCount(5); // Wszystkie / Aktywne / W walce / Zakończone / Usunięte

  // View toggle buttons present
  await expect(page.locator("#camp-view-toggle")).toBeVisible();
});

test("REGRESSION #408 — tabela kampanii ładuje dane z API", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#campaigns");

  await expect(page.locator("#campaigns-table")).toBeVisible({ timeout: 10000 });

  // tbody should get real rows (API returns campaign list)
  await expect
    .poll(async () => {
      const rows = await page.locator("#campaigns-table tbody tr").count();
      const loading = await page.locator("#campaigns-table tbody tr td").filter({ hasText: "Ładowanie…" }).count();
      return rows > 0 && loading === 0;
    }, { timeout: 15000 })
    .toBeTruthy();
});

test("REGRESSION #408 — modal kampanii otwiera się z 8 tabami", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#campaigns");

  await expect(page.locator("#campaigns-table")).toBeVisible({ timeout: 10000 });

  // Wait for real data rows
  await expect
    .poll(async () => await page.locator("#campaigns-table tbody tr td.td-sticky").count(), { timeout: 12000 })
    .toBeGreaterThan(0);

  // Click first campaign's modal button (⊞)
  const firstModalBtn = page.locator("#campaigns-table tbody tr .btn-icon").first();
  await firstModalBtn.click();

  // Modal opens
  await expect(page.locator("#camp-modal-box")).toBeVisible({ timeout: 8000 });

  // 8 tabs: overview, plan, turns, map, npcs, workshop, world, inspector
  const TABS = ["overview", "plan", "turns", "map", "npcs", "workshop", "world", "inspector"];
  for (const t of TABS) {
    await expect(
      page.locator(`[data-ctab="${t}"]`),
      `Tab ${t} brak w modalu`
    ).toHaveCount(1);
  }

  // Overview tab active by default
  await expect(page.locator('[data-ctab="overview"]')).toHaveClass(/active/);
});

test("REGRESSION #408 — admin3 nadal żyje po ANTY-GROB", async ({ page }) => {
  const r = await page.request.get("/admin3/");
  expect(r.ok(), "/admin3/ musi nadal działać podczas migracji (#408)").toBeTruthy();
});

test("REGRESSION #408 — klik campaigns w admin3 przekierowuje do /admin/#campaigns", async ({ page }) => {
  await adminLogin(page);
  await page.locator('aside.sidebar button.nav-item[data-section="campaigns"]').first().click();
  await expect(page).toHaveURL(/\/admin\/#campaigns$/, { timeout: 15000 });
});
