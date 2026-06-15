/**
 * REGRESSION #650 (B6b) — atak czarem jest oznaczany dla narracji jako MAGIA, nie broń.
 * Bug: narracja po czarze opisywała cios wyposażoną laską (LLM nie wiedział, że to zaklęcie).
 * Fix front: _handleCombatAttackResult dorzuca attack_mode:'spell' + spell_label do payloadu
 * narracji, gdy atak jest czarem. Backend (_user_text_for_llm_context) zamienia to na
 * instrukcję magii — pokryte pytest test_issue650_b6b_spell_narration.py.
 * Acceptance: serwowany app.js niesie znacznik spell w payloadzie narracji; index ?v= świeże.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #650 — app.js znakuje atak czarem (attack_mode spell) dla narracji", async ({ page }) => {
  const r = await page.request.get("/js/app.js");
  expect(r.ok(), "app.js nie serwuje się (200)").toBeTruthy();
  const src = await r.text();

  // Payload narracji ataku dostaje gałąź spell.
  expect(/attack_mode\s*=\s*['"]spell['"]/.test(src),
    "brak oznaczenia attack_mode='spell' w app.js (#650)").toBeTruthy();
  expect(/spell_label\s*=/.test(src),
    "brak spell_label w payloadzie narracji (#650)").toBeTruthy();
  // Detekcja po typie broni 'spell' / teście 'spell_attack'.
  expect(/weapon_type[\s\S]{0,40}['"]spell['"]/.test(src) || /['"]spell_attack['"]/.test(src),
    "brak detekcji czaru (weapon_type spell / spell_attack) w app.js (#650)").toBeTruthy();
});

test("REGRESSION #650 — index.html ładuje app.js z wersjonowanym importem (cache-bust)", async ({ page }) => {
  const r = await page.request.get("/");
  expect(r.ok()).toBeTruthy();
  const html = await r.text();
  const m = html.match(/app\.js\?v=([^"']+)/);
  // Wersja rośnie z każdym taskiem — sprawdzamy obecność wersjonowania; treść fixu pokrywa
  // test backendu (pytest) + test markera attack_mode w app.js powyżej.
  expect(m, "brak wersjonowanego importu app.js").toBeTruthy();
});
