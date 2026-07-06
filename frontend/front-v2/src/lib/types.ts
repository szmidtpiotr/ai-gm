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
