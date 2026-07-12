// #1219 — logika wizualizacji zegara świata (widget + popup „Łuk dnia").
// Czyste funkcje nad ClockState; zero stanu, zero I/O. Kolory jako CSS-var
// tokeny ŻAR (sekcja 6) — komponenty nie hardkodują hexów poza gradientem nieba,
// który jest efektem atmosferycznym (świadome odstępstwo, udokumentowane tu).

export type DayPhase = "dawn" | "day" | "dusk" | "night";

export interface PhaseTheme {
  phase: DayPhase;
  label: string; // "Świt" | "Dzień" | "Zmierzch" | "Noc"
  isNight: boolean;
  accent: string; // CSS var — kolor akcentu ikony/ramki
  // Gradient nieba dla łuku (od góry do horyzontu). Efekt atmosferyczny.
  sky: [string, string, string];
  // Delikatny „poblask" krawędzi topbaru (ambient — opcja C).
  ambient: string;
}

/** Faza doby z godziny (0–23). Progi spójne z zegarem/pogodą silnika. */
export function dayPhase(hour: number): DayPhase {
  const h = ((hour % 24) + 24) % 24;
  if (h >= 5 && h < 8) return "dawn";
  if (h >= 8 && h < 17) return "day";
  if (h >= 17 && h < 21) return "dusk";
  return "night";
}

const THEMES: Record<DayPhase, PhaseTheme> = {
  dawn: {
    phase: "dawn",
    label: "Świt",
    isNight: false,
    accent: "var(--gold)",
    sky: ["#3a2c4a", "#8a5a5f", "#e9a06a"],
    ambient: "rgba(233,160,106,0.10)",
  },
  day: {
    phase: "day",
    label: "Dzień",
    isNight: false,
    accent: "var(--gold)",
    sky: ["#2a4a6a", "#4a7fb0", "#a9d0e8"],
    ambient: "rgba(169,208,232,0.06)",
  },
  dusk: {
    phase: "dusk",
    label: "Zmierzch",
    isNight: false,
    accent: "var(--ember)",
    sky: ["#241a2e", "#5f3a52", "#c8683d"],
    ambient: "rgba(255,122,61,0.12)",
  },
  night: {
    phase: "night",
    label: "Noc",
    isNight: true,
    accent: "var(--mana)",
    sky: ["#0b1022", "#161a3a", "#2a2f5a"],
    ambient: "rgba(120,140,220,0.10)",
  },
};

export function phaseTheme(hour: number): PhaseTheme {
  return THEMES[dayPhase(hour)];
}

/**
 * Pozycja ciała niebieskiego (słońce/księżyc) na półokręgu łuku.
 * t=0 → lewy horyzont (wschód), t=0.5 → zenit, t=1 → prawy horyzont (zachód).
 * Dzień: wschód 6:00 → zachód 20:00 (14h). Noc: zachód 20:00 → wschód 6:00 (10h).
 */
export function arcProgress(hour: number): { t: number; body: "sun" | "moon" } {
  const h = ((hour % 24) + 24) % 24;
  const isDay = h >= 6 && h < 20;
  if (isDay) return { t: (h - 6) / 14, body: "sun" };
  const nightH = (h - 20 + 24) % 24; // 0..10
  return { t: nightH / 10, body: "moon" };
}

/** Punkt (x,y) na półokręgu o promieniu R, środek (cx,cy) — dla arcProgress.t. */
export function arcPoint(
  t: number,
  cx: number,
  cy: number,
  r: number,
): { x: number; y: number } {
  const clamped = Math.max(0, Math.min(1, t));
  const angle = Math.PI * (1 - clamped); // t=0 → π (lewo), t=1 → 0 (prawo)
  return { x: cx + r * Math.cos(angle), y: cy - r * Math.sin(angle) };
}

export const SEASON_PL: Record<string, string> = {
  wiosna: "Wiosna",
  lato: "Lato",
  jesień: "Jesień",
  zima: "Zima",
};

export const SEASON_ICON: Record<string, string> = {
  wiosna: "🌸",
  lato: "☀️",
  jesień: "🍂",
  zima: "❄️",
};
