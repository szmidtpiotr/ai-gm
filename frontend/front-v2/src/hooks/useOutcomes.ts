// FE10 modale wyników walki (#1237) — server-state dla modali koniec/łup/śmierć/
// zwycięstwo-loch/level-up/drop. Endpointy silnika (agent-zmapowane).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  ClaimLootResult,
  DeathSummary,
  DungeonRunState,
  ResurrectPreview,
  XpSnapshot,
} from "@/lib/types";

/** POST /combat/loot/claim — zabierz wybrane indeksy z puli łupu. */
export function useClaimLoot(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { characterId: number; selectedIndexes: number[] }) =>
      apiFetch<{ ok: boolean; data: ClaimLootResult }>(
        `/campaigns/${campaignId}/combat/loot/claim`,
        {
          method: "POST",
          body: { character_id: v.characterId, selected_indexes: v.selectedIndexes },
        },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["character"] });
      qc.invalidateQueries({ queryKey: ["inventory"] });
      qc.invalidateQueries({ queryKey: ["combat", campaignId] });
    },
  });
}

/**
 * POST /dungeons/boss-choice — po pokonaniu bossa: zejdź głębiej / wyjdź.
 * Silnik wymaga campaign_id + character_id (DungeonBossChoiceReq) — bez nich 422.
 */
export function useBossChoice(
  campaignId: number | undefined,
  characterId: number | undefined,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (choice: "exit" | "go_deeper") =>
      apiFetch<Record<string, unknown>>(`/dungeons/boss-choice`, {
        method: "POST",
        body: { campaign_id: campaignId, character_id: characterId, choice },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["character"] });
      qc.invalidateQueries({ queryKey: ["dungeon-run"] });
      qc.invalidateQueries({ queryKey: ["dungeon-run-full", campaignId] });
    },
  });
}

/** GET /campaigns/{id}/dungeon-run — stan biegu lochu (boss_choice_pending). */
export function useDungeonRun(campaignId: number | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["dungeon-run", campaignId],
    enabled: !!campaignId && enabled,
    retry: false,
    queryFn: () =>
      apiFetch<DungeonRunState>(`/campaigns/${campaignId}/dungeon-run`),
  });
}

/** GET /characters/{id}/xp — snapshot PD (level-up + pasek XP). */
export function useXpSnapshot(characterId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: ["xp-snapshot", characterId],
    enabled: !!characterId && enabled,
    queryFn: () => apiFetch<XpSnapshot>(`/characters/${characterId}/xp`),
  });
}

/** POST /characters/{id}/xp/spend-stat — rozdziel PD na cechę (level-up). */
export function useSpendStat(characterId: number | undefined, userId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (statKey: string) =>
      apiFetch<{ ok: boolean; xp_available?: number }>(
        `/characters/${characterId}/xp/spend-stat`,
        { method: "POST", body: { stat_key: statKey, user_id: userId } },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["character", characterId] });
      qc.invalidateQueries({ queryKey: ["xp-snapshot", characterId] });
    },
  });
}

/** GET /campaigns/{id}/death-summary — epitafium + statystyki (tylko gdy ended). */
export function useDeathSummary(campaignId: number | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["death-summary", campaignId],
    enabled: !!campaignId && enabled,
    retry: false,
    queryFn: () => apiFetch<DeathSummary>(`/campaigns/${campaignId}/death-summary`),
  });
}

/** GET /characters/{id}/resurrect-preview — dostępność + koszt wskrzeszenia. */
export function useResurrectPreview(characterId: number | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["resurrect-preview", characterId],
    enabled: !!characterId && enabled,
    retry: false,
    queryFn: () =>
      apiFetch<ResurrectPreview>(`/characters/${characterId}/resurrect-preview`),
  });
}

/** POST /characters/{id}/resurrect — wskrzeszenie w miejscu śmierci. */
export function useResurrect(characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<Record<string, unknown>>(`/characters/${characterId}/resurrect`, {
        method: "POST",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["character", characterId] });
      qc.invalidateQueries({ queryKey: ["combat"] });
    },
  });
}
