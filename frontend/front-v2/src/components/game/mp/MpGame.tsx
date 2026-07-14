import { useEffect, useRef } from "react";
import { UsersThree } from "@phosphor-icons/react";
import { Composer } from "@/components/game/Composer";
import { VitalsRail } from "@/components/game/Vitals";
import { PartyChatPanel } from "./PartyChatPanel";
import { MpStatusBar } from "./MpStatusBar";
import { useMpRound } from "@/hooks/useMpRound";
import { useMpChat } from "@/hooks/useMpChat";
import { useMpStore, type MpBlock } from "@/store/mpStore";
import type { CharacterDetail } from "@/lib/types";
import type { Vitals } from "@/lib/game";
import { cn } from "@/lib/utils";

// FE15 (#1264) — ekran gry MP: log rund (dymki akcji graczy + narracja GM) + pasek
// statusu (timer + zgłoszenia) + composer oddający akcję rundy + party chat/whispery.
// Port zachowań z multiplayer_ui.js; realtime przez mpStore (poller w useMpRound/Chat).
export function MpGame({
  campaignId,
  character,
  vitals,
  stats,
}: {
  campaignId: number;
  character: CharacterDetail | undefined;
  vitals: Vitals;
  stats: Array<{ k: string; v: number }>;
}) {
  const characterId = character?.id ?? null;
  const characterName = character?.name ?? "Bohater";

  const round = useMpRound({ campaignId, characterId, characterName, enabled: true });
  const chat = useMpChat({ campaignId, characterName, enabled: true });

  const blocks = useMpStore((s) => s.blocks);
  const composerEnabled = useMpStore((s) => s.composerEnabled);
  const placeholder = useMpStore((s) => s.placeholder);
  const hostNote = useMpStore((s) => s.hostNote);
  const reset = useMpStore((s) => s.reset);

  // Wyczyść stan MP przy wyjściu z kampanii (odmontowanie).
  useEffect(() => () => reset(), [reset]);

  const endRef = useRef<HTMLDivElement>(null);
  // Pierwszy scroll po wejściu = natychmiastowy skok na ostatnią wiadomość,
  // kolejne (nowy blok) płynne.
  const didInitialScroll = useRef(false);
  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: didInitialScroll.current ? "smooth" : "auto",
      block: "end",
    });
    if (blocks.length > 0) didInitialScroll.current = true;
  }, [blocks.length]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <div className="mx-auto w-full max-w-[660px] px-4 pb-4 pt-4">
            <div className="mb-3 flex items-center justify-center gap-2 font-ui text-micro font-semibold uppercase tracking-[0.18em] text-text-3">
              <UsersThree weight="fill" className="text-ember" size={14} /> Sesja
              drużynowa
            </div>

            {hostNote && (
              <div className="mb-3.5 rounded-md border border-line-mech bg-[rgba(232,193,90,.05)] px-3.5 py-2.5 font-serif text-label italic text-text-2">
                <span className="mr-1.5 font-ui text-[10px] font-bold uppercase not-italic tracking-wider text-gold">
                  Szept GM
                </span>
                {hostNote}
              </div>
            )}

            {blocks.map((b) => (
              <MpBlockView key={b.id} b={b} />
            ))}
            {!composerEnabled && <Typing />}
            <div ref={endRef} />
          </div>
        </div>
        <VitalsRail
          v={vitals}
          stats={stats}
          locationLabel={character?.current_location_label}
        />
      </div>

      <div className="shrink-0">
        <MpStatusBar />
        <Composer
          onSend={round.submit}
          disabled={!composerEnabled}
          placeholder={placeholder}
          chips={[]}
          onChip={() => {}}
        />
      </div>

      <PartyChatPanel onSend={chat.send} />
    </div>
  );
}

function MpBlockView({ b }: { b: MpBlock }) {
  if (b.kind === "divider") {
    return (
      <div className="mx-auto my-3 flex max-w-[94%] items-center gap-2.5">
        <span className="h-px flex-1 bg-line-soft" />
        <span className="rounded-pill border border-line px-2.5 py-0.5 font-ui text-[10px] font-bold uppercase tracking-widest text-text-3">
          Runda {b.round}
        </span>
        <span className="h-px flex-1 bg-line-soft" />
      </div>
    );
  }
  if (b.kind === "gm") {
    return (
      <div className="mb-3.5 max-w-[94%] animate-fade-in rounded-[4px_14px_14px_14px] border border-line border-l-[3px] border-l-line-ember bg-gm-bubble px-4 py-3.5 shadow-float">
        <div className="mb-1.5 font-ui text-micro font-bold uppercase tracking-[0.18em] text-ember">
          Mistrz Gry
        </div>
        <div className="whitespace-pre-wrap font-serif text-prose leading-[1.72] text-text">
          {b.text}
        </div>
      </div>
    );
  }
  // action
  if (b.mine) {
    return (
      <div className="mb-3.5 ml-auto max-w-[82%] animate-fade-in rounded-[14px_4px_14px_14px] border border-line-ember border-r-[3px] border-r-ember bg-player-card px-3.5 py-2.5 shadow-float">
        <div className="mb-1 text-right font-ui text-micro font-bold uppercase tracking-[0.2em] text-ember-glow">
          Twoja akcja
        </div>
        <div className="text-right font-serif text-label italic text-text">{b.text}</div>
      </div>
    );
  }
  return (
    <div
      className={cn(
        "mb-3.5 mr-auto max-w-[82%] animate-fade-in rounded-[4px_14px_14px_14px]",
        "border border-line bg-mech-card px-3.5 py-2.5 opacity-90",
      )}
    >
      <div className="mb-1 font-ui text-micro font-bold uppercase tracking-[0.2em] text-text-3">
        {b.name}
      </div>
      <div className="font-serif text-label italic text-text-2">{b.text}</div>
    </div>
  );
}

function Typing() {
  return (
    <div className="mb-2.5 flex items-center gap-2.5 pl-1 font-serif text-label italic text-ember-glow">
      <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-ember shadow-[0_0_8px_rgba(255,122,61,.8)]" />
      Mistrz Gry zapisuje dalszy ciąg…
    </div>
  );
}
