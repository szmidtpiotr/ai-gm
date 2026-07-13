/**
 * TDD #1355 (WALKA-T1-FIX) — regresja race'u karty pojawienia wroga.
 * Modal zasadzki pokazał już wroga; druga karta „Nieznany napastnik" ma się NIE pojawić.
 * Bug: efekt dziecka (reveal) odpalał przed efektem rodzica (suppress) → prop był null
 * przy montażu → karta się pokazała i już nie znikała (brak safety-netu setReveal(null)).
 */
import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useEnemyReveal, type RevealLive } from "./useEnemyReveal";
import type { Combatant } from "@/lib/types";

const enemy: Combatant = {
  id: "wilk",
  type: "enemy",
  name: "Wilk",
  hp_current: 12,
  hp_max: 12,
};

const activeCombat = (id: number): RevealLive => ({
  id,
  status: "active",
  combatants: [
    { id: "player", type: "player", hp_current: 20, hp_max: 20 },
    enemy,
  ],
});

// ─── Test główny: race — suppress dojeżdża PO montażu ────────────────────────

it("#1355: suppress dojeżdżający po montażu czyści już pokazaną kartę (safety net)", () => {
  // Render 1: prop suppress jeszcze null (efekt rodzica nie zdążył) → karta się pokazuje.
  const { result, rerender } = renderHook(
    ({ live, suppress }: { live: RevealLive; suppress: number | null }) =>
      useEnemyReveal(live, suppress),
    { initialProps: { live: activeCombat(77), suppress: null } },
  );
  expect(result.current.reveal, "karta powinna się pokazać zanim dojedzie suppress").not.toBeNull();

  // Render 2: rodzic ustawił suppress = id walki (race rozwiązany za późno).
  rerender({ live: activeCombat(77), suppress: 77 });
  expect(
    result.current.reveal,
    "po dojechaniu suppress karta MUSI zniknąć (dedup z modalem zasadzki)",
  ).toBeNull();
});

// ─── Test: suppress truthy-at-mount — karta NIGDY się nie pokazuje ───────────

it("#1355: suppress prawdziwy już przy montażu → karta nie pojawia się wcale", () => {
  const { result } = renderHook(() => useEnemyReveal(activeCombat(88), 88));
  expect(result.current.reveal, "zasadzka: karta ma być wyciszona od startu").toBeNull();
});

// ─── Backward compat: walka z NARRACJI (bez suppress) — karta działa ─────────

it("#1355: walka z narracji (suppress=null) → EnemyRevealCard dalej się pokazuje", () => {
  const { result } = renderHook(() => useEnemyReveal(activeCombat(99), null));
  expect(result.current.reveal, "narracyjna walka nadal odsłania kartę wroga").not.toBeNull();
  expect(result.current.reveal?.[0].name).toBe("Wilk");
});
