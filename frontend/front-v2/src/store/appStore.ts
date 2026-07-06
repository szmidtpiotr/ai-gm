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
  | "map";

export interface AppState {
  currentUser: CurrentUser | null;
  currentHeroId: number | null;
  currentCampaignId: number | null;
  /** Aktywna zakładka ekranu gry (Opowieść + 5 paneli karty postaci). */
  gameTab: GameTab;
  /** Placeholdery na przyszłe fale (walka / loch) — kształt wg sekcji 8. */
  activeCombat: unknown | null;
  dungeonRunState: unknown | null;

  setUser: (u: CurrentUser | null) => void;
  setHero: (id: number | null) => void;
  setCampaign: (id: number | null) => void;
  setGameTab: (t: GameTab) => void;
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
  activeCombat: null,
  dungeonRunState: null,

  setUser: (currentUser) => set({ currentUser }),
  setHero: (currentHeroId) => set({ currentHeroId }),
  // Zmiana kampanii → wróć do Opowieści (nie przenoś panelu między grami).
  setCampaign: (currentCampaignId) =>
    set((s) =>
      s.currentCampaignId === currentCampaignId
        ? { currentCampaignId }
        : { currentCampaignId, gameTab: "story" },
    ),
  setGameTab: (gameTab) => set({ gameTab }),
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
      activeCombat: null,
      dungeonRunState: null,
    });
  },
  reset: () =>
    set({
      currentUser: null,
      currentHeroId: null,
      currentCampaignId: null,
      activeCombat: null,
      dungeonRunState: null,
    }),
}));
