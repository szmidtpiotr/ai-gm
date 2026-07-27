// WL-4 (#1504) — server-state rejsów port↔port (Wybrzeże Łez).
// GET tras z bieżącego portu + POST wykonania rejsu. Mechaniczne, omija LLM.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface SeaRoute {
  route_key: string;
  dest_key: string;
  dest_label: string;
  fare_gp: number;
  hours: number;
  shortcut: boolean;
  affordable: boolean;
}

export interface SeaRoutesData {
  is_port: boolean;
  port_key?: string;
  port_label?: string;
  gold?: number;
  is_night?: boolean;
  has_map?: boolean;
  risk?: string;
  routes: SeaRoute[];
}

export interface VoyageEvent {
  kind: string;
  label?: string;
  narrative?: string;
  hp_loss?: number;
  gold_loss?: number;
  extra_hours?: number;
}

export interface VoyageResult {
  ok: boolean;
  route_key: string;
  dest_key: string;
  dest_label: string;
  fare_gp: number;
  hours: number;
  is_night: boolean;
  used_map: boolean;
  event: VoyageEvent | null;
  gold: number;
  current_hp?: number;
}

/** GET /campaigns/{id}/sea-routes?character_id — trasy dostępne z bieżącego portu. */
export function useSeaRoutes(campaignId: number | undefined, characterId: number | undefined) {
  return useQuery({
    queryKey: ["sea-routes", campaignId, characterId],
    enabled: !!campaignId && !!characterId,
    staleTime: 0,
    queryFn: () =>
      apiFetch<SeaRoutesData>(`/campaigns/${campaignId}/sea-routes?character_id=${characterId}`),
  });
}

/** POST /campaigns/{id}/sail → VoyageResult. Pobiera złoto, przesuwa zegar, losuje zdarzenie. */
export function useSetSail(campaignId: number | undefined, characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { routeKey: string }) =>
      apiFetch<VoyageResult>(`/campaigns/${campaignId}/sail`, {
        method: "POST",
        body: { character_id: characterId, route_key: v.routeKey },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sea-routes", campaignId, characterId] });
      qc.invalidateQueries({ queryKey: ["world-map", campaignId] });
      qc.invalidateQueries({ queryKey: ["local-map", campaignId] });
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
      qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
      qc.invalidateQueries({ queryKey: ["character"] });
    },
  });
}
