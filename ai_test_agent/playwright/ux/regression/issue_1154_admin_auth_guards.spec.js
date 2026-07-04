/**
 * REGRESSION #1154 (SEC) — routery adminowe muszą wymagać tokena.
 * Acceptance: nieautoryzowany GET na dotknięte /api/admin/* zwraca 401, nie 200.
 */
const { test, expect } = require("@playwright/test");

const GUARDED = [
  "/api/admin/world/pending/counts",
  "/api/admin/images/config",
  "/api/admin/sandbox/heroes",
  "/api/admin/rest-sandbox/heroes",
  "/api/admin/game-mechanics/content",
  "/api/admin/ui-texts",
  "/api/admin/visual",
];

for (const path of GUARDED) {
  test(`REGRESSION #1154 — ${path} 401 bez tokena`, async ({ page }) => {
    const r = await page.request.get(path);
    expect(r.status(), `${path} przeszło bez tokena`).toBe(401);
  });
}

test("REGRESSION #1154 — publiczne endpointy dalej otwarte", async ({ page }) => {
  const texts = await page.request.get("/api/ui/texts");
  expect(texts.status(), "publiczny /api/ui/texts zablokowany").not.toBe(401);
  const visual = await page.request.get("/api/visual/public");
  expect(visual.status(), "publiczny /api/visual/public zablokowany").not.toBe(401);
});
