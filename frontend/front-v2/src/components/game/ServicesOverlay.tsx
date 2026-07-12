// #1292 — modal Usług (nocleg/jedzenie/naprawa/uzdrowienie/stajnia/przewodnik/
// posłaniec). Otwierany deterministycznie (chip "Usługi" albo skrót tekstowy
// przechwycony przed LLM) — zakup jest mechaniczny, narrator go nie widzi.
// Flow: wybór (multi-select) → podsumowanie/potwierdzenie → gotowe. Po zamknięciu
// modala Game.tsx wysyła ukrytą turę proszącą narratora o krótki opis odbioru
// (zakup już opłacony — patrz lib/services.ts buildServicesReceiptText).
import { useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Bed,
  CheckCircle,
  CircleNotch,
  Coins,
  Compass,
  Envelope,
  Hammer,
  Heart,
  House,
  X,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";
import { useServicesAtLocation, useBuyServicesBatch } from "@/hooks/useServices";
import { buildServicesReceiptText, type ServiceItem, type ServicesBatchResult } from "@/lib/services";
import { useToast } from "@/components/ui/toast";

type Step = "browse" | "confirm" | "done";

export function ServicesOverlay() {
  const locationKey = useAppStore((s) => s.services);
  const closeServices = useAppStore((s) => s.closeServices);
  const setServicesReceiptPending = useAppStore((s) => s.setServicesReceiptPending);
  const characterId = useAppStore((s) => s.currentHeroId) ?? undefined;

  const open = !!locationKey;

  function handleClose(receipt?: ServicesBatchResult) {
    if (receipt && receipt.items.length) {
      setServicesReceiptPending(buildServicesReceiptText(receipt.items));
    }
    closeServices();
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-fade-in" />
        <DialogPrimitive.Content
          className="fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[calc(100%-1.5rem)] max-w-[600px] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-line bg-bg shadow-modal animate-fade-in"
          aria-describedby={undefined}
        >
          {locationKey && characterId ? (
            <ServicesBody locationKey={locationKey} characterId={characterId} onClose={handleClose} />
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
  onClose: (receipt?: ServicesBatchResult) => void;
}) {
  const { toast } = useToast();
  const services = useServicesAtLocation(locationKey, characterId);
  const buyBatch = useBuyServicesBatch(locationKey, characterId);

  const [step, setStep] = useState<Step>("browse");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<ServicesBatchResult | null>(null);

  const data = services.data;
  const gold = result?.gold_gp ?? data?.character_gold ?? 0;
  const items = data?.items ?? [];
  const selectedItems = items.filter((it) => selected.has(it.key));
  const total = selectedItems.reduce((sum, it) => sum + it.cost_gp, 0);
  const canAfford = total <= (data?.character_gold ?? 0);

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function onConfirm() {
    buyBatch.mutate(
      { serviceKeys: [...selected], characterId },
      {
        onSuccess: (r) => {
          setResult(r.data);
          setStep("done");
        },
        onError: (e) => toast(e instanceof Error ? e.message : "Nie stać Cię na wybrane usługi", "danger"),
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
          {step === "confirm" && <span className="ml-2 font-ui text-micro font-normal text-text-3">— podsumowanie</span>}
        </DialogPrimitive.Title>
        <div className="flex flex-none items-center gap-1.5 rounded-pill border border-line bg-bg px-3 py-1.5 font-mono text-label font-semibold text-gold">
          <Coins weight="fill" size={14} /> {gold}
        </div>
        <button
          onClick={() => onClose(step === "done" ? result ?? undefined : undefined)}
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
        ) : step === "browse" ? (
          <BrowseList items={items} selected={selected} onToggle={toggle} />
        ) : step === "confirm" ? (
          <ConfirmList items={selectedItems} />
        ) : (
          <DoneView result={result} />
        )}
      </div>

      {step === "browse" && (
        <FooterBar>
          <div className="font-mono text-label text-text-2">
            Wybrano {selectedItems.length} · <span className="font-semibold text-gold">{total} zł</span>
          </div>
          <button
            type="button"
            disabled={!selectedItems.length || !canAfford}
            onClick={() => setStep("confirm")}
            className={cn(
              "rounded-md px-4 py-2 font-ui text-micro font-semibold transition-colors",
              selectedItems.length && canAfford
                ? "bg-gradient-to-br from-[#d1602c] to-ember text-white hover:brightness-110"
                : "cursor-not-allowed border border-line bg-bg text-text-3",
            )}
          >
            {!selectedItems.length ? "Wybierz usługi" : !canAfford ? "Za mało złota" : "Dalej"}
          </button>
        </FooterBar>
      )}

      {step === "confirm" && (
        <FooterBar>
          <button
            type="button"
            onClick={() => setStep("browse")}
            className="rounded-md border border-line px-3.5 py-2 font-ui text-micro font-semibold text-text-2 hover:border-line-ember hover:text-ember-glow"
          >
            Wróć
          </button>
          <button
            type="button"
            disabled={buyBatch.isPending}
            onClick={onConfirm}
            className={cn(
              "flex-1 rounded-md px-4 py-2 font-ui text-micro font-semibold text-white transition-colors",
              "bg-gradient-to-br from-[#d1602c] to-ember hover:brightness-110",
              buyBatch.isPending && "opacity-60",
            )}
          >
            Potwierdź zakup — {total} zł
          </button>
        </FooterBar>
      )}

      {step === "done" && (
        <FooterBar>
          <button
            type="button"
            onClick={() => onClose(result ?? undefined)}
            className="ml-auto rounded-md bg-gradient-to-br from-[#d1602c] to-ember px-4 py-2 font-ui text-micro font-semibold text-white hover:brightness-110"
          >
            Zamknij
          </button>
        </FooterBar>
      )}
    </>
  );
}

// ── Krok 1: wybór (checkboxy) ─────────────────────────────────────────────────
function BrowseList({
  items,
  selected,
  onToggle,
}: {
  items: ServiceItem[];
  selected: Set<string>;
  onToggle: (key: string) => void;
}) {
  if (!items.length) return <Empty>Nic tu na Ciebie nie czeka.</Empty>;
  return (
    <div className="flex flex-col gap-2">
      {items.map((it) => {
        const Ico = serviceIcon(it.key);
        const on = selected.has(it.key);
        return (
          <button
            key={it.key}
            type="button"
            onClick={() => onToggle(it.key)}
            className={cn(
              "flex items-center gap-3 rounded-xl border p-3 text-left transition-colors",
              on ? "border-line-ember bg-[rgba(255,122,61,0.08)]" : "border-line bg-mech-card hover:border-line-ember/60",
            )}
          >
            <span
              className={cn(
                "flex h-5 w-5 flex-none items-center justify-center rounded-md border",
                on ? "border-ember bg-ember text-white" : "border-line",
              )}
            >
              {on && <CheckCircle weight="fill" size={14} />}
            </span>
            <span className="flex h-10 w-10 flex-none items-center justify-center rounded-lg border border-line bg-[rgba(255,122,61,0.08)] text-ember-glow">
              <Ico weight="fill" size={20} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-label font-semibold text-text">{it.label}</span>
              {it.description && (
                <span className="mt-0.5 block truncate font-mono text-[11px] text-text-3">{it.description}</span>
              )}
            </span>
            <span className="flex flex-none items-center gap-1.5 font-mono text-label font-semibold text-gold">
              <Coins weight="fill" size={14} />
              {it.cost_gp}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ── Krok 2: podsumowanie ──────────────────────────────────────────────────────
function ConfirmList({ items }: { items: ServiceItem[] }) {
  const total = items.reduce((sum, it) => sum + it.cost_gp, 0);
  return (
    <div className="flex flex-col gap-2">
      <p className="mb-1 font-serif text-body text-text-2">Potwierdź zakup:</p>
      {items.map((it) => (
        <div key={it.key} className="flex items-center justify-between rounded-md border border-line bg-mech-card px-3 py-2">
          <span className="text-label text-text">{it.label}</span>
          <span className="font-mono text-label font-semibold text-gold">{it.cost_gp} zł</span>
        </div>
      ))}
      <div className="mt-1 flex items-center justify-between border-t border-line pt-2.5">
        <span className="font-ui text-label font-semibold text-text">Razem</span>
        <span className="font-mono text-title font-semibold text-gold">{total} zł</span>
      </div>
    </div>
  );
}

// ── Krok 3: gotowe ────────────────────────────────────────────────────────────
function DoneView({ result }: { result: ServicesBatchResult | null }) {
  if (!result) return null;
  return (
    <div className="flex flex-col items-center gap-3 py-6 text-center">
      <CheckCircle weight="fill" size={40} className="text-success" />
      <p className="font-serif text-body text-text">
        Zakupiono: {result.items.map((it) => it.label).join(", ")}
      </p>
      <p className="font-mono text-label text-text-3">
        Zapłacono <span className="font-semibold text-gold">{result.total_paid_gp} zł</span> — pozostało {result.gold_gp} zł
      </p>
    </div>
  );
}

function FooterBar({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 border-t border-line bg-surface px-4 py-3">
      {children}
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
