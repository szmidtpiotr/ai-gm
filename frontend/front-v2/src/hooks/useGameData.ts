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
  RelativeThreat,
  SkillTestResolveResponse,
  SuggestedAction,
  TravelResult,
  TravelResumeResult,
  TurnHistoryPage,
  TurnResponse,
  WorldMapResponse,
} from "@/lib/types";

export interface TravelNotice {
  reason: string;
  severity: "warn" | "danger";
  title: string;
  message: string;
  step: number;
  hours_remaining: number;
  destination_label: string | null;
  can_resume: boolean;
  /** Czy gracz może odpocząć TU (safe_for_rest / karczma / po obozie). */
  can_rest?: boolean;
  /** WALKA-T1 (#1349): dla zasadzki (reason=encounter) — wróg do pokazania w modalu.
   *  Brak (null/undefined) → generyczny modal jak dotąd (nieznany/pusty enemy_key). */
  enemy?: { key: string; label: string; image_url: string | null; count: number } | null;
  /** WALKA-T1 (#1349): wskaźnik zagrożenia zasadzki (glyph/label/tier), surowy ratio ukryty. */
  relative_threat?: RelativeThreat | null;
}

/** GET /campaigns/{id}/suggested-actions — bieżące podpowiedzi akcji (chips) +
 * deterministyczny komunikat podróży (`travel_notice`: zmierzch / padasz z sił /
 * wyprawa przerwana) dla stanu kampanii. Pozwala pokazać pille i baner „musisz
 * odpocząć" na wejściu/po reload (POST /turns zwraca je tylko ulotnie, a narrator
 * LLM bywa niekonsekwentny). Nie odpytujemy podczas walki (chips walki inaczej). */
export function useSuggestedActions(
  campaignId: number | undefined,
  characterId: number | undefined,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["suggested-actions", campaignId],
    enabled: !!campaignId && enabled,
    queryFn: () =>
      apiFetch<{ suggested_actions: SuggestedAction[]; travel_notice: TravelNotice | null }>(
        `/campaigns/${campaignId}/suggested-actions${characterId ? `?character_id=${characterId}` : ""}`,
      ),
  });
}

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
      // Narracja mogła przenieść na inny hex (np. do osady) → odśwież mapę lokalną,
      // inaczej submapa nowej osady nie pokaże się (stary cache poprzedniej pozycji).
      qc.invalidateQueries({ queryKey: ["local-map", campaignId] });
      // #1418 — narracja mogła przenieść PIN na mapie świata (przeprawa przez rzekę,
      // opisowa podróż „idę do…") → odśwież world-map, inaczej pin zostaje w starym miejscu.
      qc.invalidateQueries({ queryKey: ["world-map", campaignId] });
      // Odśwież grounded pille (zależą od lokacji/stanu — inaczej pokazują stare
      // podpowiedzi niezgodne z nową lokacją).
      qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
    },
  });
}

/**
 * POST /campaigns/{id}/skill-test/resolve — #1299: rozwiąż narracyjny test
 * umiejętności. Backend używa serwerowego committed_d20 (anty-cheat) i zwraca
 * prozę + wynik. Wołane po zakończeniu animacji kości. Invalidacje jak w submit,
 * by narracja i pille odświeżyły się same.
 */
export function useResolveSkillTest(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { characterId: number; skillTestId: string; d20: number }) =>
      apiFetch<SkillTestResolveResponse>(`/campaigns/${campaignId}/skill-test/resolve`, {
        method: "POST",
        body: {
          character_id: v.characterId,
          skill_test_id: v.skillTestId,
          d20_roll: v.d20,
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      qc.invalidateQueries({ queryKey: ["character"] });
      qc.invalidateQueries({ queryKey: ["combat", campaignId] });
      qc.invalidateQueries({ queryKey: ["local-map", campaignId] });
      qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
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
      qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
      qc.invalidateQueries({ queryKey: ["local-map", campaignId] });
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
      qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
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
      qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
    },
  });
}

// ── #1291 WAIT-4 — Czekanie do pory dnia ────────────────────────────────────

export interface WaitResult {
  ok: boolean;
  delta_hours: number;
  new_clock: { day: number; hour: number; hour_str: string; period: string; display: string };
}

/** POST /characters/{id}/wait — przesuwa zegar bez leczenia (safe_for_rest required). */
export function useWait(
  campaignId: number | undefined,
  characterId: number | undefined,
  userId: number | undefined,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { target?: string; hours?: number }) =>
      apiFetch<WaitResult>(
        `/characters/${characterId}/wait?user_id=${userId ?? ""}` +
          (params.target ? `&target=${encodeURIComponent(params.target)}` : "") +
          (params.hours ? `&hours=${params.hours}` : ""),
        { method: "POST" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
      qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
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

// FAZA ML — mapa lokalna (sub-lokacje osady jako hex-grid map_level=1 pod hubem).
export interface LocalHex {
  id: number;
  q: number;
  r: number;
  hex_type: string | null;
  label: string | null;
  location_key: string | null;
}
export interface LocalMapResponse {
  hub_key: string | null;
  hub_label: string | null;
  hexes: LocalHex[];
  current_local_hex: { q: number; r: number } | null;
  has_local_map: boolean;
}

/** GET /campaigns/{id}/local-map — hex-grid sub-lokacji huba, w którym stoi drużyna.
 * `has_local_map=false` gdy hub ma <2 sub-lokacji. */
export function useLocalMap(campaignId: number | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["local-map", campaignId],
    enabled: !!campaignId && enabled,
    queryFn: () => apiFetch<LocalMapResponse>(`/campaigns/${campaignId}/local-map`),
    refetchInterval: 20_000,
    refetchIntervalInBackground: false,
  });
}

/** POST /campaigns/{id}/local-travel — przejdź do sub-lokacji (+15 min zegara). */
export function useLocalTravel(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (hexId: number) =>
      apiFetch<{ moved: boolean; local_hex: { q: number; r: number }; location_key: string }>(
        `/campaigns/${campaignId}/local-travel`,
        { method: "POST", body: { hex_id: hexId } },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["local-map", campaignId] });
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
      qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
      qc.invalidateQueries({ queryKey: ["character"] });
    },
  });
}

/** GET /campaigns/{id}/travel-estimate — realny czas podróży current→(q,r) (suma
 * travel_hours po trasie), zgodny z zegarem/narracją (nie heurystyka frontendu). */
export function useTravelEstimate(
  campaignId: number | undefined,
  to: { q: number; r: number } | undefined,
) {
  return useQuery({
    queryKey: ["travel-estimate", campaignId, to?.q, to?.r],
    enabled: !!campaignId && !!to,
    staleTime: 60_000,
    queryFn: () =>
      apiFetch<TravelEstimate>(
        `/campaigns/${campaignId}/travel-estimate?to_q=${to!.q}&to_r=${to!.r}`,
      ),
  });
}

// #1405 — szacunek podróży + ścieżka z per-hex kosztem budżetu i bieżący budżet
// marszu → front rysuje podgląd trasy i oznacza heks „tu dziś obóz" (dzienny cap).
export interface TravelEstimate {
  dist: number | null;
  hours: number | null;
  path?: Array<{ q: number; r: number }>;
  steps?: Array<{ q: number; r: number; cost: number }>;
  march?: { hours_today: number; soft_cap: number; hard_cap: number };
}

/**
 * POST /campaigns/{id}/travel — podróż do heksa. Po sukcesie unieważnia mapę,
 * zegar, strumień tur i postać (silnik dopisuje syntetyczną turę + advance scen).
 */
export function useTravel(campaignId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: {
      characterId: number;
      q: number;
      r: number;
      /** #1381 — WorldMap animuje przeskok pina i sam unieważni mapę po
       * animacji; bez tego pin przeskoczyłby na cel przed animacją. */
      deferMap?: boolean;
    }) =>
      apiFetch<TravelResult>(`/campaigns/${campaignId}/travel`, {
        method: "POST",
        body: { character_id: v.characterId, target_hex: { q: v.q, r: v.r } },
      }),
    onSuccess: (_data, v) => {
      if (!v.deferMap) {
        qc.invalidateQueries({ queryKey: ["world-map", campaignId] });
        // #1381 — suggested-actions też odroczone: jego travel_notice odpala modal
        // zasadzki. Bez tego modal wyskakiwał PRZED końcem animacji hop. WorldMap
        // unieważnia je dopiero po animacji (wtedy modal pojawia się na czas).
        qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
      }
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      qc.invalidateQueries({ queryKey: ["turn-stream", campaignId] });
      qc.invalidateQueries({ queryKey: ["character"] });
      qc.invalidateQueries({ queryKey: ["local-map", campaignId] });
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
