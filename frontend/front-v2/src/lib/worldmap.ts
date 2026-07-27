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
  // SG-1 #1481 — nowe tereny Siwych Grań.
  lodowiec: Snowflake,
  siarka: Fire,
  las_iglasty: Tree,
  // CB-1 #Czarnobór — czarny_las (bór), trzesawisko (bagno), step (trawy).
  czarny_las: Tree,
  trzesawisko: Waves,
  step: Plant,
  // MP-1 #1495 — Martwe Pustkowia: sol (biała równina → słońce/blask), martwa_ziemia (kości).
  sol: Sun,
  martwa_ziemia: Skull,
  // WL-1 #1505 — Wybrzeże Łez: morze/rafy woda (fale), plycizna mielizna (fale),
  // wydmy piaszczyste wały (żaglówka jak coast — teren nadmorski).
  morze: Waves,
  plycizna: Waves,
  rafy: Mountains,
  wydmy: Sailboat,
  // KN-1 #1483 — Koronne Niziny: pola_uprawne (złote łany zbóż) → roślina jak plains/step.
  pola_uprawne: Plant,
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
  // SG-1 #1481 — skala ŻAR (szacunek panelu) proporcjonalna do hex_type_config:
  // lodowiec 3.5h/hex = najdroższy przechodni teren → 9; siarka i bór jak forest.
  lodowiec: 9,
  siarka: 6,
  las_iglasty: 5,
  // CB-1 #Czarnobór — szacunek panelu proporcjonalny do travel_hours (hex_type_config):
  // czarny_las 3.0h → wysoki 7; trzesawisko 3.5h → 8; step 1.0h → niski 4 (jak plains).
  czarny_las: 7,
  trzesawisko: 8,
  step: 4,
  // MP-1 #1495 — sol 3.0h → wysoki 7 (żar, blask); martwa_ziemia 2.0h → średni 6 (jak siarka).
  sol: 7,
  martwa_ziemia: 6,
  // WL-1 #1505 — Wybrzeże Łez. morze/rafy nieprzejezdne pieszo (szacunek jak sea=6,
  // realnie brak marszu). plycizna 2.0h → 5 (brnięcie); wydmy 1.0h → niski 3 (jak road).
  morze: 6,
  plycizna: 5,
  rafy: 6,
  wydmy: 3,
  // KN-1 #1483 — pola_uprawne 1.0h → niski 4 (jak plains/step); teren cywilizowany, drogi wszędzie.
  pola_uprawne: 4,
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
  lodowiec: "bardzo trudny",
  siarka: "trudny",
  las_iglasty: "umiarkowany",
  // CB-1 #Czarnobór
  czarny_las: "trudny",
  trzesawisko: "bardzo trudny",
  step: "łatwy",
  // MP-1 #1495 — sol trudny (żar/blask, 3.0h); martwa_ziemia umiarkowany (2.0h, średni marsz).
  sol: "trudny",
  martwa_ziemia: "umiarkowany",
  // WL-1 #1505 — Wybrzeże Łez. morze/rafy nieprzejezdne pieszo → "bardzo trudny";
  // plycizna "trudny" (mielizna, pływy w WL-5); wydmy "łatwy" (niski koszt).
  morze: "bardzo trudny",
  plycizna: "trudny",
  rafy: "bardzo trudny",
  wydmy: "łatwy",
  // KN-1 #1483 — pola_uprawne: teren cywilizowany, najbezpieczniejszy ląd → łatwy.
  pola_uprawne: "łatwy",
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
  // SG-1 #1481 — siarka 0.35 to drugi najgroźniejszy biom po bagnie; lodowiec 0.25
  // jak góry. `las_iglasty` (0.22) celowo POZA listą — §5 chce łagodniejszej puli.
  "siarka",
  "lodowiec",
  // CB-1 #Czarnobór — Bór Zmarłych i trzęsawisko = wysokie ryzyko (encounter 0.32/0.40).
  "czarny_las",
  "trzesawisko",
  // MP-1 #1495 — martwa_ziemia 0.42 = serce krainy nieumarłych, najwyższe ryzyko.
  // `sol` (0.28) celowo POZA listą — otwarta równina, ryzyko umiarkowane.
  "martwa_ziemia",
  // WL-1 #1505 — plycizna 0.30 (mielizna + pływy WL-5) = wysokie ryzyko.
  // morze/rafy/wydmy POZA listą: morze/rafy nieprzejezdne pieszo (0.10/0.15),
  // wydmy niskie (0.12).
  "plycizna",
]);
const LOW_RISK = new Set([
  "road",
  "bridge",
  "plains",
  "heath",
  "town",
  "village",
  "castle",
  // CB-1 #Czarnobór — step otwarty, encounter 0.12: niskie ryzyko (§5 wprost).
  "step",
  // WL-1 #1505 — wydmy 0.12: niskie ryzyko (piaszczyste wały, niski koszt).
  "wydmy",
  // KN-1 #1483 — pola_uprawne 0.10 = najniższy encounter w świecie (najbezpieczniejsza kraina).
  "pola_uprawne",
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

/** #1039 — odpowiedź travel odrzucona przez bramkę krainy (coming/locked).
 *  Zwraca dane pod modal blokady albo null (podróż normalna).
 *  Wołane w miejscach wywołania mutacji, celowo NIE w useGameData: import store'u
 *  do modułu hooków rozbijał graf chunków Vite (React error #310 na ekranie gry). */
export function regionBlockFrom(
  res: { ok?: boolean; error?: string; error_code?: string; region_label?: string; region_status?: string },
): { label: string; status: string; message: string } | null {
  if (res?.ok !== false || res.error_code !== "region_locked") return null;
  return {
    label: res.region_label || "Nieznana kraina",
    status: res.region_status || "coming",
    message: res.error || "Kraina niedostępna — za zamkniętą granicą.",
  };
}
