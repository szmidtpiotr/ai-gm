// F-77 (#1268) — bramka finału: karta w czacie + modal potwierdzenia + ekran
// zwycięstwa. finishFlow w store steruje etapem (idle → confirm → victory).
import { Flag, Scroll, CircleNotch, WarningCircle } from "@phosphor-icons/react";
import { useAppStore } from "@/store/appStore";
import { useFinishCampaign } from "@/hooks/useGameData";
import { useToast } from "@/components/ui/toast";
import { APIError } from "@/lib/api";
import { VictoryScreen } from "./outcomes/VictoryScreen";

// Karta na czacie „📜 Osiągnąłeś cel…" — pojawia się w logu, gdy bramka otwarta.
export function FinaleCard({ onFinish }: { onFinish: () => void }) {
  return (
    <div
      data-testid="finale-card"
      className="mx-auto my-3 max-w-[660px] rounded-lg border border-line-ember bg-gradient-to-br from-ember/[0.1] to-surface px-4 py-3.5"
    >
      <div className="flex items-start gap-3">
        <Scroll weight="fill" className="mt-0.5 shrink-0 text-ember-glow" size={22} />
        <div className="min-w-0 flex-1">
          <div className="font-serif text-body font-semibold text-text">Osiągnąłeś cel przygody</div>
          <p className="mt-1 font-serif text-prose leading-relaxed text-text-2">
            Możesz dokończyć swoje sprawy, a gdy będziesz gotów — zakończyć przygodę.
          </p>
          <button
            type="button"
            data-testid="finale-card-finish"
            onClick={onFinish}
            className="mt-2.5 inline-flex items-center gap-1.5 rounded-md border border-line-ember bg-ember/[0.08] px-3.5 py-1.5 font-ui text-label font-semibold text-ember-glow transition-colors hover:border-ember"
          >
            <Flag weight="fill" size={14} /> Zakończ przygodę
          </button>
        </div>
      </div>
    </div>
  );
}

// Modal potwierdzenia + ekran zwycięstwa (renderowany raz na ekranie gry).
export function FinaleFlow({
  campaignId,
  heroId,
  heroName,
  heroLevel,
  turnCount,
}: {
  campaignId: number;
  heroId: number | undefined;
  heroName: string;
  heroLevel?: number;
  turnCount?: number;
}) {
  const flow = useAppStore((s) => s.finishFlow);
  const setFlow = useAppStore((s) => s.setFinishFlow);
  const finish = useFinishCampaign(campaignId);
  const { toast } = useToast();

  async function doFinish() {
    try {
      await finish.mutateAsync();
      setFlow("victory");
    } catch (err) {
      const msg =
        err instanceof APIError && err.detail === "not_host"
          ? "Tylko gospodarz może zakończyć tę kampanię."
          : err instanceof Error
            ? err.message
            : "Nie udało się zakończyć przygody.";
      toast(msg, "danger");
      setFlow("idle");
    }
  }

  if (flow === "victory") {
    return (
      <VictoryScreen
        campaignId={campaignId}
        heroId={heroId}
        heroName={heroName}
        heroLevel={heroLevel}
        turnCount={turnCount}
        onClose={() => setFlow("idle")}
      />
    );
  }

  if (flow !== "confirm") return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-6" data-testid="finale-confirm-modal">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => !finish.isPending && setFlow("idle")} />
      <div className="relative z-[2] w-full max-w-[380px] rounded-xl border border-line-ember bg-surface p-6 text-center">
        <WarningCircle weight="fill" size={40} className="mx-auto text-ember-glow" />
        <h2 className="mt-3 font-serif text-title-lg font-semibold text-text">Zakończyć przygodę?</h2>
        <p className="mt-2 font-serif text-prose leading-relaxed text-text-2">
          Ta decyzja jest nieodwracalna — kampania zostanie zamknięta, a bohater wróci do kroniki jako
          zwycięzca.
        </p>
        <div className="mt-5 flex gap-2.5">
          <button
            type="button"
            disabled={finish.isPending}
            onClick={() => setFlow("idle")}
            className="flex-1 rounded-md border border-line bg-bg py-2.5 font-ui text-body font-semibold text-text-2 transition-colors hover:border-line-ember disabled:opacity-50"
          >
            Zostań
          </button>
          <button
            type="button"
            data-testid="finale-confirm-finish"
            disabled={finish.isPending}
            onClick={doFinish}
            className="flex flex-1 items-center justify-center gap-2 rounded-md border border-line-ember bg-gradient-to-br from-[#d1602c] to-ember py-2.5 font-ui text-body font-semibold text-white shadow-[0_0_16px_rgba(255,122,61,.4)] disabled:opacity-60"
          >
            {finish.isPending ? (
              <>
                <CircleNotch className="animate-spin" size={16} /> Kończę…
              </>
            ) : (
              <>
                <Flag weight="fill" size={16} /> Zakończ
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
