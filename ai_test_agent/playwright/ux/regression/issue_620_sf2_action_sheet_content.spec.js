/**
 * REGRESSION #620 (SF2) — zawartość arkusza akcji: koszt tury + opis + powód niedostępności.
 * Acceptance: każda pozycja arkusza ma znacznik kosztu (⏳ tura akcji / ↺ reakcja),
 * 1-linijkowy opis i element powodu wyszarzenia. Reakcje (Unik/Blok) = ↺, akcje (Zaklęcie/
 * Zbliż-Cofnij/Zapasy) = ⏳. Test sprawdza statyczną strukturę DOM (markup niezależny od walki).
 */
const { test, expect } = require("@playwright/test");

// Pozycje arkusza: id → oczekiwany glif kosztu.
const ACTION_BTNS = ["combat-spell-btn", "combat-move-btn", "combat-wrestle-btn"]; // ⏳ tura
const REACTION_BTNS = ["combat-dodge-btn", "combat-block-btn"]; // ↺ reakcja

test("REGRESSION #620 — każda pozycja arkusza ma koszt, opis i powód", async ({ page }) => {
  await page.goto("/");
  for (const id of [...ACTION_BTNS, ...REACTION_BTNS]) {
    const btn = page.locator(`#combat-action-sheet #${id}`);
    await expect(btn, `przycisk #${id} musi być w arkuszu (#619)`).toHaveCount(1);
    await expect(
      btn.locator(".combat-btn__cost"),
      `#${id} — brak znacznika kosztu (#620 SF2)`
    ).toHaveCount(1);
    await expect(
      btn.locator(".combat-btn__desc"),
      `#${id} — brak 1-linijkowego opisu (#620 SF2)`
    ).toHaveCount(1);
    await expect(
      btn.locator(".combat-btn__reason"),
      `#${id} — brak elementu powodu wyszarzenia (#620 SF2)`
    ).toHaveCount(1);
  }
});

test("REGRESSION #620 — akcje mają ⏳, reakcje mają ↺", async ({ page }) => {
  await page.goto("/");
  for (const id of ACTION_BTNS) {
    await expect(
      page.locator(`#${id} .combat-btn__cost`),
      `#${id} powinno być akcją (⏳ tura) (#620)`
    ).toContainText("⏳");
  }
  for (const id of REACTION_BTNS) {
    await expect(
      page.locator(`#${id} .combat-btn__cost`),
      `#${id} powinno być reakcją (↺) (#620)`
    ).toContainText("↺");
  }
});

test("REGRESSION #620 — powody niedostępności mają statyczny tekst per warunek", async ({ page }) => {
  await page.goto("/");
  // Blok → „Brak tarczy"; Zapasy → „Wymaga zwarcia"; Zaklęcie → „Za mało many".
  await expect(
    page.locator("#combat-block-btn .combat-btn__reason"),
    "Blok — powód powinien dotyczyć tarczy (#620)"
  ).toContainText(/tarcz/i);
  await expect(
    page.locator("#combat-wrestle-btn .combat-btn__reason"),
    "Zapasy — powód powinien dotyczyć zwarcia (#620)"
  ).toContainText(/zwarci/i);
  await expect(
    page.locator("#combat-spell-btn .combat-btn__reason"),
    "Zaklęcie — powód powinien dotyczyć many (#620)"
  ).toContainText(/man/i);
});
