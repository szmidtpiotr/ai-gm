// WL-5 (#1504/#1505) — server-state pływów (Wybrzeże Łez).
// GET stanu pływu dla panelu ŻAR. Read-only. Licznik godzin tylko z Tabliczką pływów.
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface TideState {
  phase: "odplyw" | "przyplyw";
  phase_label: string;
  is_flood: boolean;
  passable: boolean;        // czy plycizna przejezdna teraz
  on_coast: boolean;        // pokazać wskaźnik?
  on_shallows: boolean;     // stoję na plycizna?
  current_hex_type: string;
  next_phase: "odplyw" | "przyplyw";
  next_phase_label: string;
  has_board: boolean;       // niesie Tabliczkę pływów?
  hours_to_change: number | null; // licznik — null bez tabliczki
  cycles_per_day: number;
  ingame_hours: number;
}

/** GET /campaigns/{id}/tide?character_id — stan pływu dla wskaźnika na wybrzeżu. */
export function useTide(campaignId: number | undefined, characterId: number | undefined) {
  return useQuery({
    queryKey: ["tide", campaignId, characterId],
    enabled: !!campaignId && !!characterId,
    staleTime: 0,
    queryFn: () =>
      apiFetch<TideState>(`/campaigns/${campaignId}/tide?character_id=${characterId}`),
  });
}
