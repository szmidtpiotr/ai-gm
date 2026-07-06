// FE13 Dziennik + Kronika bohatera (#1262 / F-23/F-58/F-79) — zakładka w grze.
// Makieta 1:1: zar9-dziennik.html. Wewnętrzne pod-zakładki Zadania / Wątki /
// Kronika, recap „Poprzednio…" + regeneracja, zadania główne + poboczne.
// Kronika bohatera (F-79) — legenda + rozdziały + blizny, read-only.
import { useState } from "react";
import {
  ArrowsClockwise,
  BookmarkSimple,
  BookOpenText,
  CaretRight,
  CheckCircle,
  Circle,
  CircleNotch,
  Coins,
  DoorOpen,
  Scroll,
  Skull,
  Star,
  Target,
  TreeStructure,
  Trophy,
  type Icon,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";
import { useToast } from "@/components/ui/toast";
import { useHeroChronicle, useJournal, useRecap, useRegenRecap } from "@/hooks/useJournal";
import {
  splitQuests,
  type ChronicleChapter,
  type HeroChronicle,
  type JournalData,
  type JournalQuest,
  type JournalThread,
  type RecapData,
} from "@/lib/journal";

type JTab = "quests" | "threads" | "chronicle";

export function Journal({
  campaignId,
  characterId,
}: {
  campaignId: number;
  characterId: number | undefined;
}) {
  const [tab, setTab] = useState<JTab>("quests");
  const userId = useAppStore((s) => s.currentUser?.id);
  const { toast } = useToast();

  const journal = useJournal(campaignId);
  const recap = useRecap(campaignId);
  const chronicle = useHeroChronicle(characterId, tab === "chronicle");
  const regen = useRegenRecap(campaignId, userId);

  function onRegen() {
    regen.mutate(undefined, {
      onSuccess: () => toast("Odświeżono streszczenie „Poprzednio…”", "success"),
      onError: (e) => {
        const msg = e instanceof Error ? e.message : "Nie udało się odświeżyć";
        toast(/cooldown|429/i.test(msg) ? "Chwila przerwy — spróbuj za moment." : msg, "danger");
      },
    });
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Nagłówek panelu — tytuł + regeneracja recapu (makieta: topbar) */}
      <header className="flex items-center gap-2.5 border-b border-line bg-surface px-4 py-2.5">
        <BookOpenText weight="fill" className="text-ember" size={18} />
        <div className="flex-1 font-serif text-title font-semibold text-text">Dziennik</div>
        <button
          onClick={onRegen}
          disabled={regen.isPending}
          aria-label="Odśwież streszczenie"
          className="flex h-9 w-9 items-center justify-center rounded-md border border-line bg-bg text-text-2 hover:border-line-ember hover:text-ember-glow disabled:opacity-50"
        >
          <ArrowsClockwise size={16} className={cn(regen.isPending && "animate-spin")} />
        </button>
      </header>

      {/* Pod-zakładki */}
      <div className="flex gap-0.5 border-b border-line bg-surface px-2.5">
        <JTabBtn on={tab === "quests"} onClick={() => setTab("quests")} icon={Scroll} label="Zadania" />
        <JTabBtn on={tab === "threads"} onClick={() => setTab("threads")} icon={TreeStructure} label="Wątki" />
        <JTabBtn on={tab === "chronicle"} onClick={() => setTab("chronicle")} icon={BookOpenText} label="Kronika" />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <div className="mx-auto w-full max-w-[720px] px-4 py-4 pb-8">
          {tab === "quests" && (
            <QuestsTab journal={journal.data} loading={journal.isLoading} recap={recap.data} />
          )}
          {tab === "threads" && <ThreadsTab threads={journal.data?.threads} loading={journal.isLoading} />}
          {tab === "chronicle" && (
            <ChronicleTab data={chronicle.data} loading={chronicle.isLoading} error={chronicle.isError} />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Zakładka Zadania (recap + główne + poboczne) ─────────────────────────────
function QuestsTab({
  journal,
  loading,
  recap,
}: {
  journal: JournalData | undefined;
  loading: boolean;
  recap: RecapData | undefined;
}) {
  if (loading) return <Loading label="Wczytywanie dziennika…" />;
  const { main, side } = splitQuests(journal?.quests ?? []);

  return (
    <>
      {recap && <RecapCard recap={recap} />}

      {main.length > 0 && (
        <>
          <SecHead>Główne zadanie</SecHead>
          {main.map((q, i) => (
            <QuestCard key={i} quest={q} main />
          ))}
        </>
      )}

      {side.length > 0 && (
        <>
          <SecHead>Zadania poboczne</SecHead>
          {side.map((q, i) => (
            <QuestCard key={i} quest={q} />
          ))}
        </>
      )}

      {!main.length && !side.length && (
        <Empty>Brak aktywnych zadań. Rusz w świat, a znajdą Cię same.</Empty>
      )}
    </>
  );
}

function RecapCard({ recap }: { recap: RecapData }) {
  const text =
    recap.summary?.trim() ||
    recap.recent_turns?.find((t) => t.gm)?.gm ||
    "Twoja opowieść dopiero się rozkręca.";
  const days = recap.hours_since_last != null ? Math.floor(recap.hours_since_last / 24) : 0;
  return (
    <div className="mb-5 rounded-[4px_12px_12px_4px] border border-line border-l-[3px] border-l-ember bg-gm-bubble px-4 py-3">
      <div className="mb-1.5 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-ember">
        <BookmarkSimple weight="fill" size={13} /> Poprzednio…
        {days >= 1 && (
          <span className="ml-auto font-ui text-micro font-normal normal-case tracking-normal text-text-3">
            po {days} {days === 1 ? "dniu" : "dniach"} przerwy
          </span>
        )}
      </div>
      <p className="font-serif text-body italic leading-relaxed text-text-2">{text}</p>
    </div>
  );
}

function QuestCard({ quest, main }: { quest: JournalQuest; main?: boolean }) {
  const done = quest.status === "completed";
  return (
    <div
      className={cn(
        "mb-2.5 flex gap-3 rounded-xl border bg-mech-card px-3.5 py-3",
        main ? "border-line-ember" : "border-line",
      )}
    >
      <span
        className={cn(
          "flex h-9 w-9 flex-none items-center justify-center rounded-lg border",
          main
            ? "border-line bg-[rgba(255,122,61,0.08)] text-ember-glow"
            : "border-[rgba(130,167,199,0.3)] bg-[rgba(130,167,199,0.08)] text-mana",
        )}
      >
        {main ? <Target weight="fill" size={17} /> : <Scroll weight="fill" size={16} />}
      </span>
      <div className="min-w-0 flex-1">
        <div className={cn("text-body font-semibold text-text", done && "text-text-3 line-through")}>
          {quest.title}
        </div>
        {quest.narrative && (
          <div className="mt-1 text-label leading-snug text-text-2">{quest.narrative}</div>
        )}
        {main && (
          <div className="mt-2 flex items-center gap-2 text-label">
            {done ? (
              <span className="flex items-center gap-1.5 text-success">
                <CheckCircle weight="fill" size={14} /> Ukończone
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-ember">
                <CaretRight weight="fill" size={14} /> W toku
              </span>
            )}
          </div>
        )}
      </div>
      {!main && (
        <span
          className={cn(
            "flex-none self-start rounded-pill border px-2.5 py-1 text-[9.5px] font-bold uppercase tracking-wide",
            done
              ? "border-[rgba(168,201,131,0.3)] text-success"
              : "border-[rgba(130,167,199,0.3)] text-mana",
          )}
        >
          {done ? "✓" : "W toku"}
        </span>
      )}
    </div>
  );
}

// ── Zakładka Wątki ────────────────────────────────────────────────────────────
function ThreadsTab({ threads, loading }: { threads: JournalThread[] | undefined; loading: boolean }) {
  if (loading) return <Loading label="Wczytywanie wątków…" />;
  if (!threads?.length) return <Empty>Żadne nici fabuły nie zawisły jeszcze w powietrzu.</Empty>;
  return (
    <>
      <SecHead>Otwarte wątki</SecHead>
      {threads.map((t) => (
        <div key={t.key} className="mb-2 flex items-start gap-3 rounded-xl border border-line bg-mech-card px-3.5 py-3">
          <TreeStructure weight="fill" className="mt-0.5 flex-none text-mana" size={16} />
          <div className="min-w-0 flex-1 text-label leading-snug text-text-2">{t.hint}</div>
          {t.turn > 0 && (
            <span className="flex-none font-mono text-[10px] text-text-3">tura {t.turn}</span>
          )}
        </div>
      ))}
    </>
  );
}

// ── Zakładka Kronika bohatera (F-79) ─────────────────────────────────────────
const OUTCOME: Record<string, { icon: Icon; label: string; color: string }> = {
  victory: { icon: Trophy, label: "Zwycięstwo", color: "text-gold" },
  death: { icon: Skull, label: "Śmierć", color: "text-danger" },
  abandoned: { icon: DoorOpen, label: "Porzucono", color: "text-text-3" },
};

function ChronicleTab({
  data,
  loading,
  error,
}: {
  data: HeroChronicle | undefined;
  loading: boolean;
  error: boolean;
}) {
  if (loading) return <Loading label="Wczytywanie kroniki…" />;
  if (error) return <Empty>Nie udało się wczytać kroniki bohatera.</Empty>;

  const legend = data?.legend?.trim();
  const chapters = data?.chapters ?? [];
  const scars = data?.scars ?? [];

  if (!legend && !chapters.length && !scars.length) {
    return (
      <Empty>Twoja legenda dopiero się zaczyna. Ukończ pierwszą przygodę, by zapisać rozdział.</Empty>
    );
  }

  return (
    <>
      {legend && (
        <>
          <SecHead>Legenda</SecHead>
          <div className="mb-5 rounded-xl border border-line-ember bg-[rgba(255,122,61,0.06)] px-4 py-3.5">
            <Star weight="fill" className="mb-2 text-gold" size={18} />
            <p className="font-serif text-body italic leading-relaxed text-text-2">{legend}</p>
          </div>
        </>
      )}

      {chapters.length > 0 && (
        <>
          <SecHead>Rozdziały</SecHead>
          {chapters.map((c) => (
            <ChapterRow key={c.id} c={c} />
          ))}
        </>
      )}

      {scars.length > 0 && (
        <>
          <SecHead>Niedokończone sprawy</SecHead>
          {scars.map((s) => (
            <div
              key={s.id}
              className="mb-2 flex gap-3 rounded-xl border border-line-danger bg-[rgba(232,96,79,0.06)] px-3.5 py-3"
            >
              <DoorOpen weight="fill" className="mt-0.5 flex-none text-danger" size={16} />
              <div className="min-w-0 flex-1">
                <div className="text-label font-semibold text-text">
                  {s.campaign_title || `Kampania #${s.campaign_id}`}
                </div>
                {s.abandonment_note && (
                  <div className="mt-1 font-serif text-label italic leading-snug text-text-3">
                    {s.abandonment_note}
                  </div>
                )}
              </div>
            </div>
          ))}
        </>
      )}
    </>
  );
}

function ChapterRow({ c }: { c: ChronicleChapter }) {
  const o = OUTCOME[c.outcome] ?? { icon: Circle, label: c.outcome || "—", color: "text-text-3" };
  const OIcon = o.icon;
  return (
    <div className="mb-2 flex gap-3 rounded-xl border border-line bg-mech-card px-3.5 py-3">
      <OIcon weight="fill" className={cn("mt-0.5 flex-none", o.color)} size={18} />
      <div className="min-w-0 flex-1">
        <div className="text-body font-semibold text-text">
          {c.campaign_title || `Kampania #${c.campaign_id}`}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[10px] text-text-3">
          <span className={o.color}>{o.label}</span>
          <span>·</span>
          <span className="flex items-center gap-1">
            <Coins weight="fill" size={10} /> {c.xp_earned ?? 0} PD
          </span>
          <span>·</span>
          <span>{c.turns_count ?? 0} tur</span>
        </div>
        {c.chapter_summary && (
          <div className="mt-1.5 font-serif text-label italic leading-snug text-text-2">
            {c.chapter_summary}
          </div>
        )}
      </div>
    </div>
  );
}

// ── prymitywy ────────────────────────────────────────────────────────────────
function JTabBtn({
  on,
  onClick,
  icon: Ico,
  label,
}: {
  on: boolean;
  onClick: () => void;
  icon: Icon;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-1 items-center justify-center gap-1.5 border-b-2 px-1 pb-2.5 pt-3 font-ui text-label font-semibold tracking-wide transition-colors",
        on ? "border-ember text-ember-glow" : "border-transparent text-text-3 hover:text-text-2",
      )}
    >
      <Ico weight={on ? "fill" : "regular"} size={15} />
      {label}
    </button>
  );
}

function SecHead({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-3 mt-4 flex items-center gap-2.5 font-ui text-[10.5px] font-bold uppercase tracking-[0.2em] text-ember first:mt-0 after:h-px after:flex-1 after:bg-line-soft after:content-['']">
      {children}
    </h3>
  );
}

function Loading({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-text-3">
      <CircleNotch className="animate-spin" size={20} />
      <span className="font-ui text-body">{label}</span>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-4 rounded-md border border-line-soft bg-surface px-4 py-8 text-center font-serif text-body text-text-3">
      {children}
    </p>
  );
}
