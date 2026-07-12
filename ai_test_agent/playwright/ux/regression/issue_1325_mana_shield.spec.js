/**
 * REGRESSION #1325 (Tarcza Many) — skill `mana_shield` istnieje w katalogu i jest reakcją INT.
 * Acceptance: /api/mechanics/skills zwraca `mana_shield` (linked_stat INT, opis reakcji bojowej),
 * co gwarantuje że gate reakcji (skill ≥ 1) ma czym się zaseedować i przycisk tarczy może się pojawić.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1325 — mana_shield w katalogu skilli (reakcja INT)", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "/api/mechanics/skills nie odpowiada 200 (#1325)").toBeTruthy();
  const body = await r.json();
  const skills = Array.isArray(body) ? body : body.skills || [];
  const ms = skills.find((s) => s.key === "mana_shield");
  expect(ms, "skill 'mana_shield' brak w katalogu — seed nie wdrożony (#1325)").toBeTruthy();
  expect(String(ms.linked_stat).toUpperCase(), "mana_shield powinien być testem INT").toBe("INT");
  expect(String(ms.description || "").length, "brak opisu skilla mana_shield").toBeGreaterThan(20);
});
