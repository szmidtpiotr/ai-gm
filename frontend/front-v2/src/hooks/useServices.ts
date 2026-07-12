// #1292 — server-state modala Usług (odczyt katalogu usług dla lokacji, zakup).
// Mirror wzorca useShop.ts, ale usługi (game_config_services) zamiast towaru NPC.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ServicesBatchResult, ServicesData } from "@/lib/services";

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

interface BuyBatchVars {
  serviceKeys: string[];
  characterId: number;
}

/** POST /services/buy-batch → { data: { items, total_paid_gp, gold_gp } }. Zakup wieloraki
 * (multi-select → podsumowanie → potwierdzenie), atomowy po stronie backendu. */
export function useBuyServicesBatch(locationKey: string | undefined, characterId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: BuyBatchVars) =>
      apiFetch<{ ok: boolean; data: ServicesBatchResult }>(`/services/buy-batch`, {
        method: "POST",
        body: { character_id: v.characterId, service_keys: v.serviceKeys },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["services", locationKey, characterId] });
      qc.invalidateQueries({ queryKey: ["character", characterId] });
    },
  });
}
