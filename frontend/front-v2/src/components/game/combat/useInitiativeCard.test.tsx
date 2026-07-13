/**
 * TDD #1356 (WALKA-T5-FIX-a) — karta inicjatywy na starcie walki.
 * Spec 5a (docs/FIX_TRAVEL_COMBAT_FLOW.md): na starcie widoczne OBA wyniki inicjatywy
 * + kto zaczyna. Dane już są w snapshotcie (`initiative_roll` gracza i wroga + `turn_order`),
 * brakowało tylko prezentacji. Hook latchuje dane raz per combat_id (jak useEnemyReveal).
 */
import { it, expect, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useInitiativeCard, type InitiativeLive } from "./useInitiativeCard";
import type { Combatant } from "@/lib/types";

const player: Combatant = {
  id: "player",
  type: "player",
  name: "Ty",
  hp_current: 20,
  hp_max: 20,
  initiative_roll: 15,
};
const wolf: Combatant = {
  id: "wilk",
  type: "enemy",
  name: "Wilk",
  hp_current: 12,
  hp_max: 12,
  initiative_roll: 8,
};

const combat = (id: number, turn_order: string[]): InitiativeLive => ({
  id,
  status: "active",
  turn_order,
  current_turn: turn_order[0],
  combatants: [player, wolf],
});

// Latch #1360 persystuje w sessionStorage — czyścimy między testami dla izolacji.
beforeEach(() => sessionStorage.clear());

// ─── Test główny: oba wyniki + gracz zaczyna ─────────────────────────────────

it("#1356: start walki → oba wyniki inicjatywy + gracz zaczyna (wyższy rzut)", () => {
  const { result } = renderHook(() => useInitiativeCard(combat(10, ["player", "wilk"])));
  expect(result.current.initiative, "karta inicjatywy ma się pokazać na starcie").not.toBeNull();
  expect(result.current.initiative?.player.roll).toBe(15);
  expect(result.current.initiative?.enemies[0].roll).toBe(8);
  expect(result.current.initiative?.enemies[0].name).toBe("Wilk");
  expect(result.current.initiative?.starter).toBe("player");
});

// ─── Kto zaczyna wg turn_order (silnik: wyższa inicjatywa pierwszy) ──────────

it("#1356: wróg pierwszy w turn_order → zaczyna wróg", () => {
  const { result } = renderHook(() => useInitiativeCard(combat(11, ["wilk", "player"])));
  expect(result.current.initiative?.starter).toBe("enemy");
});

// ─── Once-per-combat: po dismiss ta sama walka nie odsłania karty drugi raz ──

it("#1356: karta raz na walkę — po dismiss nie wraca dla tego samego combat_id", () => {
  const { result, rerender } = renderHook(
    ({ live }: { live: InitiativeLive }) => useInitiativeCard(live),
    { initialProps: { live: combat(12, ["player", "wilk"]) } },
  );
  expect(result.current.initiative).not.toBeNull();
  act(() => result.current.dismissInitiative());
  expect(result.current.initiative).toBeNull();
  rerender({ live: combat(12, ["player", "wilk"]) });
  expect(
    result.current.initiative,
    "ta sama walka nie odsłania karty inicjatywy drugi raz",
  ).toBeNull();
});

// ─── #1360: F5 w środku walki (unmount+remount) — realny scenariusz ─────────

it("#1360: F5 w środku walki → karta inicjatywy NIE wraca dla tego samego combat_id", () => {
  // Pierwsze wejście do walki — karta się pokazuje i zostaje „widziana".
  const { result, unmount } = renderHook(() => useInitiativeCard(combat(20, ["player", "wilk"])));
  expect(result.current.initiative, "start walki → karta jest").not.toBeNull();
  // F5 = pełny unmount hooka, a potem świeży mount z tym samym combat_id (runda 3+).
  unmount();
  const remount = renderHook(() => useInitiativeCard(combat(20, ["player", "wilk"])));
  expect(
    remount.result.current.initiative,
    "po F5 w trakcie tej samej walki karta inicjatywy nie może wyskoczyć ponownie",
  ).toBeNull();
});

it("#1360: nowa walka po F5 → karta inicjatywy działa normalnie (inny combat_id)", () => {
  const first = renderHook(() => useInitiativeCard(combat(21, ["player", "wilk"])));
  expect(first.result.current.initiative).not.toBeNull();
  first.unmount();
  const second = renderHook(() => useInitiativeCard(combat(22, ["player", "wilk"])));
  expect(
    second.result.current.initiative,
    "nowa walka (inny combat_id) nadal odsłania kartę inicjatywy",
  ).not.toBeNull();
});

// ─── Brak wrogów → brak karty ────────────────────────────────────────────────

it("#1356: brak żywych wrogów → brak karty inicjatywy", () => {
  const { result } = renderHook(() =>
    useInitiativeCard({
      id: 13,
      status: "active",
      turn_order: ["player"],
      combatants: [player],
    }),
  );
  expect(result.current.initiative).toBeNull();
});
