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

test("FADM-P11 #413 — /admin/#system renderuje moduł system", async ({ page }) => {
  await page.goto("/admin/");
  await page.evaluate(async () => {
    const r = await fetch("/api/admin/dev-login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "demo", password: "demo" }),
    });
    const b = await r.json();
    localStorage.setItem("aigm_admin_token", b.token);
  });
  await page.goto("/admin/#system");
  await expect(page.locator("#section-system"), "sekcja system nie wyrenderowana w /admin/ (FADM-P11 #413)").toBeVisible({ timeout: 10000 });
});

test("FADM-P11 #413 — PORTED set includes system", async ({ page }) => {
  const r = await page.request.get("/admin/");
  expect(r.status()).toBe(200);
  const body = await r.text();
  expect(body, "PORTED set should include system").toContain("'system'");
});
