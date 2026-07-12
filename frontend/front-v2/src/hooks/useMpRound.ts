import { useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getRoundNarration,
  getRoundStatus,
  getRoundsHistory,
  submitRoundAction,
  type RoundStatus,
} from "@/lib/multiplayer";
import { getMpState, useMpStore } from "@/store/mpStore";

const POLL_MS = 2000;

interface Args {
  campaignId: number;
  characterId: number | null;
  characterName: string;
  enabled: boolean;
}

// FE15 (#1264) — pętla rund MP. Port zachowań z multiplayer_ui.js (_poll /
// _fetchNarration / handleSubmit), ale zamiast DOM pisze do mpStore. Jeden poller,
// komponenty tylko czytają. Zwraca submit() dla composera.
export function useMpRound({ campaignId, characterId, characterName, enabled }: Args) {
  const qc = useQueryClient();
  const alive = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastShownRound = useRef<number | null>(null);
  const currentRoundNum = useRef<number | null>(null);

  const stop = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const schedule = useCallback(
    (fn: () => void, ms = POLL_MS) => {
      stop();
      timer.current = setTimeout(() => {
        if (alive.current) fn();
      }, ms);
    },
    [stop],
  );

  const fetchNarration = useCallback(async () => {
    if (!alive.current) return;
    try {
      const n = await getRoundNarration(campaignId);
      if (!alive.current) return;
      if (n.round_id === lastShownRound.current) {
        schedule(poll);
        return;
      }
      lastShownRound.current = n.round_id;
      getMpState().appendNarration(n, characterName, true);
      getMpState().setComposer(false, "Przygotuj kolejną akcję…");
      qc.invalidateQueries({ queryKey: ["character"] });
      qc.invalidateQueries({ queryKey: ["clock", campaignId] });
      // Po 2 s odblokuj composer (czas na przeczytanie narracji) i wznów poll.
      schedule(() => {
        getMpState().setComposer(true, "Twoja akcja w tej rundzie…");
        poll();
      });
    } catch {
      if (alive.current) schedule(fetchNarration);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId, characterName, qc, schedule]);

  const applyStatus = useCallback(
    (s: RoundStatus) => {
      const st = getMpState();
      st.setStatus(s);
      if (s.host_note) st.setHostNote(s.host_note);
      if (currentRoundNum.current !== null && s.round_number !== currentRoundNum.current) {
        st.appendDivider(s.round_number);
      }
      currentRoundNum.current = s.round_number;
    },
    [],
  );

  const poll = useCallback(async () => {
    if (!alive.current) return;
    stop();
    try {
      const s = await getRoundStatus(campaignId);
      if (!alive.current) return;
      applyStatus(s);

      if (s.status === "none" || (s.status === "collecting" && !s.my_submitted)) {
        getMpState().setComposer(true, "Twoja akcja w tej rundzie…");
        schedule(poll);
        return;
      }
      if (s.status === "collecting" && s.my_submitted) {
        getMpState().setComposer(true, "Możesz zmienić swoją akcję…");
        schedule(poll);
        return;
      }
      if (s.status === "narrating") {
        getMpState().setComposer(false, "GM tworzy narrację…");
        schedule(fetchNarration);
        return;
      }
      if (s.status === "done") {
        if (s.round_id === lastShownRound.current) {
          getMpState().setComposer(true, "Twoja akcja w tej rundzie…");
          schedule(poll);
        } else {
          getMpState().setComposer(false, "GM tworzy narrację…");
          await fetchNarration();
        }
        return;
      }
    } catch {
      if (alive.current) schedule(poll);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId, applyStatus, fetchNarration, schedule, stop]);

  const submit = useCallback(
    async (text: string) => {
      const t = text.trim();
      if (!t || !alive.current) return;
      if (!getMpState().composerEnabled) return; // #1173 — nie resubmit w trakcie narracji
      stop();
      getMpState().appendAction(characterName, t, true);
      getMpState().setComposer(false, "Wysyłanie…");
      try {
        const r = await submitRoundAction(campaignId, {
          action_text: t,
          character_id: characterId,
          character_name: characterName,
        });
        if (r.status === "narrating" || r.status === "done") {
          getMpState().setComposer(false, "GM tworzy narrację…");
          schedule(fetchNarration);
        } else {
          getMpState().setComposer(true, "Możesz zmienić swoją akcję…");
          schedule(poll);
        }
      } catch {
        getMpState().setComposer(true, "Twoja akcja w tej rundzie…");
      }
    },
    [campaignId, characterId, characterName, fetchNarration, poll, schedule, stop],
  );

  useEffect(() => {
    if (!enabled) return;
    alive.current = true;
    lastShownRound.current = null;
    currentRoundNum.current = null;
    useMpStore.getState().resetRounds();

    (async () => {
      // Historia rund → log, potem status (moja akcja w toku) → poll.
      try {
        const hist = await getRoundsHistory(campaignId);
        if (!alive.current) return;
        for (const r of hist.rounds || []) {
          getMpState().appendNarration(r, characterName, false);
          lastShownRound.current = r.round_id;
        }
      } catch {
        /* brak historii — ignoruj */
      }
      try {
        const s = await getRoundStatus(campaignId);
        if (!alive.current) return;
        applyStatus(s);
        if (s.my_submitted && s.my_action && s.status === "collecting") {
          getMpState().appendAction(characterName, s.my_action, true);
        }
      } catch {
        /* brak statusu — poll i tak spróbuje */
      }
      poll();
    })();

    return () => {
      alive.current = false;
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId, characterName, enabled]);

  return { submit };
}
