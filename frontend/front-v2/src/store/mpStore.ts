import { create } from "zustand";
import type { ChatMessage, RoundNarration, RoundStatus } from "@/lib/multiplayer";

// FE15 (#1264) — „cienka warstwa realtime → Zustand". Backend nie ma WS/SSE dla MP,
// więc pojedynczy poller (useMpRound / useMpChat) pisze tu stan, a komponenty tylko
// czytają. Gdy backend dostanie kanał WS/SSE, wystarczy podmienić źródło zapisu.
// Server-state solo (tury/walka) zostaje w TanStack Query — to jest wyłącznie MP.

// Log rundy: dymki akcji graczy + narracja GM, w kolejności rund.
export type MpBlock =
  | { kind: "divider"; id: string; round: number }
  | { kind: "action"; id: string; name: string; text: string; mine: boolean }
  | { kind: "gm"; id: string; text: string };

interface MpState {
  // Rundy
  blocks: MpBlock[];
  status: RoundStatus | null;
  composerEnabled: boolean;
  placeholder: string;
  hostNote: string | null;
  // Party chat
  chat: ChatMessage[];
  chatOpen: boolean;
  chatMinimized: boolean;
  unread: number;
  sessionPlayers: string[];

  // Rundy — mutatory (wołane przez poller)
  resetRounds: () => void;
  appendDivider: (round: number) => void;
  appendAction: (name: string, text: string, mine: boolean) => void;
  appendNarration: (r: RoundNarration, selfName: string, skipOwn: boolean) => void;
  setStatus: (s: RoundStatus | null) => void;
  setComposer: (enabled: boolean, placeholder?: string) => void;
  setHostNote: (note: string | null) => void;

  // Party chat — mutatory
  ingestChat: (msgs: ChatMessage[]) => void;
  toggleChat: () => void;
  toggleMinimized: () => void;
  reset: () => void;
}

let _seq = 0;
const nextId = () => `mp-${++_seq}`;

export const useMpStore = create<MpState>((set) => ({
  blocks: [],
  status: null,
  composerEnabled: true,
  placeholder: "Twoja akcja w tej rundzie…",
  hostNote: null,
  chat: [],
  chatOpen: false,
  chatMinimized: false,
  unread: 0,
  sessionPlayers: [],

  resetRounds: () => set({ blocks: [] }),

  appendDivider: (round) =>
    set((s) => ({ blocks: [...s.blocks, { kind: "divider", id: nextId(), round }] })),

  appendAction: (name, text, mine) =>
    set((s) => {
      const players =
        !mine && name && !s.sessionPlayers.includes(name)
          ? [...s.sessionPlayers, name]
          : s.sessionPlayers;
      return {
        blocks: [...s.blocks, { kind: "action", id: nextId(), name, text, mine }],
        sessionPlayers: players,
      };
    }),

  appendNarration: (r, selfName, skipOwn) =>
    set((s) => {
      const added: MpBlock[] = [];
      const players = new Set(s.sessionPlayers);
      for (const a of r.actions || []) {
        const mine = a.character_name === selfName;
        if (skipOwn && mine) continue;
        if (!mine && a.character_name) players.add(a.character_name);
        added.push({
          kind: "action",
          id: nextId(),
          name: a.character_name,
          text: a.action_text,
          mine,
        });
      }
      if (r.narrative) added.push({ kind: "gm", id: nextId(), text: r.narrative });
      return {
        blocks: [...s.blocks, ...added],
        sessionPlayers: [...players],
        hostNote: r.my_note ?? s.hostNote,
      };
    }),

  setStatus: (status) => set({ status }),

  setComposer: (composerEnabled, placeholder) =>
    set(placeholder ? { composerEnabled, placeholder } : { composerEnabled }),

  setHostNote: (hostNote) => set({ hostNote }),

  ingestChat: (msgs) =>
    set((s) => {
      if (!msgs.length) return {};
      const players = new Set(s.sessionPlayers);
      let unread = s.unread;
      for (const m of msgs) {
        if (!m.is_mine && m.character_name) players.add(m.character_name);
        if (!m.is_mine && !(s.chatOpen && !s.chatMinimized)) unread++;
      }
      return {
        chat: [...s.chat, ...msgs],
        sessionPlayers: [...players],
        unread,
      };
    }),

  toggleChat: () =>
    set((s) => {
      if (s.chatMinimized) return { chatMinimized: false, unread: 0 };
      const open = !s.chatOpen;
      return { chatOpen: open, unread: open ? 0 : s.unread };
    }),

  toggleMinimized: () =>
    set((s) => ({
      chatMinimized: !s.chatMinimized,
      unread: s.chatMinimized ? 0 : s.unread,
    })),

  reset: () =>
    set({
      blocks: [],
      status: null,
      composerEnabled: true,
      placeholder: "Twoja akcja w tej rundzie…",
      hostNote: null,
      chat: [],
      chatOpen: false,
      chatMinimized: false,
      unread: 0,
      sessionPlayers: [],
    }),
}));

// Ostatnie ID czatu (dla since_id) — poza store, bo to detal pollera.
export const chatCursor = { last: 0, reset: () => (chatCursor.last = 0) };

// Pomocnik: odczyt świeżego stanu bez subskrypcji (poller).
export const getMpState = () => useMpStore.getState();
