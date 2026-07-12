import { useEffect, useRef, useState } from "react";
import { ChatCircleDots, PaperPlaneRight, X, Minus } from "@phosphor-icons/react";
import { useMpStore } from "@/store/mpStore";
import type { ChatMessage } from "@/lib/multiplayer";
import { cn } from "@/lib/utils";

// FE15 (#1264) — party chat + whispery (F-71). Pływający panel nad composerem.
// Czyta mpStore (poller). `/whisper <postać> <tekst>` obsługuje warstwa send().
export function PartyChatPanel({ onSend }: { onSend: (raw: string) => void }) {
  const chat = useMpStore((s) => s.chat);
  const open = useMpStore((s) => s.chatOpen);
  const minimized = useMpStore((s) => s.chatMinimized);
  const unread = useMpStore((s) => s.unread);
  const toggle = useMpStore((s) => s.toggleChat);
  const toggleMin = useMpStore((s) => s.toggleMinimized);

  const [value, setValue] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [chat, open]);

  function send() {
    const t = value.trim();
    if (!t) return;
    onSend(t);
    setValue("");
  }

  const showPanel = open && !minimized;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-24 z-40 flex justify-end px-3 lg:bottom-6">
      {showPanel ? (
        <div className="pointer-events-auto flex h-[min(60vh,420px)] w-[min(92vw,340px)] flex-col overflow-hidden rounded-lg border border-line-ember bg-surface shadow-float">
          {/* Nagłówek */}
          <div className="flex items-center gap-2 border-b border-line bg-bg px-3 py-2">
            <ChatCircleDots weight="fill" className="text-ember" size={16} />
            <span className="flex-1 font-serif text-label font-semibold text-text">
              Czat drużyny
            </span>
            <button
              onClick={toggleMin}
              aria-label="Zwiń"
              className="text-text-3 hover:text-ember-glow"
            >
              <Minus size={16} />
            </button>
            <button
              onClick={toggle}
              aria-label="Zamknij"
              className="text-text-3 hover:text-ember-glow"
            >
              <X size={16} />
            </button>
          </div>

          {/* Wiadomości */}
          <div
            ref={listRef}
            className="flex-1 space-y-2 overflow-y-auto px-3 py-2.5 [scrollbar-width:thin]"
          >
            {chat.length === 0 ? (
              <div className="py-6 text-center font-ui text-micro text-text-3">
                Brak wiadomości. Napisz do drużyny — użyj
                <span className="font-mono text-text-2"> /whisper &lt;postać&gt; </span>
                dla szeptu.
              </div>
            ) : (
              chat.map((m) => <ChatBubble key={m.id} m={m} />)
            )}
          </div>

          {/* Pole */}
          <div className="flex items-end gap-1.5 border-t border-line bg-bg px-2.5 py-2">
            <textarea
              rows={1}
              value={value}
              onChange={(e) => setValue(e.target.value.slice(0, 500))}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder="Wiadomość / /whisper…"
              className="max-h-24 min-h-[34px] flex-1 resize-none rounded-md border border-line bg-surface px-2.5 py-2 font-ui text-label text-text outline-none placeholder:text-text-3 focus:border-line-ember"
            />
            <button
              onClick={send}
              disabled={!value.trim()}
              aria-label="Wyślij"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-[#d1602c] to-ember text-white disabled:opacity-40"
            >
              <PaperPlaneRight weight="fill" size={15} />
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => {
            if (minimized) toggleMin();
            else toggle();
          }}
          aria-label="Czat drużyny"
          className="pointer-events-auto relative flex h-12 w-12 items-center justify-center rounded-full border border-line-ember bg-surface text-ember-glow shadow-float"
        >
          <ChatCircleDots weight="fill" size={22} />
          {unread > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-ember px-1 font-mono text-[10px] font-bold text-white">
              {unread}
            </span>
          )}
        </button>
      )}
    </div>
  );
}

function ChatBubble({ m }: { m: ChatMessage }) {
  const whisper = !!m.whisper_to;
  const label = whisper
    ? m.is_mine
      ? `🤫 → ${m.whisper_to}`
      : `🤫 ${m.character_name} → Ty`
    : m.character_name;

  return (
    <div className={cn("flex flex-col", m.is_mine ? "items-end" : "items-start")}>
      <div className="mb-0.5 font-ui text-[10px] font-semibold uppercase tracking-wide text-text-3">
        {label}
      </div>
      <div
        className={cn(
          "max-w-[85%] rounded-md px-2.5 py-1.5 font-ui text-label",
          whisper
            ? "border border-line-mech bg-[rgba(232,193,90,.06)] italic text-text-2"
            : m.is_mine
              ? "bg-player-card text-text"
              : "border border-line bg-bg text-text",
        )}
      >
        {m.message}
      </div>
    </div>
  );
}
