// F-43/F-47 mapa świata — geometria heksów + heurystyki podróży (KROK 4 #1235).
// Heksy flat-top (parytet z makietą zar5). Serwer nie zwraca kosztu podróży per
// heks przed dotarciem, więc panel podróży pokazuje SZACUNKI (teren→czas/ryzyko);
// prawdziwe wartości przychodzą z backendu w odpowiedzi /travel.
import {
  Bank,
  Buildings,
  Fire,
  House,
  HouseLine,
  MapPin,
  Mountains,
  Path,
  Plant,
  Sailboat,
  Skull,
  Snowflake,
  Sun,
  Sword,
  Tree,
  Waves,
  type Icon,
} from "@phosphor-icons/react";

const HEX_SIZE = 26; // promień (środek → wierzchołek)
const HEX_W = HEX_SIZE * 1.5; // odstęp kolumn (flat-top)
const HEX_H = HEX_SIZE * Math.sqrt(3); // wysokość heksa = odstęp rzędów

/** Środek heksa (q,r) w pikselach SVG — flat-top, kolumny nieparzyste przesunięte. */
export function hexToPixel(q: number, r: number): { x: number; y: number } {
  return { x: HEX_W * q, y: HEX_H * (r + q / 2) };
}

/** Wierzchołki polygonu heksa flat-top wokół środka (px,py). */
export function hexPoints(px: number, py: number): string {
  const s = HEX_SIZE;
  const h = HEX_H / 2;
  return [
    [px + s, py],
    [px + s / 2, py + h],
    [px - s / 2, py + h],
    [px - s, py],
    [px - s / 2, py - h],
    [px + s / 2, py - h],
  ]
    .map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`)
    .join(" ");
}

/** Dystans w heksach (współrzędne axialne, cube distance). */
export function hexDistance(
  a: { q: number; r: number },
  b: { q: number; r: number },
): number {
  const dq = a.q - b.q;
  const dr = a.r - b.r;
  return (Math.abs(dq) + Math.abs(dr) + Math.abs(dq + dr)) / 2;
}

// Ikona terenu — Phosphor (nie emoji), renderowana w foreignObject wewnątrz SVG.
const TERRAIN_ICONS: Record<string, Icon> = {
  road: Path,
  bridge: Path,
  plains: Plant,
  heath: Plant,
  forest: Tree,
  hills: Mountains,
  mountains: Mountains,
  mountain: Mountains,
  grania: Mountains,
  przelecz: Mountains,
  swamp: Waves,
  river: Waves,
  water: Waves,
  lake: Waves,
  sea: Waves,
  coast: Sailboat,
  town: Buildings,
  village: House,
  ruins: HouseLine,
  castle: Bank,
  dungeon: Sword,
  cave: Skull,
  desert: Sun,
  tundra: Snowflake,
  snow: Snowflake,
  volcanic: Fire,
};

export function terrainIcon(hexType: string | null | undefined): Icon {
  return (hexType && TERRAIN_ICONS[hexType]) || MapPin;
}

// ── Heurystyki podróży (SZACUNKI wg terenu; prawda z backendu po dotarciu) ────

const TERRAIN_HOURS: Record<string, number> = {
  road: 3,
  bridge: 3,
  plains: 4,
  heath: 4,
  coast: 4,
  forest: 5,
  river: 5,
  desert: 6,
  tundra: 6,
  hills: 6,
  swamp: 6,
  water: 6,
  lake: 6,
  sea: 6,
  przelecz: 7,
  snow: 7,
  mountains: 8,
  mountain: 8,
  grania: 8,
  volcanic: 8,
};

const TERRAIN_DIFFICULTY: Record<string, string> = {
  road: "łatwy",
  bridge: "łatwy",
  plains: "łatwy",
  heath: "łatwy",
  forest: "umiarkowany",
  coast: "umiarkowany",
  river: "umiarkowany",
  desert: "umiarkowany",
  hills: "trudny",
  swamp: "trudny",
  tundra: "trudny",
  przelecz: "trudny",
  mountains: "bardzo trudny",
  mountain: "bardzo trudny",
  grania: "bardzo trudny",
  snow: "bardzo trudny",
  volcanic: "bardzo trudny",
};

// Ryzyko spotkania — high=czerwone ostrzeżenie w panelu.
const HIGH_RISK = new Set([
  "swamp",
  "forest",
  "mountains",
  "mountain",
  "grania",
  "cave",
  "dungeon",
  "ruins",
  "volcanic",
]);
const LOW_RISK = new Set([
  "road",
  "bridge",
  "plains",
  "heath",
  "town",
  "village",
  "castle",
]);

export interface TravelEstimate {
  distance: number;
  hours: number;
  difficulty: string;
  encounter: string;
  encounterWarn: boolean;
}

/** Szacunek podróży current→target na podstawie terenu celu i dystansu. */
export function estimateTravel(
  from: { q: number; r: number } | null,
  to: { q: number; r: number },
  hexType: string | null | undefined,
): TravelEstimate {
  const distance = from ? hexDistance(from, to) : 1;
  const perHex = (hexType ? TERRAIN_HOURS[hexType] : undefined) ?? 5;
  const t = hexType ?? "";
  const difficulty = TERRAIN_DIFFICULTY[t] ?? "umiarkowany";
  const encounterWarn = HIGH_RISK.has(t);
  const encounter = encounterWarn
    ? "wysokie"
    : LOW_RISK.has(t)
      ? "niskie"
      : "średnie";
  return {
    distance,
    hours: Math.max(1, Math.round(perHex * distance)),
    difficulty,
    encounter,
    encounterWarn,
  };
}
