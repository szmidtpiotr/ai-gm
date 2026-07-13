// F-24/F-25/F-26 · arkusz akcji/czarów (#1236). Makieta: zar6-akcja.html.
// WALKA-T3 (#1353): brak paska tabów — sheet otwiera się w trybie z piguły composera
// (dubel usunięty). Tryb czar: lista grupowana po spell_type z nagłówkami PL + opis
// czaru pod nazwą (kości/mana jako meta). Surowy enum nie jest już nigdzie fallbackiem.
import {
  Sword,
  Sparkle,
  ArrowsInLineHorizontal,
  Shield,
  Fire,
  Heart,
  DropHalf,
  Wind,
  X,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { DefenseReaction } from "@/lib/types";
import { SPELL_TYPE_ORDER, spellTypeLabel } from "@/lib/spells";
import {
  DEFENSE_META,
  DEFENSE_ORDER,
  defenseReasonText,
  normalizeDefenseDetails,
  type DefenseOptionDetail,
} from "@/lib/combat-defense";

// WALKA-T2-FIX (#1359): ikona per reakcja (etykiety/opisy = wspólne combat-defense.ts).
const DEFENSE_ICON: Record<DefenseReaction, typeof Shield> = {
  dodge: Wind,
  shield_block: Shield,
  arcane_ward: Sparkle,
  mana_shield: DropHalf,
};

export interface SpellAction {
  key: string;
  label: string;
  mana_cost: number;
  rank: number;
  damage_die: string | null;
  heal_die: string | null;
  spell_type: string;
  description: string | null;
  affordable: boolean;
}

export type SheetMode = "attack" | "spell" | "move" | "defense";

export function ActionSheet({
  initialMode = "spell",
  spells,
  mana,
  maxMana,
  playerZone,
  targetName,
  busy,
  onAttack,
  onCast,
  onMove,
  onDeclare,
  onClose,
  defenseOptions = [],
  defenseOptionsDetailed,
}: {
  initialMode?: SheetMode;
  spells: SpellAction[];
  mana: number;
  maxMana: number;
  playerZone: "engaged" | "ranged";
  targetName: string | null;
  busy?: boolean;
  onAttack: () => void;
  onCast: (key: string) => void;
  onMove: () => void;
  onDeclare: (reaction: DefenseReaction) => void;
  onClose: () => void;
  defenseOptions?: string[];
  defenseOptionsDetailed?: DefenseOptionDetail[];
}) {
  // #1359: preferuj detailed (available+reason); fallback do available-only (stary backend).
  const defenseDetails = normalizeDefenseDetails(defenseOptionsDetailed, defenseOptions);
  const defenseByKey = new Map(defenseDetails.map((d) => [d.key, d]));
  // WALKA-T3: tryb jest ustalony przez pigułę composera — bez przełącznika w sheecie.
  const mode = initialMode;
  const hasMana = maxMana > 0;

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-[rgba(8,6,4,.6)]" />
      <div
        className="relative flex max-h-[88vh] w-full max-w-[520px] animate-slide-up flex-col rounded-t-xl border border-b-0 border-line bg-gradient-to-b from-[#211811] to-[#181009] pb-[max(14px,env(safe-area-inset-bottom))] shadow-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mb-1 mt-2.5 h-1 w-10 rounded-full bg-text-3 opacity-50" />
        <div className="flex items-center gap-2.5 border-b border-line-soft px-4 pb-3 pt-2">
          <div className="flex-1 font-serif text-title font-semibold">
            {mode === "spell" ? "Rzuć czar" : mode === "attack" ? "Atak" : mode === "move" ? "Ruch" : "Obrona"}
          </div>
          {hasMana && (
            <div className="flex items-center gap-2">
              <span className="font-ui text-[10px] font-bold uppercase tracking-[0.14em] text-mana">
                ◈ Mana
              </span>
              <span className="h-[7px] w-20 overflow-hidden rounded-[4px] bg-inset shadow-[inset_0_0_0_1px_var(--line-soft)]">
                <span
                  className="block h-full bg-gradient-to-r from-[#5f74e8] to-mana"
                  style={{ width: `${maxMana ? (mana / maxMana) * 100 : 0}%` }}
                />
              </span>
              <span className="font-mono text-label font-semibold text-text">
                {mana}/{maxMana}
              </span>
            </div>
          )}
          <button
            type="button"
            aria-label="Zamknij"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-md border border-line text-text-3"
          >
            <X size={15} />
          </button>
        </div>

        {/* zawartość trybu (tryb ustalony przez pigułę composera — bez tabów) */}
        <div className="min-h-0 overflow-y-auto px-3.5 pb-1 pt-2.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {mode === "attack" && (
            <Opt
              variant="atk"
              icon={<Sword weight="fill" size={19} />}
              name="Atak bronią"
              desc={targetName ? `cel: ${targetName}` : "wybierz cel w banerze"}
              cost={null}
              disabled={busy || !targetName}
              onClick={onAttack}
            />
          )}

          {mode === "spell" &&
            (spells.length === 0 ? (
              <Empty>Ta postać nie zna czarów bojowych.</Empty>
            ) : (
              groupSpellsByType(spells).map(([type, list]) => (
                <div key={type} className="mb-1">
                  <div className="mb-1.5 flex items-center gap-2.5 font-ui text-[10px] font-bold uppercase tracking-[0.16em] text-ember after:h-px after:flex-1 after:bg-line-soft after:content-['']">
                    {spellTypeLabel(type)}
                  </div>
                  {list.map((sp) => (
                    <Opt
                      key={sp.key}
                      variant={sp.heal_die ? "heal" : sp.spell_type === "attack" || sp.spell_type === "attack_aoe" ? "atk" : "eff"}
                      icon={spellIcon(sp)}
                      name={sp.label}
                      desc={(sp.description ?? "").trim()}
                      meta={spellMeta(sp)}
                      cost={sp.mana_cost}
                      rank={sp.rank}
                      affordable={sp.affordable}
                      disabled={busy || !sp.affordable}
                      onClick={() => onCast(sp.key)}
                    />
                  ))}
                </div>
              ))
            ))}

          {mode === "move" && (
            <Opt
              variant="eff"
              icon={<ArrowsInLineHorizontal size={19} />}
              name={playerZone === "engaged" ? "Cofnij się" : "Zbliż się"}
              desc={
                playerZone === "engaged"
                  ? "wyjdź na dystans (zjada turę)"
                  : "wejdź w zwarcie (zjada turę)"
              }
              cost={null}
              disabled={busy}
              onClick={onMove}
            />
          )}

          {mode === "defense" && (
            <>
              {/* #1359: renderuj WSZYSTKIE posiadane obrony; niedostępne = szare + powód. */}
              {DEFENSE_ORDER.filter((k) => defenseByKey.has(k)).map((k) => {
                const m = DEFENSE_META[k];
                const Icon = DEFENSE_ICON[k];
                const detail = defenseByKey.get(k)!;
                const reason = detail.available
                  ? null
                  : defenseReasonText(detail.reason);
                return (
                  <Opt
                    key={k}
                    variant="eff"
                    icon={<Icon weight="fill" size={19} />}
                    name={m.label}
                    desc={reason ? `niedostępne — ${reason}` : m.sheetDesc}
                    cost={null}
                    disabled={busy || !detail.available}
                    onClick={() => detail.available && onDeclare(k)}
                  />
                );
              })}
              {defenseByKey.size === 0 && (
                <div className="px-4 py-6 text-center font-ui text-[12.5px] text-text-3">
                  Brak wyszkolonych reakcji obronnych.
                  <br />
                  Cios wroga rozstrzyga pasywny unik.
                </div>
              )}
            </>
          )}
        </div>

        <div className="px-4 pt-1.5 text-center font-ui text-[11px] text-text-3">
          Akcja = <b className="text-text-2">Twoja tura</b> · Nat 1 = miscast
        </div>
      </div>
    </div>
  );
}

function spellIcon(sp: SpellAction) {
  if (sp.heal_die) return <Heart weight="fill" size={19} />;
  if (sp.spell_type === "attack_aoe") return <Fire weight="fill" size={19} />;
  if (sp.spell_type === "effect" || sp.spell_type === "defense")
    return <DropHalf weight="fill" size={19} />;
  return <Sparkle weight="fill" size={19} />;
}

// Meta wiersza czaru: kości obr./lecz. (mana pokazana osobno jako badge po prawej).
function spellMeta(sp: SpellAction): string {
  const parts: string[] = [];
  if (sp.damage_die) parts.push(`${sp.damage_die} obr.`);
  if (sp.heal_die) parts.push(`${sp.heal_die} lecz.`);
  return parts.join(" · ");
}

// Grupuj czary po spell_type w kolejności SPELL_TYPE_ORDER; puste sekcje pomijane.
// Nieznane typy (defensywnie) trafiają na koniec — nigdy nie gubimy czaru.
function groupSpellsByType(spells: SpellAction[]): Array<[string, SpellAction[]]> {
  const byType = new Map<string, SpellAction[]>();
  for (const sp of spells) {
    const t = sp.spell_type || "narrative";
    const arr = byType.get(t) ?? [];
    arr.push(sp);
    byType.set(t, arr);
  }
  const ordered: Array<[string, SpellAction[]]> = [];
  for (const t of SPELL_TYPE_ORDER) {
    const list = byType.get(t);
    if (list && list.length) ordered.push([t, list]);
  }
  for (const [t, list] of byType) {
    if (!SPELL_TYPE_ORDER.includes(t)) ordered.push([t, list]);
  }
  return ordered;
}

function Opt({
  variant,
  icon,
  name,
  desc,
  meta,
  cost,
  rank,
  affordable = true,
  disabled,
  onClick,
}: {
  variant: "atk" | "heal" | "eff";
  icon: React.ReactNode;
  name: string;
  desc: string;
  meta?: string;
  cost: number | null;
  rank?: number;
  affordable?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  const iconCls =
    variant === "atk"
      ? "border-line-ember bg-[rgba(255,122,61,.1)] text-ember-glow"
      : variant === "heal"
        ? "bg-[rgba(168,201,131,.12)] text-success border-line"
        : "bg-[rgba(130,167,199,.1)] text-mana border-line";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "mb-2 flex w-full items-center gap-3 rounded-md border border-line-soft bg-surface px-3 py-2.5 text-left transition-colors hover:border-line-ember disabled:cursor-not-allowed",
        disabled && "opacity-45",
      )}
    >
      <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-md border", iconCls)}>
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-ui text-body font-semibold text-text">{name}</span>
        {desc && (
          <span className="mt-0.5 block font-ui text-[11.5px] leading-snug text-text-2">
            {desc}
          </span>
        )}
        {meta && (
          <span className="mt-0.5 block font-mono text-[10.5px] text-text-3">{meta}</span>
        )}
      </span>
      {cost != null && (
        <span className="flex shrink-0 flex-col items-end gap-1">
          <span className={cn("font-mono text-label font-semibold", affordable ? "text-mana" : "text-danger")}>
            {cost}◈
          </span>
          {rank ? (
            <span className="rounded-[5px] border border-line-ember px-1.5 font-mono text-[9.5px] text-ember-glow">
              R{rank}
            </span>
          ) : !affordable ? (
            <span className="font-ui text-[9px] text-danger">za mało</span>
          ) : null}
        </span>
      )}
    </button>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-line-soft bg-surface px-3.5 py-3 font-serif text-label text-text-3">
      {children}
    </p>
  );
}
