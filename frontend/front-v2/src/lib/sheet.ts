// KROK 5 (#1234) — pochodne karty postaci: umiejętności (pipsy+bonus), stan,
// czary (grupy per tier), ekwipunek (sylwetka + plecak), reputacja, opis.
// Reguły mechaniki (bonus, biegłość, tiery reputacji) = game_mechanics.md / config.
import type { HeroSheet } from "@/lib/types";

function num(v: unknown, fallback = 0): number {
  const n = typeof v === "string" ? Number(v) : (v as number);
  return Number.isFinite(n) ? (n as number) : fallback;
}

// ── Atrybuty → modyfikatory ──────────────────────────────────────────────────
export function readStatMods(sheet: HeroSheet | undefined): Record<string, number> {
  const raw = ((sheet ?? {}) as Record<string, unknown>).stat_modifiers;
  const out: Record<string, number> = {};
  if (raw && typeof raw === "object") {
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
      out[k.toUpperCase()] = num(v, 0);
    }
  }
  return out;
}

// ── Umiejętności → pipsy rang + bonus ────────────────────────────────────────
// Bonus = mod cechy + ranga + biegłość(+2 gdy ranga ≥ 3). Sufit rang = 3.
// Mapa etykiet/cechy jest kopią game_config_skills (zablokowany config) —
// zamiast dodatkowego zapytania trzymamy ją statycznie po stronie klienta.
const SKILL_META: Record<string, { label: string; stat: string }> = {
  stealth: { label: "Skradanie", stat: "DEX" },
  athletics: { label: "Atletyka", stat: "STR" },
  attack: { label: "Atak", stat: "STR" },
  two_handed: { label: "Broń dwuręczna", stat: "STR" },
  awareness: { label: "Spostrzegawczość", stat: "WIS" },
  persuasion: { label: "Perswazja", stat: "CHA" },
  intimidation: { label: "Zastraszanie", stat: "CHA" },
  survival: { label: "Przetrwanie", stat: "WIS" },
  lore: { label: "Wiedza", stat: "INT" },
  arcana: { label: "Arkana", stat: "INT" },
  medicine: { label: "Medycyna", stat: "WIS" },
  investigation: { label: "Dochodzenie", stat: "INT" },
  lockpick: { label: "Otwieranie zamków", stat: "DEX" },
  acrobatics: { label: "Akrobatyka", stat: "DEX" },
  insight: { label: "Wnikliwość", stat: "WIS" },
  deception: { label: "Oszustwo", stat: "CHA" },
  endurance: { label: "Wytrzymałość", stat: "CON" },
  alchemy: { label: "Alchemia", stat: "INT" },
  pickpocket: { label: "Kieszonkostwo", stat: "DEX" },
  haggling: { label: "Targowanie", stat: "CHA" },
  gamble: { label: "Gra w kości", stat: "CHA" },
  dodge: { label: "Unik", stat: "DEX" },
  shield_block: { label: "Blok tarczą", stat: "STR" },
  wrestling: { label: "Zapasy", stat: "STR" },
  dual_wield: { label: "Walka dwoma broniami", stat: "DEX" },
  ranged_attack: { label: "Atak dystansowy", stat: "DEX" },
  melee_attack: { label: "Atak wręcz", stat: "STR" },
  spell_attack: { label: "Atak zaklęciem", stat: "INT" },
};

export const PROFICIENCY_RANK = 3;
export const PROFICIENCY_BONUS = 2;

export interface SkillRow {
  key: string;
  label: string;
  stat: string;
  rank: number;
  bonus: number;
  proficient: boolean;
}

export function readSkills(sheet: HeroSheet | undefined): SkillRow[] {
  const s = (sheet ?? {}) as Record<string, unknown>;
  const skills = (s.skills && typeof s.skills === "object" ? s.skills : {}) as Record<
    string,
    unknown
  >;
  const mods = readStatMods(sheet);
  const rows: SkillRow[] = [];
  for (const [key, rawRank] of Object.entries(skills)) {
    const meta = SKILL_META[key] ?? { label: prettify(key), stat: "—" };
    const rank = Math.max(0, Math.min(PROFICIENCY_RANK, num(rawRank, 0)));
    const proficient = rank >= PROFICIENCY_RANK;
    const statMod = mods[meta.stat] ?? 0;
    const bonus = statMod + rank + (proficient ? PROFICIENCY_BONUS : 0);
    rows.push({ key, label: meta.label, stat: meta.stat, rank, bonus, proficient });
  }
  // Najpierw z rangą (malejąco), reszta alfabetycznie — jak w makiecie.
  rows.sort((a, b) => b.rank - a.rank || a.label.localeCompare(b.label, "pl"));
  return rows;
}

function prettify(key: string): string {
  return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

// ── Stan (warunki) ───────────────────────────────────────────────────────────
export interface ConditionRow {
  key: string;
  label: string;
  level: number;
  desc: string;
}

export function readConditions(sheet: HeroSheet | undefined): ConditionRow[] {
  const raw = ((sheet ?? {}) as Record<string, unknown>).conditions;
  if (!Array.isArray(raw)) return [];
  return raw.map((c): ConditionRow => {
    const o = (c ?? {}) as Record<string, unknown>;
    const runtime = (o.runtime ?? {}) as Record<string, unknown>;
    const level = num(runtime.level ?? o.level, 0);
    const label = String(o.label ?? o.key ?? "Efekt");
    const desc =
      typeof o.description === "string" && o.description.trim()
        ? o.description
        : level > 0
          ? `Poziom ${level} — kary do testów; zniknie po odpoczynku.`
          : "Aktywny efekt na postaci.";
    return { key: String(o.key ?? label), label, level, desc };
  });
}

// ── Punkty tajemne + tożsamość (opis) ────────────────────────────────────────
export function readArcanePoints(sheet: HeroSheet | undefined): number {
  const s = (sheet ?? {}) as Record<string, unknown>;
  return num(s.arcane_points ?? s.arcanePoints, 0);
}

export interface Identity {
  appearance: string;
  personality: string;
  flaw: string;
  bonds: string[];
  secret: string;
}

export function readIdentity(sheet: HeroSheet | undefined): Identity {
  const id = (((sheet ?? {}) as Record<string, unknown>).identity ?? {}) as Record<
    string,
    unknown
  >;
  const bondsRaw = Array.isArray(id.bonds) ? id.bonds : [];
  const bonds = bondsRaw
    .map((b) => {
      if (typeof b === "string") return b;
      const o = (b ?? {}) as Record<string, unknown>;
      return String(o.text ?? o.description ?? "");
    })
    .filter((t) => t.trim());
  return {
    appearance: String(id.appearance ?? ""),
    personality: String(id.personality ?? ""),
    flaw: String(id.flaw ?? ""),
    bonds,
    secret: String(id.secret ?? ""),
  };
}

// ── Reputacja ────────────────────────────────────────────────────────────────
export interface ReputationRow {
  scope_type: string;
  scope_key: string;
  value: number;
  tier: string;
}

const REP_TIER_LABEL: Record<string, string> = {
  exalted: "Czczony",
  friendly: "Przyjazny",
  neutral: "Neutralny",
  disliked: "Nielubiany",
  hated: "Znienawidzony",
};
export function repTierLabel(tier: string): string {
  return REP_TIER_LABEL[tier] ?? "Neutralny";
}
export function prettyRegion(key: string): string {
  return key
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Czary → grupy per tier (znane + zablokowane) ─────────────────────────────
export interface SpellCatalogEntry {
  key: string;
  label: string;
  tier: number;
  mana_cost: number;
  spell_type: string;
  damage_die: string | null;
  heal_die: string | null;
  description?: string | null;
  race_lock?: string | null;
}
export interface KnownSpell {
  spell_key: string;
  rank: number;
  tier: number;
  mana_cost: number;
}
export interface SpellRow extends SpellCatalogEntry {
  known: boolean;
  rank: number;
}
export interface SpellTierGroup {
  tier: number;
  rows: SpellRow[];
  knownCount: number;
}

// Poziom bohatera bramkuje tiery czarów (T = poziom min. 2·T−1, wg silnika magii).
export function tierUnlockLevel(tier: number): number {
  return Math.max(1, 2 * tier - 1);
}

export function groupSpells(
  catalog: SpellCatalogEntry[],
  known: KnownSpell[],
  race: string | undefined,
): SpellTierGroup[] {
  const knownMap = new Map(known.map((k) => [k.spell_key, k]));
  const byTier = new Map<number, SpellRow[]>();
  for (const sp of catalog) {
    if (sp.race_lock && race && sp.race_lock !== race) continue;
    const k = knownMap.get(sp.key);
    const tier = num(sp.tier, 1);
    const row: SpellRow = { ...sp, tier, known: !!k, rank: k?.rank ?? 0 };
    const arr = byTier.get(tier) ?? [];
    arr.push(row);
    byTier.set(tier, arr);
  }
  return [...byTier.keys()]
    .sort((a, b) => a - b)
    .map((tier) => {
      const rows = (byTier.get(tier) ?? []).sort(
        (a, b) => Number(b.known) - Number(a.known) || a.mana_cost - b.mana_cost,
      );
      return { tier, rows, knownCount: rows.filter((r) => r.known).length };
    });
}

// ── Ekwipunek → sylwetka (equipped) + plecak grupowany ───────────────────────
export interface InventoryItem {
  id: number;
  slot: string | null;
  equipped: number;
  quantity: number;
  label: string;
  item_type: string;
  key: string;
  can_use: boolean;
  weapon_slot: string | null;
  is_light: boolean | null;
  covered_slots: string[];
  durability: { current: number; max: number; pct: number; broken: boolean } | null;
  image_url: string | null;
}

// Kanoniczne sloty sylwetki (Diablo-overlap) + które klucze slotów backendu je
// wypełniają. Broń zajmuje main_hand; tarcza/druga broń → off_hand.
export const DOLL_SLOTS = [
  { slot: "head", label: "Głowa" },
  { slot: "amulet", label: "Amulet" },
  { slot: "chest", label: "Tors" },
  { slot: "main_hand", label: "Broń" },
  { slot: "off_hand", label: "2. ręka" },
  { slot: "hands", label: "Dłonie" },
  { slot: "legs", label: "Nogi" },
  { slot: "feet", label: "Buty" },
] as const;

const SLOT_ALIASES: Record<string, string> = {
  neck: "amulet",
  amulet: "amulet",
  torso: "chest",
  body: "chest",
  chest: "chest",
  weapon: "main_hand",
  main_hand: "main_hand",
  off_hand: "off_hand",
  offhand: "off_hand",
  shield: "off_hand",
  head: "head",
  helmet: "head",
  hands: "hands",
  gloves: "hands",
  legs: "legs",
  feet: "feet",
  boots: "feet",
};

export interface EquippedMap {
  [dollSlot: string]: InventoryItem | undefined;
}

export function splitInventory(items: InventoryItem[]): {
  equipped: EquippedMap;
  backpack: InventoryItem[];
} {
  const equipped: EquippedMap = {};
  const backpack: InventoryItem[] = [];
  for (const it of items) {
    if (it.equipped && it.slot) {
      const canonical = SLOT_ALIASES[it.slot] ?? it.slot;
      equipped[canonical] = it;
      // Broń dwuręczna zajmuje też 2. rękę (mirror w sylwetce).
      if (it.covered_slots?.includes("off_hand") && !equipped["off_hand"]) {
        equipped["off_hand"] = it;
      }
    } else {
      backpack.push(it);
    }
  }
  return { equipped, backpack };
}

// Grupy plecaka: zużywalne / sprzęt+broń / fabularne (collapsible).
export interface BagGroups {
  consumables: InventoryItem[];
  gear: InventoryItem[];
  lore: InventoryItem[];
}
const LORE_TYPES = new Set(["quest", "map", "book", "note", "key", "scroll"]);
const CONSUMABLE_TYPES = new Set(["consumable", "food", "potion"]);

export function groupBackpack(backpack: InventoryItem[]): BagGroups {
  const consumables: InventoryItem[] = [];
  const gear: InventoryItem[] = [];
  const lore: InventoryItem[] = [];
  for (const it of backpack) {
    const t = (it.item_type || "").toLowerCase();
    if (LORE_TYPES.has(t)) lore.push(it);
    else if (CONSUMABLE_TYPES.has(t)) consumables.push(it);
    else gear.push(it);
  }
  return { consumables, gear, lore };
}

// Slot docelowy przy equipowaniu z plecaka (klik) — wg typu/weapon_slot.
export function targetSlotFor(it: InventoryItem): string | null {
  const t = (it.item_type || "").toLowerCase();
  if (t === "weapon") {
    if (it.weapon_slot === "off_hand") return "off_hand";
    return "main_hand";
  }
  if (t === "armor") {
    const c = it.covered_slots?.[0];
    if (c) return SLOT_ALIASES[c] ?? c;
    return "chest";
  }
  if (t === "shield") return "off_hand";
  if (t === "amulet" || t === "ring") return "amulet";
  return null; // nie do założenia
}
