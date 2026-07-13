// SF10 reakcja (#1236 / #633) — okno uniku/bloku/bariery/tarczy many. Makieta: zar6-reakcja.html.
// Timer-ring odlicza; brak wyboru = auto „Przyjmij cios" (parytet z silnikiem, choice
// default „take"). Liczba obrażeń CELOWO ukryta — wybór pozostaje zakładem (decyzja Piotra).
// WALKA-T2-FIX (#1359): niedostępne reakcje (np. Tarcza Many bez many) są WYSZARZONE z powodem,
// nie ukryte — etykiety/opisy ze wspólnego lib/combat-defense.ts (parytet z pigułą Obrona).
import { useEffect, useRef, useState } from "react";
import { Wind, ShieldCheck, HandPalm, PawPrint, Sparkle, ShieldStar } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { DefenseReaction } from "@/lib/types";
import {
  DEFENSE_META,
  DEFENSE_ORDER,
  DEFENSE_KEY_TO_CHOICE,
  defenseReasonText,
  normalizeDefenseDetails,
  type DefenseOptionDetail,
} from "@/lib/combat-defense";

export type ReactionChoice = "take" | "dodge" | "block" | "ward" | "mana";

export interface ReactionData {
  enemyName: string;
  options: string[]; // DOSTĘPNE klucze (available-only) — wstecznie zgodne
  optionsDetailed?: DefenseOptionDetail[]; // #1359: wszystkie + available + reason (wyszarzanie)
  attackRoll?: number | null;
  playerDefense?: number | null;
}

// #1359: ikona per reakcja (etykieta/opis = wspólne combat-defense.ts).
const REACTION_ICON: Record<DefenseReaction, typeof Wind> = {
  dodge: Wind,
  shield_block: ShieldCheck,
  arcane_ward: Sparkle,
  mana_shield: ShieldStar,
};
// Wariant kolorystyczny Choice per reakcja.
const REACTION_VARIANT: Record<DefenseReaction, "dodge" | "block" | "ward" | "mana"> = {
  dodge: "dodge",
  shield_block: "block",
  arcane_ward: "ward",
  mana_shield: "mana",
};

const WINDOW_S = 8; // parytet z front/ (combat_ui.js: left=8 → auto-take)
const RING_LEN = 113; // 2πr, r=18

export function ReactionModal({
  data,
  onChoose,
}: {
  data: ReactionData;
  // #1358: drugi arg `auto` = wybór z wygaśnięcia okna (timeout), nie z kliknięcia.
  onChoose: (c: ReactionChoice, auto?: boolean) => void;
}) {
  const [left, setLeft] = useState(WINDOW_S);
  const firedRef = useRef(false);

  function fire(c: ReactionChoice, auto = false) {
    if (firedRef.current) return;
    firedRef.current = true;
    onChoose(c, auto);
  }

  useEffect(() => {
    const iv = window.setInterval(() => {
      setLeft((v) => {
        if (v <= 1) {
          window.clearInterval(iv);
          fire("take", true); // brak wyboru → przyjmij cios (#1358: oznacz jako timeout)
          return 0;
        }
        return v - 1;
      });
    }, 1000);
    return () => window.clearInterval(iv);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const offset = RING_LEN * (1 - left / WINDOW_S);
  // #1359: wszystkie posiadane reakcje (available + reason); fallback do available-only.
  const details = normalizeDefenseDetails(data.optionsDetailed, data.options);
  const detailByKey = new Map(details.map((d) => [d.key, d]));
  const ownedDefenses = DEFENSE_ORDER.filter((k) => detailByKey.has(k));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-5"
      style={{
        background:
          "radial-gradient(60% 45% at 50% 32%, rgba(232,96,79,.14), transparent 65%), rgba(8,6,4,.82)",
      }}
    >
      <div className="w-full max-w-[420px] overflow-hidden rounded-xl border border-line-danger bg-gradient-to-b from-[#241812] to-[#1a120c] shadow-modal">
        {/* nagłówek + timer ring */}
        <div className="relative border-b border-[rgba(232,96,79,.2)] bg-gradient-to-b from-[rgba(232,96,79,.12)] to-transparent px-4 pb-3.5 pt-4 text-center">
          <div className="absolute right-4 top-3.5 h-10 w-10">
            <svg width="40" height="40" viewBox="0 0 40 40" className="-rotate-90">
              <circle
                cx="20"
                cy="20"
                r="18"
                fill="none"
                strokeWidth="4"
                className="stroke-[rgba(242,232,216,.1)]"
              />
              <circle
                cx="20"
                cy="20"
                r="18"
                fill="none"
                strokeWidth="4"
                strokeLinecap="round"
                className="stroke-danger transition-[stroke-dashoffset] duration-1000 ease-linear"
                strokeDasharray={RING_LEN}
                strokeDashoffset={offset}
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center font-mono text-label font-semibold text-danger-glow">
              {left}
            </span>
          </div>
          <div className="font-ui text-[10px] font-bold uppercase tracking-[0.24em] text-danger-glow">
            Reakcja — wróg atakuje
          </div>
          <div className="mt-1.5 flex items-center justify-center gap-2 font-serif text-title font-semibold">
            <PawPrint weight="fill" size={19} className="text-danger" />
            {data.enemyName} atakuje!
          </div>
        </div>

        {/* podsumowanie nadchodzącego ciosu (bez liczby obrażeń — zakład) */}
        <div className="mx-4 mt-3.5 overflow-hidden rounded-md border border-line bg-mech-card font-mono">
          <div className="flex">
            <IncCell k="Rzut" v={fmtNum(data.attackRoll)} />
            <IncCell k="Twoja obr." v={fmtNum(data.playerDefense)} />
            <IncCell k="Cios" v="?" danger />
          </div>
        </div>

        {/* wybory — #1359: posiadane reakcje; niedostępne wyszarzone z powodem */}
        <div className="flex flex-col gap-2.5 px-4 pb-4 pt-1">
          {ownedDefenses.map((k) => {
            const meta = DEFENSE_META[k];
            const Icon = REACTION_ICON[k];
            const detail = detailByKey.get(k)!;
            const reason = detail.available ? null : defenseReasonText(detail.reason);
            return (
              <Choice
                key={k}
                variant={REACTION_VARIANT[k]}
                icon={<Icon weight="fill" size={21} />}
                name={meta.label}
                desc={reason ? `Niedostępne — ${reason}.` : meta.reactionDesc}
                meta={meta.reactionMeta}
                disabled={!detail.available}
                onClick={() => fire(DEFENSE_KEY_TO_CHOICE[k])}
              />
            );
          })}
          <Choice
            variant="take"
            icon={<HandPalm weight="fill" size={21} />}
            name="Przyjmij cios"
            desc="Bez rzutu — obrywasz pełne, ale zachowujesz akcję."
            meta="pełny cios"
            onClick={() => fire("take")}
          />
        </div>
        <div className="px-4 pb-3.5 text-center font-ui text-[11px] text-text-3">
          Brak wyboru za <b className="text-danger-glow">{left}s</b> → przyjmujesz cios
        </div>
      </div>
    </div>
  );
}

function fmtNum(v: number | null | undefined): string {
  return v == null || !Number.isFinite(v) ? "—" : String(v);
}

function IncCell({ k, v, danger }: { k: string; v: string; danger?: boolean }) {
  return (
    <div
      className={cn(
        "flex-1 border-r border-[rgba(242,232,216,.08)] px-1 py-2 text-center last:border-r-0",
        danger && "bg-[rgba(232,96,79,.12)]",
      )}
    >
      <div className="text-[8.5px] uppercase tracking-wider text-text-3">{k}</div>
      <div
        className={cn(
          "mt-0.5 text-label font-medium text-text",
          danger && "text-danger-glow",
        )}
      >
        {v}
      </div>
    </div>
  );
}

function Choice({
  variant,
  icon,
  name,
  desc,
  meta,
  disabled = false,
  onClick,
}: {
  variant: "dodge" | "block" | "ward" | "mana" | "take";
  icon: React.ReactNode;
  name: string;
  desc: string;
  meta: React.ReactNode;
  disabled?: boolean;
  onClick: () => void;
}) {
  // #1324/#1325: bariera i tarcza many dzielą paletę many (niebieski) — obie płacą maną.
  const tint =
    variant === "take"
      ? "border-[rgba(232,96,79,.3)]"
      : variant === "block"
        ? "border-line-ember"
        : variant === "ward" || variant === "mana"
          ? "border-[rgba(130,167,199,.35)]"
          : "border-line";
  const iconCls =
    variant === "take"
      ? "bg-[rgba(232,96,79,.12)] text-danger-glow"
      : variant === "block"
        ? "bg-[rgba(255,122,61,.12)] text-ember-glow"
        : "bg-[rgba(130,167,199,.14)] text-mana";
  const metaCls =
    variant === "take"
      ? "text-danger"
      : variant === "block"
        ? "text-ember-glow"
        : "text-mana";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex w-full items-center gap-3 rounded-md border bg-surface px-3.5 py-3 text-left transition-colors hover:border-ember",
        tint,
        disabled && "cursor-not-allowed opacity-45 hover:border-[inherit]",
      )}
    >
      <span
        className={cn(
          "flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-md",
          iconCls,
        )}
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-ui text-[15.5px] font-bold text-text">{name}</span>
        <span className="mt-0.5 block font-ui text-[12px] text-text-2">{desc}</span>
      </span>
      <span className={cn("shrink-0 text-right font-mono text-[11px]", metaCls)}>
        {meta}
      </span>
    </button>
  );
}
