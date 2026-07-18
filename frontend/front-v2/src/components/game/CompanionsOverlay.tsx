// #1192 FAZA TW — modal rekrutacji towarzyszy i wierzchowców w osadzie.
// Otwierany chipem „Towarzysze" (OPEN_COMPANIONS:{loc}) — najem/kupno jest
// mechaniczny (bez narratora), mirror ServicesOverlay.
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { CircleNotch, Coins, Dog, Horse, Sword, X } from "@phosphor-icons/react";
import { useAppStore } from "@/store/appStore";
import {
  useLocationCompanions,
  useHireCompanion,
  useBuyCompanion,
} from "@/hooks/useCompanions";
import type { RecruitableCompanion } from "@/lib/companions";
import { useToast } from "@/components/ui/toast";

export function CompanionsOverlay() {
  const locationKey = useAppStore((s) => s.companions);
  const close = useAppStore((s) => s.closeCompanions);
  const characterId = useAppStore((s) => s.currentHeroId) ?? undefined;
  const open = !!locationKey;

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && close()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-fade-in" />
        <DialogPrimitive.Content
          className="fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[calc(100%-1.5rem)] max-w-[600px] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-line bg-bg shadow-modal animate-fade-in"
          aria-describedby={undefined}
        >
          {locationKey && characterId ? (
            <Body locationKey={locationKey} characterId={characterId} onClose={close} />
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

function typeIcon(t: string) {
  return t === "mount" ? Horse : t === "animal" ? Dog : Sword;
}

function Body({
  locationKey,
  characterId,
  onClose,
}: {
  locationKey: string;
  characterId: number;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const q = useLocationCompanions(locationKey, characterId);
  const hire = useHireCompanion(characterId);
  const buy = useBuyCompanion(characterId);

  const data = q.data;
  const items = data?.items ?? [];
  const gold = data?.character_gold ?? 0;
  const busy = hire.isPending || buy.isPending;

  function onAcquire(c: RecruitableCompanion, mode: "hire" | "buy") {
    const m = mode === "buy" ? buy : hire;
    m.mutate(
      { companionKey: c.key },
      {
        onSuccess: () => toast(`${c.label} dołącza do ciebie.`, "success"),
        onError: (e: unknown) => {
          const msg = (e as { message?: string })?.message || "";
          toast(
            /409/.test(msg)
              ? "Masz już towarzysza tego rodzaju."
              : /402/.test(msg)
                ? "Za mało złota."
                : "Nie udało się zatrudnić.",
            "danger",
          );
        },
      },
    );
  }

  return (
    <>
      <div className="flex items-center justify-between border-b border-line px-5 py-4">
        <div className="flex items-center gap-2">
          <Horse weight="duotone" size={22} className="text-ember-glow" />
          <span className="font-serif text-title font-semibold text-text">Towarzysze</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 font-ui text-body text-amber-300">
            <Coins size={16} weight="fill" /> {gold}
          </span>
          <button onClick={onClose} className="text-text-3 hover:text-text">
            <X size={20} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        {q.isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-text-3">
            <CircleNotch className="animate-spin" size={18} /> Ładowanie…
          </div>
        ) : items.length === 0 ? (
          <p className="py-10 text-center font-serif text-prose text-text-3">
            Nikogo tu nie najmiesz.
          </p>
        ) : (
          <div className="space-y-2.5">
            {items.map((c) => {
              const Icon = typeIcon(c.type);
              const canHire = c.daily_cost > 0 && c.daily_cost <= gold;
              const canBuy = c.buy_cost != null && c.buy_cost <= gold;
              return (
                <div key={c.key} className="rounded-lg border border-line-soft bg-surface p-3">
                  <div className="flex items-start gap-2.5">
                    <Icon size={22} weight="duotone" className="mt-0.5 shrink-0 text-text-2" />
                    <div className="min-w-0 flex-1">
                      <div className="font-serif text-sm font-semibold text-text-1">{c.label}</div>
                      {c.description && (
                        <p className="mt-0.5 font-serif text-micro leading-snug text-text-3">
                          {c.description}
                        </p>
                      )}
                    </div>
                    <span className="shrink-0 font-ui text-micro text-text-3">{c.hp_base} HP</span>
                  </div>
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    {c.daily_cost > 0 && (
                      <button
                        disabled={busy || !canHire}
                        onClick={() => onAcquire(c, "hire")}
                        className="flex-1 rounded-md border border-line-ember bg-ember/[0.06] px-3 py-2 font-ui text-micro font-semibold text-ember-glow hover:bg-ember/[0.14] disabled:opacity-40"
                      >
                        Najmij · {c.daily_cost} zł/dzień
                      </button>
                    )}
                    {c.buy_cost != null && (
                      <button
                        disabled={busy || !canBuy}
                        onClick={() => onAcquire(c, "buy")}
                        className="flex-1 rounded-md border border-line-ember bg-ember/[0.06] px-3 py-2 font-ui text-micro font-semibold text-ember-glow hover:bg-ember/[0.14] disabled:opacity-40"
                      >
                        Kup · {c.buy_cost} zł
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
