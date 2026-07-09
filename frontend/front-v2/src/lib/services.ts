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
