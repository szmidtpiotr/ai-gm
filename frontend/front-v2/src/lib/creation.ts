// F-11 — reguły kreatora postaci, portowane 1:1 z frontend/front/js/app.js
// (WIZARD_* + ALL_SKILL_ROWS + budżet umiejętności). Silnik i tak przelicza
// finalny arkusz; te stałe muszą się zgadzać, by podgląd = wynik.

export const WIZARD_MAX_SWAPS = 4;
export const WIZARD_STAT_MIN = 8;
export const WIZARD_STAT_MAX = 18;

export type Race = "human" | "dwarf" | "elf";
export type Archetype = "warrior" | "scholar" | "rogue";

// #1477 (SG-8) — archetypy zamknięte dla rasy. Krasnolud nie gra Łotrzykiem
// (DEX to fabularnie słaba cecha rasy). Fallback offline'owy: serwer podaje to
// samo w GET /creation/races → races[].blocked_archetypes, i on jest źródłem
// prawdy; ta stała ratuje kreator, gdy odpowiedź jeszcze nie doszła.
export const RACE_BLOCKED_ARCHETYPES: Record<Race, Archetype[]> = {
  human: [],
  dwarf: ["rogue"],
  // #1474 — elf leśny nie gra Wojownikiem (CON −1, lekki chód): Zwiadowca albo Stroiciel.
  elf: ["warrior"],
};

export const STAT_KEYS = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"] as const;
export type StatKey = (typeof STAT_KEYS)[number];

export const ARCHETYPE_BONUS: Record<Archetype, Partial<Record<StatKey, number>>> = {
  warrior: { STR: 2, CON: 1 },
  scholar: { INT: 2, WIS: 1 },
  rogue: { DEX: 2, LCK: 1 },
};

export const STAT_META: Record<StatKey, { name: string; desc: string }> = {
  STR: { name: "Siła", desc: "obrażenia w zwarciu, udźwig" },
  DEX: { name: "Zręczność", desc: "inicjatywa, unik, broń dystansowa" },
  CON: { name: "Kondycja", desc: "punkty życia, wytrzymałość" },
  INT: { name: "Intelekt", desc: "moc czarów, wiedza tajemna" },
  WIS: { name: "Roztropność", desc: "percepcja, mana, opór" },
  CHA: { name: "Charyzma", desc: "perswazja, handel" },
  LCK: { name: "Szczęście", desc: "kryty, rzadki łup" },
};

export const RANK_LABEL = ["—", "Trained", "Skilled"] as const;

export interface SkillRow {
  key: string;
  label: string;
  stat: string;
  hint: string;
}

// Metadane etykiet — źródło prawdy dla puli umiejętności to serwer (rolled
// sheet.skills_at_creation). Tu tylko ładne nazwy PL; brakujące klucze
// (FAZA S: acrobatics/dodge/…) dostają fallback z prettify().
export const ALL_SKILL_ROWS: SkillRow[] = [
  { key: "athletics", label: "Atletyka", stat: "STR", hint: "Wspinaczka, sprint, skoki, siłowe wyczyny." },
  { key: "endurance", label: "Wytrzymałość", stat: "CON", hint: "Odporność na ból, zmęczenie, trucizny i choroby." },
  { key: "stealth", label: "Skradanie", stat: "DEX", hint: "Poruszanie się bez hałasu, ukrywanie, zasadzki." },
  { key: "sleight_of_hand", label: "Zręczne Dłonie", stat: "DEX", hint: "Kieszonkowanie, sztuczki, ukrywanie przedmiotów." },
  { key: "arcana", label: "Magia Arkanów", stat: "INT", hint: "Wiedza o zaklęciach, artefaktach i rytuałach." },
  { key: "investigation", label: "Badanie", stat: "INT", hint: "Szukanie wskazówek, analiza śladów, zagadki." },
  { key: "lore", label: "Wiedza", stat: "INT", hint: "Historia, legendy, fakty o świecie." },
  { key: "awareness", label: "Spostrzegawczość", stat: "WIS", hint: "Zauważanie ukrytych wrogów, pułapek, szczegółów." },
  { key: "survival", label: "Przetrwanie", stat: "WIS", hint: "Tropienie, orientacja, obóz, pożywienie." },
  { key: "medicine", label: "Medycyna", stat: "WIS", hint: "Opatrywanie ran, krwawienie, choroby i zatrucia." },
  { key: "persuasion", label: "Perswazja", stat: "CHA", hint: "Przekonywanie, negocjacje i dyplomacja." },
  { key: "intimidation", label: "Zastraszanie", stat: "CHA", hint: "Wywoływanie strachu, wymuszanie posłuszeństwa." },
  { key: "melee_attack", label: "Atak Wręcz", stat: "STR", hint: "Precyzja i technika w walce wręcz." },
  { key: "ranged_attack", label: "Atak Dystansowy", stat: "DEX", hint: "Celność z łukiem, kuszą i bronią miotaną." },
  { key: "spell_attack", label: "Atak Magiczny", stat: "INT", hint: "Precyzja rzucania ofensywnych zaklęć." },
  { key: "alchemy", label: "Alchemia", stat: "INT", hint: "Tworzenie mikstur, trucizn i eliksirów." },
  // FAZA S — rozszerzony katalog silnika (etykiety; pula i tak z serwera).
  { key: "attack", label: "Atak", stat: "STR", hint: "Ogólna celność ataku wręcz." },
  { key: "dodge", label: "Unik", stat: "DEX", hint: "Uchylanie się przed ciosem." },
  { key: "shield_block", label: "Blok Tarczą", stat: "STR", hint: "Zasłona tarczą, redukcja obrażeń." },
  { key: "acrobatics", label: "Akrobatyka", stat: "DEX", hint: "Balans, przewroty, zwinne manewry." },
  { key: "pickpocket", label: "Kradzież Kieszonkowa", stat: "DEX", hint: "Podbieranie przedmiotów niepostrzeżenie." },
  { key: "lockpick", label: "Otwieranie Zamków", stat: "DEX", hint: "Wytrychy, zamki, mechanizmy." },
  { key: "gamble", label: "Hazard", stat: "LCK", hint: "Gry losowe, blef, ryzyko." },
  { key: "haggling", label: "Targowanie", stat: "CHA", hint: "Negocjacja cen u kupców." },
].sort((a, b) => a.key.localeCompare(b.key));

const SKILL_META = new Map(ALL_SKILL_ROWS.map((r) => [r.key, r]));

function prettify(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Etykieta/stat/hint dla dowolnego klucza z puli serwera (fallback dla nowych). */
export function skillMeta(key: string): SkillRow {
  return SKILL_META.get(key) ?? { key, label: prettify(key), stat: "?", hint: "" };
}

export function statMod(v: number): number {
  return Math.floor((v - 10) / 2);
}

export function calcHp(archetype: Archetype, con: number, level = 1): number {
  const base = archetype === "warrior" ? 10 : archetype === "rogue" ? 8 : 6;
  return Math.max(1, base + statMod(con) * level);
}

export function calcMana(archetype: Archetype, intv: number, level = 1): number {
  if (archetype !== "scholar") return 0;
  return Math.max(1, 8 + statMod(intv) * level);
}

/** Netto budżet umiejętności = suma podniesień MINUS suma obniżeń (Opcja A #747). */
export function skillBudgetUsed(
  snapshot: Record<string, number>,
  levels: Record<string, number>,
): number {
  return Object.keys(snapshot).reduce((s, key) => {
    const o = Number(snapshot[key] || 0);
    if (!o) return s;
    return s + ((levels[key] ?? o) - o);
  }, 0);
}

export function canAdjSkill(
  origKey: string,
  delta: number,
  snapshot: Record<string, number>,
  levels: Record<string, number>,
): boolean {
  const o = Number(snapshot[origKey] || 0);
  if (!o) return false;
  const cur = levels[origKey] ?? o;
  const next = cur + delta;
  if (next < 0 || next > 2) return false;
  const test = { ...levels, [origKey]: next };
  return skillBudgetUsed(snapshot, test) <= WIZARD_MAX_SWAPS;
}
