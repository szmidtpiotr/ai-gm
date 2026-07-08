import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";
import type { LogBlock } from "@/lib/game";
import type { RollCardData } from "@/lib/types";
import { RollCard } from "./RollCard";

// F-51 log narracji (sekcja 6): dymki gracza/GM/system, karty rzutów, „GM pisze…",
// fade-in + auto-scroll. Stare rzuty (nie ostatni) zwijane do jednej linii.
export function NarrationLog({
  blocks,
  pendingRoll,
  combatRolls,
  typing,
  heroName,
  className,
}: {
  blocks: LogBlock[];
  pendingRoll?: RollCardData | null;
  /** Efemeryczne karty rzutów walki (F-52) dopisywane pod narracją w trakcie walki. */
  combatRolls?: RollCardData[];
  typing?: boolean;
  heroName?: string;
  className?: string;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  // Auto-scroll na dół gdy dochodzi nowy blok / pojawia się „GM pisze…".
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [blocks.length, typing, pendingRoll, combatRolls?.length]);

  const lastRollIdx = lastIndex(blocks, (b) => b.kind === "roll");

  return (
    <div className={cn("mx-auto w-full max-w-[660px] px-4 pb-4 pt-4", className)}>
      {blocks.map((b, i) => {
        switch (b.kind) {
          case "gm":
            return <GmBubble key={b.id} turn={b.turn} heroName={heroName} text={b.text} />;
          case "player":
            return <PlayerAction key={b.id} text={b.text} />;
          case "system":
            return <SystemBand key={b.id} text={b.text} />;
          case "completion":
            return <CompletionBand key={b.id} text={b.text} />;
          case "gold":
            return <GoldBubble key={b.id} delta={b.delta} label={b.label} />;
          case "roll":
            return (
              <RollCard key={b.id} roll={b.roll} collapsible={i !== lastRollIdx} />
            );
        }
      })}

      {combatRolls?.map((r, i) => (
        <RollCard key={`c-${i}`} roll={r} collapsible={i !== combatRolls.length - 1} />
      ))}
      {pendingRoll && <RollCard roll={pendingRoll} />}
      {typing && <Typing />}

      <div ref={endRef} />
    </div>
  );
}

function lastIndex<T>(arr: T[], pred: (x: T) => boolean): number {
  for (let i = arr.length - 1; i >= 0; i--) if (pred(arr[i])) return i;
  return -1;
}

// Narracja GM — lewo, ciepłe tło, serif. Nagłówek „MISTRZ GRY · tura N".
function GmBubble({ turn, heroName, text }: { turn: number; heroName?: string; text: string }) {
  const showName = useAppStore((s) => s.gamePrefBubbleName);
  const showTurn = useAppStore((s) => s.gamePrefBubbleTurn);
  return (
    <div className="mb-3.5 max-w-[94%] animate-fade-in rounded-[4px_14px_14px_14px] border border-line border-l-[3px] border-l-line-ember bg-gm-bubble px-4 py-3.5 shadow-float">
      {showName && (
        <div className="mb-1.5 flex items-center gap-2 font-ui text-micro font-bold uppercase tracking-[0.18em] text-ember">
          Mistrz Gry
          {showTurn && <span className="font-medium text-text-3">· tura {turn}</span>}
        </div>
      )}
      <Prose text={text} heroName={heroName} />
    </div>
  );
}

// Akcja gracza — prawo, ember, serif italic. Znak „◀".
function PlayerAction({ text }: { text: string }) {
  const showName = useAppStore((s) => s.gamePrefBubbleName);
  return (
    <div className="mb-3.5 ml-auto max-w-[82%] animate-fade-in rounded-[14px_4px_14px_14px] border border-line-ember border-r-[3px] border-r-ember bg-gradient-to-br from-[rgba(255,122,61,.2)] to-[rgba(255,122,61,.08)] bg-player-card px-3.5 py-2.5 shadow-float">
      {showName && (
        <div className="mb-1 flex items-center justify-end gap-1.5 font-ui text-micro font-bold uppercase tracking-[0.2em] text-ember-glow">
          Twoja akcja
          <span className="text-[7px] text-ember">◀</span>
        </div>
      )}
      <div className="text-right font-serif text-label italic text-text">{text}</div>
    </div>
  );
}

// Systemowe — pełna szer., wyśrodk., kreskowany obrys line-mech, mono, złoto.
function SystemBand({ text }: { text: string }) {
  return (
    <div className="mx-auto mb-3.5 flex max-w-[94%] items-center justify-center gap-2 rounded-md border border-dashed border-line-mech bg-[rgba(232,193,90,.04)] px-3 py-1.5 font-mono text-micro text-gold">
      {text}
    </div>
  );
}

// Transakcja złotem — ikona monet, złote tło, mono. Tylko sukcesy (delta < 0 = wydane).
function GoldBubble({ delta, label }: { delta: number; label: string }) {
  const sign = delta > 0 ? "+" : "";
  return (
    <div className="mx-auto mb-3.5 flex max-w-[94%] items-center justify-center gap-2 rounded-md border border-gold/40 bg-[rgba(232,193,90,.06)] px-3 py-1.5 font-mono text-micro text-gold animate-fade-in">
      <span>💰</span>
      <span>{sign}{delta} zł</span>
      {label && <span className="text-text-3">— {label}</span>}
    </div>
  );
}

// Ukończenie questa/beatu — zielona ramka, ✓ prefix, mono.
function CompletionBand({ text }: { text: string }) {
  return (
    <div className="mx-auto mb-3.5 flex max-w-[94%] items-center justify-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/5 px-3 py-1.5 font-mono text-micro text-emerald-400 animate-fade-in">
      {text}
    </div>
  );
}

// „GM pisze…" — tląca się kropka + kursywa.
function Typing() {
  return (
    <div className="mb-2.5 flex items-center gap-2.5 pl-1 font-serif text-label italic text-ember-glow">
      <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-ember shadow-[0_0_8px_rgba(255,122,61,.8)]" />
      Mistrz Gry zapisuje dalszy ciąg…
    </div>
  );
}

// Proza serif. Wyróżnienia (wg system_prompt §FORMAT):
//   *kursywa*        → <em> ember-glow (nacisk),
//   — kwestia NPC    → linia dialogu: złoto + kursywa + lewy obrys (mowa),
//   „tekst pisany"   → cytat pisany: gold-glow kursywa (listy/inskrypcje).
function Prose({ text, heroName }: { text: string; heroName?: string }) {
  const html = renderNarration(text, heroName);
  return (
    <div
      className="font-serif text-prose leading-[1.72] text-text [&_.para]:mb-2 [&_.para:last-child]:mb-0 [&_em]:italic [&_em]:text-ember-glow [&_.speech]:my-1.5 [&_.speech]:block [&_.speech]:border-l-2 [&_.speech]:border-l-line-mech [&_.speech]:pl-2.5 [&_.speech]:italic [&_.speech]:text-gold [&_.quote]:italic [&_.quote]:text-gold-glow"
      // Tylko własny escape + kontrolowane <em>/<span> — bez surowego HTML z LLM.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// *gwiazdki* i «cytaty» → <em>. Wejście musi być już escapowane.
function renderEmphasis(s: string): string {
  s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  s = s.replace(/«([^»]+)»/g, "«<em>$1</em>»");
  return s;
}

// Render narracji akapit po akapicie z wyróżnieniem dialogów kolorem.
function renderNarration(text: string, _heroName?: string): string {
  return text
    .split(/\n+/)
    .map((para) => {
      const t = para.trim();
      if (!t) return "";
      const html = renderEmphasis(escapeHtml(t));
      // Kwestia NPC (polska konwencja: myślnik na początku) → linia mowy.
      if (/^[—–]\s/.test(t)) {
        return `<span class="speech">${html}</span>`;
      }
      // Inline cytat pisany „..." → wyróżnienie cytatu.
      const withQuotes = html.replace(
        /„([^”]{1,300})”/g,
        '<span class="quote">„$1”</span>',
      );
      return `<span class="para block">${withQuotes}</span>`;
    })
    .filter(Boolean)
    .join("");
}
