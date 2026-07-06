// FE14 (#1263 / F-33) — recap „Poprzednio w Twojej przygodzie…".
// Brak makiety ŻAR → zachowanie 1:1 ze starego front/ (U19 #571) na tokenach ŻAR.
// Auto-pokaz przy wejściu, gdy backend zwróci should_show (>24h przerwy), raz na
// kampanię w sesji. Read-only: streszczenie + ostatnie tury + aktywne zadania.
import { useEffect, useRef, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { BookOpenText } from "@phosphor-icons/react";
import { useRecap } from "@/hooks/useOverlays";
import { recapGapLabel } from "@/lib/overlays";

export function RecapOverlay({ campaignId }: { campaignId?: number }) {
  const recap = useRecap(campaignId);
  const [open, setOpen] = useState(false);
  const shownFor = useRef<number | null>(null);

  const data = recap.data;
  useEffect(() => {
    if (!campaignId || !data?.should_show) return;
    if (shownFor.current === campaignId) return;
    shownFor.current = campaignId;
    setOpen(true);
  }, [campaignId, data?.should_show]);

  if (!data) return null;

  const turns = (data.recent_turns ?? []).slice().reverse();
  const quests = data.active_quests ?? [];
  const hasBody = !!data.summary || turns.length > 0 || quests.length > 0;

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/[.66] animate-fade-in" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-[calc(100%-2rem)] max-w-[520px] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-line-ember bg-gradient-to-b from-[#211811] to-[#171009] shadow-modal animate-fade-in"
        >
          {/* Nagłówek */}
          <header className="flex items-center gap-3 border-b border-line px-5 py-4">
            <div className="flex h-11 w-11 flex-none items-center justify-center rounded-xl border border-line-ember bg-[rgba(255,122,61,0.1)] text-ember-glow">
              <BookOpenText weight="fill" size={22} />
            </div>
            <div className="min-w-0">
              <DialogPrimitive.Title className="font-serif text-title font-semibold text-text">
                Poprzednio w Twojej przygodzie…
              </DialogPrimitive.Title>
              <p className="text-micro text-text-3">{recapGapLabel(data.hours_since_last)}</p>
            </div>
          </header>

          {/* Treść */}
          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-4 [scrollbar-width:thin]">
            {!hasBody && (
              <p className="font-serif text-prose italic text-text-3">
                Brak zapisanych wspomnień — po prostu graj dalej.
              </p>
            )}

            {data.summary && (
              <Section title="Streszczenie">
                <p className="font-serif text-prose leading-relaxed text-text-2">{data.summary}</p>
              </Section>
            )}

            {turns.length > 0 && (
              <Section title="Ostatnio wydarzyło się">
                <div className="space-y-3">
                  {turns.map((t) => (
                    <div key={t.turn_number} className="rounded-lg border border-line-soft bg-surface px-3.5 py-2.5">
                      <div className="mb-1 font-mono text-[10px] uppercase tracking-wide text-text-3">
                        Tura {t.turn_number}
                      </div>
                      {t.player && (
                        <p className="mb-1 font-ui text-label text-ember-glow">{t.player}</p>
                      )}
                      {t.gm && (
                        <p className="font-serif text-body leading-relaxed text-text-2">{t.gm}</p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {quests.length > 0 && (
              <Section title="Aktywne zadania">
                <ul className="space-y-1.5">
                  {quests.map((q, i) => (
                    <li key={i} className="font-serif text-body text-text-2">
                      <strong className="text-text">{q.title || "Zadanie"}</strong>
                      {q.narrative ? ` — ${q.narrative}` : ""}
                    </li>
                  ))}
                </ul>
              </Section>
            )}
          </div>

          {/* Kontynuuj */}
          <div className="border-t border-line px-5 py-3.5">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="flex w-full items-center justify-center rounded-xl bg-gradient-to-br from-[#d1602c] to-ember py-3.5 font-ui text-body font-semibold text-white shadow-[0_0_16px_rgba(255,122,61,0.3)] transition-[filter] hover:brightness-110"
            >
              Kontynuuj
            </button>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.14em] text-text-3">{title}</h3>
      {children}
    </div>
  );
}
