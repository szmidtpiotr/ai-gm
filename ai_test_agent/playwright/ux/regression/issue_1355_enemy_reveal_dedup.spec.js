/**
 * REGRESSION #1355 (WALKA-T1-FIX) — dubel karty pojawienia wroga przy zasadzce.
 * Karta „Nieznany napastnik / STAŃ DO WALKI" nie może dublować modalu zasadzki.
 * Acceptance: ŻAR (/graj) montuje ekran walki po refaktorze useEnemyReveal bez błędów
 * runtime, a katalog stanu walki (EnemyRevealCard) renderuje pojedynczy overlay.
 *
 * Uwaga: właściwy wyścig efektów (efekt dziecka przed efektem rodzica) jest domknięty
 * DETERMINISTYCZNIE testem jednostkowym `front-v2/src/components/game/combat/
 * useEnemyReveal.test.tsx` (renderHook: suppress-at-mount → brak karty; suppress
 * po montażu → safety-net czyści). Tu weryfikujemy, że refaktor nie wywalił montażu ŻAR.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1355 — ŻAR /graj montuje się po refaktorze useEnemyReveal (bez błędów runtime)", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));

  const r = await page.goto("/graj/");
  expect(r && r.ok(), "GET /graj/ nie odpowiada 200 (#1355)").toBeTruthy();

  // #root musi się zapełnić (nie biały ekran) — potwierdza że bundle z useEnemyReveal
  // wyrenderował aplikację (ekran logowania ŻAR albo gra).
  await page.waitForFunction(
    () => (document.querySelector("#root")?.children?.length ?? 0) > 0,
    null,
    { timeout: 20000 },
  );

  expect(errors, `błędy runtime ŻAR przy montażu: ${errors.join(" | ")}`).toEqual([]);
});
