// FE18/FE19 (#1267/#1268) — menu ☰ ekranu gry.
// Ustawienia: dymki, walka, głos (TTS/STT), bramka finału + strefa admina.
import { useQuery } from "@tanstack/react-query";
import {
  X, SpeakerHigh, Microphone, Flag, ChatTeardropText, Sword, Skull,
  CheckCircle, XCircle, Question,
} from "@phosphor-icons/react";
import { useAppStore, type GamePrefKey } from "@/store/appStore";
import { useVoice } from "@/hooks/useVoice";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

export function GameMenu({ finaleAllowed }: { finaleAllowed: boolean }) {
  const open = useAppStore((s) => s.gameMenuOpen);
  const close = useAppStore((s) => s.closeGameMenu);
  const setFinishFlow = useAppStore((s) => s.setFinishFlow);
  const user = useAppStore((s) => s.currentUser);
  const vs = useVoice();

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50" data-testid="game-menu">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={close} />
      <div
        className="absolute right-0 top-0 flex h-full w-[86%] max-w-[340px] flex-col border-l border-line bg-surface shadow-2xl"
        style={{ paddingTop: "var(--sa-top)" }}
      >
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <span className="font-serif text-title text-text">Ustawienia</span>
          <button aria-label="Zamknij" onClick={close} className="text-text-3 hover:text-text">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">

          {/* ── Informacje w dymkach ─────────────────────────────────────── */}
          <SectionHead icon={<ChatTeardropText size={14} />}>Dymki</SectionHead>
          <PrefToggle pkey="gamePrefBubbleName"     label="Wyświetl nazwę" />
          <PrefToggle pkey="gamePrefBubbleTurn"     label="Wyświetl numer tury" />
          <PrefToggle pkey="gamePrefBubbleDatetime" label="Wyświetl datę i godzinę" />

          {/* ── Walka ────────────────────────────────────────────────────── */}
          <SectionHead icon={<Sword size={14} />}>Walka</SectionHead>
          <PrefToggle
            pkey="gamePrefSkipCombatNarr"
            label="Szybka walka (bez narracji)"
            sub="Tylko wynik mechaniczny, bez tekstu GM"
          />

          {/* ── Głos (F-72) ─────────────────────────────────────────────── */}
          <SectionHead icon={<SpeakerHigh size={14} />}>Głos</SectionHead>
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
                onClick={() => { close(); setFinishFlow("confirm"); }}
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

          {/* ── Strefa admina (admin / tester) ──────────────────────────── */}
          {(user?.isAdmin || user?.isTester) && <AdminSection />}
        </div>
      </div>
    </div>
  );
}

// ── Strefa admina ─────────────────────────────────────────────────────────────

function AdminSection() {
  const health = useQuery({
    queryKey: ["system-health"],
    queryFn: () =>
      apiFetch<{
        status: string;
        llm: { status?: string };
        loki: { configured: boolean; reachable: boolean | null };
      }>("/health"),
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const backendOk = !health.isError && !health.isLoading;
  const llmOk = health.data?.llm?.status === "ok";
  const lokiOk = health.data?.loki?.reachable === true;
  const lokiNA = !health.data?.loki?.configured;

  return (
    <>
      <SectionHead icon={<Skull size={14} />} danger>Strefa admina</SectionHead>
      {/* service dots */}
      <div className="mb-2 flex gap-4 px-0.5">
        <Dot label="BACKEND" ok={backendOk} loading={health.isLoading} />
        <Dot label="LLM"     ok={llmOk}     loading={health.isLoading} />
        <Dot label="LOKI"    ok={lokiOk}    loading={health.isLoading} na={lokiNA} />
      </div>
      {/* debug toggle */}
      <PrefToggle pkey="gamePrefDebug" label="Pokaż debug pod wiadomościami GM" />
    </>
  );
}

function Dot({ label, ok, loading, na }: { label: string; ok: boolean; loading?: boolean; na?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      {loading ? (
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-text-3" />
      ) : na ? (
        <Question size={13} className="text-text-3" />
      ) : ok ? (
        <CheckCircle weight="fill" size={13} className="text-success" />
      ) : (
        <XCircle weight="fill" size={13} className="text-danger" />
      )}
      <span className="font-mono text-[9.5px] font-semibold uppercase tracking-wide text-text-3">{label}</span>
    </div>
  );
}

// ── Pref toggle — bezpośrednio z appStore ──────────────────────────────────

function PrefToggle({ pkey, label, sub }: { pkey: GamePrefKey; label: string; sub?: string }) {
  const val = useAppStore((s) => (s as unknown as Record<string, boolean>)[pkey]);
  const setGamePref = useAppStore((s) => s.setGamePref);
  return (
    <button
      type="button"
      role="switch"
      aria-checked={val}
      onClick={() => setGamePref(pkey, !val)}
      className="mb-1.5 flex w-full items-center gap-3 px-0.5 py-1.5 text-left"
    >
      <span className="min-w-0 flex-1">
        <span className="block font-ui text-label text-text">{label}</span>
        {sub && <span className="block font-ui text-micro text-text-3">{sub}</span>}
      </span>
      <MiniSwitch checked={val} />
    </button>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHead({ icon, danger, children }: { icon?: React.ReactNode; danger?: boolean; children: React.ReactNode }) {
  return (
    <div className={cn(
      "mb-1.5 mt-4 flex items-center gap-2 font-ui text-[10.5px] font-bold uppercase tracking-[0.2em] first:mt-0",
      danger ? "text-danger" : "text-ember",
    )}>
      {icon}
      {children}
      <span className="h-px flex-1 bg-line-soft" />
    </div>
  );
}

function Toggle({
  icon, title, sub, checked, disabled, onChange, testid,
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
      <MiniSwitch checked={checked} />
    </button>
  );
}

function MiniSwitch({ checked }: { checked: boolean }) {
  return (
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
  );
}
