// FE14 (#1263) — typy dla drobnych overlayów: recap (F-33) + bug-report (F-46).

// GET /campaigns/{id}/recap — read-only streszczenie przerwy (nie woła LLM).
export interface RecapTurn {
  turn_number: number;
  player?: string | null;
  gm?: string | null;
}
export interface RecapQuest {
  title?: string | null;
  narrative?: string | null;
}
export interface RecapData {
  should_show?: boolean;
  hours_since_last?: number | null;
  summary?: string | null;
  recent_turns?: RecapTurn[];
  active_quests?: RecapQuest[];
}

// POST /bug-report — rodzaj zgłoszenia (parytet ze starym front/ + makietą zar9-bug).
export type ReportType = "bug" | "idea" | "other";

export interface BugReportBody {
  observation: string;
  reproduction?: string;
  report_type: ReportType;
  campaign_id?: number | null;
  js_errors?: unknown[];
  screenshot_base64?: string | null;
}

export interface BugReportResult {
  github_issue_url?: string | null;
}

// „Wróciłeś po N dniach przerwy." — jak w starym renderRecapCard.
export function recapGapLabel(hours?: number | null): string {
  if (hours == null) return "Wróciłeś po dłuższej przerwie.";
  const days = Math.floor(hours / 24);
  if (days >= 1) return `Wróciłeś po ${days} ${days === 1 ? "dniu" : "dniach"} przerwy.`;
  return "Wróciłeś po dłuższej przerwie.";
}
