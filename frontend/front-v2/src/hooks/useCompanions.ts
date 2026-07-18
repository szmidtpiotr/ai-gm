// #1192 FAZA TW — server-state towarzyszy podróży + wierzchowców.
// Endpointy zwracają kopertę {ok, data} (parytet z services_shop) — rozpakowujemy do data.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ActiveCompanion, LocationCompanions } from "@/lib/companions";

type Envelope<T> = { ok: boolean; data: T };

/** GET /characters/{id}/companions — aktywni towarzysze (wierzchowiec + bojowy). */
export function useCompanions(characterId: number | undefined) {
  return useQuery({
    queryKey: ["companions", characterId],
    enabled: !!characterId,
    staleTime: 0,
    queryFn: () =>
      apiFetch<Envelope<ActiveCompanion[]>>(`/characters/${characterId}/companions`).then(
        (r) => r.data,
      ),
  });
}

/** GET /locations/{key}/companions — do rekrutacji w osadzie (stajnia/karczma). */
export function useLocationCompanions(
  locationKey: string | undefined,
  characterId: number | undefined,
) {
  return useQuery({
    queryKey: ["companions-at", locationKey, characterId],
    enabled: !!locationKey && !!characterId,
    staleTime: 0,
    queryFn: () =>
      apiFetch<Envelope<LocationCompanions>>(
        `/locations/${encodeURIComponent(locationKey!)}/companions?character_id=${characterId}`,
      ).then((r) => r.data),
  });
}

interface AcquireVars {
  companionKey: string;
  customName?: string;
  campaignId?: number;
}

function invalidate(qc: ReturnType<typeof useQueryClient>, characterId: number | undefined) {
  qc.invalidateQueries({ queryKey: ["companions", characterId] });
  qc.invalidateQueries({ queryKey: ["companions-at"] });
  qc.invalidateQueries({ queryKey: ["character", characterId] }); // złoto
}

/** POST /characters/{id}/companions/hire — najem (1. dzień płatny z góry). */
export function useHireCompanion(characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: AcquireVars) =>
      apiFetch(`/characters/${characterId}/companions/hire`, {
        method: "POST",
        body: { companion_key: v.companionKey, campaign_id: v.campaignId },
      }),
    onSuccess: () => invalidate(qc, characterId),
  });
}

/** POST /characters/{id}/companions/buy — kupno na własność. */
export function useBuyCompanion(characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: AcquireVars) =>
      apiFetch(`/characters/${characterId}/companions/buy`, {
        method: "POST",
        body: { companion_key: v.companionKey, custom_name: v.customName, campaign_id: v.campaignId },
      }),
    onSuccess: () => invalidate(qc, characterId),
  });
}

/** POST /characters/{id}/companions/dismiss — zwolnienie. */
export function useDismissCompanion(characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (companionId: number) =>
      apiFetch(`/characters/${characterId}/companions/dismiss`, {
        method: "POST",
        body: { companion_id: companionId },
      }),
    onSuccess: () => invalidate(qc, characterId),
  });
}
