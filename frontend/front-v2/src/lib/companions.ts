// #1192 FAZA TW — typy towarzyszy podróży i wierzchowców.

export type CompanionType = "mount" | "hireling" | "animal";

export interface CompanionPassives {
  travel_speed_mult?: number;
  daily_cap_bonus_h?: number;
  escape_enabled?: boolean;
  encounter_chance_mult?: number;
  terrain_speed_mult?: Record<string, number>;
  carry_bonus_kg?: number;
}

/** Aktywny towarzysz gracza (GET /characters/{id}/companions). */
export interface ActiveCompanion {
  id: number;
  companion_key: string;
  type: CompanionType;
  label: string;
  name: string;
  current_hp: number;
  hp_max: number;
  state: "active" | "dead" | "dismissed";
  ownership: "hired" | "owned";
  unpaid_days: number;
  underfed: boolean;
  daily_cost: number;
  upkeep_cost: number;
  passives: CompanionPassives;
  note: string | null;
}

/** Wpis w katalogu rekrutacji w osadzie (GET /locations/{key}/companions). */
export interface RecruitableCompanion {
  key: string;
  label: string;
  type: CompanionType;
  hp_base: number;
  daily_cost: number;
  buy_cost: number | null;
  upkeep_cost: number;
  passives: CompanionPassives;
  description: string | null;
  note: string | null;
}

export interface LocationCompanions {
  items: RecruitableCompanion[];
  character_gold: number;
  has_stable: boolean;
  has_tavern: boolean;
}
