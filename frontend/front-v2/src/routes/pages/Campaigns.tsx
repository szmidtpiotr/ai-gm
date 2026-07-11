import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Scroll,
  BookOpenText,
  Skull,
  PawPrint,
  Crown,
  Trash,
  Play,
  CircleNotch,
  Warning,
  Star,
  Lock,
  UsersThree,
} from "@phosphor-icons/react";
import {
  useCampaigns,
  useCampaignDetail,
  useCampaignTemplates,
  useDungeons,
  useHeroes,
  useCreateCampaign,
  useAssignHero,
  useDeleteCampaign,
} from "@/hooks/useGameData";
import { apiFetch } from "@/lib/api";
import {
  useActiveDungeonRun,
  useDungeonExit,
  useDeleteDungeonCampaign,
} from "@/hooks/useDungeon";
import { ResumeModal } from "@/components/game/dungeon/DungeonModals";
import { createLobby } from "@/lib/multiplayer";
import { useAppStore } from "@/store/appStore";
import { useToast } from "@/components/ui/toast";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ProgressBar } from "@/components/ui/progress-bar";
import type { Campaign, CampaignTemplate, Dungeon } from "@/lib/types";
import { cn } from "@/lib/utils";

const GENERIC_TITLE = /^(Przygoda\s+\S+|Kampania(\s+#?\d+)?|Nowa kampania|Ekspedycja:.*)$/i;

function isActiveStatus(c: Campaign): boolean {
  return !["ended", "discarded", "archived", "completed"].includes(c.status);
}

function belongsToHero(c: Campaign, heroId: number): boolean {
  if (c.character_id == null) return true; // wolna kampania — bohater może wejść
  return Number(c.character_id) === heroId;
}

function deriveProgress(planJson?: string | null): {
  pct: number | null;
  actLabel: string | null;
} {
  if (!planJson) return { pct: null, actLabel: null };
  let plan: Record<string, unknown>;
  try {
    plan = JSON.parse(planJson);
  } catch {
    return { pct: null, actLabel: null };
  }
  const acts = Array.isArray(plan.acts) ? (plan.acts as Array<Record<string, unknown>>) : null;
  if (acts && acts.length) {
    const total = acts.length;
    const active = Number(plan.active_act || 1);
    const done = acts.filter((a) => a?.completed).length;
    let pct = Math.round((done / total) * 100);
    if (pct === 0 && active > 1) pct = Math.round(((active - 1) / total) * 100);
    return { pct, actLabel: `Akt ${Math.min(active, total)} z ${total}` };
  }
  return { pct: null, actLabel: null };
}

export default function Campaigns() {
  const { heroId: heroIdParam } = useParams();
  const heroId = Number(heroIdParam);
  const navigate = useNavigate();
  const { toast } = useToast();
  const user = useAppStore((s) => s.currentUser);
  const setCampaign = useAppStore((s) => s.setCampaign);
  const setHero = useAppStore((s) => s.setHero);

  const { data: heroes } = useHeroes();
  const { data: campaigns, isLoading, isError } = useCampaigns();

  const createCampaign = useCreateCampaign();
  const assignHero = useAssignHero();
  const deleteCampaign = useDeleteCampaign();

  const [picker, setPicker] = useState<null | "nowa" | "gotowa" | "loch">(null);
  const [toDelete, setToDelete] = useState<Campaign | null>(null);
  const [busy, setBusy] = useState(false);

  const hero = heroes?.find((h) => h.id === heroId);

  const mine = (campaigns ?? []).filter(
    (c) =>
      Number(c.owner_user_id) === Number(user?.id) && belongsToHero(c, heroId),
  );
  const active = mine.filter(isActiveStatus);
  const history = (campaigns ?? []).filter(
    (c) =>
      Number(c.owner_user_id) === Number(user?.id) &&
      (c.status === "archived" || c.status === "completed") &&
      c.mode !== "dungeon" &&
      (c.character_id == null || Number(c.character_id) === heroId),
  );

  function enterGame(campaignId: number) {
    setHero(heroId);
    setCampaign(campaignId);
    navigate(`/gra/${campaignId}`);
  }

  // F-10 — utwórz kampanię danego trybu, przypisz bohatera, wejdź do gry.
  async function launch(
    mode: "solo" | "pre_built" | "dungeon",
    title: string,
    templateId?: number,
    dungeonKey?: string,
  ) {
    if (!user?.id || !hero) return;
    setBusy(true);
    try {
      const campaign = await createCampaign.mutateAsync({
        title,
        ownerUserId: user.id,
        mode,
        templateId,
      });
      await assignHero.mutateAsync({
        heroId,
        campaignId: campaign.id,
        userId: user.id,
      });
      if (mode === "dungeon" && dungeonKey) {
        await apiFetch(`/dungeons/${dungeonKey}/enter`, {
          method: "POST",
          body: { character_id: heroId, campaign_id: campaign.id },
        });
      }
      setPicker(null);
      enterGame(campaign.id);
    } catch (e) {
      toast((e as Error).message || "Nie udało się rozpocząć przygody", "danger");
    } finally {
      setBusy(false);
    }
  }

  // FE15 (#1264) — utwórz lobby drużynowe (MP) i przejdź do ekranu drużyny (F-13).
  async function launchMp() {
    if (!user?.id || !hero) return;
    setBusy(true);
    try {
      const res = await createLobby({
        title: `Drużyna ${hero.name}`,
        round_timer_minutes: 1440,
        max_players: 4,
      });
      navigate(`/druzyna/${res.campaign_id}`);
    } catch (e) {
      toast((e as Error).message || "Nie udało się utworzyć drużyny", "danger");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDelete() {
    if (!toDelete) return;
    try {
      await deleteCampaign.mutateAsync(toDelete.id);
      toast("Kampania usunięta", "success");
    } catch (e) {
      toast((e as Error).message || "Błąd usuwania", "danger");
    } finally {
      setToDelete(null);
    }
  }

  return (
    <div className="flex flex-col">
      {/* Rozpocznij przygodę — 3 typy */}
      <SectionHeader>Rozpocznij przygodę</SectionHeader>
      <div className="mb-6 grid grid-cols-3 gap-2.5">
        <TypeCard
          icon={<Scroll weight="fill" />}
          title="Nowa"
          sub="Własna historia od zera"
          onClick={() => setPicker("nowa")}
        />
        <TypeCard
          icon={<BookOpenText weight="fill" />}
          title="Gotowa"
          sub="Przygoda z Kuźni"
          onClick={() => setPicker("gotowa")}
        />
        <TypeCard
          icon={<Skull weight="fill" />}
          title="Loch"
          sub="Farmienie i łup"
          onClick={() => setPicker("loch")}
        />
      </div>

      {/* FE15 (#1264) — sesja drużynowa (MP): utwórz lobby (F-13) */}
      <button
        onClick={launchMp}
        disabled={busy}
        className="mb-6 flex items-center gap-3 rounded-lg border border-line-ember bg-[rgba(255,122,61,.06)] px-4 py-3 text-left transition-colors hover:bg-[rgba(255,122,61,.1)] disabled:opacity-50"
      >
        <UsersThree weight="fill" className="shrink-0 text-ember" size={22} />
        <span className="min-w-0 flex-1">
          <span className="block font-serif text-body font-semibold text-text">
            Drużyna (multiplayer)
          </span>
          <span className="block font-ui text-micro text-text-3">
            Utwórz lobby, zaproś kompanów, grajcie rundami
          </span>
        </span>
        <Play weight="fill" className="shrink-0 text-ember-glow" size={18} />
      </button>

      {/* Aktywne kampanie */}
      <SectionHeader count={active.length}>Aktywne kampanie</SectionHeader>
      {isLoading && <Loading />}
      {isError && <LoadError />}
      {!isLoading && active.length === 0 && (
        <p className="mb-6 rounded-lg border border-dashed border-line px-4 py-6 text-center font-ui text-label text-text-3">
          Brak aktywnych kampanii — rozpocznij przygodę powyżej.
        </p>
      )}
      <div className="mb-6 flex flex-col gap-2.5">
        {active.map((c) => (
          <ActiveCampaignCard
            key={c.id}
            campaign={c}
            userId={user?.id}
            onPlay={() =>
              c.mode === "multiplayer"
                ? navigate(`/druzyna/${c.id}`)
                : enterGame(c.id)
            }
            onDelete={() => setToDelete(c)}
          />
        ))}
      </div>

      {/* Historia — read-only */}
      {history.length > 0 && (
        <>
          <SectionHeader note="zakończone · tylko do odczytu">Historia</SectionHeader>
          <div className="flex flex-col gap-2">
            {history.map((c) => (
              <HistoryRow
                key={c.id}
                campaign={c}
                onOpen={() => navigate(`/bohaterowie/${heroId}/historia/${c.id}`)}
              />
            ))}
          </div>
        </>
      )}

      {/* F-10 — kreator nazwy (Nowa) */}
      <NowaDialog
        open={picker === "nowa"}
        defaultName={`Przygoda ${hero?.name ?? "Bohatera"}`}
        busy={busy}
        onClose={() => !busy && setPicker(null)}
        onSubmit={(name) => launch("solo", name.trim() || `Przygoda ${hero?.name ?? "Bohatera"}`)}
      />

      {/* Gotowa — picker szablonów */}
      <GotowaPicker
        open={picker === "gotowa"}
        busy={busy}
        onClose={() => !busy && setPicker(null)}
        onPick={(t) =>
          launch("pre_built", t.title || `Przygoda ${hero?.name ?? "Bohatera"}`, t.id)
        }
      />

      {/* Loch — picker lochów */}
      <LochPicker
        open={picker === "loch"}
        busy={busy}
        heroId={heroId}
        onClose={() => !busy && setPicker(null)}
        onPick={(d) => launch("dungeon", `Ekspedycja: ${d.label || d.name || d.key}`, undefined, d.key)}
      />

      {/* Potwierdzenie usunięcia */}
      <Dialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Usunąć kampanię?</DialogTitle>
            <DialogDescription>
              „{toDelete?.title}" zostanie trwale usunięta. Bohater wróci do spoczynku.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setToDelete(null)}>
              Anuluj
            </Button>
            <Button variant="danger" onClick={confirmDelete}>
              <Trash size={16} /> Usuń
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Podkomponenty ──────────────────────────────────────────────────────────

function SectionHeader({
  children,
  count,
  note,
}: {
  children: React.ReactNode;
  count?: number;
  note?: string;
}) {
  return (
    <div className="mb-3 mt-1 flex items-center gap-2.5 px-0.5 font-ui text-[11px] font-bold uppercase tracking-[0.2em] text-ember">
      <span>{children}</span>
      {count != null && (
        <span className="font-medium normal-case tracking-[0.04em] text-text-3">
          {count}
        </span>
      )}
      {note && (
        <span className="font-medium normal-case tracking-[0.04em] text-text-3">
          {note}
        </span>
      )}
      <span className="h-px flex-1 bg-line-soft" />
    </div>
  );
}

function TypeCard({
  icon,
  title,
  sub,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  sub: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-1.5 rounded-lg border border-line bg-surface p-4 text-center transition-colors hover:border-line-ember"
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-md border border-line-ember bg-ember/[0.08] text-[22px] text-ember-glow">
        {icon}
      </span>
      <span className="font-ui text-label font-semibold text-text">{title}</span>
      <span className="font-ui text-[10.5px] leading-tight text-text-3">{sub}</span>
    </button>
  );
}

function ActiveCampaignCard({
  campaign,
  userId,
  onPlay,
  onDelete,
}: {
  campaign: Campaign;
  userId?: number;
  onPlay: () => void;
  onDelete: () => void;
}) {
  const { data: detail } = useCampaignDetail(userId ? campaign.id : undefined);
  const { pct, actLabel } = deriveProgress(detail?.gm_plan_json);

  const generic = GENERIC_TITLE.test(campaign.title || "");
  const brewing = !campaign.plan_ready && generic;
  const title = brewing ? "Mglista przygoda…" : campaign.title || "Kampania";
  const sub = brewing
    ? "GM zaplata wątki — wróć za chwilę."
    : [actLabel, campaign.description].filter(Boolean).join(" · ") ||
      campaign.system_id ||
      "Fantasy";

  return (
    <div className="relative overflow-hidden rounded-lg border border-line bg-mech-card p-4">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(50%_90%_at_100%_0%,rgba(255,122,61,.07),transparent_60%)]" />
      <div className="relative z-10 flex items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-line-ember bg-ember/[0.08] text-[21px] text-ember-glow">
          {brewing ? <CircleNotch className="animate-spin" /> : <PawPrint weight="fill" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-serif text-title font-semibold text-text">
              {title}
            </span>
            {campaign.is_tutorial && (
              <span className="shrink-0 rounded-pill border border-line-ember bg-ember/[0.08] px-2 py-0.5 font-ui text-[9.5px] font-bold uppercase tracking-wide text-ember-glow">
                Wprowadzenie
              </span>
            )}
          </div>
          <div className="mt-0.5 truncate font-ui text-micro text-text-2">{sub}</div>
        </div>
        <button
          onClick={onDelete}
          aria-label="Usuń kampanię"
          className="shrink-0 text-text-3 transition-colors hover:text-danger"
        >
          <Trash size={18} />
        </button>
      </div>

      {pct != null && (
        <div className="relative z-10 mt-3">
          <div className="mb-1.5 flex justify-between font-ui text-micro text-text-3">
            <span>Postęp fabuły</span>
            <span>{pct}%</span>
          </div>
          <ProgressBar kind="xp" value={pct} max={100} />
        </div>
      )}

      <div className="relative z-10 mt-3 flex items-center justify-end gap-3">
        <Button size="sm" onClick={onPlay}>
          <Play weight="fill" size={15} /> Graj dalej
        </Button>
      </div>
    </div>
  );
}

function HistoryRow({
  campaign,
  onOpen,
}: {
  campaign: Campaign;
  onOpen: () => void;
}) {
  const won = campaign.status === "completed";
  return (
    <button
      onClick={onOpen}
      title="Historia — tylko do odczytu"
      className="flex items-center gap-3 rounded-md border border-line-soft bg-surface px-3.5 py-3 text-left opacity-90 transition-all hover:border-line hover:opacity-100"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-3">
        {won ? <Crown weight="fill" size={16} /> : <Skull weight="fill" size={16} />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate font-ui text-label font-semibold text-text-2">
          {campaign.title || "Zamknięta kampania"}
        </div>
        <div className="truncate font-ui text-micro text-text-3">
          {campaign.description || campaign.system_id || "Fantasy"}
        </div>
      </div>
      <span
        className={cn(
          "shrink-0 rounded-pill border px-2.5 py-1 font-ui text-[9.5px] font-bold uppercase tracking-wide",
          won
            ? "border-gold/35 bg-gold/[0.08] text-gold"
            : "border-danger/35 bg-danger/[0.07] text-danger",
        )}
      >
        {won ? "Zwycięstwo" : "Zamknięta"}
      </span>
    </button>
  );
}

function NowaDialog({
  open,
  defaultName,
  busy,
  onClose,
  onSubmit,
}: {
  open: boolean;
  defaultName: string;
  busy: boolean;
  onClose: () => void;
  onSubmit: (name: string) => void;
}) {
  const [name, setName] = useState("");
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Nowa kampania</DialogTitle>
          <DialogDescription>
            Nadaj roboczą nazwę — Mistrz Gry może ją później dopracować.
          </DialogDescription>
        </DialogHeader>
        <Input
          autoFocus
          placeholder={defaultName}
          value={name}
          maxLength={60}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !busy && onSubmit(name || defaultName)}
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Anuluj
          </Button>
          <Button onClick={() => onSubmit(name || defaultName)} disabled={busy}>
            {busy ? <CircleNotch className="animate-spin" size={16} /> : <Play weight="fill" size={15} />}
            Rozpocznij
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function GotowaPicker({
  open,
  busy,
  onClose,
  onPick,
}: {
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onPick: (t: CampaignTemplate) => void;
}) {
  const { data: templates, isLoading } = useCampaignTemplates();
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Gotowa przygoda</DialogTitle>
          <DialogDescription>Scenariusze zbudowane w Kuźni.</DialogDescription>
        </DialogHeader>
        {isLoading && <Loading />}
        {!isLoading && (templates ?? []).length === 0 && (
          <p className="py-6 text-center font-ui text-label text-text-3">
            Brak opublikowanych gotowych kampanii.
          </p>
        )}
        <div className="flex flex-col gap-2.5">
          {(templates ?? []).map((t) => {
            const diff = t.difficulty_rating || 2;
            return (
              <button
                key={t.id}
                disabled={busy}
                onClick={() => onPick(t)}
                className="rounded-md border border-line-ember/60 bg-bg p-3.5 text-left transition-colors hover:border-line-ember disabled:opacity-50"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-serif text-body font-semibold text-text">
                    {t.title || "Kampania"}
                  </span>
                  <span className="flex shrink-0 items-center gap-0.5 text-gold">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star key={i} weight={i < diff ? "fill" : "regular"} size={11} />
                    ))}
                  </span>
                </div>
                <p className="mt-1 font-ui text-micro text-text-2">
                  {t.description || "Brak opisu."}
                </p>
                {(t.atmosphere || t.play_count) && (
                  <p className="mt-1 font-ui text-[10.5px] text-text-3">
                    {t.atmosphere}
                    {t.play_count ? ` · ${t.play_count}× zagrane` : ""}
                  </p>
                )}
              </button>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function LochPicker({
  open,
  busy,
  heroId,
  onClose,
  onPick,
}: {
  open: boolean;
  busy: boolean;
  heroId: number;
  onClose: () => void;
  onPick: (d: Dungeon) => void;
}) {
  const navigate = useNavigate();
  const { data: dungeons, isLoading } = useDungeons(open ? heroId : undefined);
  // E22/F-42: aktywny (niedokończony) bieg → modal wznowienia zamiast listy.
  const activeRunQ = useActiveDungeonRun(heroId, open);
  const activeRun = activeRunQ.data?.active_run ?? null;
  const runCampaignId = activeRun?.campaign_id;
  const exit = useDungeonExit(runCampaignId);
  const del = useDeleteDungeonCampaign();
  const [resuming, setResuming] = useState(false);

  async function abandonActive() {
    if (!runCampaignId) return;
    setResuming(true);
    try {
      try {
        await exit.mutateAsync(heroId);
      } catch {
        /* i tak sprzątamy */
      }
      try {
        await del.mutateAsync(runCampaignId);
      } catch {
        /* noop */
      }
      await activeRunQ.refetch();
    } finally {
      setResuming(false);
    }
  }

  // Wznowienie ma priorytet — dopóki jest aktywny bieg, pokaż tylko modal.
  if (open && activeRun && runCampaignId) {
    return (
      <ResumeModal
        run={activeRun}
        busy={resuming}
        onContinue={() => {
          onClose();
          navigate(`/gra/${runCampaignId}`);
        }}
        onAbandon={abandonActive}
      />
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Loch</DialogTitle>
          <DialogDescription>Farmienie i łup — wybierz wyprawę.</DialogDescription>
        </DialogHeader>
        {isLoading && <Loading />}
        {!isLoading && (dungeons ?? []).length === 0 && (
          <p className="py-6 text-center font-ui text-label text-text-3">
            Brak dostępnych lochów.
          </p>
        )}
        <div className="flex flex-col gap-2.5">
          {(dungeons ?? []).map((d) => {
            const locked = d.cooldown?.ready === false;
            return (
              <button
                key={d.key}
                disabled={busy || locked}
                onClick={() => onPick(d)}
                className="flex items-center gap-3 rounded-md border border-line-ember/60 bg-bg p-3.5 text-left transition-colors hover:border-line-ember disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line-ember bg-ember/[0.08] text-ember-glow">
                  {locked ? <Lock size={16} /> : <Skull weight="fill" size={16} />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-serif text-body font-semibold text-text">
                    {d.label || d.name || d.key}
                  </div>
                  <div className="truncate font-ui text-micro text-text-3">
                    {locked
                      ? `Odnowa: ${Math.ceil(d.cooldown?.hours_remaining ?? 0)} h`
                      : d.atmosphere || `Poziom min. ${d.min_level ?? 1}`}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Loading() {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-text-3">
      <CircleNotch className="animate-spin" size={20} />
      <span className="font-ui text-label">Wczytywanie…</span>
    </div>
  );
}

function LoadError() {
  return (
    <div className="mb-6 flex items-center gap-2 rounded-lg border border-line-danger bg-danger/10 px-4 py-3 text-danger-glow">
      <Warning size={20} />
      <span className="font-ui text-body">Nie udało się wczytać kampanii.</span>
    </div>
  );
}
