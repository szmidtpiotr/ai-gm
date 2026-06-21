/**
 * REGRESSION #866 — MP join-link routing: /?join=TOKEN redirects to register (not login).
 * Acceptance: unauthenticated user clicking invite link sees register screen + join notice,
 * NOT the login screen. Token survives in localStorage for post-auth consumption.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #866 — /?join=TOKEN shows register screen for unauthenticated user", async ({ page, context }) => {
  // Clear storage to ensure we're unauthenticated
  await context.clearCookies();
  await page.goto(BASE);
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  // Navigate with join token
  await page.goto(`${BASE}/?join=TEST-INVITE-TOKEN-866`);
  await page.waitForTimeout(800);

  // Should land on register screen, NOT login
  const registerScreen = page.locator("#register-screen");
  const loginScreen = page.locator("#login-screen");

  const registerVisible = await registerScreen.isVisible();
  const loginVisible = await loginScreen.isVisible();

  expect(registerVisible, "Register screen must be visible after /?join=TOKEN (#866)").toBeTruthy();
  expect(loginVisible, "Login screen must NOT be visible after /?join=TOKEN (#866)").toBeFalsy();
});

test("REGRESSION #866 — join notice visible on register screen", async ({ page, context }) => {
  await context.clearCookies();
  await page.goto(BASE);
  await page.evaluate(() => localStorage.clear());

  await page.goto(`${BASE}/?join=TEST-INVITE-TOKEN-866`);
  await page.waitForTimeout(800);

  const notice = page.locator("#register-mp-join-notice");
  const noticeVisible = await notice.isVisible();
  expect(noticeVisible, "MP join notice must be visible on register screen (#866)").toBeTruthy();
});

test("REGRESSION #866 — join token stored in localStorage after routing", async ({ page, context }) => {
  await context.clearCookies();
  await page.goto(BASE);
  await page.evaluate(() => localStorage.clear());

  await page.goto(`${BASE}/?join=TEST-INVITE-TOKEN-866`);
  await page.waitForTimeout(800);

  const storedToken = await page.evaluate(() => localStorage.getItem("pendingJoinToken"));
  expect(storedToken, "Token must be saved to localStorage.pendingJoinToken (#866)").toBe("TEST-INVITE-TOKEN-866");
});

test("REGRESSION #866 — URL cleaned after join routing (no ?join= in address bar)", async ({ page, context }) => {
  await context.clearCookies();
  await page.goto(BASE);
  await page.evaluate(() => localStorage.clear());

  await page.goto(`${BASE}/?join=TEST-INVITE-TOKEN-866`);
  await page.waitForTimeout(800);

  const url = page.url();
  expect(url, "URL must not contain ?join= after routing (#866)").not.toContain("join=");
});

test("REGRESSION #866 — backend join endpoint rejects missing token with 404", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/multiplayer/join/NONEXISTENT-TOKEN-866`);
  expect([404, 401, 403], "Missing token must return 404 or auth error (#866)").toContain(r.status());
});
