// #1292 — modal Usługi (nocleg/jedzenie/naprawa/uzdrowienie/stajnia/przewodnik/
// posłaniec). Zakup jest mechaniczny — omija narratora/LLM całkowicie.
export interface ServiceItem {
  key: string;
  label: string;
  cost_gp: number;
  description: string | null;
}

export interface ServicesData {
  location_key: string | null;
  items: ServiceItem[];
  character_gold: number;
}

export interface ServicesBatchResult {
  items: Array<{ key: string; label: string; cost_gp: number }>;
  total_paid_gp: number;
  gold_gp: number;
}

// Musi zaczynać się dokładnie od tego prefiksu — backend (turns.py
// _SERVICES_RECEIPT_PREFIX) po nim rozpoznaje ukrytą turę-kwitek i pomija
// SPEND_GOLD (zakup już opłacony), a NarrationLog/buildLog ukrywa dymek gracza
// (isVisiblePlayerText: tekst zaczynający się od "[" nie jest renderowany).
export const SERVICES_RECEIPT_PREFIX = "[SERVICES_RECEIPT:";

/** Tekst ukrytej tury proszącej narratora o krótki opis odbioru zakupionych usług. */
export function buildServicesReceiptText(items: ServicesBatchResult["items"]): string {
  const list = items.map((it) => it.label).join(", ");
  return (
    `${SERVICES_RECEIPT_PREFIX} Bohater właśnie zapłacił i otrzymuje: ${list}. ` +
    "Opisz krótko i naturalnie, jak NPC to podaje/wykonuje. NIE dodawaj tagu " +
    "płatności — już zapłacone. Bez pytań, bez nowych wątków.]"
  );
}
