/**
 * REGRESSION #914 (W13) — Szwy wzrostu: email capture + OG/SEO + analytics script.
 * Acceptance: subscribe endpoint returns 200; showcase index has og:title + umami script.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #914 — subscribe endpoint accepts valid email", async ({ page }) => {
  const r = await page.request.post("/api/showcase/subscribe", {
    data: { email: "pw_test914@example.com" },
    headers: { "Content-Type": "application/json" },
  });
  expect(r.ok(), "subscribe endpoint nie odpowiada 2xx (#914)").toBeTruthy();
  const body = await r.json();
  expect(body.ok, "response.ok powinna być true (#914)").toBe(true);
});

test("REGRESSION #914 — subscribe endpoint rejects invalid email", async ({ page }) => {
  const r = await page.request.post("/api/showcase/subscribe", {
    data: { email: "not-an-email" },
    headers: { "Content-Type": "application/json" },
  });
  expect(r.status(), "nieprawidłowy email powinien zwrócić 422 (#914)").toBe(422);
});

test("REGRESSION #914 — showcase index has OG meta tags", async ({ page }) => {
  await page.goto("/showcase/");
  const ogTitle = await page.getAttribute('meta[property="og:title"]', "content");
  expect(ogTitle, "og:title brakuje na showcase (#914)").toBeTruthy();
  const ogImg = await page.getAttribute('meta[property="og:image"]', "content");
  expect(ogImg, "og:image brakuje na showcase (#914)").toBeTruthy();
});

test("REGRESSION #914 — showcase index has Umami analytics script", async ({ page }) => {
  await page.goto("/showcase/");
  const umamiScript = await page.locator('script[data-website-id]').count();
  expect(umamiScript, "Umami script tag brakuje na showcase (#914)").toBeGreaterThan(0);
});

test("REGRESSION #914 — showcase index has subscribe form", async ({ page }) => {
  await page.goto("/showcase/");
  const form = await page.locator("#subscribe-form").count();
  expect(form, "formularz subskrypcji brakuje na showcase (#914)").toBeGreaterThan(0);
});
