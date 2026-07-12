import { useEffect, useRef, useState } from "react";
import {
  Microphone,
  PaperPlaneRight,
  Command,
  Sword,
  Shield,
  Sparkle,
  SpeakerHigh,
  Stop,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { Chip } from "@/lib/game";
import { useAppStore } from "@/store/appStore";
import { voice } from "@/lib/voice";
import { useVoice } from "@/hooks/useVoice";

const MAX = 500;

// F-50 composer (sekcja 6): mic (STT placeholder) · pole + licznik · paleta · wyślij.
// Quick-action chips nad polem (suggested_actions z ostatniej tury).
export function Composer({
  onSend,
  disabled,
  chips,
  onChip,
  placeholder = "Co robisz?",
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
  chips: Chip[];
  onChip: (chip: Chip) => void;
  /** FE15 (#1264): MP nadpisuje podpowiedź stanem rundy (np. „GM tworzy narrację…"). */
  placeholder?: string;
}) {
  const [value, setValue] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);
  const openPalette = useAppStore((s) => s.openPalette);
  const prefill = useAppStore((s) => s.composerPrefill);
  const setComposerPrefill = useAppStore((s) => s.setComposerPrefill);

  // F-72 (#1267) głos: mic dyktuje (STT), overlay „Czytam…" (TTS). onSend przez ref,
  // by callback transkrypcji zawsze widział świeżą funkcję bez re-subskrypcji.
  const vs = useVoice();
  const onSendRef = useRef(onSend);
  onSendRef.current = onSend;
  useEffect(() => {
    voice.onTranscript = (text, autosend) => {
      setValue(text);
      requestAnimationFrame(() => {
        taRef.current?.focus();
        autoGrow();
      });
      if (autosend && text.trim()) {
        onSendRef.current(text.trim());
        setValue("");
      }
    };
    return () => {
      voice.onTranscript = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // FE14 (#1263): komenda z palety → wstaw tekst, ustaw fokus, wyczyść bufor.
  useEffect(() => {
    if (prefill == null) return;
    setValue(prefill);
    setComposerPrefill(null);
    requestAnimationFrame(() => {
      const el = taRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
      autoGrow();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  function autoGrow() {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 128) + "px";
  }

  function submit() {
    const t = value.trim();
    if (!t || disabled) return;
    onSend(t);
    setValue("");
    requestAnimationFrame(autoGrow);
  }

  return (
    <div className="shrink-0 border-t border-line bg-surface px-3.5 pb-2 pt-2.5">
      {/* F-72: overlay „Czytam…" (TTS aktywny) — z przyciskiem zatrzymania. */}
      {vs.playing && (
        <div className="mx-auto mb-2 flex max-w-[660px] items-center gap-2 rounded-md border border-line-ember bg-ember/[0.08] px-3 py-1.5">
          <SpeakerHigh className="animate-pulse text-ember-glow" size={15} />
          <span className="flex-1 font-ui text-micro text-ember-glow">Czytam narrację…</span>
          <button
            type="button"
            onClick={() => vs.stopPlayback()}
            aria-label="Zatrzymaj czytanie"
            className="flex h-6 w-6 items-center justify-center rounded-sm text-ember-glow hover:text-text"
          >
            <Stop weight="fill" size={13} />
          </button>
        </div>
      )}

      {/* quick-action chips — jeden poziomy rząd z przewijaniem (bez zawijania) */}
      {chips.length > 0 && (
        <div className="mx-auto mb-2 flex max-w-[660px] gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {chips.map((c, i) => {
            const off = disabled || c.enabled === false;
            return (
              <button
                key={i}
                type="button"
                disabled={off}
                title={c.enabled === false ? c.reason || undefined : undefined}
                onClick={() => onChip(c)}
                className="flex shrink-0 items-center gap-1.5 rounded-pill border border-line bg-surface px-3.5 py-2 font-ui text-label text-text transition-colors hover:border-line-ember hover:text-ember-glow disabled:opacity-50 disabled:hover:border-line disabled:hover:text-text"
              >
                {c.icon ? <span aria-hidden>{c.icon}</span> : <ChipIcon label={c.label} />}
                {c.label}
              </button>
            );
          })}
        </div>
      )}

      <div className="mx-auto flex max-w-[660px] items-end gap-2">
        {/* mic — dyktowanie STT (F-72 #1267). Pulsuje na czerwono w trakcie nagrania. */}
        <button
          type="button"
          aria-label={vs.recording ? "Zatrzymaj dyktowanie" : "Dyktuj głosem"}
          title={
            vs.sttLocked
              ? "Głos wyłączony przez administratora"
              : !vs.available
                ? "Głos chwilowo niedostępny"
                : vs.recording
                  ? "Nagrywam — kliknij, aby zatrzymać"
                  : "Dyktuj głosem"
          }
          disabled={vs.sttLocked || !vs.available}
          onClick={() => vs.toggleStt()}
          data-testid="composer-mic"
          className={cn(
            "flex h-11 w-11 shrink-0 items-center justify-center rounded-md border transition-colors disabled:opacity-40",
            vs.recording
              ? "animate-pulse border-line-danger bg-danger/[0.12] text-danger"
              : "border-line bg-bg text-text-2 hover:border-line-ember hover:text-ember-glow",
          )}
        >
          <Microphone weight={vs.recording ? "fill" : "regular"} size={19} />
        </button>

        <div className="flex flex-1 items-end gap-1.5 rounded-lg border border-line bg-bg pl-3.5 pr-1.5 py-1.5 focus-within:border-line-ember focus-within:shadow-[0_0_0_3px_rgba(255,122,61,.1)]">
          <textarea
            ref={taRef}
            rows={1}
            value={value}
            disabled={disabled}
            onChange={(e) => {
              setValue(e.target.value.slice(0, MAX));
              autoGrow();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={placeholder}
            className="max-h-32 min-h-[28px] flex-1 resize-none self-center bg-transparent py-1.5 font-ui text-body text-text outline-none placeholder:italic placeholder:text-text-3"
          />
          {/* paleta komend (F-44) — Ctrl+/ albo ta ikona */}
          <button
            type="button"
            aria-label="Paleta komend"
            title="Paleta komend (Ctrl+/)"
            onClick={openPalette}
            className="mb-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-sm text-text-3 transition-colors hover:text-ember-glow"
          >
            <Command size={16} />
          </button>
          <span className="mb-2 shrink-0 self-end font-mono text-[10px] text-text-3">
            {value.length}/{MAX}
          </span>
        </div>

        <button
          type="button"
          aria-label="Wyślij"
          disabled={disabled || !value.trim()}
          onClick={submit}
          className={cn(
            "flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-white",
            "bg-gradient-to-br from-[#d1602c] to-ember shadow-[0_0_16px_rgba(255,122,61,.4)]",
            "disabled:opacity-40 disabled:shadow-none",
          )}
        >
          <PaperPlaneRight weight="fill" size={18} />
        </button>
      </div>
    </div>
  );
}

// Heurystyka ikony chipa po treści etykiety (Phosphor, jeden zestaw).
function ChipIcon({ label }: { label: string }) {
  const l = label.toLowerCase();
  if (/atak|uderz|walcz/.test(l)) return <Sword className="text-ember" size={14} />;
  if (/unik|blok|obron|tarcz/.test(l)) return <Shield className="text-ember" size={14} />;
  if (/czar|zaklęci|magi/.test(l)) return <Sparkle className="text-ember" size={14} />;
  return <Sparkle className="text-ember" size={14} weight="regular" />;
}
