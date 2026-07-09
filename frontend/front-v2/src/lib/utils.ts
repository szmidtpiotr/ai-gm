import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional class names, dedupe conflicting Tailwind utilities. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Usuwa resztkowe tagi mechaniki LLM ([QUEST_COMPLETE:...], [BEAT_COMPLETE:...],
 * [ARC_ADVANCE:...] itd.) z tekstu widocznego dla gracza. Backend strippuje je przy
 * zapisie, ale tokeny streamowane na żywo oraz stare tury w bazie mogą je zawierać.
 * Mirror backendowego strip_all_mechanic_tags (llm_tag_parser.py).
 */
export function stripMechanicTags(s: string | null | undefined): string {
  if (!s) return "";
  return s.replace(/\s*\[[A-Z][A-Z0-9_]+:[^\]]*\]/g, "").trim();
}
