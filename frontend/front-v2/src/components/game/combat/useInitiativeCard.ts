import { useEffect, useState } from "react";
import type { Combatant } from "@/lib/types";
import { hasSeenCombat, markSeenCombat } from "./combat-seen";

/** Namespace latcha „widziane" (sessionStorage) — karta inicjatywy. */
const NS = "aigm:initSeen";

/** Minimalny kształt „żywego" stanu walki potrzebny do karty inicjatywy. */
export interface InitiativeLive {
  id?: number | null;
  status?: string;
  turn_order?: string[] | null;
  current_turn?: string | null;
  combatants?: Combatant[] | null;
}

export interface InitiativeData {
  player: { roll: number | null };
  enemies: { id: string; name: string; roll: number | null }[];
  starter: "player" | "enemy";
}

/**
 * WALKA-T5-FIX-a (#1356) — karta inicjatywy na starcie walki. Spec 5a: pokaż OBA
 * wyniki inicjatywy (gracz vs wróg) + kto zaczyna. Dane są w snapshotcie
 * (`initiative_roll` na kombatantach, `turn_order` z silnika — combat_service.py),
 * brakowało wyłącznie prezentacji. Latch once-per-combat_id (wzorzec useEnemyReveal):
 * kto-zaczyna zamrażamy przy PIERWSZYM aktywnym snapshotcie, zanim auto-driver tury
 * wroga zdąży przesunąć `current_turn`. Latch trwały (sessionStorage) — #1360:
 * przeżywa F5 w środku walki, więc karta nie wyskakuje ponownie po odświeżeniu.
 */
export function useInitiativeCard(live: InitiativeLive | null | undefined) {
  const [initiative, setInitiative] = useState<InitiativeData | null>(null);

  useEffect(() => {
    const cid = live?.id;
    if (!cid || live?.status !== "active") return;
    if (hasSeenCombat(NS, cid)) return;
    const combatants = live.combatants ?? [];
    const player = combatants.find((c) => c.type === "player") ?? null;
    const enemies = combatants.filter(
      (c) => (c.type === "enemy" || c.type === "summon") && Number(c.hp_current ?? 0) > 0,
    );
    if (!player || !enemies.length) return;
    // Kto zaczyna: pierwszy w turn_order (silnik: najwyższa inicjatywa, remis → gracz),
    // fallback current_turn. Latchujemy tu, bo tura wroga może zaraz przesunąć current_turn.
    const first = (live.turn_order && live.turn_order[0]) || live.current_turn || "player";
    const starter: "player" | "enemy" = String(first) === "player" ? "player" : "enemy";
    markSeenCombat(NS, cid);
    setInitiative({
      player: { roll: player.initiative_roll ?? null },
      enemies: enemies.map((e) => ({
        id: String(e.id),
        name: e.name ?? e.enemy_key ?? "Wróg",
        roll: e.initiative_roll ?? null,
      })),
      starter,
    });
  }, [live?.id, live?.status]);

  return {
    initiative,
    dismissInitiative: () => setInitiative(null),
  };
}
