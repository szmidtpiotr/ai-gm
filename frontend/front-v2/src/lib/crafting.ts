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
