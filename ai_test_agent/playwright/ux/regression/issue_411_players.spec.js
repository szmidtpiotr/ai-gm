/**
 * REGRESSION #411 (FADM-P9) — Port sekcji players do modularnego admin/.
 * Acceptance: /admin/#players ładuje moduł players.js i wyświetla listę użytkowników.
 */
const { test, expect } = require("@playwright/test");

test("FADM-P9 #411 — players.js serves 200", async ({ page }) => {
  const r = await page.request.get("/admin/sections/players.js");
  expect(r.status(), "players.js should be 200").toBe(200);
  const body = await r.text();
  expect(body, "should export init function").toContain("export async function init");
});

test("FADM-P9 #411 — API /api/admin/accounts responds", async ({ page }) => {
  const r = await page.request.get("/api/admin/accounts");
  expect([200, 401], `/api/admin/accounts got ${r.status()}`).toContain(r.status());
});

test("FADM-P9 #411 — /admin/#players renderuje moduł players", async ({ page }) => {
  await page.goto("/admin/");
  await page.evaluate(async () => {
    const r = await fetch("/api/admin/dev-login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "demo", password: "demo" }),
    });
    const b = await r.json();
    localStorage.setItem("aigm_admin_token", b.token);
  });
  await page.goto("/admin/#players");
  await expect(page.locator("#section-players"), "sekcja players nie wyrenderowana w /admin/ (FADM-P9 #411)").toBeVisible({ timeout: 10000 });
});

test("FADM-P9 #411 — PORTED set includes players", async ({ page }) => {
  const r = await page.request.get("/admin/");
  expect(r.status()).toBe(200);
  const body = await r.text();
  expect(body, "PORTED set should include players").toContain("'players'");
});
