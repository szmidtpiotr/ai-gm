// Backend response shapes (subset used by the wejście/hub/profil surfaces).

export interface HeroSheet {
  archetype?: string;
  class?: string;
  hp?: number;
  max_hp?: number;
  hp_current?: number;
  current_mana?: number;
  max_mana?: number;
  level?: number;
  gold_gp?: number;
  gold?: number;
  [k: string]: unknown;
}

export interface Hero {
  id: number;
  name: string;
  race: string;
  campaign_id: number | null;
  campaign_title: string | null;
  campaign_status: string | null;
  status: string | null;
  hero_status: "idle" | "in_campaign" | "in_dungeon" | string;
  campaigns_completed: number;
  total_xp_lifetime: number;
  sheet_json: HeroSheet;
}

export interface Campaign {
  id: number;
  title: string;
  status: string;
  mode: string | null;
  system_id?: string | null;
  language?: string | null;
  owner_user_id?: number | null;
  character_id: number | null;
  character_count: number;
  created_at?: string | null;
  description: string;
  plan_ready: boolean;
  hero_blocked: boolean;
  hero_status?: string | null;
  /** Only present on the single-campaign detail endpoint (owner view). */
  gm_plan_json?: string | null;
}

// F-09 — gotowe kampanie z Kuźni (GET /campaign-templates → items).
export interface CampaignTemplate {
  id: number;
  title: string;
  description?: string | null;
  atmosphere?: string | null;
  difficulty_rating?: number | null;
  play_count?: number | null;
}

// F-09 — loch (GET /dungeons → dungeons).
export interface Dungeon {
  key: string;
  label?: string | null;
  name?: string | null;
  atmosphere?: string | null;
  loot_tier?: number | null;
  min_level?: number | null;
  cooldown?: { ready: boolean; hours_remaining?: number | null } | null;
}

// #1095 — read-only viewer paged turns.
export interface TurnHistoryEntry {
  turn_number: number;
  user_text?: string | null;
  assistant_text?: string | null;
  created_at?: string | null;
}
export interface TurnHistoryPage {
  campaign_id: number;
  title: string;
  status: string;
  total_count: number;
  turns: TurnHistoryEntry[];
}

// F-11 — LLM identity preview (POST /characters/{id}/generate-identity).
export interface IdentityPreview {
  appearance: string;
  personality: string;
  bonds: Array<{ description: string; type: string }>;
  weaknesses: Array<{ description: string; type: string }>;
}

export interface LlmSettings {
  mode: string;
  provider: string;
  base_url: string;
  model: string;
  api_key_set: boolean;
  source: string;
}

export interface Chronicle {
  legend_digest?: string | null;
  chapters?: Array<Record<string, unknown>>;
  abandonment_note?: string | null;
  [k: string]: unknown;
}

// ── F-12 ekran gry (KROK 4 #1233) ────────────────────────────────────────────

// GET /campaigns/{id}/clock — zegar świata gry (sekcja 8, strumień).
export interface ClockState {
  ingame_hours: number;
  day: number;
  hour: number;
  hour_str: string; // "22:00"
  period: string; // "Rano" | "Popołudnie" | "Wieczór" | "Noc"
  display: string; // "Dzień 3, 14:00 Popołudnie"
}

// GET /characters/{id} — pełny bohater (paski HP/Mana + rail atrybutów).
export interface CharacterDetail {
  id: number;
  campaign_id: number | null;
  user_id: number | null;
  name: string;
  race: string;
  sheet_json: HeroSheet;
  current_location_label?: string | null;
  safe_for_rest?: boolean;
}

// Element listy quick-action chipów (suggested_actions z odpowiedzi tury).
export interface SuggestedAction {
  label?: string | null;
  text?: string | null;
  type?: string | null;
  icon?: string | null;
  [k: string]: unknown;
}

// Odpowiedź POST /campaigns/{id}/turns (podzbiór używany przez ekran gry).
export interface TurnResponse {
  turn_number?: number;
  prose?: string;
  route?: string;
  result?: Record<string, unknown> | null;
  suggested_actions?: SuggestedAction[];
  skill_test_pending?: Record<string, unknown> | null;
  combat_state?: Record<string, unknown> | null;
  clock?: ClockState | null;
  [k: string]: unknown;
}

// ── F-43/F-47 mapa świata + podróż (KROK 4 FE8 #1235) ────────────────────────

export type HexStatus = "discovered" | "known" | "outline" | "unexplored";

// Jeden heks z GET /campaigns/{id}/world-map (widok gracza, z mgłą wojny).
export interface WorldHex {
  q: number;
  r: number;
  hex_type: string | null;
  label: string | null;
  status: HexStatus;
}

export interface HexTypeCfg {
  hex_type: string;
  label: string;
  map_color: string;
  map_icon: string;
}

export interface WorldMapResponse {
  hexes: WorldHex[];
  teleport_connections: unknown[];
  current_hex: { q: number; r: number } | null;
  hex_types: Record<string, HexTypeCfg>;
}

// Odpowiedź POST /campaigns/{id}/travel (podzbiór — cinematyka + advance).
export interface TravelResult {
  total_hours?: number;
  clock?: ClockState | null;
  arrived_hex?: { q: number; r: number } | null;
  hex_data?: {
    hex_type?: string | null;
    label?: string | null;
    atmosphere?: string | null;
  } | null;
  encounter?: { enemy_key?: string | null } | null;
  [k: string]: unknown;
}

// Znormalizowana karta rzutu (F-52) — aktor decyduje o stronie/kolorze (sekcja 6).
export interface RollCardData {
  actor: "player" | "enemy";
  title: string; // "TEST: PERSWAZJA" / "WYJEC — ATAK PAZURAMI"
  cells: Array<{ k: string; v: string; sum?: boolean; res?: boolean }>;
  crit?: boolean; // Nat 20 — złoty flash
  fumble?: boolean; // Nat 1 — krwawy flash
}
