/**
 * REGRESSION #846 (M5) — Hex mapa: pełna obsługa dotykowa (pinch-zoom/pan/tap).
 * Acceptance: map.js i campaigns.js serwują touch handlery; brak statycznej blokady mobile.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #846 — map.js serwuje touch handlery pinch/pan/tap", async ({ page }) => {
  const r = await page.request.get("/admin/sections/map.js");
  expect(r.ok(), "map.js nie odpowiada 200 (#846)").toBeTruthy();
  const txt = await r.text();
  expect(txt.includes("touchstart"), "map.js brak touchstart (#846)").toBeTruthy();
  expect(txt.includes("touchmove"), "map.js brak touchmove (#846)").toBeTruthy();
  expect(txt.includes("touchend"), "map.js brak touchend (#846)").toBeTruthy();
  expect(txt.includes("Math.hypot"), "map.js brak pinch-zoom logic (#846)").toBeTruthy();
  expect(txt.includes("mobileReadonly") === false, "map.js wciąż ma mobileReadonly blokadę M0-5").toBeTruthy();
});

test("REGRESSION #846 — campaigns.js serwuje touch handlery dla hex-mapy kampanii", async ({ page }) => {
  const r = await page.request.get("/admin/sections/campaigns.js");
  expect(r.ok(), "campaigns.js nie odpowiada 200 (#846)").toBeTruthy();
  const txt = await r.text();
  expect(txt.includes("touchstart"), "campaigns.js brak touchstart (#846)").toBeTruthy();
  expect(txt.includes("pinch"), "campaigns.js brak pinch-zoom logic (#846)").toBeTruthy();
  expect(txt.includes("_showHexEditModal"), "campaigns.js brak tap-to-edit (#846)").toBeTruthy();
  expect(!txt.includes("Edycja hexów niedostępna na mobile"), "campaigns.js wciąż ma blokadę M0-5").toBeTruthy();
});

test("REGRESSION #846 — map.js nie ma już blokady mobileReadonly (M0-5 zastąpione przez M5)", async ({ page }) => {
  const mapR = await page.request.get("/admin/sections/map.js");
  const campR = await page.request.get("/admin/sections/campaigns.js");
  expect(mapR.ok()).toBeTruthy();
  expect(campR.ok()).toBeTruthy();
  const mapTxt = await mapR.text();
  const campTxt = await campR.text();
  expect(!mapTxt.includes("mobileReadonly"), "map.js wciąż ma mobileReadonly M0-5 blokadę").toBeTruthy();
  expect(!campTxt.includes("mobileReadonly"), "campaigns.js wciąż ma mobileReadonly M0-5 blokadę").toBeTruthy();
});
