/**
 * REGRESSION #651 (B6c) — atak czarem jako rozwijane menu przy „Atak".
 * Mag: klik „Atak" otwiera arkusz z atakiem bronią + czarami atakującymi (attack/attack_aoe).
 * Nie-mag: „Atak" działa bezpośrednio. Picker Akcji odfiltrowany do nie-atakujących.
 * Acceptance: markup arkusza #combat-attack-sheet w index; app.js ma handler/populate/filtr; ?v=651.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #651 — index.html ma arkusz #combat-attack-sheet i świeży ?v=651", async ({ page }) => {
  const r = await page.request.get("/");
  expect(r.ok()).toBeTruthy();
  const html = await r.text();
  expect(html.includes('id="combat-attack-sheet"'), "brak arkusza #combat-attack-sheet (#651)").toBeTruthy();
  expect(html.includes('id="combat-attack-sheet-list"'), "brak listy arkusza ataku (#651)").toBeTruthy();
  const m = html.match(/app\.js\?v=([^"']+)/);
  expect(m && m[1].includes("651"), `?v= nie zbumpowane do 651 (jest: ${m && m[1]})`).toBeTruthy();
});

test("REGRESSION #651 — app.js: handler ataku rozgałęziony + menu czarów atakujących", async ({ page }) => {
  const r = await page.request.get("/js/app.js");
  expect(r.ok()).toBeTruthy();
  const src = await r.text();

  // Klik „Atak" idzie przez onCombatAttackButton (mag → menu, reszta → bezpośredni atak).
  expect(/onCombatAttackButton/.test(src), "brak onCombatAttackButton (#651)").toBeTruthy();
  expect(/btnCombatAttack\?\.addEventListener\(\s*['"]click['"]\s*,\s*onCombatAttackButton/.test(src),
    "klik Atak nie podpiety do onCombatAttackButton (#651)").toBeTruthy();
  // Mag rozgałęzia do menu.
  expect(/_combatIsScholar\s*\(\)/.test(src), "brak rozgałęzienia scholar→menu (#651)").toBeTruthy();
  expect(/function populateAttackSheet/.test(src), "brak populateAttackSheet (#651)").toBeTruthy();

  // Menu zawiera tylko czary atakujące (attack/attack_aoe) + atak bronią.
  const popStart = src.indexOf("async function populateAttackSheet");
  const popBody = src.slice(popStart, popStart + 2000);
  expect(/attack_aoe/.test(popBody) && /'attack'|"attack"/.test(popBody),
    "menu nie filtruje czarów atakujących (#651)").toBeTruthy();
  // pozycja ataku bronią jest w helperze _attackSheetWeaponHtml (poza ciałem populate) → szukaj w całym src
  expect(/data-attack-mode="weapon"/.test(src), "menu nie ma pozycji ataku bronią (#651)").toBeTruthy();

  // Picker Akcji (openSpellPicker) odfiltrowany do NIE-atakujących.
  const pickStart = src.indexOf("async function openSpellPicker");
  const pickBody = src.slice(pickStart, pickStart + 1500);
  expect(/spell_type\s*!==\s*['"]attack['"]/.test(pickBody),
    "openSpellPicker nie wyklucza czarów atakujących (#651)").toBeTruthy();
});
