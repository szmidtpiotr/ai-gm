/**
 * TDD #1358 (WALKA-T5-FIX-c) — timeout okna reakcji (8s) był cichy.
 * Po wygaśnięciu ReactionModal odpalał `take` bez żadnego komunikatu — karta rzutu
 * była identyczna jak przy ręcznym „Przyjmij cios", więc gracz nie wiedział czy sam
 * kliknął, czy spadło HP bo nie zdążył. Po fixie karta timeout-take jest odróżnialna
 * (dopisek „czas minął"), a CombatView pokazuje toast „Czas minął — przyjąłeś cios".
 */
import { it, expect, describe } from "vitest";
import { rollFromReaction } from "./combat";
import type { CombatActionResult } from "@/lib/types";

function result(card: ReturnType<typeof rollFromReaction>) {
  return card.cells.find((c) => c.res);
}

// ─── Test główny: timeout-take odróżnialny od ręcznego take ──────────────────

it("timeout-take → karta z dopiskiem czas-minął (odróżnialna od ręcznego take)", () => {
  const r: CombatActionResult = { damage: 4, enemy_name: "Wilk", reaction: {} };
  const card = rollFromReaction(r, "take", true); // timedOut = true
  const res = result(card);
  expect(res, "brak komórki wyniku").toBeTruthy();
  expect(res!.v.toLowerCase(), "karta timeout nie mówi czas-minął (#1358)").toContain(
    "czas minął",
  );
  // Nadal niesie liczbę obrażeń — to wciąż przyjęty cios.
  expect(res!.v).toContain("4");
});

// ─── Backward compat: ręczny take bez zmian ──────────────────────────────────

describe("backward compatibility", () => {
  it("ręczny take (timedOut pominięty) → CIOS · X Obr. bez dopisku", () => {
    const r: CombatActionResult = { damage: 4, enemy_name: "Wilk", reaction: {} };
    const card = rollFromReaction(r, "take");
    expect(result(card)?.v).toBe("CIOS · 4 Obr.");
  });

  it("ręczny take (timedOut=false) identyczny jak bez argumentu", () => {
    const r: CombatActionResult = { damage: 7, enemy_name: "Ork", reaction: {} };
    expect(rollFromReaction(r, "take", false).cells.find((c) => c.res)?.v).toBe(
      "CIOS · 7 Obr.",
    );
  });

  it("unik nietknięty przez nowy argument", () => {
    const r: CombatActionResult = {
      damage: 0,
      enemy_name: "Wilk",
      reaction: { dodged: true },
    };
    expect(rollFromReaction(r, "dodge", true).cells.find((c) => c.res)?.v).toContain(
      "UNIK UDANY",
    );
  });
});
