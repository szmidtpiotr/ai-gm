/**
 * TDD #1357 (WALKA-T5-FIX-b) — rzut uniku wroga ukryty na froncie.
 * Backend liczy i wysyła `dodge_roll {raw,modifier,total,verdict}`, ale karta rzutu
 * pokazywała tylko słowo „WRÓG UNIKA" — bez liczb, więc gracz nie wie CZEMU trafił
 * lub nie. Po fixie karta ataku gracza pokazuje OBIE strony liczbowo (Twój atak vs
 * unik wroga) + werdykt. Semantyka #826: zwykłe pudło = udany unik wroga; „PUDŁO"
 * tylko przy Nat 1 gracza.
 */
import { describe, it, expect } from "vitest";
import { rollFromPlayerAttack, toHitStageCard } from "./combat";
import type { CombatActionResult } from "@/lib/types";

// Pomocnik: znajdź komórkę po etykiecie.
function cell(card: ReturnType<typeof rollFromPlayerAttack>, k: string) {
  return card.cells.find((c) => c.k === k);
}
// Pomocnik: komórka wyniku (res:true).
function result(card: ReturnType<typeof rollFromPlayerAttack>) {
  return card.cells.find((c) => c.res);
}

// ─── Test główny: unik wroga → obie liczby widoczne ──────────────────────────

it("dodged attack pokazuje liczby uniku wroga (d20+DEX=suma) + werdykt", () => {
  const r: CombatActionResult = {
    hit: false,
    dodged: true,
    player_raw_d20: 8,
    attack_total: 10,
    dodge_roll: { raw: 15, modifier: 2, total: 17, dodged: true, player_roll: 10, verdict: "dodged" },
  };
  const card = rollFromPlayerAttack(r, "ATAK");
  // Twoja suma ataku nadal widoczna.
  expect(cell(card, "Suma")?.v).toBe("10");
  // Nowa komórka: unik wroga z rozbiciem d20+mod=suma.
  const dodge = cell(card, "Unik");
  expect(dodge, "brak komórki uniku wroga (#1357)").toBeTruthy();
  expect(dodge!.v).toContain("17"); // suma uniku
  expect(dodge!.v).toContain("15"); // surowy d20 wroga
  // Werdykt.
  expect(result(card)?.v).toContain("WRÓG UNIKA");
});

// ─── Trafienie: obie liczby też widoczne (czemu trafiłem) ────────────────────

it("trafienie pokazuje unik wroga (przegrany) — obie strony liczbowo", () => {
  const r: CombatActionResult = {
    hit: true,
    dodged: false,
    player_raw_d20: 14,
    attack_total: 16,
    damage: 5,
    damage_die: "1d6",
    damage_rolls: [4],
    dodge_roll: { raw: 12, modifier: 2, total: 14, dodged: false, player_roll: 16, verdict: "hit" },
  };
  const card = rollFromPlayerAttack(r, "ATAK");
  const dodge = cell(card, "Unik");
  expect(dodge, "unik wroga niewidoczny przy trafieniu (#1357)").toBeTruthy();
  expect(dodge!.v).toContain("14");
  // Etap NA TRAFIENIE też niesie liczby uniku (przeżywa filtr toHitStageCard).
  const stage = toHitStageCard(card, true);
  expect(stage.cells.find((c) => c.k === "Unik"), "unik znika na etapie NA TRAFIENIE").toBeTruthy();
});

// ─── #826: Nat 1 gracza = PUDŁO, nie „WRÓG UNIKA" ────────────────────────────

it("Nat 1 gracza pokazuje PUDŁO (semantyka #826), bez dodge_roll nie wybucha", () => {
  const r: CombatActionResult = {
    hit: false,
    dodged: true, // backend ustawia dodged=true przy Nat1, ale to fumble gracza
    player_nat1: true,
    player_raw_d20: 1,
    attack_total: 3,
    // brak dodge_roll — backend nie liczy uniku przy Nat1
  };
  const card = rollFromPlayerAttack(r, "ATAK");
  expect(result(card)?.v).toBe("PUDŁO");
  expect(cell(card, "Unik"), "nie ma uniku przy Nat1").toBeFalsy();
});

// ─── Backward compat: leczenie i zwykłe pola bez zmian ───────────────────────

describe("backward compatibility", () => {
  it("heal card nie dostaje komórki uniku", () => {
    const r: CombatActionResult = {
      spell_type: "heal",
      heal_amount: 6,
      heal_rolls: [5],
      damage_die: "1d8",
      player_raw_d20: 12,
      attack_total: 14,
    };
    const card = rollFromPlayerAttack(r, "CZAR");
    expect(cell(card, "Unik")).toBeFalsy();
    expect(result(card)?.v).toBe("+6 HP");
  });

  it("trafienie bez dodge_roll (stary backend) nadal działa", () => {
    const r: CombatActionResult = {
      hit: true,
      dodged: false,
      player_raw_d20: 15,
      attack_total: 17,
      damage: 4,
      damage_die: "1d6",
      damage_rolls: [3],
    };
    const card = rollFromPlayerAttack(r, "ATAK");
    expect(cell(card, "Unik")).toBeFalsy();
    expect(result(card)?.v).toBe("4 Obr.");
  });
});

// ─── WALKA-FIX: heal die + karta ruchu wroga (zone_change) ────────────────────
// Bug 1: czar leczący — backend przysyła `heal_die` (nie `damage_die`), więc karta
// nie pokazywała kości leczenia i front nie miał czego animować.
// Bug 2: doskok melee (`zone_change`) renderował się jako fantomowe „ATAK — PUDŁO".
import { rollFromEnemyZoneChange } from "./combat";

describe("heal die na karcie czaru leczącego", () => {
  it("kość leczenia z heal_die widoczna (k8) mimo braku damage_die", () => {
    const r: CombatActionResult = {
      hit: true,
      spell_type: "heal",
      heal_amount: 8,
      heal_rolls: [5],
      heal_die: "1d8",
      // damage_die celowo BRAK — backend heal path go nie ustawia
    };
    const card = rollFromPlayerAttack(r, "LECZNICZY DOTYK");
    expect(cell(card, "k8")?.v).toBe("5");
    expect(result(card)?.v).toBe("+8 HP");
  });
});

describe("rollFromEnemyZoneChange — karta ruchu zamiast fantomowego ataku", () => {
  it("doskok do zwarcia: tytuł RUCH, akcja DOSKOK, bez PUDŁO", () => {
    const r: CombatActionResult = {
      enemy_name: "Bandyta",
      hit: false,
      damage: 0,
      zone_change: { actor_id: "bandit_01", from: "ranged", to: "engaged", charged: true },
    };
    const card = rollFromEnemyZoneChange(r);
    expect(card.title).toBe("BANDYTA — RUCH");
    expect(card.actor).toBe("enemy");
    expect(cell(card as never, "Akcja")?.v).toBe("DOSKOK");
    const res = card.cells.find((c) => c.res);
    expect(res?.v).toContain("bez ataku");
    expect(card.cells.some((c) => c.v === "PUDŁO")).toBe(false);
  });

  it("odskok na dystans (fled): akcja ODSKOK", () => {
    const r: CombatActionResult = {
      enemy_name: "Bandyta",
      zone_change: { from: "engaged", to: "ranged", fled: true },
    };
    const card = rollFromEnemyZoneChange(r);
    expect(cell(card as never, "Akcja")?.v).toBe("ODSKOK");
  });
});
