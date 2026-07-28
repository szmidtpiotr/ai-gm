/**
 * terrain_palette.js — paleta RODZIN terenu dla mapy świata (#1542 M-2a, M-30).
 *
 * Idea: teren czyta się szybciej, gdy pokrewne typy dzielą wspólny ODCIEŃ
 * (rodzina), a różnią się tylko WARIANTEM (jaśniej/ciemniej) + małą ikoną.
 *   • rodzina  = wspólny hue (lasy zielone, woda niebieska, góry szare …)
 *   • wariant  = przesunięcie jasności `l` w [-1..+1] względem bazy rodziny
 *   • ikona    = glif rozróżniający typ w obrębie rodziny
 *
 * To warstwa PREZENTACJI: zwraca tylko kolor + ikonę na istniejący SVG.
 * Silnik mapy, dane hexów i baza (hex_type_config) bez zmian — renderer używa
 * tego zamiast surowego map_color/map_icon, z fallbackiem gdy typ nieznany.
 */

// ── Rodziny: wspólny odcień bazowy + domyślna ikona ──────────────────────────
export const TERRAIN_FAMILIES = {
  lasy:        { label: 'Lasy',          base: '#3e6b45', icon: '🌲' },
  bagna:       { label: 'Bagna',         base: '#5c6b3e', icon: '🥀' },
  gory:        { label: 'Góry',          base: '#7a746a', icon: '⛰' },
  stepy:       { label: 'Stepy',         base: '#9ca863', icon: '🌾' },
  woda:        { label: 'Woda',          base: '#2f5f88', icon: '🌊' },
  drogi_osady: { label: 'Drogi i osady', base: '#b0863a', icon: '🏘' },
  // #1551 MU-5 — rodziny terenów specyficznych dla krain (wcześniej „inne”).
  pustynia:    { label: 'Pustynia',      base: '#c2a86a', icon: '🏜' },
  pustkowia:   { label: 'Pustkowia',     base: '#6b5f52', icon: '☠' },
  obiekty:     { label: 'Obiekty',       base: '#8a6a8a', icon: '⚑' },
};

// ── Typ terenu → { rodzina, jasność, ikona } ─────────────────────────────────
// `l` > 0 rozjaśnia, `l` < 0 przyciemnia bazę rodziny. `icon` nadpisuje ikonę
// rodziny. `tint` (opcjonalnie) domiesza inny hue dla wariantów-wyjątków.
const TYPE_MAP = {
  // — lasy —
  forest:      { fam: 'lasy',  l:  0.00, icon: '🌲' },
  las_iglasty: { fam: 'lasy',  l:  0.08, icon: '🌲' },
  czarny_las:  { fam: 'lasy',  l: -0.28, icon: '🌲' },

  // — bagna —
  swamp:       { fam: 'bagna', l:  0.00, icon: '🥀' },
  trzesawisko: { fam: 'bagna', l: -0.12, icon: '🌫' },

  // — góry / skały —
  mountain:    { fam: 'gory',  l: -0.06, icon: '⛰' },
  grania:      { fam: 'gory',  l: -0.16, icon: '🏔' },
  hills:       { fam: 'gory',  l:  0.14, icon: '⛰' },
  przelecz:    { fam: 'gory',  l:  0.06, icon: '🗻' },
  tundra:      { fam: 'gory',  l:  0.22, icon: '🌫' },
  snow:        { fam: 'gory',  l:  0.42, icon: '❄' },
  lodowiec:    { fam: 'gory',  l:  0.48, icon: '🧊' },
  siarka:      { fam: 'gory',  l:  0.10, icon: '🟡', tint: '#c9a53a', tintMix: 0.5 },

  // — stepy / równiny —
  plains:      { fam: 'stepy', l:  0.00, icon: '🌾' },
  step:        { fam: 'stepy', l:  0.05, icon: '🌾' },
  heath:       { fam: 'stepy', l: -0.10, icon: '🌿' },

  // — woda —
  water:       { fam: 'woda',  l:  0.00, icon: '🌊' },
  morze:       { fam: 'woda',  l: -0.18, icon: '🌊' },   // #1551 MU-4/5: kanoniczne morze Kresów
  sea:         { fam: 'woda',  l: -0.10, icon: '🌊' },   // legacy (0 hexów po MU-4), zostawione dla zgodności
  lake:        { fam: 'woda',  l:  0.12, icon: '💧' },
  river:       { fam: 'woda',  l:  0.08, icon: '💧' },
  brod:        { fam: 'woda',  l:  0.22, icon: '🏞' },
  coast:       { fam: 'woda',  l:  0.20, icon: '🏖' },
  plycizna:    { fam: 'woda',  l:  0.26, icon: '🌊' },
  rafy:        { fam: 'woda',  l:  0.05, icon: '🪸' },

  // — drogi i osady —
  road:        { fam: 'drogi_osady', l:  0.04, icon: '🛤' },
  bridge:      { fam: 'drogi_osady', l:  0.10, icon: '🌉' },
  ruins:       { fam: 'drogi_osady', l: -0.14, icon: '🏚' },
  village:     { fam: 'drogi_osady', l:  0.06, icon: '🏠' },
  town:        { fam: 'drogi_osady', l:  0.14, icon: '🏘' },
  city:        { fam: 'drogi_osady', l:  0.22, icon: '🏰' },
  castle:      { fam: 'drogi_osady', l:  0.28, icon: '🏰' },

  // — stepy: pola uprawne —
  pola_uprawne:{ fam: 'stepy', l:  0.10, icon: '🌾' },

  // — pustynia (Wybrzeże/pustynne) —
  desert:      { fam: 'pustynia', l:  0.00, icon: '🏜' },
  wydmy:       { fam: 'pustynia', l:  0.12, icon: '🏜' },

  // — pustkowia (Martwe Pustkowia) —
  sol:           { fam: 'pustkowia', l:  0.38, icon: '🧂' },
  martwa_ziemia: { fam: 'pustkowia', l: -0.10, icon: '☠' },

  // — obiekty / POI (nie-biomy) —
  cave:        { fam: 'obiekty', l: -0.18, icon: '🕳' },
  dungeon:     { fam: 'obiekty', l: -0.30, icon: '⚔' },

  // — góry: wulkan —
  volcanic:    { fam: 'gory',  l: -0.28, icon: '🌋', tint: '#7a2a1a', tintMix: 0.45 },
};

// ── Helpery kolorów ──────────────────────────────────────────────────────────
function _hexToRgb(hex) {
  const h = hex.replace('#', '');
  return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16));
}
function _rgbToHex(rgb) {
  return '#' + rgb.map(v => Math.max(0, Math.min(255, Math.round(v)))
    .toString(16).padStart(2, '0')).join('');
}
// l>0: miesza ku bieli, l<0: ku czerni; |l| = siła (0..1).
function _shade(hex, l) {
  const rgb = _hexToRgb(hex);
  const target = l >= 0 ? 255 : 0;
  const k = Math.min(1, Math.abs(l));
  return _rgbToHex(rgb.map(v => v + (target - v) * k));
}
function _mix(hexA, hexB, k) {
  const a = _hexToRgb(hexA), b = _hexToRgb(hexB);
  return _rgbToHex(a.map((v, i) => v + (b[i] - v) * k));
}

/**
 * Styl wizualny typu terenu.
 * @param {string} hexType
 * @returns {{color:string, icon:string, family:string}|null} null gdy typ nieznany
 */
export function terrainStyle(hexType) {
  const t = TYPE_MAP[hexType];
  if (!t) return null;
  const fam = TERRAIN_FAMILIES[t.fam];
  let color = _shade(fam.base, t.l || 0);
  if (t.tint) color = _mix(color, t.tint, t.tintMix != null ? t.tintMix : 0.4);
  return { color, icon: t.icon || fam.icon, family: t.fam };
}

/** Kolor terenu z fallbackiem (dla renderera). */
export function terrainColor(hexType, fallback) {
  const s = terrainStyle(hexType);
  return s ? s.color : (fallback || '#4a6a4a');
}

/** Ikona terenu z fallbackiem. */
export function terrainIcon(hexType, fallback) {
  const s = terrainStyle(hexType);
  return s ? s.icon : (fallback || '');
}

/** Lista rodzin do legendy: [{key,label,base,icon,types:[...]}]. */
export function terrainFamilyLegend() {
  const byFam = {};
  for (const [type, t] of Object.entries(TYPE_MAP)) (byFam[t.fam] ||= []).push(type);
  return Object.entries(TERRAIN_FAMILIES).map(([key, f]) => ({
    key, ...f, types: byFam[key] || [],
  }));
}
