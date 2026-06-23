/**
 * REGRESSION #967 (interface-design) — kompaktowy combat banner (Wariant D).
 * Każdy uczestnik = JEDNA linia .cline z inline HP barem; żadna obecna dana nie zniknęła:
 * HP liczby + pasek, DEF, INI, strefa (🗡/🏹), warunki, cel (🎯). Banner niższy o ≥40%.
 * Acceptance: window.combatLineHtml(c, opts) zwraca pojedynczą linię z .cline__hpbar i kompletem danych.
 */
const { test, expect } = require("@playwright/test");

async function loadHelper(page) {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.combatLineHtml === "function", null, { timeout: 20000 });
}

test("REGRESSION #967 — linia wroga: kompakt + HP bar + wszystkie dane", async ({ page }) => {
  await loadHelper(page);
  const html = await page.evaluate(() => window.combatLineHtml(
    { type: "enemy", id: 7, name: "Nieumarły Mistrz", hp_current: 16, hp_max: 20,
      defense: 13, initiative_roll: 1, zone: "engaged",
      conditions: [{ key: "bleeding", label: "Krwawienie" }] },
    { isActive: true, isTarget: true }
  ));
  expect(html).toContain("cline");                 // jednoliniowy root
  expect(html).toContain("cline__hpbar");          // pasek HP wrócił (regresja v1)
  expect(html).toMatch(/16\s*\/\s*20/);            // liczby HP
  expect(html).toContain("DEF");
  expect(html).toContain("13");                    // DEF wartość
  expect(html).toContain("INI");
  expect(html).toContain("🎯");                    // wybrany cel
  expect(html).not.toContain("combat-combatant__hp-row");  // nie stara wieloliniowa karta
});

test("REGRESSION #967 — linia gracza: TY + HP bar + DEF, kompakt", async ({ page }) => {
  await loadHelper(page);
  const html = await page.evaluate(() => window.combatLineHtml(
    { type: "player", name: "Mizel", hp_current: 9, hp_max: 12, defense: 13,
      initiative_roll: 14, zone: "engaged", conditions: [] },
    { isActive: true }
  ));
  expect(html).toContain("cline__hpbar");
  expect(html).toMatch(/9\s*\/\s*12/);
  expect(html).toContain("TY");
  expect(html).toContain("DEF");
});
