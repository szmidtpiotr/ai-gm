// FE9 walka (#1236) — server-state walki. Query pollowany co 2s TYLKO gdy combat
// aktywny (refetchInterval zwraca false, gdy backend nie ma aktywnej walki);
// mutacje na endpointy silnika (agent-zmapowane w combat.py).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { CombatActionResult, CombatEnvelope } from "@/lib/types";

const COMBAT_POLL_MS = 2_000; // parytet ze starym frontem (combat_ui.js #730)

/**
 * GET /campaigns/{id}/combat → { active, combat }. Zawsze zamontowany (tani GET
 * wykrywa wznowioną walkę po F5), ale POLLING włącza się dopiero gdy walka
 * aktywna — spełnia „refetchInterval tylko gdy combat aktywny".
 */
export function useCombatState(campaignId: number | undefined) {
  return useQuery({
    queryKey: ["combat", campaignId],
    enabled: !!campaignId,
    queryFn: () => apiFetch<CombatEnvelope>(`/campaigns/${campaignId}/combat`),
    // Poll wyłącznie w trakcie aktywnej walki; poza nią 1 fetch (mount/invalidacja).
    refetchInterval: (q) =>
      q.state.data?.active && q.state.data.combat?.status === "active"
        ? COMBAT_POLL_MS
        : false,
    refetchIntervalInBackground: false,
  });
}

/** Config kości 3D zapisany przez admina (GET /game/dice-config, bez auth). */
export function useDiceConfig() {
  return useQuery({
    queryKey: ["dice-config"],
    queryFn: () =>
      apiFetch<{ config: Record<string, unknown> | null }>("/game/dice-config"),
    staleTime: Infinity,
    retry: false,
  });
}

// ── Mutacje akcji walki ──────────────────────────────────────────────────────
// Wszystkie zwracają CombatActionResult z `combat_state` — wołający wpisuje go do
// cache, więc UI odświeża się natychmiast bez czekania na kolejny poll.

function useCombatMutation<V>(
  campaignId: number | undefined,
  fn: (v: V) => Promise<CombatActionResult>,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      if (data?.combat_state) {
        qc.setQueryData<CombatEnvelope>(["combat", campaignId], {
          active: data.combat_state.status === "active",
          combat: data.combat_state,
        });
      }
      qc.invalidateQueries({ queryKey: ["character"] });
      // #1191 — kills feed the Bestiariusz; refresh it after every combat action.
      qc.invalidateQueries({ queryKey: ["bestiary"] });
    },
  });
}

export interface AttackVars {
  raw_d20?: number | null;
  enemy_key?: string | null;
  target_id?: string | null;
  spell_key?: string | null;
}

/** POST /combat/resolve-attack — atak bronią lub czar (spell_key). */
export function useResolveAttack(campaignId: number | undefined) {
  return useCombatMutation<AttackVars>(campaignId, (v) =>
    apiFetch<CombatActionResult>(`/campaigns/${campaignId}/combat/resolve-attack`, {
      method: "POST",
      body: { attacker: "player", ...v },
    }),
  );
}

/** POST /combat/zone-change — Zbliż się / Cofnij się (toggle, zjada turę). */
export function useZoneChange(campaignId: number | undefined) {
  return useCombatMutation<void>(campaignId, () =>
    apiFetch<CombatActionResult>(`/campaigns/${campaignId}/combat/zone-change`, {
      method: "POST",
    }),
  );
}

/** POST /combat/flee — Uciekaj. */
export function useFlee(campaignId: number | undefined) {
  return useCombatMutation<void>(campaignId, () =>
    apiFetch<CombatActionResult>(`/campaigns/${campaignId}/combat/flee`, {
      method: "POST",
    }),
  );
}

/** POST /combat/enemy-turn — driver tury wroga (auto). */
export function useEnemyTurn(campaignId: number | undefined) {
  return useCombatMutation<void>(campaignId, () =>
    apiFetch<CombatActionResult>(`/campaigns/${campaignId}/combat/enemy-turn`, {
      method: "POST",
    }),
  );
}

/** POST /combat/resolve-reaction — SF10 Przyjmij/Unik/Blok/Bariera (#1324). */
export function useResolveReaction(campaignId: number | undefined) {
  return useCombatMutation<"take" | "dodge" | "block" | "ward">(campaignId, (choice) =>
    apiFetch<CombatActionResult>(
      `/campaigns/${campaignId}/combat/resolve-reaction`,
      { method: "POST", body: { choice } },
    ),
  );
}
