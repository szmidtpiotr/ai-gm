/**
 * REGRESSION #624 (B1) — Łotrzyk dostaje DEX+2/LCK+1, nie bonusy maga (INT/WIS).
 * Acceptance: kreator (app.js ARCHETYPE_BONUS) obiecuje rogue = {DEX:2, LCK:1};
 * backend musi nadać dokładnie to samo (spójność kreator↔postać, lekcja #618).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #624 — kreator obiecuje rogue DEX+2/LCK+1", async ({ page }) => {
  const r = await page.request.get("/js/app.js");
  expect(r.ok(), "app.js nie serwuje się (200)").toBeTruthy();
  const src = await r.text();

  // Wyłuskaj mapowanie ARCHETYPE_BONUS z kreatora.
  const m = src.match(/const ARCHETYPE_BONUS\s*=\s*(\{[^;]*\})/);
  expect(m, "brak stałej ARCHETYPE_BONUS w app.js").toBeTruthy();
  const bonus = eval(`(${m[1]})`);

  // Łotrzyk: DEX+2, LCK+1 — i ŻADNYCH bonusów maga.
  expect(bonus.rogue).toEqual({ DEX: 2, LCK: 1 });
  expect(bonus.rogue.INT, "rogue nie powinien dostawać INT").toBeUndefined();
  expect(bonus.rogue.WIS, "rogue nie powinien dostawać WIS").toBeUndefined();

  // Brak regresji u pozostałych klas.
  expect(bonus.warrior).toEqual({ STR: 2, CON: 1 });
  expect(bonus.scholar).toEqual({ INT: 2, WIS: 1 });
});
