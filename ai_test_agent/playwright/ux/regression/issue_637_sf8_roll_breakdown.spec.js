/**
 * REGRESSION #637 (SF8) — karta rzutu rozbija wynik po NAZWANYM źródle.
 * Acceptance:
 *  - window.sf8AttackBreakdown(attackRoll, extras) zwraca uporządkowaną listę
 *    {label, value} z już policzonych pól (stat/ranga/biegłość/oburęczny/zaskoczenie/
 *    zniszczona broń). Stat zawsze obecny; pozostałe składniki = 0 odfiltrowane.
 *  - window.sf8SkillBreakdown(modBreakdown) analogicznie dla testu umiejętności.
 *  - Etykiety stata po polsku (Siła/Zręczność/...). Front NIC nie liczy — suma
 *    składników jest spójna z modyfikatorem silnika (total = d20 + Σ value).
 * Kontrakt JS (deterministyczny, bez LLM) — czysta prezentacja.
 */
const { test, expect } = require("@playwright/test");

async function loadPlayerApp(page) {
  await page.goto("/");
  await page.waitForFunction(
    () => typeof window.sf8AttackBreakdown === "function" && typeof window.sf8SkillBreakdown === "function",
    null,
    { timeout: 15000 }
  );
}

test("REGRESSION #637 — sf8AttackBreakdown nazywa wszystkie policzone składniki ataku", async ({ page }) => {
  await loadPlayerApp(page);

  // d20=12, total=17: stat +2 (DEX), ranga +1, biegłość +2, oburęczny 0 → pominięty.
  const out = await page.evaluate(() =>
    window.sf8AttackBreakdown(
      { attack_stat: "DEX", stat_mod: 2, skill_rank: 1, proficiency: 2, weapon_bonus: 0, raw: 12, total: 17 },
      {}
    )
  );
  const labels = out.map((p) => p.label);
  expect(labels, "stat po polsku obecny").toContain("Zręczność");
  expect(labels, "ranga obecna").toContain("Ranga");
  expect(labels, "biegłość obecna").toContain("Biegłość");
  expect(labels, "oburęczny=0 odfiltrowany").not.toContain("Oburęczny");
  // ≥2 nazwane składniki, nie sama suma
  expect(out.length).toBeGreaterThanOrEqual(2);
  // front nic nie liczy: d20 + Σ value = total silnika
  const sum = out.reduce((a, p) => a + p.value, 0);
  expect(12 + sum, "suma składników + d20 = total silnika").toBe(17);
});

test("REGRESSION #637 — sf8AttackBreakdown pokazuje kary (oburęczny −2, zniszczona broń) i extras", async ({ page }) => {
  await loadPlayerApp(page);
  const out = await page.evaluate(() =>
    window.sf8AttackBreakdown(
      { attack_stat: "STR", stat_mod: 3, skill_rank: 0, proficiency: 0, weapon_bonus: -2, raw: 8, total: 11 },
      { surprise: 2, durability: -1 }
    )
  );
  const byLabel = Object.fromEntries(out.map((p) => [p.label, p.value]));
  expect(byLabel["Siła"]).toBe(3);
  expect(byLabel["Oburęczny"], "kara oburęczna −2").toBe(-2);
  expect(byLabel["Zaskoczenie"]).toBe(2);
  expect(byLabel["Zniszczona broń"]).toBe(-1);
  expect(out, "ranga/biegłość=0 odfiltrowane").not.toEqual(expect.arrayContaining([expect.objectContaining({ label: "Ranga" })]));
});

test("REGRESSION #637 — sf8AttackBreakdown: stat ZAWSZE obecny nawet gdy 0", async ({ page }) => {
  await loadPlayerApp(page);
  const out = await page.evaluate(() =>
    window.sf8AttackBreakdown({ attack_stat: "INT", stat_mod: 0, skill_rank: 0, proficiency: 0, weapon_bonus: 0 }, {})
  );
  expect(out.length, "tylko stat zostaje").toBe(1);
  expect(out[0].label).toBe("Inteligencja");
  expect(out[0].value).toBe(0);
});

test("REGRESSION #637 — sf8SkillBreakdown nazywa składniki testu umiejętności", async ({ page }) => {
  await loadPlayerApp(page);
  const out = await page.evaluate(() =>
    window.sf8SkillBreakdown({ governing_stat: "WIS", stat_mod: 1, skill_rank: 3, proficiency: 2, total: 6 })
  );
  const byLabel = Object.fromEntries(out.map((p) => [p.label, p.value]));
  expect(byLabel["Mądrość"]).toBe(1);
  expect(byLabel["Ranga"]).toBe(3);
  expect(byLabel["Biegłość"]).toBe(2);
  const sum = out.reduce((a, p) => a + p.value, 0);
  expect(sum, "suma składników = total modyfikatora").toBe(6);
});

// Uwaga: render rozbicia w OKNIE kości (playCombatDiceRoll) zależy od biblioteki 3D
// (DICE.dice_box), niestabilnej w headless — weryfikowany wizualnie (screenshot 390px),
// nie automatem. Logikę składników pokrywają helpery powyżej; wiring dymka pokryty ręcznie.

test("REGRESSION #637 — app.js wystawia helpery SF8 na window", async ({ page }) => {
  const src = await page.request.get("/js/app.js");
  expect(src.ok(), "app.js dostępny").toBeTruthy();
  const body = await src.text();
  expect(body.includes("window.sf8AttackBreakdown"), "sf8AttackBreakdown na window").toBeTruthy();
  expect(body.includes("window.sf8SkillBreakdown"), "sf8SkillBreakdown na window").toBeTruthy();
});
