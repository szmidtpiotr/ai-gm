// FE14 (#1263) — server-state drobnych overlayów: recap (F-33) + bug-report (F-46).
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { BugReportBody, BugReportResult, RecapData } from "@/lib/overlays";

/**
 * GET /campaigns/{id}/recap — streszczenie przerwy. Read-only, nie woła LLM.
 * Backend zwraca should_show (czy była >24h przerwa). Bez pollingu, staleTime duży.
 */
export function useRecap(campaignId: number | undefined) {
  return useQuery({
    queryKey: ["recap", campaignId],
    enabled: !!campaignId,
    staleTime: 5 * 60_000,
    retry: false,
    queryFn: () => apiFetch<RecapData>(`/campaigns/${campaignId}/recap`),
  });
}

/** POST /bug-report — zgłoszenie testera (błąd/pomysł/inne) + auto-kontekst. */
export function useBugReport() {
  return useMutation({
    mutationFn: (body: BugReportBody) =>
      apiFetch<BugReportResult>("/bug-report", { method: "POST", body }),
  });
}
