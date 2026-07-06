import { create } from "zustand";
import { clearSession, readStoredUser, storeSession } from "@/lib/auth";

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
  | "skills"
  | "spells"
  | "inventory"
  | "reputation"
  | "map"
  | "journal";

// FE12 Sklep (#1261) — otwierany narracyjnie (turn → open_shop). Overlay nad grą,
// nie zakładka. Trzymamy klucz NPC + opcjonalną kwestię powitalną (podnagłówek).
export interface ShopContext {
  npcKey: string;
  greeting?: string | null;
}

export interface AppState {
  currentUser: CurrentUser | null;
  currentHeroId: number | null;
  currentCampaignId: number | null;
  /** Aktywna zakładka ekranu gry (Opowieść + panele karty + mapa + dziennik). */
  gameTab: GameTab;
  /** FE12 (#1261) — otwarty sklep (overlay) albo null. */
  shop: ShopContext | null;
  /** FE14 (#1263 / F-44) — paleta komend otwarta (Ctrl+/ albo ikona w composerze). */
  paletteOpen: boolean;
  /** FE14 (#1263) — tekst do wstawienia w composer (komenda z palety, np. /roll). */
  composerPrefill: string | null;
  /** Placeholdery na przyszłe fale (walka / loch) — kształt wg sekcji 8. */
  activeCombat: unknown | null;
  dungeonRunState: unknown | null;

  setUser: (u: CurrentUser | null) => void;
  setHero: (id: number | null) => void;
  setCampaign: (id: number | null) => void;
  setGameTab: (t: GameTab) => void;
  openShop: (ctx: ShopContext) => void;
  closeShop: () => void;
  openPalette: () => void;
  closePalette: () => void;
  togglePalette: () => void;
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
  // Hydrate from localStorage so a refresh keeps the player logged in.
  currentUser: readStoredUser(),
  currentHeroId: null,
  currentCampaignId: null,
  gameTab: "story",
  shop: null,
  paletteOpen: false,
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
        : { currentCampaignId, gameTab: "story", shop: null },
    ),
  setGameTab: (gameTab) => set({ gameTab }),
  openShop: (shop) => set({ shop }),
  closeShop: () => set({ shop: null }),
  openPalette: () => set({ paletteOpen: true }),
  closePalette: () => set({ paletteOpen: false }),
  togglePalette: () => set((s) => ({ paletteOpen: !s.paletteOpen })),
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
      activeCombat: null,
      dungeonRunState: null,
    }),
}));
