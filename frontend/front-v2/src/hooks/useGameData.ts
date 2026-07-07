// Server-state queries + mutations for hub / kampanie / kreator (sekcja 8).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  Campaign,
  CampaignTemplate,
  CharacterDetail,
  Chronicle,
  ClockState,
  Dungeon,
  Hero,
  IdentityPreview,
  LlmSettings,
  TravelResult,
  TravelResumeResult,
  TurnHistoryPage,
  TurnResponse,
  WorldMapResponse,
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

// ── F-12 ekran gry (KROK 4 #1233) — strumień tur + zegar + postać ────────────

/** GET /characters/{id} — pełny arkusz (paski HP/Mana + rail atrybutów). */
export function useCharacter(characterId: number | undefined) {
  return useQuery({
    queryKey: ["character", characterId],
    enabled: !!characterId,
    queryFn: () => apiFetch<CharacterDetail>(`/characters/${characterId}`),
  });
}

/** Zegar świata gry — lekki polling (sekcja 8: strumień tur). */
export function useCampaignClock(campaignId: number | undefined) {
  return useQuery({
    queryKey: ["clock", campaignId],
    enabled: !!campaignId,
    queryFn: () => apiFetch<ClockState>(`/campaigns/${campaignId}/clock`),
    refetchInterval: 20_000,
  });
}

/**
 * Strumień tur — auto-odświeżanie bez F5 (sekcja 8). Polling ~6s;
 * zatrzymany gdy karta w tle (refetchIntervalInBackground=false).
 */
export function useTurnStream(campaignId: number | undefined) {
  return useQuery({
    queryKey: ["turn-stream", campaignId],
    enabled: !!campaignId,
    queryFn: () =>
      apiFetch<TurnHistoryPage>(
        `/campaigns/${campaignId}/turns-history?limit=200`,
      ),
    refetchInterval: 6_000,
    refetchIntervalInBackground: false,
  });
}

/**
 * POST /campaigns/{id}/turns — wyślij akcję gracza. Po sukcesie unieważnia
 * strumień tur + zegar + postać → log i paski odświeżają się same.
 */
export function useSubmitTurn(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { characterId: number; text: string }) =>
      apiFetch<TurnResponse>(`/campaigns/${campaignId}/turns`, {
        method: "POST",
        body: { character_id: v.characterId, text: v.text },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      qc.invalidateQueries({ queryKey: ["character"] });
      // FE9 (#1236): narracja mogła rozpocząć walkę — sprawdź stan combat, by baner
      // i pasek akcji pojawiły się bez F5 (poll startuje dopiero gdy walka aktywna).
      qc.invalidateQueries({ queryKey: ["combat", campaignId] });
    },
  });
}

// ── F-77 bramka finału (#1268 / #1097) ───────────────────────────────────────

/** POST /campaigns/{id}/finish — gracz kończy przygodę (bramka #1009 otwarta). */
export function useFinishCampaign(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ ok: boolean; campaign_id: number; ended_at?: string }>(
        `/campaigns/${campaignId}/finish`,
        { method: "POST" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaign", campaignId] });
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["heroes"] });
    },
  });
}

// ── F-80 przyciski po przerwaniu podróży (#1268 / PT12 #1122) ─────────────────

/** POST /campaigns/{id}/travel-resume — mechaniczne „Kontynuuj podróż". */
export function useTravelResume(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<TravelResumeResult>(`/campaigns/${campaignId}/travel-resume`, {
        method: "POST",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      qc.invalidateQueries({ queryKey: ["world-map", campaignId] });
      qc.invalidateQueries({ queryKey: ["character"] });
      qc.invalidateQueries({ queryKey: ["combat", campaignId] });
    },
  });
}

/** POST /campaigns/{id}/build-camp — mechaniczne „Rozbij obóz". */
export function useBuildCamp(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ ok: boolean; current_clock?: ClockState | null }>(
        `/campaigns/${campaignId}/build-camp`,
        { method: "POST" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
      qc.invalidateQueries({ queryKey: ["character"] });
    },
  });
}

/** POST /characters/{id}/rest — długi odpoczynek („Odpocznij" po przerwaniu). */
export function useRestLong(
  campaignId: number | undefined,
  characterId: number | undefined,
  userId: number | undefined,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<Record<string, unknown>>(
        `/characters/${characterId}/rest?type=long&user_id=${userId ?? ""}`,
        { method: "POST" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["character", characterId] });
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
    },
  });
}

// ── F-43/F-47 mapa świata + podróż (KROK 4 FE8 #1235) ────────────────────────

/**
 * GET /campaigns/{id}/world-map — heksy z mgłą wojny + aktualna pozycja +
 * konfiguracja typów terenu. Lekki polling, by nowo odkryte heksy pojawiały
 * się bez F5 (parytet z ekranem gry).
 */
export function useWorldMap(
  campaignId: number | undefined,
  characterId: number | undefined,
) {
  return useQuery({
    queryKey: ["world-map", campaignId, characterId],
    enabled: !!campaignId && !!characterId,
    queryFn: () =>
      apiFetch<WorldMapResponse>(
        `/campaigns/${campaignId}/world-map?character_id=${characterId}`,
      ),
    refetchInterval: 20_000,
    refetchIntervalInBackground: false,
  });
}

/**
 * POST /campaigns/{id}/travel — podróż do heksa. Po sukcesie unieważnia mapę,
 * zegar, strumień tur i postać (silnik dopisuje syntetyczną turę + advance scen).
 */
export function useTravel(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { characterId: number; q: number; r: number }) =>
      apiFetch<TravelResult>(`/campaigns/${campaignId}/travel`, {
        method: "POST",
        body: { character_id: v.characterId, target_hex: { q: v.q, r: v.r } },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["world-map", campaignId] });
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
      qc.invalidateQueries({ queryKey: ["character"] });
    },
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

/** DELETE /characters/{id} — usuń bohatera (kaskadowo powiązane kampanie). */
export function useDeleteHero() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { heroId: number; userId: number }) =>
      apiFetch<{ ok: boolean; deleted_id: number; name: string }>(
        `/characters/${v.heroId}?user_id=${v.userId}`,
        { method: "DELETE" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["heroes"] });
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    },
  });
}

export function useAssignHero() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { heroId: number; campaignId: number; userId: number }) =>
      apiFetch(`/characters/${v.heroId}/assign-campaign`, {
        method: "POST",
        body: { campaign_id: v.campaignId, user_id: v.userId },
      }),
    // Świeżo utworzona kampania (loch/solo) musi trafić do listy zanim Game.tsx
    // wyliczy z niej character_id — inaczej ekran gry twierdzi „brak bohatera".
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["heroes"] });
    },
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
