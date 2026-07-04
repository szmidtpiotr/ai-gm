/**
 * REGRESSION #1169 — martwe wywołania admina ożywione.
 * Acceptance: run-command, bg from-tile oraz locations admin-PATCH już nie 404/405
 * (route istnieje; bez tokenu spodziewamy się 401/403/400/422, nie 404/405).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1169 — run-command endpoint istnieje", async ({ page }) => {
  const r = await page.request.post("/api/admin/campaigns/1/run-command", { data: { text: "/help" } });
  expect(r.status(), "run-command nie może być 404 (#1169)").not.toBe(404);
});

test("REGRESSION #1169 — bg from-tile endpoint istnieje", async ({ page }) => {
  const r = await page.request.post("/api/admin/ui/bg/login/from-tile", { data: { filename: "x.png" } });
  expect(r.status(), "bg from-tile nie może być 404 (#1169)").not.toBe(404);
});

test("REGRESSION #1169 — locations admin-PATCH (cel repointu map.js) istnieje", async ({ page }) => {
  const r = await page.request.patch("/api/locations/admin/locations/some_key", { data: { canonical: 1 } });
  // 401/403/404-entity/422 dopuszczalne; 405 (Method Not Allowed) oznaczałoby brak PATCH.
  expect(r.status(), "PATCH musi być obsługiwany (nie 405) (#1169)").not.toBe(405);
});
