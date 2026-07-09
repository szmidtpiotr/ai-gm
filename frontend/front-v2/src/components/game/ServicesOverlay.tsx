// #1292 — modal Usług (nocleg/jedzenie/naprawa/uzdrowienie/stajnia/przewodnik/
// posłaniec). Otwierany deterministycznie (chip "Usługi" albo skrót tekstowy
// przechwycony przed LLM) — zakup jest mechaniczny, narrator w ogóle go nie widzi.
// Layout mirror ShopOverlay.tsx (lista zamiast siatki — brak sprzedaży/zakładek).
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Bed, CircleNotch, Coins, Compass, Envelope, Hammer, Heart, House, X } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";
import { useServicesAtLocation, useBuyService } from "@/hooks/useServices";
import type { ServiceItem } from "@/lib/services";
import { useToast } from "@/components/ui/toast";

export function ServicesOverlay() {
  const locationKey = useAppStore((s) => s.services);
  const closeServices = useAppStore((s) => s.closeServices);
  const characterId = useAppStore((s) => s.currentHeroId) ?? undefined;

  const open = !!locationKey;
  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && closeServices()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-fade-in" />
        <DialogPrimitive.Content
          className="fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[calc(100%-1.5rem)] max-w-[600px] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-line bg-bg shadow-modal animate-fade-in"
          aria-describedby={undefined}
        >
          {locationKey && characterId ? (
            <ServicesBody locationKey={locationKey} characterId={characterId} onClose={closeServices} />
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

function ServicesBody({
  locationKey,
  characterId,
  onClose,
}: {
  locationKey: string;
  characterId: number;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const services = useServicesAtLocation(locationKey, characterId);
  const buy = useBuyService(locationKey, characterId);

  const data = services.data;
  const gold = data?.character_gold ?? 0;

  function onBuy(it: ServiceItem) {
    buy.mutate(
      { serviceKey: it.key, characterId },
      {
        onSuccess: (r) => toast(`Kupiono: ${it.label} za ${r.data.paid_gp} zł`, "success"),
        onError: (e) => toast(e instanceof Error ? e.message : "Nie stać Cię na tę usługę", "danger"),
      },
    );
  }

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line bg-gradient-to-r from-[rgba(255,122,61,0.08)] to-surface px-4 py-3.5">
        <div className="flex h-12 w-12 flex-none items-center justify-center rounded-xl border border-line-ember bg-[radial-gradient(circle_at_40%_35%,rgba(255,122,61,0.25),#241c13)] text-ember-glow">
          <House weight="fill" size={22} />
        </div>
        <DialogPrimitive.Title className="min-w-0 flex-1 truncate font-serif text-title font-semibold text-text">
          Usługi
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
        {services.isLoading ? (
          <Loading />
        ) : services.isError || !data ? (
          <Empty>Nie udało się wczytać usług.</Empty>
        ) : (
          <ServiceList items={data.items} gold={gold} busy={buy.isPending} onBuy={onBuy} />
        )}
      </div>
    </>
  );
}

function ServiceList({
  items,
  gold,
  busy,
  onBuy,
}: {
  items: ServiceItem[];
  gold: number;
  busy: boolean;
  onBuy: (it: ServiceItem) => void;
}) {
  if (!items.length) return <Empty>Nic tu na Ciebie nie czeka.</Empty>;
  return (
    <div className="flex flex-col gap-2">
      {items.map((it) => {
        const Ico = serviceIcon(it.key);
        const afford = gold >= it.cost_gp;
        return (
          <div key={it.key} className="flex items-center gap-3 rounded-xl border border-line bg-mech-card p-3">
            <span className="flex h-10 w-10 flex-none items-center justify-center rounded-lg border border-line bg-[rgba(255,122,61,0.08)] text-ember-glow">
              <Ico weight="fill" size={20} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-label font-semibold text-text">{it.label}</div>
              {it.description && (
                <div className="mt-0.5 truncate font-mono text-[11px] text-text-3">{it.description}</div>
              )}
            </div>
            <div className="flex flex-none items-center gap-1.5 font-mono text-label font-semibold text-gold">
              <Coins weight="fill" size={14} />
              {it.cost_gp}
            </div>
            <button
              type="button"
              disabled={!afford || busy}
              onClick={() => onBuy(it)}
              className={cn(
                "flex-none rounded-md px-3.5 py-2 font-ui text-micro font-semibold transition-colors",
                afford
                  ? "bg-gradient-to-br from-[#d1602c] to-ember text-white hover:brightness-110"
                  : "cursor-not-allowed border border-line bg-bg text-text-3",
                busy && "opacity-60",
              )}
            >
              {afford ? "Kup" : "Za mało"}
            </button>
          </div>
        );
      })}
    </div>
  );
}

function Loading() {
  return (
    <div className="flex items-center justify-center gap-2 py-14 text-text-3">
      <CircleNotch className="animate-spin" size={20} />
      <span className="font-ui text-body">Wczytywanie usług…</span>
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

function serviceIcon(key: string) {
  if (key.startsWith("inn_")) return Bed;
  if (key.startsWith("tavern_")) return House;
  if (key === "blacksmith_repair") return Hammer;
  if (key.startsWith("healer_")) return Heart;
  if (key === "stable_night") return House;
  if (key === "guide_day") return Compass;
  if (key === "messenger") return Envelope;
  return House;
}
