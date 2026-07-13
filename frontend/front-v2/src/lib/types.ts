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
  /** #1080 — hidden onboarding tutorial campaign (badge + "skip" button). */
  is_tutorial?: boolean;
  hero_status?: string | null;
  /** Only present on the single-campaign detail endpoint (owner view). */
  gm_plan_json?: string | null;
  /** F-77 (#1268) — #1009/#1097 bramka finału otwarta (cel przygody osiągnięty). */
  finale_available?: boolean;
  /** MP: gospodarz sesji (finał tylko dla niego). Solo → null. */
  host_user_id?: number | null;
}

// Odpowiedź POST /campaigns/{id}/travel-resume (PT12 #1122).
export interface TravelResumeResult {
  ok: boolean;
  message?: string;
  arrived_hex?: { q: number; r: number } | null;
  encounter?: { enemy_key?: string | null; enemy_label?: string | null } | null;
  current_clock?: ClockState | null;
  suggested_actions?: SuggestedAction[];
  /** true gdy wznowienie rozpoczęło walkę (encounter) — front przechodzi do walki. */
  combat_started?: boolean;
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
export interface WeatherState {
  type: string; // "clear" | "clouds" | "rain" | "storm" | "fog" | "snow" | "heat"
  type_label: string; // "deszcz"
  intensity: string; // "light" | "moderate" | "heavy"
  intensity_label: string; // "słaby" | "umiarkowany" | "silny"
  label: string; // "silny deszcz" | "mgła"
  march_mult: number; // 1.0 = brak wpływu na marsz
  slows_travel: boolean;
  effect: string | null; // "marsz wolniejszy" | null
}

export interface ClockState {
  ingame_hours: number;
  day: number;
  hour: number;
  hour_str: string; // "22:00"
  period: string; // "Rano" | "Popołudnie" | "Wieczór" | "Noc"
  display: string; // "Dzień 3, 14:00 Popołudnie"
  // #1219 widget — pola opcjonalne (starszy backend ich nie zwraca):
  season?: string | null; // "wiosna" | "lato" | "jesień" | "zima"
  weather?: WeatherState | null;
  is_night?: boolean;
  hours_to_night?: number;
  night_hint?: string | null;
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
  /** Strukturalny ciąg akcji (T33 / suggested_actions.py) — SEARCH, TRAVEL_RESUME, … */
  action?: string | null;
  enabled?: boolean | null;
  reason?: string | null;
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
  skill_test_pending?: SkillTestPending | null;
  combat_state?: Record<string, unknown> | null;
  clock?: ClockState | null;
  completed_beats?: Array<{ key: string; label?: string }>;
  completed_quests?: Array<{ title: string; xp?: number }>;
  gold_events?: Array<{ delta: number; label: string; source?: string; service_key?: string }>;
  /** #1312 — narrator granted an item this turn → green bubble (like beat/quest). */
  granted_items?: Array<{ label: string }>;
  /** #1292 — deterministyczny skrót: otwórz modal Usługi zamiast narracji (bez LLM). */
  open_services?: string;
  /** #1338 BL-C3 — deterministyczny skrót: otwórz modal Rzemiosła (klucz lokacji). */
  open_crafting?: string;
  [k: string]: unknown;
}

// ── F-52/#1299 narracyjny test umiejętności (dice popup jak w walce) ──────────
// Backend (turn_skill_router) zwraca to w odpowiedzi tury, gdy trzeba rzucić kością.
// committed_d20 jest zablokowany serwerowo (anty-cheat) — klient tylko go animuje.
export interface SkillTestPending {
  skill_test_id: string;
  skill_key?: string;
  skill_label?: string;
  committed_d20?: number;
  dc?: number;
  modifier_breakdown?: { total?: number; [k: string]: unknown };
  counter?: { counter_type?: string; dc?: number; [k: string]: unknown };
  [k: string]: unknown;
}

// Mechaniczny wynik z POST /skill-test/resolve (autorytatywny, z serwera).
export interface SkillTestResult {
  skill_key?: string;
  skill_label?: string;
  d20_roll?: number;
  modifier?: number;
  player_total?: number;
  margin?: number;
  outcome?: string;
  nat20?: boolean;
  nat1?: boolean;
  success?: boolean;
  [k: string]: unknown;
}

// Odpowiedź POST /campaigns/{id}/skill-test/resolve.
export interface SkillTestResolveResponse {
  prose?: string;
  skill_test_result?: SkillTestResult;
  turn_number?: number;
  suggested_actions?: SuggestedAction[];
  // D1 (#780): po sukcesie Skradania — bramka przewagi (Atak/Zastraszenie/Wycofaj).
  advantage_gate?: {
    source?: string;
    title?: string;
    options?: SuggestedAction[];
    [k: string]: unknown;
  } | null;
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
  // #1311 — POI/quest metadata (discovered hexes only; the 'known' fog layer never
  // leaks location identity). Let the map render location hexes distinctly from terrain.
  location_key?: string | null;
  is_poi?: boolean;
  is_quest?: boolean;
  has_note?: boolean;
  // #1196 — hex holds this hero's completed, still-buried treasure map (✕ marker).
  is_treasure?: boolean;
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
  cells: Array<{
    k: string;
    v: string;
    sum?: boolean;
    res?: boolean;
    // Kolor komórki wyniku wg skutku dla gracza (nie wg strony): ok=zielony (dobrze
    // — unik udany / 0 HP), bad=czerwony (dostałeś), warn=złoty (neutralnie). Gdy brak,
    // RollCard bierze domyślny kolor po stronie aktora.
    tone?: "ok" | "bad" | "warn";
  }>;
  crit?: boolean; // Nat 20 — złoty flash
  fumble?: boolean; // Nat 1 — krwawy flash
}

// ── FE9 walka (#1236 / F-53/F-24..26/F-52/F-70) ──────────────────────────────
// Kształt z backendu: combat_service._row_to_combat_dict (agent-zmapowane pola).

export type CombatZone = "engaged" | "ranged";

export interface CombatCondition {
  key?: string;
  label?: string;
  runtime?: { level?: number } | null;
  [k: string]: unknown;
}

// Jeden uczestnik walki. Aktywny = combat.current_turn === id. Strona = type.
export interface Combatant {
  id: string; // "player" | slug wroga | "summon:..."
  combatant_id?: string;
  type: "player" | "enemy" | "summon";
  name?: string;
  enemy_key?: string;
  hp_current?: number;
  hp_max?: number;
  defense?: number; // DEF / AC
  initiative_roll?: number | null;
  zone?: CombatZone;
  conditions?: CombatCondition[];
  absorb_hp?: number; // pula absorpcji tarczy (gracz)
  image_url?: string | null;
  // reakcja SF10 — obecne tylko na graczu gdy okno otwarte (damage OBCIĘTE po stronie serwera)
  pending_reaction?: {
    attack_roll?: number;
    round?: number;
    options?: string[];
    nat20?: boolean;
    enemy_name?: string;
  } | null;
  [k: string]: unknown;
}

// BL-A7 (#1344) — relatywny wskaźnik zagrożenia grupy (glyph+label; surowy ratio ukryty).
export interface RelativeThreat {
  glyph: string; // 🟢/🟡/🔴/💀
  label: string; // słaby / wyrównany / groźny / zabójczy
  tier: string; // trivial / even / dangerous / deadly
  count?: number;
}

// Snapshot walki (GET /campaigns/{id}/combat → { active, combat }).
export interface CombatState {
  id?: number;
  round?: number;
  turn_order?: string[];
  current_turn?: string; // "player" | id combatanta
  combatants?: Combatant[];
  status?: "active" | "ended";
  ended_reason?: "victory" | "fled" | "player_dead" | null;
  loot_pool?: unknown;
  relative_threat?: RelativeThreat | null; // BL-A7 (#1344)
  defense_options?: string[]; // WALKA-T2 (#1350): reakcje obronne DOSTĘPNE (available-only)
  // WALKA-T2-FIX (#1359): WSZYSTKIE obrony wg posiadanych skilli + available + reason,
  // żeby UI wyszarzyło niedostępne z powodem zamiast je ukrywać.
  defense_options_detailed?: DefenseOptionDetailWire[];
  [k: string]: unknown;
}

// WALKA-T2-FIX (#1359): kształt wpisu detailed z backendu (patrz lib/combat-defense.ts).
export interface DefenseOptionDetailWire {
  key: string;
  available: boolean;
  reason: string | null;
}

// WALKA-T2 (#1350): typy reakcji obronnej deklarowanych z piguły „Obrona".
export type DefenseReaction = "dodge" | "shield_block" | "arcane_ward" | "mana_shield";

export interface CombatEnvelope {
  active: boolean;
  combat: CombatState | null;
}

// Odpowiedź POST resolve-attack / enemy-turn / resolve-reaction (podzbiór).
export interface CombatActionResult {
  hit?: boolean;
  blocked?: boolean;
  block_reason?: "out_of_range" | "no_ammo" | "unsupported_effect" | string;
  mana_insufficient?: boolean;
  current_mana?: number;
  // rzut gracza
  player_raw_d20?: number;
  attack_total?: number;
  player_nat20?: boolean;
  player_nat1?: boolean;
  target_name?: string;
  target_id?: string;
  enemy_key?: string;
  // rzut wroga
  raw_d20?: number;
  attack_roll?: number;
  target_ac?: number;
  enemy_name?: string;
  // obrażenia / efekt
  damage?: number;
  damage_die?: string;
  damage_rolls?: number[];
  damage_multiplier?: number;
  dodged?: boolean;
  // WALKA-T5-FIX-b (#1357): rzut uniku wroga na atak gracza — do pokazania OBU
  // liczb na karcie (Twój atak vs unik wroga) + werdykt. Źródło: combat_service.py.
  dodge_roll?: {
    raw?: number; // surowy d20 wroga
    modifier?: number; // DEX mod wroga
    total?: number; // raw + modifier
    dodged?: boolean;
    player_roll?: number; // suma ataku gracza (== attack_total)
    verdict?: "hit" | "perfect_dodge" | "fumble_dodge" | "dodged" | string;
  } | null;
  enemy_dead?: boolean;
  mana_spent?: number;
  mana_after?: number;
  spell_type?: "heal" | "effect" | "attack" | "attack_aoe" | string;
  heal_amount?: number;
  heal_rolls?: number[];
  player_hp_remaining?: number;
  player_incapacitated?: boolean;
  // okno reakcji SF10
  reaction_window?: boolean;
  reaction_options?: string[]; // DOSTĘPNE (available-only) — bramka okna reakcji
  reaction_options_detailed?: DefenseOptionDetailWire[]; // #1359: wszystkie + available + reason
  reaction?: {
    dodged?: boolean;
    full_block?: boolean;
    warded?: boolean; // #1324: Arkanowa Bariera — cios znegowany testem INT
    reduction?: number;
    available?: boolean;
    d20?: number; // surowy rzut testu uniku/bloku/bariery — do animacji kości reakcji
    dodge_total?: number;
    block_total?: number;
    ward_total?: number; // #1324
    absorbed?: number; // #1325: Tarcza Many — ile obrażeń pochłonięto maną
    mana_spent?: number; // #1325: ile many faktycznie wydano (ceil pochłonięte / R)
    mana_cost?: number; // #1324: koszt many pobrany za próbę bariery
    current_mana?: number; // #1324/#1325: pula many po reakcji
  } | null;
  // łup / nagrody z zabójczego ciosu (FE10 #1237)
  loot?: LootItem[];
  gold_drop?: number;
  xp_granted?: number;
  dungeon_boss_loot?: LootItem[] | null;
  aoe_hits?: Array<{ loot?: LootItem[]; gold_drop?: number; xp_granted?: number }>;
  // sterowanie pętlą
  advance_turn?: string | "ended" | "awaiting_reaction";
  combat_state?: CombatState | null;
  [k: string]: unknown;
}

// ── FE10 modale wyników walki (#1237 / F-27..F-32) ───────────────────────────

// Wpis puli łupu (combat.loot_pool / result.loot / claim available).
export interface LootItem {
  label?: string | null;
  key?: string | null;
  source_key?: string | null;
  source_type?: "item" | "consumable" | "weapon" | string | null;
  qty?: number | null;
  quantity?: number | null;
  rarity?: number | null;
  is_special?: boolean | null;
  // T6 (#1352): 'rolled' = łup z tabeli wroga, 'consolation' = gwarantowany drobiazg
  // przy pustym losowaniu. Steruje tonem modala końca walki.
  origin?: "rolled" | "consolation" | string | null;
  [k: string]: unknown;
}

// Diff karta celebracji rzadkiego dropu (build_drop_comparison).
export interface DropComparison {
  inventory_id: number;
  name: string;
  item_type: "weapon" | "armor" | string;
  rarity: number;
  rarity_label: string;
  is_special: boolean;
  suggested_slot?: string | null;
  affixes?: Array<{ name?: string; effects?: Array<{ type?: string; value?: number }> }>;
  diff?: Record<string, number | null>;
  [k: string]: unknown;
}

export interface ClaimLootResult {
  claimed: Array<{ comparison?: DropComparison | null; [k: string]: unknown }>;
  available?: LootItem[];
  selected_indexes?: number[];
}

// GET /characters/{id}/xp (get_xp_snapshot).
export interface XpSnapshot {
  xp_available: number;
  xp_lifetime_earned: number;
  stat_point_costs: Record<string, number>;
  stat_value_ceiling: number;
  skill_rank_ceiling: number;
  rank_up_costs?: Record<string, number>;
}

// GET /campaigns/{id}/death-summary (solo_death_service.death_summary_payload).
export interface DeathSummary {
  outcome: "death" | "victory";
  campaign_id: number;
  character_id: number;
  character_name: string;
  character_class: string;
  level: number;
  epitaph: string;
  death_reason: string;
  stats: {
    turn_count?: number;
    gold?: number;
    npcs_met?: number;
    quests_completed?: number;
    [k: string]: unknown;
  };
  [k: string]: unknown;
}

// GET /characters/{id}/resurrect-preview (resurrection_service.cost_preview).
export interface ResurrectPreview {
  enabled: boolean;
  reason?: string;
  uses_remaining?: number | null;
  cost?: Record<string, unknown> | null;
  config?: Record<string, unknown> | null;
}

// GET /campaigns/{id}/dungeon-run.
export interface DungeonRunState {
  dungeon_run?: {
    boss_choice_pending?: boolean;
    cycle?: number;
    rooms_cleared?: number;
    enemies_defeated?: number;
    label?: string | null;
    [k: string]: unknown;
  } | null;
}
