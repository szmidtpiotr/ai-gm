// Server-state queries + mutations for hub / kampanie / kreator (sekcja 8).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  Campaign,
  CampaignTemplate,
  Chronicle,
  Dungeon,
  Hero,
  IdentityPreview,
  LlmSettings,
  TurnHistoryPage,
} from "@/lib/types";

export function useHeroes() {
  return useQuery({
    queryKey: ["heroes"],
    queryFn: () => apiFetch<{ heroes: Hero[] }>("/heroes"),
    select: (d) => d.heroes,
  });
}

export function useCampaigns() {
  return useQuery({
    queryKey: ["campaigns"],
    queryFn: () => apiFetch<{ campaigns: Campaign[] }>("/campaigns"),
    select: (d) => d.campaigns,
  });
}

/** Single campaign detail — carries gm_plan_json (owner view) for progress. */
export function useCampaignDetail(campaignId: number | undefined) {
  return useQuery({
    queryKey: ["campaign", campaignId],
    enabled: !!campaignId,
    queryFn: () => apiFetch<Campaign>(`/campaigns/${campaignId}`),
  });
}

export function useCampaignTemplates() {
  return useQuery({
    queryKey: ["campaign-templates"],
    queryFn: () => apiFetch<{ items: CampaignTemplate[] }>("/campaign-templates"),
    select: (d) => d.items ?? [],
  });
}

export function useDungeons(characterId: number | undefined) {
  return useQuery({
    queryKey: ["dungeons", characterId],
    enabled: !!characterId,
    queryFn: () =>
      apiFetch<{ dungeons: Dungeon[] }>(`/dungeons?character_id=${characterId}`),
    select: (d) => d.dungeons ?? [],
  });
}

export function useTurnsHistory(
  campaignId: number | undefined,
  limit = 50,
  offset = 0,
) {
  return useQuery({
    queryKey: ["turns-history", campaignId, limit, offset],
    enabled: !!campaignId,
    queryFn: () =>
      apiFetch<TurnHistoryPage>(
        `/campaigns/${campaignId}/turns-history?limit=${limit}&offset=${offset}`,
      ),
  });
}

export function useLlmSettings(userId: number | undefined) {
  return useQuery({
    queryKey: ["llm-settings", userId],
    enabled: !!userId,
    queryFn: () => apiFetch<LlmSettings>(`/users/${userId}/llm-settings`),
  });
}

export function useChronicle(userId: number | undefined) {
  return useQuery({
    queryKey: ["chronicle", userId],
    enabled: false,
    queryFn: () => apiFetch<Chronicle>(`/users/${userId}/chronicle`),
  });
}

// ── Mutations ───────────────────────────────────────────────────────────────

/** F-10 — create a campaign (own/pre-built/dungeon), then assign the hero. */
export function useDeleteCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (campaignId: number) =>
      apiFetch<void>(`/campaigns/${campaignId}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["heroes"] });
    },
  });
}

interface CreateCampaignVars {
  title: string;
  ownerUserId: number;
  mode: "solo" | "pre_built" | "dungeon";
  templateId?: number;
}

export function useCreateCampaign() {
  return useMutation({
    mutationFn: (v: CreateCampaignVars) =>
      apiFetch<Campaign>("/campaigns", {
        method: "POST",
        body: {
          title: v.title,
          system_id: "fantasy",
          model_id: "default",
          owner_user_id: v.ownerUserId,
          language: "pl",
          mode: v.mode,
          status: "active",
          ...(v.templateId != null ? { template_id: v.templateId } : {}),
        },
      }),
  });
}

export function useAssignHero() {
  return useMutation({
    mutationFn: (v: { heroId: number; campaignId: number; userId: number }) =>
      apiFetch(`/characters/${v.heroId}/assign-campaign`, {
        method: "POST",
        body: { campaign_id: v.campaignId, user_id: v.userId },
      }),
  });
}

// ── F-11 kreator postaci ──────────────────────────────────────────────────
interface CreateCharacterVars {
  userId: number;
  name: string;
  race: "human" | "dwarf";
  archetype: "warrior" | "scholar" | "rogue";
  backstory: string;
}

export function useCreateCharacter() {
  return useMutation({
    mutationFn: (v: CreateCharacterVars) =>
      apiFetch<Hero>("/characters", {
        method: "POST",
        body: {
          user_id: v.userId,
          name: v.name,
          race: v.race,
          system_id: "fantasy",
          sheet_json: {
            archetype: v.archetype,
            background_note: v.backstory,
            backstory: v.backstory,
          },
        },
      }),
  });
}

export function useGenerateIdentity() {
  return useMutation({
    mutationFn: (characterId: number) =>
      apiFetch<IdentityPreview>(`/characters/${characterId}/generate-identity`, {
        method: "POST",
      }),
  });
}

interface FinalizeVars {
  characterId: number;
  statOverrides: Record<string, number>;
  skills: Record<string, number>;
  skillSlotCurrent: Record<string, string> | null;
  identityOverrides: {
    appearance: string;
    personality: string;
    bonds: Array<{ description: string; type: string }> | null;
    weaknesses: Array<{ description: string; type: string }> | null;
  };
}

export function useFinalizeSheet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: FinalizeVars) =>
      apiFetch<Hero>(`/characters/${v.characterId}/finalize-sheet`, {
        method: "POST",
        body: {
          stat_overrides: v.statOverrides,
          skills: v.skills,
          skill_slot_current: v.skillSlotCurrent,
          identity_overrides: v.identityOverrides,
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["heroes"] });
    },
  });
}
