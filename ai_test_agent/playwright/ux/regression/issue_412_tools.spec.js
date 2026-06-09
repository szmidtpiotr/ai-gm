/**
 * REGRESSION #412 (FADM-P10) — Port sekcji tools do modularnego admin/.
 * Acceptance: /admin/#tools ładuje moduł tools.js; sandbox/Playwright/Inspector działają.
 */
const { test, expect } = require("@playwright/test");

test("FADM-P10 #412 — tools.js serves 200", async ({ page }) => {
  const r = await page.request.get("/admin/sections/tools.js");
  expect(r.status(), "tools.js should be 200").toBe(200);
  const body = await r.text();
  expect(body, "should export init function").toContain("export async function init");
});

test("FADM-P10 #412 — API /api/admin/sandbox/heroes responds", async ({ page }) => {
  const r = await page.request.get("/api/admin/sandbox/heroes");
  expect([200, 401], `/api/admin/sandbox/heroes got ${r.status()}`).toContain(r.status());
});

test("FADM-P10 #412 — /admin/#tools renderuje moduł tools", async ({ page }) => {
  await page.goto("/admin/");
  await page.evaluate(async () => {
    const r = await fetch("/api/admin/dev-login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "demo", password: "demo" }),
    });
    const b = await r.json();
    localStorage.setItem("aigm_admin_token", b.token);
  });
  await page.goto("/admin/#tools");
  await expect(page.locator("#section-tools"), "sekcja tools nie wyrenderowana w /admin/ (FADM-P10 #412)").toBeVisible({ timeout: 10000 });
});

test("FADM-P10 #412 — PORTED set includes tools", async ({ page }) => {
  const r = await page.request.get("/admin/");
  expect(r.status()).toBe(200);
  const body = await r.text();
  expect(body, "PORTED set should include tools").toContain("'tools'");
});
