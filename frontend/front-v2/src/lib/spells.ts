// WALKA-T3 (#1353) · współdzielone metadane typów czarów.
// Jedno źródło prawdy dla etykiet PL kategorii + kolejności sekcji — używane
// przez arkusz czarów w walce (ActionSheet) i panel czarów bohatera (PanelSpells).

// Etykieta PL sekcji per `spell_type` z DB (game_config_spells.spell_type).
// Wszystkie realne wartości: attack / attack_aoe / heal / defense / effect /
// effect_aoe / narrative / reaction / summon.
export const SPELL_TYPE_PL: Record<string, string> = {
  attack: "Atakujące",
  attack_aoe: "Obszarowe",
  heal: "Lecznicze",
  defense: "Ochronne",
  effect: "Efekty",
  effect_aoe: "Obszarowe efekty",
  narrative: "Użytkowe",
  reaction: "Reakcje",
  summon: "Przyzwania",
};

// Kolejność sekcji na liście czarów. Narracyjne („Użytkowe") na końcu —
// decyzja designowa: nie chowamy ich w walce, ale schodzą pod czary bojowe.
export const SPELL_TYPE_ORDER: string[] = [
  "attack",
  "attack_aoe",
  "defense",
  "heal",
  "effect",
  "effect_aoe",
  "reaction",
  "summon",
  "narrative",
];

// Etykieta sekcji dla typu; nieznany typ → sam typ jako fallback (nigdy pusty).
export function spellTypeLabel(spellType: string): string {
  return SPELL_TYPE_PL[spellType] ?? spellType;
}

// #975 R6 / #1373 — lustro backendowej reguły `spell_service.learn_spell`.
// `race_lock` = lista ras dopuszczonych do nauki, rozdzielona przecinkami
// ("human", "dwarf", "human,dwarf"). Bohater widzi/uczy się czaru wtedy i tylko
// wtedy, gdy jego rasa jest na liście.
//   • pusty/NULL race_lock = legacy „pula ludzka" → traktowany jak ["human"]
//     (krasnolud wykluczony — używa wyłącznie Rdzeń-magii),
//   • "dwarf" = tylko krasnolud, "human,dwarf" = obie rasy.
// Nieznana rasa traktowana jak „human" (domyślna wartość backendu).
export function raceLockList(raceLock: string | undefined | null): string[] {
  const raw = (raceLock ?? "").trim().toLowerCase();
  const list = raw
    ? raw.split(",").map((s) => s.trim()).filter(Boolean)
    : ["human"];
  return list.length ? list : ["human"];
}

export function canRaceLearnSpell(
  race: string | undefined | null,
  raceLock: string | undefined | null,
): boolean {
  const r = (race ?? "").trim().toLowerCase() || "human";
  return raceLockList(raceLock).includes(r);
}
