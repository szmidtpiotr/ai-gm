/**
 * REGRESSION #406 (FADM-P4) — Port sekcji world → modularny admin/.
 * Acceptance: /admin/#world renderuje sekcję z 4 tabami (npcs/enemies/loot/pending),
 * tabela NPC i wrogów ładuje dane z API, admin3 żyje po ANTY-GROB.
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

test("REGRESSION #406 — /admin/#world renderuje sekcję z 4 tabami", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#world");

  // Modular shell renders into #panel — wait for world-tabs (the section identifier)
  await expect(page.locator("#world-tabs")).toBeVisible({ timeout: 10000 });

  const TABS = ["npcs", "enemies", "loot", "pending"];
  for (const t of TABS) {
    await expect(
      page.locator(`#world-tabs .stab[data-wtab="${t}"]`),
      `Tab ${t} brak`
    ).toHaveCount(1);
  }

  // Domyślny tab npcs aktywny
  await expect(page.locator('#world-tabs .stab[data-wtab="npcs"]')).toHaveClass(/active/);
  await expect(page.locator("#wtab-npcs")).toHaveClass(/active/);
});

test("REGRESSION #406 — tab NPC wczytuje dane z API", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#world");

  await expect(page.locator("#world-tabs")).toBeVisible({ timeout: 10000 });

  await expect
    .poll(async () => await page.locator("#npcs-table tbody tr").count(), { timeout: 12000 })
    .toBeGreaterThan(0);

  await expect(page.locator("#npcs-table tbody tr").first()).not.toContainText("Ładowanie…");
});

test("REGRESSION #406 — przełączenie na tab Wrogowie wczytuje tabelę", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#world");

  await expect(page.locator("#world-tabs")).toBeVisible({ timeout: 10000 });

  await page.locator('#world-tabs .stab[data-wtab="enemies"]').click();
  await expect(page.locator("#wtab-enemies")).toHaveClass(/active/);

  await expect
    .poll(async () => await page.locator("#world-enemies-table tbody tr").count(), { timeout: 12000 })
    .toBeGreaterThan(0);
  await expect(page.locator("#world-enemies-table tbody tr").first()).not.toContainText("Ładowanie…");
});

test("REGRESSION #406 — admin3 nadal żyje po ANTY-GROB", async ({ page }) => {
  await adminLogin(page);
  await expect(page).toHaveURL(/\/admin3\//);
});
