/**
 * REGRESSION #619 (SF1) — pasek walki zwinięty do 3 filarów + bottom sheet.
 * Acceptance: w composerze walki są DOKŁADNIE 3 przyciski (Atak / Akcja ▾ / Ucieczka),
 * a pozostałe akcje (Zaklęcie/Zbliż-Cofnij/Unik/Blok/Zapasy) żyją w arkuszu #combat-action-sheet.
 * Test sprawdza statyczną strukturę DOM (markup obecny niezależnie od loginu/walki).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #619 — composer ma dokładnie 3 filary", async ({ page }) => {
  await page.goto("/");
  // Bezpośrednie dzieci-przyciski composera walki (markup statyczny, hidden do walki).
  const bar = page.locator("#combat-composer > button");
  await expect(bar, "composer powinien mieć 3 przyciski (#619 SF1)").toHaveCount(3);
  // Trzy filary po id.
  await expect(page.locator("#combat-attack-btn"), "brak Atak").toHaveCount(1);
  await expect(page.locator("#combat-action-btn"), "brak Akcja ▾ (#619)").toHaveCount(1);
  await expect(page.locator("#combat-flee-btn"), "brak Ucieczka").toHaveCount(1);
});

test("REGRESSION #619 — reszta akcji przeniesiona do arkusza", async ({ page }) => {
  await page.goto("/");
  const sheet = page.locator("#combat-action-sheet");
  await expect(sheet, "brak kontenera arkusza #combat-action-sheet (#619)").toHaveCount(1);
  // 5 przeniesionych przycisków musi żyć WEWNĄTRZ arkusza (te same id = te same handlery).
  for (const id of [
    "combat-spell-btn",
    "combat-move-btn",
    "combat-dodge-btn",
    "combat-block-btn",
    "combat-wrestle-btn",
  ]) {
    await expect(
      page.locator(`#combat-action-sheet #${id}`),
      `przycisk #${id} nie jest w arkuszu (#619)`
    ).toHaveCount(1);
  }
  // Te przyciski NIE mogą już wisieć bezpośrednio w pasku.
  await expect(
    page.locator("#combat-composer > #combat-move-btn"),
    "Zbliż/Cofnij nadal w pasku zamiast w arkuszu (#619)"
  ).toHaveCount(0);
});

test("REGRESSION #619 — arkusz domyślnie ukryty + ma backdrop i listę", async ({ page }) => {
  await page.goto("/");
  // Arkusz istnieje, ale jest ukryty do czasu otwarcia (atrybut hidden).
  await expect(page.locator("#combat-action-sheet")).toBeHidden();
  await expect(
    page.locator("#combat-action-sheet-backdrop"),
    "arkusz musi mieć tło zamykające (#619)"
  ).toHaveCount(1);
  await expect(
    page.locator("#combat-action-sheet-list"),
    "arkusz musi mieć listę pozycji (#619)"
  ).toHaveCount(1);
  // Filar „Akcja" jest podpięty (handler otwierający — weryfikacja kliknięcia wizualnie w Sandbox/game-screen).
  await expect(page.locator("#combat-action-btn[aria-haspopup='dialog']")).toHaveCount(1);
});
