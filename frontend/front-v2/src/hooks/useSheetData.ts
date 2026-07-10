// KROK 5 (#1234) — server-state karty postaci: ekwipunek, czary, katalog czarów,
// reputacja + mutacja equip (klik na sylwetce/plecaku). Postać (arkusz) czyta
// useCharacter z useGameData.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  InventoryItem,
  KnownSpell,
  ReputationRow,
  SpellCatalogEntry,
} from "@/lib/sheet";

/** GET /inventory/{id} → { ok, data: InventoryItem[] }. */
export function useInventory(characterId: number | undefined) {
  return useQuery({
    queryKey: ["inventory", characterId],
    enabled: !!characterId,
    queryFn: () => apiFetch<{ data: InventoryItem[] }>(`/inventory/${characterId}`),
    select: (d) => d.data ?? [],
  });
}

/** GET /characters/{id}/spells → znane czary (z rangą). */
export function useSpells(characterId: number | undefined) {
  return useQuery({
    queryKey: ["spells", characterId],
    enabled: !!characterId,
    queryFn: () =>
      apiFetch<{ spells: KnownSpell[] }>(`/characters/${characterId}/spells`),
    select: (d) => d.spells ?? [],
  });
}

/** GET /spells → pełny katalog (do pokazania zablokowanych obok znanych). */
export function useSpellCatalog(enabled: boolean) {
  return useQuery({
    queryKey: ["spell-catalog"],
    enabled,
    staleTime: 10 * 60_000, // config, rzadko się zmienia
    queryFn: () => apiFetch<{ spells: SpellCatalogEntry[] }>(`/spells`),
    select: (d) => d.spells ?? [],
  });
}

export interface PublicSkill {
  key: string;
  label: string;
  linked_stat: string;
  description: string | null;
  rank_ceiling: number | null;
}

/** GET /mechanics/skills → publiczny katalog umiejętności (label/cecha/opis).
 * Zasila tooltip opisu w panelu Umiejętności + ekran awansu (V2). */
export function usePublicSkills(enabled = true) {
  return useQuery({
    queryKey: ["public-skills"],
    enabled,
    staleTime: 10 * 60_000, // config, rzadko się zmienia
    queryFn: () => apiFetch<{ skills: PublicSkill[] }>(`/mechanics/skills`),
    select: (d) => d.skills ?? [],
  });
}

/** GET /characters/{id}/reputation → standing per region. */
export function useReputation(characterId: number | undefined) {
  return useQuery({
    queryKey: ["reputation", characterId],
    enabled: !!characterId,
    queryFn: () =>
      apiFetch<{ reputation: ReputationRow[] }>(
        `/characters/${characterId}/reputation`,
      ),
    select: (d) => d.reputation ?? [],
  });
}

export interface InventoryItemDetail {
  id: number;
  quantity: number;
  equipped: number;
  kind: "weapon" | "consumable" | "item";
  item_type: string;
  name: string;
  description: string | null;
  value_gp: number;
  note: string | null;
  image_url: string | null;
  durability: { current: number; max: number; pct: number; broken: boolean } | null;
  weapon?: {
    damage_die: string | null;
    linked_stat: string | null;
    weapon_type: string | null;
    attack_bonus: number;
  };
  consumable?: {
    effect_type: string | null;
    effect_value: number | null;
    effect_dice: string | null;
  };
  affixes?: Array<{ key: string; label: string; bonus_stat?: string; bonus_value?: number }>;
}

/** GET /inventory/{charId}/{invId}/detail — pełny opis przedmiotu (obraz, opis, notatka). */
export function useInventoryDetail(
  characterId: number | undefined,
  inventoryId: number | null,
) {
  return useQuery({
    queryKey: ["inventory-detail", characterId, inventoryId],
    enabled: !!characterId && inventoryId !== null,
    queryFn: () =>
      apiFetch<{ ok: boolean; data: InventoryItemDetail }>(
        `/inventory/${characterId}/${inventoryId}/detail`,
      ),
    select: (d) => d.data,
    staleTime: 30_000,
  });
}

/** Odpowiedź POST /inventory/{charId}/use — zużywalne LUB przedmiot-mapa.
 * Mapa: consumed=false + map_reveal z listą odsłoniętych heksów (do animacji). */
export interface UseItemResult {
  ok?: boolean;
  item?: { item_type?: string };
  map_reveal?: { mode: string; count: number; revealed_hexes: [number, number][] };
  narrative?: string;
}

/** POST /inventory/{charId}/use — użyj zużywalnego albo przedmiotu-mapy. */
export function useUseItem(characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (inventoryId: number) =>
      apiFetch<UseItemResult>(`/inventory/${characterId}/use`, {
        method: "POST",
        body: { inventory_id: inventoryId },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventory", characterId] });
      qc.invalidateQueries({ queryKey: ["character", characterId] });
      // Przedmiot-mapa odsłania heksy → odśwież mapę świata (klucz ["world-map", ...])
      // po prefiksie, bo tu nie mamy campaignId — inaczej nowe heksy nie doczytają się.
      qc.invalidateQueries({ queryKey: ["world-map"] });
    },
  });
}

/** DELETE /inventory/{charId}/{invId} — wyrzuć przedmiot. */
export function useDropItem(characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (inventoryId: number) =>
      apiFetch<{ ok: boolean }>(`/inventory/${characterId}/${inventoryId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventory", characterId] });
    },
  });
}

/**
 * POST /inventory/{id}/equip — załóż/zdejmij (slot=null → zdejmij). Po sukcesie
 * unieważnia ekwipunek + arkusz (paski obrony/udźwig zależą od założonych rzeczy).
 */
export function useEquipItem(characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { inventoryId: number; slot: string | null }) =>
      apiFetch<{ ok: boolean }>(`/inventory/${characterId}/equip`, {
        method: "POST",
        body: { inventory_id: v.inventoryId, slot: v.slot },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventory", characterId] });
      qc.invalidateQueries({ queryKey: ["character", characterId] });
    },
  });
}
