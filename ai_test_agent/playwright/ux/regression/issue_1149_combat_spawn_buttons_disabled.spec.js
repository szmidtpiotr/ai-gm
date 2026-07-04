/**
 * REGRESSION #1149 — po spawnie walki z encountera (podróż PT / wejście na sub-hex) przyciski
 * walki (Atak/Akcja/Ucieczka) bywały `disabled` mimo że backend oddał turę graczowi; F5 naprawiał.
 *
 * ROOT CAUSE: `handleCombatFlee` (combat_ui.js) ustawiał `combatBusy=true; playerActionFetchActive=true`,
 * ale reset flag był TYLKO w bloku `catch` — udana ucieczka (ścieżka `try`) nie miała `finally`, więc
 * obie flagi zostawały `true` po wyjściu z walki. `hideCombatUI` też ich nie czyścił (tylko
 * `enemyTurnInFlight`). Następny encounter w podróży widział zalegające flagi:
 *   • `combatBusy=true` blokował auto-turę wroga (pollCombatState: `... && !combatBusy && ...`),
 *   • `playerActionFetchActive=true` trzymał reconciler na `fetch_in_flight` — a dla TEJ flagi
 *     reconciler NIE ma watchdoga (ma go tylko `enemyTurnFetchActive`), więc nigdy nie resyncował.
 * Efekt: przyciski martwe do F5 (reload zerował moduł JS → flagi=false).
 *
 * FIX: reset `combatBusy`/`playerActionFetchActive` w `finally` `handleCombatFlee` ORAZ w `hideCombatUI`
 * (siatka bezpieczeństwa — koniec KAŻDEJ walki czyści flagi akcji, nie zatruwając następnej).
 *
 * Ten spec jest kontraktowy na czystym reconcilerze i DOKUMENTUJE, dlaczego reset MUSI być upstream:
 * sam reconciler nie odzyska zalegającego `playerActionFetchActive` (brak watchdoga) — dlatego flagi
 * trzeba zerować przy zakończeniu walki, a nie liczyć na resync.
 */
const { test, expect } = require("@playwright/test");

async function loadReconciler(page) {
  await page.goto("/");
  return await page.evaluate(async () => {
    const r = await fetch("/js/combat_reconcile.js");
    if (!r.ok) return { ok: false, status: r.status };
    const src = await r.text();
    // eslint-disable-next-line no-new-func
    new Function(src)(); // IIFE podpina reconcileCombatTurn do window
    return { ok: true, hasFn: typeof window.reconcileCombatTurn === "function" };
  });
}

test("REGRESSION #1149 — zalegający playerActionFetchActive trzyma akcję (brak watchdoga → reset MUSI być upstream)", async ({ page }) => {
  const loaded = await loadReconciler(page);
  expect(loaded.ok, "/js/combat_reconcile.js musi być serwowany").toBeTruthy();

  const out = await page.evaluate(() => {
    // Scenariusz #1149: backend = tura gracza, walka aktywna, ale flaga akcji gracza ZALEGA
    // (wyciekła z udanej ucieczki poprzedniej walki). Reconciler nie zna timestampu POST-a
    // akcji gracza, więc traktuje to jak realny fetch w locie i NIE resyncuje.
    const cs = { status: "active", current_turn: "player" };
    const flags = {
      combatBusy: true,
      enemyTurnInFlight: false,
      enemyTurnFetchActive: false,
      playerActionFetchActive: true, // <-- zaleg z ucieczki (przed fixem)
    };
    return window.reconcileCombatTurn(cs, flags, 0);
  });
  // To NIE jest bug w reconcilerze — to dowód, że sam reconciler nie wystarcza:
  expect(out.canAct, "reconciler nie odblokuje akcji dopóki flaga akcji gracza zalega").toBe(false);
  expect(out.clearCombatBusy, "reconciler NIE czyści combatBusy gdy 'fetch' w locie").toBe(false);
  expect(out.reason).toBe("fetch_in_flight");
});

test("REGRESSION #1149 — po fixie: czyste flagi (reset na koniec walki) → tura gracza włączona", async ({ page }) => {
  await loadReconciler(page);
  const out = await page.evaluate(() => {
    // Po fixie hideCombatUI/handleCombatFlee zerują flagi na koniec walki, więc NASTĘPNA
    // walka startuje z czystym stanem — reconciler od razu oddaje akcję graczowi.
    const cs = { status: "active", current_turn: "player" };
    const flags = {
      combatBusy: false,
      enemyTurnInFlight: false,
      enemyTurnFetchActive: false,
      playerActionFetchActive: false, // <-- wyzerowane przez fix
    };
    return window.reconcileCombatTurn(cs, flags, 0);
  });
  expect(out.canAct, "czysty stan po zakończeniu poprzedniej walki → akcja gracza włączona").toBe(true);
  expect(out.overlayVisible).toBe(false);
  expect(out.reason).toBe("player_turn");
});
