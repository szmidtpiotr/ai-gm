// FE14 (#1263 / F-46) — zgłoszenie problemu wg makiety zar9-bug.html.
// FAB widoczny tylko dla testera (is_tester). Bottom-sheet: rodzaj (Błąd/Pomysł/Inne),
// „Co się stało?" (wymagane), „Jak powtórzyć?" (opcjonalne), auto-kontekst
// (kampania/tura/ekran), POST /bug-report.
// Draggable góra/dół (touch) — deltaY zapisany w localStorage.
import { useState, useRef } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Bug,
  ChatCircle,
  Lightbulb,
  Paperclip,
  PaperPlaneRight,
  X,
  type Icon,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";
import { useBugReport } from "@/hooks/useOverlays";
import type { ReportType } from "@/lib/overlays";
import { useToast } from "@/components/ui/toast";

const TYPES: { key: ReportType; label: string; icon: Icon; tone: string; onTone: string }[] = [
  { key: "bug", label: "Błąd", icon: Bug, tone: "text-danger", onTone: "border-line-danger bg-[rgba(232,96,79,0.08)] text-danger" },
  { key: "idea", label: "Pomysł", icon: Lightbulb, tone: "text-success", onTone: "border-line-ember bg-[rgba(255,122,61,0.1)] text-ember-glow" },
  { key: "other", label: "Inne", icon: ChatCircle, tone: "text-mana", onTone: "border-line-ember bg-[rgba(255,122,61,0.1)] text-ember-glow" },
];

const LS_FAB_DY = "aigm_fab_dy";

export function BugReportFab({
  campaignId,
  turnNumber,
  screen,
}: {
  campaignId?: number;
  turnNumber?: number;
  screen: string;
}) {
  const isTester = useAppStore((s) => s.currentUser?.isTester);
  const [open, setOpen] = useState(false);
  const [deltaY, setDeltaY] = useState<number>(() => {
    try { return parseInt(localStorage.getItem(LS_FAB_DY) ?? "0", 10) || 0; }
    catch { return 0; }
  });
  const dragRef = useRef<{ startTouchY: number; startDelta: number } | null>(null);

  if (!isTester) return null;

  function onTouchStart(e: React.TouchEvent) {
    dragRef.current = { startTouchY: e.touches[0].clientY, startDelta: deltaY };
  }
  function onTouchMove(e: React.TouchEvent) {
    if (!dragRef.current) return;
    const delta = e.touches[0].clientY - dragRef.current.startTouchY;
    // Clamp: nie wychodź za ekran (ok. -60 w górę, 400 w dół od pozycji startowej)
    setDeltaY(Math.max(-60, Math.min(400, dragRef.current.startDelta + delta)));
  }
  function onTouchEnd() {
    try { localStorage.setItem(LS_FAB_DY, String(deltaY)); } catch {}
    dragRef.current = null;
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Trigger asChild>
        <button
          type="button"
          aria-label="Zgłoś problem"
          title="Przeciągnij aby zmienić pozycję. Kliknij aby zgłosić."
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
          style={deltaY !== 0 ? { transform: `translateY(${deltaY}px)` } : undefined}
          // Mobile: pod paskiem przygody (nie zasłania przycisku wyślij w composerze).
          // Przeciągalne góra/dół — deltaY z localStorage.
          // Desktop: prawy dolny róg (composer wyśrodkowany, brak kolizji).
          className="fixed right-3 top-[calc(var(--sa-top)+3.75rem)] z-40 flex h-11 w-11 cursor-grab items-center justify-center rounded-full border border-line-ember bg-gradient-to-br from-[#d1602c] to-ember text-white shadow-[0_0_16px_rgba(255,122,61,0.4)] active:cursor-grabbing lg:right-4 lg:top-auto lg:bottom-6 lg:h-12 lg:w-12 lg:transform-none"
        >
          <Bug weight="fill" size={22} />
        </button>
      </DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/[.62] animate-fade-in" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed bottom-0 left-1/2 z-50 flex max-h-[92vh] w-full max-w-[480px] -translate-x-1/2 flex-col overflow-hidden rounded-t-[22px] border border-b-0 border-line bg-gradient-to-b from-[#211811] to-[#171009] shadow-modal animate-slide-up"
          style={{ paddingBottom: "max(16px, var(--sa-bottom))" }}
        >
          <ReportForm
            campaignId={campaignId}
            turnNumber={turnNumber}
            screen={screen}
            onClose={() => setOpen(false)}
          />
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function ReportForm({
  campaignId,
  turnNumber,
  screen,
  onClose,
}: {
  campaignId?: number;
  turnNumber?: number;
  screen: string;
  onClose: () => void;
}) {
  const [type, setType] = useState<ReportType>("bug");
  const [observation, setObservation] = useState("");
  const [reproduction, setReproduction] = useState("");
  const { toast } = useToast();
  const report = useBugReport();

  const ctxParts = [
    campaignId ? `kampania #${campaignId}` : null,
    turnNumber != null ? `tura ${turnNumber}` : null,
    `ekran ${screen}`,
  ].filter(Boolean);

  function submit() {
    const obs = observation.trim();
    if (!obs || report.isPending) return;
    report.mutate(
      {
        observation: obs,
        reproduction: reproduction.trim() || undefined,
        report_type: type,
        campaign_id: campaignId ?? null,
        js_errors: [],
      },
      {
        onSuccess: (r) => {
          toast(
            r.github_issue_url ? "Zgłoszono! Dziękujemy." : "Zgłoszenie zapisane. Dziękujemy!",
            "success",
          );
          onClose();
        },
        onError: (e) =>
          toast(e instanceof Error ? e.message : "Nie udało się wysłać zgłoszenia", "danger"),
      },
    );
  }

  return (
    <>
      <div className="mx-auto mb-1.5 mt-2.5 h-1 w-10 rounded-full bg-text-3/50" />

      {/* Nagłówek */}
      <header className="flex items-center gap-3 border-b border-line-soft px-[18px] pb-3.5 pt-1.5">
        <div className="flex h-[38px] w-[38px] flex-none items-center justify-center rounded-[10px] border border-line-ember bg-[rgba(255,122,61,0.1)] text-ember-glow">
          <Bug weight="fill" size={19} />
        </div>
        <div className="min-w-0 flex-1">
          <DialogPrimitive.Title className="font-serif text-title font-semibold text-text">
            Zgłoś problem
          </DialogPrimitive.Title>
          <p className="text-micro text-text-3">Pomóż ulepszyć Kroniki Kresów</p>
        </div>
        <button
          onClick={onClose}
          aria-label="Zamknij"
          className="flex h-9 w-9 flex-none items-center justify-center rounded-md border border-line bg-bg text-text-2 hover:border-line-ember hover:text-ember-glow"
        >
          <X size={16} />
        </button>
      </header>

      <div className="overflow-y-auto px-[18px] py-4 [scrollbar-width:thin]">
        {/* Rodzaj */}
        <Label>Rodzaj</Label>
        <div className="flex gap-[7px]">
          {TYPES.map((t) => {
            const on = type === t.key;
            const Ico = t.icon;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setType(t.key)}
                className={cn(
                  "flex flex-1 flex-col items-center gap-1.5 rounded-[11px] border px-1 py-2.5 text-micro font-semibold transition-colors",
                  on ? t.onTone : "border-line bg-surface text-text-2",
                )}
              >
                <Ico weight="fill" size={19} className={cn(!on && t.tone)} />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Co się stało? */}
        <Label>Co się stało?</Label>
        <textarea
          rows={3}
          value={observation}
          onChange={(e) => setObservation(e.target.value)}
          placeholder="Opisz co zaobserwowałeś…"
          className="w-full resize-none rounded-xl border border-line bg-surface px-3.5 py-3 font-ui text-body leading-relaxed text-text outline-none placeholder:text-text-3 focus:border-line-ember"
        />

        {/* Jak powtórzyć? */}
        <Label>Jak to powtórzyć? (opcjonalnie)</Label>
        <textarea
          rows={2}
          value={reproduction}
          onChange={(e) => setReproduction(e.target.value)}
          placeholder="Kroki do odtworzenia…"
          className="w-full resize-none rounded-xl border border-line bg-surface px-3.5 py-3 font-ui text-body leading-relaxed text-text outline-none placeholder:text-text-3 focus:border-line-ember"
        />

        {/* Auto-kontekst */}
        <div className="mt-3 flex items-center gap-2.5 rounded-[11px] border border-line-soft bg-surface px-3.5 py-2.5 text-micro text-text-2">
          <Paperclip weight="fill" size={15} className="flex-none text-success" />
          <span>
            Dołączę automatycznie:{" "}
            <b className="font-mono font-normal text-text">{ctxParts.join(" · ")}</b>
          </span>
        </div>
      </div>

      {/* Wyślij */}
      <div className="px-[18px] pb-1 pt-1.5">
        <button
          type="button"
          onClick={submit}
          disabled={!observation.trim() || report.isPending}
          className="flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-br from-[#d1602c] to-ember py-3.5 font-ui text-body font-semibold text-white shadow-[0_0_16px_rgba(255,122,61,0.3)] transition-[filter] hover:brightness-110 disabled:opacity-50"
        >
          <PaperPlaneRight weight="fill" size={18} />
          {report.isPending ? "Wysyłam…" : "Wyślij zgłoszenie"}
        </button>
      </div>
    </>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2 mt-3.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-text-3 first:mt-0">
      {children}
    </div>
  );
}
