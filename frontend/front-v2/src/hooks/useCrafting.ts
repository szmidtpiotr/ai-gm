// #1338 BL-C3 — server-state rzemiosła. Odczyt przepisów po kluczu lokacji,
// wykonanie przepisu (craft). Po craftcie unieważniamy postać (złoto) + ekwipunek
// (komponenty zużyte, wynik dodany) — parytet z useShop.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { CraftResult, LocationCrafting } from "@/lib/crafting";

/** GET /locations/{loc}/crafting — przepisy dostępne u lokalnych rzemieślników. */
export function useLocationCrafting(locationKey: string | undefined, characterId: number | undefined) {
  return useQuery({
    queryKey: ["crafting", locationKey, characterId],
    enabled: !!locationKey && !!characterId,
    staleTime: 0,
    queryFn: () => apiFetch<LocationCrafting>(`/locations/${encodeURIComponent(locationKey!)}/crafting`),
  });
}

interface CraftVars {
  characterId: number;
  recipeKey: string;
}

/** POST /characters/{id}/craft — waliduje komponenty+złoto → konsumuje → wytwarza. */
export function useCraft(locationKey: string | undefined, characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: CraftVars) =>
      apiFetch<CraftResult>(`/characters/${v.characterId}/craft`, {
        method: "POST",
        body: { recipe_key: v.recipeKey },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["crafting", locationKey, characterId] });
      qc.invalidateQueries({ queryKey: ["character", characterId] });
      qc.invalidateQueries({ queryKey: ["inventory", characterId] });
    },
  });
}
