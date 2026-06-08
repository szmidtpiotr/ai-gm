/**
 * REGRESSION #386 (D11) — Confirm password field in register form.
 * Acceptance: register form has #register-password-confirm field; app.js validates match.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #386 — register form has confirm password field", async ({ page }) => {
  const r = await page.request.get("/");
  expect(r.ok(), "player UI should load").toBeTruthy();
  const body = await r.text();
  expect(body, "confirm field must exist in register form").toContain("register-password-confirm");
});

test("REGRESSION #386 — confirm field is type=password", async ({ page }) => {
  const r = await page.request.get("/");
  const body = await r.text();
  const idx = body.indexOf('id="register-password-confirm"');
  expect(idx, "confirm field must exist").toBeGreaterThan(0);
  const context = body.substring(Math.max(0, idx - 150), idx + 300);
  expect(context, "confirm field must be type=password").toContain('type="password"');
});

test("REGRESSION #386 — app.js references register-password-confirm", async ({ page }) => {
  const r = await page.request.get("/front/js/app.js");
  expect(r.ok(), "app.js should load").toBeTruthy();
  const js = await r.text();
  expect(js, "app.js must validate confirm field").toContain("register-password-confirm");
});

test("REGRESSION #386 — original register-password field still exists", async ({ page }) => {
  const r = await page.request.get("/");
  const body = await r.text();
  expect(body, "original password field must remain").toContain('id="register-password"');
});
