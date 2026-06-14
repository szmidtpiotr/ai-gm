/**
 * REGRESSION #588 + #591 — Admin tables: multi-select + column resize/filter.
 * #588: Kampanie multi-select działa (window.rowCheck/toggleAll zdefiniowane → pasek zaznaczenia).
 * #591: shared/table.js dodaje resize grip + wiersz filtrów per-kolumna do każdej data-table.
 */
const { test, expect } = require("@playwright/test");

async function adminLogin(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
}

test("REGRESSION #588 — Kampanie: rowCheck/toggleAll zdefiniowane + pasek zaznaczenia", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#campaigns");
  await page.waitForTimeout(1500);

  // helpery globalne dostępne (były undefined → onchange rzucał błąd)
  const defined = await page.evaluate(
    () => typeof window.rowCheck === "function" && typeof window.toggleAll === "function"
  );
  expect(defined, "window.rowCheck/toggleAll muszą być zdefiniowane (#588)").toBeTruthy();

  // klik master checkbox → pasek zaznaczenia (#camp-sel-bar) staje się widoczny
  const master = page.locator("#camp-check-all");
  if (await master.count()) {
    await master.check();
    await expect(page.locator("#camp-sel-bar")).toHaveClass(/visible/);
  }
});

test("REGRESSION #591 — data-table dostaje wiersz filtrów + resize grip", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#campaigns");
  await page.waitForTimeout(1500);

  const table = page.locator("table.data-table").first();
  await expect(table, "brak data-table w sekcji").toBeVisible();

  // #591: enhanceTable wstrzykuje wiersz filtrów per-kolumna jako DROPDOWNY wartości
  await expect(table.locator("thead tr.col-filter-row"), "brak wiersza filtrów (#591)").toHaveCount(1);
  await expect(table.locator(".col-filter-select").first(), "brak dropdownów filtra (#591)").toBeVisible();

  // #591: resize grip na nagłówkach
  const grips = await table.locator(".col-resize-grip").count();
  expect(grips, "brak uchwytów resize na kolumnach (#591)").toBeGreaterThan(0);
});
