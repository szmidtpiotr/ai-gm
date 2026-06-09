/**
 * REGRESSION #450 (FADM-P14) — Forge (Kuźnia) sportowany do modularnego /admin/.
 * Acceptance: /admin/#forge renderuje sekcję Kuźni (zakładki + lista szablonów)
 * BEZ przekierowania do /admin3/. Forge dodany do PORTED set.
 */
const { test, expect } = require("@playwright/test");

async function _login(page) {
  await page.goto("/admin/");
  const tok = await page.evaluate(async () => {
    const r = await fetch("/api/admin/dev-login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "demo", password: "demo" }),
    });
    const b = await r.json();
    localStorage.setItem("aigm_admin_token", b.token);
    localStorage.setItem("aigm_admin_user", b.username || "demo");
    return b.token;
  });
  expect(tok, "login token missing").toBeTruthy();
}

test("REGRESSION #450 — /admin/#forge renderuje Kuźnię bez redirectu do admin3", async ({ page }) => {
  await _login(page);
  await page.goto("/admin/#forge");
  // Daj routerowi czas na ewentualny redirect / mount modułu
  await page.waitForTimeout(2500);

  // NIE wolno przekierować do admin3
  expect(page.url(), "forge redirected to /admin3/ — nie sportowany (#450)").not.toContain("/admin3/");
  expect(page.url(), "powinien zostać na /admin/#forge (#450)").toContain("/admin/");

  // Sekcja Kuźni musi być w DOM (zakładki forge lub lista szablonów)
  const forgeTabs = page.locator("#forge-tabs, #section-forge, #forge-templates-list");
  await expect(forgeTabs.first(), "sekcja Kuźni nie wyrenderowana (#450)").toBeVisible({ timeout: 5000 });
});

test("REGRESSION #450 — backend forge endpoints nietknięte (parity)", async ({ page }) => {
  // GET templates — auth-gated
  const noauth = await page.request.get("/api/admin/forge/templates");
  expect(noauth.status(), "forge templates musi być auth-gated (#450)").toBe(401);

  // Public campaign-templates — 200
  const pub = await page.request.get("/api/campaign-templates");
  expect(pub.ok(), "public campaign-templates nie 200 (#450)").toBeTruthy();
});
