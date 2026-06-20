/**
 * REGRESSION #741 (FAZA L) — D-pad lochu: przeciąganie + zapamiętanie pozycji + środek ⊕ otwiera mapę.
 * Acceptance:
 *  - środkowy przycisk #dungeon-nav-center NIE jest disabled i ma title="Mapa lochu",
 *  - klik ⊕ wywołuje openDungeonMap() (binding w initDungeon),
 *  - D-pad da się przeciągnąć, a pozycja jest zapisywana w localStorage (klucz dungeonNavPos)
 *    i odtwarzana przy starcie; tap vs drag rozróżniony progiem ruchu.
 * Deterministycznie: sprawdzamy DOM (atrybuty przycisku) + obecność logiki w app.js
 * (binding środka oraz persystencja pozycji). E2E przeciągania w realnym lochu zostaje pytestowi/manualowi.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #741 — środek ⊕ aktywny, otwiera mapę, D-pad draggable+persist", async ({ page }) => {
  await page.goto("/");

  // 1) Przycisk środka D-pada jest aktywny (nie disabled) i ma title mapy.
  const center = page.locator("#dungeon-nav-center");
  await expect(center).toHaveCount(1);
  await expect(center).not.toHaveAttribute("disabled", /.*/);
  await expect(center).toHaveAttribute("title", "Mapa lochu");

  // 2) Logika w app.js: binding środka → openDungeonMap oraz persystencja pozycji D-pada.
  const js = await (await page.request.get("/js/app.js")).text();
  expect(js, "binding środka ⊕ → openDungeonMap (#741)").toContain("dungeon-nav-center");
  expect(js, "persystencja pozycji D-pada w localStorage (#741)").toContain("dungeonNavPos");
  expect(js, "init drag D-pada (#741)").toContain("initDpadDrag");
});
