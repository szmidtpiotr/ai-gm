/**
 * REGRESSION #700 (SMOKE-LOCH P1) — desync tury walki: backend=player, frontend wisi na "Tura wroga" (atak disabled).
 * Acceptance: gdy backend.current_turn==='player' i żaden fetch walki nie jest w locie, reconciler
 * (window.reconcileCombatTurn) chowa overlay "Tura wroga", włącza akcję gracza i sygnalizuje wyczyszczenie
 * zalegających flag (combatBusy / enemyTurnInFlight). Backend = jedyne źródło prawdy o turze.
 */
const { test, expect } = require("@playwright/test");

// Ładuje czysty moduł reconcilera do kontekstu strony (bez logowania, bez walki — test deterministyczny).
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

test("REGRESSION #700 — backend oddał turę graczowi + brak fetchu → overlay zdjęty, akcja włączona", async ({ page }) => {
  const loaded = await loadReconciler(page);
  expect(loaded.ok, "/js/combat_reconcile.js musi być serwowany (#700)").toBeTruthy();
  expect(loaded.hasFn, "window.reconcileCombatTurn musi istnieć").toBeTruthy();

  const out = await page.evaluate(() => {
    const cs = { status: "active", current_turn: "player" };
    const flags = {
      combatBusy: true,
      enemyTurnInFlight: true,
      enemyTurnFetchActive: false,
      playerActionFetchActive: false,
    };
    return window.reconcileCombatTurn(cs, flags, 0);
  });
  expect(out.overlayVisible, "overlay 'Tura wroga' musi zniknąć gdy backend oddał turę").toBe(false);
  expect(out.canAct, "przycisk Atak musi się włączyć (tura gracza)").toBe(true);
  expect(out.clearEnemyTurnInFlight, "zalegający enemyTurnInFlight musi zostać wyczyszczony").toBe(true);
  expect(out.clearCombatBusy, "zalegający combatBusy musi zostać wyczyszczony").toBe(true);
});

test("REGRESSION #700 — tura wroga: overlay widoczny, akcja zablokowana", async ({ page }) => {
  await loadReconciler(page);
  const out = await page.evaluate(() => {
    const cs = { status: "active", current_turn: "enemy_1" };
    return window.reconcileCombatTurn(cs, {}, 0);
  });
  expect(out.overlayVisible).toBe(true);
  expect(out.canAct).toBe(false);
});

test("REGRESSION #700 — realny fetch tury wroga w locie: brak fałszywego resyncu", async ({ page }) => {
  await loadReconciler(page);
  const out = await page.evaluate(() => {
    const cs = { status: "active", current_turn: "player" };
    const flags = { enemyTurnFetchActive: true }; // backend POST jeszcze się rozlicza
    return window.reconcileCombatTurn(cs, flags, 0);
  });
  // Dopóki realny POST tury wroga trwa, NIE czyścimy flag ani nie zdejmujemy overlayu na siłę.
  expect(out.canAct).toBe(false);
  expect(out.clearEnemyTurnInFlight).toBe(false);
});

test("REGRESSION #700 — walka zakończona: brak overlayu, brak akcji", async ({ page }) => {
  await loadReconciler(page);
  const out = await page.evaluate(() => {
    const cs = { status: "ended", current_turn: "player" };
    return window.reconcileCombatTurn(cs, { enemyTurnInFlight: true }, 0);
  });
  expect(out.overlayVisible).toBe(false);
  expect(out.canAct).toBe(false);
});
