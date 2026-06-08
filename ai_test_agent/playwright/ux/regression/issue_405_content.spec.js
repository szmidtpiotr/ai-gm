/**
 * REGRESSION #405 (FADM-P3) — Port sekcji content → modularny admin/.
 * Acceptance: /admin/#content renderuje sekcję z 6 tabami (weapons/armor/items/consumables/loot/spells),
 * tabela broni ładuje dane, Smart Entry button istnieje.
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

test("REGRESSION #405 — /admin/#content renderuje sekcję z tabami zawartości", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#content");

  // Sekcja content zamontowana
  await expect(page.locator("#section-content")).toBeVisible({ timeout: 10000 });

  // 6 tabów (weapons, armor, items, consumables, loot, spells)
  const TABS = ["weapons", "armor", "items", "consumables", "loot", "spells"];
  for (const t of TABS) {
    await expect(page.locator(`#content-tabs .stab[data-tab="${t}"]`), `Tab ${t} brak`).toHaveCount(1);
  }

  // Domyślny tab weapons aktywny
  await expect(page.locator('#content-tabs .stab[data-tab="weapons"]')).toHaveClass(/active/);
  await expect(page.locator("#stab-weapons")).toHaveClass(/active/);
});

test("REGRESSION #405 — tab Broń wczytuje dane z API", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#content");

  await expect(page.locator("#section-content")).toBeVisible({ timeout: 10000 });

  // Tabela broni ładuje dane (przynajmniej 1 wiersz, nie placeholder)
  await expect
    .poll(async () => await page.locator("#weapons-table tbody tr").count(), { timeout: 12000 })
    .toBeGreaterThan(0);

  await expect(page.locator("#weapons-table tbody tr").first()).not.toContainText("Ładowanie…");
});

test("REGRESSION #405 — przełączenie na tab Spells wczytuje tabelę czarów", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#content");

  await expect(page.locator("#section-content")).toBeVisible({ timeout: 10000 });

  await page.locator('#content-tabs .stab[data-tab="spells"]').click();
  await expect(page.locator("#stab-spells")).toHaveClass(/active/);

  // Tabela czarów wczytana
  await expect
    .poll(async () => await page.locator("#spells-table tbody tr").count(), { timeout: 12000 })
    .toBeGreaterThan(0);
  await expect(page.locator("#spells-table tbody tr").first()).not.toContainText("Ładowanie…");
});

test("REGRESSION #405 — admin3 nadal żyje po ANTY-GROB", async ({ page }) => {
  await adminLogin(page);
  await expect(page).toHaveURL(/\/admin3\//);
});
