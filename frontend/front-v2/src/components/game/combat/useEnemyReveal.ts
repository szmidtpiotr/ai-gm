import { useEffect, useRef, useState } from "react";
import type { Combatant } from "@/lib/types";

/** Minimalny kształt „żywego" stanu walki potrzebny do decyzji o karcie pojawienia. */
export interface RevealLive {
  id?: number | null;
  status?: string;
  combatants?: Combatant[] | null;
}

/**
 * BL-A7 (#1344) + WALKA-T1-FIX (#1355) — karta pojawienia wroga (EnemyRevealCard),
 * once per combat_id (jak seenTiles w DungeonView). Wyodrębnione z CombatView, by
 * domknąć testem regresję race'u z #1355:
 *  - `suppressRevealCombatId` truthy-at-mount → karta NIGDY się nie pokazuje
 *    (zasadzka w drodze: modal podróży już pokazał wroga — dedup overlayów),
 *  - `suppressRevealCombatId` dojeżdżający PÓŹNIEJ (race: efekt dziecka odpalił przed
 *    efektem rodzica) → safety-net czyści już pokazaną kartę.
 */
export function useEnemyReveal(
  live: RevealLive | null | undefined,
  suppressRevealCombatId: number | null,
) {
  const [reveal, setReveal] = useState<Combatant[] | null>(null);
  const revealedRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    const cid = live?.id;
    if (!cid || live?.status !== "active") return;
    // #1349/#1355: walka z zasadzki — modal podróży już pokazał wroga, więc oznacz
    // combat jako „odsłonięty" i NIE pokazuj drugiej karty (dedup overlayów).
    if (suppressRevealCombatId != null && cid === suppressRevealCombatId) {
      revealedRef.current.add(cid);
      // #1355 safety-net: gdy suppress dojechał PO tym, jak karta zdążyła się pokazać
      // (race: efekt dziecka przed efektem rodzica), skasuj już pokazaną kartę.
      setReveal(null);
      return;
    }
    if (revealedRef.current.has(cid)) return;
    const enemies = (live.combatants ?? []).filter(
      (c) => c.type === "enemy" && Number(c.hp_current ?? 0) > 0,
    );
    if (!enemies.length) return;
    revealedRef.current.add(cid);
    setReveal(enemies);
  }, [live?.id, live?.status, suppressRevealCombatId]);

  return {
    reveal,
    dismissReveal: () => setReveal(null),
  };
}
