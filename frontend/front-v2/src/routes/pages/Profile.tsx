import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  PencilSimple,
  UsersThree,
  Crown,
  Clock,
  Scroll,
  Users,
  Envelope,
  Brain,
  ShieldCheck,
  CaretRight,
  SignOut,
  SpeakerHigh,
  Microphone,
  Sword,
  ChatTeardropText,
  Skull,
  CheckCircle,
  XCircle,
  Question,
  type Icon,
} from "@phosphor-icons/react";
import { useAppStore, type GamePrefKey } from "@/store/appStore";
import { useHeroes, useLlmSettings } from "@/hooks/useGameData";
import { useToast } from "@/components/ui/toast";
import { PushButton } from "@/components/PushButton";
import { useVoice } from "@/hooks/useVoice";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

// F-07 Profil gracza. Makieta 1:1 → zar8-profil.html.
export default function Profile() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const user = useAppStore((s) => s.currentUser);
  const logout = useAppStore((s) => s.logout);
  const { data: heroes } = useHeroes();
  const { data: llm } = useLlmSettings(user?.id);
  const vs = useVoice();

  const name = user?.displayName || user?.username || "Gracz";
  const email = user?.email || "—";
  const initial = name.charAt(0).toUpperCase();

  const heroCount = heroes?.length ?? 0;
  const completed = (heroes ?? []).reduce((n, h) => n + (h.campaigns_completed || 0), 0);
  const legends = (heroes ?? []).filter((h) => (h.campaigns_completed || 0) > 0).length;

  function onLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  const soon = () => toast("Ta sekcja pojawi się wkrótce.", "info");

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      {/* nagłówek tożsamości */}
      <div className="relative flex items-center gap-4 overflow-hidden rounded-xl border border-line bg-mech-card p-[18px]">
        <div
          className="relative z-10 flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-pill border-2 border-line-ember font-serif text-[30px] text-ember-glow"
          style={{ background: "radial-gradient(circle at 35% 30%,#553d2b,#241c13 70%)" }}
        >
          {initial}
        </div>
        <div className="relative z-10 min-w-0 flex-1">
          <div className="truncate font-serif text-title-lg font-semibold text-text">{name}</div>
          <div className="mt-0.5 truncate font-mono text-label text-text-2">{email}</div>
          <button
            onClick={soon}
            className="mt-2 inline-flex items-center gap-1.5 rounded-pill border border-line-ember bg-ember/[0.08] px-3 py-1 font-ui text-micro text-ember-glow"
          >
            <PencilSimple size={13} /> Edytuj profil
          </button>
        </div>
      </div>

      {/* kafle kroniki */}
      <div className="grid grid-cols-4 gap-2">
        <ChronTile icon={UsersThree} value={heroCount} label="Bohaterów" />
        <ChronTile icon={Crown} value={completed} label="Ukończonych" />
        <ChronTile icon={Clock} value="—" label="W grze" />
        <ChronTile icon={Scroll} value={legends} label="Legendy" />
      </div>

      <div className="grid gap-x-8 lg:grid-cols-2">
        <section>
          <SectionHead>Społeczność</SectionHead>
          <div className="flex flex-col gap-2">
            <Row icon={Users} title="Znajomi" sub="Wspólne przygody" onClick={soon} />
            <Row icon={Envelope} title="Zaproszenia" sub="Zaproś do gry" onClick={soon} />
          </div>
        </section>

        <section>
          <SectionHead>Ustawienia konta</SectionHead>
          <div className="flex flex-col gap-2">
            <Row
              icon={Brain}
              title="Konfiguracja LLM"
              sub="Model narracji"
              badge={llm?.model}
              onClick={soon}
            />
            <Row icon={ShieldCheck} title="Bezpieczeństwo" sub="Hasło, sesje" onClick={soon} />
            <PushButton />
          </div>
        </section>
      </div>

      {/* ── Ustawienia gry ─────────────────────────────────────────────────── */}
      <section>
        <SectionHead>Ustawienia gry</SectionHead>
        <div className="flex flex-col gap-2">

          {/* Informacje w dymkach */}
          <SettingsGroup icon={<ChatTeardropText size={17} />} title="Informacje w dymkach">
            <PrefToggle pkey="gamePrefBubbleName" label="Wyświetl nazwę" />
            <PrefToggle pkey="gamePrefBubbleTurn" label="Wyświetl numer tury" />
            <PrefToggle pkey="gamePrefBubbleDatetime" label="Wyświetl datę i godzinę" />
          </SettingsGroup>

          {/* Walka */}
          <SettingsGroup icon={<Sword size={17} />} title="Walka">
            <PrefToggle
              pkey="gamePrefSkipCombatNarr"
              label="Szybka walka (bez narracji)"
              sub="Wyłącza tekst GM po akcjach bojowych — tylko wynik mechaniczny"
            />
          </SettingsGroup>

          {/* Głos */}
          <SettingsGroup icon={<SpeakerHigh size={17} />} title="Głos">
            <VoiceRow
              icon={<SpeakerHigh size={16} />}
              label="Czytaj narrację GM (TTS)"
              sub={vs.ttsLocked ? "Wyłączone przez administratora" : undefined}
              checked={vs.ttsEnabled}
              disabled={vs.ttsLocked || !vs.available}
              onChange={(v) => vs.setTtsEnabled(v, { unlock: v })}
            />
            <VoiceRow
              icon={<Microphone size={16} />}
              label="Auto-wyślij dyktowanie (STT)"
              sub={vs.sttLocked ? "Głos wyłączony przez administratora" : undefined}
              checked={vs.autosend}
              disabled={vs.sttLocked || !vs.available}
              onChange={(v) => vs.setAutosend(v)}
            />
            {!vs.available && (
              <p className="mt-1 font-ui text-micro text-text-3">Usługa głosu chwilowo niedostępna.</p>
            )}
          </SettingsGroup>

          {/* Strefa admina — tylko dla admin/tester */}
          {(user?.isAdmin || user?.isTester) && <AdminGroup />}
        </div>
      </section>

      <button
        onClick={onLogout}
        className="mt-2 flex w-full items-center justify-center gap-2.5 rounded-md border border-line-danger bg-danger/[0.06] py-3.5 font-ui text-body font-semibold text-danger"
      >
        <SignOut size={18} /> Wyloguj się
      </button>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ChronTile({ icon: I, value, label }: { icon: Icon; value: number | string; label: string }) {
  return (
    <div className="rounded-md border border-line bg-surface px-1.5 py-3.5 text-center">
      <I weight="fill" size={18} className="mx-auto text-ember-glow" />
      <div className="mt-1 font-mono text-title font-semibold text-text">{value}</div>
      <div className="mt-0.5 font-ui text-[9.5px] uppercase tracking-wide text-text-3">{label}</div>
    </div>
  );
}

function SectionHead({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2.5 mt-4 flex items-center gap-2.5 font-ui text-[10.5px] font-bold uppercase tracking-[0.2em] text-ember">
      {children}
      <span className="h-px flex-1 bg-line-soft" />
    </div>
  );
}

function Row({ icon: I, title, sub, badge, onClick }: { icon: Icon; title: string; sub: string; badge?: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-3.5 rounded-md border border-line-soft bg-surface px-3.5 py-3 text-left transition-colors hover:border-line"
    >
      <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-2">
        <I size={18} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-ui text-body font-semibold text-text">{title}</span>
        <span className="block truncate font-ui text-micro text-text-3">{sub}</span>
      </span>
      {badge && (
        <span className="shrink-0 rounded-pill border border-mana/30 px-2.5 py-1 font-mono text-[9.5px] uppercase tracking-wide text-mana">
          {badge}
        </span>
      )}
      <CaretRight size={15} className="shrink-0 text-text-3" />
    </button>
  );
}

// Expandable settings group
function SettingsGroup({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="overflow-hidden rounded-md border border-line-soft bg-surface">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3.5 px-3.5 py-3 text-left"
      >
        <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-2">
          {icon}
        </span>
        <span className="flex-1 font-ui text-body font-semibold text-text">{title}</span>
        <CaretRight
          size={15}
          className={cn("shrink-0 text-text-3 transition-transform duration-200", open && "rotate-90")}
        />
      </button>
      {open && (
        <div className="border-t border-line-soft px-3.5 pb-2 pt-1">
          {children}
        </div>
      )}
    </div>
  );
}

// Toggle row for game prefs (localStorage-backed via appStore)
function PrefToggle({ pkey, label, sub }: { pkey: GamePrefKey; label: string; sub?: string }) {
  const val = useAppStore((s) => (s as unknown as Record<string, boolean>)[pkey]);
  const setGamePref = useAppStore((s) => s.setGamePref);
  return <ToggleRow label={label} sub={sub} checked={val} onChange={(v) => setGamePref(pkey, v)} />;
}

// Toggle row for voice controls
function VoiceRow({ icon, label, sub, checked, disabled, onChange }: {
  icon: React.ReactNode;
  label: string;
  sub?: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="my-1.5 flex w-full items-center gap-2.5 text-left disabled:opacity-50"
    >
      <span className="text-text-3">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block font-ui text-label text-text">{label}</span>
        {sub && <span className="block font-ui text-micro text-text-3">{sub}</span>}
      </span>
      <Switch checked={checked} />
    </button>
  );
}

// Toggle row generic (for prefs without icon)
function ToggleRow({ label, sub, checked, onChange }: { label: string; sub?: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="my-1.5 flex w-full items-center gap-2.5 text-left"
    >
      <span className="min-w-0 flex-1">
        <span className="block font-ui text-label text-text">{label}</span>
        {sub && <span className="mt-0.5 block font-ui text-micro leading-snug text-text-3">{sub}</span>}
      </span>
      <Switch checked={checked} />
    </button>
  );
}

function Switch({ checked }: { checked: boolean }) {
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

// Admin zone — health indicators + debug toggle
function AdminGroup() {
  const gamePrefDebug = useAppStore((s) => s.gamePrefDebug);
  const setGamePref = useAppStore((s) => s.setGamePref);
  const health = useQuery({
    queryKey: ["system-health"],
    queryFn: () => apiFetch<{
      status: string;
      llm: { status?: string };
      loki: { configured: boolean; reachable: boolean | null };
    }>("/health"),
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const backendOk = !health.isError;
  const llmOk = health.data?.llm?.status === "ok";
  const lokiOk = health.data?.loki?.reachable === true;
  const lokiConfigured = health.data?.loki?.configured ?? false;

  return (
    <div className="overflow-hidden rounded-md border border-line-danger/40 bg-[rgba(232,96,79,0.04)]">
      {/* header */}
      <div className="flex items-center gap-3.5 px-3.5 py-3">
        <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md border border-line-danger/40 bg-bg text-danger">
          <Skull size={17} />
        </span>
        <span className="flex-1 font-ui text-body font-semibold text-danger">Strefa admina</span>
      </div>
      <div className="border-t border-line-danger/20 px-3.5 pb-3 pt-2">
        {/* service dots */}
        <div className="mb-3 flex gap-4">
          <ServiceDot label="BACKEND" ok={backendOk} loading={health.isLoading} />
          <ServiceDot label="LLM" ok={llmOk} loading={health.isLoading} />
          <ServiceDot label="LOKI" ok={lokiOk} loading={health.isLoading} na={!lokiConfigured} />
        </div>
        {/* debug toggle */}
        <ToggleRow
          label="Pokaż debug pod wiadomościami GM"
          checked={gamePrefDebug}
          onChange={(v) => setGamePref("gamePrefDebug", v)}
        />
      </div>
    </div>
  );
}

function ServiceDot({ label, ok, loading, na }: { label: string; ok: boolean; loading?: boolean; na?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      {loading ? (
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-text-3" />
      ) : na ? (
        <Question size={14} className="text-text-3" />
      ) : ok ? (
        <CheckCircle weight="fill" size={14} className="text-success" />
      ) : (
        <XCircle weight="fill" size={14} className="text-danger" />
      )}
      <span className="font-mono text-[10px] font-semibold uppercase tracking-wide text-text-3">{label}</span>
    </div>
  );
}
