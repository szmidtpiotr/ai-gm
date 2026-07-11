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

/** Rzut ataku/czaru gracza → karta (prawo/ember). Nat20 crit, Nat1 fumble.
 * Kolumna wyniku jest jawna: TRAFIENIE/−X HP (zielony), WRÓG UNIKA / PUDŁO (złoty). */
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

  // Etykieta + wartość + kolor zależają od tego, co realnie się stało z Twoim ciosem.
  let label = "Wynik";
  let resV: string;
  let tone: "ok" | "bad" | "warn";
  if (r.blocked) {
    resV = r.mana_insufficient ? "ZA MAŁO MANY" : "POZA ZASIĘGIEM";
    tone = "warn";
  } else if (r.spell_type === "heal") {
    // Kości leczenia (np. 1d8) przed sumą.
    if (r.heal_rolls?.length && r.damage_die) {
      const sides = Number(r.damage_die.split("d")[1] || 6);
      for (const rv of r.heal_rolls) cells.push({ k: `k${sides}`, v: String(rv) });
    }
    label = "Lecz.";
    resV = `+${r.heal_amount ?? 0} HP`;
    tone = "ok";
  } else if (r.dodged) {
    resV = "WRÓG UNIKA"; // przeciwnik uchylił się przed Twoim ciosem
    tone = "warn";
  } else if (r.hit) {
    // Kości obrażeń (np. 2d6) widoczne przed sumą.
    if (r.damage_rolls?.length && r.damage_die) {
      const sides = Number(r.damage_die.split("d")[1] || 6);
      for (const rv of r.damage_rolls) cells.push({ k: `k${sides}`, v: String(rv) });
    }
    label = "Wynik";
    resV = `${r.damage ?? 0} Obr.`; // trafienie — zadane obrażenia
    tone = "ok";
  } else {
    resV = "PUDŁO";
    tone = "warn";
  }
  cells.push({ k: label, v: resV, res: true, tone });

  return { actor: "player", title, cells, crit, fumble };
}

/** Rzut ataku wroga (bez okna reakcji) → karta (lewo/krwawy). Kolor wg skutku dla Ciebie. */
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
  // Kości obrażeń wroga (np. 1d6) widoczne gdy trafił.
  const hit = !!r.hit && !r.dodged;
  if (hit && r.damage_rolls?.length && r.damage_die) {
    const sides = Number(r.damage_die.split("d")[1] || 6);
    for (const rv of r.damage_rolls) cells.push({ k: `k${sides}`, v: String(rv) });
  }
  cells.push({
    k: "Wynik",
    v: r.dodged ? "UNIKASZ" : r.hit ? `${r.damage ?? 0} Obr.` : "PUDŁO",
    res: true,
    tone: hit ? "bad" : "ok",
  });
  const name = String(r.enemy_name || "Wróg").toUpperCase();
  return { actor: "enemy", title: `${name} — ATAK`, cells, crit, fumble };
}

/** Etap d20 (na trafienie) dwuetapowej animacji kości: karta BEZ kości i wartości
 * obrażeń — pokazuje tylko czy cios siadł. Pełna karta (z −X HP) wyświetla się
 * dopiero po drugim etapie (kość obrażeń), żeby nie zdradzać wyniku przed rzutem. */
export function toHitStageCard(full: RollCardData, hit: boolean): RollCardData {
  const forPlayer = full.actor === "player";
  const cells = full.cells.filter((c) => !c.res && !/^k\d+$/.test(c.k));
  cells.push({
    k: "Wynik",
    v: hit ? "TRAFIENIE" : "PUDŁO",
    res: true,
    tone: hit ? (forPlayer ? "ok" : "bad") : forPlayer ? "warn" : "ok",
  });
  return { ...full, cells };
}

/** Wynik reakcji SF10 (wróg atakuje, Ty reagujesz) → karta (lewo/krwawy).
 * Jasno mówi czy unik/blok się udał + koloruje wg skutku dla Ciebie. */
export function rollFromReaction(
  r: CombatActionResult,
  choice: "take" | "dodge" | "block",
): RollCardData {
  const react = r.reaction || {};
  const dmg = Number(r.damage ?? 0);
  const cells: RollCardData["cells"] = [];
  const label =
    choice === "dodge" ? "UNIK" : choice === "block" ? "BLOK" : "CIOS";
  cells.push({ k: "Reakcja", v: label, sum: true });

  let resV: string;
  let tone: "ok" | "bad" | "warn";
  if (choice === "dodge") {
    if (react.dodged) {
      resV = "UNIK UDANY · 0 Obr."; // uchyliłeś się w całości
      tone = "ok";
    } else {
      resV = `UNIK NIEUDANY · ${dmg} Obr.`; // nie zdążyłeś — cios dosięga
      tone = "bad";
    }
  } else if (choice === "block") {
    if (react.full_block || dmg <= 0) {
      resV = "BLOK PEŁNY · 0 Obr."; // tarcza pochłonęła cały cios
      tone = "ok";
    } else {
      resV = `BLOK · ${dmg} Obr.`; // część obrażeń zablokowana
      tone = "warn";
    }
  } else {
    resV = `CIOS · ${dmg} Obr.`; // przyjąłeś na klatę
    tone = "bad";
  }
  cells.push({ k: "Skutek", v: resV, res: true, tone });
  const name = String(r.enemy_name || "Wróg").toUpperCase();
  return { actor: "enemy", title: `${name} — ATAK`, cells, fumble: false };
}

export { fmt };
