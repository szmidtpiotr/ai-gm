/**
 * REGRESSION #574 (U24) — Napad: counterplay (ostrzeżenie + rzut obronny + próg biedy + limit 24h).
 * Acceptance: mechanika napadu wystawia DC obrony z zamka {8,12,16,20,24} rosnące z poziomem,
 * próg biedy 50 gp, limit 24h i % kradzieży 20% — wszystko liczone przez backend (mechanika decyduje).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #574 — DC obrony należy do zamka {8,12,16,20,24}", async ({ page }) => {
  const r = await page.request.get("/api/debug/robbery-preview?level=5");
  expect(r.ok(), "endpoint robbery-preview nie odpowiada 200 (#574)").toBeTruthy();
  const b = await r.json();
  expect(b.ok).toBeTruthy();
  expect(b.dc_lock).toEqual([8, 12, 16, 20, 24]);
  // każde DC z drabiny musi być w zamku
  for (const dc of Object.values(b.dc_by_level)) {
    expect([8, 12, 16, 20, 24]).toContain(dc);
  }
});

test("REGRESSION #574 — DC rośnie z poziomem bohatera", async ({ page }) => {
  const r = await page.request.get("/api/debug/robbery-preview?level=1");
  const b = await r.json();
  expect(b.dc_by_level["1"]).toBeLessThanOrEqual(b.dc_by_level["5"]);
  expect(b.dc_by_level["5"]).toBeLessThanOrEqual(b.dc_by_level["10"]);
});

test("REGRESSION #574 — granice napadu: próg biedy 50, limit 24h, kradzież 20%", async ({ page }) => {
  const r = await page.request.get("/api/debug/robbery-preview?level=3");
  const b = await r.json();
  expect(b.poverty_threshold_gp).toBe(50);
  expect(b.rate_limit_hours).toBe(24);
  expect(b.gold_percent).toBe(20);
  expect(b.default_defense_stat).toBe("WIS");
});
