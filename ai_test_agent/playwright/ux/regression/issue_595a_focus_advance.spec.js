/**
 * REGRESSION #595a — Po zabiciu wroga z focusem cel przeskakuje na następnego żywego.
 * Bug: focus był CZYSZCZONY po śmierci celu → gracz tracił celowanie / marnował atak.
 * Fix: `_nextLivingEnemyId` zwraca następnego żywego wroga (kolejność inicjatywy).
 * Acceptance: helper przeskakuje na kolejnego, zawija na początek, nie zwraca martwego.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #595a — focus przeskakuje na następnego żywego wroga", async ({ page }) => {
  // app.js wystawia _nextLivingEnemyId na window przy ładowaniu (przed logowaniem).
  await page.goto("/index.html");
  await page.waitForFunction(() => typeof window._nextLivingEnemyId === "function");

  const cases = await page.evaluate(() => {
    const order = ["e1", "player", "e2", "e3"];
    const mk = (over) => [
      { id: "e1", hp_current: over.e1 ?? 10 },
      { id: "e2", hp_current: over.e2 ?? 10 },
      { id: "e3", hp_current: over.e3 ?? 10 },
    ];
    return {
      // e2 (focus) ginie → następny żywy po e2 w kolejności = e3
      next_after_dead: window._nextLivingEnemyId(mk({ e2: 0 }), order, "e2"),
      // e3 (ostatni) ginie → zawija na pierwszego żywego = e1
      wrap_to_first: window._nextLivingEnemyId(mk({ e3: 0 }), order, "e3"),
      // e2 ginie, e3 też martwy → zawija na e1
      skip_dead_wrap: window._nextLivingEnemyId(mk({ e2: 0, e3: 0 }), order, "e2"),
      // wszyscy martwi → null
      all_dead: window._nextLivingEnemyId(mk({ e1: 0, e2: 0, e3: 0 }), order, "e2"),
    };
  });

  expect(cases.next_after_dead, "po zabiciu e2 → e3").toBe("e3");
  expect(cases.wrap_to_first, "po zabiciu ostatniego e3 → zawinięcie na e1").toBe("e1");
  expect(cases.skip_dead_wrap, "pomija martwego e3 → e1").toBe("e1");
  expect(cases.all_dead, "brak żywych → null").toBeNull();
});
