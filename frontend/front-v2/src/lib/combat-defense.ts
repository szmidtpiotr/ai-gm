// WALKA-T2-FIX (#1359) — WSPÓLNE źródło etykiet/opisów reakcji obronnych + tłumaczenie
// powodów niedostępności. Jedno źródło dla piguły „Obrona" (ActionSheet) i modalu reakcji
// (ReactionModal), żeby etykiety nie rozjeżdżały się między powierzchniami (BUG-3).
import type { DefenseReaction } from "@/lib/types";

// Szczegół pojedynczej opcji obrony niesiony z backendu (`defense_options_detailed`,
// `reaction_options_detailed`): klucz + czy dostępna + powód niedostępności.
export interface DefenseOptionDetail {
  key: string;
  available: boolean;
  reason: string | null; // no_mana | no_shield | cap_reached | locked | null
}

// Metadane per reakcja. `sheetDesc` — pigułka Obrona; `reactionDesc`/`reactionMeta` — modal.
export const DEFENSE_META: Record<
  DefenseReaction,
  { label: string; sheetDesc: string; reactionDesc: string; reactionMeta: string }
> = {
  dodge: {
    label: "Unik",
    sheetDesc: "test zręczności na następny cios wroga",
    reactionDesc: "Test zręczności — całość albo nic. Sukces = 0 obrażeń.",
    reactionMeta: "d20+DEX",
  },
  shield_block: {
    label: "Blok tarczą",
    sheetDesc: "tarcza pochłonie część następnego ciosu",
    reactionDesc: "Tarcza pochłania część obrażeń.",
    reactionMeta: "tarcza",
  },
  arcane_ward: {
    label: "Arkanowa Bariera",
    sheetDesc: "test intelektu za 1 manę — udany neguje cios",
    reactionDesc:
      "Test intelektu — całość albo nic. Sukces = 0 obrażeń. Mana schodzi zawsze.",
    reactionMeta: "d20+INT · 1 many",
  },
  mana_shield: {
    label: "Tarcza Many",
    sheetDesc: "maną pochłoń obrażenia najbliższego ciosu",
    reactionDesc:
      "Bez rzutu — pochłaniasz część ciosu maną (2 obr. za 1 manę, limit z rangi).",
    reactionMeta: "za manę · 1/rundę",
  },
};

export const DEFENSE_ORDER: DefenseReaction[] = [
  "dodge",
  "shield_block",
  "arcane_ward",
  "mana_shield",
];

// Backendowy klucz reakcji → wybór w modalu (ReactionChoice).
export const DEFENSE_KEY_TO_CHOICE: Record<DefenseReaction, "dodge" | "block" | "ward" | "mana"> = {
  dodge: "dodge",
  shield_block: "block",
  arcane_ward: "ward",
  mana_shield: "mana",
};

// Powód niedostępności → krótki tekst PL do wyszarzonej opcji (tooltip/podpis).
export function defenseReasonText(reason: string | null | undefined): string | null {
  switch (reason) {
    case "no_mana":
      return "brak many";
    case "no_shield":
      return "brak tarczy";
    case "cap_reached":
      return "limit reakcji w tej rundzie";
    case "locked":
      return "zablokowane po nieudanym uniku";
    default:
      return null;
  }
}

// Znormalizuj: preferuj `detailed` (key/available/reason); w razie braku (stary backend)
// zbuduj z listy dostępnych kluczy (wszystkie available=true).
export function normalizeDefenseDetails(
  detailed: DefenseOptionDetail[] | undefined | null,
  fallbackAvailableKeys: string[] | undefined | null,
): DefenseOptionDetail[] {
  if (Array.isArray(detailed) && detailed.length) return detailed;
  return (fallbackAvailableKeys ?? []).map((key) => ({
    key,
    available: true,
    reason: null,
  }));
}
