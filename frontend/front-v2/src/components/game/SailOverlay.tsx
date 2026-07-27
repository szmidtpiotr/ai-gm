// WL-4 (#1504) — modal Rejsów. Otwierany chipem „Wypłyń" w porcie (OPEN_SAIL:).
// Flow: lista tras (koszt złota / czas / ryzyko) → potwierdzenie → wynik rejsu
// (dotarłeś + ewentualne zdarzenie: sztorm / rafa / piraci). Mechaniczne, omija LLM.
import { useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Anchor,
  CheckCircle,
  CircleNotch,
  Clock,
  Coins,
  Compass,
  Lightning,
  Skull,
  WarningCircle,
  Waves,
  X,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";
import { useSeaRoutes, useSetSail, type SeaRoute, type VoyageResult } from "@/hooks/useSeaVoyage";
import { useToast } from "@/components/ui/toast";

type Step = "browse" | "done";

export function SailOverlay() {
  const portKey = useAppStore((s) => s.sail);
  const closeSail = useAppStore((s) => s.closeSail);
  const characterId = useAppStore((s) => s.currentHeroId) ?? undefined;
  const campaignId = useAppStore((s) => s.currentCampaignId) ?? undefined;

  const open = !!portKey;

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && closeSail()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-fade-in" />
        <DialogPrimitive.Content
          className="fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[calc(100%-1.5rem)] max-w-[600px] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-line bg-bg shadow-modal animate-fade-in"
          aria-describedby={undefined}
        >
          {portKey && characterId && campaignId ? (
            <SailBody campaignId={campaignId} characterId={characterId} onClose={closeSail} />
          ) : (
            <div className="flex items-center justify-center gap-2 p-10 text-text-3">
              <CircleNotch className="animate-spin" size={20} />
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function SailBody({
  campaignId,
  characterId,
  onClose,
}: {
  campaignId: number;
  characterId: number;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const routes = useSeaRoutes(campaignId, characterId);
  const sail = useSetSail(campaignId, characterId);

  const [step, setStep] = useState<Step>("browse");
  const [result, setResult] = useState<VoyageResult | null>(null);

  const data = routes.data;
  const gold = result?.gold ?? data?.gold ?? 0;

  function onSail(route: SeaRoute) {
    sail.mutate(
      { routeKey: route.route_key },
      {
        onSuccess: (r) => {
          setResult(r);
          setStep("done");
        },
        onError: (e) => toast(e instanceof Error ? e.message : "Rejs się nie udał", "danger"),
      },
    );
  }

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line bg-gradient-to-r from-[rgba(61,140,255,0.10)] to-surface px-4 py-3.5">
        <div className="flex h-12 w-12 flex-none items-center justify-center rounded-xl border border-line bg-[radial-gradient(circle_at_40%_35%,rgba(61,140,255,0.28),#101a24)] text-[#7db8e8]">
          <Anchor weight="fill" size={22} />
        </div>
        <DialogPrimitive.Title className="min-w-0 flex-1 truncate font-serif text-title font-semibold text-text">
          Rejs
          {data?.port_label && (
            <span className="ml-2 font-ui text-micro font-normal text-text-3">— {data.port_label}</span>
          )}
        </DialogPrimitive.Title>
        <div className="flex flex-none items-center gap-1.5 rounded-pill border border-line bg-bg px-3 py-1.5 font-mono text-label font-semibold text-gold">
          <Coins weight="fill" size={14} /> {gold}
        </div>
        <button
          onClick={onClose}
          aria-label="Zamknij"
          className="flex h-9 w-9 flex-none items-center justify-center rounded-md border border-line bg-bg text-text-2 hover:border-line-ember hover:text-ember-glow"
        >
          <X size={16} />
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3.5 [scrollbar-width:thin]">
        {routes.isLoading ? (
          <Loading />
        ) : routes.isError || !data ? (
          <Empty>Nie udało się wczytać tras rejsu.</Empty>
        ) : step === "done" ? (
          <DoneView result={result} />
        ) : !data.is_port ? (
          <Empty>Tu nie ma portu — rejs możliwy tylko z nabrzeża.</Empty>
        ) : !data.routes.length ? (
          <Empty>Stąd nigdzie nie wypłyniesz.</Empty>
        ) : (
          <>
            {data.is_night && (
              <RiskBanner>
                Noc na morzu — ryzyko rejsu rośnie (sztorm, rafy, piraci).
              </RiskBanner>
            )}
            {data.has_map && (
              <div className="mb-3 flex items-center gap-2 rounded-md border border-line-soft bg-[rgba(61,140,255,0.06)] px-3 py-2 font-ui text-micro text-[#7db8e8]">
                <Compass weight="fill" size={15} /> Masz Mapę Smolnego — mniejsze ryzyko rafy, dostępne skróty.
              </div>
            )}
            <div className="flex flex-col gap-2">
              {data.routes.map((r) => (
                <RouteRow
                  key={r.route_key}
                  route={r}
                  risk={data.risk}
                  pending={sail.isPending}
                  onSail={() => onSail(r)}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {step === "done" && (
        <FooterBar>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto rounded-md bg-gradient-to-br from-[#2c72d1] to-[#3d8cff] px-4 py-2 font-ui text-micro font-semibold text-white hover:brightness-110"
          >
            Zejdź na ląd
          </button>
        </FooterBar>
      )}
    </>
  );
}

function RouteRow({
  route,
  risk,
  pending,
  onSail,
}: {
  route: SeaRoute;
  risk?: string;
  pending: boolean;
  onSail: () => void;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-xl border p-3",
        route.shortcut ? "border-[#3d8cff]/50 bg-[rgba(61,140,255,0.06)]" : "border-line bg-mech-card",
      )}
    >
      <span className="flex h-10 w-10 flex-none items-center justify-center rounded-lg border border-line bg-[rgba(61,140,255,0.08)] text-[#7db8e8]">
        <Waves weight="fill" size={20} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-label font-semibold text-text">
          {route.dest_label}
          {route.shortcut && (
            <span className="ml-1.5 rounded-pill bg-[#3d8cff]/20 px-1.5 py-0.5 align-middle font-ui text-[10px] font-semibold text-[#7db8e8]">
              skrót
            </span>
          )}
        </span>
        <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-[11px] text-text-3">
          <span className="flex items-center gap-1 text-gold">
            <Coins weight="fill" size={12} /> {route.fare_gp} zł
          </span>
          <span className="flex items-center gap-1">
            <Clock size={12} /> {route.hours} h
          </span>
          {risk && (
            <span className="flex items-center gap-1">
              <WarningCircle size={12} /> ryzyko {risk}
            </span>
          )}
        </span>
      </span>
      <button
        type="button"
        disabled={pending || !route.affordable}
        onClick={onSail}
        className={cn(
          "flex-none rounded-md px-3.5 py-2 font-ui text-micro font-semibold transition-colors",
          route.affordable
            ? "bg-gradient-to-br from-[#2c72d1] to-[#3d8cff] text-white hover:brightness-110"
            : "cursor-not-allowed border border-line bg-bg text-text-3",
          pending && "opacity-60",
        )}
      >
        {!route.affordable ? "Za mało złota" : "Wypłyń"}
      </button>
    </div>
  );
}

function DoneView({ result }: { result: VoyageResult | null }) {
  if (!result) return null;
  const ev = result.event;
  const EvIcon = ev?.kind === "sztorm" ? Lightning : ev?.kind === "rafa" ? Skull : ev?.kind === "piraci" ? WarningCircle : null;
  return (
    <div className="flex flex-col items-center gap-3 py-6 text-center">
      <CheckCircle weight="fill" size={40} className="text-success" />
      <p className="font-serif text-body text-text">
        Dobiłeś do brzegu: <span className="font-semibold">{result.dest_label}</span>
      </p>
      <p className="font-mono text-label text-text-3">
        Rejs zajął {result.hours} h · zapłacono <span className="text-gold">{result.fare_gp} zł</span> · zostało {result.gold} zł
      </p>
      {ev && (
        <div className="mt-1 flex items-start gap-2 rounded-md border border-line-ember bg-[rgba(255,122,61,0.08)] px-3 py-2.5 text-left">
          {EvIcon && <EvIcon weight="fill" size={18} className="mt-0.5 flex-none text-ember-glow" />}
          <span className="font-serif text-body text-text-2">
            <span className="font-semibold text-ember-glow">{ev.label}. </span>
            {ev.narrative}
          </span>
        </div>
      )}
    </div>
  );
}

function RiskBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-2 rounded-md border border-line-ember bg-[rgba(255,122,61,0.08)] px-3 py-2 font-ui text-micro text-ember-glow">
      <WarningCircle weight="fill" size={15} /> {children}
    </div>
  );
}

function FooterBar({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 border-t border-line bg-surface px-4 py-3">{children}</div>
  );
}

function Loading() {
  return (
    <div className="flex items-center justify-center gap-2 py-14 text-text-3">
      <CircleNotch className="animate-spin" size={20} />
      <span className="font-ui text-body">Sprawdzam trasy rejsu…</span>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-line-soft bg-surface px-4 py-8 text-center font-serif text-body text-text-3">
      {children}
    </p>
  );
}
