/**
 * REGRESSION #831 (M0-2) — Nawigacja mobilna: hamburger otwiera szufladę ze wszystkimi sekcjami.
 * Acceptance: na @390px topbar ma hamburger, klik otwiera drawer z >=17 sekcjami, klik sekcji zamyka drawer.
 */
const { test, expect } = require("@playwright/test");

test.use({ viewport: { width: 390, height: 844 } });

/** Login jako demo, zwróć token do localStorage przed nawigacją */
async function loginDemo(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const body = await resp.json();
  const token = body.token;
  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
}

test("REGRESSION #831 — hamburger istnieje w HTML", async ({ page }) => {
  const r = await page.request.get("/admin/");
  expect(r.ok(), "GET /admin/ nie zwraca 200 (#831)").toBeTruthy();
  const html = await r.text();
  expect(html, "Brak id=hamburger-btn (#831)").toContain('id="hamburger-btn"');
  expect(html, "Brak id=mobile-drawer (#831)").toContain('id="mobile-drawer"');
  expect(html, "Brak id=drawer-overlay (#831)").toContain('id="drawer-overlay"');
  expect(html, "Brak id=mobile-drawer-nav (#831)").toContain('id="mobile-drawer-nav"');
});

test("REGRESSION #831 — szuflada otwiera się po kliknięciu hamburgera", async ({ page }) => {
  await loginDemo(page);
  await page.goto("/admin/");
  await page.waitForLoadState("domcontentloaded");

  const drawer = page.locator("#mobile-drawer");
  const hamburger = page.locator("#hamburger-btn");

  await expect(drawer).not.toHaveClass(/open/);
  await hamburger.click();
  await expect(drawer).toHaveClass(/open/);
});

test("REGRESSION #831 — overlay zamyka szufladę", async ({ page }) => {
  await loginDemo(page);
  await page.goto("/admin/");
  await page.waitForLoadState("domcontentloaded");

  const drawer = page.locator("#mobile-drawer");
  const overlay = page.locator("#drawer-overlay");

  await page.locator("#hamburger-btn").click();
  await expect(drawer).toHaveClass(/open/);

  await overlay.click();
  await expect(drawer).not.toHaveClass(/open/);
});

test("REGRESSION #831 — szuflada zawiera co najmniej 17 sekcji", async ({ page }) => {
  await loginDemo(page);
  await page.goto("/admin/");
  await page.waitForLoadState("domcontentloaded");

  await page.locator("#hamburger-btn").click();
  const items = page.locator("#mobile-drawer-nav .nav-item");
  const count = await items.count();
  expect(count, `Za mało sekcji w szufladzie: ${count} (oczekiwano >=17)`).toBeGreaterThanOrEqual(17);
});

test("REGRESSION #831 — klik sekcji zamyka szufladę", async ({ page }) => {
  await loginDemo(page);
  await page.goto("/admin/");
  await page.waitForLoadState("domcontentloaded");

  const drawer = page.locator("#mobile-drawer");
  await page.locator("#hamburger-btn").click();
  await expect(drawer).toHaveClass(/open/);

  await page.locator("#mobile-drawer-nav .nav-item").first().click();
  await expect(drawer).not.toHaveClass(/open/);
});
