/**
 * REGRESSION #409 (FADM-P7) — Port sekcji dungeons → modularny admin/.
 * Acceptance: /admin/#dungeons renderuje tabelę lochów z danymi z API,
 * cztery taby (lochy/zagadki/kafelki/kategorie) istnieją, admin3 żyje po ANTY-GROB,
 * klik dungeons w admin3 przekierowuje do /admin/#dungeons.
 */
const { test, expect } = require("@playwright/test");

async function adminLogin(page) {
  await page.goto("/admin3/");
  const overlay = page.locator("#login-overlay");
  if (await overlay.isVisible({ timeout: 5000 }).catch(() => false)) {
    await page.fill("#login-user", "demo");
    await page.fill("#login-pass", "demo");
    await page.click("#login-submit");
    await page.waitForSelector("#login-overlay", { state: "hidden", timeout: 10000 });
  }
}

test("REGRESSION #409 — /admin/#dungeons renderuje sekcję z tabelą lochów", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#dungeons");

  // Modular shell renders into #panel — wait for dungeons-table
  await expect(page.locator("#dungeons-table")).toBeVisible({ timeout: 10000 });

  // Table must have thead
  await expect(page.locator("#dungeons-table thead")).toBeVisible();

  // 4 stab-bar tabs present: dungeons / riddles / tiles / tilecats
  const TABS = ["dungeons", "riddles", "tiles", "tilecats"];
  for (const tab of TABS) {
    await expect(
      page.locator(`#dungeons-stab-bar .stab[data-dtab="${tab}"]`),
      `Tab ${tab} brak`
    ).toBeVisible();
  }
});

test("REGRESSION #409 — tabela lochów ładuje dane z API", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#dungeons");

  await expect(page.locator("#dungeons-table")).toBeVisible({ timeout: 10000 });

  // tbody should get real rows
  await expect
    .poll(async () => {
      const rows = await page.locator("#dungeons-table tbody tr").count();
      const loading = await page.locator("#dungeons-table tbody tr td")
        .filter({ hasText: "Ładowanie…" }).count();
      return rows > 0 && loading === 0;
    }, { timeout: 15000 })
    .toBeTruthy();
});

test("REGRESSION #409 — admin3 nadal żyje po ANTY-GROB", async ({ page }) => {
  await adminLogin(page);
  await expect(page).toHaveURL(/\/admin3\//);
});

test("REGRESSION #409 — klik dungeons w admin3 przekierowuje do /admin/#dungeons", async ({ page }) => {
  await adminLogin(page);
  await page.locator('aside.sidebar button.nav-item[data-section="dungeons"]').first().click();
  await expect(page).toHaveURL(/\/admin\/#dungeons$/, { timeout: 15000 });
});
