/**
 * REGRESSION #601 (S7) — Gamble: hazard z prawdziwą stawką złota.
 * Acceptance: skill `gamble` (CHA) jest w publicznym katalogu /api/mechanics/skills;
 * istniejące skille (haggling/persuasion) nietknięte (brak regresji po dodaniu skilla).
 * (Mechanika stawki/wypłaty/limitu testowana deterministycznie w pytest test_issue601_gamble.py.)
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #601 — katalog skilli zawiera gamble (CHA)", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "/api/mechanics/skills nie odpowiada 200 (#601)").toBeTruthy();

  const body = await r.json();
  const skills = body.skills || [];
  const byKey = Object.fromEntries(skills.map((s) => [s.key, s.linked_stat]));

  expect(byKey.gamble, "brak skilla gamble w katalogu (#601)").toBe("CHA");

  // Brak regresji — sąsiednie skille (S5/S6) i rdzenne nadal obecne
  expect(byKey.haggling).toBe("CHA");
  expect(byKey.persuasion).toBe("CHA");
});
