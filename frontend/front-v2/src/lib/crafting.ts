// #1338 BL-C3 — Rzemiosło u rzemieślnika NPC. Kontrakt: backend/app/api/crafting.py
// + crafting_service.py. Modal lokacyjny (jak Usługi), NIE npc-owy jak sklep:
// przepisy pochodzą od crafter_type wszystkich rzemieślników w lokacji.

export type CraftOutputType = "consumable" | "weapon_upgrade" | "armor_repair";

export interface RecipeInput {
  item_key: string;
  qty: number;
}

export interface CraftRecipe {
  key: string;
  label: string;
  inputs: RecipeInput[];
  output_type: CraftOutputType | string;
  output_key?: string | null;
  output_qty?: number;
  service_cost_gold: number;
  crafter_type: string;
}

export interface LocationCrafting {
  location_key: string;
  location_label: string | null;
  crafters: string[];
  recipes: CraftRecipe[];
}

export interface CraftResult {
  ok: boolean;
  output_type: string;
  output_key?: string | null;
  output_qty?: number;
  recipe_key: string;
  recipe_label: string;
  service_cost_gold: number;
  dwarf_discount?: boolean;
  gold_after?: number | null;
  consumed?: RecipeInput[];
  weapon_key?: string;
  damage_bonus?: number;
}

// ── #1341 BL-D2 — eksperymenty: ukryte receptury + fuszerki ───────────────────

export interface ExperimentComponent {
  item_key: string;
  qty: number;
}

export type ExperimentOutcome = "discovery" | "failure" | "fumble";

export interface ExperimentResult {
  ok: boolean;
  outcome: ExperimentOutcome;
  matched: boolean;
  experiment_cost_gold: number;
  gold_after?: number | null;
  components: ExperimentComponent[];
  consumed?: ExperimentComponent[];
  message?: string;
  // discovery
  recipe_key?: string;
  recipe_label?: string;
  output_key?: string | null;
  output_qty?: number;
  discovered?: boolean;
  // roll (tylko przy dopasowaniu)
  roll?: {
    skill: string;
    dc: number;
    tier: string;
    raw: number;
    modifier: number;
    total: number;
    is_nat20: boolean;
    is_nat1: boolean;
  };
  // fumble
  fumble?: "loss" | "slag" | "damage" | "cursed";
  self_damage?: number;
  hp_after?: number;
  cursed_item?: { name: string; flaw: string };
}

export interface DiscoveredRecipe {
  recipe_key: string;
  discovered_at: string;
  label?: string | null;
  craft_tier?: string | null;
  output_type?: string | null;
  output_key?: string | null;
}

// ── #1375 BL-E1 — zakładka Receptury: karty z licznikami komponentów + sety ────

export interface RecipeCardInput {
  item_key: string;
  label: string;
  qty: number;
  owned: number;
  enough: boolean;
}

export interface RecipeCard {
  recipe_key: string;
  label: string;
  availability: string; // 'crafter' | 'experiment' | 'loot'
  source?: string | null;
  discovered_at?: string | null;
  craft_tier?: string | null;
  set_key?: string | null;
  output_type: string;
  output_key?: string | null;
  output_qty: number;
  service_cost_gold: number;
  service_cost_gold_hire: number;
  inputs: RecipeCardInput[];
  can_craft_now: boolean;
  requires_skill_self: boolean;
  can_self_craft: boolean;
}

export interface RecipeSetGroup {
  set_key: string;
  set_label: string;
  discovered: RecipeCard[];
  discovered_count: number;
  total: number;
  undiscovered: number;
  complete: boolean;
}

export interface CharacterRecipes {
  character_id: number;
  has_any: boolean;
  can_self_craft: boolean;
  service_markup: number;
  sets: RecipeSetGroup[];
  loose: RecipeCard[];
  discovered: DiscoveredRecipe[]; // back-compat (BL-D2 #1341)
}

/** Tryb wykonania receptury lootowej: samodzielnie (skill) lub zlecenie (×1.5). */
export type CraftMode = "self" | "service";

/** Etykieta wyniku eksperymentu — dramatyczny nagłówek panelu rezultatu. */
export function experimentOutcomeLabel(o: ExperimentOutcome): string {
  switch (o) {
    case "discovery":
      return "Odkrycie!";
    case "failure":
      return "Receptura się wymyka";
    case "fumble":
      return "Fuszerka";
    default:
      return o;
  }
}

/** Ile sztuk komponentu `item_key` posiada bohater (suma stosów z ekwipunku). */
export function ownedQty(inv: { key: string; quantity: number }[] | undefined, itemKey: string): number {
  if (!inv) return 0;
  return inv.reduce((sum, it) => (it.key === itemKey ? sum + (it.quantity || 0) : sum), 0);
}

/** Czy bohaterowi starczy WSZYSTKICH komponentów na dany przepis. */
export function hasAllComponents(
  recipe: CraftRecipe,
  inv: { key: string; quantity: number }[] | undefined,
): boolean {
  return recipe.inputs.every((inp) => ownedQty(inv, inp.item_key) >= inp.qty);
}

/** Czytelna nazwa typu wyniku (badge/podtytuł). */
export function outputTypeLabel(t: string): string {
  switch (t) {
    case "consumable":
      return "Mikstura";
    case "weapon_upgrade":
      return "Ulepszenie broni";
    case "armor_repair":
      return "Naprawa pancerza";
    default:
      return t;
  }
}
