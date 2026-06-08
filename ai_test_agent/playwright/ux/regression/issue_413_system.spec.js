/**
 * REGRESSION #413 (FADM-P11) — Port sekcji system do modularnego admin/.
 * Acceptance: /admin/#system ładuje moduł system.js z 12 tabami (LLM, DB, Config, itp.).
 */
const { test, expect } = require("@playwright/test");

test("FADM-P11 #413 — system.js serves 200", async ({ page }) => {
  const r = await page.request.get("/admin/sections/system.js");
  expect(r.status(), "system.js should be 200").toBe(200);
  const body = await r.text();
  expect(body, "should export init function").toContain("export async function init");
});

test("FADM-P11 #413 — system.js contains all 12 tab keys", async ({ page }) => {
  const r = await page.request.get("/admin/sections/system.js");
  const body = await r.text();
  // Tabs defined as data-systab="key" in HTML template (double quotes)
  const tabs = ['llm', 'database', 'config', 'slash', 'resurrection', 'email', 'visual', 'teksty', 'voice', 'imagegen', 'narration', 'gamemodes'];
  for (const tab of tabs) {
    expect(body, `system.js should contain tab data-systab="${tab}"`).toContain(`data-systab="${tab}"`);
  }
});

test("FADM-P11 #413 — API /api/admin/llm/global-settings responds", async ({ page }) => {
  const r = await page.request.get("/api/admin/llm/global-settings");
  expect([200, 401], `/api/admin/llm/global-settings got ${r.status()}`).toContain(r.status());
});

test("FADM-P11 #413 — admin3 switchSection redirects system to /admin/", async ({ page }) => {
  const r = await page.request.get("/admin3/");
  expect(r.status()).toBe(200);
  const body = await r.text();
  expect(body, "admin3 should have redirect for system").toContain("/admin/#system");
});

test("FADM-P11 #413 — PORTED set includes system", async ({ page }) => {
  const r = await page.request.get("/admin/");
  expect(r.status()).toBe(200);
  const body = await r.text();
  expect(body, "PORTED set should include system").toContain("'system'");
});
