/** RM6 (#1033) — Admin map region selector + status badges. */
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

test("RM6 - admin map has region selector", async ({ page }) => {
  test.setTimeout(60000);
  await adminLogin(page);
  await page.goto("/admin/#map");
  await page.waitForSelector("#wb-region-select", { timeout: 20000 });
  const select = page.locator("#wb-region-select");
  await expect(select).toBeVisible();
  const options = await select.locator("option").count();
  expect(options).toBeGreaterThanOrEqual(6);
  const opts = await select.locator("option").allTextContents();
  expect(opts.some(o => o.toLowerCase().includes("kresy"))).toBeTruthy();
});

test("RM6 - selecting Kresy shows live badge", async ({ page }) => {
  test.setTimeout(60000);
  await adminLogin(page);
  await page.goto("/admin/#map");
  await page.waitForSelector("#wb-region-select", { timeout: 20000 });
  await page.selectOption("#wb-region-select", "kresy");
  await page.waitForTimeout(2000);
  const hexCount = await page.locator("#wb-svg polygon.whx").count();
  expect(hexCount).toBeGreaterThan(0);
  const barText = await page.locator("#wb-region-bar").textContent();
  expect(barText.toLowerCase()).toContain("live");
});

test("RM6 - coming region shows warning", async ({ page }) => {
  test.setTimeout(60000);
  await adminLogin(page);
  await page.goto("/admin/#map");
  await page.waitForSelector("#wb-region-select", { timeout: 20000 });
  await page.selectOption("#wb-region-select", "koronne_niziny");
  await page.waitForTimeout(2000);
  const barText = await page.locator("#wb-region-bar").textContent();
  const lc = barText.toLowerCase();
  expect(lc.includes("coming") || lc.includes("niedostepna")).toBeTruthy();
});