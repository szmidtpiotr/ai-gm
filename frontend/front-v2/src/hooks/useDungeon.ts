// FE16 loch (#1265) — server-state biegu lochu. Port 1:1 z app.js: run trzymany
// w cache (setQueryData po każdej mutacji move/resolve), silnik bez zmian.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { Dir, DungeonRun } from "@/lib/dungeon";

// ── GET stan biegu (resume / odświeżenie po resolve-tile) ────────────────────

interface RunEnvelope {
  dungeon_run?: DungeonRun | null;
  onboarding_cards?: unknown[];
}

const RUN_KEY = (campaignId: number | undefined) => ["dungeon-run-full", campaignId];

/** GET /campaigns/{id}/dungeon-run — pełny graf biegu. Bez pollingu (jak app.js). */
export function useDungeonRunFull(campaignId: number | undefined) {
  return useQuery({
    queryKey: RUN_KEY(campaignId),
    enabled: !!campaignId,
    retry: false,
    queryFn: () =>
      apiFetch<RunEnvelope>(`/campaigns/${campaignId}/dungeon-run`),
  });
}

/** Ręczne wpisanie świeżego runu do cache (parytet z `_activeDungeonRun = ...`). */
export function useDungeonRunCache(campaignId: number | undefined) {
  const qc = useQueryClient();
  return {
    set(run: DungeonRun | null | undefined) {
      qc.setQueryData<RunEnvelope>(RUN_KEY(campaignId), (prev) => ({
        ...(prev || {}),
        dungeon_run: run ?? (prev?.dungeon_run ?? null),
      }));
    },
    invalidate() {
      qc.invalidateQueries({ queryKey: RUN_KEY(campaignId) });
    },
  };
}

// ── Ruch przez drzwi (L4) ─────────────────────────────────────────────────────

export interface DungeonMoveResult {
  ok: boolean;
  blocked?: boolean;
  reason?: string;
  node_id?: string;
  node?: Record<string, unknown>;
  content?: Record<string, unknown>;
  fog_discovered?: string[];
  is_cleared?: boolean;
  combat?: { error?: string } | Record<string, unknown> | null;
  narrative?: string;
  completed?: boolean;
  dungeon_run?: DungeonRun;
}

/** POST /dungeons/move — kierunek N/S/E/W. */
export function useDungeonMove(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { characterId: number; direction: Dir }) =>
      apiFetch<DungeonMoveResult>(`/dungeons/move`, {
        method: "POST",
        body: {
          campaign_id: campaignId,
          character_id: v.characterId,
          direction: v.direction,
        },
      }),
    onSuccess: () => {
      // Ruch mógł rozpocząć walkę — poll combat wykryje ją bez F5.
      qc.invalidateQueries({ queryKey: ["combat", campaignId] });
      qc.invalidateQueries({ queryKey: ["character"] });
    },
  });
}

// ── Akcja kafla: skrzynia / zagadka / podpowiedź / odpoczynek (L6) ───────────

export interface DungeonTileResult {
  ok: boolean;
  narrative?: string;
  hint?: string;
  solved?: boolean;
  failed_permanently?: boolean;
  heal_amount?: number;
  loot?: Array<{ label?: string; key?: string; quantity?: number }>;
  blocked?: boolean;
  no_charges?: boolean;
  hp_after?: number;
  onboarding_note?: string;
  // chest
  roll?: number;
  dex_mod?: number;
  total?: number;
  dc?: number;
  success?: boolean;
  attempt?: number;
  max_attempts?: number;
  chest_locked_forever?: boolean;
  trap?: { triggered?: boolean; description?: string; damage?: number } | null;
}

/** POST /dungeons/resolve-tile — open_chest | answer_riddle | riddle_hint | rest. */
export function useDungeonResolveTile(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: {
      characterId: number;
      action: "open_chest" | "answer_riddle" | "riddle_hint" | "rest";
      payload?: Record<string, unknown> | null;
    }) =>
      apiFetch<DungeonTileResult>(`/dungeons/resolve-tile`, {
        method: "POST",
        body: {
          campaign_id: campaignId,
          character_id: v.characterId,
          action: v.action,
          payload: v.payload ?? null,
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["character"] });
    },
  });
}

// ── Wyjście / porzucenie (L7) ─────────────────────────────────────────────────

export interface DungeonExitResult {
  ok: boolean;
  relinked_campaign_id?: number | null;
  previous_campaign_id?: number | null;
}

/** POST /dungeons/exit — porzuć (mid-segment) lub wyjdź po wygranej. */
export function useDungeonExit(campaignId: number | undefined) {
  return useMutation({
    mutationFn: (characterId: number) =>
      apiFetch<DungeonExitResult>(`/dungeons/exit`, {
        method: "POST",
        body: { campaign_id: campaignId, character_id: characterId },
      }),
  });
}

/** DELETE /campaigns/{id} — sprzątnij jednorazową kampanię lochu. */
export function useDeleteDungeonCampaign() {
  return useMutation({
    mutationFn: (campaignId: number) =>
      apiFetch<void>(`/campaigns/${campaignId}`, { method: "DELETE" }),
  });
}

// ── Śmierć w lochu (L13) — restore checkpoint + cooldown ─────────────────────

export interface DungeonDeathResult {
  ok: boolean;
  restored?: boolean;
  cooldown_until?: string | null;
}

/** POST /dungeons/death — przywróć punkt kontrolny + cooldown. */
export function useDungeonDeath(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (characterId: number) =>
      apiFetch<DungeonDeathResult>(`/dungeons/death`, {
        method: "POST",
        body: { campaign_id: campaignId, character_id: characterId },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["character"] });
    },
  });
}

// ── Wybór po bossie (L8) — zejdź głębiej / wyjdź ──────────────────────────────

export interface BossChoiceResult {
  ok: boolean;
  choice?: string;
  new_cycle?: number;
  previous_campaign_id?: number | null;
  narrative?: string;
}

/** POST /dungeons/boss-choice — wymaga campaign_id + character_id (silnik). */
export function useDungeonBossChoice(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { characterId: number; choice: "exit" | "go_deeper" }) =>
      apiFetch<BossChoiceResult>(`/dungeons/boss-choice`, {
        method: "POST",
        body: {
          campaign_id: campaignId,
          character_id: v.characterId,
          choice: v.choice,
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["character"] });
      qc.invalidateQueries({ queryKey: ["dungeon-run-full", campaignId] });
    },
  });
}

// ── Aktywny bieg dla bohatera (resume/porzuć na wejściu, E22) ─────────────────

export interface ActiveRunResponse {
  active_run?: (DungeonRun & { campaign_id: number }) | null;
}

/** GET /dungeons/active-run?character_id= — niedokończony bieg (modal wznowienia). */
export function useActiveDungeonRun(characterId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: ["dungeon-active-run", characterId],
    enabled: !!characterId && enabled,
    retry: false,
    queryFn: () =>
      apiFetch<ActiveRunResponse>(
        `/dungeons/active-run?character_id=${characterId}`,
      ),
  });
}
