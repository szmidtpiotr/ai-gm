/**
 * REGRESSION #896 — login background FOUC fix (no green monster flash).
 * Acceptance: CSS must not hardcode bg-login.jpg; index.html must have localStorage
 * preload script; API must return login bg URL for caching.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #896 — CSS default login bg is not hardcoded to bg-login.jpg", async ({ page }) => {
  const r = await page.request.get("/css/styles.css");
  expect(r.ok(), "styles.css nie odpowiada 200 (#896)").toBeTruthy();
  const css = await r.text();
  expect(
    css.includes("bg-login.jpg"),
    "styles.css nadal zawiera bg-login.jpg jako domyślne tło logowania (#896)"
  ).toBeFalsy();
});

test("REGRESSION #896 — index.html has localStorage bg preload script in <head>", async ({ page }) => {
  const r = await page.request.get("/");
  expect(r.ok(), "index.html nie odpowiada 200 (#896)").toBeTruthy();
  const html = await r.text();
  expect(
    html.includes("ai-gm-bg-cache"),
    "index.html nie ma skryptu preload localStorage 'ai-gm-bg-cache' (#896)"
  ).toBeTruthy();
});

test("REGRESSION #896 — /api/ui/backgrounds returns login bg URL", async ({ page }) => {
  const r = await page.request.get("/api/ui/backgrounds");
  expect(r.ok(), "/api/ui/backgrounds nie odpowiada 200 (#896)").toBeTruthy();
  const data = await r.json();
  expect(data.backgrounds, "brak klucza 'backgrounds' w odpowiedzi (#896)").toBeTruthy();
  expect(
    typeof data.backgrounds === "object",
    "'backgrounds' musi być obiektem (#896)"
  ).toBeTruthy();
  expect(
    "login" in data.backgrounds,
    "'backgrounds' nie zawiera klucza 'login' (#896)"
  ).toBeTruthy();
});
