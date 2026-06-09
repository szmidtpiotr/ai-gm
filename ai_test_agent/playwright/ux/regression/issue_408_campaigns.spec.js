/**
 * REGRESSION #408 (FADM-P6) — Port sekcji campaigns → modularny admin/.
 * Acceptance: /admin/#campaigns renderuje tabelę kampanii z danymi z API,
 * modal kampanii otwiera się i pokazuje 8 tabów, sekcja działa w /admin/.
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


