/**
 * REGRESSION #449 (FADM-P13) — Modularny shell /admin/ ma własny ekran logowania.
 * Acceptance: Świeże wejście na /admin/ bez tokenu pokazuje formularz logowania;
 * po zalogowaniu panel ładuje się bez przekierowania do /admin3/.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #449 — /admin/ bez tokenu pokazuje formularz logowania", async ({ page }) => {
  // Wyczyść localStorage przed testem (świeże wejście)
  await page.goto("/admin/");
  await page.evaluate(() => {
    localStorage.removeItem("aigm_admin_token");
    localStorage.removeItem("aigm_admin_user");
  });
  await page.reload();

  // Login overlay musi być widoczny
  const overlay = page.locator("#login-overlay");
  await expect(overlay, "login overlay not visible without token (#449)").toBeVisible({ timeout: 5000 });

  // Formularz musi mieć wymagane pola
  await expect(page.locator("#login-user"), "login username field missing (#449)").toBeVisible();
  await expect(page.locator("#login-pass"), "login password field missing (#449)").toBeVisible();
  await expect(page.locator("#login-submit"), "login submit button missing (#449)").toBeVisible();
});

test("REGRESSION #449 — logowanie na /admin/ działa bez odwiedzania /admin3/", async ({ page }) => {
  await page.goto("/admin/");
  await page.evaluate(() => {
    localStorage.removeItem("aigm_admin_token");
    localStorage.removeItem("aigm_admin_user");
  });
  await page.reload();

  // Wypełnij i wyślij formularz
  await page.locator("#login-user").fill("demo");
  await page.locator("#login-pass").fill("demo");
  await page.locator("#login-submit").click();

  // Po zalogowaniu: overlay znika, panel widoczny
  await expect(page.locator("#login-overlay"), "overlay should hide after login (#449)").not.toBeVisible({ timeout: 8000 });

  // Nie nastąpił redirect do admin3
  expect(page.url(), "should stay on /admin/, not redirect to /admin3/ (#449)").toContain("/admin/");
  expect(page.url(), "should not redirect to /admin3/ (#449)").not.toContain("/admin3/");
});

test("REGRESSION #449 — backend /api/admin/dev-login zwraca username", async ({ page }) => {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
    headers: { "Content-Type": "application/json" },
  });
  expect(r.ok(), "dev-login endpoint not 200 (#449)").toBeTruthy();
  const body = await r.json();
  expect(body.token, "response missing token (#449)").toBeTruthy();
  expect(body.username, "response missing username field needed by modular shell (#449)").toBeTruthy();
  expect(body.username, "wrong username in response (#449)").toBe("demo");
});
