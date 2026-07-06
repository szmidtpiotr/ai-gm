import { useCallback, useEffect, useRef } from "react";
import { getPartyChat, parseWhisper, postPartyChat } from "@/lib/multiplayer";
import { chatCursor, getMpState } from "@/store/mpStore";

const POLL_MS = 5000;

// FE15 (#1264) — party chat + whispery. Poll co 5 s (pierwszy po 1 s), wynik → mpStore.
// send() parsuje `/whisper <postać> <tekst>`; whispery backend filtruje po odbiorcy.
export function useMpChat({
  campaignId,
  characterName,
  enabled,
}: {
  campaignId: number;
  characterName: string;
  enabled: boolean;
}) {
  const alive = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const poll = useCallback(async () => {
    if (!alive.current) return;
    try {
      const data = await getPartyChat(campaignId, chatCursor.last);
      if (!alive.current) return;
      const msgs = data.messages || [];
      if (msgs.length) {
        chatCursor.last = Math.max(chatCursor.last, ...msgs.map((m) => m.id));
        getMpState().ingestChat(msgs);
      }
    } catch {
      /* poll czatu nie jest krytyczny */
    }
    if (alive.current) timer.current = setTimeout(poll, POLL_MS);
  }, [campaignId]);

  const send = useCallback(
    async (raw: string) => {
      const { whisperTo, message } = parseWhisper(raw);
      if (!message) return;
      try {
        await postPartyChat(campaignId, {
          message,
          character_name: characterName || "Gracz",
          whisper_to: whisperTo,
        });
        // Natychmiastowy poll, by własna wiadomość pojawiła się bez czekania 5 s.
        poll();
      } catch {
        /* zignoruj błąd wysyłki czatu */
      }
    },
    [campaignId, characterName, poll],
  );

  useEffect(() => {
    if (!enabled) return;
    alive.current = true;
    chatCursor.reset();
    timer.current = setTimeout(poll, 1000);
    return () => {
      alive.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [enabled, poll]);

  return { send };
}
