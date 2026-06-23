/**
 * REGRESSION #967 (interface-design) — kompaktowy combat banner (Wariant D).
 * Każdy uczestnik = JEDNA linia .cline z inline HP barem; żadna obecna dana nie zniknęła:
 * HP liczby + pasek, DEF, INI, strefa (🗡/🏹), warunki, cel (🎯). Banner niższy o ≥40%.
 * Dodatkowo: w walce pasek przygody NIE chowa się przy scrollu (górna belka nie ucieka).
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

test("REGRESSION #967 — w walce pasek przygody NIE chowa się przy scrollu (belka nie ucieka)", async ({ page }) => {
  await loadHelper(page);
  // Przygotuj scrollowalny chat (wymuszona wysokość — bez pełnego layoutu gry).
  await page.evaluate(() => {
    const gs = document.getElementById("game-screen");
    gs.classList.add("screen--active"); gs.hidden = false;
    const cm = document.getElementById("chat-messages");
    cm.style.cssText = "height:200px;overflow-y:auto;display:block";
    cm.innerHTML = "";
    for (let i = 0; i < 40; i++) { const d = document.createElement("div"); d.style.cssText = "height:40px"; cm.appendChild(d); }
  });
  const scrollDown = () => page.evaluate(() => {
    const cm = document.getElementById("chat-messages");
    cm.scrollTop = 0; cm.dispatchEvent(new Event("scroll"));
    cm.scrollTop = cm.scrollHeight; cm.dispatchEvent(new Event("scroll"));
  });

  // Kontrola: BEZ banera walki pasek się chowa przy scrollu w dół (auto-hide #952 działa).
  await page.evaluate(() => {
    document.getElementById("combat-banner").hidden = true;
    document.querySelector(".header--game").classList.remove("header--hidden");
  });
  await scrollDown();
  await page.waitForTimeout(150);
  const hiddenNoCombat = await page.evaluate(() => document.querySelector(".header--game").classList.contains("header--hidden"));
  expect(hiddenNoCombat).toBe(true);   // auto-hide aktywne poza walką

  // W walce: ten sam scroll w dół NIE chowa paska — brak 50px luki nad banerem.
  await page.evaluate(() => {
    document.getElementById("combat-banner").hidden = false;
    document.querySelector(".header--game").classList.remove("header--hidden");
  });
  await scrollDown();
  await page.waitForTimeout(150);
  const hiddenInCombat = await page.evaluate(() => document.querySelector(".header--game").classList.contains("header--hidden"));
  expect(hiddenInCombat).toBe(false);  // pasek trzyma się góry — belka nie ucieka
});
