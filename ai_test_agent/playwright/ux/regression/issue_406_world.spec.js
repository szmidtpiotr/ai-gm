/**
 * REGRESSION #406 (FADM-P4) — Port sekcji world → modularny admin/.
 * Acceptance: /admin/#world renderuje sekcję z 4 tabami (npcs/enemies/loot/pending),
 * tabela NPC i wrogów ładuje dane z API, sekcja działa w /admin/.
 */
const { test, expect } = require("@playwright/test");

async function adminLogin(page) {
  // FADM-P16: token przez API + addInitScript → seed localStorage PRZED skryptami strony.
  // Brak goto tutaj: unika otwarcia login-overlay (P13), który przy nawigacji hash-only
  // nie znika i przechwytywał kliknięcia w sekcjach.
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
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

