// #1292 — server-state modala Usług (odczyt katalogu usług dla lokacji, zakup).
// Mirror wzorca useShop.ts, ale usługi (game_config_services) zamiast towaru NPC.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ServicesData } from "@/lib/services";

/** GET /services/at-location/{key}?character_id — usługi dostępne tutaj + złoto gracza. */
export function useServicesAtLocation(locationKey: string | undefined, characterId: number | undefined) {
  return useQuery({
    queryKey: ["services", locationKey, characterId],
    enabled: !!locationKey && !!characterId,
    staleTime: 0,
    queryFn: () =>
      apiFetch<{ ok: boolean; data: ServicesData }>(
        `/services/at-location/${encodeURIComponent(locationKey!)}?character_id=${characterId}`,
      ),
    select: (d) => d.data,
  });
}

interface BuyVars {
  serviceKey: string;
  characterId: number;
}

/** POST /services/{key}/buy → { data: { gold_gp, paid_gp, label } }. */
export function useBuyService(locationKey: string | undefined, characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: BuyVars) =>
      apiFetch<{ ok: boolean; data: { gold_gp: number; paid_gp: number; label: string } }>(
        `/services/${v.serviceKey}/buy`,
        { method: "POST", body: { character_id: v.characterId } },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["services", locationKey, characterId] });
      qc.invalidateQueries({ queryKey: ["character", characterId] });
    },
  });
}
