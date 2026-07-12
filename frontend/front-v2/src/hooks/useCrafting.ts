// #1338 BL-C3 — server-state rzemiosła. Odczyt przepisów po kluczu lokacji,
// wykonanie przepisu (craft). Po craftcie unieważniamy postać (złoto) + ekwipunek
// (komponenty zużyte, wynik dodany) — parytet z useShop.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  CharacterRecipes,
  CraftResult,
  ExperimentComponent,
  ExperimentResult,
  LocationCrafting,
} from "@/lib/crafting";

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

// ── #1341 BL-D2 — eksperymenty: ukryte receptury + fuszerki ───────────────────

/** GET /characters/{id}/recipes — trwale odkryte receptury (widoczne po eksperymencie). */
export function useCharacterRecipes(characterId: number | undefined) {
  return useQuery({
    queryKey: ["character-recipes", characterId],
    enabled: !!characterId,
    staleTime: 0,
    queryFn: () => apiFetch<CharacterRecipes>(`/characters/${characterId}/recipes`),
  });
}

/** POST /characters/{id}/craft/experiment — 2–4 komponenty → dopasowanie ukrytej receptury. */
export function useExperiment(characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (components: ExperimentComponent[]) =>
      apiFetch<ExperimentResult>(`/characters/${characterId}/craft/experiment`, {
        method: "POST",
        body: { components },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["character", characterId] });
      qc.invalidateQueries({ queryKey: ["inventory", characterId] });
      qc.invalidateQueries({ queryKey: ["character-recipes", characterId] });
    },
  });
}
