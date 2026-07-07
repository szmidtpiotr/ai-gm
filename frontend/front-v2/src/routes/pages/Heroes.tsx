import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  User,
  Plus,
  Play,
  Heart,
  Coins,
  Circle,
  Moon,
  CircleNotch,
  Warning,
  Trash,
} from "@phosphor-icons/react";
import { useHeroes, useCampaigns, useDeleteHero } from "@/hooks/useGameData";
import { joinViaToken } from "@/lib/multiplayer";
import { useAppStore } from "@/store/appStore";
import { useToast } from "@/components/ui/toast";
import type { Hero } from "@/lib/types";
import { cn } from "@/lib/utils";

const RACE_PL: Record<string, string> = { human: "Człowiek", dwarf: "Krasnolud" };
const CLASS_PL: Record<string, string> = {
  warrior: "Wojownik",
  scholar: "Uczony",
  mage: "Mag",
  rogue: "Łotrzyk",
  ranger: "Łowca",
  cleric: "Kapłan",
};

function cap(s: string) {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

function heroMeta(h: Hero): string {
  const race = RACE_PL[h.race] ?? cap(h.race || "");
  const rawClass = String(h.sheet_json?.archetype ?? h.sheet_json?.class ?? "");
  const cls = CLASS_PL[rawClass.toLowerCase()] ?? cap(rawClass);
  const lvl = h.sheet_json?.level ?? 1;
  return [race, cls, `poziom ${lvl}`].filter(Boolean).join(" · ");
}

function heroHp(h: Hero): { cur: number; max: number } {
  const s = h.sheet_json ?? {};
  const max = Number(s.max_hp ?? s.hp ?? 0);
  const cur = Number(s.hp_current ?? s.hp ?? max);
  return { cur, max };
}

function heroGold(h: Hero): number {
  const s = h.sheet_json ?? {};
  return Number(s.gold_gp ?? s.gold ?? 0);
}

export default function Heroes() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const setHero = useAppStore((s) => s.setHero);
  const userId = useAppStore((s) => s.currentUser?.id);
  const { data: heroes, isLoading, isError } = useHeroes();
  const { data: campaigns } = useCampaigns();
  const deleteHero = useDeleteHero();
  const { toast } = useToast();
  // Bohater do usunięcia (modal potwierdzenia) — usuwa też powiązane kampanie.
  const [pendingDelete, setPendingDelete] = useState<Hero | null>(null);

  function confirmDelete() {
    if (!pendingDelete || userId == null) return;
    deleteHero.mutate(
      { heroId: pendingDelete.id, userId },
      {
        onSuccess: () => {
          toast("Bohater i powiązane kampanie usunięte.", "success");
          setPendingDelete(null);
        },
        onError: (e) =>
          toast(e instanceof Error ? e.message : "Nie udało się usunąć bohatera.", "danger"),
      },
    );
  }

  // FE15 (#1264): zaproszenie przez link (?join=TOKEN) → dołącz do drużyny i wejdź
  // do lobby. RootRedirect przekierowuje ?join na /bohaterowie (§11).
  const joinedRef = useRef(false);
  useEffect(() => {
    const token = params.get("join");
    if (!token || joinedRef.current) return;
    joinedRef.current = true;
    joinViaToken(token)
      .then((d) => navigate(`/druzyna/${d.campaign_id}`, { replace: true }))
      .catch(() => {
        const next = new URLSearchParams(params);
        next.delete("join");
        setParams(next, { replace: true });
      });
  }, [params, navigate, setParams]);

  function enterHero(hero: Hero) {
    setHero(hero.id);
    // Nowy flow (§11): dokładnie 1 aktywna kampania → prosto do gry; ≥2 → lista.
    const active = (campaigns ?? []).filter(
      (c) => c.character_id === hero.id && c.status === "active",
    );
    if (active.length === 1) {
      navigate(`/gra/${active[0].id}`);
    } else {
      navigate(`/bohaterowie/${hero.id}/kampanie`);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-serif text-title-lg text-text">Twoi bohaterowie</h1>
      <p className="-mt-2 font-ui text-label text-text-3">
        Wybierz bohatera, by kontynuować przygodę — albo stwórz nowego.
      </p>

      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-16 text-text-3">
          <CircleNotch className="animate-spin" size={22} />
          <span className="font-ui text-body">Wczytywanie bohaterów…</span>
        </div>
      )}

      {isError && (
        <div className="flex items-center gap-2 rounded-lg border border-line-danger bg-danger/10 px-4 py-3 text-danger-glow">
          <Warning size={20} />
          <span className="font-ui text-body">
            Nie udało się wczytać bohaterów. Odśwież stronę.
          </span>
        </div>
      )}

      {heroes && (
        <div className="grid grid-cols-1 gap-4">
          {heroes.map((h) => (
            <HeroCard
              key={h.id}
              hero={h}
              onEnter={() => enterHero(h)}
              onDelete={() => setPendingDelete(h)}
            />
          ))}

          <button
            onClick={() => navigate("/bohaterowie/nowy")}
            className="flex min-h-[132px] flex-col items-center justify-center gap-2.5 rounded-lg border border-dashed border-line-ember bg-ember/[0.03] text-ember-glow transition-colors hover:bg-ember/[0.07]"
          >
            <span className="flex h-11 w-11 items-center justify-center rounded-md border border-line-ember">
              <Plus size={22} />
            </span>
            <span className="font-ui text-body font-semibold">Nowy bohater</span>
            <span className="font-ui text-micro text-text-3">Stwórz postać od podstaw</span>
          </button>
        </div>
      )}

      {pendingDelete && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-6" data-testid="hero-delete-modal">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => !deleteHero.isPending && setPendingDelete(null)}
          />
          <div className="relative z-[2] w-full max-w-[380px] rounded-xl border border-line-danger bg-surface p-6 text-center">
            <Warning weight="fill" size={40} className="mx-auto text-danger" />
            <h2 className="mt-3 font-serif text-title-lg font-semibold text-text">Usunąć bohatera?</h2>
            <p className="mt-2 font-serif text-prose leading-relaxed text-text-2">
              <b className="text-text">{pendingDelete.name}</b> oraz wszystkie powiązane kampanie zostaną
              trwale usunięte. Tej operacji nie można cofnąć.
            </p>
            <div className="mt-5 flex gap-2.5">
              <button
                type="button"
                disabled={deleteHero.isPending}
                onClick={() => setPendingDelete(null)}
                className="flex-1 rounded-md border border-line bg-bg py-2.5 font-ui text-body font-semibold text-text-2 transition-colors hover:border-line-ember disabled:opacity-50"
              >
                Anuluj
              </button>
              <button
                type="button"
                data-testid="hero-delete-confirm"
                disabled={deleteHero.isPending}
                onClick={confirmDelete}
                className="flex flex-1 items-center justify-center gap-2 rounded-md border border-line-danger bg-danger/[0.12] py-2.5 font-ui text-body font-semibold text-danger transition-colors hover:bg-danger/20 disabled:opacity-60"
              >
                {deleteHero.isPending ? (
                  <>
                    <CircleNotch className="animate-spin" size={16} /> Usuwam…
                  </>
                ) : (
                  <>
                    <Trash size={16} /> Usuń
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function HeroCard({
  hero,
  onEnter,
  onDelete,
}: {
  hero: Hero;
  onEnter: () => void;
  onDelete: () => void;
}) {
  const inCampaign = hero.hero_status === "in_campaign" && !!hero.campaign_id;
  const inDungeon = hero.hero_status === "in_dungeon";
  const active = inCampaign || inDungeon;
  const { cur, max } = heroHp(hero);
  const gold = heroGold(hero);

  return (
    <div className="relative">
      {/* Usuń bohatera — poza kartą (nie zagnieżdżamy przycisku w przycisku). */}
      <button
        type="button"
        aria-label={`Usuń bohatera ${hero.name}`}
        title="Usuń bohatera"
        onClick={onDelete}
        className="absolute right-2 top-2 z-30 flex h-8 w-8 items-center justify-center rounded-md border border-line bg-surface/90 text-text-3 backdrop-blur transition-colors hover:border-line-danger hover:text-danger"
      >
        <Trash size={15} />
      </button>
    <button
      onClick={onEnter}
      className={cn(
        "group relative flex w-full gap-3.5 overflow-hidden rounded-lg border bg-mech-card p-3.5 text-left transition-colors",
        active
          ? "border-line-ember shadow-float"
          : "border-line hover:border-line-ember",
      )}
    >
      {/* portret = sylwetka-placeholder */}
      <span
        className="flex h-[88px] w-[70px] shrink-0 items-center justify-center rounded-md border border-line text-[34px] text-ember-glow/70"
        style={{
          background:
            "radial-gradient(70% 50% at 50% 30%, rgba(255,122,61,.2), transparent 70%), linear-gradient(180deg,#2b2016,#161009)",
        }}
      >
        <User weight="fill" />
      </span>

      <div className="relative z-10 min-w-0 flex-1 pb-8">
        <div className="truncate pr-8 font-serif text-title font-semibold text-text">
          {hero.name}
        </div>
        <div className="mt-0.5 truncate font-ui text-micro text-text-2">
          {heroMeta(hero)}
        </div>

        <span
          className={cn(
            "mt-2 inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 font-ui text-[10.5px] font-semibold tracking-wide",
            active
              ? "border border-success/35 bg-success/10 text-success"
              : "border border-line text-text-3",
          )}
        >
          {active ? <Circle weight="fill" size={9} /> : <Moon weight="fill" size={10} />}
          {inDungeon
            ? "W lochu"
            : inCampaign
              ? `W kampanii «${hero.campaign_title ?? "…"}»`
              : "Spoczynek"}
        </span>

        <div className="mt-2.5 flex gap-3 font-mono text-micro text-text-3">
          <span className="flex items-center gap-1">
            <Heart weight="fill" size={12} className="text-ember" />
            <b className="font-medium text-text-2">
              {cur}/{max}
            </b>
          </span>
          <span className="flex items-center gap-1">
            <Coins weight="fill" size={12} className="text-gold" />
            <b className="font-medium text-text-2">{gold}</b>
          </span>
        </div>
      </div>

      <span
        className={cn(
          "absolute bottom-3 right-3 z-20 flex items-center gap-1.5 rounded-pill border px-3 py-1.5 font-ui text-micro font-semibold",
          active
            ? "border-line-ember bg-ember/10 text-ember-glow"
            : "border-line bg-surface text-text-2",
        )}
      >
        <Play weight="fill" size={13} /> {active ? "Graj" : "Wznów"}
      </span>
    </button>
    </div>
  );
}
