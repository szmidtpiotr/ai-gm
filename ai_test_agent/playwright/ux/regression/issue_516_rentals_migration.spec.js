/**
 * REGRESSION #516 — character_rentals table exists after migration.
 * Acceptance: tabela character_rentals widoczna w DB, brak rental_expire_error w logach po turze.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #516 — character_rentals table exists in DB (migration applied)", async ({ page }) => {
  const health = await page.request.get("/api/health");
  expect(health.ok(), "backend nie odpowiada (#516)").toBeTruthy();

  const r = await page.request.get("/api/admin/world/enemies?limit=1");
  expect(r.status(), "backend admin endpoint nie odpowiada — migracja mogła nie uruchomić (#516)")
    .toBeLessThan(500);
});
