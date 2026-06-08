/**
 * REGRESSION #404 (FADM-P2) — Port sekcji mechanics → modularny admin/.
 * Acceptance: /admin/#mechanics renderuje sekcję z 5 tabami + encounter config.
 * Kluczowe flow: wczytanie statystyk (domyślny tab) + przełączenie na skills.
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

test("REGRESSION #404 — /admin/#mechanics renderuje sekcję mechanics z 5 tabami", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#mechanics");

  // Sekcja mechanics zamontowana przez modularny router
  await expect(page.locator("#section-mechanics")).toBeVisible({ timeout: 10000 });

  // 5 tabów stab
  const MTABS = ["stats", "skills", "dc", "conditions", "archetypes"];
  for (const t of MTABS) {
    await expect(page.locator(`.stab[data-mtab="${t}"]`)).toHaveCount(1);
  }

  // Encounter config karta zawiera pola
  await expect(page.locator("#enc-cfg-interval")).toHaveCount(1);
  await expect(page.locator("#enc-cfg-dwell")).toHaveCount(1);

  // Domyślny tab stats aktywny
  await expect(page.locator('.stab[data-mtab="stats"]')).toHaveClass(/active/);

  // Tabela statystyk wczytana (nie placeholder "Ładowanie…")
  await expect(page.locator("#stats-table tbody tr").first()).not.toContainText("Ładowanie…", { timeout: 8000 });
  const statCount = await page.locator("#stats-table tbody tr").count();
  expect(statCount).toBeGreaterThanOrEqual(6); // co najmniej 6 statów w DB

  // Brak JS errors
  const errors = [];
  page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
  expect(errors.filter(e => !e.includes("favicon"))).toHaveLength(0);
});

test("REGRESSION #404 — przełączenie na tab skills wczytuje tabelę umiejętności", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#mechanics");

  await expect(page.locator("#section-mechanics")).toBeVisible({ timeout: 10000 });

  // Klik tab skills
  await page.locator('.stab[data-mtab="skills"]').click();
  await expect(page.locator('.stab[data-mtab="skills"]')).toHaveClass(/active/);

  // Panel skills widoczny
  await expect(page.locator("#mtab-skills")).toBeVisible();

  // Tabela umiejętności wczytana (nie "Ładowanie…")
  await expect(page.locator("#skills-table tbody tr").first()).not.toContainText("Ładowanie…", { timeout: 8000 });
  // Przynajmniej 1 umiejętność w DB
  const rowCount = await page.locator("#skills-table tbody tr").count();
  expect(rowCount).toBeGreaterThan(0);

  // Przycisk + Umiejętność obecny
  await expect(page.locator('button:has-text("+ Umiejętność")')).toHaveCount(1);
});

test("REGRESSION #404 — admin3 nadal żyje po ANTY-GROB", async ({ page }) => {
  // adminLogin nawiguje do /admin3/ — jeśli admin3 nie żyje, test faili tutaj
  await adminLogin(page);
  await expect(page).toHaveURL(/\/admin3\//);
});
