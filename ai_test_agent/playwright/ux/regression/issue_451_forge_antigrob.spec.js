/**
 * REGRESSION #451 (FADM-P15) — Anti-grób: Forge usunięty z admin3, shell bez linków do admin3.
 * Acceptance: admin3 nie zawiera sekcji Forge (#section-forge usunięty), klik Kuźni w admin3
 * redirectuje do /admin/#forge, modularny /admin/ nie linkuje do admin3, /admin/#forge bez regresji.
 */
const { test, expect } = require("@playwright/test");

async function _login(page) {
  await page.goto("/admin/");
  await page.evaluate(async () => {
    const r = await fetch("/api/admin/dev-login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "demo", password: "demo" }),
    });
    const b = await r.json();
    localStorage.setItem("aigm_admin_token", b.token);
    localStorage.setItem("aigm_admin_user", b.username || "demo");
  });
}

test("REGRESSION #451 — admin3 nie zawiera już sekcji Forge", async ({ page }) => {
  const r = await page.request.get("/admin3/");
  expect(r.ok(), "admin3 nie serwuje 200 (#451)").toBeTruthy();
  const html = await r.text();
  expect(html.includes('id="section-forge"'), "admin3 wciąż ma #section-forge (#451)").toBeFalsy();
  expect(html.includes('id="tpl-entity-modal"'), "admin3 wciąż ma forge modal tpl-entity-modal (#451)").toBeFalsy();
  expect(html.includes('id="forge-plan-dialog"'), "admin3 wciąż ma forge-plan-dialog (#451)").toBeFalsy();
  // redirect dla forge musi istnieć
  expect(html.includes("key === 'forge'"), "admin3 brak redirectu forge → /admin/ (#451)").toBeTruthy();
});

test("REGRESSION #451 — modularny shell nie linkuje do admin3", async ({ page }) => {
  const r = await page.request.get("/admin/");
  expect(r.ok(), "/admin/ nie serwuje 200 (#451)").toBeTruthy();
  const html = await r.text();
  // Footer + placeholder nie mogą zawierać href do /admin3/
  expect(/href="\/admin3\//.test(html), "shell wciąż ma href do /admin3/ (#451)").toBeFalsy();
});

test("REGRESSION #451 — /admin/#forge działa bez regresji", async ({ page }) => {
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  await _login(page);
  await page.goto("/admin/#forge");
  await page.waitForTimeout(2500);
  expect(page.url(), "powinien zostać na /admin/#forge (#451)").toContain("/admin/");
  expect(page.url(), "nie wolno redirectować do admin3 (#451)").not.toContain("/admin3/");
  await expect(page.locator("#forge-tabs").first(), "Kuźnia nie wyrenderowana (#451)").toBeVisible({ timeout: 5000 });
  expect(errors, "page errors w /admin/#forge: " + JSON.stringify(errors)).toHaveLength(0);
});
