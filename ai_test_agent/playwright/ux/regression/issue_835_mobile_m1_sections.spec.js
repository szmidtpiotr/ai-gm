/**
 * REGRESSION #835 (M1) — Admin mobile: Overview tabs scroll, Push card-view, economy table scroll.
 * Acceptance: At 390px viewport — section tabs scrollable, push table uses card layout,
 * overview economy table wrapped for horizontal scroll. No desktop regression at 1280px.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #835 — section-tabs have overflow-x:auto in mobile CSS", async ({ page }) => {
  const r = await page.request.get("/admin/shared/components.css");
  expect(r.ok(), "components.css not reachable").toBeTruthy();
  const css = await r.text();
  expect(css, "section-tabs missing overflow-x rule for mobile").toContain("overflow-x");
  expect(css, "section-tabs missing -webkit-overflow-scrolling").toContain("-webkit-overflow-scrolling: touch");
});

test("REGRESSION #835 — push.js has data-table--cards class", async ({ page }) => {
  const r = await page.request.get("/admin/sections/push.js");
  expect(r.ok(), "push.js not reachable").toBeTruthy();
  const src = await r.text();
  expect(src, "push.js missing data-table--cards class on table wrapper").toContain("data-table--cards");
  const labels = ["Gracz", "Status", "Subskrypcji", "Ostatnia rej.", "Akcja"];
  for (const label of labels) {
    expect(src, `push.js missing data-label="${label}"`).toContain(`data-label="${label}"`);
  }
});

test("REGRESSION #835 — overview.js has data-table--scroll wrapper for economy table", async ({ page }) => {
  const r = await page.request.get("/admin/sections/overview.js");
  expect(r.ok(), "overview.js not reachable").toBeTruthy();
  const src = await r.text();
  // Check that data-table--scroll appears in the econHost.innerHTML region
  const econIdx = src.indexOf("econHost.innerHTML");
  expect(econIdx, "econHost.innerHTML not found in overview.js").toBeGreaterThan(-1);
  const region = src.slice(econIdx, econIdx + 2000);
  expect(region, "economy table missing data-table--scroll wrapper").toContain("data-table--scroll");
});

test("REGRESSION #835 — admin panel loads on mobile viewport without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/admin/");
  // Wait for shell to render
  await page.waitForSelector(".shell", { timeout: 8000 });

  // Page should not have horizontal scroll (scrollWidth <= clientWidth)
  const hasOverflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth > document.documentElement.clientWidth;
  });
  expect(hasOverflow, "admin panel has horizontal overflow at 390px width").toBeFalsy();
});
