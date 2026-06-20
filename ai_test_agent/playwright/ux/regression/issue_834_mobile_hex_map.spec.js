/**
 * REGRESSION #834 (M0-5) — Mobile hex map: SVG scales to viewport, edit blocked on mobile.
 * Acceptance: map.js has mobileReadonly guard; campaigns.js has mobileReadonly guard;
 * components.css has .mobile-edit-notice; CSS has SVG mobile scaling rules.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #834 — map.js serves mobileReadonly guard", async ({ page }) => {
  const r = await page.request.get("/admin/sections/map.js");
  expect(r.ok(), "map.js not served (#834)").toBeTruthy();
  const body = await r.text();
  expect(body.includes("mobileReadonly"), "map.js missing mobileReadonly guard (#834)").toBeTruthy();
  expect(body.includes("mobile-edit-notice"), "map.js missing mobile-edit-notice class usage (#834)").toBeTruthy();
});

test("REGRESSION #834 — campaigns.js serves mobileReadonly guard", async ({ page }) => {
  const r = await page.request.get("/admin/sections/campaigns.js");
  expect(r.ok(), "campaigns.js not served (#834)").toBeTruthy();
  const body = await r.text();
  expect(body.includes("mobileReadonly"), "campaigns.js missing mobileReadonly guard (#834)").toBeTruthy();
  expect(body.includes("mobile-edit-notice"), "campaigns.js missing mobile notice class (#834)").toBeTruthy();
});

test("REGRESSION #834 — components.css has mobile-edit-notice and SVG scaling rules", async ({ page }) => {
  const r = await page.request.get("/admin/shared/components.css");
  expect(r.ok(), "components.css not served (#834)").toBeTruthy();
  const body = await r.text();
  expect(body.includes("mobile-edit-notice"), "components.css missing .mobile-edit-notice (#834)").toBeTruthy();
  expect(body.includes("touch-action: none"), "components.css missing touch-action:none for SVG (#834)").toBeTruthy();
});

test("REGRESSION #834 — admin map section loads without JS errors at 390px viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/admin/#map");
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.waitForTimeout(1500);
  expect(errors.filter(e => !e.includes("favicon")).length, `JS errors on mobile map: ${errors.join("; ")}`).toBe(0);
});
