// FE18/FE19 (#1267/#1268) — menu ☰ ekranu gry. Ustawienia głosu (TTS/STT autosend)
// + bramka finału „Zakończ przygodę" (tylko gdy cel osiągnięty i — w MP — gospodarz).
import { X, SpeakerHigh, Microphone, Flag } from "@phosphor-icons/react";
import { useAppStore } from "@/store/appStore";
import { useVoice } from "@/hooks/useVoice";
import { cn } from "@/lib/utils";

export function GameMenu({ finaleAllowed }: { finaleAllowed: boolean }) {
  const open = useAppStore((s) => s.gameMenuOpen);
  const close = useAppStore((s) => s.closeGameMenu);
  const setFinishFlow = useAppStore((s) => s.setFinishFlow);
  const vs = useVoice();

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50" data-testid="game-menu">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={close} />
      <div className="absolute right-0 top-0 flex h-full w-[86%] max-w-[340px] flex-col border-l border-line bg-surface shadow-2xl" style={{ paddingTop: "var(--sa-top)" }}>
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <span className="font-serif text-title text-text">Menu</span>
          <button aria-label="Zamknij" onClick={close} className="text-text-3 hover:text-text">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {/* ── Głos (F-72) ─────────────────────────────────────────────── */}
          <SectionHead>Głos</SectionHead>
          <Toggle
            icon={<SpeakerHigh size={18} />}
            title="Czytanie narracji (TTS)"
            sub={vs.ttsLocked ? "Wyłączone przez administratora" : "Lektor czyta odpowiedzi GM"}
            checked={vs.ttsEnabled}
            disabled={vs.ttsLocked || !vs.available}
            onChange={(v) => vs.setTtsEnabled(v, { unlock: v })}
            testid="toggle-tts"
          />
          <Toggle
            icon={<Microphone size={18} />}
            title="Auto-wyślij dyktowanie"
            sub={vs.sttLocked ? "Głos wyłączony przez administratora" : "Po transkrypcji wyślij od razu"}
            checked={vs.autosend}
            disabled={vs.sttLocked || !vs.available}
            onChange={(v) => vs.setAutosend(v)}
            testid="toggle-autosend"
          />
          {!vs.available && (
            <p className="mt-1 px-1 font-ui text-micro text-text-3">Usługa głosu chwilowo niedostępna.</p>
          )}

          {/* ── Przygoda (F-77) ─────────────────────────────────────────── */}
          {finaleAllowed && (
            <>
              <SectionHead>Przygoda</SectionHead>
              <button
                type="button"
                data-testid="menu-finish-campaign"
                onClick={() => {
                  close();
                  setFinishFlow("confirm");
                }}
                className="flex w-full items-center gap-3 rounded-md border border-line-ember bg-ember/[0.06] px-3.5 py-3 text-left transition-colors hover:border-ember"
              >
                <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md border border-line-ember bg-bg text-ember-glow">
                  <Flag weight="fill" size={18} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-ui text-body font-semibold text-ember-glow">Zakończ przygodę</span>
                  <span className="block font-ui text-micro text-text-3">Osiągnąłeś cel — dokończ opowieść</span>
                </span>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SectionHead({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2.5 mt-4 flex items-center gap-2.5 font-ui text-[10.5px] font-bold uppercase tracking-[0.2em] text-ember first:mt-0">
      {children}
      <span className="h-px flex-1 bg-line-soft" />
    </div>
  );
}

function Toggle({
  icon,
  title,
  sub,
  checked,
  disabled,
  onChange,
  testid,
}: {
  icon: React.ReactNode;
  title: string;
  sub: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
  testid?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      data-testid={testid}
      onClick={() => onChange(!checked)}
      className="mb-2 flex w-full items-center gap-3.5 rounded-md border border-line-soft bg-surface px-3.5 py-3 text-left transition-colors hover:border-line disabled:opacity-50"
    >
      <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-2">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-ui text-body font-semibold text-text">{title}</span>
        <span className="block truncate font-ui text-micro text-text-3">{sub}</span>
      </span>
      <span
        className={cn(
          "relative h-6 w-11 shrink-0 rounded-pill border transition-colors",
          checked ? "border-line-ember bg-ember/70" : "border-line bg-bg",
        )}
      >
        <span
          className={cn(
            "absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-pill bg-white transition-all",
            checked ? "left-[calc(100%-1.15rem)]" : "left-1",
          )}
        />
      </span>
    </button>
  );
}
