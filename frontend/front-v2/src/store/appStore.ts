import { create } from "zustand";

// Client-state szkielet (Zustand) — kandydaci wg frontend_design.md sekcja 8.
// Server-state (tury, walka, ekwipunek) NIE tu — trzyma TanStack Query.

export interface CurrentUser {
  id: number;
  username: string;
  email?: string;
}

export interface AppState {
  currentUser: CurrentUser | null;
  currentHeroId: number | null;
  currentCampaignId: number | null;
  /** Placeholdery na przyszłe fale (walka / loch) — kształt wg sekcji 8. */
  activeCombat: unknown | null;
  dungeonRunState: unknown | null;

  setUser: (u: CurrentUser | null) => void;
  setHero: (id: number | null) => void;
  setCampaign: (id: number | null) => void;
  reset: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentUser: null,
  currentHeroId: null,
  currentCampaignId: null,
  activeCombat: null,
  dungeonRunState: null,

  setUser: (currentUser) => set({ currentUser }),
  setHero: (currentHeroId) => set({ currentHeroId }),
  setCampaign: (currentCampaignId) => set({ currentCampaignId }),
  reset: () =>
    set({
      currentUser: null,
      currentHeroId: null,
      currentCampaignId: null,
      activeCombat: null,
      dungeonRunState: null,
    }),
}));
