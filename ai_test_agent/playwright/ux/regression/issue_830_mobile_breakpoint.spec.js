/**
 * REGRESSION #830 (MOBILE M0-1) — admin nie może renderować się jak pomniejszony desktop @390px.
 * Prawdziwy mechanizm: szeroki element (np. .data-table min-width:560px) rozpycha LAYOUT VIEWPORT
 *   z 390px do ~szerokości treści (Chrome Android wide-viewport). Cała strona (900px) jest wtedy
 *   skalowana w dół do 390px ekranu → "pomniejszony desktop", mikro tekst. @media(max-width:768px)
 *   wciąż matchuje (Chrome liczy je względem device-width), ale to nie ratuje — strona i tak jest
 *   zeskalowana. Guard: html,body{overflow-x:hidden; max-width:100vw} przycina nadmiar → layout
 *   viewport zostaje 390px → render w realnej skali.
 * Acceptance: @390px (emulacja mobile) layout viewport NIE rozszerza się ponad szerokość ekranu,
 *   brak poziomego scrolla strony — NAWET gdy w DOM jest element szerszy niż viewport.
 */
const { test, expect } = require("@playwright/test");

// Emulacja realnego telefonu (isMobile honoruje <meta viewport> + wide-viewport jak Chrome
// Android, w przeciwieństwie do zwykłego resize desktopowego chromium).
test.use({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
  deviceScaleFactor: 3,
});

test("REGRESSION #830 — wide content nie rozpycha layout viewport @390px", async ({ page }) => {
  await page.goto("/admin/");

  // Sanity: na czystej stronie layout viewport = szerokość ekranu, breakpoint matchuje.
  const base = await page.evaluate(() => ({
    iw: window.innerWidth,
    mq: window.matchMedia("(max-width: 768px)").matches,
  }));
  expect(base.iw, "bazowy layout viewport != 390 (#830)").toBeLessThanOrEqual(391);
  expect(base.mq, "breakpoint 768px nie matchuje @390px (#830)").toBeTruthy();

  // Wstrzykujemy element znacznie szerszy niż viewport (symuluje .data-table / szeroką sekcję
  // wyrenderowaną poza kontenerem scrolla). Bez globalnego guardu rozpycha layout viewport.
  await page.evaluate(() => {
    const d = document.createElement("div");
    d.id = "issue830-probe";
    d.style.cssText = "width:900px;height:40px;";
    document.body.appendChild(d);
  });
  await page.waitForTimeout(200);

  const state = await page.evaluate(() => ({
    innerW: window.innerWidth,
    rootScrollW: document.documentElement.scrollWidth,
    probeW: document.getElementById("issue830-probe").getBoundingClientRect().width,
  }));

  // KLUCZ: szeroki element NIE może rozszerzyć layout viewportu ponad szerokość ekranu.
  // Bez fixu Chrome-mobile rozszerza innerWidth do ~900 → cała strona skalowana w dół.
  expect(
    state.innerW,
    `layout viewport rozepchnięty do ${state.innerW}px przez szeroki element — strona zostanie zeskalowana (shrunk desktop) (#830)`
  ).toBeLessThanOrEqual(391);
  // Strona nie może mieć poziomego scrolla strony.
  expect(
    state.rootScrollW,
    `strona przewija się poziomo: scrollWidth=${state.rootScrollW} (#830)`
  ).toBeLessThanOrEqual(391);
});
