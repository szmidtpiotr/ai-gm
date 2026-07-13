/**
 * REGRESSION #1356 (WALKA-T5-FIX-a) — karta inicjatywy na starcie walki.
 * Spec 5a: na starcie walki gracz widzi OBA wyniki inicjatywy (Ty vs Wróg) + kto zaczyna.
 * Acceptance: ŻAR (/graj) montuje ekran walki z nowym overlayem InitiativeCard bez błędów
 * runtime (bundle z useInitiativeCard renderuje się poprawnie).
 *
 * Uwaga: właściwa logika (latch obu rzutów + starter z turn_order, once-per-combat_id)
 * jest domknięta DETERMINISTYCZNIE testem jednostkowym `front-v2/src/components/game/
 * combat/useInitiativeCard.test.tsx` (renderHook). Tu weryfikujemy, że nowy overlay
 * nie wywalił montażu ŻAR.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1356 — ŻAR /graj montuje się z InitiativeCard (bez błędów runtime)", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));

  const r = await page.goto("/graj/");
  expect(r && r.ok(), "GET /graj/ nie odpowiada 200 (#1356)").toBeTruthy();

  await page.waitForFunction(
    () => (document.querySelector("#root")?.children?.length ?? 0) > 0,
    null,
    { timeout: 20000 },
  );

  expect(errors, `błędy runtime ŻAR przy montażu: ${errors.join(" | ")}`).toEqual([]);
});
