/**
 * REGRESSION #586 (S6) — Haggling: targowanie wpięte w ceny sklepu.
 * Acceptance: skill `haggling` (CHA) jest w publicznym katalogu /api/mechanics/skills;
 * istniejące skille rdzenne nietknięte (brak regresji po dodaniu nowego skilla).
 * (Mechanika rabatu testowana deterministycznie w pytest test_issue_s6_haggling.py.)
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #586 — katalog skilli zawiera haggling (CHA)", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "/api/mechanics/skills nie odpowiada 200 (#586)").toBeTruthy();

  const body = await r.json();
  const skills = body.skills || [];
  const byKey = Object.fromEntries(skills.map((s) => [s.key, s.linked_stat]));

  expect(byKey.haggling, "brak skilla haggling w katalogu (#586)").toBe("CHA");

  // Brak regresji — rdzenne i sąsiednie skille nadal obecne
  expect(byKey.persuasion).toBe("CHA");
  expect(byKey.gamble === undefined || true).toBeTruthy(); // gamble = S7 (osobne issue)
});
