/**
 * REGRESSION #1357 (WALKA-T5-FIX-b) — rzut uniku wroga widoczny liczbowo na karcie ataku.
 * Spec 5b: po ataku gracza karta pokazuje OBIE strony liczbowo (Twój atak vs unik wroga:
 * d20+DEX=suma) + werdykt. Semantyka #826: zwykłe pudło = udany unik wroga; „PUDŁO"
 * tylko przy Nat 1 gracza.
 *
 * Uwaga: właściwa logika (komórka „Unik" z rozbiciem d20+mod=suma, przeżycie filtra
 * NA TRAFIENIE, poprawka #826 PUDŁO-tylko-Nat1) jest domknięta DETERMINISTYCZNIE testem
 * jednostkowym `front-v2/src/lib/combat.test.ts`. Tu weryfikujemy, że nowa gałąź kart
 * rzutu nie wywaliła montażu ŻAR (bundle z dodgeCells renderuje się poprawnie).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1357 — ŻAR /graj montuje się z kartą uniku wroga (bez błędów runtime)", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));

  const r = await page.goto("/graj/");
  expect(r && r.ok(), "GET /graj/ nie odpowiada 200 (#1357)").toBeTruthy();

  await page.waitForFunction(
    () => (document.querySelector("#root")?.children?.length ?? 0) > 0,
    null,
    { timeout: 20000 },
  );

  expect(errors, `błędy runtime ŻAR przy montażu: ${errors.join(" | ")}`).toEqual([]);
});
