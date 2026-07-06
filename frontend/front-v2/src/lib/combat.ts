// FE9 walka (#1236) — pochodne stanu walki: karty rzutów combat (F-52), progi
// HP dla paska w banerze (F-53), etykiety stref. Źródło: makieta zar7-walka/zar7-kosc.
import type { CombatActionResult, CombatState, Combatant } from "@/lib/types";
import type { RollCardData } from "@/lib/types";

// ── HP bar (parytet ze starym `_woundThresholds`) ────────────────────────────
export function hpTier(cur: number, max: number): "hi" | "mid" | "lo" {
  const pct = max > 0 ? (cur / max) * 100 : 0;
  return pct > 60 ? "hi" : pct > 30 ? "mid" : "lo";
}

export function hpPct(cur: number, max: number): number {
  return Math.max(0, Math.min(100, max > 0 ? Math.round((cur / max) * 100) : 0));
}

// ── Struktura banera: gracz + wrogowie w strefach względem gracza ─────────────
export interface CombatView {
  round: number;
  currentTurn: string;
  isPlayerTurn: boolean;
  player: Combatant | null;
  engaged: Combatant[]; // ZWARCIE
  ranged: Combatant[]; // DYSTANS
  status: string;
  endedReason: string | null;
}

export function readCombat(cs: CombatState | null | undefined): CombatView | null {
  if (!cs) return null;
  const combatants = Array.isArray(cs.combatants) ? cs.combatants : [];
  const player = combatants.find((c) => c.type === "player") ?? null;
  const enemies = combatants.filter((c) => c.type === "enemy" || c.type === "summon");
  const engaged: Combatant[] = [];
  const ranged: Combatant[] = [];
  for (const e of enemies) {
    (String(e.zone || "engaged") === "ranged" ? ranged : engaged).push(e);
  }
  return {
    round: Number(cs.round || 1),
    currentTurn: String(cs.current_turn ?? ""),
    isPlayerTurn: cs.current_turn === "player",
    player,
    engaged,
    ranged,
    status: String(cs.status ?? "active"),
    endedReason: (cs.ended_reason as string) ?? null,
  };
}

export function isCombatantActive(c: Combatant, currentTurn: string): boolean {
  const id = String(c.id ?? c.combatant_id ?? "");
  return id !== "" && id === String(currentTurn);
}

export function livingEnemies(view: CombatView): Combatant[] {
  return [...view.engaged, ...view.ranged].filter(
    (e) => Number(e.hp_current ?? 0) > 0,
  );
}

// ── Karty rzutów (F-52) z wyników silnika ────────────────────────────────────

function fmt(mod: number): string {
  return (mod >= 0 ? "+" : "") + mod;
}

/** Rzut ataku/czaru gracza → karta (prawo/ember). Nat20 crit, Nat1 fumble. */
export function rollFromPlayerAttack(
  r: CombatActionResult,
  title: string,
): RollCardData {
  const d20 = Number(r.player_raw_d20 ?? NaN);
  const total = Number(r.attack_total ?? NaN);
  const crit = !!r.player_nat20 || d20 === 20;
  const fumble = !!r.player_nat1 || d20 === 1;
  const cells: RollCardData["cells"] = [];
  if (Number.isFinite(d20)) cells.push({ k: "d20", v: String(d20) });
  if (Number.isFinite(total)) cells.push({ k: "Suma", v: String(total), sum: true });

  let resV: string;
  if (r.blocked) resV = r.mana_insufficient ? "ZA MAŁO MANY" : "POZA ZASIĘGIEM";
  else if (r.spell_type === "heal") resV = `+${r.heal_amount ?? 0} HP`;
  else if (r.dodged) resV = "UNIK";
  else if (r.hit) resV = `−${r.damage ?? 0} HP`;
  else resV = "PUDŁO";
  cells.push({ k: r.spell_type === "heal" ? "Lecz." : "Obraż.", v: resV, res: true });

  return { actor: "player", title, cells, crit, fumble };
}

/** Rzut ataku wroga → karta (lewo/krwawy). */
export function rollFromEnemyAttack(r: CombatActionResult): RollCardData {
  const d20 = Number(r.raw_d20 ?? NaN);
  const total = Number(r.attack_roll ?? NaN);
  const ac = Number(r.target_ac ?? NaN);
  const crit = d20 === 20;
  const fumble = d20 === 1;
  const cells: RollCardData["cells"] = [];
  if (Number.isFinite(d20)) cells.push({ k: "d20", v: String(d20) });
  if (Number.isFinite(total)) cells.push({ k: "Atak", v: String(total), sum: true });
  if (Number.isFinite(ac)) cells.push({ k: "Obr.", v: String(ac) });
  cells.push({
    k: r.hit ? "Trafia" : "Wynik",
    v: r.dodged ? "UNIK" : r.hit ? `−${r.damage ?? 0} HP` : "PUDŁO",
    res: true,
  });
  const name = String(r.enemy_name || "Wróg").toUpperCase();
  return { actor: "enemy", title: `${name} — ATAK`, cells, crit, fumble };
}

/** Wynik reakcji SF10 → karta (lewo/krwawy). */
export function rollFromReaction(
  r: CombatActionResult,
  choice: "take" | "dodge" | "block",
): RollCardData {
  const react = r.reaction || {};
  const cells: RollCardData["cells"] = [];
  const label =
    choice === "dodge" ? "UNIK" : choice === "block" ? "BLOK" : "CIOS";
  cells.push({ k: "Reakcja", v: label, sum: true });
  let resV: string;
  if (choice === "dodge" && react.dodged) resV = "0 HP · UNIK";
  else if (choice === "block") resV = `−${r.damage ?? 0} HP · BLOK`;
  else resV = `−${r.damage ?? 0} HP`;
  cells.push({ k: "Skutek", v: resV, res: true });
  const name = String(r.enemy_name || "Wróg").toUpperCase();
  return { actor: "enemy", title: `${name} — TRAFIENIE`, cells, fumble: false };
}

export { fmt };
