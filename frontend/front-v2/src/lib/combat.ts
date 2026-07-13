// FE9 walka (#1236) — pochodne stanu walki: karty rzutów combat (F-52), progi
// HP dla paska w banerze (F-53), etykiety stref. Źródło: makieta zar7-walka/zar7-kosc.
import type { CombatActionResult, CombatState, Combatant, RelativeThreat } from "@/lib/types";
import type { RollCardData } from "@/lib/types";
import { normalizeDefenseDetails, type DefenseOptionDetail } from "@/lib/combat-defense";

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
  relativeThreat: RelativeThreat | null; // BL-A7 (#1344)
  defenseOptions: string[]; // WALKA-T2 (#1350): reakcje obronne DOSTĘPNE (available-only)
  // WALKA-T2-FIX (#1359): wszystkie obrony wg skilli + available + reason (wyszarzanie w UI)
  defenseOptionsDetailed: DefenseOptionDetail[];
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
    relativeThreat: (cs.relative_threat as RelativeThreat) ?? null,
    defenseOptions: Array.isArray(cs.defense_options)
      ? (cs.defense_options as string[])
      : [],
    defenseOptionsDetailed: normalizeDefenseDetails(
      cs.defense_options_detailed,
      Array.isArray(cs.defense_options) ? (cs.defense_options as string[]) : [],
    ),
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

/** WALKA-T5-FIX-b (#1357): komórka „Unik" — rzut uniku wroga (d20+DEX=suma) tak,
 * by gracz widział OBIE strony liczbowo i wiedział CZEMU trafił lub nie. Zwraca []
 * gdy backend nie przysłał `dodge_roll` (leczenie, Nat1 gracza, stary backend). */
function dodgeCells(r: CombatActionResult): RollCardData["cells"] {
  const dr = r.dodge_roll;
  if (!dr) return [];
  const total = Number(dr.total ?? NaN);
  if (!Number.isFinite(total)) return [];
  const raw = Number(dr.raw ?? NaN);
  const mod = Number(dr.modifier ?? 0);
  const v = Number.isFinite(raw) ? `${raw}${fmt(mod)}=${total}` : String(total);
  return [{ k: "Unik", v }];
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
  // #1357: obie strony liczbowo — dorzuć unik wroga zaraz po sumie ataku gracza.
  cells.push(...dodgeCells(r));

  // Etykieta + wartość + kolor zależają od tego, co realnie się stało z Twoim ciosem.
  let label = "Wynik";
  let resV: string;
  let tone: "ok" | "bad" | "warn";
  if (r.blocked) {
    resV = r.mana_insufficient ? "ZA MAŁO MANY" : "POZA ZASIĘGIEM";
    tone = "warn";
  } else if (fumble) {
    // #826: „PUDŁO" tylko przy Nat 1 gracza (własna kompromitacja), nie przy uniku wroga.
    resV = "PUDŁO";
    tone = "warn";
  } else if (r.spell_type === "heal") {
    // Kości leczenia (np. 1d8) przed sumą — backend przysyła `heal_die`, nie `damage_die`.
    const healDie = r.heal_die ?? r.damage_die;
    if (r.heal_rolls?.length && healDie) {
      const sides = Number(healDie.split("d")[1] || 6);
      for (const rv of r.heal_rolls) cells.push({ k: `k${sides}`, v: String(rv) });
    }
    label = "Lecz.";
    resV = `+${r.heal_amount ?? 0} HP`;
    tone = "ok";
  } else if (r.dodged) {
    // przeciwnik uchylił się przed Twoim ciosem; Nat 20 uniku = unik krytyczny (#1357).
    resV = r.dodge_roll?.verdict === "perfect_dodge" ? "WRÓG UNIKA (KRYT.)" : "WRÓG UNIKA";
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
  const hit = !!r.hit && !r.dodged;
  // Okno reakcji: obrażenia rozliczy dopiero karta reakcji — bez kości obrażeń
  // (zakład „Cios: ?" z ReactionModal) i bez mylącego „0 Obr.".
  const windowPending = hit && !!r.reaction_window;
  // Kości obrażeń wroga (np. 1d6) widoczne gdy trafił i wynik jest ostateczny.
  if (hit && !windowPending && r.damage_rolls?.length && r.damage_die) {
    const sides = Number(r.damage_die.split("d")[1] || 6);
    for (const rv of r.damage_rolls) cells.push({ k: `k${sides}`, v: String(rv) });
  }
  cells.push({
    k: "Wynik",
    v: r.dodged
      ? "UNIKASZ"
      : windowPending
        ? "TRAFIA · reakcja?"
        : r.hit
          ? `${r.damage ?? 0} Obr.`
          : "PUDŁO",
    res: true,
    tone: windowPending ? "warn" : hit ? "bad" : "ok",
  });
  const name = String(r.enemy_name || "Wróg").toUpperCase();
  return { actor: "enemy", title: `${name} — ATAK`, cells, crit, fumble };
}

/** Tura wroga bez ataku: melee doskakuje do gracza / odskakuje na dystans (zjada turę).
 * Bez tej karty odpowiedź `zone_change` wpadała w rollFromEnemyAttack i renderowała
 * fantomowe „ATAK — PUDŁO" (bez kolumn d20), sugerując dodatkowy atak wroga. */
export function rollFromEnemyZoneChange(r: CombatActionResult): RollCardData {
  const zc = r.zone_change || {};
  const toEngaged = String(zc.to || "engaged") === "engaged";
  const name = String(r.enemy_name || "Wróg").toUpperCase();
  return {
    actor: "enemy",
    title: `${name} — RUCH`,
    cells: [
      { k: "Akcja", v: toEngaged ? "DOSKOK" : "ODSKOK", sum: true },
      {
        k: "Skutek",
        v: toEngaged
          ? "wchodzi w zwarcie · bez ataku"
          : "odskakuje na dystans · bez ataku",
        res: true,
        tone: "warn",
      },
    ],
    fumble: false,
  };
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
  choice: "take" | "dodge" | "block" | "ward" | "mana",
  timedOut = false, // #1358: take z wygaśnięcia okna (8s) — karta odróżnialna od ręcznego
): RollCardData {
  const react = r.reaction || {};
  const dmg = Number(r.damage ?? 0);
  const cells: RollCardData["cells"] = [];
  const label =
    choice === "dodge"
      ? "UNIK"
      : choice === "block"
        ? "BLOK"
        : choice === "ward"
          ? "BARIERA"
          : choice === "mana"
            ? "TARCZA MANY"
            : "CIOS";
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
  } else if (choice === "ward") {
    // #1324: Arkanowa Bariera — test INT, mana pobrana niezależnie od wyniku.
    if (react.warded) {
      resV = "BARIERA · 0 Obr."; // cios rozbił się o magiczną osłonę
      tone = "ok";
    } else {
      resV = `BARIERA PRZEBITA · ${dmg} Obr.`; // test nieudany — cios przechodzi, mana i tak zeszła
      tone = "bad";
    }
  } else if (choice === "mana") {
    // #1325: Tarcza Many — deterministyczna absorpcja many; płacisz tylko za pochłonięte.
    const absorbed = Number(react.absorbed ?? 0);
    const spent = Number(react.mana_spent ?? 0);
    if (dmg <= 0) {
      resV = `TARCZA MANY · 0 Obr. · −${spent} many`; // cios pochłonięty w całości
      tone = "ok";
    } else {
      resV = `TARCZA MANY · −${absorbed} Obr. · ${dmg} przeszło · −${spent} many`;
      tone = "warn";
    }
  } else {
    // #1358: rozróżnij ręczny „Przyjmij cios" od cichego wygaśnięcia okna (8s).
    resV = timedOut
      ? `CIOS · ${dmg} Obr. · czas minął`
      : `CIOS · ${dmg} Obr.`; // przyjąłeś na klatę
    tone = "bad";
  }
  cells.push({ k: "Skutek", v: resV, res: true, tone });
  const name = String(r.enemy_name || "Wróg").toUpperCase();
  return { actor: "enemy", title: `${name} — ATAK`, cells, fumble: false };
}

export { fmt };
