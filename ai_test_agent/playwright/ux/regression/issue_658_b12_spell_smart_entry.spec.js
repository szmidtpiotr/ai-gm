/**
 * REGRESSION #658 (B12) — Kreator AI (Smart Entry) obsługuje czary.
 * Przed fixem: klik "🤖 Kreator AI" na zakładce Czary dawał toast "nie obsługuje tej zakładki"
 * (mapa _openSmartEntryForCurrentTab nie znała 'spells'; dropdown SE_TABLE_LABELS bez czarów).
 * Acceptance: na zakładce Czary klik Kreator AI otwiera overlay Smart Entry z tabelą
 * game_config_spells, a dropdown tabel zawiera pozycję "Czary".
 */
const { test, expect } = require("@playwright/test");

async function adminLogin(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
}

test("REGRESSION #658 — Kreator AI otwiera Smart Entry dla czarów z zakładki Czary", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#content");

  await expect(page.locator("#section-content")).toBeVisible({ timeout: 10000 });

  // Przełącz na zakładkę Czary
  await page.locator('#content-tabs .stab[data-tab="spells"]').click();
  await expect(page.locator("#stab-spells")).toHaveClass(/active/);

  // Klik Kreator AI — przed fixem to dawało toast "nie obsługuje" i NIE otwierało overlay
  await page.locator("#content-kreator-btn").click();

  // Overlay Smart Entry musi być widoczny i ustawiony na tabelę czarów
  const overlay = page.locator("#smart-entry-overlay");
  await expect(overlay).toHaveClass(/visible/, { timeout: 5000 });
  await expect(page.locator("#se-table-select")).toHaveValue("game_config_spells");
});

test("REGRESSION #658 — dropdown tabel Kreatora zawiera pozycję Czary", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#content");

  await expect(page.locator("#section-content")).toBeVisible({ timeout: 10000 });

  // Otwórz Kreator AI z dowolnej zakładki (domyślnie weapons)
  await page.locator("#content-kreator-btn").click();
  await expect(page.locator("#smart-entry-overlay")).toHaveClass(/visible/, { timeout: 5000 });

  // Dropdown musi mieć opcję game_config_spells
  const spellOption = page.locator('#se-table-select option[value="game_config_spells"]');
  await expect(spellOption).toHaveCount(1);
});
