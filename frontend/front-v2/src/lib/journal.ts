// FE13 Dziennik + Kronika (#1262 / F-23/F-58/F-79) — kształty odpowiedzi.
// Kontrakty: GET /campaigns/{id}/journal, GET /campaigns/{id}/recap,
// GET /characters/{id}/chronicle (kronika bohatera, read-only).

// ── Dziennik kampanii (Zadania / Wątki) ──────────────────────────────────────
export interface JournalQuest {
  title: string;
  narrative: string;
  status: string; // "active" | "completed"
  quest_type: string; // "main" | "side" | ...
  created_turn?: number;
  completed_turn?: number | null;
}

export interface JournalThread {
  key: string;
  hint: string;
  status: string;
  turn: number;
}

export interface JournalChronEntry {
  type: string; // "event" | "beat"
  text: string;
  turn: number;
}

export interface JournalData {
  quests: JournalQuest[];
  threads: JournalThread[];
  chronicle: JournalChronEntry[];
}

/** Główne zadanie = quest_type main; reszta = poboczne (kolejność: aktywne najpierw). */
export function splitQuests(quests: JournalQuest[]): {
  main: JournalQuest[];
  side: JournalQuest[];
} {
  const main: JournalQuest[] = [];
  const side: JournalQuest[] = [];
  for (const q of quests) {
    (q.quest_type === "main" || q.quest_type === "story" ? main : side).push(q);
  }
  const order = (q: JournalQuest) => (q.status === "completed" ? 1 : 0);
  main.sort((a, b) => order(a) - order(b));
  side.sort((a, b) => order(a) - order(b));
  return { main, side };
}

// ── Recap „Poprzednio…" ──────────────────────────────────────────────────────
export interface RecapData {
  campaign_id: number;
  should_show: boolean;
  hours_since_last: number | null;
  turn_count: number;
  threshold_hours: number;
  summary: string | null;
  recent_turns: Array<{ turn_number: number; player?: string; gm?: string }>;
  active_quests: Array<{ title: string; narrative?: string }>;
}

// ── Kronika bohatera (F-79) — legenda + rozdziały + blizny ────────────────────
export interface ChronicleChapter {
  id: number;
  campaign_id: number;
  outcome: string; // "victory" | "death" | "abandoned"
  chapter_summary?: string | null;
  xp_earned?: number;
  turns_count?: number;
  completed_at?: string | null;
  campaign_title?: string | null;
}

export interface ChronicleScar {
  id: number;
  campaign_id: number;
  abandonment_note?: string | null;
  campaign_title?: string | null;
}

export interface HeroChronicle {
  legend: string | null;
  chapters: ChronicleChapter[];
  scars: ChronicleScar[];
}
