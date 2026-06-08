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

test("FADM-P10 #412 — admin3 switchSection redirects tools to /admin/", async ({ page }) => {
  const r = await page.request.get("/admin3/");
  expect(r.status()).toBe(200);
  const body = await r.text();
  expect(body, "admin3 should have redirect for tools").toContain("/admin/#tools");
});

test("FADM-P10 #412 — PORTED set includes tools", async ({ page }) => {
  const r = await page.request.get("/admin/");
  expect(r.status()).toBe(200);
  const body = await r.text();
  expect(body, "PORTED set should include tools").toContain("'tools'");
});
