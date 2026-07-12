/**
 * REGRESSION #1350 (WALKA-T2) — piguła „Obrona" wg skilli postaci. Composer maga renderuje
 * opcje z backendowego `defense_options`, a nie hardcoded unik/blok. Ten test pilnuje
 * kontraktu katalogu skilli, z którego backend buduje `defense_options` dla obu reakcji
 * magicznych (Arkanowa Bariera #1324 + Tarcza Many #1325) — źródło opcji obrony maga.
 * Acceptance: /api/mechanics/skills zwraca arcane_ward ORAZ mana_shield jako reakcje INT.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1350 — obie reakcje magiczne w katalogu (źródło defense_options)", async ({
  page,
}) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "katalog skilli nie odpowiada 200 (#1350)").toBeTruthy();
  const body = await r.json();
  const rows = Array.isArray(body) ? body : body.skills || [];

  const ward = rows.find((s) => s && s.key === "arcane_ward");
  const shield = rows.find((s) => s && s.key === "mana_shield");

  expect(ward, "brak arcane_ward — composer nie pokaże Arkanowej Bariery (#1350)").toBeTruthy();
  expect(shield, "brak mana_shield — composer nie pokaże Tarczy Many (#1350)").toBeTruthy();
  // Obie to reakcje INT (magiczny odpowiednik uniku/bloku) — parytet z _reaction_options.
  expect(ward.linked_stat, "arcane_ward musi być testem INT").toBe("INT");
  expect(shield.linked_stat, "mana_shield musi być testem INT").toBe("INT");
});
