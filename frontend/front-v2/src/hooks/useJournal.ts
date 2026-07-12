// FE13 Dziennik + Kronika (#1262) — server-state dziennika, recapu i kroniki.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { HeroChronicle, JournalData, RecapData } from "@/lib/journal";

/** GET /campaigns/{id}/journal → zadania + wątki + kronika kampanii. */
export function useJournal(campaignId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: ["journal", campaignId],
    enabled: !!campaignId && enabled,
    queryFn: () => apiFetch<JournalData>(`/campaigns/${campaignId}/journal`),
  });
}

/** GET /campaigns/{id}/recap → „Poprzednio…" (read-only, bez LLM). */
export function useRecap(campaignId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: ["recap", campaignId],
    enabled: !!campaignId && enabled,
    queryFn: () => apiFetch<RecapData>(`/campaigns/${campaignId}/recap`),
  });
}

/**
 * POST /campaigns/{id}/history/summary — świeże podsumowanie (LLM, persist).
 * Zasila recap „Poprzednio…" po kliknięciu regeneracji. 429 = cooldown.
 */
export function useRegenRecap(campaignId: number | undefined, userId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => {
      const qs = new URLSearchParams({
        user_id: String(userId ?? 1),
        persist: "true",
        max_turns: "200",
        audience: "player",
      });
      return apiFetch<{ summary?: string }>(
        `/campaigns/${campaignId}/history/summary?${qs.toString()}`,
        { method: "POST", body: {} },
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recap", campaignId] });
    },
  });
}

/** GET /characters/{id}/chronicle → legenda + rozdziały + blizny (read-only). */
export function useHeroChronicle(characterId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: ["hero-chronicle", characterId],
    enabled: !!characterId && enabled,
    queryFn: () => apiFetch<HeroChronicle>(`/characters/${characterId}/chronicle`),
  });
}
