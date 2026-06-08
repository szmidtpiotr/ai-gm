/**
 * Smoke suite for Admin Panel v3 (/admin3/) — the active admin interface.
 *
 * Verifies: dev-login works, every nav section mounts (becomes active, renders
 * non-empty content) and raises no uncaught JS exception. This is a shell-level
 * smoke test — it does not assert business data, only that each section loads.
 *
 * Run:
 *   docker exec ai-gm-dev-test-agent-1 npx playwright test \
 *     playwright/ux/admin3/admin3_smoke.spec.js \
 *     --config=playwright/playwright.config.js --reporter=list
 */
const { test, expect } = require("@playwright/test");

const ADMIN_USER = process.env.AI_TEST_ADMIN_USER || "ai_test_player";
const ADMIN_PASS = process.env.AI_TEST_ADMIN_PASS || "demo";

// Sections exposed in the v3 sidebar (button.nav-item[data-section=…]).
// NOTE: `overview` ported out to modular /admin/#overview (FADM-P1 #403) — admin3 now
// redirects it. Covered by issue_403_overview.spec.js, not this smoke list.
const SECTIONS = [
  "players",
  "campaigns",
  "content",
  "world",
  "map",
  "mechanics",
  "dungeons",
  "forge",
  "invites",
  "push",
  "bugreports",
  "system",
  "tools",
];

async function clearState(page) {
  await page.addInitScript(() => {
    try {
      localStorage.clear();
      sessionStorage.clear();
    } catch (_) {
      /* ignore */
    }
  });
}

async function adminLogin(page, { user = ADMIN_USER, pass = ADMIN_PASS } = {}) {
  await page.goto("/admin3/");
  // With no stored token the login overlay opens automatically.
  await page.waitForSelector("#login-overlay.open", { timeout: 15000 });
  await page.fill("#login-user", user);
  await page.fill("#login-pass", pass);
  await page.click("#login-submit");
  // Overlay closes by losing .open AND becoming display:none — wait for hidden
  // (a `:not(.open)` selector would match the hidden node and never go visible).
  await page.locator("#login-overlay").waitFor({ state: "hidden", timeout: 20000 });
}

test.describe("ADMIN3 — auth", () => {
  test("złe hasło pokazuje błąd, nie loguje", async ({ page }) => {
    await clearState(page);
    await page.goto("/admin3/");
    await page.waitForSelector("#login-overlay.open", { timeout: 15000 });
    await page.fill("#login-user", "definitely_not_a_user");
    await page.fill("#login-pass", "wrong");
    await page.click("#login-submit");
    const err = page.locator("#login-err");
    await expect(err, "Brak komunikatu błędu przy złym haśle").toHaveClass(/show/, {
      timeout: 10000,
    });
    // Overlay must stay open (not logged in).
    await expect(page.locator("#login-overlay")).toHaveClass(/open/);
  });

  test("poprawne logowanie zamyka overlay", async ({ page }) => {
    await clearState(page);
    await adminLogin(page);
    await expect(page.locator("#login-overlay")).not.toHaveClass(/open/);
    // Default section is now `players` (overview ported out do /admin/, FADM-P1 #403).
    await expect(page.locator("#section-players")).toHaveClass(/active/, { timeout: 15000 });
  });

  test("klik 'overview' w admin3 przekierowuje do modularnego /admin/", async ({ page }) => {
    await clearState(page);
    await adminLogin(page);
    await page.locator('aside.sidebar button.nav-item[data-section="overview"]').first().click();
    await expect(page).toHaveURL(/\/admin\/#overview$/, { timeout: 15000 });
  });
});

test.describe("ADMIN3 — sekcje ładują się", () => {
  for (const key of SECTIONS) {
    test(`sekcja ${key} montuje się bez błędu JS`, async ({ page }) => {
      const pageErrors = [];
      page.on("pageerror", (e) => pageErrors.push(e.message));

      await page.setViewportSize({ width: 1440, height: 900 });
      await clearState(page);
      await adminLogin(page);

      // The desktop sidebar nav — scope to it; a hidden mobile-drawer clone of the
      // same buttons exists earlier in the DOM and would intercept the match.
      const navItem = page.locator(`aside.sidebar button.nav-item[data-section="${key}"]`);
      const hasNav = (await navItem.count().catch(() => 0)) > 0;
      test.skip(!hasNav, `Brak pozycji nawigacji dla sekcji ${key}`);

      await navItem.first().click();

      const section = page.locator(`#section-${key}`);
      await expect(section, `Sekcja ${key} nie stała się aktywna`).toHaveClass(/active/, {
        timeout: 20000,
      });

      // Section shell must render some content (not a blank pane).
      await expect
        .poll(async () => (await section.innerText().catch(() => "")).trim().length, {
          timeout: 15000,
          message: `Sekcja ${key} jest pusta`,
        })
        .toBeGreaterThan(0);

      expect(
        pageErrors,
        `Sekcja ${key} rzuciła nieobsłużony wyjątek JS: ${pageErrors[0] || ""}`,
      ).toEqual([]);
    });
  }
});
