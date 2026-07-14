import { create } from "zustand";
import { clearSession, readStoredUser, storeSession } from "@/lib/auth";

export type GamePrefKey =
  | "gamePrefBubbleName"
  | "gamePrefBubbleTurn"
  | "gamePrefBubbleDatetime"
  | "gamePrefSkipCombatNarr"
  | "gamePrefShowPlayerDice"
  | "gamePrefShowEnemyDice"
  | "gamePrefDebug";

const PREF_LS: Record<GamePrefKey, [string, boolean]> = {
  gamePrefBubbleName:     ["bubble_name",               true],
  gamePrefBubbleTurn:     ["bubble_turn",               true],
  gamePrefBubbleDatetime: ["bubble_datetime",           true],
  gamePrefSkipCombatNarr: ["aigm_skip_combat_narrative", false],
  gamePrefShowPlayerDice: ["aigm_show_player_dice",     true],
  gamePrefShowEnemyDice:  ["aigm_show_enemy_dice",      true],
  gamePrefDebug:          ["aigm_debug",                false],
};

function readPref(lsKey: string, def: boolean): boolean {
  try {
    const v = localStorage.getItem(lsKey);
    if (v === null) return def;
    return v !== "false" && v !== "0";
  } catch { return def; }
}

// Client-state szkielet (Zustand) — kandydaci wg frontend_design.md sekcja 8.
// Server-state (tury, walka, ekwipunek) NIE tu — trzyma TanStack Query.

export interface CurrentUser {
  id: number;
  username: string;
  email?: string;
  displayName?: string;
  isAdmin?: boolean;
  isTester?: boolean;
  role?: string;
}

/** Login payload as returned by POST /auth/login. */
export interface LoginPayload {
  user_id: number;
  username: string;
  display_name?: string | null;
  email?: string | null;
  is_admin?: number;
  is_tester?: number;
  role?: string;
  access_token: string;
  refresh_token?: string;
}

// KROK 5 (#1234) — panele karty postaci to zakładki w obrębie gry, nie osobny
// ekran. Który panel jest aktywny trzyma client-state (rail desktop / scroll mobile).
export type GameTab =
  | "story"
  | "character"
  | "spells"
  | "inventory"
  | "recipes"
  | "reputation"
  | "collections"
  | "map"
  | "journal";

// FE12 Sklep (#1261) — otwierany narracyjnie (turn → open_shop). Overlay nad grą,
// nie zakładka. Trzymamy klucz NPC + opcjonalną kwestię powitalną (podnagłówek).
export interface ShopContext {
  npcKey: string;
  greeting?: string | null;
}

export interface AppState {
  // Game preferences (localStorage-backed)
  gamePrefBubbleName: boolean;
  gamePrefBubbleTurn: boolean;
  gamePrefBubbleDatetime: boolean;
  gamePrefSkipCombatNarr: boolean;
  gamePrefShowPlayerDice: boolean;
  gamePrefShowEnemyDice: boolean;
  gamePrefDebug: boolean;
  setGamePref: (k: GamePrefKey, v: boolean) => void;

  currentUser: CurrentUser | null;
  currentHeroId: number | null;
  currentCampaignId: number | null;
  /** Aktywna zakładka ekranu gry (Opowieść + panele karty + mapa + dziennik). */
  gameTab: GameTab;
  /** #1309 — użycie przedmiotu-mapy: heksy do „wjechania" animacją na mapie świata.
   *  `ts` pozwala retriggerować animację przy powtórnym odsłonięciu tych samych heksów. */
  mapReveal: { hexes: [number, number][]; ts: number } | null;
  /** #1381 — trwa animacja przeskoku pina po trasie na mapie świata. Gdy true,
   *  Game.tsx wstrzymuje modal zasadzki (travel_notice), żeby nie wyskoczył PRZED
   *  końcem animacji. Ustawiany/gaszony przez WorldMap. */
  travelAnimating: boolean;
  /** #1196 — wymuszenie mapy ŚWIATA (nie lokalnej osady) po kliknięciu „Użyj" na
   *  mapie skarbu. Czytane wprost w renderze — niezależne od efektu forceWorldMap. */
  mapView: "auto" | "world";
  /** FE12 (#1261) — otwarty sklep (overlay) albo null. */
  shop: ShopContext | null;
  /** #1292 — otwarty modal Usług (klucz lokacji) albo null. Mechaniczny, omija LLM. */
  services: string | null;
  /** #1338 BL-C3 — otwarty modal Rzemiosła (klucz lokacji) albo null. Deterministyczny. */
  crafting: string | null;
  /** #1292 — po zamknięciu modala Usług: ukryta tura proszona o narrację odbioru
   *  (zakup już opłacony mechanicznie). Game.tsx konsumuje i czyści. */
  servicesReceiptPending: string | null;
  /** Po zamknięciu modalu zwycięstwa: ukryta tura prosząca narratora o epilog walki
   *  (mechanika już rozliczona przez /combat). Game.tsx konsumuje i czyści. */
  combatEpiloguePending: string | null;
  /** FE14 (#1263 / F-44) — paleta komend otwarta (Ctrl+/ albo ikona w composerze). */
  paletteOpen: boolean;
  /** FE19 (#1268 / F-77) — menu ☰ ekranu gry otwarte. */
  gameMenuOpen: boolean;
  /** F-27 V2 — ekran awansu (wydawanie PD) otwarty. Awans ręczny, nie auto-modal. */
  advancementOpen: boolean;
  /** #1291 WAIT-4 — modal wyboru pory czekania otwarty. */
  waitOpen: boolean;
  /** FE19 (#1268 / F-77) — etap bramki finału: modal potwierdzenia / ekran zwycięstwa. */
  finishFlow: "idle" | "confirm" | "victory";
  /** FE14 (#1263) — tekst do wstawienia w composer (komenda z palety, np. /roll). */
  composerPrefill: string | null;
  /** Placeholdery na przyszłe fale (walka / loch) — kształt wg sekcji 8. */
  activeCombat: unknown | null;
  dungeonRunState: unknown | null;

  setUser: (u: CurrentUser | null) => void;
  setHero: (id: number | null) => void;
  setCampaign: (id: number | null) => void;
  setGameTab: (t: GameTab) => void;
  /** #1309 — ustaw heksy do animacji odsłonięcia (stempluje świeży ts). */
  setMapReveal: (hexes: [number, number][]) => void;
  setTravelAnimating: (v: boolean) => void;
  /** #1196 — wyczyść po skonsumowaniu (inaczej każde otwarcie mapy re-centruje). */
  clearMapReveal: () => void;
  /** #1196 — wymuś/zwolnij mapę świata. */
  setMapView: (v: "auto" | "world") => void;
  openShop: (ctx: ShopContext) => void;
  closeShop: () => void;
  openServices: (locationKey: string) => void;
  closeServices: () => void;
  openCrafting: (locationKey: string) => void;
  closeCrafting: () => void;
  setServicesReceiptPending: (text: string | null) => void;
  setCombatEpiloguePending: (text: string | null) => void;
  openPalette: () => void;
  closePalette: () => void;
  togglePalette: () => void;
  openGameMenu: () => void;
  closeGameMenu: () => void;
  toggleGameMenu: () => void;
  openAdvancement: () => void;
  closeAdvancement: () => void;
  openWait: () => void;
  closeWait: () => void;
  setFinishFlow: (f: "idle" | "confirm" | "victory") => void;
  /** Wstaw tekst do composera (paleta → komenda); Composer konsumuje i czyści. */
  setComposerPrefill: (text: string | null) => void;
  /** Persist tokens + user after a successful auth call. */
  login: (payload: LoginPayload) => CurrentUser;
  /** Clear tokens + user (wyloguj). */
  logout: () => void;
  reset: () => void;
}

function toUser(p: LoginPayload): CurrentUser {
  return {
    id: p.user_id,
    username: p.username,
    email: p.email ?? undefined,
    displayName: p.display_name ?? undefined,
    isAdmin: !!p.is_admin,
    isTester: !!p.is_tester,
    role: p.role,
  };
}

export const useAppStore = create<AppState>((set) => ({
  // Game prefs — hydrated from localStorage on startup.
  gamePrefBubbleName:     readPref("bubble_name",               true),
  gamePrefBubbleTurn:     readPref("bubble_turn",               true),
  gamePrefBubbleDatetime: readPref("bubble_datetime",           true),
  gamePrefSkipCombatNarr: readPref("aigm_skip_combat_narrative", false),
  gamePrefShowPlayerDice: readPref("aigm_show_player_dice",     true),
  gamePrefShowEnemyDice:  readPref("aigm_show_enemy_dice",      true),
  gamePrefDebug:          readPref("aigm_debug",                false),
  setGamePref: (k, v) => {
    const [lsKey] = PREF_LS[k];
    try { localStorage.setItem(lsKey, v ? "1" : "0"); } catch {}
    set({ [k]: v } as Partial<AppState>);
  },

  // Hydrate from localStorage so a refresh keeps the player logged in.
  currentUser: readStoredUser(),
  currentHeroId: null,
  currentCampaignId: null,
  gameTab: "story",
  mapReveal: null,
  travelAnimating: false,
  mapView: "auto",
  shop: null,
  services: null,
  crafting: null,
  servicesReceiptPending: null,
  combatEpiloguePending: null,
  paletteOpen: false,
  gameMenuOpen: false,
  advancementOpen: false,
  waitOpen: false,
  finishFlow: "idle",
  composerPrefill: null,
  activeCombat: null,
  dungeonRunState: null,

  setUser: (currentUser) => set({ currentUser }),
  setHero: (currentHeroId) => set({ currentHeroId }),
  // Zmiana kampanii → wróć do Opowieści (nie przenoś panelu między grami) + zamknij sklep.
  setCampaign: (currentCampaignId) =>
    set((s) =>
      s.currentCampaignId === currentCampaignId
        ? { currentCampaignId }
        : { currentCampaignId, gameTab: "story", mapReveal: null, mapView: "auto", shop: null, services: null, crafting: null, gameMenuOpen: false, finishFlow: "idle" },
    ),
  setGameTab: (gameTab) => set({ gameTab }),
  setMapReveal: (hexes) => set({ mapReveal: { hexes, ts: Date.now() } }),
  setTravelAnimating: (v) => set({ travelAnimating: v }),
  clearMapReveal: () => set({ mapReveal: null }),
  setMapView: (mapView) => set({ mapView }),
  openShop: (shop) => set({ shop }),
  closeShop: () => set({ shop: null }),
  openServices: (locationKey) => set({ services: locationKey }),
  closeServices: () => set({ services: null }),
  openCrafting: (locationKey) => set({ crafting: locationKey }),
  closeCrafting: () => set({ crafting: null }),
  setServicesReceiptPending: (servicesReceiptPending) => set({ servicesReceiptPending }),
  setCombatEpiloguePending: (combatEpiloguePending) => set({ combatEpiloguePending }),
  openPalette: () => set({ paletteOpen: true }),
  closePalette: () => set({ paletteOpen: false }),
  togglePalette: () => set((s) => ({ paletteOpen: !s.paletteOpen })),
  openGameMenu: () => set({ gameMenuOpen: true }),
  closeGameMenu: () => set({ gameMenuOpen: false }),
  toggleGameMenu: () => set((s) => ({ gameMenuOpen: !s.gameMenuOpen })),
  openAdvancement: () => set({ advancementOpen: true, gameMenuOpen: false }),
  closeAdvancement: () => set({ advancementOpen: false }),
  openWait: () => set({ waitOpen: true, paletteOpen: false }),
  closeWait: () => set({ waitOpen: false }),
  setFinishFlow: (finishFlow) => set({ finishFlow }),
  setComposerPrefill: (composerPrefill) => set({ composerPrefill }),
  login: (payload) => {
    const user = toUser(payload);
    storeSession(payload.access_token, payload.refresh_token, user);
    set({ currentUser: user });
    return user;
  },
  logout: () => {
    clearSession();
    set({
      currentUser: null,
      currentHeroId: null,
      currentCampaignId: null,
      gameTab: "story",
      shop: null,
      services: null,
      crafting: null,
      servicesReceiptPending: null,
      combatEpiloguePending: null,
      activeCombat: null,
      dungeonRunState: null,
    });
  },
  reset: () =>
    set({
      currentUser: null,
      currentHeroId: null,
      currentCampaignId: null,
      shop: null,
      services: null,
      crafting: null,
      servicesReceiptPending: null,
      combatEpiloguePending: null,
      activeCombat: null,
      dungeonRunState: null,
    }),
}));
