// FE10 (#1237) — F-27 Level-up (makieta zar9-levelup). Przyrosty (HP/mana/pkt
// tajemny) + rozdział punktu cechy (PD) + odblokowane czary. Wywoływany
// zdarzeniem silnika: wzrost sheet.level (próg XP przekroczony).
import { useState } from "react";
import { Medal, Sparkle, CheckCircle } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

export interface StatPick {
  k: string;
  v: number;
  newV: number;
  affordable: boolean;
}

export function LevelUpModal({
  level,
  hpGain,
  manaGain,
  arcaneGain,
  stats,
  pointsAvailable,
  unlockedSpells,
  committing,
  onConfirm,
}: {
  level: number;
  hpGain: number;
  manaGain: number;
  arcaneGain: number;
  stats: StatPick[];
  pointsAvailable: number;
  unlockedSpells: Array<{ label: string; tier: number }>;
  committing: boolean;
  onConfirm: (pickedStat: string | null) => void;
}) {
  const [picked, setPicked] = useState<string | null>(null);
  const canPick = pointsAvailable > 0;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-5"
      style={{
        background:
          "radial-gradient(60% 45% at 50% 30%, rgba(232,193,90,.16), transparent 60%), rgba(8,6,4,.82)",
      }}
      data-testid="modal-levelup"
    >
      <div className="max-h-[92vh] w-full max-w-[410px] overflow-y-auto rounded-xl border border-line-mech bg-gradient-to-b from-[#241a11] to-[#170f09] shadow-modal [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {/* nagłówek */}
        <div className="relative overflow-hidden border-b border-line-soft bg-gradient-to-b from-[rgba(232,193,90,.14)] to-transparent px-5 pb-4 pt-6 text-center">
          <div
            className="pointer-events-none absolute inset-0 opacity-80"
            style={{
              background:
                "conic-gradient(from 0deg at 50% 40%, transparent, rgba(232,193,90,.08) 10%, transparent 20%, rgba(232,193,90,.06) 30%, transparent 40%)",
            }}
          />
          <Medal weight="fill" size={56} className="relative mx-auto text-gold drop-shadow-[0_0_22px_rgba(232,193,90,.55)]" />
          <div className="relative mt-2.5 font-ui text-[11px] font-bold uppercase tracking-[0.3em] text-gold-glow">
            Awans
          </div>
          <div className="relative mt-1 font-serif text-title-lg font-semibold text-text">
            Poziom <b className="text-gold-glow">{level}</b>
          </div>
        </div>

        {/* przyrosty */}
        <div className="flex border-b border-line-soft px-3 py-3.5">
          <Gain v={`+${hpGain}`} k="Zdrowie" />
          {manaGain > 0 && <Gain v={`+${manaGain}`} k="Mana" />}
          {arcaneGain > 0 && <Gain v={`+${arcaneGain}`} k="Pkt tajemny" />}
        </div>

        {/* rozdział punktu cechy */}
        <div className="px-[18px] pb-1.5 pt-4">
          <div className="mb-[11px] flex items-center gap-[9px] font-ui text-[10px] font-bold uppercase tracking-[0.18em] text-ember">
            Rozdziel punkt cechy <span className="font-mono text-ember-glow">{pointsAvailable}</span>
            <span className="h-px flex-1 bg-line-soft" />
          </div>
          {!canPick && (
            <div className="mb-2 font-ui text-[11.5px] text-text-3">
              Brak PD na rozdział — zdobądź doświadczenie, potem rozwiń cechy w zakładce Postać.
            </div>
          )}
          <div className="grid grid-cols-2 gap-[7px]">
            {stats.map((s) => {
              const sel = picked === s.k;
              const selectable = canPick && s.affordable;
              return (
                <button
                  key={s.k}
                  type="button"
                  disabled={!selectable || committing}
                  onClick={() => setPicked(sel ? null : s.k)}
                  data-testid={`levelup-stat-${s.k}`}
                  className={cn(
                    "flex items-center gap-2 rounded-[10px] border px-[11px] py-[9px] text-left",
                    sel
                      ? "border-line-mech bg-gradient-to-b from-[rgba(232,193,90,.1)] to-[#1e1811]"
                      : "border-line bg-[#1e1811]",
                    !selectable && "opacity-45",
                  )}
                >
                  <span className="w-[30px] font-mono text-[11px] font-semibold text-text-2">{s.k}</span>
                  {sel ? (
                    <span className="ml-auto font-mono text-[11px] text-success">
                      {s.v}→{s.newV}
                    </span>
                  ) : (
                    <span className="ml-auto font-mono text-[14px] font-semibold text-text">{s.v}</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* odblokowane czary */}
        {unlockedSpells.map((sp) => (
          <div
            key={sp.label}
            className="mx-[18px] mt-3.5 flex items-center gap-[11px] rounded-md border border-line-ember bg-[rgba(255,122,61,.06)] px-3.5 py-3"
          >
            <span className="flex h-[38px] w-[38px] flex-none items-center justify-center rounded-[10px] border border-line-ember bg-[rgba(255,122,61,.12)] text-ember-glow">
              <Sparkle weight="fill" size={19} />
            </span>
            <div>
              <div className="font-ui text-[13.5px] font-semibold text-text">Nowy czar w zasięgu</div>
              <div className="mt-px font-ui text-[11px] text-text-2">
                {sp.label} (Tier {sp.tier}) — wydaj punkt tajemny w zakładce Czary
              </div>
            </div>
          </div>
        ))}

        {/* potwierdź */}
        <div className="px-[18px] pb-[18px] pt-4">
          <button
            type="button"
            disabled={committing}
            onClick={() => onConfirm(picked)}
            data-testid="levelup-confirm"
            className="flex w-full items-center justify-center gap-2 rounded-md bg-gradient-to-br from-gold to-[#c9962e] py-3.5 font-ui text-[15px] font-bold text-[#1a1206] disabled:opacity-60"
          >
            <CheckCircle weight="fill" size={18} /> {committing ? "Zapisuję…" : "Potwierdź awans"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Gain({ v, k }: { v: string; k: string }) {
  return (
    <div className="flex-1 border-r border-line-soft text-center font-mono last:border-r-0">
      <div className="text-[16px] font-semibold text-success">{v}</div>
      <div className="mt-[3px] font-ui text-[9px] uppercase tracking-[0.1em] text-text-3">{k}</div>
    </div>
  );
}
