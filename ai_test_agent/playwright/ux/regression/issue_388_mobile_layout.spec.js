/**
 * REGRESSION #388 (D13) — Mobile layout: responsive CSS at 375px, 44px touch targets.
 * Acceptance: body no horizontal overflow, .btn min-height 44px, viewport meta present.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #388 — CSS has min-height 44px for .btn touch targets", async ({ page }) => {
  const r = await page.request.get("/");
  const html = await r.text();
  const cssMatch = html.match(/href="([^"]*styles[^"]*\.css[^"]*)"/);
  expect(cssMatch, "CSS link must exist").toBeTruthy();
  let cssPath = cssMatch[1];
  if (cssPath.startsWith(".")) cssPath = cssPath.slice(1);
  if (!cssPath.startsWith("/")) cssPath = "/front/" + cssPath;

  const cssResp = await page.request.get(cssPath);
  expect(cssResp.ok(), "CSS must load").toBeTruthy();
  const css = await cssResp.text();
  expect(css, ".btn must have min-height: 44px").toContain("min-height: 44px");
});

test("REGRESSION #388 — body has overflow-x hidden (no horizontal scroll)", async ({ page }) => {
  const r = await page.request.get("/");
  const html = await r.text();
  const cssMatch = html.match(/href="([^"]*styles[^"]*\.css[^"]*)"/);
  let cssPath = cssMatch[1];
  if (cssPath.startsWith(".")) cssPath = cssPath.slice(1);
  if (!cssPath.startsWith("/")) cssPath = "/front/" + cssPath;

  const css = await (await page.request.get(cssPath)).text();
  expect(css, "body must have overflow-x: hidden").toContain("overflow-x: hidden");
});

test("REGRESSION #388 — page loads on mobile viewport 375px", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.waitForSelector("#login-screen", { timeout: 5000 });

  // Check no horizontal overflow
  const hasHorizontalScroll = await page.evaluate(() => {
    return document.body.scrollWidth > window.innerWidth;
  });
  expect(hasHorizontalScroll, "no horizontal scroll on 375px").toBe(false);
});

test("REGRESSION #388 — viewport meta tag present", async ({ page }) => {
  const r = await page.request.get("/");
  const html = await r.text();
  expect(html, "viewport meta with width=device-width required").toContain("width=device-width");
});
