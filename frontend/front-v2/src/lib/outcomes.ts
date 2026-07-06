// FE10 modale wyników walki (#1237 / F-27..F-32) — pochodne danych dla modali
// koniec-walki/łup/śmierć/zwycięstwo-loch/level-up/drop. Źródło: makiety
// zar7-koniec / zar7-smierc / zar7-zwyciestwo / zar9-levelup / zar9-drop.
import type { CombatState, LootItem } from "@/lib/types";

// ── XP: próg poziomu (parytet z DEFAULT_XP_LEVEL_THRESHOLDS w xp_service) ──────
// Klucz = poziom, wartość = skumulowane XP wymagane. Klient liczy postęp paska;
// admin może nadpisać progi w DB — wtedy pasek jest przybliżeniem (liczby XP z
// backendu pozostają prawdą). Dla DEV (domyślne progi) pasek jest dokładny.
const XP_THRESHOLDS: Record<number, number> = {
  1: 0,
  2: 100,
  3: 250,
  4: 450,
  5: 700,
  6: 1000,
  7: 1350,
  8: 1750,
  9: 2200,
  10: 2700,
};
const MAX_LEVEL = 10;

export function levelFromLifetime(lifetime: number): number {
  let lvl = 1;
  for (let l = 2; l <= MAX_LEVEL; l++) {
    if (lifetime >= XP_THRESHOLDS[l]) lvl = l;
    else break;
  }
  return lvl;
}

export interface XpProgress {
  level: number;
  intoLevel: number; // XP zdobyte w obrębie bieżącego poziomu
  span: number; // XP potrzebne na cały bieżący poziom
  toNext: number; // ile brakuje do następnego
  basePct: number; // % paska przed przyrostem
  gainPct: number; // % przyrostu (segment glow)
  atCap: boolean;
}

/** Postęp XP: pasek base (przed walką) + segment gain (przyrost z walki). */
export function xpProgress(lifetime: number, gain: number): XpProgress {
  const lvl = levelFromLifetime(lifetime);
  if (lvl >= MAX_LEVEL) {
    return { level: lvl, intoLevel: 0, span: 1, toNext: 0, basePct: 100, gainPct: 0, atCap: true };
  }
  const base = XP_THRESHOLDS[lvl];
  const next = XP_THRESHOLDS[lvl + 1];
  const span = Math.max(1, next - base);
  const intoLevel = Math.max(0, lifetime - base);
  const before = Math.max(0, intoLevel - Math.max(0, gain));
  const basePct = clampPct((before / span) * 100);
  const gainPct = clampPct((Math.min(intoLevel, span) / span) * 100) - basePct;
  return {
    level: lvl,
    intoLevel: Math.min(intoLevel, span),
    span,
    toNext: Math.max(0, next - lifetime),
    basePct,
    gainPct: Math.max(0, gainPct),
    atCap: false,
  };
}

function clampPct(v: number): number {
  return Math.max(0, Math.min(100, v));
}

// ── Łup: normalizacja wpisu puli do wyświetlenia w siatce ─────────────────────

export interface LootView {
  name: string;
  qtyLabel: string;
  kind: "gold" | "consumable" | "weapon" | "item";
  rare: boolean;
}

export function lootView(entry: LootItem): LootView {
  const raw = String(entry.label || entry.source_key || entry.key || "?").replace(/_/g, " ");
  const name = raw.charAt(0).toUpperCase() + raw.slice(1);
  const qty = Number(entry.qty ?? entry.quantity ?? 1) || 1;
  const type = String(entry.source_type || "").toLowerCase();
  const kind: LootView["kind"] =
    type === "weapon" ? "weapon" : type === "consumable" ? "consumable" : "item";
  const rare = !!entry.is_special || Number(entry.rarity ?? 0) >= 2;
  return {
    name,
    qtyLabel: qty > 1 ? `×${qty}` : type === "consumable" ? "×1" : "sztuka",
    kind,
    rare,
  };
}

/** Odczyt niezabranej puli łupu z zakończonego stanu walki. */
export function lootPool(cs: CombatState | null | undefined): LootItem[] {
  const p = (cs as Record<string, unknown> | null | undefined)?.loot_pool;
  return Array.isArray(p) ? (p as LootItem[]) : [];
}

// ── Diff karty rzadkiego dropu (zar9-drop) ────────────────────────────────────

export interface DiffRow {
  label: string;
  oldV: string;
  newV: string;
  dir: "up" | "down" | "same" | "none";
}

// Etykieta efektu afiksu (parytet z front/ _affixEffectLabel).
export function affixEffectLabel(eff: { type?: string; value?: number } | undefined): string {
  const t = String(eff?.type || "").toLowerCase();
  const v = Number(eff?.value ?? 0);
  const sign = v >= 0 ? "+" : "";
  if (t === "damage_bonus") return `${sign}${v} obrażeń`;
  if (t === "ac_bonus") return `${sign}${v} pancerza`;
  if (t === "heal_on_hit") return `${sign}${v} leczenia przy trafieniu`;
  if (t === "attack_bonus") return `${sign}${v} do trafienia`;
  return t ? `${t} ${sign}${v}` : "";
}

// Tier → poziom odblokowania czaru (parytet z lib/sheet.tierUnlockLevel).
export function tierUnlockLevel(tier: number): number {
  return Math.max(1, 2 * tier - 1);
}
