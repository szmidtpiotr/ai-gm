/* #700 (SMOKE-LOCH P1) — czysty reconciler stanu tury walki.
 *
 * Problem: pod szybkim/wielokrotnym inputem w walce lochu front zacinał się na overlayu
 * "Tura wroga" z `combatBusy=true`/`enemyTurnInFlight=true`, mimo że backend już oddał turę
 * graczowi (`active_combat.current_turn = 'player'`). Brakowało reaktywnego re-syncu: nic nie
 * zdejmowało overlayu / nie odblokowywało akcji, gdy backend (źródło prawdy) zmienił turę.
 *
 * Ta funkcja jest CZYSTA (bez DOM, bez sieci) — liczy docelowy stan UI z (cs, flagi, czas).
 * app.js woła ją w pętli pollCombatState i po turze wroga, po czym aplikuje dyrektywy.
 *
 * Zasada: backend = jedyne źródło prawdy o turze. Lokalne flagi mogą jedynie WSTRZYMAĆ resync,
 * gdy REALNY fetch walki (POST tury wroga / akcji gracza) jest w locie — wtedy nie ścigamy się
 * z odpowiedzią, która zaraz nadejdzie. Gdy żaden fetch nie trwa, a flagi nadal mówią "wróg/busy"
 * — to desync: zdejmij overlay, włącz akcję, wyczyść zalegające flagi.
 *
 * @param {object|null} cs    combat_state z backendu ({status, current_turn, ...})
 * @param {object}      flags { combatBusy, enemyTurnInFlight, enemyTurnFetchActive,
 *                              playerActionFetchActive, reactionPending, enemyTurnStartedAt,
 *                              watchdogMs }
 * @param {number}      nowMs Date.now() w momencie wywołania (testowalność)
 * @returns {{overlayVisible:boolean, canAct:boolean, isPlayerTurn:boolean,
 *            clearEnemyTurnInFlight:boolean, clearCombatBusy:boolean, reason:string}}
 */
(function (root) {
  function reconcileCombatTurn(cs, flags, nowMs) {
    flags = flags || {};
    nowMs = typeof nowMs === "number" ? nowMs : 0;

    const out = {
      overlayVisible: false,
      canAct: false,
      isPlayerTurn: false,
      clearEnemyTurnInFlight: false,
      clearCombatBusy: false,
      reason: "no_combat",
    };

    // Brak walki lub walka nieaktywna (ended / inny status) → żadnego overlayu ani akcji.
    if (!cs || cs.status !== "active") {
      out.reason = cs && cs.status === "ended" ? "ended" : "no_combat";
      return out;
    }

    const isPlayerTurn = cs.current_turn === "player";
    out.isPlayerTurn = isPlayerTurn;

    // Okno reakcji (SF10 #633) ma własny modal — nie ruszamy overlayu/akcji.
    if (flags.reactionPending) {
      out.overlayVisible = false;
      out.canAct = false;
      out.reason = "reaction_pending";
      return out;
    }

    if (!isPlayerTurn) {
      // Tura wroga wg backendu — overlay włączony, akcja zablokowana.
      out.overlayVisible = true;
      out.canAct = false;
      out.reason = "enemy_turn";
      return out;
    }

    // Backend mówi: tura gracza (źródło prawdy).
    const fetchInFlight = !!flags.enemyTurnFetchActive || !!flags.playerActionFetchActive;
    if (fetchInFlight) {
      // Realny POST jeszcze się rozlicza — nie ścigaj się z nadchodzącą odpowiedzią.
      // (Watchdog awaryjny: jeśli fetch tury wroga wisi absurdalnie długo, i tak resyncuj.)
      const startedAt = flags.enemyTurnStartedAt || 0;
      const watchdogMs = flags.watchdogMs || 8000;
      const stuck =
        flags.enemyTurnFetchActive && startedAt > 0 && nowMs - startedAt > watchdogMs;
      if (!stuck) {
        out.overlayVisible = !!flags.enemyTurnFetchActive;
        out.canAct = false;
        out.reason = "fetch_in_flight";
        return out;
      }
      out.reason = "watchdog_timeout";
    }

    // Żaden fetch nie trwa (lub watchdog wymusił) a flagi nadal mówią "wróg/busy" → DESYNC.
    // Resync do backendu: zdejmij overlay, włącz akcję, wyczyść zalegające flagi.
    out.overlayVisible = false;
    out.canAct = true;
    out.clearEnemyTurnInFlight = !!flags.enemyTurnInFlight;
    out.clearCombatBusy = !!flags.combatBusy;
    if (!out.reason || out.reason === "fetch_in_flight") {
      out.reason =
        flags.enemyTurnInFlight || flags.combatBusy ? "watchdog_resync" : "player_turn";
    }
    return out;
  }

  root.reconcileCombatTurn = reconcileCombatTurn;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { reconcileCombatTurn };
  }
})(typeof window !== "undefined" ? window : globalThis);
