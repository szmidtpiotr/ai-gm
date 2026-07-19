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
  return s
    // #1469: colon optional — also strips bare tags like [DEATH_TRIGGER].
    .replace(/\s*\[[A-Z][A-Z0-9_]+(?::[^\]]*)?\]/g, "")
    // #1299: narrator czasem dokleja "Roll <skill> d20" jako końcową linię narracji
    // (zamiast pola roll_cue). Backend to przechwytuje i tnie, ale stare tury w bazie
    // oraz tokeny streamowane na żywo mogą ją zawierać — usuń, by dyrektywa mechaniczna
    // nie pokazała się graczowi jako tekst narracji.
    .replace(/\s*(?:\n|^)Roll\s+[^\n]+?\s+d\d+\s*$/i, "")
    .trim();
}
