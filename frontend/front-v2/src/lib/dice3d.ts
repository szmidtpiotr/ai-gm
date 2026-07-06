// F-70 · silnik kości 3D — ZACHOWANY z front/ (dice-box-threejs, THREE r143 + Cannon).
// NIE przepisujemy fizyki; to tylko cienki loader + „recreate-per-roll" wrapper, wierny
// combat_ui.js:1684-1783 (#829). Owinięty w React w Dice3DOverlay.
//
// Dlaczego dice-box-threejs, a nie legacy dice.js: obsługuje predeterminację
// (`1d20@15`) → kość ląduje na wartości już wylosowanej przez backend, i nie ma buga
// „drugi rzut niewidoczny" (#829). To wciąż silnik three.js/cannon ze starego front/.

const BASE = import.meta.env.BASE_URL || "/"; // "/v2/" na DEV
const ASSET_PATH = `${BASE}vendor/dice-box-threejs/`;
const UMD_SRC = `${ASSET_PATH}dice-box-threejs.umd.js`;

type DiceCtor = new (sel: string, opts: Record<string, unknown>) => DiceBox;
interface DiceBox {
  initialize: () => Promise<unknown>;
  roll: (notation: string) => unknown;
  onRollComplete?: () => void;
  initialized?: boolean;
  clearDice?: () => void;
  clear?: () => void;
}

let _loadPromise: Promise<DiceCtor | null> | null = null;

/** Wstrzyknij UMD raz; zwróć konstruktor `window['dice-box-threejs']` lub null. */
export function loadDiceEngine(): Promise<DiceCtor | null> {
  if (_loadPromise) return _loadPromise;
  _loadPromise = new Promise((resolve) => {
    const w = window as unknown as Record<string, unknown>;
    if (typeof w["dice-box-threejs"] === "function") {
      resolve(w["dice-box-threejs"] as DiceCtor);
      return;
    }
    const s = document.createElement("script");
    s.src = UMD_SRC;
    s.async = true;
    s.onload = () => resolve((w["dice-box-threejs"] as DiceCtor) ?? null);
    s.onerror = () => resolve(null);
    document.head.appendChild(s);
  });
  return _loadPromise;
}

export interface Dice3DConfig {
  gravity_multiplier?: number;
  light_intensity?: number;
  baseScale?: number;
  strength?: number;
  theme_customColorset?: Record<string, unknown>;
}

/**
 * Rzuć `notation` (np. "1d20") lądując na `forced` (wynik/-i z backendu) w kontenerze
 * o id `mountId`. Buduje ŚWIEŻY box na każdy rzut (recreate-per-roll — reużyty singleton
 * nie repaintuje się na mobile). Woła `onSettle()` po osiadnięciu; twardy backstop 9s.
 * Zwraca true jeśli 3D wystartowało, false gdy silnik/kontener niedostępny (→ fallback 2D).
 */
export async function rollDice3D(
  mountId: string,
  notation: string,
  forced: number[] | null,
  config: Dice3DConfig,
  onSettle: () => void,
): Promise<boolean> {
  const Ctor = await loadDiceEngine();
  const mount = document.getElementById(mountId);
  if (typeof Ctor !== "function" || !mount) return false;

  // Zbuduj świeży kontener wewnątrz mount (czyści poprzednią kanwę + kontekst WebGL).
  mount.innerHTML = "";
  const el = document.createElement("div");
  el.id = "dice3d-canvas";
  el.style.width = "100%";
  el.style.height = "100%";
  mount.appendChild(el);

  let box: DiceBox;
  try {
    box = new Ctor("#dice3d-canvas", {
      assetPath: ASSET_PATH,
      sounds: false,
      shadows: true,
      theme_colorset: "white",
      theme_texture: "",
      theme_material: "plastic",
      gravity_multiplier: config.gravity_multiplier ?? 400,
      light_intensity: config.light_intensity ?? 0.9,
      baseScale: config.baseScale ?? 100,
      strength: config.strength ?? 1.4,
      ...(config.theme_customColorset
        ? { theme_customColorset: config.theme_customColorset }
        : {}),
    });
  } catch {
    return false;
  }

  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    onSettle();
  };
  const backstop = window.setTimeout(finish, 9000);

  const predet =
    Array.isArray(forced) && forced.length
      ? `${notation}@${forced.join(",")}`
      : String(notation);

  try {
    // initialize() jest async (ładuje assety, buduje scenę); roll() wcześniej rzuca.
    await box.initialize();
    if (box.initialized !== true) throw new Error("dice3d not initialized");
    box.onRollComplete = () => {
      window.clearTimeout(backstop);
      window.setTimeout(finish, 550);
    };
    const p = box.roll(predet) as { catch?: (f: () => void) => void };
    if (p && typeof p.catch === "function") p.catch(() => {});
    return true;
  } catch {
    window.clearTimeout(backstop);
    return false;
  }
}
