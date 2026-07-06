// FE12 Sklep (#1261) — server-state handlu. Odczyt po kluczu NPC, kup/sprzedaj.
// Po każdej transakcji unieważniamy sklep + postać (złoto) + ekwipunek.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ShopData } from "@/lib/shop";

/** GET /shop/by-key/{npcKey}?character_id — towary + sprzedaż + złoto gracza. */
export function useShop(npcKey: string | undefined, characterId: number | undefined) {
  return useQuery({
    queryKey: ["shop", npcKey, characterId],
    enabled: !!npcKey && !!characterId,
    staleTime: 0,
    queryFn: () =>
      apiFetch<{ ok: boolean; data: ShopData }>(
        `/shop/by-key/${encodeURIComponent(npcKey!)}?character_id=${characterId}`,
      ),
    select: (d) => d.data,
  });
}

interface BuyVars {
  npcId: number;
  characterId: number;
  itemType: string;
  itemKey: string;
}

/** POST /shop/{npcId}/buy → { data: { gold_gp, paid_gp, ... } }. */
export function useBuyItem(npcKey: string | undefined, characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: BuyVars) =>
      apiFetch<{ ok: boolean; data: { gold_gp: number; paid_gp: number } }>(
        `/shop/${v.npcId}/buy`,
        {
          method: "POST",
          body: { character_id: v.characterId, item_type: v.itemType, item_key: v.itemKey },
        },
      ),
    onSuccess: () => invalidate(qc, npcKey, characterId),
  });
}

interface SellVars {
  npcId: number;
  characterId: number;
  inventoryId: number;
}

/** POST /shop/{npcId}/sell → { data: { gold_gp, earned_gp, oversupply, ... } }. */
export function useSellItem(npcKey: string | undefined, characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: SellVars) =>
      apiFetch<{
        ok: boolean;
        data: {
          gold_gp: number;
          earned_gp: number;
          base_sell_gp?: number;
          oversupply?: boolean;
          recent_sell_count?: number;
        };
      }>(`/shop/${v.npcId}/sell`, {
        method: "POST",
        body: { character_id: v.characterId, inventory_id: v.inventoryId },
      }),
    onSuccess: () => invalidate(qc, npcKey, characterId),
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  npcKey: string | undefined,
  characterId: number | undefined,
) {
  qc.invalidateQueries({ queryKey: ["shop", npcKey, characterId] });
  qc.invalidateQueries({ queryKey: ["character", characterId] });
  qc.invalidateQueries({ queryKey: ["inventory", characterId] });
}
