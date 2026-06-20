/**
 * REGRESSION #719 (L-fix) — modal kości pokazuje rzut wroga na unik (test opozycyjny).
 * Acceptance: w grze modal ataku dopisuje linię "🛡 Unik wroga: …" + werdykt trafienie/pudło.
 * Spec deterministyczny: weryfikuje, że serwowany bundle frontu nadal NAZYWA dane uniku
 * (dice-dodge-line / "Unik wroga" / werdykty) i że styl tej linii istnieje. Pełny e2e przez
 * walkę z LLM jest niestabilny → logikę silnika pokrywa pytest (test_issue719_dodge_modal_contract).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #719 — front serwuje render linii uniku w modalu kości", async ({ page }) => {
  const appResp = await page.request.get("/js/app.js");
  expect(appResp.ok(), "app.js nie serwowany 200 (#719)").toBeTruthy();
  const app = await appResp.text();

  // render linii uniku wroga
  expect(app.includes("dice-dodge-line"), "brak klasy dice-dodge-line w app.js (#719)").toBeTruthy();
  expect(app.includes("Unik wroga"), "brak etykiety 'Unik wroga' (#719)").toBeTruthy();
  // werdykt hit/miss
  expect(app.includes("Wróg uniknął ciosu"), "brak werdyktu pudła (#719)").toBeTruthy();
  expect(app.includes("dice-verdict-hit"), "brak klasy werdyktu trafienia (#719)").toBeTruthy();
  // oba call-site przekazują dodge_roll z backendu
  expect(app.includes("data.dodge_roll"), "call-site nie przekazuje data.dodge_roll (#719)").toBeTruthy();
});

test("REGRESSION #719 — styl linii uniku obecny w bundlu CSS", async ({ page }) => {
  const cssResp = await page.request.get("/css/styles.css");
  expect(cssResp.ok(), "styles.css nie serwowany 200 (#719)").toBeTruthy();
  const css = await cssResp.text();
  expect(css.includes(".dice-dodge-line"), "brak reguły .dice-dodge-line (#719)").toBeTruthy();
  expect(css.includes("dice-verdict-hit"), "brak reguły werdyktu trafienia (#719)").toBeTruthy();
  expect(css.includes("dice-verdict-miss"), "brak reguły werdyktu pudła (#719)").toBeTruthy();
});
